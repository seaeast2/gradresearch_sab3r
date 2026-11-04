#!/usr/bin/env python3
"""RANSAC plane selection and bounded ray-depth refinement for E4."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


COLORS = np.array([
    [238, 179, 44], [62, 155, 224], [157, 108, 189], [226, 86, 87],
    [112, 187, 111], [231, 135, 56], [145, 145, 145],
], dtype=np.uint8)


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
        offset = -np.dot(normal, sample[0])
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
    # Recompute the final inlier set against the refit plane.
    best = np.abs(points @ normal + offset) <= threshold
    return (normal.astype(np.float64), offset), best


def write_ply(path: Path, xyz: np.ndarray, rgb: np.ndarray, normals=None):
    xyz = np.asarray(xyz, dtype=np.float32).reshape(-1, 3)
    rgb = np.asarray(rgb, dtype=np.uint8).reshape(-1, 3)
    if normals is None:
        props = "property float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue"
    else:
        normals = np.asarray(normals, dtype=np.float32).reshape(-1, 3)
        props = "property float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\nproperty uchar red\nproperty uchar green\nproperty uchar blue"
    with path.open("w", encoding="ascii") as stream:
        stream.write("ply\nformat ascii 1.0\n")
        stream.write(f"element vertex {len(xyz)}\n{props}\nend_header\n")
        if normals is None:
            for p, c in zip(xyz, rgb):
                stream.write(f"{p[0]:.7g} {p[1]:.7g} {p[2]:.7g} {c[0]} {c[1]} {c[2]}\n")
        else:
            for p, n, c in zip(xyz, normals, rgb):
                stream.write(f"{p[0]:.7g} {p[1]:.7g} {p[2]:.7g} {n[0]:.7g} {n[1]:.7g} {n[2]:.7g} {c[0]} {c[1]} {c[2]}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pointmap", type=Path, required=True)
    parser.add_argument("--regions", type=Path, required=True)
    parser.add_argument("--region-stats", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rgb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    with np.load(args.pointmap, allow_pickle=False) as src:
        original = src["point_world"].astype(np.float32)
        local = src["point_local"].astype(np.float32)
        rgb = src["rgb_uint8"].copy()
        confidence = src["confidence_avg"].astype(np.float32)
        valid = src["valid"].astype(bool)
        pose = src["pose_sim3_raw"].astype(np.float64).reshape(-1)
        frame_id = int(src["frame_id"])
        timestamp = str(src["timestamp"])
    with np.load(args.regions, allow_pickle=False) as src:
        region_ids = src["region_id_semantic_geometry"].astype(np.int32)
        semantic_ids = src["semantic_label_id"].astype(np.uint8)
        valid &= src["valid"].astype(bool)
    stats = json.loads(args.region_stats.read_text(encoding="utf-8"))
    label_names = stats["label_names"]
    image = np.asarray(Image.open(args.rgb).convert("RGB"))
    if image.shape != rgb.shape or not np.array_equal(image, rgb):
        raise ValueError("E4 RGB does not exactly align with the frozen E1 pointmap")
    if region_ids.shape != valid.shape or original.shape[:2] != valid.shape:
        raise ValueError("E1 and E3 point grids do not match")
    finite = valid & np.isfinite(original).all(axis=-1) & np.isfinite(local).all(axis=-1) & np.isfinite(confidence)
    valid &= finite

    # The raw lietorch Sim(3) embedding stores translation in its first 3 entries.
    # Radial rays are recovered directly from the fixed world point and its camera center.
    camera_center = pose[:3].astype(np.float32)
    relative = original - camera_center
    radial_depth = np.linalg.norm(relative, axis=-1)
    ray = relative / np.maximum(radial_depth[..., None], 1e-12)

    accepted_spacing = float(stats["median_accepted_edge_spacing_world_units"])
    plane_threshold = max(0.01, 2.0 * accepted_spacing)
    max_delta = 3.0 * accepted_spacing
    eligible = config["eligibility"]
    candidate_labels = set(config["candidate_labels"])
    minimum_pixels = int(eligible["minimum_region_pixels"])
    max_pca_ratio = float(eligible["maximum_pca_smallest_eigenvalue_ratio"])
    min_inlier_fraction = float(eligible["minimum_ransac_inlier_fraction"])
    label_to_id = {name: i for i, name in enumerate(label_names)}
    target_label_ids = {label_to_id[name] for name in candidate_labels if name in label_to_id}

    refined = original.copy()
    modified = np.zeros(valid.shape, dtype=bool)
    candidate_results = []
    huber_delta = float(config["refinement"]["huber_delta_world_units"])
    prior_lambda = float(config["refinement"]["displacement_prior_lambda"])
    boundary_px = int(config["refinement"]["boundary_freeze_pixels"])
    conf_scale = max(float(np.median(confidence[valid])), 1e-6)
    all_ids = np.unique(region_ids[region_ids > 0])

    for rid in all_ids:
        mask = (region_ids == rid) & valid
        count = int(mask.sum())
        flat_labels = semantic_ids[mask]
        label_id = int(np.bincount(flat_labels).argmax()) if flat_labels.size else -1
        label_name = label_names[label_id] if 0 <= label_id < len(label_names) else "unknown"
        result = {"region_id": int(rid), "semantic_label": label_name, "pixel_count": count, "status": "ineligible", "reason": None}
        if label_id not in target_label_ids:
            result["reason"] = "semantic_class_not_in_plane_candidates"
            candidate_results.append(result)
            continue
        if count < minimum_pixels:
            result["reason"] = "below_minimum_region_pixels"
            candidate_results.append(result)
            continue
        points = original[mask].astype(np.float64)
        center = points.mean(axis=0)
        eigvals = np.linalg.eigvalsh((points - center).T @ (points - center) / max(count, 1))
        ratio = float(max(eigvals[0], 0) / max(eigvals.sum(), 1e-12))
        result["pca_smallest_eigenvalue_ratio"] = ratio
        if ratio > max_pca_ratio:
            result["reason"] = "pca_planarity_ratio_exceeds_limit"
            candidate_results.append(result)
            continue
        plane, inliers = fit_plane_ransac(points, plane_threshold, int(config["plane_fit"]["iterations"]), int(rid))
        if plane is None:
            result["reason"] = "ransac_plane_fit_failed"
            candidate_results.append(result)
            continue
        normal, offset = plane
        inlier_fraction = float(inliers.mean())
        result.update({
            "ransac_inlier_fraction": inlier_fraction,
            "plane_normal": normal.tolist(),
            "plane_offset": float(offset),
            "plane_inlier_rmse": float(np.sqrt(np.mean((points[inliers] @ normal + offset) ** 2))) if inliers.any() else None,
        })
        if inlier_fraction < min_inlier_fraction:
            result["reason"] = "ransac_inlier_fraction_below_limit"
            candidate_results.append(result)
            continue

        interior = ndimage.binary_erosion(mask, structure=np.ones((3, 3), dtype=bool), iterations=boundary_px, border_value=0) if boundary_px else mask.copy()
        interior &= mask
        yy, xx = np.where(interior)
        if yy.size == 0:
            result["reason"] = "no_interior_pixels_after_boundary_freeze"
            candidate_results.append(result)
            continue
        rays = ray[yy, xx]
        depth0 = radial_depth[yy, xx]
        a = rays @ normal
        b = float(np.dot(normal, camera_center) + offset)
        good = np.isfinite(a) & np.isfinite(depth0) & (np.abs(a) >= 0.1) & (depth0 > 1e-6)
        yy, xx, rays, depth0, a = yy[good], xx[good], rays[good], depth0[good], a[good]
        if yy.size == 0:
            result["reason"] = "rays_parallel_to_plane_or_invalid"
            candidate_results.append(result)
            continue
        weights = np.clip(confidence[yy, xx] / conf_scale, 0.1, 10.0)
        depth = depth0.copy()
        for _ in range(8):
            residual = a * depth + b
            robust = np.minimum(1.0, huber_delta / np.maximum(np.abs(residual), 1e-12))
            numerator = weights * robust * a * (-b) + prior_lambda * depth0
            denominator = weights * robust * a * a + prior_lambda
            updated = numerator / np.maximum(denominator, 1e-12)
            depth = np.clip(updated, depth0 - max_delta, depth0 + max_delta)
        good_depth = np.isfinite(depth) & (depth > 0)
        yy, xx, rays, depth0, depth = yy[good_depth], xx[good_depth], rays[good_depth], depth0[good_depth], depth[good_depth]
        new_points = camera_center + rays * depth[:, None]
        displacement = np.linalg.norm(new_points - original[yy, xx], axis=-1)
        moved = displacement > 1e-6
        refined[yy[moved], xx[moved]] = new_points[moved].astype(np.float32)
        modified[yy[moved], xx[moved]] = True
        residual_before = np.abs(original[yy, xx] @ normal + offset)
        residual_after = np.abs(refined[yy, xx] @ normal + offset)
        result.update({
            "status": "eligible_applied",
            "reason": None,
            "interior_pixel_count": int(len(yy)),
            "modified_pixel_count": int(moved.sum()),
            "mean_displacement": float(displacement[moved].mean()) if moved.any() else 0.0,
            "max_displacement": float(displacement.max()) if displacement.size else 0.0,
            "plane_residual_rmse_before": float(np.sqrt(np.mean(residual_before**2))),
            "plane_residual_rmse_after": float(np.sqrt(np.mean(residual_after**2))),
        })
        candidate_results.append(result)

    outside_delta = float(np.max(np.abs(refined[~modified] - original[~modified]))) if np.any(~modified) else 0.0
    if outside_delta != 0.0:
        raise RuntimeError(f"non-target points moved: outside_delta={outside_delta}")
    delta = refined - original
    magnitude = np.linalg.norm(delta, axis=-1)
    point_colors = rgb
    labels_rgb = COLORS[np.minimum(semantic_ids, len(COLORS) - 1)]
    delta_rgb = np.zeros_like(rgb)
    if modified.any():
        scaled = np.clip(magnitude[modified] / max(max_delta, 1e-8), 0, 1)
        delta_rgb[modified] = np.stack([np.full_like(scaled, 255), (1 - scaled) * 80, (1 - scaled) * 80], axis=-1).astype(np.uint8)
    write_ply(args.output / "original_world.ply", original[valid], point_colors[valid])
    write_ply(args.output / "semantic_region.ply", original[valid], labels_rgb[valid])
    write_ply(args.output / "optimized_world.ply", refined[valid], point_colors[valid])
    write_ply(args.output / "delta_vectors.ply", original[modified], delta_rgb[modified], delta[modified])
    np.savez_compressed(
        args.output / "refinement.npz",
        original_world=original,
        refined_world=refined,
        modified=modified,
        semantic_label_id=semantic_ids,
        region_id=region_ids,
        valid=valid,
        frame_id=np.int64(frame_id),
        timestamp=np.asarray(timestamp),
    )
    summary = {
        "stage": "E4_geometry_refinement",
        "status": "completed",
        "frame_id": frame_id,
        "timestamp": timestamp,
        "input_pointmap": str(args.pointmap.resolve()),
        "input_regions": str(args.regions.resolve()),
        "input_shape_hw": list(valid.shape),
        "candidate_region_count": len(candidate_results),
        "eligible_region_count": sum(r["status"] == "eligible_applied" for r in candidate_results),
        "modified_pixel_count": int(modified.sum()),
        "modified_fraction": float(modified.sum() / max(valid.sum(), 1)),
        "outside_delta_max_abs": outside_delta,
        "median_sampling_spacing_world_units": accepted_spacing,
        "plane_inlier_threshold_world_units": plane_threshold,
        "max_radial_displacement_world_units": max_delta,
        "camera_center_world": camera_center.tolist(),
        "fixed_pose_sim3_raw": pose.tolist(),
        "config": config,
        "candidate_regions": candidate_results,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.output / "refinement.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "candidate_regions"}, indent=2))


if __name__ == "__main__":
    main()
