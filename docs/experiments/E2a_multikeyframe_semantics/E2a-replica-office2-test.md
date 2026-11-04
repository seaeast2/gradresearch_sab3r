# E2a test: SAB3R tags on Replica office2 Keyframes

## Run

- Run ID: `E1a-replica-office2-test-20261104-001`; all 13 E1a Keyframes were tagged (`0, 283, 413, 463, 512, 581, 648, 692, 762, 811, 869, 923, 966`).
- Host execution used NVIDIA RTX 5060 with PyTorch 2.7.1+cu128 / CUDA 12.8. The fixed SAB3R checkpoint SHA-256 was `0b25a93727afbbd6cc65f21e49dc70c3e1c2c7559c13c0e1f806352d440924e6`.
- Total E2a elapsed time: 143.65 s. Peak allocated memory was approximately 6,371 MiB per Keyframe.
- Every Keyframe saved semantic scores, top-1/top-2 margins, masks, overlays, and inference metadata using the shared 7-prompt set: floor, wall, ceiling, table, cabinet, door, other.

## Alignment and limits

All 13 inputs and model outputs were aligned exactly at 288×512, with no additional crop or resize in E2a. Tags use argmax over the fixed prompts; raw scores and margins are available, but no confidence calibration or semantic accuracy claim is made. Temporal association is measured in E3a.

## Provenance

- E2a `keyframes_manifest.json` SHA-256: `4ab00485ef60607cbacb0c71e891c794fb1387ffd76efda02c79dbe6603fa84a`.
- The source E1a export manifest hash is embedded in the E2a manifest.
- Per-frame result hashes and metadata are under `runs/semantic_region_pointmap/E1a-replica-office2-test-20261104-001/stages/E2a_multikeyframe_semantics/`.
