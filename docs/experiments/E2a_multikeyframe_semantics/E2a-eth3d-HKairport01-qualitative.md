# E2a: SAB3R tags on ETH3D HKairport01 Keyframes

**Result: all 19 exported Keyframes received SAB3R tags.** This is a qualitative pipeline run; HKairport01 has no semantic ground truth, so the run does not establish tagging accuracy or metric improvement.

## Setup

- Source E1a run: `E1a-eth3d-HKairport01-qual-20261104-002` (19 Keyframes).
- E2a run: `E1a-eth3d-HKairport01-qual-20261104-003`.
- Host GPU: NVIDIA GeForce RTX 5060, 8,151 MiB total; PyTorch 2.7.1+cu128, CUDA 12.8.
- SAB3R checkpoint SHA-256: `0b25a93727afbbd6cc65f21e49dc70c3e1c2c7559c13c0e1f806352d440924e6`.
- All E1 pointmaps are 416×512. To fit the available GPU memory, SAB3R inference used a 384-pixel long edge (384×320 after edge padding). Similarity scores were cropped to remove padding, bilinearly mapped to 416×512, and only then converted to labels. Every saved score map and label mask therefore matches its E1 pointmap grid.
- The lower-resolution inference is a pipeline adaptation. No semantic correctness claim is made from visual plausibility or the predicted label distribution.

## Outcome

- 19/19 Keyframes completed, with frame IDs `0, 131, 145–153, 160, 162–164, 167–169, 198`.
- E2a elapsed time: 202.19 s total; 143.75 s summed per-frame inference time.
- Peak allocated GPU memory: 5,815.4 MiB per frame.
- The fixed prompt set predicted labels `floor`, `wall`, `table`, `cabinet`, and `other` in the first Keyframe; absence of other labels is not evidence of semantic error or correctness.
- E2a manifest SHA-256: `e570af356933be24cd7c8bf1c66740288537bd14971c2673cf03d161b3323401`.

## Preserved failed attempt

The preceding run `E1a-eth3d-HKairport01-qual-20261104-002` attempted native 512×416 inference and failed on its first Keyframe with CUDA out of memory. At failure, only 71.56 MiB of 7.53 GiB was free and the allocation request was 416 MiB. Its command log SHA-256 is `54b34cf8d6d5d642e09d20d4f94f4bc4a1867eebe8a8d530b00de120d5821d04`. That run remains unchanged; the successful 384-resolution attempt is isolated in run `...-003`.

## Artifacts

Per-Keyframe scores, masks, overlays, inference metadata, resized model inputs, and source hashes are stored under `runs/semantic_region_pointmap/E1a-eth3d-HKairport01-qual-20261104-003/stages/E2a_multikeyframe_semantics/`. The stage manifest and command log are alongside them. The original 512-resolution OOM log is under the corresponding E2a stage in run `...-002`.

The SAB3R paper (`docs/papers/SAB3R.pdf`) describes mapping pixel predictions to the image's 3D points and resizing predictions for evaluation at original image dimensions. This run follows that pixel-grid mapping but uses a lower inference resolution to fit the host GPU; it does not reproduce the paper's full quantitative protocol.
