# E4a: Replica room0 error-guided local refinement

## 목적과 설정 동결

E3a에서 persistent Region별 cross-view pointmap residual을 오류 후보 점수로 계산하고, 검증 장면에서 동결한 문턱값을 넘는 Region만 선택적으로 보정한다. 점수는 GT 오차의 대체물이 아니다.

문턱값은 두 validation scene office0와 room0에서 수락된 18개 인접-Keyframe Region link의 normalized P90 mutual-correspondence distance 중 90th percentile을 기준으로 **2.04 × scene global median local spacing**으로 정했다. GT label 또는 geometry는 이 설정에 사용하지 않았고, test scene은 처리하지 않았다. 표본 수가 작으므로 frozen pilot 기준으로만 취급한다.

## 입력 및 재현 정보

- Output run: `E4a-room0-validation-20261104-001`
- E1a/E2a/E3a source: `E1a-replica-room0-validation-20261104-001`
- Scene: Replica room0, 7 Keyframe, 6개 인접 frame pair
- E3a temporal manifest SHA-256: `12b83d13e8c16fa271d27cf2c6c8e61c77d6c4f3884559c3497bb02eddc8ec31`
- Frozen config: `configs/e4a_error_guided_refinement.json`
- `global median local spacing`: 0.0120808 world units
- Score threshold: 0.02464 world units (2.04 × spacing)
- Per-point maximum radial displacement: 0.02416 world units (2 × spacing)
- Candidate labels: floor, wall, ceiling; 최소 2 observations, 합계 500 pixels, 200 mutual correspondences, PCA planarity ratio ≤0.12, RANSAC inlier fraction ≥0.85

## 처리와 안전 조건

각 accepted E3a link에서 상호 최근접 3D 대응 거리의 P90을 계산하고 scene spacing으로 나눴다. Persistent Region 점수는 연결 edge 중 최대 P90 ratio로 정의했다. 점수가 threshold 이상이어도 semantic label, 관측 수, pixel/대응 수, merged planarity와 RANSAC inlier 조건에 하나라도 걸리면 보정하지 않고 사유를 기록한다.

적격 Region에는 고정된 Keyframe camera ray 방향으로만 Huber IRLS plane refinement를 적용한다. 점은 Region 경계 2 pixel을 고정하고 displacement를 제한한다. 실제 변경 전후 shared-plane RMSE 개선률이 1% 미만이면 그 Region의 수정을 원본으로 되돌린다. GT는 후보 선택과 최적화에 읽히지 않는다.

## 결과

- 평가한 persistent Region: 811개.
- Frozen 점수 threshold 이상인 후보 2개:
  - global Region 485 (`wall`): score 2.1512×spacing. PCA ratio 0.00964였지만 RANSAC inlier fraction 0.6654로 최소 0.85 조건을 통과하지 못해 `ineligible` 처리.
  - global Region 554 (`cabinet`): score 2.8228×spacing였으나 허용 평면 semantic class가 아니어서 `not_selected` 처리.
- 실제 선택 및 보정 Region: 0개; 수정 pixel: 0개; rollback: 0개. 모든 출력 Keyframe point 좌표는 입력과 동일했다.
- 이유 집계는 중복 가능: threshold 미달 809, 반복 관측 부족 801, 최소 대응 수 부족 801, 최소 pixel 수 부족 744, 비대상 semantic class 564, RANSAC inlier 비율 미달 1.
- E4a stage status는 `completed`; artifact 8개의 SHA-256이 manifest와 일치했다. 요약 JSON SHA-256: `e464c82d288112ae517c9fd2516862a55a408f0b36f6311a9036397b2513ef79`.

## 해석

이 validation run은 frozen selection gate가 high-score이지만 혼합/비평면인 wall Region을 거부하고, 허용 class 밖의 cabinet도 수정하지 않는 것을 보여준다. 하지만 보정 가능한 Region이 없어 optimizer가 실제 point를 수정하는 효과는 검증하지 못했다. 이는 안전한 no-op 결과로 기록한다. H1 향상이나 localization 성능을 주장할 수 없다. 다른 독립 scene의 frozen 평가와 GT geometry 평가가 필요하며, room0 결과를 보고 threshold를 완화하지 않는다.

산출물은 `runs/semantic_region_pointmap/E4a-room0-validation-20261104-001/stages/E4a_error_guided_local_refinement/artifacts/`에 있다. 각 Keyframe NPZ에는 original/refined world pointmap, modified mask, semantic label ID, Region ID가 저장된다.
