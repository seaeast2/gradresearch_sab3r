# E2a — SAB3R tags on two Replica office0 Keyframes

**판정: E1a의 두 Keyframe 모두 tagging 완료.** 동일 SAB3R checkpoint, 7개 고정 prompt, 전처리 규칙으로 frame 0과 frame 82를 추론했습니다. Score, top-1/top-2 margin, label mask와 overlay를 Keyframe별로 저장했습니다. 의미 정답 평가와 temporal Region 연결은 이 단계에 포함하지 않습니다.

## 실행 구성

- Run: `E1a-multikeyframe-20261104-002`; 입력 E1a export도 같은 run의 완료 stage에서 읽었습니다.
- SAB3R checkpoint SHA-256: `0b25a93727afbbd6cc65f21e49dc70c3e1c2c7559c13c0e1f806352d440924e6`
- Host GPU: NVIDIA GeForce RTX 5060; Python 3.11.18, PyTorch 2.7.1+cu128, CUDA 12.8.
- 두 입력 모두 288×512였고, SAB3R 입력 RGB가 E1a NPZ의 RGB와 pixel-exact 일치했습니다.
- 각 Keyframe 추론은 8.69초와 8.02초였으며, peak allocated GPU memory는 각각 6,370.6 MiB와 6,371.1 MiB였습니다.
- E2a stage manifest에는 25개 artifact가 있고, manifest SHA-256을 재검증해 모두 일치했습니다.

## Argmax tag 픽셀 수

| Label | frame 0 | frame 82 |
|---|---:|---:|
| floor | 22,147 | 16,784 |
| wall | 27,338 | 82,978 |
| ceiling | 2,060 | 2,189 |
| table | 62,384 | 16,981 |
| cabinet | 24,385 | 15,843 |
| door | 1,461 | 11,958 |
| other | 7,681 | 723 |

이 분포는 고정 후보 prompt 간 argmax pixel count이며 semantic 정확도나 temporal 안정성 지표가 아닙니다. 두 Keyframe의 시야가 다르므로 픽셀 수 차이만으로 tag 흔들림을 판정하지 않습니다. Confidence margin은 원 score로 보존했지만 calibration threshold는 적용하지 않았습니다.

## 산출물과 다음 단계

Keyframe별 결과는 [E2a artifacts](../../../runs/semantic_region_pointmap/E1a-multikeyframe-20261104-002/stages/E2a_multikeyframe_semantics/artifacts/keyframes/)에 있고, frame ID·입력 hash·score hash는 [keyframes manifest](../../../runs/semantic_region_pointmap/E1a-multikeyframe-20261104-002/stages/E2a_multikeyframe_semantics/artifacts/keyframes_manifest.json)에 기록했습니다.

E2a는 Keyframe마다 독립 tag만 만들었습니다. 같은 class tag만으로 Region을 병합하지 않으며, E3a에서 MASt3R-SLAM 대응점·World 공간 overlap·표면 기하를 함께 사용해 같은 물리 표면인지 검사해야 합니다.
