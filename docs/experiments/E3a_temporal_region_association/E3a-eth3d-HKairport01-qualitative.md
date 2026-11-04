# E3a: temporal Region association on ETH3D HKairport01

**Result: the 19 tagged Keyframes were processed and 45 adjacent-Keyframe Region links were accepted.** This is a qualitative association run. HKairport01 has no semantic or Region correspondence ground truth, so accepted links are not verified as correct and rejected links are not verified as false.

## Inputs and method

- E1a export run: `E1a-eth3d-HKairport01-qual-20261104-002`.
- E2a tagging run: `E1a-eth3d-HKairport01-qual-20261104-003` (384-pixel inference; score maps restored to the 416×512 pointmap grid).
- E3a run: `E1a-eth3d-HKairport01-qual-20261104-004`.
- All 19 E1a/E2a Keyframe IDs and source hashes passed the E3a input checks.
- The CCGS paper in `docs/papers/Pointmap Association and Piecewise-Plane Constraint for Consistent and Compact 3D Gaussian Segmentation Field.pdf` informed the geometry correspondence and Region-overlap workflow: mutual nearest 3D pointmap correspondences, semantic Region overlap, partial one-to-one Hungarian matching, and normal/plane-offset gates for planar Regions.
- MASt3R learned descriptors are absent from the E1a export; associations use geometry-based pointmap correspondences only.

## Outcome

- 1,147 local Regions across 19 Keyframes; 1,102 global Regions after temporal association.
- 26,157 candidate edges: 45 accepted and 26,112 rejected.
- Accepted links span 15 of the 18 adjacent Keyframe pairs. Three adjacent pairs had no accepted link.
- Accepted-link labels: 26 wall, 9 cabinet, 8 table, and 2 other.
- Adjacent-Keyframe mutual point correspondence counts ranged from 7,965 to 94,395; median point distances ranged from 0.00742 to 0.01096 world units.
- Association radius: `0.0320274` world units; global median local point spacing: `0.00800686` world units.
- Runtime: 16.47 s.
- `temporal_regions.json` SHA-256: `2154ede3757667dfc6ee1ce0c326b3d4b0893846a44f4d0e40458184b2988bf5`.
- E1a export manifest SHA-256: `9d7d3194f8202688248e1b67c1ae61c14abda4bab54b1e6a243bf6dae6ea0056`; E2a tagging manifest SHA-256: `e570af356933be24cd7c8bf1c66740288537bd14971c2673cf03d161b3323401`.

The matching thresholds are exploratory pilot settings carried from validation work. This run measures their behavior on a longer real sequence, not their accuracy. The substantial number of rejected candidates and the fragmented Regions are diagnostic counts, not evidence of successful or failed semantic tracking. The next stage must inspect the linked Region previews and residuals before any local refinement; E5a GT accuracy evaluation is unavailable for this scene.

## Artifacts

Per-Keyframe Region previews, all candidate-edge decisions, global Region mappings, thresholds, and input manifest hashes are under `runs/semantic_region_pointmap/E1a-eth3d-HKairport01-qual-20261104-004/stages/E3a_temporal_region_association/`.
