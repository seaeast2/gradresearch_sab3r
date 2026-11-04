"""Pixel-aligned, lossless-ish MASt3R-SLAM keyframe export for offline refinement."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def _array(value: Any, dtype: Any | None = None) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    result = np.asarray(value)
    if dtype is not None:
        result = result.astype(dtype, copy=False)
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def export_keyframes(keyframes: Any, timestamps: Any, output_dir: str | Path) -> None:
    """Export final per-keyframe RGB, local/world points, confidence, and Sim(3).

    Called inside MASt3R-SLAM after its final single-threaded optimization and
    before its stock calibrated PLY writer can constrain/mutate ``X_canon``.
    Arrays preserve the model's keyframe pixel grid; no confidence filtering is
    applied here.
    """
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to mix with existing export artifacts: {output}")
    output.mkdir(parents=True, exist_ok=True)
    keyframe_dir = output / "keyframes"
    keyframe_dir.mkdir()
    records: list[dict[str, Any]] = []

    for ordinal in range(len(keyframes)):
        frame = keyframes[ordinal]
        frame_id = int(frame.frame_id)
        local = _array(frame.X_canon, np.float32).reshape(-1, 3)
        conf_accum = _array(frame.C, np.float32).reshape(-1)
        confidence = _array(frame.get_average_conf(), np.float32).reshape(-1)
        rgb_float = _array(frame.uimg, np.float32)
        if rgb_float.ndim != 3 or rgb_float.shape[-1] != 3:
            raise ValueError(f"keyframe {frame_id}: expected HxWx3 RGB, got {rgb_float.shape}")
        height, width = rgb_float.shape[:2]
        if len(local) != height * width or len(confidence) != height * width:
            raise ValueError(
                f"keyframe {frame_id}: RGB {height}x{width} does not align with "
                f"point/confidence counts {len(local)}/{len(confidence)}"
            )
        rgb = np.clip(np.rint(rgb_float * 255.0), 0, 255).astype(np.uint8)
        local = local.reshape(height, width, 3)
        confidence = confidence.reshape(height, width)
        conf_accum = conf_accum.reshape(height, width)
        pose = _array(frame.T_WC.data, np.float64).reshape(-1)
        world = _array(frame.T_WC.act(frame.X_canon), np.float32).reshape(height, width, 3)
        valid = (
            np.isfinite(local).all(axis=-1)
            & np.isfinite(world).all(axis=-1)
            & np.isfinite(confidence)
        )
        timestamp = str(timestamps[frame_id])
        filename = f"kf_{ordinal:06d}_frame_{frame_id:08d}.npz"
        destination = keyframe_dir / filename
        np.savez_compressed(
            destination,
            rgb_uint8=rgb,
            point_local=local,
            point_world=world,
            confidence_avg=confidence,
            confidence_accumulated=conf_accum,
            valid=valid,
            pose_sim3_raw=pose,
            frame_id=np.asarray(frame_id, dtype=np.int64),
            timestamp=np.asarray(timestamp),
            fusion_count=np.asarray(int(frame.N), dtype=np.int32),
            update_count=np.asarray(int(frame.N_updates), dtype=np.int32),
            processed_shape=np.asarray(_array(frame.img_shape).reshape(-1), dtype=np.int32),
            true_shape=np.asarray(_array(frame.img_true_shape).reshape(-1), dtype=np.int32),
        )
        records.append({
            "ordinal": ordinal,
            "frame_id": frame_id,
            "timestamp": timestamp,
            "file": f"keyframes/{filename}",
            "sha256": _sha256(destination),
            "height": height,
            "width": width,
            "valid_pixel_count": int(valid.sum()),
            "fusion_count": int(frame.N),
            "update_count": int(frame.N_updates),
        })

    manifest = {
        "format": "semantic-region-pointmap-keyframes-v1",
        "coordinate_contract": {
            "point_local": "MASt3R-SLAM Frame.X_canon in canonical camera/local coordinates",
            "point_world": "Frame.T_WC.act(point_local), in final MASt3R-SLAM world coordinates",
            "pose_sim3_raw": "raw lietorch Sim3 embedded representation; retain without reinterpretation",
            "confidence_avg": "Frame.get_average_conf(); unthresholded",
            "pixel_grid": "top-left origin, row-major HxW, aligned to exported rgb_uint8",
            "rgb": "Frame.uimg after MASt3R-SLAM resize/downsample preprocessing, RGB order",
        },
        "keyframe_count": len(records),
        "keyframes": records,
    }
    (output / "export_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
