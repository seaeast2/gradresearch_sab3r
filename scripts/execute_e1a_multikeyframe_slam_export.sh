#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 || $# -gt 5 ]]; then
  echo "usage: $0 SOURCE_RGB_DIR UPSTREAM_CONFIG KEYFRAME_BUFFER MAST3R_PYTHON [CALIB_YAML]" >&2
  exit 2
fi
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
task_source="$1"
task_config="$2"
task_buffer="$3"
task_python="$4"
task_calib="${5:-}"
if [[ "${EXPERIMENT_STAGE:-}" != "E1a_multikeyframe_slam_export" || -z "${EXPERIMENT_ARTIFACTS_DIR:-}" ]]; then
  echo "invoke through run_semantic_region_stage.sh for E1a_multikeyframe_slam_export" >&2
  exit 2
fi

task_staged_rgb="$EXPERIMENT_ARTIFACTS_DIR/input_rgb"
"$task_python" "$task_root/scripts/prepare_e1a_sequence.py" \
  "$task_source" "$task_staged_rgb" --minimum-frames 2

task_args=(
  --stage-name E1a_multikeyframe_slam_export
  --dataset "$task_staged_rgb"
  --config "$task_config"
  --keyframe-buffer "$task_buffer"
  --python "$task_python"
)
if [[ -n "$task_calib" ]]; then
  task_args+=(--calib "$task_calib")
fi
python3 "$task_root/scripts/run_slam_export.py" "${task_args[@]}"

python3 - "$EXPERIMENT_ARTIFACTS_DIR/pointmaps/export_manifest.json" <<'PY'
import json, pathlib, sys
manifest = json.loads(pathlib.Path(sys.argv[1]).read_text())
count = manifest.get("keyframe_count", 0)
if count < 2:
    raise SystemExit(f"E1a requires at least 2 exported Keyframes; got {count}. Artifacts are retained as a failed attempt.")
print(f"E1a multi-Keyframe gate passed: {count} Keyframes")
PY
