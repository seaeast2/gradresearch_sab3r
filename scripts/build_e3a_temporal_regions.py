#!/usr/bin/env python3
"""Build per-Keyframe Regions and conservative geometry-only temporal links."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from scipy.optimize import linear_sum_assignment

from build_e3_regions import geometry_components, normals_and_spacing, region_preview


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def descriptor(mask: np.ndarray, points: np.ndarray, sample_limit: int) -> dict:
    ys, xs = np.where(mask)
    values = points[mask].astype(np.float64)
    center = values.mean(axis=0)
    covariance = np.cov(values, rowvar=False) if len(values) > 2 else np.zeros((3, 3))
    eigvals, eigvecs = np.linalg.eigh(covariance)
    eigvals = np.maximum(eigvals, 0)
    normal = eigvecs[:, 0]
    planarity = float(eigvals[0] / max(eigvals.sum(), 1e-12))
    if len(values) > sample_limit:
        indices = np.linspace(0, len(values) - 1, sample_limit, dtype=np.int64)
        sample = values[indices]
    else:
        sample = values
    return {
        "pixel_count": int(mask.sum()),
        "centroid": center,
        "bounds_min": values.min(axis=0),
        "bounds_max": values.max(axis=0),
        "normal": normal,
        "planarity_ratio": planarity,
        "pca_eigenvalues": eigvals,
        "sample": sample,
        "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1a-artifacts", type=Path, required=True)
    parser.add_argument("--e2a-artifacts", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f"refusing to mix with existing E3a artifacts: {args.output}")
    started = time.perf_counter()
    e1a = args.e1a_artifacts.resolve()
    e2a = args.e2a_artifacts.resolve()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    export_path = e1a / "pointmaps" / "export_manifest.json"
    tagging_path = e2a / "keyframes_manifest.json"
    export = json.loads(export_path.read_text(encoding="utf-8"))
    tagging = json.loads(tagging_path.read_text(encoding="utf-8"))
    if export["keyframe_count"] < 2 or tagging["keyframe_count"] != export["keyframe_count"]:
        parser.error("E3a requires matching multi-Keyframe E1a/E2a manifests")
    if tagging["source_e1a_export_manifest_sha256"] != sha256(export_path):
        parser.error("E2a tags do not reference this exact E1a export manifest")

    args.output.mkdir(parents=True, exist_ok=True)
    label_names: list[str] | None = None
    frames = []
    mask_arrays = {}
    region_ids_by_ordinal = {}
    point_data_by_ordinal = {}
    spacing_values = []
    region_gate = config["region_build"]
    assoc_cfg = config["association"]
    for keyframe, tagged in zip(export["keyframes"], tagging["keyframes"]):
        if keyframe["frame_id"] != tagged["frame_id"]:
            parser.error("E1a and E2a Keyframe order/frame IDs do not match")
        pointmap = e1a / "pointmaps" / keyframe["file"]
        scores_path = e2a / tagged["result_dir"] / "semantic_scores.npz"
        if sha256(pointmap) != keyframe["sha256"] or sha256(scores_path) != tagged["semantic_scores_sha256"]:
            parser.error("E1a pointmap or E2a semantic score hash mismatch")
        with np.load(pointmap, allow_pickle=False) as data:
            rgb = data["rgb_uint8"].copy()
            points = data["point_world"].astype(np.float32)
            valid = data["valid"].astype(bool)
            confidence = data["confidence_avg"].astype(np.float32)
        with np.load(scores_path, allow_pickle=False) as sem:
            labels = sem["label_id"].astype(np.uint8)
            current_names = [str(x) for x in sem["labels"].tolist()]
        if label_names is None:
            label_names = current_names
        if current_names != label_names or labels.shape != valid.shape or points.shape[:2] != labels.shape:
            parser.error("E2a labels or pixel grids differ across Keyframes")
        valid &= np.isfinite(points).all(axis=-1) & np.isfinite(confidence) & (confidence > 0)
        region_ids, region_count, _fallback = geometry_components(
            points, labels, valid,
            float(region_gate["max_neighbor_distance_over_local_spacing"]),
            float(region_gate["max_unsigned_normal_angle_degrees"]),
        )
        _normals, spacing, _fallback = normals_and_spacing(points, labels, valid)
        spacing_values.extend(spacing[valid & np.isfinite(spacing) & (spacing > 0)][::64].tolist())
        ordinal = int(keyframe["ordinal"])
        mask_arrays[f"region_ids_kf_{ordinal:03d}"] = region_ids
        mask_arrays[f"semantic_labels_kf_{ordinal:03d}"] = labels
        region_ids_by_ordinal[ordinal] = region_ids
        point_data_by_ordinal[ordinal] = {"points": points, "valid": valid}
        preview_path = args.output / f"regions_kf_{ordinal:03d}_frame_{keyframe['frame_id']:08d}.png"
        Image.fromarray(region_preview(rgb, region_ids)).save(preview_path)
        rows = []
        for region_id in np.unique(region_ids[region_ids > 0]):
            mask = region_ids == region_id
            item = descriptor(mask, points, int(assoc_cfg["sample_limit_per_region"]))
            item["local_region_id"] = int(region_id)
            item["semantic_label_id"] = int(np.bincount(labels[mask].astype(np.int64)).argmax())
            item["semantic_label"] = label_names[item["semantic_label_id"]]
            rows.append(item)
        frames.append({
            "ordinal": ordinal,
            "frame_id": int(keyframe["frame_id"]),
            "timestamp": keyframe["timestamp"],
            "pointmap": keyframe["file"],
            "pointmap_sha256": keyframe["sha256"],
            "semantic_scores": str(scores_path.relative_to(e2a)),
            "semantic_scores_sha256": tagged["semantic_scores_sha256"],
            "region_count": region_count,
            "valid_pixel_count": int(valid.sum()),
            "preview": preview_path.name,
            "regions": rows,
        })

    global_spacing = float(np.median(np.asarray(spacing_values, dtype=np.float64))) if spacing_values else 1e-3
    radius = float(assoc_cfg["max_point_distance_over_global_spacing"]) * global_spacing
    min_pixels = int(assoc_cfg["min_region_pixels"])
    min_correspondences = int(assoc_cfg["min_mutual_correspondence_pixels"])
    min_overlap = float(assoc_cfg["min_bidirectional_correspondence_overlap_fraction"])
    max_angle = float(assoc_cfg["max_unsigned_normal_angle_degrees"])
    max_offset = float(assoc_cfg["max_plane_offset_over_global_spacing"]) * global_spacing
    max_planarity = float(assoc_cfg["max_planarity_ratio"])
    candidates = []
    accepted_edges = []
    descriptors = {}
    for frame in frames:
        for region in frame["regions"]:
            descriptors[(frame["ordinal"], region["local_region_id"])] = region

    correspondence_pairs = []
    for left, right in zip(frames, frames[1:]):
        ordinal_a, ordinal_b = left["ordinal"], right["ordinal"]
        data_a, data_b = point_data_by_ordinal[ordinal_a], point_data_by_ordinal[ordinal_b]
        ids_a = region_ids_by_ordinal[ordinal_a]
        ids_b = region_ids_by_ordinal[ordinal_b]
        flat_a = np.flatnonzero(data_a["valid"].ravel())
        flat_b = np.flatnonzero(data_b["valid"].ravel())
        points_a = data_a["points"].reshape(-1, 3)[flat_a].astype(np.float64)
        points_b = data_b["points"].reshape(-1, 3)[flat_b].astype(np.float64)
        tree_a, tree_b = cKDTree(points_a), cKDTree(points_b)
        dist_ab, nn_ab = tree_b.query(points_a, k=1, workers=-1)
        dist_ba, nn_ba = tree_a.query(points_b, k=1, workers=-1)
        mutual = (dist_ab <= radius) & (nn_ba[nn_ab] == np.arange(len(points_a)))
        mutual_a = flat_a[mutual]
        mutual_b = flat_b[nn_ab[mutual]]
        region_a = ids_a.ravel()[mutual_a]
        region_b = ids_b.ravel()[mutual_b]
        valid_pairs = (region_a > 0) & (region_b > 0)
        region_a, region_b = region_a[valid_pairs], region_b[valid_pairs]
        distances = dist_ab[mutual][valid_pairs]
        pair_counts = {}
        for rid_a, rid_b in zip(region_a.tolist(), region_b.tolist()):
            pair_counts[(rid_a, rid_b)] = pair_counts.get((rid_a, rid_b), 0) + 1
        correspondence_pairs.append({
            "from_keyframe_ordinal": ordinal_a,
            "to_keyframe_ordinal": ordinal_b,
            "valid_point_count": [int(len(flat_a)), int(len(flat_b))],
            "mutual_correspondence_count": int(len(region_a)),
            "median_mutual_distance_world_units": float(np.median(distances)) if len(distances) else None,
            "pair_counts": pair_counts,
        })

        regions_a = {row["local_region_id"]: row for row in left["regions"]}
        regions_b = {row["local_region_id"]: row for row in right["regions"]}
        labels_a = sorted({r["semantic_label_id"] for r in left["regions"]})
        for label_id in labels_a:
            group_a = [r for r in left["regions"] if r["semantic_label_id"] == label_id]
            group_b = [r for r in right["regions"] if r["semantic_label_id"] == label_id]
            if not group_a or not group_b:
                continue
            score = np.zeros((len(group_a), len(group_b)), dtype=np.float64)
            edges = {}
            for ai, a in enumerate(group_a):
                for bi, b in enumerate(group_b):
                    common = pair_counts.get((a["local_region_id"], b["local_region_id"]), 0)
                    overlap_a = common / max(a["pixel_count"], 1)
                    overlap_b = common / max(b["pixel_count"], 1)
                    overlap = min(overlap_a, overlap_b)
                    reasons = []
                    if a["pixel_count"] < min_pixels or b["pixel_count"] < min_pixels:
                        reasons.append("region_below_minimum_pixel_count")
                    if common < min_correspondences:
                        reasons.append("insufficient_mutual_pointmap_correspondences")
                    if overlap < min_overlap:
                        reasons.append("insufficient_bidirectional_correspondence_overlap")
                    expanded_a_min = a["bounds_min"] - radius
                    expanded_a_max = a["bounds_max"] + radius
                    if np.any(expanded_a_max < b["bounds_min"]) or np.any(b["bounds_max"] < expanded_a_min):
                        reasons.append("world_bounds_disjoint")
                    normal_angle = None
                    plane_offset = None
                    planar_a = a["planarity_ratio"] <= max_planarity
                    planar_b = b["planarity_ratio"] <= max_planarity
                    if planar_a and planar_b:
                        dot = float(np.clip(abs(np.dot(a["normal"], b["normal"])), 0.0, 1.0))
                        normal_angle = float(np.rad2deg(np.arccos(dot)))
                        plane_offset = float(abs(np.dot(a["normal"], b["centroid"] - a["centroid"])))
                        if normal_angle > max_angle:
                            reasons.append("plane_normal_mismatch")
                        if plane_offset > max_offset:
                            reasons.append("plane_offset_exceeded")
                    elif planar_a != planar_b:
                        reasons.append("planarity_mismatch")
                    score[ai, bi] = overlap
                    edges[(ai, bi)] = {
                        "from": {"keyframe_ordinal": ordinal_a, "frame_id": left["frame_id"], "local_region_id": a["local_region_id"]},
                        "to": {"keyframe_ordinal": ordinal_b, "frame_id": right["frame_id"], "local_region_id": b["local_region_id"]},
                        "semantic_label": a["semantic_label"],
                        "pixel_count": [a["pixel_count"], b["pixel_count"]],
                        "mutual_pointmap_correspondence_count": common,
                        "bidirectional_correspondence_overlap_fraction": {"a_to_b": overlap_a, "b_to_a": overlap_b, "symmetric_min": overlap},
                        "plane_normal_angle_degrees": normal_angle,
                        "plane_offset_world_units": plane_offset,
                        "reasons": reasons,
                    }
            costs = 1.0 - score
            for (ai, bi), edge in edges.items():
                if edge["reasons"]:
                    costs[ai, bi] = 1e6
            rows, cols = linear_sum_assignment(costs)
            matched = set()
            for ai, bi in zip(rows.tolist(), cols.tolist()):
                edge = edges[(ai, bi)]
                if not edge["reasons"]:
                    edge["decision"] = "accepted"
                    candidates.append(edge)
                    accepted_edges.append(((ordinal_a, group_a[ai]["local_region_id"]), (ordinal_b, group_b[bi]["local_region_id"]), edge))
                    matched.add((ai, bi))
            for key, edge in edges.items():
                if key in matched:
                    continue
                if not edge["reasons"]:
                    edge["reasons"].append("not_selected_by_one_to_one_hungarian_assignment")
                edge["decision"] = "rejected"
                candidates.append(edge)

    nodes = list(descriptors)
    parent = {node: node for node in nodes}

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for key_a, key_b, _edge in accepted_edges:
        root_a, root_b = find(key_a), find(key_b)
        if root_a != root_b:
            parent[root_b] = root_a
    roots = sorted({find(node) for node in nodes})
    global_ids = {root: index + 1 for index, root in enumerate(roots)}
    region_mapping = []
    for node, row in descriptors.items():
        region_mapping.append({
            "keyframe_ordinal": node[0],
            "local_region_id": node[1],
            "global_region_id": global_ids[find(node)],
            "semantic_label": row["semantic_label"],
            "pixel_count": row["pixel_count"],
        })
    by_global = {}
    for item in region_mapping:
        by_global.setdefault(str(item["global_region_id"]), []).append(item)
    global_regions = [
        {"global_region_id": int(global_id), "observations": observations}
        for global_id, observations in by_global.items()
    ]
    np.savez_compressed(args.output / "region_masks.npz", **mask_arrays)
    manifest = {
        "stage": "E3a_temporal_region_association",
        "status": "completed",
        "association_method": "mutual nearest 3D pointmap correspondences, semantic Region overlap, one-to-one Hungarian assignment with partial rejection; planar pairs also use normal and offset gates",
        "learned_feature_correspondences": "MASt3R descriptors are not present in the E1a export; this pilot computes geometry-based pointmap correspondences",
        "thresholds": config,
        "global_median_local_spacing_world_units": global_spacing,
        "association_radius_world_units": radius,
        "source_manifests": {
            "e1a_path": str(export_path), "e1a_sha256": sha256(export_path),
            "e2a_path": str(tagging_path), "e2a_sha256": sha256(tagging_path),
        },
        "keyframes": [{k: v for k, v in frame.items() if k != "regions"} | {"region_count": frame["region_count"]} for frame in frames],
        "keyframe_count": len(frames),
        "adjacent_keyframe_correspondences": [
            {k: v for k, v in row.items() if k != "pair_counts"}
            for row in correspondence_pairs
        ],
        "region_mapping": region_mapping,
        "global_regions": global_regions,
        "candidate_edge_count": len(candidates),
        "accepted_edge_count": len(accepted_edges),
        "rejected_edge_count": len(candidates) - len(accepted_edges),
        "candidate_edges": candidates,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.output / "temporal_regions.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=lambda value: value.tolist() if isinstance(value, np.ndarray) else float(value)) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("keyframe_count", "candidate_edge_count", "accepted_edge_count", "rejected_edge_count", "association_radius_world_units", "elapsed_seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
