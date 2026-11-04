#!/usr/bin/env python3
"""Evaluate original and refined E1 points against paired Replica GT depth."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_depth_grid(depth_path: Path, output_hw: tuple[int, int]):
    raw = np.asarray(Image.open(depth_path))
    if raw.ndim != 2 or raw.dtype != np.uint16:
        raise ValueError(f"expected 16-bit single-channel Replica depth PNG, got {raw.shape} {raw.dtype}")
    h, w = raw.shape
    long_edge = 512
    scale = long_edge / max(w, h)
    resized_w = int(round(w * scale))
    resized_h = int(round(h * scale))
    resized = np.asarray(Image.fromarray(raw).resize((resized_w, resized_h), Image.Resampling.NEAREST))
    cx, cy = resized_w // 2, resized_h // 2
    halfw = ((2 * cx) // 16) * 8
    halfh = ((2 * cy) // 16) * 8
    left, top = cx - halfw, cy - halfh
    cropped = resized[top:cy + halfh, left:cx + halfw]
    if cropped.shape != output_hw:
        raise ValueError(f"Replica GT crop {cropped.shape} does not match E1 grid {output_hw}")
    return cropped, {
        "source_shape_hw": [h, w],
        "resized_shape_hw": [resized_h, resized_w],
        "crop_ltrb": [left, top, cx + halfw, cy + halfh],
        "output_shape_hw": list(cropped.shape),
        "resample": "PIL nearest neighbor",
        "resize_scale_x": resized_w / w,
        "resize_scale_y": resized_h / h,
    }


def backproject(depth_m, camera):
    h, w = depth_m.shape
    original_w = float(camera["w"])
    original_h = float(camera["h"])
    cropmeta = None
    # Match the official long-edge resize and center crop used for the E1 RGB.
    resized_w = int(round(original_w * 512 / max(original_w, original_h)))
    resized_h = int(round(original_h * 512 / max(original_w, original_h)))
    cx0, cy0 = resized_w // 2, resized_h // 2
    halfw = ((2 * cx0) // 16) * 8
    halfh = ((2 * cy0) // 16) * 8
    crop_left, crop_top = cx0 - halfw, cy0 - halfh
    fx = float(camera["fx"]) * resized_w / original_w
    fy = float(camera["fy"]) * resized_h / original_h
    cx = (float(camera["cx"]) + 0.5) * resized_w / original_w - 0.5 - crop_left
    cy = (float(camera["cy"]) + 0.5) * resized_h / original_h - 0.5 - crop_top
    yy, xx = np.indices((h, w), dtype=np.float32)
    xyz = np.stack(((xx - cx) * depth_m / fx, (yy - cy) * depth_m / fy, depth_m), axis=-1)
    cropmeta = {"fx": fx, "fy": fy, "cx": cx, "cy": cy, "crop_left": crop_left, "crop_top": crop_top}
    return xyz, cropmeta


def fit_umeyama(source: np.ndarray, target: np.ndarray):
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3 or len(source) < 3:
        raise ValueError("Sim(3) alignment requires matching Nx3 point arrays")
    mu_s = source.mean(axis=0)
    mu_t = target.mean(axis=0)
    src = source - mu_s
    tgt = target - mu_t
    cov = (tgt.T @ src) / len(source)
    u, singular, vt = np.linalg.svd(cov)
    d = np.eye(3)
    if np.linalg.det(u @ vt) < 0:
        d[-1, -1] = -1
    rotation = u @ d @ vt
    variance = np.sum(src * src) / len(source)
    scale = float(np.sum(singular * np.diag(d)) / max(variance, 1e-12))
    translation = mu_t - scale * (rotation @ mu_s)
    return scale, rotation, translation


def apply_sim3(points, scale, rotation, translation):
    return scale * (points @ rotation.T) + translation


def summarize(errors, mask, threshold):
    selected = errors[mask & np.isfinite(errors)]
    if not selected.size:
        return {"count": 0, "rmse_m": None, "mean_m": None, "median_m": None, "p95_m": None, "outlier_rate_over_threshold": None, "same_pixel_inlier_rate": None}
    inliers = selected <= threshold
    return {
        "count": int(selected.size),
        "rmse_m": float(np.sqrt(np.mean(selected**2))),
        "mean_m": float(np.mean(selected)),
        "median_m": float(np.median(selected)),
        "p95_m": float(np.percentile(selected, 95)),
        "outlier_rate_over_threshold": float(np.mean(~inliers)),
        "same_pixel_inlier_rate": float(np.mean(inliers)),
    }


def save_error_image(path, errors, valid, max_m=0.25):
    gray = np.zeros(errors.shape, dtype=np.uint8)
    scaled = np.clip(errors[valid] / max_m, 0, 1)
    gray[valid] = np.rint(scaled * 255).astype(np.uint8)
    Image.fromarray(gray).save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pointmap", type=Path, required=True)
    parser.add_argument("--semantic-scores", type=Path, required=True)
    parser.add_argument("--refinement", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--camera-params", type=Path, required=True)
    parser.add_argument("--depth-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    with np.load(args.pointmap, allow_pickle=False) as src:
        original = src["point_world"].astype(np.float32)
        valid = src["valid"].astype(bool)
        frame_id = int(src["frame_id"])
        timestamp = str(src["timestamp"])
    with np.load(args.refinement, allow_pickle=False) as src:
        refined = src["refined_world"].astype(np.float32)
        modified = src["modified"].astype(bool)
    with np.load(args.semantic_scores, allow_pickle=False) as src:
        semantic_ids = src["label_id"].astype(np.uint8)
        label_names = [str(x) for x in src["labels"].tolist()]
    if original.shape != refined.shape or original.shape[:2] != semantic_ids.shape:
        raise ValueError("E1/E2/E4 output grids are inconsistent")

    source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    source_record = next((x for x in source_manifest["frames"] if int(x["sequence_index"]) == frame_id), None)
    if source_record is None:
        raise ValueError(f"frame_id={frame_id} is missing from the E0a source manifest")
    rgb_path = Path(source_record["source_path"])
    depth_path = args.depth_root / f"depth{frame_id:06d}.png"
    cam_meta = json.loads(args.camera_params.read_text(encoding="utf-8"))["camera"]
    depth_raw, resize_crop = source_depth_grid(depth_path, semantic_ids.shape)
    depth_m = depth_raw.astype(np.float32) / float(cam_meta["scale"])
    gt_valid = np.isfinite(depth_m) & (depth_m > 1e-6)
    gt_xyz, intrinsics = backproject(depth_m, cam_meta)
    correspondence = valid & gt_valid & np.isfinite(original).all(axis=-1) & np.isfinite(refined).all(axis=-1)
    yy, xx = np.indices(correspondence.shape)
    fit_mask = correspondence & ((yy % 2) == 0) & ((xx % 2) == 0)
    source_fit = original[fit_mask].astype(np.float64)
    target_fit = gt_xyz[fit_mask].astype(np.float64)
    if len(source_fit) < 100:
        raise ValueError(f"too few valid pixels for evaluation-only Sim(3): {len(source_fit)}")
    scale, rotation, translation = fit_umeyama(source_fit, target_fit)
    original_aligned = apply_sim3(original.astype(np.float64), scale, rotation, translation).astype(np.float32)
    refined_aligned = apply_sim3(refined.astype(np.float64), scale, rotation, translation).astype(np.float32)
    error_before = np.linalg.norm(original_aligned - gt_xyz, axis=-1)
    error_after = np.linalg.norm(refined_aligned - gt_xyz, axis=-1)
    semantic_plane_ids = {i for i, name in enumerate(label_names) if name in {"floor", "wall", "ceiling"}}
    semantic_plane = correspondence & np.isin(semantic_ids, list(semantic_plane_ids))
    threshold = float(config["outlier_threshold_m"])
    subsets = {
        "all_valid_correspondences": correspondence,
        "semantic_plane_candidates": semantic_plane,
        "modified_points": correspondence & modified,
        "unmodified_points": correspondence & ~modified,
    }
    methods = {"B0_original": error_before, "B2_semantic_plane_refinement": error_after}
    metrics = {name: {subset: summarize(errors, mask, threshold) for subset, mask in subsets.items()} for name, errors in methods.items()}
    gt_pair_count = int(correspondence.sum())
    if gt_pair_count != int((correspondence & modified).sum() + (correspondence & ~modified).sum()):
        raise RuntimeError("evaluation subset accounting mismatch")

    save_error_image(args.output / "gt_error_before_gray.png", error_before, correspondence)
    save_error_image(args.output / "gt_error_after_gray.png", error_after, correspondence)
    change = error_after - error_before
    change_valid = correspondence & (modified | (semantic_plane & modified))
    Image.fromarray(np.where(change_valid, np.clip((change + threshold) / (2 * threshold), 0, 1) * 255, 0).astype(np.uint8)).save(args.output / "gt_error_change_gray.png")
    np.savez_compressed(
        args.output / "gt_pointwise_errors.npz",
        error_before_m=error_before.astype(np.float32),
        error_after_m=error_after.astype(np.float32),
        correspondence=correspondence,
        semantic_plane=semantic_plane,
        modified=modified,
        gt_depth_m=depth_m,
    )
    result = {
        "stage": "E5_gt_evaluation",
        "status": "completed",
        "frame_id": frame_id,
        "timestamp": timestamp,
        "scene": "Replica/office0",
        "input_pointmap": str(args.pointmap.resolve()),
        "input_pointmap_sha256": sha256_file(args.pointmap),
        "semantic_scores": str(args.semantic_scores.resolve()),
        "semantic_scores_sha256": sha256_file(args.semantic_scores),
        "refinement": str(args.refinement.resolve()),
        "refinement_sha256": sha256_file(args.refinement),
        "rgb_source": str(rgb_path),
        "rgb_source_sha256": source_record["source_sha256"],
        "depth_source": str(depth_path.resolve()),
        "depth_source_sha256": sha256_file(depth_path),
        "camera_params": str(args.camera_params.resolve()),
        "camera_params_sha256": sha256_file(args.camera_params),
        "depth_scale": float(cam_meta["scale"]),
        "depth_resize_crop": resize_crop,
        "backprojection_intrinsics": intrinsics,
        "valid_gt_depth_pixels": int(gt_valid.sum()),
        "valid_correspondence_pixels": gt_pair_count,
        "sim3_fit_pixel_count": int(fit_mask.sum()),
        "sim3_fit_sampling": "deterministic even-row/even-column lattice from B0 only",
        "sim3_fit_scale": scale,
        "sim3_fit_rotation": rotation.tolist(),
        "sim3_fit_translation": translation.tolist(),
        "same_sim3_used_for_all_methods": True,
        "metric_definition": "same-pixel Euclidean distance between aligned predicted point and Replica depth backprojection; this is a depth-derived point correspondence metric, not mesh point-to-surface distance",
        "outlier_threshold_m": threshold,
        "coverage": {"b0_existing_points": int(valid.sum()), "b2_existing_points": int(valid.sum()), "points_added_or_removed": 0},
        "metrics": metrics,
        "mean_target_error_change_m": float(np.mean(error_after[semantic_plane]) - np.mean(error_before[semantic_plane])) if semantic_plane.any() else None,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (args.output / "metrics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
