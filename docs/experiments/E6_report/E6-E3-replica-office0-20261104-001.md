# E6 — Semantic Region Pointmap pilot synthesis

**판정: E0a–E5 파일럿 파이프라인 완료. 계획서의 H1 예비 목표(여러 장면 중앙값 RMSE 10% 이상 감소)는 이 결과로 지지되지 않았습니다.** E6는 이미 완료된 단계의 산출물과 해시를 취합합니다. 새로운 모델 추론이나 3DGS 실험은 수행하지 않았습니다.

## 실행 범위

- Result run: `E3-replica-office0-20261104-001`; E1: `E0a-readiness-20261104-002`; E2: `E2-replica-office0-20261104-001`; E0a: `E0a-readiness-20261104-002`.
- Scene/frame: Replica office0, frame 0, 1 exported Keyframe.
- E1 SLAM export와 E2 SAB3R semantic inference를 완료하고, E3에서 semantic/geometry Region 후보를 생성했습니다. E4는 고정 Pose로 선택된 평면 후보만 ray 방향으로 제한 보정했습니다. E5는 별도 Replica depth를 평가 전용으로 사용했습니다.
- E3 Region 수: semantic 4-연결 78, geometry gate 적용 324. E4는 후보 324개 중 6개를 보정해 24,663점을 변경했습니다.
- GT가 E3 Region 생성이나 E4 보정의 입력으로 쓰이지 않았습니다. B0/B2는 E5의 동일 전역 Sim(3)으로 평가됐습니다.

## 핵심 결과

| 지표 | B0 원본 | B2 semantic plane refinement |
|---|---:|---:|
| 전체 유효 대응 RMSE (m) | 0.113589 | 0.113548 |
| Semantic plane 후보 RMSE (m) | 0.116629 | 0.116518 |
| Semantic 후보 RMSE 변화 | — | -0.096% |
| 보정된 점 수 | — | 24,663 |

Semantic 후보 RMSE의 변화는 위 실험 계획의 10% 감소 기준에 미달합니다. E5 지표는 depth로 역투영한 같은 pixel 대응 오차이며 GT mesh까지의 point-to-surface 거리는 아닙니다. 보정된 subset은 E4 기하 규칙으로 선택되어 독립적인 효과 추정으로 해석하지 않습니다.

## 해석 및 다음 실험

이 파일럿은 고정된 단일 Keyframe에서 E1–E5 실행과 산출물 추적을 확인했습니다. 하나의 장면·시점만으로 H1을 지지할 수 없으며, semantic grouping의 geometry-only 대비 추가 가치(H2), 여러 Keyframe의 Region 연계와 temporal merge(H3)도 평가하지 않았습니다. geometry gate 뒤 작은 Region이 다수 생긴 점도 후속 개선 대상입니다.

다음 확장에서는 여러 장면/시점의 평가, B1 geometry-only와 B2 비교, B3 temporal merge, GT mesh 표면 지표, semantic 정답 평가를 별도 run으로 수행해야 합니다. 3DGS는 계획서에서 선택 실험으로 분리되어 있으므로 본 보고서의 결론에 포함하지 않았습니다.

## 추적 정보

단계별 입력 run, manifest SHA-256, artifact SHA-256은 [`e6_summary.json`](e6_summary.json)에 기록했습니다. 해당 manifest가 가리키는 모든 파일의 존재와 SHA-256을 생성 시점에 다시 확인했습니다. E0a–E5 상세 기록은 각 단계별 보고서와 run manifest를 기준으로 합니다.
