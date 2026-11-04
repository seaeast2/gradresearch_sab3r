#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 5 || $# -gt 6 ]]; then
  echo "usage: $0 RUN_ID SOURCE_RGB_DIR UPSTREAM_CONFIG KEYFRAME_BUFFER MAST3R_PYTHON [CALIB_YAML]" >&2
  exit 2
fi
task_run_id="$1"; shift
bash "$task_root/scripts/run_semantic_region_stage.sh" \
  "$task_run_id" E1a_multikeyframe_slam_export \
  bash "$task_root/scripts/execute_e1a_multikeyframe_slam_export.sh" "$@"
