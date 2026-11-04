#!/usr/bin/env python3
"""Read-only integrity checks for a completed E1 keyframe export."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import lietorch
import numpy as np
import torch
from plyfile import PlyData


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--upstream-rgb", type=Path, required=True)
    parser.add_argument("--ply", type=Path, required=True)
    parser.add_argument("--trajectory", type=Path, required=True)
    args = parser.parse_args()
    stage = Path("runs/semantic_region_pointmap") / args.run_id / "stages/E1_slam_export/artifacts"
    manifest_path = stage / "pointmaps/export_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest["keyframes"]
    if len(records) != 1:
        raise ValueError(f"this pilot check expects one keyframe, got {len(records)}")
    record = records[0]
    npz_path = stage / "pointmaps" / record["file"]
    if sha256(npz_path) != record["sha256"]:
        raise ValueError("exported keyframe NPZ hash does not match export_manifest.json")

    with np.load(npz_path, allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    rgb_bgr = cv2.imread(str(args.upstream_rgb), cv2.IMREAD_COLOR)
    if rgb_bgr is None:
        raise FileNotFoundError(args.upstream_rgb)
    rgb = cv2.cvtColor(rgb_bgr, cv2.COLOR_BGR2RGB)
    rgb_exact = rgb.shape == data["rgb_uint8"].shape and np.array_equal(rgb, data["rgb_uint8"])

    local = data["point_local"]
    world = data["point_world"]
    confidence = data["confidence_avg"]
    valid = data["valid"]
    if local.shape != world.shape or local.shape[:2] != rgb.shape[:2]:
        raise ValueError("RGB and local/world pointmap shapes do not align")
    if confidence.shape != valid.shape or valid.shape != local.shape[:2]:
        raise ValueError("confidence/valid masks do not align with pointmap")
    if not np.isfinite(local[valid]).all() or not np.isfinite(world[valid]).all() or not np.isfinite(confidence[valid]).all():
        raise ValueError("valid pointmap entries contain NaN/Inf")

    pose = torch.as_tensor(data["pose_sim3_raw"], dtype=torch.float32, device="cuda").reshape(1, -1)
    local_tensor = torch.as_tensor(local.reshape(-1, 3), dtype=torch.float32, device="cuda")
    recomputed_world = lietorch.Sim3(pose).act(local_tensor).reshape(world.shape).cpu().numpy()
    world_max_abs_error = float(np.max(np.abs(recomputed_world - world)))

    ply = PlyData.read(str(args.ply))
    ply_vertices = ply["vertex"].count
    trajectory_rows = [line for line in args.trajectory.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = {
        "run_id": args.run_id,
        "keyframe_count": len(records),
        "frame_id": int(data["frame_id"]),
        "timestamp": str(data["timestamp"]),
        "image_size_hw": list(rgb.shape[:2]),
        "rgb_exact_match_to_upstream_keyframe_png": rgb_exact,
        "valid_pixel_count": int(valid.sum()),
        "confidence_range_valid": [float(confidence[valid].min()), float(confidence[valid].max())],
        "local_xyz_range_valid": [local[valid].min(axis=0).astype(float).tolist(), local[valid].max(axis=0).astype(float).tolist()],
        "world_xyz_range_valid": [world[valid].min(axis=0).astype(float).tolist(), world[valid].max(axis=0).astype(float).tolist()],
        "world_transform_recompute_max_abs_error": world_max_abs_error,
        "stock_ply_vertices_after_confidence_filter": int(ply_vertices),
        "trajectory_rows": len(trajectory_rows),
        "pointmap_npz_sha256": sha256(npz_path),
        "export_manifest_sha256": sha256(manifest_path),
    }
    if not rgb_exact:
        raise ValueError("exported RGB differs from upstream keyframe PNG")
    if world_max_abs_error > 1e-5:
        raise ValueError(f"world point transform mismatch: max abs error={world_max_abs_error}")
    if len(trajectory_rows) != len(records):
        raise ValueError("trajectory row count differs from keyframe count")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
