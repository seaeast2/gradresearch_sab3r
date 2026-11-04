# E1a–E3a: Replica room0 validation sequence

이 장면은 E3a의 association 설정을 장면 단위로 검토하기 위한 **validation 장면**이다. E3a office0의 단일 two-Keyframe 파일럿과 구분된 run으로 만들었으며, 이 결과를 test 평가나 정확도 주장에 사용하지 않는다.

## 실행 정보

- Run ID: `E1a-replica-room0-validation-20261104-001`
- Source: `/home/hlee221212/works/gradresearch/data/E2b/Replica/room0/results`
- RGB 입력: 1,000장; depth PNG는 SLAM RGB 입력에서 제외
- MASt3R-SLAM: 호스트 GPU, RTX 5060, 153.24 s, host-wide peak memory 4,230 MiB
- SAB3R: 7/7 Keyframe, GPU 추론 합계 56.47 s, 최대 allocated memory 6,371.1 MiB
- Keyframes: frame IDs `0, 207, 385, 533, 621, 733, 823`; pointmap grid 모두 288×512, 유효 point 147,456
- E1a export manifest SHA-256: `8c72361bd85207befa1d9197dfb148933663e05872f7fb2f12c0fe3fb929633c`
- E2a keyframes manifest SHA-256: `5e19f6dca34f1ab89e327a5f64a2012abb7a5fb9ccdbba3d0139a07b7139ca6f`
- E3a config: `configs/e3a_temporal_region_association.json` (office0 pilot과 같은 exploratory 값)

## E3a 결과

- Frame-local Region 수는 순서대로 `150, 143, 195, 64, 72, 85, 119`였다. 합계 828개 local Region에서 17개의 temporal edge를 수락했고, persistent ID는 811개가 됐다.
- 6개 인접 Keyframe 쌍에서 상호 최근접 pointmap correspondence는 각각 `45,970`, `45,477`, `45,388`, `46,900`, `35,917`, `38,469`개였다. 쌍별 유효 pixel은 양쪽 147,456개다.
- 같은 semantic class의 전체 Region 조합 21,235개 중 17개가 최소 크기, 대응 수, 양방향 overlap, world bounds 및 적용 가능한 평면 gate를 모두 통과했다. 조합 수는 임계값 후보 수율이며 물리 표면 recall/precision을 뜻하지 않는다.
- 통과한 링크는 floor 4, ceiling 5, cabinet 4, door 3, wall 2, other 1개였다. 인접 frame pair마다 class별 Hungarian one-to-one matching을 수행했다.
- 주요 거부 사유는 overlap 미달 21,207, 상호 대응 수 미달 21,182, 최소 Region 크기 미달 21,006 등이었다. 여러 사유가 한 조합에 동시에 기록될 수 있다.

## 해석 및 한계

7개 Keyframe에서도 pipeline은 연결 edge를 생성했고, office0 두 프레임 파일럿보다 더 많은 연속 관측을 처리했다. 그러나 이 장면도 Replica room0 한 개뿐이며, 현재 보고서에는 같은 물리 표면을 지정한 수동 정답 또는 GT correspondence 평가가 없다. 따라서 17개 edge의 correctness와 811개 persistent ID의 안정성은 아직 검증되지 않았다. 실험상 후보 pair 조합의 다수는 거부됐고, 이를 validation accuracy로 해석하지 않는다.

office0 및 room0 두 validation scene을 함께 검토한 뒤 association/error-score 설정을 동결해야 한다. 독립 test scene을 본 뒤 threshold를 바꾸지 않는다. 남은 실행 목표는 다른 Replica scene에서 frozen 설정을 평가하고, dense GT가 확보되는 scene만 B0–B4 기하 비교에 넣는 것이다.

## 산출물

- E1a: `runs/semantic_region_pointmap/E1a-replica-room0-validation-20261104-001/stages/E1a_multikeyframe_slam_export/`
- E2a: `runs/semantic_region_pointmap/E1a-replica-room0-validation-20261104-001/stages/E2a_multikeyframe_semantics/`
- E3a: `runs/semantic_region_pointmap/E1a-replica-room0-validation-20261104-001/stages/E3a_temporal_region_association/`
- E3a `temporal_regions.json` SHA-256: `12b83d13e8c16fa271d27cf2c6c8e61c77d6c4f3884559c3497bb02eddc8ec31`
- 각 stage manifest는 artifacts의 SHA-256을 기록한다.
