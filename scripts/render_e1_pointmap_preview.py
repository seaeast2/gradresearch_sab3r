#!/usr/bin/env python3
"""Render an RGB/pointmap sanity preview from one E1 keyframe NPZ."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("npz", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--stride", type=int, default=4)
    args = parser.parse_args()
    if args.stride < 1:
        parser.error("--stride must be positive")
    with np.load(args.npz, allow_pickle=False) as data:
        rgb = data["rgb_uint8"]
        xyz = data["point_world"]
        valid = data["valid"]
    sampled = valid[::args.stride, ::args.stride]
    colors = rgb[::args.stride, ::args.stride][sampled].astype(np.float32) / 255.0
    points = xyz[::args.stride, ::args.stride][sampled]
    finite = np.isfinite(points).all(axis=1)
    points, colors = points[finite], colors[finite]

    fig = plt.figure(figsize=(16, 5.5), constrained_layout=True)
    image_ax = fig.add_subplot(1, 3, 1)
    image_ax.imshow(rgb)
    image_ax.set_title("Keyframe RGB (pointmap pixel grid)")
    image_ax.axis("off")
    for index, (horizontal, label) in enumerate(((0, "X"), (1, "Y")), start=2):
        ax = fig.add_subplot(1, 3, index)
        ax.scatter(points[:, horizontal], points[:, 2], c=colors, s=1.0, linewidths=0, rasterized=True)
        ax.set_xlabel(f"World {label} (SLAM units)")
        ax.set_ylabel("World Z (SLAM units)")
        ax.set_title(f"RGB-colored pointmap: {label}–Z projection")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=0.18)
    fig.suptitle(f"E1 pointmap preview — {len(points):,} sampled valid points")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160, facecolor="white")
    plt.close(fig)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
