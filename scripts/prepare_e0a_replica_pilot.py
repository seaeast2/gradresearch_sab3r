#!/usr/bin/env python3
"""Prepare a small RGB-only PNG sequence from the existing Replica office0 frames."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--count", type=int, default=30)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    if not source.is_dir():
        parser.error(f"source directory not found: {source}")
    if args.count < 2:
        parser.error("--count must be at least 2")
    if destination.exists():
        parser.error(f"destination exists; use a new run ID: {destination}")
    images = sorted(source.glob("frame*.jpg"))
    if len(images) < args.count:
        parser.error(f"found {len(images)} RGB frames, need {args.count}")
    destination.mkdir(parents=True)
    records = []
    for index, image_path in enumerate(images[:args.count]):
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            parser.error(f"failed to decode RGB image: {image_path}")
        output = destination / f"{index:06d}.png"
        if not cv2.imwrite(str(output), image, [cv2.IMWRITE_PNG_COMPRESSION, 3]):
            parser.error(f"failed to write PNG: {output}")
        records.append({
            "sequence_index": index,
            "source_path": str(image_path),
            "source_sha256": sha256(image_path),
            "output_path": output.name,
            "output_sha256": sha256(output),
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
        })
    manifest = {
        "dataset_id": "Replica/office0",
        "source_directory": str(source),
        "selection": f"first {args.count} sorted frame*.jpg files; RGB only; no depth/pose copied",
        "encoding": "lossless PNG from decoded source JPEG pixels",
        "rgb_frame_count": len(records),
        "frames": records,
    }
    (destination / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
