# E2a test: SAB3R tags on Replica office1 Keyframes

## Run

- Run ID: `E1a-replica-office1-test-20261104-003`.
- Input: all 9 completed E1a Keyframes (`0, 280, 412, 515, 648, 661, 699, 751, 881`).
- Execution: host CUDA, NVIDIA RTX 5060, PyTorch 2.7.1+cu128 / CUDA 12.8. The fixed SAB3R checkpoint SHA-256 is `0b25a93727afbbd6cc65f21e49dc70c3e1c2c7559c13c0e1f806352d440924e6`.
- One inference took about 8 s per Keyframe; total E2a elapsed time was 99.54 s. Peak allocated memory was about 6,371 MiB per Keyframe.
- All tags, raw scores, top-1/top-2 margins, masks, overlays, and inference metadata were saved for each Keyframe. The 7-prompt label set was shared across frames: floor, wall, ceiling, table, cabinet, door, and other.

## Alignment and limits

All nine model inputs and outputs were aligned exactly at 288×512; this stage introduced no additional resize or crop. The inference policy is argmax over the fixed prompts. Scores and margins are retained, but no confidence calibration or semantic accuracy claim is made here. Temporal consistency and Region association are evaluated in E3a.

## Provenance

- E2a `keyframes_manifest.json` SHA-256: `b5b9fead1bda27d5fd8236e052b9866a9bdfbcfedded716bd41e31e31dcfb220`.
- Input E1a export manifest SHA-256 is embedded in the E2a manifest.
- Per-frame inference metadata and artifact hashes are under `runs/semantic_region_pointmap/E1a-replica-office1-test-20261104-003/stages/E2a_multikeyframe_semantics/`.
