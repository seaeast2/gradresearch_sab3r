# H4 ablation: 1× versus 2× spacing displacement bound on three Replica test scenes

## Protocol

The half-displacement config reduced only the maximum radial depth change from 2× to 1× scene median spacing. The robust loss, confidence weights, Region selection threshold, planarity/inlier gates, boundary freeze, and rollback criterion were unchanged. Each variant reused that scene's E1a–E3a output and B0-derived common Sim(3); GT was used only in E5a evaluation.

## B3 results

| Scene | 2× RMSE (m) | 1× RMSE (m) | Δ RMSE (m) | 2× outlier | 1× outlier | 2× F-score | 1× F-score | Applied / rollback Regions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Replica/room1 | 0.190151 | 0.190151 | 0.000000 | 66.4623% | 66.4623% | 0.757167 | 0.757167 | 0 / 0 |
| Replica/office1 | 0.064212 | 0.064208 | −0.000004 | 30.4459% | 30.4405% | 0.929416 | 0.929416 | 1 / 0 |
| Replica/office2 | 0.172684 | 0.172684 | −0.0000001 | 56.8176% | 56.8182% | 0.802863 | 0.802861 | 2 / 1 |

RMSE deltas are 1× minus 2×. Reducing the bound halved maximum radial displacement as configured, while the selected and rolled-back Region counts and total modified-pixel counts stayed the same. Metric differences were negligible and mixed: office1 improved slightly on RMSE/outlier rate, office2's outlier rate/F-score moved slightly worse, and room1 had no selected Region. This does not establish that the smaller bound improves scene accuracy; the safety invariant that edits stay within the configured bound held.

## Provenance

1× displacement run IDs and `metrics.json` SHA-256:

- room1: `H4-room1-halfdisp-20261104-001` — `7a80105676c6ec59d33f5d1e70ccb90548469d460aa414eddcdbe5e1a032cf96`.
- office1: `H4-office1-halfdisp-20261104-001` — `ddd4faf45d3950cec17b10c43176c5c252e378c4dc3ea37aa72e897f229e83d6`.
- office2: `H4-office2-halfdisp-20261104-001` — `057f509ce3d17af1ecae7c3cf4bca11bb5c0b96d305b8d13381e2ce33dd08ec2`.

Each run retains its E4a summary, config and source hashes, and full E5a metrics. These three scenes are all indoor Replica data.
