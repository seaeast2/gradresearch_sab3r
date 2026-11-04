# E4a test: frozen error-guided local refinement on Replica office1

## Outcome

- Run ID: `E1a-replica-office1-test-20261104-003`; 454 persistent Regions were examined.
- The validation-frozen threshold was `2.04 × scene median local spacing`; the scene spacing was 0.005719 world units. Maximum radial displacement was bounded at 0.011438 world units.
- One persistent wall Region (global id 5; two observations in Keyframes 0 and 280) passed the error, planarity, inlier, size, and correspondence gates. Its temporal P90 error score was 2.7344× spacing, plane inlier fraction 0.8961, and PCA planarity ratio 0.00672.
- The optimizer changed 24,520 pixels in frame 0 and 4,994 in frame 280 (29,514 total). No Region was rolled back, and the summary confirms all non-target points are exactly unchanged.
- The paired plane-fit RMSE improved from 0.040007 to 0.038649 world units (3.40%). This is a local optimizer diagnostic, not a GT accuracy result; E5a determines whether the change improves reconstruction against held-out GT.
- The other 453 Regions were not selected. The result is a single eligible Region, so it is insufficient to claim broad efficacy.

## Provenance

- E4a `refinement_summary.json` SHA-256: `e5bf68c7489096e3cf215d385dc21b63c1cda2ff60628c22364e31c49b029b35`.
- Frozen threshold and gates came from the validation configuration; no office1 GT was used for selection.
- Per-Keyframe modified pixel counts, displacements, and artifact hashes are in `runs/semantic_region_pointmap/E1a-replica-office1-test-20261104-003/stages/E4a_error_guided_local_refinement/`.
