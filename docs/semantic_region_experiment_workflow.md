# Semantic Region Pointmap 실험 실행 흐름

이 저장소는 `/home/hlee221212/works/gradresearch`의 실험 운영 방식에서 **실험 ID별 결과 격리, 설정/환경 스냅샷, 기존 결과 덮어쓰기 방지**를 가져옵니다. 원본 데이터·체크포인트·외부 모델 코드와 실행 결과는 이 연구 저장소 밖 또는 Git 미추적 경로에서 관리합니다.

## 환경 경계

- MASt3R-SLAM과 SAB3R은 서로 다른 Python 가상환경에서 설치·실행합니다. 모델 저장소를 수정하거나 두 환경을 합치지 않습니다.
- `bash scripts/bootstrap_model_envs.sh`는 `.venvs/mast3r-slam`과 `.venvs/sab3r`를 생성하지만, 패키지는 설치하지 않습니다. CUDA 호환성은 두 upstream의 고정 버전을 확인한 뒤 각 환경에 따로 설치합니다.
- `MAST3R_SLAM_ROOT`, `SAB3R_ROOT` 환경 변수에 각 외부 체크아웃 경로를 지정합니다.
- 데이터 경로와 체크포인트 경로는 공유 설정에 박아 넣지 않습니다. 실행 명령이 받도록 하고, run config에 실제 식별자와 해시를 기록합니다.
- `scripts/experiment.py`는 실험 디렉터리와 provenance 기록을 관리합니다. E1은 `scripts/run_slam_export.sh`로 고정한 MASt3R-SLAM checkout을 실행하며, E2–E6의 model/analysis 명령은 아직 연결되지 않았습니다.

### GPU/CUDA 확인 위치

Codex 샌드박스 안에서는 `nvidia-smi`, CUDA 장치 조회, GPU tensor 연산이 호스트 GPU를 제대로 보여주지 않을 수 있습니다. 샌드박스에서 `nvidia-smi`가 실패하거나 `torch.cuda.is_available()`가 `false`여도 **호스트 GPU가 없다는 뜻으로 해석하지 않습니다.** 이러한 값은 실행 문맥과 함께 `sandbox` 관측으로만 기록합니다.

실제 GPU 이름·VRAM·driver 확인, CUDA smoke run, MASt3R-SLAM/SAB3R GPU 추론은 **샌드박스 밖의 호스트 터미널 또는 GPU가 연결된 실행 환경에서 수행**합니다. 호스트에서 새 E0 run을 만들 때는 `EXPERIMENT_EXECUTION_CONTEXT=host`를 지정해 기록에 문맥을 남깁니다. 이미 완료된 E0 결과를 수정하지 말고 새 run ID를 사용합니다.

```bash
export EXPERIMENT_EXECUTION_CONTEXT=host
export MAST3R_SLAM_ROOT=/path/to/MASt3R-SLAM
export MAST3R_SLAM_PYTHON=/path/to/mast3r-python
export SAB3R_ROOT=/path/to/sab-3r
export SAB3R_PYTHON=/path/to/sab3r-python
python3 scripts/experiment.py init --run-id E0-host-20261104-001
python3 scripts/experiment.py capture-env E0-host-20261104-001
```

호스트에서 실행할 때마다 run ID를 새 값으로 바꿉니다.

이 명령이 sandbox 안에서 실행되면 `host`라고 임의 지정하지 않습니다. 실행 위치를 바꾸지 못한 경우에는 `sandbox` 결과로 남기고 실제 GPU probe는 보류합니다.

## 최초 실행

```bash
cd /home/hlee221212/works/gradresearch_sab3r
bash scripts/bootstrap_model_envs.sh
export MAST3R_SLAM_ROOT=/path/to/MASt3R-SLAM
export SAB3R_ROOT=/path/to/sab-3r
python scripts/experiment.py init --run-id pilot-replica-001
python scripts/experiment.py capture-env pilot-replica-001
python scripts/experiment.py status pilot-replica-001
```

생성 경로는 `runs/semantic_region_pointmap/<run-id>/`이며, 기존 run ID가 있으면 초기화를 거부합니다. 실행 ID는 데이터 split과 설정 조합마다 새로 부여합니다. 재실행 결과를 덮어쓰지 않고 새 run ID를 사용합니다.

## 단계와 산출물 경계

```text
runs/semantic_region_pointmap/<run-id>/
├── config.json
├── run.json
└── stages/
    ├── E0_environment/{manifest.json,artifacts/,logs/}
    ├── E0a_preflight/{manifest.json,artifacts/,logs/}
    ├── E1_slam_export/{manifest.json,artifacts/,logs/}
    ├── E2_sab3r_semantics/{manifest.json,artifacts/,logs/}
    ├── E3_region_build/{manifest.json,artifacts/,logs/}
    ├── E4_geometry_refinement/{manifest.json,artifacts/,logs/}
    ├── E5_gt_evaluation/{manifest.json,artifacts/,logs/}
    └── E6_report/{manifest.json,artifacts/,logs/}
```

| 단계 | 입력 | 독립 산출물 예시 | 진행 게이트 |
|---|---|---|---|
| E0 환경 | 설정, 외부 체크아웃 | 환경·GPU·commit 정보 | 서로 다른 모델 환경과 버전 기록 확인 |
| E0a E1 사전 점검 | 호스트 GPU, 고정 upstream, 모델 Python, 짧은 RGB 입력 | `preflight.json`, 입력 hash manifest | GPU/CUDA, import, checkpoint, config, 데이터 경로 확인; 추론은 수행하지 않음 |
| E1 SLAM export | RGB 시퀀스 | 최종 Pose, Pointmap, confidence, pixel mapping | RGB overlay, 좌표계, Sim(3) scale 검증 |
| E2 SAB3R 의미 | Keyframe RGB | 원본 semantic score/mask, 색상 overlay | 출력 해상도 및 crop/resize 정합 확인 |
| E3 Region | E1 export + E2 mask | frame-wise 및 global Region, merge 기록 | 깊이/법선 분리, 오병합 사례 기록 |
| E4 보정 | Region + 고정 Pointmap | 보정 Pointmap, displacement, 실패 사유 | 대상 외 점 불변, 변위 제한 확인 |
| E5 GT 평가 | 원본/보정 Pointmap + 평가 전용 GT | per-region 및 per-scene 지표 | split/config 고정, GT 입력 누설 방지 |
| E6 보고 | 지표·로그·실패 사례 | 표·그림·결론 초안 | 모든 run과 입력 hash 추적 가능 |

실제 E0a 점검은 [E0a 사전 점검 결과](experiments/E0a_preflight/E0a-readiness-20261104-002.md)에 기록했습니다. 통과 판정은 사전 환경 확인이며 SLAM 추론 성공을 의미하지 않습니다.

실제 E1 실행 및 export 확인은 [E1 결과 보고서](experiments/E1_slam_export/E1-replica-office0-pilot.md)에 기록했습니다.

공통 runner는 그 단계의 `logs/command.log`에 로그를 남기고 상태를 기록하며, 해당 단계의 `artifacts/`만 출력 경로로 사용합니다. E1 전용 runner는 MASt3R-SLAM CLI와 배열 export를 연결합니다. E2–E6은 각 전용 실행기를 추가해야 합니다.

```bash
bash scripts/run_slam_export.sh \\
  E0a-readiness-20261104-002 \\
  runs/semantic_region_pointmap/E0a-readiness-20261104-002/stages/E0a_preflight/artifacts/replica_office0_rgb30 \\
  "$MAST3R_SLAM_ROOT/config/base.yaml" \\
  --python "$MAST3R_SLAM_PYTHON" --keyframe-buffer 32
```

단계 완료 후 manifest에 산출물 SHA-256이 기록됩니다. 단계는 성공·실패 모두 같은 run에서 재실행할 수 없으므로 변경/재실험은 새 run ID로 분리합니다. 실패 시 원인과 부분 산출물을 보존합니다.

### E1 — 실제 SLAM export 실행

MASt3R-SLAM 공식 실행은 최종 trajectory, confidence threshold 기반 PLY, Keyframe RGB 이미지를 저장하지만, 이 연구의 픽셀 단위 처리에 필요한 원본 per-keyframe pointmap/confidence 배열은 기본 산출물에 포함하지 않습니다. [공식 `main.py`](https://github.com/rmurai0610/MASt3R-SLAM/blob/main/main.py)와 [`evaluate.py`](https://github.com/rmurai0610/MASt3R-SLAM/blob/main/mast3r_slam/evaluate.py)를 기준으로 `scripts/run_slam_export.py`는 upstream을 변경하지 않고 stage 내부에 launcher 사본을 만들어 마지막 프레임 처리 직후 배열 export hook을 넣습니다.

```bash
export MAST3R_SLAM_ROOT=/path/to/pinned/MASt3R-SLAM
bash scripts/run_slam_export.sh \\
  pilot-replica-001 \\
  /path/to/short_rgb_sequence \\
  "$MAST3R_SLAM_ROOT/config/base.yaml"
```

출력은 `stages/E1_slam_export/artifacts/` 안에만 생깁니다. `pointmaps/keyframes/*.npz`에는 픽셀 정렬 RGB, local/world pointmap, 평균·누적 confidence, 유효 mask, raw Sim(3), frame/timestamp, fusion/update count를 보존하고, `export_manifest.json`에 좌표계와 파일 hash를 기록합니다. upstream PLY/trajectory/Keyframe 이미지는 `upstream_output/` 아래 둡니다. export hook은 기본 calibrated PLY 저장이 canonical pointmap을 ray에 투영해 바꾸기 전에 원본 점을 저장합니다. 좌표는 upstream `T_WC.act(X_canon)` 규약을 따릅니다.

실행기는 입력 config를 상속하는 run 전용 config를 만들어 **`single_thread: true`**를 강제합니다. 각 최적화 작업이 끝난 뒤 다음 frame으로 넘어가며, 마지막 sequence에서도 backend queue가 빌 때까지 기다린 후 export합니다. 비동기 multi-thread 결과와 섞이지 않도록 합니다. 원본 config와 run 전용 config hash, upstream `main.py` SHA, 생성 launcher SHA를 기록합니다.

## 환경 준비 순서

1. 외부 저장소를 체크아웃하고 사용할 commit을 고정합니다.
2. 각 upstream README의 권장 Python/PyTorch/CUDA 조합으로 독립 가상환경을 만듭니다.
3. 환경변수에 저장소 경로를 지정하고 `init`, `capture-env`를 수행합니다.
4. 소형 시퀀스로 E1만 수행합니다. export 형식과 RGB/기하 정합을 확인하기 전에는 후속 단계를 시작하지 않습니다.
5. 검증된 동일 E1 산출물을 고정 입력으로 E2 이후 비교군에 재사용합니다. 모든 비교군은 별도의 run ID와 stage 경로를 씁니다.

환경 자동 설치는 upstream별 CUDA/의존성 조합을 확인한 뒤 별도 설치 스크립트로 추가합니다. E1의 MASt3R-SLAM export는 연결·실행했고, E2 이후의 SAB3R 추론과 Region/geometry/evaluation 코드는 아직 연결하지 않았습니다.
