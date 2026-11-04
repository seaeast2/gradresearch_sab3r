# E1a — Replica office0 120-frame multi-Keyframe export

**판정: 다중 Keyframe export gate 통과.** Replica office0의 연속 RGB 120장을 host GPU에서 MASt3R-SLAM에 입력해 최종 Keyframe pointmap 2개를 export했습니다. 이 결과는 E1a의 Keyframe 수 gate를 통과하지만, 반복 관측된 표면의 대응·병합 여부는 E3a에서 확인해야 합니다.

## 실행 기록

- Run: `E1a-multikeyframe-20261104-002`
- Input: `/home/hlee221212/works/gradresearch/data/Replica/office0/results/frame*.jpg` 120장. Depth PNG는 RGB 입력에서 제외했습니다.
- MASt3R-SLAM: commit `e6f4e3d474fad0e11f561482012be864ba8c3f17`, clean checkout
- Python 3.11.18, PyTorch 2.7.1+cu128, CUDA 12.8
- GPU: NVIDIA GeForce RTX 5060, 8151 MiB; driver 595.99.02
- Config는 upstream `config/base.yaml`을 상속하고 `single_thread: true` 및 backend CUDA cache release를 적용했습니다. Keyframe buffer는 32입니다.
- 전체 입력 RGB의 source/staged SHA-256 및 순번 대응은 [source manifest](../../../runs/semantic_region_pointmap/E1a-multikeyframe-20261104-002/stages/E0a_preflight/artifacts/input_rgb/source_manifest.json)에 저장했습니다.
- 실행 시간 28.93초. 200ms 간격 `nvidia-smi` host-wide memory 샘플 peak 4,150 MiB; 이는 프로세스 단독 VRAM 측정이 아닙니다.

## 결과

| Keyframe | 원본 frame ID | Timestamp (s) | Grid | 유효 pixel | Fusion/update count | NPZ SHA-256 |
|---:|---:|---:|---:|---:|---:|---|
| 0 | 0 | 0.0 | 288×512 | 147,456 | 83 / 83 | `402f7092c967d0a65078bd0c2ab7008a3a79b16d31ea2d0e2a71eb85d08dc84c` |
| 1 | 82 | 2.7333333 | 288×512 | 147,456 | 38 / 38 | `10a2bcff652cf4d807656d9a0f38fb164ad2151c377454d4f35249fef1b3f3de` |

`keyframe_count=2`로 E1a의 최소 Keyframe 수 조건을 만족했습니다. 두 pointmap, RGB, pose, confidence, frame/timestamp, fusion count는 [export manifest](../../../runs/semantic_region_pointmap/E1a-multikeyframe-20261104-002/stages/E1a_multikeyframe_slam_export/artifacts/pointmaps/export_manifest.json)와 [stage manifest](../../../runs/semantic_region_pointmap/E1a-multikeyframe-20261104-002/stages/E1a_multikeyframe_slam_export/manifest.json)에 기록했습니다.

## 실패 기록과 범위

첫 시도 `E1a-multikeyframe-20261104-001`은 MASt3R-SLAM image-sequence loader가 PNG만 읽는 점을 놓쳐 추론 전에 실패했습니다. 코드를 PNG 입력으로 고친 뒤 새 run `...-002`에서 재실행했고, 실패 시도는 이전 run에 보존했습니다.

두 Keyframe이 같은 표면을 실제로 관측하는지, temporal association이 맞는지, 여러 scene에서 결과가 재현되는지는 이 단계만으로 판정하지 않습니다. 다음 E2a에서 두 Keyframe 각각 SAB3R tag를 만들고 E3a에서 대응점과 기하 근거를 확인합니다.
