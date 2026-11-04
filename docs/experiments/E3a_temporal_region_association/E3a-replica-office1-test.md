# E3a test: temporal semantic Region association on Replica office1

## Outcome

- Run ID: `E1a-replica-office1-test-20261104-003`; 9 Keyframes, with 52/73/39/54/60/50/37/46/53 local Regions in ordinal order.
- The association stage found 4,726 candidate same-class Region pairs across 8 adjacent Keyframe pairs. Ten passed mutual pointmap correspondence, overlap, and geometry gates; 4,716 were rejected. The resulting mapping contains 454 global Regions and 464 local-to-global entries.
- Total mutual pointmap correspondences by adjacent pair ranged from 12,417 to 45,999. The association radius was 0.022875 world units (4× the scene median local spacing, 0.005719).
- The method uses reciprocal nearest 3D pointmap matches, semantic Region overlap, one-to-one partial Hungarian matching, and additional normal/offset gates for planar pairs. This follows the pointmap association motivation in *Pointmap Association and Piecewise-Plane Constraint for Consistent and Compact 3D Gaussian Segmentation Field*; the present experiment does not claim its downstream Gaussian-field method.

## Interpretation

Ten accepted links establish that the implemented association pipeline produces candidate temporal links in this scene. No semantic or geometric ground-truth labels were used to verify link correctness, so this count is not an accuracy estimate. E4a applies the frozen validation-derived error and planarity gates before any correction.

## Provenance

- E3a `temporal_regions.json` SHA-256: `a24274275b8df35030bc9a5dca1b4af3b5391cbbe007556693f8c036eb24e3d3`.
- E1a/E2a source manifest hashes are embedded in the result JSON.
- Full candidate/rejection records and per-Keyframe visualizations are under `runs/semantic_region_pointmap/E1a-replica-office1-test-20261104-003/stages/E3a_temporal_region_association/`.
