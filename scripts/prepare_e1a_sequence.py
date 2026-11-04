#!/usr/bin/env python3
"""Copy an ordered RGB sequence into an isolated E1a run input directory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="RGB-only image sequence directory")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--minimum-frames", type=int, default=2)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    if not source.is_dir():
        parser.error(f"source directory not found: {source}")
    if args.minimum_frames < 2:
        parser.error("--minimum-frames must be at least 2")
    if destination.exists():
        parser.error(f"destination exists; use a new run ID: {destination}")
    files = [path for path in source.iterdir() if path.is_file()]
    jpeg_images = sorted(
        (path for path in files if path.suffix.lower() in {".jpg", ".jpeg"}),
        key=lambda path: path.name,
    )
    png_images = sorted(
        (path for path in files if path.suffix.lower() == ".png"),
        key=lambda path: path.name,
    )
    # Replica results folders also contain depth PNGs. Prefer their RGB JPEGs;
    # use PNG only for a PNG-only RGB sequence such as a prepared E0a input.
    images = jpeg_images or png_images
    if len(images) < args.minimum_frames:
        parser.error(f"found {len(images)} RGB images; need at least {args.minimum_frames}")

    destination.mkdir(parents=True)
    records = []
    for index, image in enumerate(images):
        output = destination / f"{index:08d}.png"
        decoded = cv2.imread(str(image), cv2.IMREAD_COLOR)
        if decoded is None:
            raise RuntimeError(f"failed to decode RGB image: {image}")
        if not cv2.imwrite(str(output), decoded, [cv2.IMWRITE_PNG_COMPRESSION, 3]):
            raise RuntimeError(f"failed to encode PNG: {output}")
        round_trip = cv2.imread(str(output), cv2.IMREAD_COLOR)
        if round_trip is None or not (round_trip == decoded).all():
            raise RuntimeError(f"decoded RGB pixels changed during PNG staging: {image}")
        records.append({
            "sequence_index": index,
            "source_filename": image.name,
            "source_path": str(image),
            "source_sha256": sha256(image),
            "staged_filename": output.name,
            "staged_sha256": sha256(output),
            "decoded_shape_hwc": list(decoded.shape),
        })

    manifest = {
        "dataset_id": source.name,
        "source_directory": str(source),
        "selection": (
            "all immediate JPEG images, lexicographically sorted by filename"
            if jpeg_images else
            "all immediate PNG images (PNG-only source), lexicographically sorted by filename"
        ),
        "encoding": "lossless PNG preserving decoded source RGB pixels",
        "rgb_frame_count": len(records),
        "frame_index_mapping": "staged zero-padded filename order maps to source_filename in this manifest",
        "frames": records,
    }
    (destination / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"rgb_frame_count": len(records), "manifest": str(destination / 'source_manifest.json')}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
