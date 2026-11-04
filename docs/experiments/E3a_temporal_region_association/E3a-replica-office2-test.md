# E3a test: temporal semantic Region association on Replica office2

## Outcome

- Run ID: `E1a-replica-office2-test-20261104-001`; 13 Keyframes with 39–335 local Regions each (2,357 local-to-global mapping entries overall).
- The stage enumerated 198,986 candidate same-class Region pairs across 12 adjacent Keyframe pairs. Twenty-five passed mutual pointmap correspondence, overlap, and geometry gates; 198,961 were rejected. The output contains 2,332 global Regions.
- Mutual pointmap correspondence counts by adjacent pair ranged from 22,489 to 45,435. Association radius was 0.034643 world units (4× scene median local spacing, 0.008661).
- Association uses reciprocal nearest 3D pointmap matches, semantic Region overlap, one-to-one partial Hungarian assignment, and extra normal/offset checks for planar pairs. The pointmap association motivation is drawn from *Pointmap Association and Piecewise-Plane Constraint for Consistent and Compact 3D Gaussian Segmentation Field*; this experiment does not implement or evaluate its Gaussian field.

## Interpretation

The stage produced 25 candidate temporal links, but E3a has no GT Region correspondence labels. The accepted-edge count therefore is not link accuracy. The large candidate pool and low acceptance fraction are retained as implementation and scalability evidence; E4a still decides whether any linked Region qualifies for bounded correction.

## Provenance

- E3a `temporal_regions.json` SHA-256: `2f79ed9dee414638e228a02e480e5cbc3abdf68b6e9baeb99a57dd125fe99126`.
- Source E1a/E2a manifest hashes are embedded in the output.
- Candidate/rejection records, correspondence statistics, and Region previews are under `runs/semantic_region_pointmap/E1a-replica-office2-test-20261104-001/stages/E3a_temporal_region_association/`.
