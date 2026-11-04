# E4a test: frozen error-guided local refinement on Replica office2

## Outcome

- Run ID: `E1a-replica-office2-test-20261104-001`; 2,332 persistent Regions were examined.
- The frozen validation threshold remained `2.04 × scene median local spacing`; scene spacing was 0.008661 world units and maximum radial displacement was 0.017321 units.
- Two Regions passed all gates and were applied: floor Region 307 (117,871 points, 24.62% plane-fit RMSE reduction) and wall Region 313 (139,438 points, 8.52% reduction). Their P90 temporal error scores were 2.541× and 2.128× spacing; plane inlier fractions were 0.9799 and 0.9654.
- One additional eligible floor Region (id 1618) was rolled back because plane-fit RMSE improvement was only 0.188%, below the frozen 1% minimum. Its before/after plane-fit RMSEs were 0.091875 and 0.091702 world units.
- Applied edits changed 240,694 pixels across Keyframes 413, 463, 512, 581, and 648. No other Keyframes were changed. The output confirms non-target points are exactly unchanged.
- These plane-fit diagnostics are not GT accuracy. E5a evaluates whether corrections improve held-out Replica metrics. The rollback is a preserved safety-gate outcome.

## Provenance

- E4a `refinement_summary.json` SHA-256: `65c37994254a0839fe965463789c05f0261d8cb6207a49e71e1dc05e704787c5`.
- Selection used the unchanged validation-frozen threshold and planarity/inlier gates; office2 GT was not used.
- Region-level eligibility, rollback reasons, displacements, and per-Keyframe artifact hashes are under `runs/semantic_region_pointmap/E1a-replica-office2-test-20261104-001/stages/E4a_error_guided_local_refinement/`.
