#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 1 ]]; then
  echo "usage: $0 RUN_ID" >&2
  exit 2
fi
task_run_id="$1"
bash "$task_root/scripts/run_semantic_region_stage.sh" \
  "$task_run_id" E7_outdoor_transfer \
  python3 "$task_root/scripts/run_e7_outdoor_transfer.py" \
  --run-dir "$task_root/runs/semantic_region_pointmap/$task_run_id"
