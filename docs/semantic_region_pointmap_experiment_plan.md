# 의미 기반 Region 분할을 활용한 SLAM Pointmap의 국부 기하 최적화 — 상세 실험 계획서

- **문서 유형:** 석사학위논문 연구용 실험 실행 계획서(초안)
- **작성 기준일:** 2026-11-03
- **실험 수행 GitHub 저장소:** [seaeast2/gradresearch_sab3r](https://github.com/seaeast2/gradresearch_sab3r) (`https://github.com/seaeast2/gradresearch_sab3r.git`)
- **실험 프로젝트 루트:** `gradresearch_sab3r/` (GitHub 기본 브랜치 `main`)
- **저장소 초기 상태:** 2026-11-03 확인 시 빈 공개 저장소 — 아래 폴더/파일 목록은 생성할 *권장 구조*이며 아직 생성된 파일을 의미하지 않음
- **가제(국문):** 의미 기반 영역 분할을 이용한 SLAM Pointmap의 국부 기하 최적화 연구
- **가제(영문):** Semantic-Guided Region-wise Geometric Refinement of Pointmaps in Visual SLAM
- **실험 단계:** 오프라인 후처리 기반 재현성 검증 → 필요 시 기존 SLAM 파이프라인으로 확장
- **최우선 범위:** 정적 장면, 평면/준평면 Region, 기하 왜곡 및 이상점 감소
- **범위 제외:** 전체 지도와의 공동 재최적화, 카메라 Pose 재추정, Region 경계 공동 최적화, 동적 객체 추적, 3DGS 엔드투엔드 학습

> **근거와 제안의 구분.** MASt3R-SLAM의 pointmap fusion 및 pose/scale 정렬, SAB3R의 pointmap과 픽셀별 CLIP·DINOv2 특징 출력은 첨부 논문에 근거한다. 본 문서에서 제안하는 Region 분할·연결·평면 제약·평가지표 조합 및 임계값은 **연구자가 새로 설계하여 검증할 실험 프로토콜**이며, 해당 논문의 기성 알고리즘 또는 검증된 성능을 의미하지 않는다.

---

## 1. 연구 배경과 문제 정의

### 1.1 문제 상황

MASt3R-SLAM은 연속 영상으로부터 카메라 위치를 추정하고, Keyframe을 기준으로 Pointmap을 융합한다. 프레임별 점 좌표를 여러 관측에 걸쳐 평균화하더라도 모델의 편향, 깊이 추정 오차, 자세/스케일 오차 때문에 실제 평면인 바닥·벽 등의 점군이 휘거나 구간별로 불연속이 발생할 수 있다. 단순 전역 평면 투영은 바닥과 벽, 다양한 기하 구조를 구별하지 못하므로 정상 형상도 손상할 수 있다.

SAB3R은 MASt3R에 의미 특징 추정 기능을 결합하여 픽셀별 CLIP 및 DINOv2 특징과 3D 재구성 정보를 제공한다. 이 특징을 이용해 점군의 의미를 나눈 후, 같은 의미 및 같은 표면에 속하는 공간적으로 연결된 점을 **Region**으로 구성하면 각 Region의 기하학적 형태에 맞춘 국부 최적화를 적용할 수 있다.

### 1.2 연구 목표

**전체 SLAM 재최적화 없이 기존 카메라 Pose와 다른 Region의 좌표는 고정한 채, 의미적으로 구분된 평면 영역의 Pointmap을 선택적으로 보정하여 실제 기하 오차를 줄이는가?**

이 연구는 `chair` 같은 의미 클래스의 두 객체를 완벽히 식별하는 것이 목적이 아니다. 같은 의미 클래스라도 공간적으로 분리된 영역이면 별도 Region ID를 부여한다. 반대로 복수 프레임에서 관측한 같은 표면의 영역은 다중 시점 연결 근거가 있을 때 같은 Region ID로 병합한다.

### 1.3 연구 범위

**포함:**

1. 기존 MASt3R-SLAM의 Keyframe, 융합 Pointmap, 신뢰도, 최종 Pose 추출 및 고정.
2. SAB3R를 이용한 픽셀별 의미 분류 및 의미 확신도 산출.
3. 2D/3D 이웃 관계, 깊이 불연속, 표면 방향, 다중 시점 대응을 고려한 Region 생성/병합.
4. Planar Region의 강건 평면 추정과 선택적 점 위치 보정.
5. GT 기준 기하 정확도, 이상점 비율, 의미·Region 분할 품질, 변경 영향 범위 평가.

**제외:**

- SLAM 추적 및 Loop Closure 결과를 다시 최적화하는 작업.
- Region 간 경계를 일치시키는 연립 최적화.
- 곡면 전체에 대한 복잡한 비강체 재배치.
- 단안 영상만으로 절대 미터 스케일을 회복한다는 주장.
- 3D Gaussian Splatting의 품질 향상을 실증 없이 주장하는 작업.

**경계 주의:** 다른 Region 좌표를 고정해도 경계 불연속이 커질 수 있으므로, 경계 손상 여부는 안전성·한계 지표로 반드시 기록한다. 경계의 공동 보정은 향후 연구로 남긴다.

---

## 2. 가설 및 판정 기준

| 가설 | 연구 질문 | 실험적 검증 방식 | 반증 가능성 |
|---|---|---|---|
| H1 | 의미 기반 Region 분할 후 평면 보정이 원본 SLAM보다 실제 기하 오차를 낮추는가? | GT 평면·메시까지의 거리, surface accuracy, 이상점 비율 | GT 오차가 동일하거나 악화되면 기각 |
| H2 | 의미 분할이 기하 정보만으로 평면 영역을 구분하는 방법보다 유리한가? | 동일 최적화기로 Semantic+Geometry와 Geometry-only 비교 | Geometry-only가 유사하거나 우수하면 의미 부가가치 미확인 |
| H3 | 프레임 간 Region 병합이 프레임별 독립 Region보다 유리한가? | 동일 장면·설정에서 temporal merge on/off 비교 | 차이가 없거나 과병합으로 악화되면 기각 |
| H4 | 신뢰도·강건 추정·변위 제한으로 정상점 손실을 줄일 수 있는가? | 가중치/robust loss/변위 제한 ablation | 보정량 증가에 따른 손실이 감소하지 않으면 기각 |

### 2.1 실험 성공 조건(사전 등록 초안)

연구 시작 전 검증 데이터와 성공 기준을 고정한다. 다음 수치는 논문 결과가 아니라 **예비 목표**다.

- 주요 지표: GT를 기준으로 측정한 **대상 평면 Region의 point-to-surface RMSE**.
- 예비 성능 목표: 원본 대비 RMSE **10% 이상 감소**(다수 장면의 중앙값); 10%는 실험 설계용 목표치이며 결과에 따라 수정하지 않는다.
- 보호 기준: 비대상 Region의 Point 좌표 변경량이 구현상 0이며, 대상 Region의 GT 기준 F-score·completeness가 유의하게 악화되지 않을 것.
- 이상점 기준: GT 표면까지 거리 > `2–3 × 평가 voxel 크기`인 점의 비율을 주요 보조 지표로 사용하고, 절대 거리 임계값은 장면 단위와 센서 정밀도에 맞게 고정.
- 실패 정의: 대상 Region 선별 실패, 과병합, 평면이 아닌 Region에 대한 평면 적용, GT 오차 증가, 경계 간극 급증, Pose/스케일 불일치 등.
- 대상 Region만 골라 성공률을 발표하지 않고 **선정된 전체 후보에 대한 적용률·실패율**을 함께 보고한다.

---

## 3. 이론적·기술적 근거

### 3.1 MASt3R-SLAM (기존 기술)

- Pointmap과 pixel matching을 이용해 추적하고, Keyframe Canonical Pointmap을 신뢰도 가중평균으로 갱신한다(논문 §3.3, Eq. (8)).
- Pose는 `Sim(3)`로 다루며 스케일 일관성에 주의해야 한다(논문 §3.1).
- Backend는 Keyframe Pose와 dense geometry의 전역 일관성을 개선하지만, 모든 점 좌표를 자유롭게 각각 최적화하는 방식과 동일하지 않다(논문 §3.5 및 Limitations).
- 제안 연구에서는 기존 결과를 **동일한 입력 기하 상태**로 저장하고 후처리하므로 모델 교체 효과와 후처리 효과를 혼동하지 않는다.

### 3.2 SAB3R (기존 기술)

- 픽셀별 Pointmap과 CLIP/DINOv2 특징을 하나의 backbone에서 예측한다(논문 §4, Fig. 3).
- 의미 레이블은 CLIP 특징과 텍스트 프롬프트 사이 유사도로 얻는 **질의 및 후보 클래스 집합에 의존하는 결과**다. 고정된 전역 Instance ID가 자동 생성되는 것은 아니다.
- 논문의 'Map and Locate' 평가는 ScanNet 기반 2~4장 이미지 그룹과 의미 라벨을 사용하므로, 장기 연속 영상 SLAM에서 안정적인 Region 추적·병합은 별도 검증이 필요하다(논문 §3–5).

### 3.3 두 모델을 무리하게 결합하지 않는 이유

SAB3R의 pointmap head와 MASt3R-SLAM의 핵심 tracking/feature matching 구현은 그대로 상호 대체 가능하다고 가정할 수 없다. 따라서 **1차 실험은 MASt3R-SLAM의 점군과 Pose를 고정**, 같은 RGB Keyframe을 SAB3R에 넣어 의미 정보만 추출한다. 원본 Pointmap에 의미를 붙일 때는 동일 Keyframe 픽셀 정렬을 우선 활용하고, SAB3R 입력/출력 해상도 차이·크롭·패딩·좌표계를 기록하며 정확한 매핑을 적용한다.

**체크포인트 확인:** SAB3R 공개 README에는 Hugging Face Hub `uva-cv-lab/SAB3R`의 `demo_ckpt/base/base.pt`를 사용하는 추론 경로가 제시된다. 코드/체크포인트 변경 가능성이 있으므로 실제 실행·VRAM 측정으로 확인한다.

---

## 4. 전체 파이프라인 및 데이터 흐름

```text
[동일 RGB 영상 시퀀스]
           |
           v
[MASt3R-SLAM: 고정된 기존 실행]
   ├─ Keyframe RGB 원본 및 픽셀 좌표계
   ├─ Canonical Pointmap + Confidence
   ├─ 최종 Keyframe Sim(3) Pose / Camera rays
   └─ 프레임별 Correspondence (가능할 경우)
           |
           +-----------------------------+
           |                             |
           v                             v
[최종 World 좌표 Pointmap]      [SAB3R: 의미 특징 추론]
                                         |
                                [Semantic labels / scores]
           |                             |
           +-------------+---------------+
                         v
            [Frame-wise 2D/3D Region 생성]
                         |
             [시간·공간적 Region Association]
                         |
               [Global Region ID 할당]
                         |
                 [평면 후보만 선별]
                         |
               [Robust Plane Estimation]
                         |
          [Ray-constrained Local Refinement]
                         |
          [비대상점 고정, 결과 재투영/평가]
                         |
              [실험군 비교·정량 평가]
```

### 4.1 처리 모드의 구분

- **모드 A (권장 / 핵심 실험):** 전체 영상으로 MASt3R-SLAM 실행 → 최종 Pose 저장 → SAB3R Keyframe별 의미 추론 → 오프라인 Region 최적화.
- **모드 B (선택):** 생성된 Keyframe의 의미 결과를 SLAM 내부 캐시에 저장. **온라인 포인트 수정은 수행하지 않음.**
- **모드 C (향후):** 추적·Fusion 단계에 Region 최적화를 결합하는 실시간 시스템. 이번 학위논문 범위 밖.

---

## 5. 데이터 표현 및 좌표계

### 5.1 Keyframe 저장 단위

Keyframe `k`의 데이터:

```text
frame_id, timestamp, rgb_path
image_size, resize_crop_info
X_cam[k][v,u,3]            # Canonical pointmap, camera/local 좌표
C_geom[k][v,u]             # Geometry confidence
T_world_cam[k]             # 최종 Sim(3) (행렬 규약 명시)
ray[k][v,u,3]              # 규격화된 camera ray, 얻을 수 있을 때
valid[k][v,u]              # NaN/Inf/뒷방향/비정상값 제거 mask
semantic_feature[k][v,u,d] # 선택적으로 별도 압축 저장
semantic_label[k][v,u]
semantic_score[k][v,u]
region_local[k][v,u]
region_global[k][v,u]
```

**주의:** `Sim(3)` 행렬에 스케일이 포함되므로 좌표 변환 시 `p_W=s_k R_k p_{C_k}+t_k`처럼 **점 변환과 Pose 방향 정의**를 확인한다. 점 좌표는 World 기준으로 비교하되 Pixel 인덱스와 Keyframe 원본 연관성을 유지한다. 전체 시퀀스에 대해 단일 전역 단위/스케일을 유지하고, Region별로 임의의 scale fitting을 하지 않는다.

### 5.2 Region 데이터

```text
region_id, semantic_label, semantic_score_avg
members = [(frame_id, pixel_id), ...]
point_indices_world
num_frames_observed
support_matches
bbox_3d, centroid, estimated_normal
plane = (n_x,n_y,n_z,d) or null
planarity_score, inlier_ratio
merge_history, split_history
optimization_status, failure_reason
```

하나의 Pointmap에 여러 의미/Region이 존재한다. `chair`라는 의미 레이블은 여러 Region에 반복되어도 된다. Region ID는 **최적화를 위한 공간 연결 영역의 식별자**이지, 동일 실물 객체의 영구적 정체성이 아니다.

---

## 6. 단계별 세부 구현 계획

### 단계 0. 실험 환경과 재현성 고정

1. 두 저장소의 commit hash, PyTorch/CUDA 버전, OS, GPU, driver, calibration 사용 여부 기록.
2. 동일한 동영상·해상도·Keyframe 추출 규칙·MASt3R-SLAM 설정을 모든 실험군에서 사용.
3. 실험 결과 파일에 `scene_id`, `run_id`, `git_hash`, `config_hash`, `seed`, `model_weight_hash`, `elapsed`, `peak_vram` 기록.
4. 동일 시퀀스에서 후처리 입력을 재사용하여 SLAM의 프레임별 비결정성 변동을 최소화.

**산출물:** 환경 명세, 기준 실행 로그, 원본 Keyframe/Pointmap/Trajectory 캐시.

### 단계 1. 기준 Pointmap 추출 및 검증

1. 1~2개 짧은 영상에서 MASt3R-SLAM 재현.
2. Canonical Pointmap/Confidence/최종 Pose를 저장. 저장 코드가 없다면 우선 최소 Export 기능만 추가.
3. World Pointmap과 RGB 픽셀 색의 일대일 정합을 시각화.
4. Pose 변경 전후의 데이터 혼용 방지: Loop Closure·Backend 최적화 후 최종 결과만 확정.
5. 하나의 벽/바닥 영역을 수동 선택하여 point-to-plane 오차를 계산하는 작은 단위시험 생성.

**검증:** RGB에 대응하는 3D 점이 맞는지, 좌표계·스케일·행렬 방향이 일치하는지, 재구성 시각화로 확인. 실패 시 의미 분할 진행 중단.

### 단계 2. SAB3R 의미 추론 및 2D 마스크 생성

1. Keyframe RGB를 SAB3R에 통과시키며 실제 출력 tensor의 의미·해상도를 코드 수준에서 확인.
2. 후보 라벨은 실험의 핵심 클래스(예: `floor`, `wall`, `ceiling`, `ground`, `road`, `runway`)와 교란 클래스(`table`, `cabinet`, `door`, `other`)로 미리 고정. `runway`는 모델 학습 영역의 편향이 있을 수 있으므로 별도 정성 분석.
3. 각 픽셀의 CLIP 특징 `f_i`와 텍스트 벡터 `t_l`의 cosine similarity로 클래스 점수 산출.
4. `label = argmax_l cos(f_i,t_l)`. 최고 점수만으로 미지 클래스를 단정하지 말고 최고-차점 마진 및 calibration 검증으로 `void/uncertain` 처리.
5. 작은 홀 제거, 고립 픽셀 정리, 필요 시 morphology를 수행하되 원본 mask를 반드시 보존.
6. Pointmap 픽셀과 의미 출력 픽셀 정렬(크롭, 종횡비, 보간) 검증.

**중요:** 의미 구분의 오류를 기하 최적화 오류와 분리하기 위해 GT/수동 마스크 기반 **Oracle segmentation** 실험도 준비한다.

### 단계 3. 프레임별 Region 분할

초기 Region은 이미지 내 동일 레이블의 4/8-연결 성분에서 출발한다. 픽셀 `a,b`가 인접할 때 다음을 모두 만족하는 경우에만 연결한다.

- (i) `label(a)=label(b)` 또는 둘의 충분한 의미 유사도.
- (ii) 3D 거리 `||X_a-X_b||`가 **깊이·픽셀 해상도·국부 샘플 간격으로 정규화한** 임계값 아래.
- (iii) 깊이/법선 불연속이 지나치지 않을 것.
- (iv) Confidence가 최소 조건을 통과할 것.

벽과 바닥의 의미가 잘 나뉘어도 같은 벽 클래스가 모서리를 경계로 이어질 수 있다. 평면 최적화의 실제 단위는 **semantic class 하나가 아니라, 대략 한 개의 일관된 기하 표면(plane patch)인 Region**이어야 하므로, **법선 차이 또는 평면 residual을 이용한 region split**을 추가한다.

**산출물:** Keyframe별 `region_local` 마스크와 Region 통계·시각화.

### 단계 4. Keyframe 간 Region Association / 병합

후보 쌍 `A,B`는 다음을 모두 고려한다.

1. 같은 또는 충분히 가까운 의미 클래스.
2. 공통 World 좌표계에서 bbox/voxel 공간 후보 근접 또는 겹침.
3. 다중 시점 대응점(SLAM match)이 일정 비율 이상 연결하는지.
4. 표면 법선/평면 방향 일치, 양방향 점군 근접도, 과도한 3D 오차·가림 충돌 여부.
5. 두 Region을 병합했을 때 RANSAC 평면 inlier 비율이 비정상적으로 낮아지지 않는지.

초기 후보의 점수는 예를 들어 다음처럼 가중 합으로 설계할 수 있다(전부 가설적 설계):

`S_assoc(A,B) = w_s S_sem + w_m S_match + w_o S_overlap + w_n S_normal − w_r E_plane`.

**강한 대응 관계 우선:** MASt3R-SLAM에서 얻을 수 있는 feature correspondence를 먼저 사용하고, 거리 기반 연산은 근접 후보 확인용으로 사용한다. 서로 다른 시점이 같은 평면을 보지만 점군이 오차로 벌어진 경우 **거리만으로 무조건 분리하지 않는다.** 반대로 멀리 떨어진 동일 클래스끼리 의미만으로 병합하지 않는다.

**구현 구조:** Region 간 연결 그래프 구성 → 신뢰 가능한 edge만 채택 → Union-Find로 Connected Components 계산 → 병합 후 표면 품질 검사 → 오류 시 edge 취소 및 재분리.

**반례 단위시험:** `chair` 두 개가 분리되어 있는 경우, 동일 벽이 두 프레임에서 중복 관측된 경우, 직각으로 만나는 두 벽의 경우, 바닥 위 카펫·책상과 의미 오분류의 경우, 깊이 불연속으로 가려진 같은 표면.

### 단계 5. 평면/준평면 후보 선별

- 대상: `floor`, `wall`, `ground`, `runway` 등 **평면성 검사를 통과한** 클래스.
- RANSAC/MSAC 등을 이용해 Region별 평면 `n^T x + d = 0`, `||n||=1` 추정.
- 최소 점 개수, 다중 Keyframe 관측 수, inlier 비율, 고유값(PCA) 기반 평면성, 법선 분산 등을 기준으로 적용 여부 판단.
- 활주로·도로는 완전 평면이라고 전제하지 않는다. 실제 배수 경사·경사진 구간은 **평면 패치로 분할**하거나 최적화 대상에서 제외한다.
- `void`, 동적 객체, 반사·투명 영역, 신뢰도가 낮은 영역은 제외.

**결과:** `eligible`, `ineligible`, `deferred` 상태와 그 이유. 적용한 Region 수뿐 아니라 제외율도 보고.

### 단계 6. 국부 기하 최적화 — 기본형

**최적화 전제:** SLAM 최종 Keyframe Pose와 비대상 점은 고정한다. 보정 대상은 선별된 Region 내부 점만이다.

Region의 점 `p_i^0 ∈ R^3`, 추정 평면 `(n,d)`, 신뢰도 `w_i`에 대해 가장 단순한 목적함수:

\[
E_R(\{p_i\},n,d)
=\sum_{i\in R} w_i\,\rho(n^\top p_i+d)
+\lambda\sum_{i\in R}\|p_i-p_i^0\|^2.
\]

- `ρ`: L1, Huber 또는 Cauchy 등 강건 손실(1차 구현은 Huber 권장).
- 두 번째 항: 과도한 점 이동 억제.
- 평면 파라미터는 강건 초기 추정 후 고정하거나 제한적으로 재추정하되, 충분한 제약 없이 점과 평면을 동시에 자유롭게 이동시키면 미정성(degeneracy)이 생길 수 있음.

**권장 기본 구현 — ray-constrained depth refinement:**

가능하다면 원래 Keyframe의 카메라 중심 `c_i`와 pixel ray `r_i`를 유지하여 각 점의 깊이 `z_i`만 바꾼다.

\[
p_i'=c_i+z_i'r_i,\quad
E_R(\{z_i'\})=\sum_{i\in R} w_i\rho\big(n^\top(c_i+z_i'r_i)+d\big)
+\lambda\sum_{i\in R}(z_i'-z_i^0)^2.
\]

이 파라미터화는 원래 픽셀과 관측 ray의 대응을 보존하므로 자유 3D 이동보다 해석이 쉽다. `|n^T r_i|`가 작으면(ray가 평면에 거의 평행) 업데이트를 건너뛰고, 잘못된 ray 방향·음수 깊이·과도한 `|Δz_i|`는 차단한다.

**실행 정책:** `max_delta = α × local_spacing` 혹은 GT 독립 검증에서 선택한 고정 거리 제한, geometry confidence가 낮은 점의 영향 축소, 경계에서 거리 `b` 이내에 속한 점은 **수정 제외 또는 약화**(경계 정합 자체는 해결하지 않음).

**대안:** 유효한 ray가 없을 경우 `p_i'=p_i - \eta_i(n^Tp_i+d)n`으로 제한된 법선 방향 보정. 두 방법을 혼합해 주효과를 주장하지 않고 별도 ablation으로 비교.

### 단계 7. 수정 결과 기록·시각화

- `original_world.ply`, `semantic_region.ply`, `optimized_world.ply`, `delta_vectors.ply` 저장.
- 원래 점 좌표와 수정 점을 동일 point ID로 연결하여 변위량, GT 오차 전후, 평면 residual 전후를 색으로 표시.
- 수정하지 않은 Region에 대해 byte-level 또는 수치적으로 좌표가 동일함을 assert.
- 잘못된 평탄화로 부자연스러운 벽·바닥 경계가 발생하는지 컬러 오버레이로 제공.

---

## 7. 데이터셋 선정 및 실험 역할

| 데이터 | 주요 용도 | 장점 | 제약/주의 |
|---|---|---|---|
| **Replica** (1순위 통제 실험) | GT mesh/평면/semantic을 이용한 기하 평가 | 깨끗한 dense scene geometry, semantic 및 planar pre-segmentation 제공 | 제공된 3D 자산을 이용해 **RGB 단안 시퀀스·GT Pose를 별도 렌더링**해야 하므로 구현 비용 존재 |
| **ScanNet** (현실 검증) | 실내 RGB 영상, 평면/벽/바닥, 실제 센서 오차 평가 | RGB-D·Pose·메시·semantic annotation | 접근 승인 필요, 노이즈 있는 GT 메시/라벨은 절대 진실이 아님 |
| **ScanNet++** (선택 확장) | 고품질 현실 장면의 추가 검증 | 영상·메시·semantics·공식 도구 | 원본 전체 데이터 크기가 큼; 일부 장면만 선택 |
| **ETH3D-SLAM / TUM RGB-D** (보조) | SLAM 재현·트래킹 확인 | Pose·카메라 정보 접근 | 평가 대상 semantic label 및 dense plane GT가 부족할 수 있음 |
| **자체 촬영 또는 CARLA 등 합성 환경** (선택) | 활주로/도로 특수 사례 | 장면 구조·평면·GT를 통제 가능 | 오픈 환경 편향, 랜더링·시뮬레이터 개발 추가 비용 |

**데이터 분할 권고:** (a) 2개 예비 장면, (b) 3~5개 validation 장면, (c) 5~10개 test 장면을 **장면 단위로** 구분한다. 실제 준비 가능한 장면 수에 따라 사전 확정한다. 한 장면의 여러 프레임을 train/validation/test로 따로 나누지 않는다.

**입력 통제:** 모든 방법은 RGB만으로 SLAM을 진행하며, **GT depth/GT semantic/GT pose를 제안 기법에 입력하지 않는다.** GT는 *Oracle 상한 비교와 평가 전용*이다. Oracle 실험 결과는 실제 SAB3R 적용 결과와 분명히 분리한다.

### 7.1 합성 평면 파일럿

- 전형적인 실내 공간: 평면 바닥 1개, 직교 벽 2개, 장애물 1~2개.
- RGB 영상 + 완전 정확한 GT mesh/semantic/pose를 생성.
- 기존 Pointmap에 깊이 방향 noise, 국부 파형 편향, 계단식 오프셋, 3D stray points를 **주입하는 별도 통제 실험**을 구성.
- 주입된 왜곡은 알고리즘 검증용이며, 실제 MASt3R-SLAM의 오류 분포를 재현한 것이라고 주장하지 않는다.
- 오차 강도(`σ`), 비율, 연결 경계 오차 등을 단계적으로 증가시키고 GT와 비교한다.

---

## 8. 비교군 및 Ablation 설계

**모든 후처리군은 반드시 동일한 MASt3R-SLAM 최종 Pointmap/Keyframe/Pose를 입력으로 사용한다.** 다른 입력 모델을 써서 생긴 기하 정확도 차이를 본 연구 효과로 오인하지 않는다.

| 그룹 | 의미 분할 | Region 연결/병합 | 평면 최적화 | 목적 |
|---|---|---|---|---|
| **B0: Original** | 없음 | 없음 | 없음 | 원본 SLAM 성능 |
| **B1: Geometry-only** | 없음 | 3D 근접·법선 기반 | 동일 | 의미 정보의 부가 효과 검증(강한 비교군) |
| **B2: Semantic, no temporal merge** | SAB3R | 프레임별 독립 Region | 동일 | 시계열 병합 자체의 기여 검증 |
| **B3: Semantic + temporal merge** | SAB3R | 의미·기하·시점 대응 결합 | 동일 | **주요 제안 방법** |
| **B4: Oracle segmentation** | GT 마스크(평가 전용) | B3와 동일 | 동일 | 분할 정확도의 상한 영향 분석 |

**필수 Ablation(선정된 B3에 적용):**

- `A1`: CLIP semantic confidence gate on/off.
- `A2`: spatial distance only vs spatial + normals vs spatial + temporal matches.
- `A3`: RANSAC/MSAC plane fit vs simple least-squares fit.
- `A4`: uniform weights vs geometry-confidence weights.
- `A5`: unconstrained XYZ displacement vs ray-constrained depth.
- `A6`: displacement limit off/on.
- `A7`: Region boundary band freeze off/on.
- `A8`: label prompt variants(동의어 프롬프트 포함 vs 단일 프롬프트) — validation에서만 선택.

**공정성:** B1~B4에서 최대 변경량·평면 추정·최적화 제약·평가 샘플 규칙을 통일하고, Region 추출 방식 외의 변수를 최대한 고정한다.

---

## 9. 주요 수식과 지표 정의

### 9.1 의미 특징 및 Region 후보

SAB3R 특징 `f_i`와 텍스트 임베딩 `t_l`의 유사도:

\[
S_{i,l}=\frac{f_i^\top t_l}{\|f_i\|\|t_l\|},\qquad \hat l_i=\arg\max_l S_{i,l}.
\]

최고값이 아닌 **1·2위 유사도 차**를 신뢰도 보조 지표로 기록할 수 있다. 실제 확률로 정규화되어 있지 않으면 이를 '확률'이라 부르지 않는다.

Frame 간 연결 점수의 실험형 예시:

\[
S_{AB}=w_s S_{\text{sem}} +w_o S_{\text{overlap}}+w_m S_{\text{match}}+w_nS_{\text{normal}}-w_pE_{\text{plane}}.
\]

단일 임계값에 과적합하지 않도록 validation에서 범위를 고정하여 탐색한다.

### 9.2 평면 residual (보조 지표)

\[
RMSE_{\text{self-plane}}(R)=\sqrt{\frac{1}{|R|}\sum_{i\in R}(n_R^T p_i+d_R)^2}.
\]

**핵심 주의:** 알고리즘이 자기 점군에서 추정한 평면에 점을 투영하면 이 오차는 거의 반드시 작아진다. 따라서 self-plane RMSE 개선만으로 '3D 재구성 정확도 향상'이라고 주장하면 안 된다. 진짜 주요 평가지표는 독립 **GT geometry / held-out observations**를 기준으로 해야 한다.

### 9.3 GT 기하 정확도 (핵심 지표)

GT mesh `M_GT`에 대한 대상 Region 점 `p_i`의 최근접 표면거리 `d(p_i,M_GT)`:

\[
RMSE_{GT}(R)=\sqrt{\frac{1}{|R|}\sum_{i\in R}d(p_i,M_{GT})^2}.
\]

- Precision/accuracy: 예측점→GT surface 거리 평균 또는 중앙값.
- Completeness/coverage: GT 표면 균일 샘플→예측점 거리. **보정이 중복점 삭제/샘플 감소로 빈 구멍을 만들지 않는지 반드시 별도 측정.**
- F-score@τ: GT와 추정 사이 양방향 거리에서 임계값 `τ` 이내 precision/recall의 조화평균.
- `OutlierRate@τ = #\{p_i:d(p_i,M_GT)>τ\}/#\{p_i\}`. 극단적 stray point는 GT 영역 validity 조건도 함께 적용.
- Semantic IoU 및 Region 성분 분할 품질(수동/GT 마스크 기준), overmerge/undermerge 사례 수.
- Normal error: GT 표면 법선과 예측 국부 법선의 각도 오차.
- Reprojection/held-out depth consistency: 제공된 검증 프레임의 GT depth 또는 mesh-rendered depth와 비교.

### 9.4 안전성 지표

- `ModifiedFraction`: 실제 좌표가 수정된 점의 비율.
- `MeanDisplacement` / `MaxDisplacement`: Region 내 수정 크기.
- `OutsideDelta`: 비대상 Region 점 변위. **코드상 0 유지 여부를 확인**.
- `BoundaryGapBefore/After`: 변경 Region의 경계와 인접 Region 간 최근접 거리 변화(표면 기하가 달라 단독으로 정확도 지표가 되지는 않음).
- `FailureRate`: region 추출/평면 탐지/최적화 실패 수÷전체 후보 수.
- 처리 시간/Peak GPU memory: 추출, 의미 추론, 병합, 최적화를 나누어 보고. **후처리이므로 실시간성은 연구 목표로 주장하지 않는다.**

### 9.5 스케일·Pose·GT 공정성

단안 SLAM 결과에는 전역 similarity gauge가 있으므로 전 장면에 대해 **단 한 번의 공통 Sim(3) GT 정렬**을 수행할 수 있다. 단, 해당 변환은 **B0에서 추정하고 B1~B4에 재사용**하여 모든 그룹이 같은 좌표 기준으로 평가되게 한다. Region마다 별도 best-fit alignment를 허용하면 실제 위치 왜곡을 감출 수 있다. GT Pose를 SLAM 입력으로 제공하는 것이 아니라 평가 정렬에만 사용한다.

---

## 10. 임계값·초기 설정·탐색 계획

> 다음 값은 검증되어 제시된 수치가 아니다. 단위·해상도·월드 스케일을 확인한 뒤 *validation*에서만 확정한다.

| 파라미터 | 초기 탐색 방향 | 선정 방법 |
|---|---|---|
| voxel/downsample 크기 `v` | 예: 0.01, 0.02, 0.05 m (스케일 정합 후) | 장면 거리/GT 해상도에 따라 선택 |
| 3D 연결 거리 `ε` | `1.5v`, `2v`, `3v` 또는 국부 이웃 간격 배수 | Overmerge/undermerge trade-off |
| 법선 차이 `θ` | 예: 10°, 20°, 30° | 평면/모서리 분리 정성 평가 |
| 의미 유사도 `τ_sem` | score margin 및 cosine 분포로 선택 | validation PR 곡선 |
| planar inlier ratio | 예: 0.65, 0.75, 0.85 | GT 평면 분류 안정도 |
| 최소 Frame 관측 수 | 예: 2, 3, 5 | 소규모/가림 Region 영향 |
| plane RANSAC 거리 | `1v`~`3v` 등 | GT 및 재구성 노이즈 기준 |
| `λ` displacement prior | log scale grid | GT RMSE vs 변위/경계 손실 |
| max displacement | local spacing/depth uncertainty 배수 | 과도 보정 방지 |
| boundary exclusion band | 0/2/4 pixel 및 3D 거리 기준 | 경계 변형 통계 |

동일 대상 Test Set에 여러 차례 임계값을 조정하지 않는다. 숫자를 확정하지 못했을 경우 '실험 초안의 범위'로 기록하고 결과 발표 전 프로토콜을 동결한다.

---

## 11. 구체적인 실험 세트

### 실험 E0 — 입력·좌표계 검증

- 데이터: 실내 정적 짧은 시퀀스 1~2개.
- 확인: Pointmap 픽셀↔RGB 일치, Point cloud/world pose 방향, scale, Keyframe 순서, Loop Closure 이후 최종 Pose 반영.
- 통과 기준: 잘못된 좌표계로 인한 체계적 위치 오차가 없고, 재투영 검사/시각화가 정상.

### 실험 E1 — 의미 분할 가능성

- 데이터: 바닥·벽·천장이 잘 보이는 장면.
- 결과: RGB/CLIP query mask/GT or 수동 mask/Pointmap 컬러링 비교.
- 관찰: 바닥과 벽 혼동, 벽-가구 혼동, 다른 조명·각도에서 mask 흔들림.
- 지표: mIoU (대상 클래스), 평면 후보 영역 내 pixel precision/recall, void 비율.

### 실험 E2 — Connected Region 병합 정확성

- 데이터: 동일 표면 재관측, 직각 벽, 분리된 같은 클래스 객체, 부분 가림 포함.
- 비교: 2D-only 연결, 3D-only, semantic + 3D, semantic + 3D + temporal match.
- 지표: GT·수동 region에 대한 과병합/과분할 사례 수, 시간별 Region ID 안정성, 잘못된 병합 연결(edge) 비율.

### 실험 E3 — 통제된 평면 왜곡 회복

- 입력: GT가 있는 합성 장면으로부터 만든 정확한 pointcloud에 알려진 bias/noise/outlier를 주입한 데이터.
- 목적: 최적화 방향 및 기대 동작 단위 시험. 실 SLAM 결과와 구분해 보고.
- 조건: point noise 강도별·outlier 비율별·Region 면적별 경향.
- 측정: GT planar surface RMSE, OutlierRate, displacement, 다른 Region 변화.

### 실험 E4 — 실제 SLAM 결과의 원본 vs 제안법 (핵심)

- 데이터: Replica render 또는 ScanNet 실제 RGB 시퀀스.
- 그룹: B0~B4 동일 원본 Pointmap, 동일 평가 영역.
- 표: 전체 장면 평균/중앙값과 각 Scene별 결과 동시 제시.
- 검증: 주요 가설 H1/H2/H3 및 실패 예시 전부 기록.

### 실험 E5 — 최적화 안전성과 일반화

- 데이터: planar Region, nonplanar Region, 유리·반사·적은 텍스처, 가림 영역.
- 목적: 평면 선택 실패 시 손해를 통계화; 적용 제외 규칙 검증.
- 지표: False planar activation, GT normal error, 경계 간극, unaffected-region displacement.

### 실험 E6 — 선택적 3DGS 후속 실험(논문 본론과 분리)

- 개요: 동일 Gaussian 초기화/학습 설정에서 원본 Pointmap vs 후처리 Pointmap을 초기점으로 사용하고, rendering 차이를 측정.
- 전제: 3DGS 구현·학습 비용 및 평가시간이 허용될 때만 진행.
- 측정: held-out PSNR/SSIM/LPIPS, Gaussian outlier 수, 렌더링 hole/ghost 사례.
- **주의:** 수행하지 않으면 '3DGS 이상 Gaussian 감소'를 실증 기여로 주장하지 않는다. Pointmap 품질 개선은 3DGS 품질 개선과 동의어가 아니다.

---

### 다음 실행 확장 — 연속 Keyframe의 temporal Region 병합 및 오차 유도 보정 (E1a–E6a)

이 확장은 현재 실행 워크플로의 E1–E6 단계 코드에 알파벳 접미사를 붙인다. 아래 E1a–E6a는 **실행 워크플로 코드**이며, 앞 절의 연구 질문별 실험 E1–E6(의미 분할, Connected Region, 합성 왜곡, 실제 SLAM 비교, 안전성, 선택적 3DGS)를 대체하지 않는다. 이번 단일 Keyframe 파일럿에서 빠진 다중 시점 연결을 구현하고, 오류 후보 Region의 선택적 보정을 검증한다.

#### 연구 질문

1. 연속 RGB 시퀀스에서 만들어진 복수 MASt3R-SLAM Keyframe에 SAB3R tag를 부여하고, 같은 물리 표면을 오병합 없이 persistent Region으로 연결할 수 있는가?
2. 다중 시점 기하 불일치가 큰 Region을 선별해 국소 보정하면, 프레임별 독립 Region(B2)보다 GT 기하 오차가 낮아지는가?
3. 이 결과가 실내 한 장면에 한정되지 않고 다른 장면 유형에서도 재현되는가?

#### 확장 단계와 완료 게이트

| 코드 | 단계 | 처리와 분리 산출물 | 완료 게이트 |
|---|---|---|---|
| E1a | 다중 Keyframe SLAM export | 연속 RGB의 최종 Pose, Keyframe별 pointmap/confidence/RGB, frame correspondence, 입력·코드 hash | 유효 Keyframe 2개 이상, 동일 표면 재관측, pixel·world 좌표 정합 확인 |
| E2a | Keyframe별 SAB3R tagging | 각 Keyframe의 score, tag, score margin, void mask, 전처리·hash | 동일 label/prompt/전처리로 모든 Keyframe 처리, 픽셀 대응 검증 |
| E3a | temporal Region association/merge | frame-local Region ID와 persistent ID 대응, 채택·기각 edge, merge/split history, 시각화 | 반복 관측된 같은 표면 연결, 분리 표면/직각 벽 분리, ID 안정성과 오병합 기록 |
| E4a | 오류 후보 기반 국소 최적화 | validation에서 고정한 품질 점수, 후보·제외 사유, 보정 전후 pointmap, 변위·로그 | 비대상 점 변화 0, 변위 제한 준수, 적용률·실패율 보고, 원본 복구 가능 |
| E5a | 다중 시점 GT 평가 | 동일 SLAM export의 B0–B3 결과, scene/region metric, error visualization | GT surface RMSE와 completeness/F-score/outlier/normal/boundary 지표 기록 |
| E6a | 확장 결과 보고 | E1a–E5a manifest 및 hash를 검증한 요약 | B2/B3 비교, 장면별 결과, 실패 사례와 한계 포함 |

#### 시퀀스와 장면 설계

- E1a는 validation에서 정한 Keyframe 설정으로 연속 RGB를 처리한다. 최소 2개 Keyframe을 만들고, 관심 표면이 서로 다른 시점에서 반복 관측되어야 한다. 기존 30프레임 파일럿은 Keyframe 하나만 생성했으므로 E1a 성공 자료로 간주하지 않는다.
- 독립된 sequence/scene 3개 이상을 목표로 하고 실내 외에 개방형 또는 야외 장면을 포함한다. 확보한 GT geometry가 부족한 장면은 추적·정성 결과로 분리하고 주요 정확도 집계에 넣지 않는다. 목표 수를 채우지 못하면 실제 수와 한계를 보고한다.
- 데이터 split과 Keyframe/association/error-score 임계값은 scene 단위로 나누고 validation에서 고정한다. 같은 장면의 프레임을 train/validation/test 독립 표본처럼 세지 않는다.

#### Semantic tag와 persistent Region ID

SAB3R의 `wall`, `floor` 등은 의미 tag이며, persistent Region ID는 같은 물리 표면을 나타내는 별도 식별자다. tag가 같다는 이유만으로 병합하지 않는다. 후보 연결은 공통 World 좌표 overlap, MASt3R-SLAM 대응점, 법선·평면 일관성, 양방향 점군 근접도와 가림 충돌을 함께 본다. 근거가 부족하거나 상충하면 `deferred`로 두고 자동 병합하지 않는다. 병합 뒤 평면 inlier와 표면 일관성을 재검사하며, 품질이 악화되면 연결 edge를 취소하고 분리한다.

#### 오류 후보 선정과 보정

- test GT를 보정 대상 선정에 사용하지 않는다. 후보 점수는 validation에서 동결한 SLAM confidence, 다중 시점 대응 residual, cross-view 3D consistency, plane residual과 normal dispersion 등 추론 시 이용 가능한 신호로 만든다. 이 점수는 GT 오차의 대체 지표가 아니다.
- 큰 residual만으로 비평면이나 혼합 Region을 평탄화하지 않는다. 평면성, 최소 관측 수, inlier 비율, semantic uncertainty를 통과하지 못한 후보는 `ineligible` 또는 `deferred`로 기록한다.
- 기존 SLAM Pose와 비대상 점은 고정하고 선택 Region 내부만 robust, bounded 최적화한다. ray-constrained displacement와 boundary freeze를 적용하고, held-out/GT 평가가 악화되거나 제한을 넘은 후보는 실패로 보존한다.

#### 비교군과 분석

- B0: 원본 SLAM. B1: geometry-only Region. B2: SAB3R tag와 frame-local Region, temporal merge 없음. B3: semantic·기하·시점 대응으로 연결한 persistent Region. B4 Oracle은 평가 전용 GT mask가 확보될 때만 별도 상한으로 추가한다.
- 주 비교는 B2 대 B3이며, 모든 방법은 같은 E1a export, 같은 optimizer, 같은 평가 mask와 B0에서 계산한 공통 Sim(3)를 사용한다. Region ID 안정성, over/under-merge, 잘못된 association edge, 대상 surface RMSE, completeness, F-score, outlier, normal error와 boundary gap을 함께 기록한다.
- 결론은 scene 단위 결과로 낸다. 실내 단일 장면 성공만으로 일반화하지 않고, 각 환경의 결과와 실패 사례를 모두 보고한다.

## 12. 데이터 기록과 분석 통계

### 12.1 평가 단위

- **Scene 단위가 최종 독립 표본**이다. 한 Scene의 수십만 개 Point를 각각 독립 표본으로 간주하여 p-value를 과대평가하지 않는다.
- 같은 Scene 내 Region 수와 각 Region의 성능은 보조적으로 보고한다.
- 모든 실험군에 동일 테스트 장면, 동일 기준 Pointmap, 동일 GT 정렬 및 동일 평가 마스크를 적용한다.

### 12.2 결과 표(템플릿)

| Scene | Method | 대상 Point 수 | 적용 Region 수 | GT RMSE↓ | F-score↑ | Outlier@τ↓ | BoundaryGap 변화 | 시간(s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Scene A | B0 | | | | | | | |
| Scene A | B1 | | | | | | | |
| Scene A | B2 | | | | | | | |
| Scene A | B3 | | | | | | | |
| Scene A | B4 | | | | | | | |

각 Scene의 `ΔRMSE = RMSE(B3)-RMSE(B0)` 및 개선률 `(RMSE(B0)-RMSE(B3))/RMSE(B0)`를 산출한다. 가능하면 부트스트랩 CI를 **Scene 단위 resampling**으로 계산하고, 표본 수가 적을 때는 유의성 주장보다 일관성과 실패 사례 중심으로 해석한다.

### 12.3 도표/그림 필수 산출물

1. 원본/의미 mask/3D Region ID/최적화 Pointcloud 네 칸 비교.
2. 수정 벡터의 크기 heatmap 및 경계 확대.
3. GT surface distance 색상 비교 전/후.
4. 실험군별 GT RMSE box/paired plot.
5. Outlier rate vs threshold 곡선.
6. `λ` 및 merge threshold에 따른 성능/안전성 trade-off.
7. 성공 사례 2개와 실패 사례 2개를 **같은 기준으로** 소개.

---

## 13. 품질 보증 및 단위시험 목록

- [ ] Pointmap의 RGB 픽셀 인덱스와 추출된 3D 좌표가 일치한다.
- [ ] Camera-to-world와 world-to-camera가 뒤바뀌지 않았다.
- [ ] Sim(3) scale을 중복 적용하거나 무시하지 않는다.
- [ ] 최종 Loop Closure Pose를 반영한 데이터만 평가에 입력된다.
- [ ] SAB3R의 crop/resize를 되돌려 semantic mask와 RGB가 정합된다.
- [ ] Uncertain label은 억지로 평면 Region에 포함되지 않는다.
- [ ] 직각으로 만나는 두 벽을 하나의 평면 Region으로 병합하지 않는다.
- [ ] 같은 의미로 분리된 두 의자는 위치만으로 병합되지 않는다.
- [ ] 가까이 있지만 깊이 단절된 두 표면을 잘못 잇지 않는다.
- [ ] 달리 관측된 같은 평면은 충분한 대응 근거가 있다면 병합될 수 있다.
- [ ] 최적화는 Region 내부 점에만 적용되며 나머지 좌표는 완전 불변이다.
- [ ] 최소 점 수 미달, ray와 평면의 평행, 음수 depth 등의 예외가 처리된다.
- [ ] 평면의 실제 기하 정확도는 외부 GT/hold-out 자료로 평가된다.
- [ ] GT를 Region 추출/threshold tuning에 누설하지 않는다(Oracle 예외 별도 표기).
- [ ] 모든 원본 결과가 덮어쓰기 없이 보관된다.

---

## 14. 구현 기술과 폴더 구조(권장)

### 14.1 공식 실험 수행 저장소 지정

본 연구의 **실험 코드·환경 설정·실행 스크립트·분석 코드 및 경량 결과 기록은 아래 GitHub 저장소 하나에서 관리한다.** MASt3R-SLAM과 SAB3R은 외부 선행연구 구현체로 이용하며, 본 연구의 신규 모듈은 이 저장소의 `src/`에 작성한다.

- **GitHub:** https://github.com/seaeast2/gradresearch_sab3r
- **Clone URL:** `https://github.com/seaeast2/gradresearch_sab3r.git`
- **기본 브랜치:** `main` (2026-11-03 연결된 GitHub에서 확인)
- **로컬 작업 폴더:** `gradresearch_sab3r/`
- **상태:** 2026-11-03 현재 비어 있는 공개 저장소. 본 문서의 하위 디렉터리 구조는 **초기 구성 제안**이며 실제 커밋 및 실행 여부와 구분한다.

최초 체크아웃 명령:

```bash
git clone https://github.com/seaeast2/gradresearch_sab3r.git
cd gradresearch_sab3r
```

비어 있는 저장소라면 첫 커밋 이전에는 소스/실행 명령이 존재하지 않는다. 우선 `README.md`, `.gitignore`, `docs/experiment_plan.md`, `configs/`, `src/`, `scripts/`, `tests/` 등을 추가하여 첫 커밋을 만든다. 작업은 가급적 기능 단위 브랜치에서 진행하고 검증된 변경을 `main`에 병합한다. 최초 문서/설정 초기화는 `main`에서 수행할 수도 있다.

### 14.2 구현 환경과 모듈 분리

**실험 컨트롤 및 전처리:** Python, PyTorch, NumPy, SciPy, Open3D, OpenCV, scikit-image, PyYAML, pytest.

**성능 최적화(필요 시):** FAISS/voxel hash, CUDA 연산, chunked processing. 초기에 CPU+NumPy/Open3D 기준 정답을 만들고 이후 최적화한다. **C++로 옮기는 것은 성능 병목이 확인된 뒤** 수행.

```text
gradresearch_sab3r/                  # 공식 연구 저장소 (예정 구조)
├── README.md                       # 연구 목표, 실행 순서, 결과 요약
├── .gitignore                      # 대용량·임시 데이터 추적 제외
├── docs/
│   ├── experiment_plan.md          # 이 계획서의 저장소 내 사본(업로드 시)
│   ├── data_provenance.md          # 데이터셋·학습 모델 출처/라이선스
│   └── experiment_protocol.md      # 평가 절차 및 실험군 정의
├── configs/
│   ├── env.yaml
│   ├── datasets.yaml
│   ├── segmentation.yaml
│   ├── association.yaml
│   └── refinement.yaml
├── src/
│   ├── export_slam.py
│   ├── infer_sab3r.py
│   ├── align_pixels.py
│   ├── build_regions.py
│   ├── associate_regions.py
│   ├── fit_planes.py
│   ├── refine_rays.py
│   ├── evaluate_geometry.py
│   └── visualize.py
├── tests/
│   ├── test_sim3.py
│   ├── test_mask_alignment.py
│   ├── test_connected_components.py
│   ├── test_region_merge.py
│   ├── test_plane_fit.py
│   └── test_no_outside_motion.py
├── scripts/
│   ├── run_baselines.sh
│   ├── run_ablation.sh
│   └── render_figures.sh
├── third_party/                    # 선택: 외부 저장소는 commit 고정
│   ├── MASt3R-SLAM/               # 별도 clone 또는 git submodule(선택)
│   └── sab-3r/                    # 별도 clone 또는 git submodule(선택)
├── data/                           # 데이터셋 원본: Git 추적 금지
├── checkpoints/                    # 모델 weight: Git 추적 금지
├── cache/                          # 원본 Pointmap + 추론 결과: Git 추적 금지
├── runs/                           # 대용량 run 출력: Git 추적 금지
├── figures/                        # 논문 그림 중 작은 최종본만 선택 커밋
└── results/
    ├── per_scene.csv               # 재현 가능한 요약 표는 선택 커밋
    ├── per_region.csv
    └── summary.csv
```

### 14.3 Git 저장 정책 및 실행 재현성

**버전/환경 기록:** 최초 실험 전 본 저장소의 `git rev-parse HEAD`, MASt3R-SLAM과 SAB3R의 정확한 소스 commit SHA, Python/PyTorch/CUDA 및 기타 의존성 버전을 `runs/<experiment_id>/manifest.yaml` 등에 기록한다. 가능하면 `configs/`에 실험군별 고정 설정을 커밋한다. 후속 재현을 위해 실행 스크립트에 `dataset_id`, `scene_id`, `random_seed`, `checkpoint_id`, `output_path` 등을 명시한다.

**원본 모델 사용:** MASt3R-SLAM과 SAB3R을 수정한 사본으로 불투명하게 복사하지 않는다. 초기에는 독립 폴더/가상환경에서 실행하고, 통합이 필요해지면 `third_party/`에 *고정 커밋의 git submodule*로 연결하거나 `docs/data_provenance.md`에 외부 소스 URL과 SHA를 기록한다. 외부 코드를 수정하면 패치 또는 수정 커밋을 기록한다.

**Git에 포함할 것:** 연구자가 작성한 `src/`, `scripts/`, `tests/`, 작은 YAML/JSON 설정, 문서, 결과 집계 CSV, 라이선스 정보, 가벼운 예시 그림.

**Git에서 제외할 것:** RGB/RGB-D 원본 데이터셋, 대용량 PLY/NPZ, 모든 모델 체크포인트, 캐시, 디버그 영상/로그, 실험별 대용량 출력, 가상환경, 개인정보가 포함될 수 있는 촬영 데이터 및 비밀 키. `.gitignore`로 제외하되 저장소에서 추적 중인 파일은 `.gitignore`만으로 제거되지 않으므로 별도 확인한다. 대용량 산출물은 로컬 또는 별도 연구용 스토리지에 저장한다.

**실험 관리 규칙:** 결과는 날짜가 아니라 고유한 `experiment_id`를 기준으로 보존하고, `B0`~`B4`, `E0`~`E6` 실험군 이름과 연결한다. `runs/<experiment_id>/`에 변경 불가능한 입력 해시/설정/버전과 측정 지표를 남기고, `results/`에는 비교를 위한 경량 집계본을 기록한다. 결과가 나쁘더라도 실패한 실행 기록은 삭제하지 않는다.

**개발 단위와 완료 조건:** 단계별 변경은 `tests/` 회귀 검사와 작은 단위 실험을 통과한 뒤 `main`에 반영한다. SLAM Export, SAB3R mask 정합, Region 생성·병합, 평면 최적화, GT 평가 모듈을 별도 코드로 유지하여 원인 분석과 실험군 재사용을 가능하게 한다.

### 14.4 외부 모델 실행 관계

최초 단계에서는 MASt3R-SLAM, SAB3R을 **서로 독립된 가상환경**에서 구동하고 파일 인터페이스로 연결한다. CUDA/torch 버전이 다를 경우 불필요한 통합 디버깅을 피할 수 있다. SAB3R 공개 문서는 Python 3.11, PyTorch+CUDA 12.1 경로를 제시하고, MASt3R-SLAM도 별도 환경 설치를 안내한다(세부 버전은 README 확인).

---

## 15. 주차별 일정(12주 예시)

| 주차 | 핵심 활동 | 완료 산출물 | 통과 조건 |
|---|---|---|---|
| 1 | 공식 GitHub 저장소 초기화, 선행연구 정리, 환경/데이터 접근 확인 | `gradresearch_sab3r` 초기 커밋, 재현성 문서, dataset license check | 실험 구조와 원본 저장소 실행 가능 |
| 2 | MASt3R-SLAM 소규모 재현, pointmap/pose export | 원본 PLY/NPZ+trajectory | 좌표·RGB 정합 확인 |
| 3 | SAB3R 추론 재현, CLIP 의미 마스크 | 의미 컬러 이미지, 텐서 검증 | 바닥/벽 식별 정성 확인 |
| 4 | Pixel→Pointmap 레이블 전달, 2D connected component | Region별 Pointmap | frame-wise 분할 정상 |
| 5 | 3D 연결/법선·평면 기반 Region split | 영역 연결 그래프 | 직각 벽 오병합 방지 |
| 6 | Frame 간 Region association/Union-Find | Global Region ID | 반복 관측 동일 평면 연결 |
| 7 | 평면 후보 판별/RANSAC, synthetic noise 실험 | 초기 평면 fitting 결과 | GT plane에서 정상 동작 |
| 8 | Ray-constrained depth optimization + safety | 수정 Pointmap/변위 map | 비대상 좌표 불변 |
| 9 | 기준 비교군 B0~B4 실행 | per-scene/per-region 결과 | GT metric 산출 가능 |
| 10 | Ablation, threshold sensitivity | sensitivity figures | 실험 로그/통계 확보 |
| 11 | 실패 사례 분석, 추가 test 장면 | 제한점/결과 표 | 개선·악화 양쪽 검증 |
| 12 | 논문 실험 절 작성/그림 확정 | 논문용 정량표·시각화 | 재현 가능한 최종 package |

**우선순위 재조정:** 구현이 지연되면 3DGS, 실시간 결합, 야외 활주로를 먼저 제외하고 `고정된 SLAM 결과 → floor/wall 분할 → Region 연결 → 평면 최적화 → GT 비교`의 최소 핵심 실험을 완료한다.

---

## 16. 예상 리스크와 대응 방안

| 위험 | 영향 | 대응 방안 |
|---|---|---|
| SAB3R semantic 경계 오분류 | 서로 다른 표면이 병합 | score/margin gate, geometric normal split, Oracle 상한 실험 |
| SAB3R와 SLAM의 tensor/픽셀·크롭 불일치 | 엉뚱한 점에 라벨 | Pixel mapping unit test, RGB overlay 검증 |
| Pose/Scale drift | 동일 표면인데 거리 단절 | 최종 World/Sim(3) 정렬, temporal match 근거, 다른 Scene은 별도 처리 |
| 2D Pixel connectivity가 3D 연결을 보장하지 않음 | 연결 오류 | 깊이 불연속/법선 검사 및 3D 그래프 재검증 |
| 가깝지만 다른 표면 병합 | 최적화 중 심각한 기하 손상 | plane residual / normal / view-consistency hard gate |
| 진짜 평면이 아닌 지형/도로 | 과평탄화 | inlier ratio, residual/곡률 검사, 면 분할 또는 제외 |
| RANSAC 자가평가 편향 | 허위 개선 | GT/held-out metric을 주요 지표로 사용 |
| GT 메시의 부정확성 | 평가 왜곡 | mesh quality 조사, 합성 GT 병행, noisy 영역 제외 표시 |
| Pointmap 누락/추정 점군의 hole | 보정 후 형상 손실 | completeness + F-score 필수, plane 투영만으로 점 추가하지 않음 |
| 경계 gap 증가 | 전체 지도 시각 품질 저하 | boundary band freeze 및 gap 지표 기록, 공동 보정은 향후 과제로 제한 |
| 메모리/추론 시간 과다 | 일정 지연 | Keyframe-only inference, batch 작게, float16/압축 캐시, 장면 축소 |
| 코드/체크포인트 호환성 | 재현 불가 | commit 및 버전 고정, 별도 가상환경 및 파일 인터페이스 |
| 평가에 GT가 새어 들어감 | 학술적 타당성 저해 | GT는 평가/Oracle에만 사용, split·config freeze |

---

## 17. 최소 성공 구현(MVP)과 확장 우선순위

**MVP 1 — 단일 프레임 Geometry Refinement:** GT가 있는 공간의 벽/바닥 하나를 SAB3R로 분할하고, 그 Pointmap에서 선택 점만 제한된 평면 보정하여 GT 오차를 비교. 이때 아직 SLAM temporal merge는 수행하지 않는다.

**MVP 2 — 다중 Keyframe Static Map:** MASt3R-SLAM의 최종 World Pointmap에 의미 mask를 합성하고 2개 이상 Keyframe의 같은 평면 Region을 병합. 동일 평면 중복 관측을 검증한다.

**MVP 3 — 논문 핵심:** B0 원본, B1 geometry-only, B2 semantic no-merge, B3 semantic temporal-merge를 실행하고 **GT 기준 대상 평면 오차**를 비교한다. B4 Oracle은 가능할 때 진행한다.

**다음 실행 확장:** 위 MVP2/MVP3를 위한 연속 Keyframe tag/Region 병합 및 오차 유도 국소 보정을 E1a–E6a로 구체화했다. 단계 정의와 안전 gate는 이 절 앞의 “다음 실행 확장 — 연속 Keyframe의 temporal Region 병합 및 오차 유도 보정”을 따른다.

**선택 확장:** semantic confidence calibration, adaptive local planar patches, 3DGS 후속 비교.

---

## 18. 예상 학술적 기여와 한계 기술 문안

### 18.1 기대 기여(검증 후에만 확정 표현)

1. 연속 영상 기반 SLAM Pointmap에 **의미 특징 및 3D 연결성을 결합한 Region-level 표현**을 구축하는 절차.
2. 기존 SLAM 자세를 고정한 채 **평면 Region에만 기하학적 제약을 적용하는 국부 보정 모듈**.
3. 의미 정보, 시간적 Region 연결, 강건 평면 추정의 효과를 **동일한 기존 Pointmap 위에서 정량 분리**한 실험.

### 18.2 연구 한계(논문용 초안)

본 연구는 기존 단안 Dense SLAM이 추정한 카메라 자세와 전역 좌표계를 고정한 채, 의미 기반으로 분할된 평면 영역의 Pointmap을 국부적으로 정제한다. 이 과정에서 서로 다른 영역의 접합 경계와 전체 지도의 기하 정합성을 동시에 최적화하지 않는다. 따라서 국부 평면 오차가 감소하더라도 인접한 벽·바닥 등의 상대 정합성이 완전히 보장되지는 않는다. 또한 의미 분할 정확도와 원본 SLAM 자세의 품질이 최적화 성능에 영향을 미치며, 곡면·비평면·동적 객체에 대한 일반화는 다루지 않는다. 후속 연구에서는 Region 간 경계 제약과 SLAM Pose 및 Geometry의 공동 최적화를 통합하는 방법을 검토한다.

---

## 19. 결과 해석의 결정표

| 관찰 결과 | 허용되는 결론 | 피해야 할 결론 |
|---|---|---|
| B3가 B0보다 GT 오차 감소 | 제안 후처리가 해당 평면 Region의 기하 오차를 감소 | 전역 SLAM 지도가 정확해졌음 |
| B3가 B1보다 유리 | 동일 평면 최적화 조건에서 semantic-guided grouping의 추가 이점 가능 | 모든 의미 분할 방식보다 우수 |
| B3가 B2보다 유리 | Temporal Region association이 이 데이터에 효과 | 영구적인 객체 추적을 해결 |
| B4만 크게 개선 | Region 보정 잠재력은 있으나 SAB3R mask가 병목 | 현재 모델만으로 충분히 성공 |
| self-plane 오차만 감소, GT 오차 증가 | 평탄화는 됐지만 실제 기하 정확도 악화 | 정확도가 개선됨 |
| GT RMSE 감소, boundary gap 증가 | 국부 정제와 경계 손상 사이 trade-off 존재 | 전체 지도가 문제 없음 |
| 3DGS 실험 미수행 | Pointmap geometry 논문으로 제한 | Gaussian ghost 감소가 실증됨 |

---

## 20. 선행연구·공개 구현 및 데이터 출처

### 주요 첨부 논문

1. Chen et al., **SAB3R: Semantic-Augmented Backbone in 3D Reconstruction**, 2025. 관련 내용: §3 Map and Locate, §4 Method, Fig. 3, §5 Experiments.
2. Murai et al., **MASt3R-SLAM: Real-Time Dense SLAM with 3D Reconstruction Priors**, CVPR 2025. 관련 내용: §3.1 `Sim(3)`, §3.3 `Tracking and Pointmap Fusion`, §3.4 loop closure, §3.5 backend.
3. Leroy et al., **Grounding Image Matching in 3D with MASt3R**, 2024. 관련 내용: pointmap 및 learned descriptor matching.
4. Wang et al., **DUSt3R: Geometric 3D Vision Made Easy**, 2024. 관련 내용: pixel-aligned pointmap과 다중 시점 정렬.

### 구현(2026-11-03 기준 공개 페이지 확인)

- **본 연구 공식 실험 저장소:** https://github.com/seaeast2/gradresearch_sab3r (현재 빈 저장소, 코드는 본 계획에 따라 생성 예정)
- SAB3R: https://github.com/UVA-Computer-Vision-Lab/sab-3r
- SAB3R project: https://uva-computer-vision-lab.github.io/sab3r/
- MASt3R-SLAM: https://github.com/rmurai0610/MASt3R-SLAM
- MASt3R-SLAM project: https://edexheim.github.io/mast3r-slam/

### 데이터셋

- Replica: https://github.com/facebookresearch/Replica-Dataset
- ScanNet: https://www.scan-net.org/ScanNet/
- ScanNet++ docs: https://scannetpp.mlsg.cit.tum.de/scannetpp/documentation
- ETH3D-SLAM: https://eth3d.ethz.ch/slam_documentation

**참고:** ScanNet 이용은 별도 이용약관 승인에 따를 수 있으며, ScanNet++ 전체 데이터는 매우 크므로 일부 Scene만 받는 데이터 준비가 필요하다. SAB3R·MASt3R 기반 모델의 라이선스(예: CC BY-NC-SA 4.0)를 확인하고 비상업적 학술 연구 및 결과 재배포 조건을 준수한다.

---

## 21. 지도교수 면담용 간략 요약

**연구 문제:** 기존 단안 Dense SLAM이 생성한 Pointmap의 국부적 기하 오차를 전체 Pose 재최적화 없이 개선할 수 있는가?

**핵심 아이디어:** SAB3R의 open-vocabulary semantic feature로 바닥·벽 등의 점군을 분류하고, 공간 연결성과 다중 시점 대응 관계를 결합하여 독립적으로 처리 가능한 Region을 구성한다. 기하적으로 평면성이 확인된 Region에 한해 MASt3R-SLAM의 원본 Pointmap을 국부적으로 보정한다.

**실험 핵심:** MASt3R-SLAM 출력 Pointmap/카메라 Pose를 고정하고, 원본·기하 전용·의미 기반 단일 프레임·의미 기반 다중 프레임 병합·GT 의미 분할 상한 실험을 같은 데이터셋에서 비교한다. 결과는 자기 평면 residual이 아니라 독립 GT mesh 기준 정확도와 이상점 비율을 중심으로 검증한다.

**제외 범위:** 다른 Region의 기하 재배치와의 공동 조정, SLAM Pose 재최적화, 실시간 융합, 복잡한 비평면 객체의 최적화는 후속 연구로 남긴다.

**기대 성과:** 의미 기반 Region 구성이 단순 기하 분할 대비 개선 효과를 갖는 조건과 한계, 평면 Region 정제의 기하 오차 감소 효과 및 경계 손상 trade-off를 정량적으로 제시한다.

**실험 구현 위치:** `https://github.com/seaeast2/gradresearch_sab3r.git`에서 연구 코드·실험 설정·재현성 문서를 통합 관리한다. 외부 모델 및 데이터셋의 원본과 대용량 산출물은 별도로 관리하고 정확한 버전/출처를 기록한다.
