#!/usr/bin/env python3
"""Select high-error persistent planar Regions and refine only their interiors."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fit_plane_ransac(points, threshold, iterations, seed):
    if len(points) < 3:
        return None, np.zeros(len(points), dtype=bool)
    rng = np.random.default_rng(seed)
    best = np.zeros(len(points), dtype=bool)
    for _ in range(iterations):
        sample = points[rng.choice(len(points), size=3, replace=False)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        norm = np.linalg.norm(normal)
        if norm < 1e-10:
            continue
        normal /= norm
        offset = -float(np.dot(normal, sample[0]))
        inliers = np.abs(points @ normal + offset) <= threshold
        if inliers.sum() > best.sum():
            best = inliers
    if best.sum() < 3:
        return None, best
    inlier_points = points[best]
    center = inlier_points.mean(axis=0)
    _, _, vt = np.linalg.svd(inlier_points - center, full_matrices=False)
    normal = vt[-1]
    normal /= np.linalg.norm(normal)
    offset = -float(np.dot(normal, center))
    best = np.abs(points @ normal + offset) <= threshold
    return (normal, offset), best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1a-artifacts", type=Path, required=True)
    parser.add_argument("--e2a-artifacts", type=Path, required=True)
    parser.add_argument("--e3a-artifacts", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"refusing to mix with existing E4a artifacts: {args.output}")
    started = time.perf_counter()
    e1a, e2a, e3a = (p.resolve() for p in (args.e1a_artifacts, args.e2a_artifacts, args.e3a_artifacts))
    config = json.loads(args.config.read_text(encoding="utf-8"))
    export_path = e1a / "pointmaps/export_manifest.json"
    tagging_path = e2a / "keyframes_manifest.json"
    temporal_path = e3a / "temporal_regions.json"
    export, tagging, temporal = (json.loads(p.read_text(encoding="utf-8")) for p in (export_path, tagging_path, temporal_path))
    if tagging["source_e1a_export_manifest_sha256"] != sha256(export_path):
        parser.error("E2a tags do not reference this E1a export manifest")
    if temporal["source_manifests"]["e1a_sha256"] != sha256(export_path) or temporal["source_manifests"]["e2a_sha256"] != sha256(tagging_path):
        parser.error("E3a associations do not reference the supplied E1a/E2a manifests")
    if len(export["keyframes"]) != len(tagging["keyframes"]) or len(export["keyframes"]) != temporal["keyframe_count"]:
        parser.error("E1a/E2a/E3a Keyframe counts differ")

    args.output.mkdir(parents=True, exist_ok=True)
    spacing = float(temporal["global_median_local_spacing_world_units"])
    radius = float(temporal["association_radius_world_units"])
    threshold_ratio = float(config["frozen_error_threshold_spacing_ratio"])
    mask_archive = np.load(e3a / "region_masks.npz", allow_pickle=False)
    keyframes = []
    for record, tagged in zip(export["keyframes"], tagging["keyframes"]):
        if record["frame_id"] != tagged["frame_id"]:
            parser.error("E1a/E2a Keyframe ordering differs")
        point_path = e1a / "pointmaps" / record["file"]
        score_path = e2a / tagged["result_dir"] / "semantic_scores.npz"
        if sha256(point_path) != record["sha256"] or sha256(score_path) != tagged["semantic_scores_sha256"]:
            parser.error("E1a pointmap or E2a semantic-score hash mismatch")
        with np.load(point_path, allow_pickle=False) as data:
            point_data = {name: data[name].copy() for name in data.files}
        with np.load(score_path, allow_pickle=False) as sem:
            labels = sem["label_id"].astype(np.uint8)
            label_names = [str(x) for x in sem["labels"].tolist()]
        ordinal = int(record["ordinal"])
        region_ids = mask_archive[f"region_ids_kf_{ordinal:03d}"].astype(np.int32)
        valid = point_data["valid"].astype(bool) & np.isfinite(point_data["point_world"]).all(axis=-1)
        if labels.shape != valid.shape or region_ids.shape != valid.shape:
            parser.error("E1a/E2a/E3a image grids are not aligned")
        keyframes.append({
            "ordinal": ordinal, "frame_id": int(record["frame_id"]), "point_path": point_path,
            "point_hash": record["sha256"], "data": point_data, "labels": labels,
            "label_names": label_names, "regions": region_ids, "valid": valid,
            "refined": point_data["point_world"].astype(np.float32).copy(),
            "modified": np.zeros(valid.shape, dtype=bool),
        })

    # Compute per-link pointmap residuals using the same mutual NN gate as E3a.
    accepted = [edge for edge in temporal["candidate_edges"] if edge["decision"] == "accepted"]
    global_id_by_local = {(x["keyframe_ordinal"], x["local_region_id"]): x["global_region_id"] for x in temporal["region_mapping"]}
    links = []
    for left, right in zip(keyframes, keyframes[1:]):
        flat_a = np.flatnonzero(left["valid"].ravel())
        flat_b = np.flatnonzero(right["valid"].ravel())
        points_a = left["data"]["point_world"].reshape(-1, 3)[flat_a].astype(np.float64)
        points_b = right["data"]["point_world"].reshape(-1, 3)[flat_b].astype(np.float64)
        dist_ab, nn_ab = cKDTree(points_b).query(points_a, k=1, workers=-1)
        _dist_ba, nn_ba = cKDTree(points_a).query(points_b, k=1, workers=-1)
        mutual = (dist_ab <= radius) & (nn_ba[nn_ab] == np.arange(len(points_a)))
        pix_a, pix_b, distances = flat_a[mutual], flat_b[nn_ab[mutual]], dist_ab[mutual]
        rid_a = left["regions"].ravel()[pix_a]
        rid_b = right["regions"].ravel()[pix_b]
        for edge in accepted:
            if edge["from"]["keyframe_ordinal"] != left["ordinal"] or edge["to"]["keyframe_ordinal"] != right["ordinal"]:
                continue
            select = (rid_a == edge["from"]["local_region_id"]) & (rid_b == edge["to"]["local_region_id"])
            vals = distances[select]
            if vals.size == 0:
                continue
            links.append({
                "global_region_id": int(global_id_by_local[(left["ordinal"], edge["from"]["local_region_id"])]),
                "from_keyframe_ordinal": left["ordinal"], "to_keyframe_ordinal": right["ordinal"],
                "from_local_region_id": int(edge["from"]["local_region_id"]),
                "to_local_region_id": int(edge["to"]["local_region_id"]),
                "semantic_label": edge["semantic_label"],
                "mutual_correspondence_count": int(vals.size),
                "p50_world_units": float(np.percentile(vals, 50)),
                "p90_world_units": float(np.percentile(vals, 90)),
                "p90_spacing_ratio": float(np.percentile(vals, 90) / max(spacing, 1e-12)),
            })
    links_by_global = {}
    for link in links:
        links_by_global.setdefault(link["global_region_id"], []).append(link)
    observations_by_global = {}
    for item in temporal["region_mapping"]:
        observations_by_global.setdefault(int(item["global_region_id"]), []).append(item)

    elig = config["eligibility"]
    target_labels = set(elig["candidate_semantic_labels"])
    minimum_obs = int(elig["minimum_observations"])
    minimum_pixels = int(elig["minimum_total_region_pixels"])
    minimum_corr = int(elig["minimum_mutual_correspondences"])
    max_planarity = float(elig["maximum_pca_smallest_eigenvalue_ratio"])
    min_inlier_fraction = float(elig["minimum_ransac_inlier_fraction"])
    plane_threshold = float(config["plane_fit"]["inlier_distance_over_global_spacing"]) * spacing
    max_delta = float(config["refinement"]["maximum_radial_displacement_over_global_spacing"]) * spacing
    huber_delta = float(config["refinement"]["huber_delta_over_global_spacing"]) * spacing
    prior_lambda = float(config["refinement"]["displacement_prior_lambda"])
    boundary_px = int(config["refinement"]["boundary_freeze_pixels"])
    conf_values = np.concatenate([k["data"]["confidence_avg"][k["valid"]].astype(np.float64) for k in keyframes if k["valid"].any()])
    conf_scale = max(float(np.median(conf_values)), 1e-6)
    candidates = []

    for global_id, observations in observations_by_global.items():
        label = observations[0]["semantic_label"]
        region_links = links_by_global.get(global_id, [])
        score = max((x["p90_spacing_ratio"] for x in region_links), default=None)
        total_pixels = sum(int(x["pixel_count"]) for x in observations)
        corr_count = sum(int(x["mutual_correspondence_count"]) for x in region_links)
        result = {
            "global_region_id": global_id, "semantic_label": label,
            "observations": observations, "total_region_pixels": total_pixels,
            "accepted_temporal_link_count": len(region_links),
            "mutual_correspondence_count": corr_count,
            "temporal_p90_error_score_spacing_ratio": score,
            "link_error_scores": region_links, "eligible": False,
            "status": "not_selected", "reason": [],
        }
        reasons = []
        if label not in target_labels:
            reasons.append("semantic_label_not_in_planar_candidates")
        if len(observations) < minimum_obs:
            reasons.append("insufficient_keyframe_observations")
        if score is None or score < threshold_ratio:
            reasons.append("temporal_error_score_below_frozen_threshold")
        if total_pixels < minimum_pixels:
            reasons.append("below_minimum_total_region_pixels")
        if corr_count < minimum_corr:
            reasons.append("below_minimum_mutual_correspondence_count")
        if reasons:
            result["reason"] = reasons
            candidates.append(result)
            continue

        obs_data = []
        point_parts = []
        for obs in observations:
            frame = keyframes[int(obs["keyframe_ordinal"])]
            mask = (frame["regions"] == int(obs["local_region_id"])) & frame["valid"]
            point_parts.append(frame["data"]["point_world"][mask].astype(np.float64))
            obs_data.append((frame, mask, int(obs["local_region_id"])))
        all_points = np.concatenate(point_parts, axis=0)
        center = all_points.mean(axis=0)
        eigenvalues = np.maximum(np.linalg.eigvalsh((all_points - center).T @ (all_points - center) / max(len(all_points), 1)), 0)
        planarity = float(eigenvalues[0] / max(eigenvalues.sum(), 1e-12))
        result["pca_planarity_ratio"] = planarity
        if planarity > max_planarity:
            result.update(status="ineligible", reason=["merged_region_not_sufficiently_planar"])
            candidates.append(result)
            continue
        plane, inliers = fit_plane_ransac(
            all_points, plane_threshold, int(config["plane_fit"]["iterations"]),
            int(config["plane_fit"]["seed"]) + global_id,
        )
        if plane is None:
            result.update(status="ineligible", reason=["ransac_plane_fit_failed"])
            candidates.append(result)
            continue
        normal, offset = plane
        inlier_fraction = float(inliers.mean())
        before_rmse = float(np.sqrt(np.mean((all_points @ normal + offset) ** 2)))
        result.update({
            "plane_normal": normal.tolist(), "plane_offset_world_units": float(offset),
            "plane_inlier_fraction": inlier_fraction, "plane_rmse_before_world_units": before_rmse,
        })
        if inlier_fraction < min_inlier_fraction:
            result.update(status="ineligible", reason=["ransac_inlier_fraction_below_limit"])
            candidates.append(result)
            continue

        per_observation = []
        for frame, mask, local_id in obs_data:
            interior = ndimage.binary_erosion(mask, structure=np.ones((3, 3), dtype=bool), iterations=boundary_px, border_value=0) if boundary_px else mask.copy()
            yy, xx = np.where(interior)
            if not len(yy):
                continue
            original = frame["data"]["point_world"].astype(np.float64)
            camera_center = frame["data"]["pose_sim3_raw"].astype(np.float64).reshape(-1)[:3]
            relative = original[yy, xx] - camera_center
            depth0 = np.linalg.norm(relative, axis=-1)
            rays = relative / np.maximum(depth0[:, None], 1e-12)
            a = rays @ normal
            b = float(np.dot(normal, camera_center) + offset)
            good = np.isfinite(depth0) & np.isfinite(a) & (depth0 > 1e-6) & (np.abs(a) >= 0.1)
            yy, xx, rays, depth0, a = yy[good], xx[good], rays[good], depth0[good], a[good]
            if not len(yy):
                continue
            confidence = frame["data"]["confidence_avg"][yy, xx].astype(np.float64)
            weights = np.clip(confidence / conf_scale, 0.1, 10.0)
            depth = depth0.copy()
            for _ in range(8):
                residual = a * depth + b
                robust = np.minimum(1.0, huber_delta / np.maximum(np.abs(residual), 1e-12))
                numerator = weights * robust * a * (-b) + prior_lambda * depth0
                denominator = weights * robust * a * a + prior_lambda
                depth = np.clip(numerator / np.maximum(denominator, 1e-12), depth0 - max_delta, depth0 + max_delta)
            good_depth = np.isfinite(depth) & (depth > 0)
            yy, xx, rays, depth0, depth = yy[good_depth], xx[good_depth], rays[good_depth], depth0[good_depth], depth[good_depth]
            new_points = camera_center + rays * depth[:, None]
            displacement = np.linalg.norm(new_points - original[yy, xx], axis=-1)
            moved = displacement > 1e-6
            before = np.abs(original[yy, xx] @ normal + offset)
            after = np.abs(new_points @ normal + offset)
            frame["refined"][yy[moved], xx[moved]] = new_points[moved].astype(np.float32)
            frame["modified"][yy[moved], xx[moved]] = True
            per_observation.append({
                "keyframe_ordinal": frame["ordinal"], "frame_id": frame["frame_id"],
                "local_region_id": local_id, "interior_pixel_count": int(len(yy)),
                "modified_pixel_count": int(moved.sum()),
                "mean_displacement_world_units": float(displacement[moved].mean()) if moved.any() else 0.0,
                "max_displacement_world_units": float(displacement.max()) if displacement.size else 0.0,
                "plane_rmse_before_world_units": float(np.sqrt(np.mean(before ** 2))),
                "plane_rmse_after_world_units": float(np.sqrt(np.mean(after ** 2))),
            })
        refined_parts = [frame["refined"][mask].astype(np.float64) for frame, mask, _ in obs_data]
        after_points = np.concatenate(refined_parts, axis=0)
        after_rmse = float(np.sqrt(np.mean((after_points @ normal + offset) ** 2)))
        improvement = (before_rmse - after_rmse) / max(before_rmse, 1e-12)
        result.update({
            "region_modifications": per_observation,
            "plane_rmse_after_world_units": after_rmse,
            "relative_plane_rmse_improvement": improvement,
            "eligible": True,
        })
        if improvement < float(config["refinement"]["minimum_relative_plane_rmse_improvement"]):
            for frame, mask, _local_id in obs_data:
                frame["refined"][mask] = frame["data"]["point_world"][mask]
                frame["modified"][mask] = False
            result.update(status="rejected_and_rolled_back", reason=["plane_rmse_improvement_below_limit"])
        else:
            result.update(status="applied", reason=[])
        candidates.append(result)

    output_keyframes = []
    for frame in keyframes:
        original = frame["data"]["point_world"].astype(np.float32)
        modified = frame["modified"]
        if np.any(frame["refined"][~modified] != original[~modified]):
            raise RuntimeError("a non-target point changed")
        displacement = np.linalg.norm(frame["refined"] - original, axis=-1)
        if modified.any() and float(displacement[modified].max()) > max_delta + 1e-5:
            raise RuntimeError("maximum displacement bound violated")
        path = args.output / f"refined_kf_{frame['ordinal']:03d}_frame_{frame['frame_id']:08d}.npz"
        np.savez_compressed(
            path, point_world_original=original, point_world_refined=frame["refined"],
            modified=modified, valid=frame["valid"], semantic_label_id=frame["labels"],
            local_region_id=frame["regions"], frame_id=np.int64(frame["frame_id"]),
        )
        output_keyframes.append({
            "ordinal": frame["ordinal"], "frame_id": frame["frame_id"],
            "file": path.name, "modified_pixel_count": int(modified.sum()),
        })

    summary = {
        "stage": "E4a_error_guided_local_refinement", "status": "completed",
        "selection_score_definition": config["selection_signal"],
        "frozen_error_threshold_spacing_ratio": threshold_ratio,
        "global_median_local_spacing_world_units": spacing,
        "maximum_radial_displacement_world_units": max_delta,
        "sources": {
            "e1a_export_manifest_sha256": sha256(export_path),
            "e2a_keyframes_manifest_sha256": sha256(tagging_path),
            "e3a_temporal_regions_sha256": sha256(temporal_path),
            "e4a_config_sha256": sha256(args.config),
        },
        "candidate_region_count": len(candidates),
        "selected_region_count": sum(x["status"] == "applied" for x in candidates),
        "rolled_back_region_count": sum(x["status"] == "rejected_and_rolled_back" for x in candidates),
        "keyframes": output_keyframes, "accepted_link_error_scores": links,
        "candidate_regions": candidates, "non_target_points_exactly_unchanged": True,
        "elapsed_seconds": time.perf_counter() - started, "config": config,
    }
    (args.output / "refinement_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("stage", "keyframes", "candidate_region_count", "selected_region_count", "rolled_back_region_count", "maximum_radial_displacement_world_units", "elapsed_seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
