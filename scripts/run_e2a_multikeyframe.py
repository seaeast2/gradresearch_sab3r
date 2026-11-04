#!/usr/bin/env python3
"""Apply the fixed SAB3R prompt set to every Keyframe in an E1a export."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e1a-artifacts", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--featup", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inference-size", type=int, default=512)
    args = parser.parse_args()

    e1a = args.e1a_artifacts.resolve()
    output = args.output.resolve()
    if os.environ.get("EXPERIMENT_STAGE") != "E2a_multikeyframe_semantics":
        parser.error("invoke this command inside E2a_multikeyframe_semantics")
    export_path = e1a / "pointmaps" / "export_manifest.json"
    export = json.loads(export_path.read_text(encoding="utf-8"))
    if export.get("keyframe_count", 0) < 2:
        parser.error("E2a requires the completed E1a multi-Keyframe gate")
    if output.exists() and any(output.iterdir()):
        parser.error(f"refusing to mix with existing E2a outputs: {output}")
    output.mkdir(parents=True, exist_ok=True)
    input_images = output / "keyframe_inputs"
    keyframe_outputs = output / "keyframes"
    input_images.mkdir()
    keyframe_outputs.mkdir()

    script = Path(__file__).with_name("run_e2_sab3r.py").resolve()
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(args.repo.resolve()), str(args.featup.resolve())]
        + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env.setdefault("MPLCONFIGDIR", "/tmp/sab3r-mpl-cache")
    started = time.perf_counter()
    records = []
    for keyframe in export["keyframes"]:
        pointmap = e1a / "pointmaps" / keyframe["file"]
        if not pointmap.is_file() or sha256(pointmap) != keyframe["sha256"]:
            raise RuntimeError(f"E1a pointmap missing or hash mismatch: {pointmap}")
        with np.load(pointmap, allow_pickle=False) as arrays:
            rgb = arrays["rgb_uint8"].copy()
            if rgb.shape[:2] != (keyframe["height"], keyframe["width"]):
                raise RuntimeError(f"Keyframe RGB shape mismatch: {pointmap}")
            frame_id = int(arrays["frame_id"])
            timestamp = float(arrays["timestamp"])
        if frame_id != keyframe["frame_id"]:
            raise RuntimeError(f"frame ID mismatch between pointmap and export manifest: {pointmap}")

        stem = f"kf_{keyframe['ordinal']:06d}_frame_{frame_id:08d}"
        image = input_images / f"{stem}.png"
        Image.fromarray(rgb, mode="RGB").save(image)
        result_dir = keyframe_outputs / stem
        command = [
            sys.executable, str(script),
            "--repo", str(args.repo.resolve()),
            "--featup", str(args.featup.resolve()),
            "--checkpoint", str(args.checkpoint.resolve()),
            "--input-npz", str(pointmap),
            "--input-image", str(image),
            "--output", str(result_dir),
            "--stage-name", "E2a_multikeyframe_semantics",
            "--inference-size", str(args.inference_size),
        ]
        subprocess.run(command, cwd=args.repo.resolve(), env=env, check=True)
        score_file = result_dir / "semantic_scores.npz"
        inference_file = result_dir / "inference.json"
        with np.load(score_file, allow_pickle=False) as scores:
            label_ids, label_counts = np.unique(scores["label_id"], return_counts=True)
            label_distribution = {str(int(label)): int(count) for label, count in zip(label_ids, label_counts)}
        records.append({
            "ordinal": keyframe["ordinal"],
            "frame_id": frame_id,
            "timestamp": timestamp,
            "pointmap": str(pointmap.relative_to(e1a)),
            "pointmap_sha256": sha256(pointmap),
            "input_image": str(image.relative_to(output)),
            "input_image_sha256": sha256(image),
            "result_dir": str(result_dir.relative_to(output)),
            "semantic_scores_sha256": sha256(score_file),
            "inference_sha256": sha256(inference_file),
            "label_pixel_counts_by_id": label_distribution,
        })

    manifest = {
        "stage": "E2a_multikeyframe_semantics",
        "status": "completed",
        "source_e1a_export_manifest": str(export_path),
        "source_e1a_export_manifest_sha256": sha256(export_path),
        "keyframe_count": len(records),
        "labels_and_prompts": "fixed by scripts/run_e2_sab3r.py and shared across every Keyframe",
        "inference_size_long_edge": args.inference_size,
        "elapsed_seconds": time.perf_counter() - started,
        "keyframes": records,
    }
    if len(records) != export["keyframe_count"]:
        raise RuntimeError("not every E1a Keyframe received SAB3R tags")
    (output / "keyframes_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "completed", "keyframe_count": len(records), "manifest": str(output / 'keyframes_manifest.json')}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
