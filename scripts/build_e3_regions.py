#!/usr/bin/env python3
"""Build single-keyframe semantic and geometry-connected Region candidates."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


COLORS = np.array([
    [230, 74, 74], [67, 133, 212], [156, 97, 177], [237, 171, 55],
    [91, 174, 104], [223, 119, 58], [155, 155, 155],
], dtype=np.uint8)


def components_4(labels: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, int]:
    output = np.zeros(labels.shape, dtype=np.int32)
    next_id = 1
    cross = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
    for class_id in np.unique(labels[valid]):
        local, count = ndimage.label(valid & (labels == class_id), structure=cross)
        if count:
            selected = local > 0
            output[selected] = local[selected] + next_id - 1
            next_id += count
    return output, next_id - 1


def normals_and_spacing(points: np.ndarray, labels: np.ndarray, valid: np.ndarray):
    h, w, _ = points.shape
    normals = np.full((h, w, 3), np.nan, dtype=np.float32)
    if h >= 3 and w >= 3:
        dx = points[1:-1, 2:] - points[1:-1, :-2]
        dy = points[2:, 1:-1] - points[:-2, 1:-1]
        normal = np.cross(dx, dy)
        norm = np.linalg.norm(normal, axis=-1)
        normal_valid = valid[1:-1, 1:-1] & (norm > 1e-8) & np.isfinite(norm)
        block = normals[1:-1, 1:-1]
        block[normal_valid] = normal[normal_valid] / norm[normal_valid, None]

    scale_values = np.full((h, w), np.nan, dtype=np.float32)
    distance_parts = []
    for y0, x0, y1, x1 in ((slice(None), slice(None, -1), slice(None), slice(1, None)),
                           (slice(None, -1), slice(None), slice(1, None), slice(None))):
        same = valid[y0, x0] & valid[y1, x1] & (labels[y0, x0] == labels[y1, x1])
        delta = points[y0, x0] - points[y1, x1]
        distance = np.linalg.norm(delta, axis=-1)
        same &= np.isfinite(distance) & (distance > 1e-8)
        distance_parts.append(distance[same])

    all_distances = np.concatenate([part for part in distance_parts if part.size]) if any(part.size for part in distance_parts) else np.array([], dtype=np.float32)
    fallback = float(np.median(all_distances)) if all_distances.size else 1.0
    sums = np.zeros((h, w), dtype=np.float64)
    counts = np.zeros((h, w), dtype=np.int16)
    for y0, x0, y1, x1 in ((slice(None), slice(None, -1), slice(None), slice(1, None)),
                           (slice(None, -1), slice(None), slice(1, None), slice(None))):
        same = valid[y0, x0] & valid[y1, x1] & (labels[y0, x0] == labels[y1, x1])
        distance = np.linalg.norm(points[y0, x0] - points[y1, x1], axis=-1)
        same &= np.isfinite(distance) & (distance > 1e-8)
        a_sum, b_sum = sums[y0, x0], sums[y1, x1]
        a_count, b_count = counts[y0, x0], counts[y1, x1]
        a_sum[same] += distance[same]
        b_sum[same] += distance[same]
        a_count[same] += 1
        b_count[same] += 1
    has = counts > 0
    scale_values[has] = (sums[has] / counts[has]).astype(np.float32)
    scale_values[~has] = fallback
    return normals, scale_values, fallback


def geometry_components(points, labels, valid, spacing_factor, normal_degrees):
    h, w = labels.shape
    normals, spacing, fallback = normals_and_spacing(points, labels, valid)
    parent = np.arange(h * w, dtype=np.int64)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return int(a)

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    cos_limit = float(np.cos(np.deg2rad(normal_degrees)))
    for y, x, yy, xx, axis in (
        (slice(None), slice(None, -1), slice(None), slice(1, None), 0),
        (slice(None, -1), slice(None), slice(1, None), slice(None), 1),
    ):
        same = valid[y, x] & valid[yy, xx] & (labels[y, x] == labels[yy, xx])
        distances = np.linalg.norm(points[y, x] - points[yy, xx], axis=-1)
        spacing_limit = spacing_factor * np.minimum(spacing[y, x], spacing[yy, xx])
        accepted = same & np.isfinite(distances) & (distances <= spacing_limit)
        n0, n1 = normals[y, x], normals[yy, xx]
        both_normals = np.isfinite(n0).all(axis=-1) & np.isfinite(n1).all(axis=-1)
        dot = np.zeros_like(distances)
        dot[both_normals] = np.abs(np.sum(n0[both_normals] * n1[both_normals], axis=-1))
        accepted &= ~both_normals | (dot >= cos_limit)
        for ay, ax in np.argwhere(accepted):
            py, px = int(ay), int(ax)
            qy = py + (axis == 1)
            qx = px + (axis == 0)
            union(py * w + px, qy * w + qx)

    flat_valid = np.flatnonzero(valid.ravel())
    roots = np.fromiter((find(int(i)) for i in flat_valid), dtype=np.int64, count=flat_valid.size)
    _, inverse = np.unique(roots, return_inverse=True)
    output = np.zeros(h * w, dtype=np.int32)
    output[flat_valid] = inverse.astype(np.int32) + 1
    return output.reshape(h, w), int(inverse.max() + 1 if inverse.size else 0), fallback


def summarize_regions(region_id, labels, valid, points, confidence, label_names, spacing_median):
    rows = []
    for rid in np.unique(region_id[region_id > 0]):
        mask = region_id == rid
        ys, xs = np.where(mask)
        pts = points[mask].astype(np.float64)
        center = pts.mean(axis=0)
        centered = pts - center
        eigvals = np.linalg.eigvalsh(centered.T @ centered / max(len(pts), 1)) if len(pts) >= 3 else np.zeros(3)
        eigvals = np.maximum(eigvals, 0)
        planarity = float(eigvals[0] / max(eigvals.sum(), 1e-12))
        normal = np.linalg.eigh(centered.T @ centered)[1][:, 0] if len(pts) >= 3 else np.full(3, np.nan)
        residual = np.abs(centered @ normal) if len(pts) >= 3 else np.array([], dtype=float)
        rows.append({
            "region_id": int(rid),
            "semantic_label_id": int(np.bincount(labels[mask].astype(np.int64)).argmax()),
            "semantic_label": label_names[int(np.bincount(labels[mask].astype(np.int64)).argmax())],
            "pixel_count": int(mask.sum()),
            "bbox_xyxy": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
            "centroid_xy": [float(xs.mean()), float(ys.mean())],
            "mean_geometry_confidence": float(confidence[mask].mean()),
            "world_centroid": center.tolist(),
            "world_bounds_min": pts.min(axis=0).tolist(),
            "world_bounds_max": pts.max(axis=0).tolist(),
            "pca_eigenvalues_ascending": eigvals.tolist(),
            "pca_planarity_ratio_smallest_over_sum": planarity,
            "self_fitted_plane_rmse": float(np.sqrt(np.mean(residual**2))) if residual.size else None,
            "self_fitted_plane_inlier_fraction_2x_median_sampling": float(np.mean(residual <= 2 * spacing_median)) if residual.size else None,
        })
    return rows


def region_preview(rgb, region_ids):
    base = rgb.astype(np.float32)
    boundaries = np.zeros(region_ids.shape, dtype=bool)
    boundaries[:, 1:] |= (region_ids[:, 1:] != region_ids[:, :-1]) & (region_ids[:, 1:] > 0)
    boundaries[1:, :] |= (region_ids[1:, :] != region_ids[:-1, :]) & (region_ids[1:, :] > 0)
    color = np.zeros_like(rgb)
    for rid in np.unique(region_ids[region_ids > 0]):
        color[region_ids == rid] = ((int(rid) * np.array([67, 131, 197])) % 200 + 35).astype(np.uint8)
    out = np.clip(0.72 * base + 0.28 * color, 0, 255).astype(np.uint8)
    out[boundaries] = [255, 255, 255]
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pointmap", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    with np.load(args.pointmap, allow_pickle=False) as data:
        rgb = data["rgb_uint8"].copy()
        points = data["point_world"].astype(np.float32)
        valid = data["valid"].astype(bool)
        confidence = data["confidence_avg"].astype(np.float32)
        frame_id = int(data["frame_id"])
        timestamp = str(data["timestamp"])
    with np.load(args.scores, allow_pickle=False) as sem:
        labels = sem["label_id"].astype(np.uint8)
        label_names = [str(x) for x in sem["labels"].tolist()]
    if labels.shape != valid.shape or points.shape[:2] != labels.shape or rgb.shape[:2] != labels.shape:
        raise ValueError("E1 pointmap, RGB, and E2 semantic label grids must match exactly")
    valid &= np.isfinite(points).all(axis=-1) & np.isfinite(confidence) & (confidence > 0)
    baseline_ids, baseline_count = components_4(labels, valid)
    geo_ids, geo_count, fallback_spacing = geometry_components(
        points, labels, valid,
        float(config["geometry_gate"]["max_neighbor_distance_over_local_spacing"]),
        float(config["geometry_gate"]["max_unsigned_normal_angle_degrees"]),
    )
    valid_spacing = []
    for y0, x0, y1, x1 in ((slice(None), slice(None, -1), slice(None), slice(1, None)),
                           (slice(None, -1), slice(None), slice(1, None), slice(None))):
        edge_valid = valid[y0, x0] & valid[y1, x1] & (geo_ids[y0, x0] == geo_ids[y1, x1])
        if edge_valid.any():
            valid_spacing.append(np.linalg.norm(points[y0, x0][edge_valid] - points[y1, x1][edge_valid], axis=-1))
    median_spacing = float(np.median(np.concatenate(valid_spacing))) if valid_spacing else fallback_spacing
    semantic_rows = summarize_regions(baseline_ids, labels, valid, points, confidence, label_names, median_spacing)
    geo_rows = summarize_regions(geo_ids, labels, valid, points, confidence, label_names, median_spacing)
    Image.fromarray(region_preview(rgb, baseline_ids)).save(args.output / "semantic_4conn_regions.png")
    Image.fromarray(region_preview(rgb, geo_ids)).save(args.output / "semantic_geometry_regions.png")
    np.savez_compressed(
        args.output / "region_local.npz",
        region_id_semantic_4conn=baseline_ids,
        region_id_semantic_geometry=geo_ids,
        semantic_label_id=labels,
        valid=valid,
        frame_id=np.int64(frame_id),
        timestamp=np.asarray(timestamp),
    )
    summary = {
        "stage": "E3_region_build",
        "status": "completed",
        "frame_id": frame_id,
        "timestamp": timestamp,
        "source_pointmap": str(args.pointmap.resolve()),
        "source_scores": str(args.scores.resolve()),
        "input_shape_hw": list(labels.shape),
        "valid_pixel_count": int(valid.sum()),
        "label_names": label_names,
        "config": config,
        "semantic_4conn_region_count": baseline_count,
        "semantic_geometry_region_count": geo_count,
        "fallback_local_spacing_world_units": fallback_spacing,
        "median_accepted_edge_spacing_world_units": median_spacing,
        "temporal_association": "not run: source E1 export contains one keyframe",
        "region_stats_semantic_4conn": semantic_rows,
        "region_stats_semantic_geometry": geo_rows,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.output / "regions.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"region_stats_semantic_4conn", "region_stats_semantic_geometry"}}, indent=2))


if __name__ == "__main__":
    main()
