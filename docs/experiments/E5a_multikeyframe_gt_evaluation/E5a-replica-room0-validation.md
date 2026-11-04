# E5a validation: multi-Keyframe B0–B3 on Replica room0

## 평가 설계

이 실행은 threshold를 고정한 validation 장면에서 E5a pipeline을 점검한다. test 성능이나 연구 가설의 최종 판정으로 사용하지 않는다.

- Scene: Replica room0; E1a 1,000 RGB 입력에서 Keyframe 7개 (`0, 207, 385, 533, 621, 733, 823`)
- GT: 각 Keyframe에 짝지은 Replica depth, `cam_params.json`, `traj.txt`
- GT depth는 E1과 동일한 512 long-edge resize/crop으로 pointmap pixel grid에 맞췄다. 각 frame GT point를 Replica camera-to-world Pose로 GT world 좌표로 변환했다.
- 하나의 공통 Sim(3)를 전체 Keyframe의 B0 점과 GT world 사이에서 한 번 추정했다. 결정적 even-row/even-column 격자 258,043개를 사용했고 동일 변환을 B0–B3 모두에 재사용했다.
- GT는 B0 alignment와 결과 지표에만 사용했다. B1/B2/B3의 Region 선택 및 최적화 입력에는 depth나 GT trajectory를 전달하지 않았다.
- Primary metric은 같은 pixel의 world point 거리다. 이는 Replica mesh까지의 point-to-surface distance가 아니다. Scene F-score는 모든 Keyframe의 결정적 2×2 lattice point를 합쳐 5 cm nearest-neighbor threshold로 계산했다.

## 비교군

- B0: 원본 MASt3R-SLAM pointmap.
- B1: SAB3R 의미 라벨 없이 seed normal/plane 조건으로 만든 geometry-only local Region과 bounded optimizer.
- B2: SAB3R frame-local Region, temporal merge 없이 같은 local optimizer.
- B3: E3a persistent Region과 E4a temporal optimizer.
- B4: 실행하지 않았다. 이 Replica export에는 paired depth와 camera trajectory는 있지만 Oracle semantic/plane mask가 없다.

B1–B3는 같은 frozen residual score threshold (2.04×local spacing), RANSAC planarity/inlier gates, Huber loss, confidence weights, boundary freeze, displacement bound, rollback 조건을 공유한다. B3만 여러 observation을 함께 사용해 shared plane을 추정하고 B1/B2는 frame-local plane을 쓴다.

## 결과

| Method | Same-pixel RMSE (m) | Semantic-plane RMSE (m) | 5 cm outlier | Normal error mean (°) | Boundary-gap error (m) | Scene F-score @5 cm |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 0.161391 | 0.089705 | 33.9587% | 14.2086 | 0.0215678 | 0.86910 |
| B1 | 0.161387 | 0.089698 | 33.9783% | 14.1906 | 0.0215688 | 0.86859 |
| B2 | 0.161391 | 0.089705 | 33.9587% | 14.2086 | 0.0215678 | 0.86910 |
| B3 | 0.161391 | 0.089705 | 33.9587% | 14.2086 | 0.0215678 | 0.86910 |

- B1은 18개 geometry-only Region에서 42,580 pixels를 수정했다. RMSE 차이는 약 −0.000004 m로 사실상 0에 가깝고, outlier 비율과 F-score는 약간 악화했다.
- B2와 B3는 수정한 점이 0개여서 B0와 동일했다. B2의 높은 score wall 후보는 RANSAC inlier fraction을 통과하지 못했고, B3 E4a에서도 적격 temporal Region이 없었다.
- 따라서 이 validation scene에서는 의미 frame-local 또는 temporal Region 보정의 GT 이득을 관찰하지 못했다. H1–H3를 지지하는 결과가 아니다.

## 해석 및 한계

한 frame씩 카메라 좌표 GT에 정렬해 평가하면 Keyframe 간 pose/scale inconsistency를 숨길 수 있다. 본 평가는 `traj.txt`로 GT point를 world에 변환하고 단일 B0 Sim(3)를 재사용한다. 공통 scale은 1.125818, translation은 `[3.419293, 0.437575, 0.568103]`이었다. 이 프로토콜에서 room0 B0 RMSE는 0.1614 m였다.

이 장면은 validation 전용이며 표본은 한 scene이다. 여러 독립 test scene 결과가 필요하다. B4 Oracle은 GT mask 부재 때문에 제외되었고, mesh point-to-surface 거리도 계산하지 않았다.

## 무결성

- Run: `E5a-room0-validation-20261104-003`
- E5a stage: `completed`; metrics artifact hash는 manifest와 일치
- `metrics.json` SHA-256: `5dc17a42d01475606a5ad13e5db1b23b16eb37da3d0e3198aebdd3ac3622b4a7`
- Camera params SHA-256: `ffbefdeb53755e1490d6936dffdee253510e68d5e443e1ba91e60202addc1a0a`
- `traj.txt` SHA-256: `5692a60076e426b403dc64025ff38c443606a506704545ee192d4dbadedaaca2`
- 결과 JSON 및 per-Keyframe 지표: `runs/semantic_region_pointmap/E5a-room0-validation-20261104-003/stages/E5a_multikeyframe_gt_evaluation/artifacts/metrics.json`
