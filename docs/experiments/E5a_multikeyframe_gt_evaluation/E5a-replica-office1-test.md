# E5a test: multi-Keyframe B0–B3 evaluation on Replica office1

## Protocol

- Scene split: `test`; scene: Replica/office1. E1a exported 9 Keyframes from a 1,000-frame RGB sequence (`0, 280, 412, 515, 648, 661, 699, 751, 881`).
- Paired Replica depth was backprojected and transformed to GT world with camera-to-world poses from `traj.txt`. One Sim(3) was fit from B0 only across all Keyframes and reused for B0–B3; scale was 1.052735. GT was evaluation-only for E1a–E4a.
- Metrics are same-pixel point distances and scene-level nearest-neighbor F-score on a deterministic 2×2 pixel lattice at a 5 cm threshold. Same-pixel metrics are not mesh point-to-surface errors.
- B4 was unavailable: the supplied Replica export contains depth and trajectory, but no GT semantic/plane masks.

## Results

| Method | All-point RMSE (m) | Semantic-plane RMSE (m) | 5 cm outlier rate | Mean normal error (°) | Boundary-gap error (m) | Scene F-score @5 cm |
|---|---:|---:|---:|---:|---:|---:|
| B0 original | 0.064210 | 0.052576 | 30.4345% | 13.9292 | 0.0045823 | 0.929415 |
| B1 geometry-only | 0.064201 | 0.052560 | 30.4243% | 13.9303 | 0.0045831 | 0.929479 |
| B2 semantic frame-local | 0.064194 | 0.052539 | 30.3303% | 13.8002 | 0.0045823 | 0.929908 |
| B3 semantic temporal | 0.064212 | 0.052581 | 30.4459% | 13.9242 | 0.0045823 | 0.929416 |

- B1 changed 145,514 pixels. Its RMSE improved by 0.000009 m and F-score by 0.000065; these are negligible changes.
- B2 changed 186,856 pixels. It had the best values in this run, but the RMSE improvement was 0.000015 m and F-score increase 0.000493. These small gains do not establish a meaningful semantic refinement benefit.
- B3 used the E4a output, including the accepted temporal wall Region, but was marginally worse than B0 in RMSE and outlier rate; F-score was higher by 0.000002. The local plane-fit improvement reported by E4a did not translate into a measurable scene-level gain.
- This one test scene yields a mixed, near-zero result and does not support H1–H3. It is not evidence of equivalence; more independent scenes and the planned safety ablations remain necessary.

## Provenance and limits

- Run ID: `E1a-replica-office1-test-20261104-003`; E0a–E5a stage manifests completed.
- E5a metrics SHA-256: `2767892fe853c021b6b148014478adb3107e3d9b365a9de4cbcf827ea8c6bf2e`.
- Camera parameters SHA-256: `ffbefdeb53755e1490d6936dffdee253510e68d5e443e1ba91e60202addc1a0a`; office1 trajectory, input, and stage manifest hashes are in `metrics.json` and the stage manifests.
- Full per-Keyframe metrics: `runs/semantic_region_pointmap/E1a-replica-office1-test-20261104-003/stages/E5a_multikeyframe_gt_evaluation/artifacts/metrics.json`.
- The sample is one indoor Replica test scene. It cannot support broad environment generalization.
