#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 3 ]]; then
  echo "usage: $0 RUN_ID DATASET_PATH UPSTREAM_CONFIG [--calib CALIB_YAML] [--python PYTHON]" >&2
  exit 2
fi
task_run_id="$1"; task_dataset="$2"; task_config="$3"; shift 3
bash "$task_root/scripts/run_semantic_region_stage.sh" \
  "$task_run_id" E1_slam_export \
  python "$task_root/scripts/run_slam_export.py" \
    --dataset "$task_dataset" --config "$task_config" "$@"
