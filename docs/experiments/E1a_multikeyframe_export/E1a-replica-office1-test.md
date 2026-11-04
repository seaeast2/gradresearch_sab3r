# E1a test: MASt3R-SLAM multi-Keyframe export on Replica office1

## Run

- Run ID: `E1a-replica-office1-test-20261104-003` (extension workflow config).
- Input: all 1,000 RGB frames from Replica `office1/results`, staged as lossless PNGs; depth and trajectory were not passed to SLAM.
- Host preflight: passed. RTX 5060 (8,151 MiB reported), Python 3.11.18, CUDA available, pinned MASt3R-SLAM checkout clean at `e6f4e3d474fad0e11f561482012be864ba8c3f17`, required checkpoints present.
- MASt3R-SLAM used `single_thread: true`, keyframe buffer 32, and the pinned `config/base.yaml` inherited by the run-specific config.

## Outcome

E1a completed successfully and exported 9 Keyframes at source frame ids `0, 280, 412, 515, 648, 661, 699, 751, 881`. Runtime was 151.60 s; host-wide peak GPU memory reported by the stage monitor was 4,306 MiB across 757 samples. Exported pointmaps and correspondence inputs passed the multi-Keyframe gate.

This verifies the office1 sequence can be processed by the current export hook. It does not evaluate semantic quality, temporal Region correctness, or geometric accuracy; those belong to E2a–E5a.

## Provenance

- E0a `preflight.json` SHA-256: `f3d317fc5c72de01bfa8cddf1ce844f1c95812c40113e9e7d2eef138088041f9`.
- E1a `pointmaps/export_manifest.json` SHA-256: `5b75fe6ace72efdb0d19c49e4e437c93ecc5b46443374c544ee57554a25c4285`.
- Input RGB mapping and source hashes: `runs/semantic_region_pointmap/E1a-replica-office1-test-20261104-003/stages/E0a_preflight/artifacts/input_rgb/source_manifest.json`.
- Full stage logs and pointmap hashes: `runs/semantic_region_pointmap/E1a-replica-office1-test-20261104-003/stages/E1a_multikeyframe_slam_export/`.
