#!/usr/bin/env python3
"""Export SAB3R-labeled E1a world pointmaps as colorized binary PLY files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


PALETTE = np.asarray(
    [
        [238, 179, 44],  # floor
        [62, 155, 224],  # wall
        [157, 108, 189],  # ceiling
        [226, 86, 87],  # table
        [112, 187, 111],  # cabinet
        [231, 135, 56],  # door
        [145, 145, 145],  # other
    ],
    dtype=np.uint8,
)

VERTEX_DTYPE = np.dtype(
    {
        "names": ["x", "y", "z", "red", "green", "blue", "label_id"],
        "formats": ["<f4", "<f4", "<f4", "u1", "u1", "u1", "u1"],
        "offsets": [0, 4, 8, 12, 13, 14, 15],
        "itemsize": 16,
    }
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_ply(path: Path, points: np.ndarray, labels: np.ndarray) -> int:
    if points.ndim != 2 or points.shape[1] != 3 or labels.shape != (len(points),):
        raise ValueError("point/color label arrays have incompatible shapes")
    rgb = PALETTE[labels]
    vertices = np.empty(len(points), dtype=VERTEX_DTYPE)
    vertices["x"], vertices["y"], vertices["z"] = points.T
    vertices["red"], vertices["green"], vertices["blue"] = rgb.T
    vertices["label_id"] = labels
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {len(vertices)}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "property uchar label_id\n"
        "end_header\n"
    ).encode("ascii")
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(vertices.tobytes())
    return len(vertices)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e2a-artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    e2a = args.e2a_artifacts.resolve()
    output = args.output.resolve()
    manifest_path = e2a / "keyframes_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "completed" or manifest.get("stage") != "E2a_multikeyframe_semantics":
        parser.error("input must be a completed E2a multikeyframe stage")
    if output.exists() and any(output.iterdir()):
        parser.error(f"refusing to overwrite non-empty output directory: {output}")

    source_manifest = Path(manifest["source_e1a_export_manifest"]).resolve()
    if not source_manifest.is_file() or sha256(source_manifest) != manifest["source_e1a_export_manifest_sha256"]:
        parser.error("E1a export manifest is missing or its hash differs from E2a provenance")
    e1a_artifacts = source_manifest.parent.parent
    export = json.loads(source_manifest.read_text(encoding="utf-8"))
    labels_names = ["floor", "wall", "ceiling", "table", "cabinet", "door", "other"]
    output.mkdir(parents=True, exist_ok=True)

    frame_records = []
    merged_points = []
    merged_labels = []
    for frame in manifest["keyframes"]:
        ordinal = int(frame["ordinal"])
        frame_id = int(frame["frame_id"])
        point_record = export["keyframes"][ordinal]
        if int(point_record["frame_id"]) != frame_id:
            raise RuntimeError(f"E1a/E2a frame ordering mismatch at ordinal {ordinal}")
        pointmap_path = e1a_artifacts / "pointmaps" / point_record["file"]
        if not pointmap_path.is_file() or sha256(pointmap_path) != point_record["sha256"]:
            raise RuntimeError(f"E1a pointmap missing or hash mismatch: {pointmap_path}")
        score_path = e2a / frame["result_dir"] / "semantic_scores.npz"
        if not score_path.is_file() or sha256(score_path) != frame["semantic_scores_sha256"]:
            raise RuntimeError(f"E2a semantic score missing or hash mismatch: {score_path}")

        with np.load(pointmap_path, allow_pickle=False) as pointmap:
            points_grid = pointmap["point_world"]
            valid = pointmap["valid"].astype(bool)
            stored_frame_id = int(pointmap["frame_id"])
        with np.load(score_path, allow_pickle=False) as semantics:
            labels_grid = semantics["label_id"]
            labels = [str(value) for value in semantics["labels"].tolist()]
            semantic_frame_id = int(semantics["frame_id"])

        if labels != labels_names:
            raise RuntimeError(f"unexpected E2a label order in {score_path}: {labels}")
        if stored_frame_id != frame_id or semantic_frame_id != frame_id:
            raise RuntimeError(f"frame ID mismatch for E2a frame {frame_id}")
        if points_grid.shape[:2] != labels_grid.shape or valid.shape != labels_grid.shape:
            raise RuntimeError(f"pointmap/tag grid mismatch for frame {frame_id}")
        if int(np.max(labels_grid)) >= len(PALETTE):
            raise RuntimeError(f"label ID out of palette range for frame {frame_id}")

        usable = valid & np.isfinite(points_grid).all(axis=-1)
        points = np.asarray(points_grid[usable], dtype=np.float32)
        label_ids = np.asarray(labels_grid[usable], dtype=np.uint8)
        stem = f"kf_{ordinal:06d}_frame_{frame_id:08d}"
        ply_path = output / f"{stem}_semantic.ply"
        count = write_ply(ply_path, points, label_ids)
        frame_records.append(
            {
                "ordinal": ordinal,
                "frame_id": frame_id,
                "timestamp": frame["timestamp"],
                "vertex_count": count,
                "pointmap_sha256": sha256(pointmap_path),
                "semantic_scores_sha256": sha256(score_path),
                "ply": ply_path.name,
                "ply_sha256": sha256(ply_path),
            }
        )
        merged_points.append(points)
        merged_labels.append(label_ids)

    if len(frame_records) != int(manifest["keyframe_count"]):
        raise RuntimeError("not every E2a keyframe was exported")
    merged_path = output / "all_keyframes_semantic_world_pointmap.ply"
    merged_count = write_ply(merged_path, np.concatenate(merged_points), np.concatenate(merged_labels))
    result = {
        "status": "completed",
        "stage": "E2b_semantic_color_ply_export",
        "source_e2a_manifest": str(manifest_path),
        "source_e2a_manifest_sha256": sha256(manifest_path),
        "source_e1a_export_manifest": str(source_manifest),
        "source_e1a_export_manifest_sha256": sha256(source_manifest),
        "coordinate_frame": export.get("coordinate_contract", "point_world as saved by E1a"),
        "vertex_policy": "E1a valid pixels with finite point_world coordinates; no confidence filtering",
        "color_policy": "fixed E2a semantic palette; RGB and integer label_id stored per vertex",
        "labels": labels_names,
        "palette_rgb": {name: PALETTE[i].tolist() for i, name in enumerate(labels_names)},
        "keyframe_count": len(frame_records),
        "keyframes": frame_records,
        "merged_ply": {
            "file": merged_path.name,
            "vertex_count": merged_count,
            "contains_per_keyframe_duplicates": True,
            "sha256": sha256(merged_path),
        },
        "semantic_accuracy_note": "Colors visualize SAB3R predictions and do not imply semantic ground-truth validation.",
    }
    result_path = output / "export_manifest.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "completed", "keyframe_count": len(frame_records), "merged_vertex_count": merged_count, "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
