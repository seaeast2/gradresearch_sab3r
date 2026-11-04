# E5 — Replica office0 depth-based geometry evaluation

**판정: 평가 완료. 이 파일럿은 H1 성공 목표를 뒷받침하지 않습니다.** E4에서 사용한 원본 pointmap과 보정 pointmap을 같은 평가 전용 Sim(3)로 정렬해 Replica office0 frame 0 depth와 비교했습니다. GT는 E3/E4의 Region 선택과 최적화 입력에 전달하지 않았습니다.

## 평가 절차

- GT: `/home/hlee221212/works/gradresearch/data/Replica/office0/results/depth000000.png`, RGB와 같은 frame 0
- 16-bit depth를 `cam_params.json`의 scale 6553.5로 미터 단위화했습니다.
- GT depth는 E1과 같은 512 long-edge resize 및 center crop의 픽셀 기하에 nearest-neighbor로 맞췄습니다. 결과 격자는 288×512이며 원본과 대응하는 유효 depth pixel은 147,238개입니다.
- E1 원본 B0의 짝지은 점만 이용해 even-row/even-column 격자 36,809개에서 **한 번의 전역 Sim(3)** 를 구하고, 동일 변환을 B0/B2에 적용했습니다. Region별 정렬은 하지 않았습니다.
- 주요 거리는 depth로 역투영한 같은 pixel의 GT 3D 점과 예측 점 사이의 Euclidean distance입니다. 이 값은 GT mesh까지의 point-to-surface distance가 아닙니다.
- 보조 outlier 기준은 5 cm로 고정했습니다. 이 단일 파일럿에서 validation으로 고른 threshold는 아닙니다.

실행 설정은 [`e5_gt_evaluation.json`](../../../configs/e5_gt_evaluation.json), 구현은 [`evaluate_e5_gt.py`](../../../scripts/evaluate_e5_gt.py)에 있습니다. 입력 파일 hash, depth scale, resize/crop와 정렬 transform은 `metrics.json`에 기록했습니다.

## 결과

| 평가 집합 | 점 수 | B0 RMSE (m) | B2 RMSE (m) | B0 mean (m) | B2 mean (m) | B0 outlier >5cm | B2 outlier >5cm |
|---|---:|---:|---:|---:|---:|---:|---:|
| 전체 유효 대응 | 147,238 | 0.113589 | 0.113548 | 0.057375 | 0.057271 | 25.07% | 24.92% |
| Semantic plane 후보 전체 | 51,545 | 0.116629 | 0.116518 | 0.062550 | 0.062251 | 27.18% | 26.75% |
| E4가 실제 수정한 점 | 24,663 | 0.033617 | 0.032796 | 0.031589 | 0.030964 | 7.31% | 6.40% |
| 수정하지 않은 점 | 122,575 | 0.123576 | 0.123576 | 0.062564 | 0.062564 | 28.64% | 28.64% |

Semantic plane 후보 전체의 RMSE 감소는 약 **0.000112 m (0.096%)**, mean distance 감소는 약 **0.000299 m (0.48%)**입니다. 5 cm outlier 비율은 약 0.44 percentage point 감소했습니다. 수정된 subset의 개선 폭은 더 커 보이지만, 이 subset은 E4의 기하 조건으로 골라진 점이므로 독립적인 효과 추정으로 해석하면 안 됩니다. 비대상 점의 값은 B0와 동일하고 점을 추가·삭제하지 않아 point coverage 수는 유지됐습니다.

오차 영상 및 픽셀별 전후 오차는 [E5 artifacts](../../../runs/semantic_region_pointmap/E3-replica-office0-20261104-001/stages/E5_gt_evaluation/artifacts/)에 있습니다.

## 결론과 한계

이 단일 Keyframe 결과는 안전한 제한 보정이 실행되고 비대상 점이 고정됨을 보여주지만, 계획서의 예비 목표인 여러 장면 중앙값 10% RMSE 감소를 지지하지 않습니다. 한 장면·한 시점이며, depth 기반 같은-pixel GT만 사용했고, GT mesh surface, semantic IoU, geometry-only B1, temporal B3, Oracle B4는 평가하지 않았습니다. 따라서 semantic grouping이 geometry-only보다 낫다거나 다중 시점 Region 병합이 유효하다는 결론은 낼 수 없습니다.
