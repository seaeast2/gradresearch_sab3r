# E6a multi-Keyframe experiment synthesis

Generated UTC: 2026-11-04T10:50:44+00:00

## Scene-level B0–B3 evaluation

| Scene | Split | KFs | B0 RMSE (m) | B1 RMSE | B2 RMSE | B3 RMSE | B0 F@5cm | B3 F@5cm | B3 modified px | B3 selected / rollback |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Replica/room1 | test | 10 | 0.190151 | 0.190146 | 0.190150 | 0.190151 | 0.757167 | 0.757167 | 0 | 0 / 0 |
| Replica/office1 | test | 9 | 0.064210 | 0.064201 | 0.064194 | 0.064212 | 0.929415 | 0.929416 | 29514 | 1 / 0 |
| Replica/office2 | test | 13 | 0.172711 | 0.172710 | 0.172707 | 0.172684 | 0.802228 | 0.802863 | 240694 | 2 / 1 |

## Validation reference

| Scene | Split | KFs | B0 RMSE (m) | B2 RMSE (m) | B3 RMSE (m) | B0 F@5cm | B3 F@5cm |
|---|---|---:|---:|---:|---:|---:|---:|
| Replica/room0 | validation (legacy metrics omitted split field) | 7 | 0.161391 | 0.161391 | 0.161391 | 0.869102 | 0.869102 |

B0–B3 use one B0-derived scene Sim(3), reused within each scene. GT is evaluation-only. These are same-pixel point distances and 5 cm nearest-neighbor F-scores on an image lattice, not mesh point-to-surface errors. B4 Oracle was unavailable because the provided Replica exports lack GT semantic/plane masks.

## H4 ablations

| Factor | Scene | Baseline B3 RMSE | Ablation B3 RMSE | Δ RMSE | Baseline F@5cm | Ablation F@5cm | Applied / rollback |
|---|---|---:|---:|---:|---:|---:|---:|
| robust_loss=squared | Replica/room1 | 0.190151 | 0.190151 | +0.000000 | 0.757167 | 0.757167 | 0 / 0 |
| robust_loss=squared | Replica/office1 | 0.064212 | 0.064206 | -0.000007 | 0.929416 | 0.929419 | 1 / 0 |
| robust_loss=squared | Replica/office2 | 0.172684 | 0.172680 | -0.000004 | 0.802863 | 0.802899 | 2 / 1 |
| confidence_weights=uniform | Replica/room1 | 0.190151 | 0.190151 | +0.000000 | 0.757167 | 0.757167 | 0 / 0 |
| confidence_weights=uniform | Replica/office1 | 0.064212 | 0.064206 | -0.000007 | 0.929416 | 0.929418 | 1 / 0 |
| confidence_weights=uniform | Replica/office2 | 0.172684 | 0.172687 | +0.000003 | 0.802863 | 0.802634 | 2 / 1 |
| maximum_radial_displacement_over_global_spacing=1.0 | Replica/room1 | 0.190151 | 0.190151 | +0.000000 | 0.757167 | 0.757167 | 0 / 0 |
| maximum_radial_displacement_over_global_spacing=1.0 | Replica/office1 | 0.064212 | 0.064208 | -0.000004 | 0.929416 | 0.929416 | 1 / 0 |
| maximum_radial_displacement_over_global_spacing=1.0 | Replica/office2 | 0.172684 | 0.172684 | -0.000000 | 0.802863 | 0.802861 | 2 / 1 |

## Interpretation and limitations

- Three independent Replica test scenes (room1, office1, office2) were evaluated; all are indoor scenes, so environment generalization remains untested.
- The E5a main comparisons show very small and mixed B1–B3 changes; the pre-set 10% RMSE improvement target was not reached. No positive H1–H3 claim is supported by these results.
- The three H4 factor ablations show small, scene-dependent changes. Huber versus squared loss and confidence versus uniform weights do not show a consistent scene-level accuracy advantage; halving the displacement bound preserves the configured safety limit but does not yield consistent metric gains.
- The local point-to-plane objective can improve while GT scene metrics remain unchanged or worsen. E4a rollback and exact non-target invariants are part of the result, not omitted failures.
- B4 Oracle is unavailable because the supplied exports have no GT semantic/plane masks. E5a used paired GT depth and point-cloud surface F-score; the office2 mesh was not used for triangle point-to-surface scoring, and no matching meshes were found for room1/office1. E3a accepted edge counts have not been verified against GT associations.

## Optional research E6: 3DGS feasibility

Status: **deferred; prerequisites not yet pinned**.
- Replica RGB sequences, trajectories, and paired depth are present. An office2 mesh is available (hash and header recorded above), but no matching mesh was found for the room1/office1 test scenes and the mesh has no semantic labels.
- The workspace has no checked-out 3DGS training/rasterizer implementation, and the SAB3R Python environment cannot import `gsplat`, `diff_gaussian_rasterization`, or `simple_knn`.
- No matched Gaussian initialization/training protocol, held-out rendering split, or Gaussian outlier/ghost annotation is configured. Installing and validating that stack would be a separate substantial experiment, so the optional E6 was not run in this E1a–E6a cycle.
- No claim is made that pointmap refinement reduces Gaussian outliers or improves rendering quality. Revisit E6 only after pinning a 3DGS implementation and protocol on validation scenes.

## Preserved attempts

- `E1a-multikeyframe-20261104-001` (failed): E0_environment=completed, E0a_preflight=completed, E1a_multikeyframe_slam_export=failed, E2a_multikeyframe_semantics=planned, E3a_temporal_region_association=planned, E4a_error_guided_local_refinement=planned, E5a_multikeyframe_gt_evaluation=planned, E6a_extension_report=planned
- `E1a-multikeyframe-20261104-002` (failed): E0_environment=completed, E0a_preflight=completed, E1a_multikeyframe_slam_export=completed, E2a_multikeyframe_semantics=completed, E3a_temporal_region_association=failed, E4a_error_guided_local_refinement=planned, E5a_multikeyframe_gt_evaluation=planned, E6a_extension_report=planned
- `E1a-replica-office1-test-20261104-001` (running): E0_environment=completed, E0a_preflight=completed, E1_slam_export=planned, E2_sab3r_semantics=planned, E3_region_build=planned, E4_geometry_refinement=planned, E5_gt_evaluation=planned, E6_report=planned
- `E1a-replica-office1-test-20261104-002` (running): E0_environment=completed, E0a_preflight=completed, E1_slam_export=planned, E2_sab3r_semantics=planned, E3_region_build=planned, E4_geometry_refinement=planned, E5_gt_evaluation=planned, E6_report=planned
- `E5a-room0-validation-20261104-001` (failed): E0_environment=planned, E0a_preflight=planned, E1a_multikeyframe_slam_export=planned, E2a_multikeyframe_semantics=planned, E3a_temporal_region_association=planned, E4a_error_guided_local_refinement=planned, E5a_multikeyframe_gt_evaluation=failed, E6a_extension_report=planned
- `E5a-room0-validation-20261104-002` (running): E0_environment=planned, E0a_preflight=planned, E1a_multikeyframe_slam_export=planned, E2a_multikeyframe_semantics=planned, E3a_temporal_region_association=planned, E4a_error_guided_local_refinement=planned, E5a_multikeyframe_gt_evaluation=completed, E6a_extension_report=planned
- `E6a-replica-multikeyframe-synthesis-20261104-001` (failed): E6a_extension_report=failed
- `E6a-replica-multikeyframe-synthesis-20261104-002` (failed): E6a_extension_report=failed
- `E6a-replica-multikeyframe-synthesis-20261104-003` (completed): E6a_extension_report=completed

## Provenance index

The adjacent `e6a_synthesis.json` contains the verified stage manifest SHA-256 values and artifact hashes for every included run.
