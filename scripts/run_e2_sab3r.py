#!/usr/bin/env python3
"""Run SAB3R pixel semantic inference on the fixed E1 keyframe export."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
import types
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image


PROMPTS = [
    "a photo of a floor",
    "a photo of a wall",
    "a photo of a ceiling",
    "a photo of a table",
    "a photo of a cabinet",
    "a photo of a door",
    "other indoor scene content",
]
LABELS = ["floor", "wall", "ceiling", "table", "cabinet", "door", "other"]
PALETTE = np.array([
    [238, 179, 44], [62, 155, 224], [157, 108, 189], [226, 86, 87],
    [112, 187, 111], [231, 135, 56], [145, 145, 145],
], dtype=np.uint8)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--featup", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--input-npz", type=Path, required=True)
    parser.add_argument("--input-image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    featup = args.featup.resolve()
    sys.path.insert(0, str(featup))
    sys.path.insert(0, str(repo))
    # FeatUp's top-level __init__ eagerly imports an optional CUDA extension.
    # E2 only needs its upstream MaskCLIP tokenizer and text encoder, so expose
    # the package paths without triggering that unrelated extension import.
    for package_name, package_path in (
        ("featup", featup / "featup"),
        ("featup.featurizers", featup / "featup" / "featurizers"),
        ("featup.featurizers.maskclip", featup / "featup" / "featurizers" / "maskclip"),
    ):
        package = types.ModuleType(package_name)
        package.__path__ = [str(package_path)]
        sys.modules[package_name] = package
    os.environ.setdefault("MPLCONFIGDIR", str(args.output / "mplconfig"))

    import mast3r.utils.path_to_dust3r  # noqa: F401 - adds vendored DUSt3R to sys.path
    from dust3r.image_pairs import make_pairs
    from dust3r.inference import inference
    from dust3r.utils.image import load_images
    from mast3r.model import AsymmetricMASt3R
    from featup.featurizers.maskclip.clip import tokenize, load as load_clip

    args.output.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("E2 inference requires the host CUDA device")
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.manual_seed(0)

    with np.load(args.input_npz, allow_pickle=False) as source:
        rgb = source["rgb_uint8"].copy()
        frame_id = int(source["frame_id"])
        timestamp = float(source["timestamp"])
    source_image = np.asarray(Image.open(args.input_image).convert("RGB"))
    if source_image.shape != rgb.shape or not np.array_equal(source_image, rgb):
        raise RuntimeError("E1 image and NPZ RGB are not pixel-aligned")

    start = time.perf_counter()
    model = AsymmetricMASt3R(
        pos_embed="RoPE100", patch_embed_cls="PatchEmbedDust3R",
        img_size=(512, 512), head_type="catmlp+dpt", output_mode="pts3d+desc24",
        clip_head_type="dpt", dino_head_type="dpt",
        depth_mode=("exp", -float("inf"), float("inf")),
        conf_mode=("exp", 1, float("inf")), enc_embed_dim=1024, enc_depth=24,
        enc_num_heads=16, dec_embed_dim=768, dec_depth=12, dec_num_heads=12,
        two_confs=True, landscape_only=False,
    )
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    state = checkpoint.get("module", checkpoint)
    model.load_state_dict(state)
    model.eval().to(device)
    del checkpoint, state

    imgs = load_images([str(args.input_image)], size=512, verbose=True)
    loaded_hw = tuple(int(x) for x in imgs[0]["true_shape"][0])
    if loaded_hw != rgb.shape[:2]:
        raise RuntimeError(f"SAB3R crop/resize changed pixel grid: {loaded_hw} vs {rgb.shape[:2]}")
    second = copy.deepcopy(imgs[0])
    second["idx"] = 1
    second["instance"] = "1"
    pairs = make_pairs([imgs[0], second], scene_graph="complete", prefilter=None, symmetrize=True)

    with torch.inference_mode():
        result = inference(pairs, model, device, batch_size=1, verbose=True)
        # The official demo consumes pred1 CLIP features from this same inference path.
        clip_features = result["pred1"]["clip"][0].to(dtype=torch.float32)
        del result, model
        torch.cuda.empty_cache()
        clip_features = clip_features.to(device)
        clip_cpu = load_clip("ViT-B/16", device=device, download_root=str(repo / "checkpoints" / "torch_cache"))[0]
        clip_cpu.eval()
        token_ids = tokenize(PROMPTS).to(device)
        text_features = F.normalize(clip_cpu.encode_text(token_ids).float(), dim=-1)
        # SAB3R's postprocessor returns dense CLIP features in HxWxC layout.
        pixel_features = F.normalize(clip_features, dim=-1)
        scores = torch.einsum("hwc,lc->hwl", pixel_features, text_features)
        score_array = scores.cpu().numpy().astype(np.float32)
        labels = score_array.argmax(axis=-1).astype(np.uint8)
        sorted_scores = np.sort(score_array, axis=-1)
        top_score = sorted_scores[..., -1]
        margin = sorted_scores[..., -1] - sorted_scores[..., -2]

    if score_array.shape[:2] != rgb.shape[:2]:
        raise RuntimeError(f"semantic score grid {score_array.shape[:2]} != E1 RGB {rgb.shape[:2]}")
    elapsed = time.perf_counter() - start
    for label_id, label in enumerate(LABELS):
        mask = (labels == label_id).astype(np.uint8) * 255
        Image.fromarray(mask).save(args.output / f"mask_{label_id:02d}_{label}.png")
    semantic_rgb = PALETTE[labels]
    overlay = np.clip(0.58 * rgb.astype(np.float32) + 0.42 * semantic_rgb, 0, 255).astype(np.uint8)
    Image.fromarray(semantic_rgb).save(args.output / "semantic_labels.png")
    Image.fromarray(overlay).save(args.output / "semantic_overlay.png")
    np.savez_compressed(
        args.output / "semantic_scores.npz",
        scores=score_array,
        label_id=labels,
        top_similarity=top_score.astype(np.float32),
        top1_top2_margin=margin.astype(np.float32),
        labels=np.asarray(LABELS),
        prompts=np.asarray(PROMPTS),
        frame_id=np.int64(frame_id),
        timestamp=np.float64(timestamp),
    )
    gpu_memory = torch.cuda.max_memory_allocated(device) / (1024**2)
    checkpoint_path = args.checkpoint.absolute()
    metadata = {
        "stage": "E2_sab3r_semantics",
        "status": "completed",
        "execution_context": "host",
        "device": torch.cuda.get_device_name(device),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "sab3r_checkpoint": str(checkpoint_path),
        "sab3r_checkpoint_sha256": sha256_file(args.checkpoint),
        "sab3r_hf_repo": "uva-cv-lab/SAB3R",
        "sab3r_hf_revision": checkpoint_path.parents[2].name,
        "input_npz": str(args.input_npz.resolve()),
        "input_npz_sha256": sha256_file(args.input_npz),
        "input_image": str(args.input_image.resolve()),
        "input_image_sha256": sha256_file(args.input_image),
        "frame_id": frame_id,
        "timestamp": timestamp,
        "input_shape_hw": list(rgb.shape[:2]),
        "sab3r_loaded_shape_hw": list(loaded_hw),
        "resize_crop_alignment": "exact; no crop or resize was introduced for this E1 keyframe",
        "labels": LABELS,
        "text_prompts": PROMPTS,
        "scoring": "cosine similarity between normalized SAB3R per-pixel CLIP features and normalized CLIP text embeddings",
        "mask_policy": "argmax over fixed candidate prompts; raw scores and top1-top2 margin saved; no confidence calibration or threshold claimed",
        "elapsed_seconds": elapsed,
        "peak_allocated_gpu_mib": gpu_memory,
        "features_shape_hwc": list(clip_features.shape),
    }
    (args.output / "inference.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
