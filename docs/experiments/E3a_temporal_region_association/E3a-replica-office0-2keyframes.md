# E3a: Replica office0 temporal Region association

## 목적

두 MASt3R-SLAM Keyframe의 SAB3R semantic/geometry Regions를 같은 SLAM world 좌표계에서 연결한다. 동일 semantic label만으로 병합하지 않고, pointmap correspondence, bidirectional Region overlap, one-to-one assignment, 그리고 planar geometry gates를 함께 요구한다.

## 참고 논문과 구현 범위

`docs/papers/Pointmap Association and Piecewise-Plane Constraint for Consistent and Compact 3D Gaussian Segmentation Field.pdf`의 CCGS는 인접 이미지의 pointmap 사이에서 3D 최근접 픽셀 대응을 구하고, 대응으로 재정의한 mask overlap을 Hungarian algorithm으로 매칭하며 partial match를 허용한다(논문 §3, pp. 3–4). 이 파일럿은 그 흐름을 Region에 적용해 상호 최근접 3D point correspondence와 Hungarian 1:1 배정을 사용한다. 다만 E1a 산출물에 MASt3R learned matching descriptor는 export되지 않아, descriptor matching은 하지 않았다.

## 입력과 재현 정보

- Run: `E3a-temporal-association-20261104-001`
- E1a/E2a source run: `E1a-multikeyframe-20261104-002`
- Scene: Replica office0, 연속 RGB 120장 중 SLAM이 export한 Keyframe 2개
- Keyframes: frame 0 (0.000 s), frame 82 (2.733 s), 각 pointmap 288×512
- E1a export manifest SHA-256: `f1044cad77af7fd0267ccf7e7375052459cb3f762efda33f60381185f7a2df3e`
- E2a keyframes manifest SHA-256: `5d4a77f6339817b2156fa083d9cd135e867ae13a73a0886674e7ad25bc8c592b`
- E3a config: `configs/e3a_temporal_region_association.json`
- 모든 임계값은 exploratory pilot 값이다. 이 두 Keyframe 결과로 임계값을 조정하거나 검증하지 않았다.

## 절차

1. 각 Keyframe에서 E1a pointmap과 E2a semantic score grid의 pixel alignment 및 manifest SHA-256을 확인했다.
2. 같은 semantic class 안에서 인접 pixel의 3D 거리·normal 조건으로 frame-local Regions를 구성했다.
3. 인접 Keyframe의 유효 point를 각각 KD-tree로 검색하고, 양방향 최근접인 점 쌍 중 설정한 공간 거리 이내인 대응만 보존했다.
4. 각 Region 쌍에 대해 상호 대응 점 수와 양방향 정규화 overlap을 계산했다. 같은 semantic class끼리 Hungarian assignment를 수행하고, 최소 크기·대응 수·overlap·bounds·평면 normal/offset gate를 통과하지 않은 매칭은 거부했다.
5. 통과한 인접-frame edge만 union-find로 persistent Region ID에 연결하고, mask/overlay 및 accepted/rejected edge 기록을 저장했다.

## 설정값

| 항목 | 값 |
|---|---:|
| Region 이웃 거리 | 3 × local sampling spacing |
| Region normal 변화 제한 | 45° |
| 최소 Region 크기 | 100 pixels |
| 상호 point correspondence 거리 | 4 × global median local spacing = 0.03383 world units |
| 최소 상호 대응 수 | 30 pixels |
| 최소 양방향 overlap | 0.15 |
| 평면 normal 차이 제한 | 45° |
| 평면 offset 제한 | 4 × global median local spacing |
| planar 분류 기준 | PCA smallest-eigenvalue / eigenvalue sum ≤ 0.12 |

## 결과

- 각 Keyframe의 유효 point 수: 147,456 / 147,456.
- frame 0 → frame 82 상호 최근접 point correspondence: 34,017쌍 (유효 pixel 수 대비 약 23.1%). 대응 거리 중앙값은 0.01043 world units였다.
- Frame-local Region 수: 278개와 115개.
- 같은-class Region 조합 9,734개를 후보로 평가했고, 1쌍이 모든 gate를 통과했다. 연결 전 전체 local Region 393개가 persistent Region 392개가 됐다.
- 통과 edge는 `floor`, local Region 60 → 101, 상호 대응 653개, 양방향 overlap 0.3749 / 0.4063, normal 차이 13.35°, 평면 offset 0.01707 world units였다.
- 나머지 조합은 overlap 부족(9,731), 최소 상호 대응 부족(9,721), 최소 Region 크기 미달(9,684), bounds 분리(9,517), plane offset 초과(9,372) 등을 포함한 gate 이유로 거부됐다. 이유는 중복될 수 있다.

**해석:** 파일럿 구현은 실행 가능하며 엄격한 one-to-one geometry association으로 결과를 생성했다. 단, 두 Keyframe만으로 실제 표면 정합의 precision/recall이나 장면 간 일반화를 측정하지 못했고, 통과한 floor 쌍도 GT 또는 수동 정답으로 검증하지 않았다. 단 하나의 연결은 실패가 아니라 현재 설정에서의 낮은 association coverage 결과로 보존한다. 여러 장면 validation 전에 이 결과를 근거로 임계값을 완화하지 않는다.

## 산출물 및 integrity

`runs/semantic_region_pointmap/E3a-temporal-association-20261104-001/stages/E3a_temporal_region_association/artifacts/`에 다음을 저장했다.

- `temporal_regions.json`: 설정, 입력 manifest hash, Keyframe 요약, 상호 correspondence 통계, 전체 후보 edge와 rejection 사유, persistent ID mapping
- `region_masks.npz`: Keyframe별 local Region ID와 semantic label grid
- `regions_kf_000_frame_00000000.png`, `regions_kf_001_frame_00000082.png`: local Region overlay

Stage manifest는 네 산출물의 SHA-256을 기록했고 stage status는 `completed`다. 첫 실행은 설정 키 불일치로 시작 직후 실패했으며 해당 실패는 `E1a-multikeyframe-20261104-002`의 E3a stage manifest/log에 보존했다. 수정 후 별도 run ID에서 성공했다.

실행 명령:

```bash
python3 scripts/experiment.py init \
  --config configs/semantic_region_multikeyframe_extension.json \
  --run-id E3a-temporal-association-20261104-001
bash scripts/run_e3a_temporal_region_association.sh \
  E3a-temporal-association-20261104-001 \
  E1a-multikeyframe-20261104-002 \
  E1a-multikeyframe-20261104-002
```
