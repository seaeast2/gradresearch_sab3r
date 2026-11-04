# E4a: error-guided local refinement on ETH3D HKairport01

**Result: one wall Region passed the frozen local refinement gates.** The selected Region was refined in two Keyframes. This is a qualitative run without geometry ground truth; the plane-fit residual is an internal fitting measure and does not establish improved scene accuracy.

## Inputs and method

- E1a: `E1a-eth3d-HKairport01-qual-20261104-002`.
- E2a: `E1a-eth3d-HKairport01-qual-20261104-003`.
- E3a: `E1a-eth3d-HKairport01-qual-20261104-004`.
- E4a run: `E1a-eth3d-HKairport01-qual-20261104-005`.
- The existing E4a config was used unchanged. Its frozen temporal-error threshold is 2.04 local-spacing units, derived from two Replica validation scenes. Candidate classes are floor, wall, and ceiling. Camera poses and non-target points remain fixed.

## Outcome

- 1,102 global Region candidates; one Region was applied and none were rolled back.
- The applied wall Region (global ID 591) connected frame 163/local Region 30 and frame 164/local Region 52, with 287 mutual point correspondences.
- Its temporal P90 error score was 2.541 local-spacing units. The fitted plane had PCA planarity ratio 0.00484 and RANSAC inlier fraction 0.927.
- Internal plane-fit RMSE decreased from 0.009284 to 0.007810 world units (15.88%). This measures fit to the estimated plane used by the optimizer, not distance to ground truth.
- 281 points changed in frame 163 and 572 in frame 164 (853 total). Mean displacement was 0.00340 and 0.00420 world units respectively; maximum observed displacement was 0.01117 world units. All non-target points remained exactly unchanged.
- Runtime: 8.96 s.
- `refinement_summary.json` SHA-256: `90f8044b20a6c7633b056255002e71883aa91b5514c0c6ffac9d636bb5db6a43`.
- Source E3a hash: `2154ede3757667dfc6ee1ce0c326b3d4b0893846a44f4d0e40458184b2988bf5`.

Only one Region was refined because most candidates did not pass all semantic, temporal-error, size, correspondence, and planar-fit checks. This sample is too small to validate the frozen threshold or determine whether the correction improved the actual scene. HKairport01 has no GT depth/mesh for E5a evaluation.

## Artifacts

Per-Keyframe output pointmaps and the full candidate eligibility, residual, and modification records are under `runs/semantic_region_pointmap/E1a-eth3d-HKairport01-qual-20261104-005/stages/E4a_error_guided_local_refinement/`.
