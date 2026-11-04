# E5a test: multi-Keyframe B0–B3 evaluation on Replica room1

## Protocol

- Scene split: `test`; scene: Replica/room1.
- E1a consumed 1,000 consecutive RGB frames and exported 10 Keyframes (frame ids `0, 45, 165, 212, 242, 260, 276, 427, 465, 931`). E2a tagged all 10 at the aligned 288×512 grid.
- E3a found 6,638 candidate Region pairs across nine adjacent Keyframe pairs; 13 passed its geometry/semantic gates and 6,625 were rejected. This confirms some temporal links but does not establish their ground-truth correctness.
- E4a used the validation-frozen error threshold `2.04 × scene median local spacing`. It selected 0 of 634 persistent Regions; all refined pointmaps equal their inputs.
- E5a transformed paired Replica depth into GT world using `traj.txt`, fit one scene-level Sim(3) from B0 only, and reused it for B0–B3. Scale was 1.027135. GT was not used by E1a–E4a selection or refinement.
- Same-pixel distances are point-to-point correspondences, not mesh point-to-surface distances. Scene F-score uses a deterministic 2×2 image lattice and 5 cm nearest-neighbor threshold. B4 was not run because the supplied export has no GT semantic/plane masks.

## Results

| Method | All-point RMSE (m) | Semantic-plane RMSE (m) | 5 cm outlier rate | Mean normal error (°) | Mean semantic boundary gap error (m) | Scene F-score @5 cm |
|---|---:|---:|---:|---:|---:|---:|
| B0 original | 0.190151 | 0.188694 | 66.4623% | 13.4751 | 0.0122369 | 0.757167 |
| B1 geometry-only | 0.190146 | 0.188690 | 66.4680% | 13.4728 | 0.0122385 | 0.757070 |
| B2 semantic frame-local | 0.190150 | 0.188694 | 66.5271% | 13.4713 | 0.0122369 | 0.757563 |
| B3 semantic temporal | 0.190151 | 0.188694 | 66.4623% | 13.4751 | 0.0122369 | 0.757167 |

- B1 changed 109,213 pixels and B2 changed 106,064, but each metric moved only slightly. B1's scene F-score decreased by 0.000098; B2's increased by 0.000396 while its outlier rate worsened by 0.0648 percentage points. These small mixed changes do not support a meaningful improvement claim.
- B3 is identical to B0 because E4a found no eligible temporal Region. E3a's accepted links did not result in a Region passing E4a's frozen selection and plane-quality gates.
- This test scene does not support H1–H3. The result is a negative/mixed test outcome, not evidence that the methods are equivalent. H4 ablations and more independent scenes remain necessary.

## Provenance and limits

- Run: `E1a-replica-room1-test-20261104-001`; all E1a–E5a stage manifests report `completed`.
- E5a metrics SHA-256: `3c9c0dc2c0488f2aa4f9635af43b5212315766a7cce2d7c19de07ccc496dd52d`.
- E1a/E2a/E3a/E4a source-manifest SHA-256 values are recorded in the metrics artifact; E3a temporal Region JSON SHA-256 is `25a6d30397ca4d1e1b29776eb3d6e40d024be9e86c32281a9027a7e0f079e37e`; E4a refinement summary SHA-256 is `51d77dca5585ab42918b335e788a6b3dea3d3d230de388cbecadc4b8a396f0a1`.
- Replica camera parameter SHA-256: `ffbefdeb53755e1490d6936dffdee253510e68d5e443e1ba91e60202addc1a0a`; trajectory SHA-256: `5c650f90192da13b628308a6cbaf68fa6e048cfaa8f1870c5e66572296cc5c7d`.
- Full per-Keyframe metrics and source hashes: `runs/semantic_region_pointmap/E1a-replica-room1-test-20261104-001/stages/E5a_multikeyframe_gt_evaluation/artifacts/metrics.json`.
- One test scene is insufficient for a broad generalization claim; all sampled environments here are indoor Replica scenes.
