# E1a test: MASt3R-SLAM multi-Keyframe export on Replica office2

## Run

- Run ID: `E1a-replica-office2-test-20261104-001` (E1a–E6a extension workflow).
- Input: all 1,000 RGB frames from Replica `office2/results`, staged as lossless PNGs; depth and trajectory were not passed to SLAM.
- Host preflight passed: RTX 5060 (8,151 MiB reported), Python 3.11.18, CUDA available, clean pinned MASt3R-SLAM checkout at `e6f4e3d474fad0e11f561482012be864ba8c3f17`, and required checkpoints present.
- E1a used the run-specific configuration with `single_thread: true`, keyframe buffer 32, and the pinned `config/base.yaml`.

## Outcome

E1a completed on the 1,000-frame sequence and exported 13 Keyframes at source frame ids `0, 283, 413, 463, 512, 581, 648, 692, 762, 811, 869, 923, 966`. Runtime was 156.30 s; the host-wide GPU memory monitor recorded a 4,614 MiB peak over 780 samples. The multi-Keyframe export gate passed.

This confirms that the current export hook processes office2. Semantic tags, temporal association quality, and GT geometric accuracy are evaluated in E2a–E5a.

## Provenance

- E0a `preflight.json` SHA-256: `b596b4300e02ad754894f489aa9b6350e8d8d97897c2540fa3aee11d7b641b7d`.
- E1a `pointmaps/export_manifest.json` SHA-256: `55b1a18d2e5884a9ffe1bbd14a1dbaf0be1047d33df9f747fa2f863c6790670d`.
- Input RGB mapping and source hashes: `runs/semantic_region_pointmap/E1a-replica-office2-test-20261104-001/stages/E0a_preflight/artifacts/input_rgb/source_manifest.json`.
- Full logs and per-Keyframe pointmap hashes: `runs/semantic_region_pointmap/E1a-replica-office2-test-20261104-001/stages/E1a_multikeyframe_slam_export/`.
