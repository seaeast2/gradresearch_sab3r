# E4 — Replica office0 bounded plane refinement

**판정: 고정 Pose ray-depth 보정 실행 완료, 안전성 조건 통과.** `E3-replica-office0-20261104-001`의 frozen E1/E3 결과만 사용했습니다. GT depth는 E4 입력에 전달하지 않았습니다.

## 사전 고정 규칙

평면 후보는 `floor`, `wall`, `ceiling` label 중 500 pixel 이상이고 PCA 최소 고유값 비율이 0.05 이하인 Region입니다. 결정적 seed로 512회 3점 RANSAC을 수행하고, 0.75 이상 inlier인 경우만 적용했습니다. 점은 Keyframe camera ray 방향으로만 움직이며 Huber IRLS, confidence 가중치, 2 pixel 경계 동결, 최대 radial displacement 3×E3 median sample spacing을 사용했습니다. 이 초기값은 validation에서 튜닝한 값이 아닙니다.

설정과 구현은 [`e4_geometry_refinement.json`](../../../configs/e4_geometry_refinement.json), [`refine_e4_geometry.py`](../../../scripts/refine_e4_geometry.py)에 있습니다.

## 결과

- 후보 Region 324개 중 평면 보정 적용: **6개** (wall 3, ceiling 2, floor 1)
- 실제 변경 점: **24,663 / 147,456 (16.73%)**
- 변경 점 평균 변위: 각 Region에서 1.19–2.69 mm
- 최대 변위: **12.41 mm**, 설정 상한은 23.55 mm
- 비대상 및 동결 점의 최대 절대 좌표 변화: **0.0**
- 적용된 6개 Region 모두 self-plane RMSE가 감소했습니다. 이는 내부 일관성 점검이며 GT 정확도 근거가 아닙니다.

| Region | Label | RANSAC inlier | 변경 점 | self-plane RMSE 전→후 (m) |
|---:|---|---:|---:|---:|
| 3 | wall | 97.21% | 1,627 | 0.00468 → 0.00347 |
| 9 | ceiling | 99.61% | 654 | 0.00669 → 0.00457 |
| 14 | ceiling | 99.79% | 618 | 0.00280 → 0.00145 |
| 19 | wall | 80.80% | 3,411 | 0.01111 → 0.00814 |
| 40 | wall | 96.82% | 17,177 | 0.00648 → 0.00357 |
| 63 | floor | 98.11% | 1,176 | 0.00269 → 0.00149 |

[`E4 artifacts`](../../../runs/semantic_region_pointmap/E3-replica-office0-20261104-001/stages/E4_geometry_refinement/artifacts/)에는 original/optimized/semantic PLY, displacement vector PLY, 전체 refined point 배열과 region별 적용·제외 사유가 있습니다.

## 해석 범위

이 결과는 ray를 유지한 채 선택된 6개 Region의 self-plane residual을 줄이고, 다른 점을 고정하는 구현 조건을 확인합니다. 실제 GT 오차 개선 여부는 E5에서 같은 B0 기준 Sim(3)를 적용해 별도로 평가합니다. 한 Keyframe에서만 실행했으므로 다중 시점 기하나 temporal Region 품질은 검증하지 않았습니다.
