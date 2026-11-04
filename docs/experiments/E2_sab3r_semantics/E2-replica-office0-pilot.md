# E2 — Replica office0 SAB3R semantic pilot

**판정: 의미 특징 추론과 픽셀 정렬 산출물 생성 완료.** 성공 run은 `E2-replica-office0-20261104-001`이며, 기존 E1 결과 `E0a-readiness-20261104-002`의 단일 Keyframe을 입력으로 재사용했습니다. E2는 의미 mask/score 생성 단계이고 Region 분할이나 정답 기준 의미 정확도 평가는 포함하지 않습니다.

## 실행 구성

- SAB3R 공식 저장소: commit `eceb1bc5eed1e1a3505fe6eba3e9079093a32aa9`
- FeatUp 소스: commit `6b5a6c0e91f75e69194807128dcbc39c3084a30d`
- Python 3.11.18, PyTorch 2.7.1+cu128, CUDA 12.8
- 호스트 GPU: NVIDIA GeForce RTX 5060
- SAB3R checkpoint: Hugging Face `uva-cv-lab/SAB3R`, revision `cc4fc56ca47061efe98f7b9a2d407e06a0c0fd41`
- Checkpoint SHA-256: `0b25a93727afbbd6cc65f21e49dc70c3e1c2c7559c13c0e1f806352d440924e6`
- E1 NPZ SHA-256: `fa8a417272281bda95102b0806060945465c3e652a8f1cb37bceb9915f1746c9`
- Frame 0, timestamp 0.0, 입력/출력 격자 288×512. SAB3R 전처리 후 크기도 288×512였고 E1 RGB와 pixel-exact 일치를 확인했습니다.
- 단일 이미지 입력은 공식 SAB3R demo의 single-image 처리와 같이 동일 이미지를 두 view로 복제해 pairwise forward에 전달했습니다.
- CLIP 텍스트 후보는 `floor`, `wall`, `ceiling`, `table`, `cabinet`, `door`, `other`의 7개로 고정했습니다. 각 후보의 prompt 및 raw cosine similarity를 저장했습니다.

## 산출물과 실행 결과

[`E2 artifacts`](../../../runs/semantic_region_pointmap/E2-replica-office0-20261104-001/stages/E2_sab3r_semantics/artifacts/)에 픽셀별 7-class score tensor, argmax label ID, 각 class mask, 색상 label map, RGB overlay 및 `inference.json`이 저장됐습니다. manifest에는 각 파일의 SHA-256이 기록되어 있습니다.

![E1 keyframe 위의 SAB3R prompt argmax overlay](../../../runs/semantic_region_pointmap/E2-replica-office0-20261104-001/stages/E2_sab3r_semantics/artifacts/semantic_overlay.png)

실제 candidate argmax 분포는 다음과 같습니다. 이 값은 mask 생성 결과의 픽셀 수이며 의미 분류 정확도는 아닙니다.

| 후보 | 픽셀 수 |
|---|---:|
| floor | 22,147 |
| wall | 27,338 |
| ceiling | 2,060 |
| table | 62,384 |
| cabinet | 24,385 |
| door | 1,461 |
| other | 7,681 |

- SAB3R dense CLIP 출력 shape: `288×512×512`; score tensor: `288×512×7`
- score 값은 모두 finite이며 raw cosine similarity 범위는 0.2308–0.3798입니다.
- 최고 점수와 차점 점수 간 차이도 함께 저장했지만, calibration 자료가 없어 confidence threshold나 `void` 판정은 적용하지 않았습니다.
- 실행 시간 약 34.0초, PyTorch가 관측한 peak allocated GPU memory 약 6,371 MiB입니다.

## 해석 범위와 다음 단계

이 결과는 고정 prompt 집합으로 픽셀별 점수와 후보 mask를 만들고 E1 좌표 격자에 정렬할 수 있음을 확인합니다. 한 장면의 단일 Keyframe 파일럿이라 의미 정확도, 프레임 간 안정성, temporal Region 연결은 검증하지 않았습니다. class별 mask를 바로 신뢰 레이블로 취급하지 말고, E3에서 연결 성분과 3D 기하 조건을 적용하기 전에 정성 검토와 필요 시 수동/Oracle mask 비교가 필요합니다.

최초 실행은 코드의 DUSt3R 경로 등록 문제로 추론을 시작하기 전에 실패해 원 run `E0a-readiness-20261104-002`의 E2 실패 manifest에 보존했습니다. 수정된 코드는 새 성공 run에서 실행했고 E1 입력의 hash를 기록해 추적 가능하게 했습니다.

재실행 명령:

```bash
bash scripts/run_e2_sab3r_semantics.sh \
  E2-replica-office0-20261104-001 \
  E0a-readiness-20261104-002
```

실행기 SHA-256: `scripts/run_e2_sab3r.py` `a9343c5fe999c6bc8c600ffcc45ef1902edf5efb2e9d178fd7a62d0317639b45`; `scripts/run_e2_sab3r_semantics.sh` `4ef9e20e3fe019e13a19ca3e7c1d7d03c1791c9eda180dd30a0a64a9740cd307`.
