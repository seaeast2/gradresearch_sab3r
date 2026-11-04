# H4 ablation: squared loss versus Huber on three Replica test scenes

## Protocol

The squared-loss config changed only the optimizer loss: Huber IRLS reweighting was disabled. Confidence weights, the 2× spacing displacement bound, Region selection threshold, planarity and inlier gates, boundary freeze, and rollback criterion remained the same as the Huber baseline. Each ablation used the same scene's E1a–E3a outputs and was evaluated with the same B0-derived scene Sim(3). GT was used only in E5a metrics.

## B3 results

| Scene | Huber RMSE (m) | Squared RMSE (m) | Δ RMSE (m) | Huber outlier | Squared outlier | Huber F-score | Squared F-score | Selected / rollback Regions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Replica/room1 | 0.190151 | 0.190151 | 0.000000 | 66.4623% | 66.4623% | 0.757167 | 0.757167 | 0 / 0 |
| Replica/office1 | 0.064212 | 0.064206 | −0.000007 | 30.4459% | 30.4453% | 0.929416 | 0.929419 | 1 / 0 |
| Replica/office2 | 0.172684 | 0.172680 | −0.000004 | 56.8176% | 56.8129% | 0.802863 | 0.802899 | 2 / 1 |

RMSE deltas are squared loss minus Huber. The changes are negligible. In room1, neither loss selected an eligible Region. In office1 and office2, both variants applied the same Region set and changed the same number of pixels; office2's rollback gate rejected one Region under both losses. This ablation provides no evidence that disabling Huber materially changes held-out scene accuracy or safety behavior at the tested settings.

## Provenance

Squared-loss run IDs and `metrics.json` SHA-256:

- room1: `H4-room1-squared-20261104-001` — `b5d09b2745d76c244cbfdcd7ac19526220f09ac58d321c909c63b0f28308eae1`.
- office1: `H4-office1-squared-20261104-001` — `2733be6facce8518e9f2eaf4534257fda2c113e140be69eb9effb023588bcc59`.
- office2: `H4-office2-squared-20261104-001` — `7f259a8b00dc890870438d8cb00de8109803a9bae5646440f555965e892cef2d`.

The E4a summaries, optimizer config hashes, source manifest hashes, and complete per-Keyframe metrics are retained in each run directory. Test scenes are all indoor Replica scenes; this is not an environment-generalization result.
