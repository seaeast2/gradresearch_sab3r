# E5a test: multi-Keyframe B0–B3 evaluation on Replica office2

## Protocol

- Scene split: `test`; scene: Replica/office2. E1a processed 1,000 RGB frames and exported 13 Keyframes (`0, 283, 413, 463, 512, 581, 648, 692, 762, 811, 869, 923, 966`).
- Paired Replica depth was transformed into GT world with camera-to-world poses from `traj.txt`. One Sim(3) was fit from B0 only across all Keyframes and reused for B0–B3; scale was 1.061624. GT was evaluation-only for E1a–E4a.
- Metrics are same-pixel point distances and scene-level nearest-neighbor F-score on a deterministic 2×2 lattice at a 5 cm threshold. They are not mesh point-to-surface metrics. B4 was unavailable because no GT semantic/plane masks are supplied.

## Results

| Method | All-point RMSE (m) | Semantic-plane RMSE (m) | 5 cm outlier rate | Mean normal error (°) | Boundary-gap error (m) | Scene F-score @5 cm |
|---|---:|---:|---:|---:|---:|---:|
| B0 original | 0.172711 | 0.138926 | 56.9482% | 13.3115 | 0.0257038 | 0.802228 |
| B1 geometry-only | 0.172710 | 0.138923 | 56.9898% | 13.2821 | 0.0257031 | 0.801946 |
| B2 semantic frame-local | 0.172707 | 0.138919 | 56.9510% | 13.2877 | 0.0257038 | 0.802865 |
| B3 semantic temporal | 0.172684 | 0.138872 | 56.8176% | 13.3017 | 0.0257038 | 0.802863 |

- B1 changed 206,885 pixels; its RMSE change was effectively zero and F-score decreased by 0.000282.
- B2 changed 133,571 pixels. Its RMSE improved by 0.000003 m, outlier rate by 0.003 percentage points, and F-score by 0.000636.
- B3 used the E4a output, including two applied Regions and one region rolled back by the frozen safety gate. RMSE improved by 0.000027 m, outlier rate by 0.130 percentage points, and F-score by 0.000634 versus B0. These are small changes and do not meet the pre-registered 10% RMSE target.
- This is one indoor test scene. It shows a small favorable direction for B2/B3 on several metrics, but does not establish a robust method benefit or support broad generalization.

## Provenance and limits

- Run ID: `E1a-replica-office2-test-20261104-001`; E0a–E5a stage manifests completed.
- E5a `metrics.json` SHA-256: `2383a6ff2ca1948a0ae7c9296ca5393859c0e94a762ca94a61ab0dc265374962`.
- Camera parameters, trajectory, source manifests, and all Keyframe hashes are recorded in `metrics.json` and the stage manifests.
- Full per-Keyframe metrics: `runs/semantic_region_pointmap/E1a-replica-office2-test-20261104-001/stages/E5a_multikeyframe_gt_evaluation/artifacts/metrics.json`.
