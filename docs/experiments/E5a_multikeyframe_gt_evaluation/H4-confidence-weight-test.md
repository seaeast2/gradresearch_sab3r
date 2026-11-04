# H4 ablation: confidence weighting versus uniform weights on three Replica test scenes

## Protocol

The uniform-weight config changed only the point confidence weights: normalized `confidence_avg` weights were replaced by unit weights. Huber loss, the 2× spacing displacement bound, Region selection threshold, planarity and inlier gates, boundary freeze, and rollback criterion remained fixed. The same E1a–E3a outputs and B0-derived common scene Sim(3) were used for each paired comparison; GT was evaluation-only.

## B3 results

| Scene | Confidence RMSE (m) | Uniform RMSE (m) | Δ RMSE (m) | Confidence outlier | Uniform outlier | Confidence F-score | Uniform F-score | Applied / rollback Regions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Replica/room1 | 0.190151 | 0.190151 | 0.000000 | 66.4623% | 66.4623% | 0.757167 | 0.757167 | 0 / 0 |
| Replica/office1 | 0.064212 | 0.064206 | −0.000007 | 30.4459% | 30.4423% | 0.929416 | 0.929418 | 1 / 0 |
| Replica/office2 | 0.172684 | 0.172687 | +0.000003 | 56.8176% | 56.8426% | 0.802863 | 0.802634 | 2 / 1 |

RMSE deltas are uniform minus confidence-weighted. The direction is scene-dependent: office1 shifts slightly in favor of uniform weights, while office2 shifts slightly in favor of confidence weights. Room1 has no selected Region. The apply/rollback counts remain the same, with only tiny per-pixel count differences. This does not show a consistent accuracy benefit from confidence weighting, nor does it justify removing it.

## Provenance

Uniform-weight run IDs and `metrics.json` SHA-256:

- room1: `H4-room1-uniform-20261104-001` — `96a75396d78bc37b89467e51fa5edb950857f963ed9e106a4dea99057815792f`.
- office1: `H4-office1-uniform-20261104-001` — `4d67e22386465aa5087337caf6cd99eca8bc89f3578e7d57289949e47eccf707`.
- office2: `H4-office2-uniform-20261104-001` — `ca16e2e91191b0dff19138506898860cf9278f0e39e6b790f7010bc3231cde3d`.

All E4a summaries and complete E5a metrics are retained in their isolated run directories. These are three indoor Replica test scenes and do not establish broader environment generalization.
