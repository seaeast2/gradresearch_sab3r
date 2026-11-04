# E3 — Replica office0 local Region build

**판정: 단일 Keyframe에서 frame-wise Region 후보 생성 완료.** 성공 run은 `E3-replica-office0-20261104-001`이며 E1 pointmap과 E2 prompt-score 결과를 해시로 고정해 사용했습니다. GT는 입력하지 않았습니다.

## 절차

같은 의미 label의 4-연결 성분을 기준군으로 만들고, 제안 후보에서는 인접 pixel 사이의 3D edge를 추가로 검사했습니다. edge 길이는 양 끝점의 같은 label 이웃 간격 중 작은 값의 배수(3.0) 이하여야 하고, 국부 pointmap normal의 unsigned 차이는 45° 이하여야 연결했습니다. normal 계산이 불가능한 가장자리 pixel에서는 거리 조건만 사용했습니다. 임계값은 초기 파일럿 값이며 validation에서 선택·동결한 값이 아닙니다.

실행 설정은 [`e3_region_build.json`](../../../configs/e3_region_build.json), 구현은 [`build_e3_regions.py`](../../../scripts/build_e3_regions.py)에 있습니다. 입력 validity는 E1 valid mask, finite world coordinate, finite positive geometry confidence의 교집합입니다.

## 결과

- Grid: 288×512, 유효 pixel 147,456개
- 의미 label만 사용한 4-연결: **78 Regions**
- 거리·normal gate도 적용: **324 Regions**
- geometry gate 뒤 Region 크기 중앙값: 1 pixel; 가장 큰 Region: 58,456 pixels
- 기준 4-연결에서 label별 Region 수: floor 3, wall 14, ceiling 7, table 11, cabinet 5, door 1, other 37
- gate가 작은 고립 component를 많이 만들었으므로, 324를 유효한 표면 수로 해석하지 않습니다. E4는 최소 크기 및 평면 적합 기준으로 후보를 더 걸러내고 제외 사유를 기록합니다.

![의미·geometry 연결 조건으로 나눈 E3 Region 경계](../../../runs/semantic_region_pointmap/E3-replica-office0-20261104-001/stages/E3_region_build/artifacts/semantic_geometry_regions.png)

전체 mask와 Region별 통계는 [E3 artifacts](../../../runs/semantic_region_pointmap/E3-replica-office0-20261104-001/stages/E3_region_build/artifacts/)에 있습니다. `regions.json`의 self-fitted plane residual은 Region 설명용 통계이며 GT 정확도 지표가 아닙니다.

## 한계와 다음 stage

E1 export에 Keyframe이 하나뿐이라 temporal association/merge는 실행하지 않았습니다. E2 score margin은 calibration되지 않았고, 이 단계에서는 별도 minimum semantic margin gate를 적용하지 않았습니다. 따라서 E4에서 작은 Region이나 plane-fit이 불안정한 후보를 보정 대상으로 강제하지 않습니다. E5에서는 E4가 선택한 Region을 고정한 뒤, 원본 Replica frame 0 depth를 평가 전용 GT로 사용합니다.

오류가 난 최초 E3 실행은 E2 result run의 failed manifest에 보존되어 있고, Region 산출 전에 종료됐습니다. 인접 edge를 2D pixel index로 변환하는 오류를 고친 뒤 새 run에서 완료했습니다.
