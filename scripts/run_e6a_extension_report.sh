#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 2 ]]; then
  echo "usage: $0 OUTPUT_RUN_ID --primary-run RUN_ID [--primary-run RUN_ID ...] [--support-run RUN_ID ...] [--validation-metrics-run RUN_ID ...] [--ablation-run RUN_ID ...] [--attempt-run RUN_ID ...]" >&2
  exit 2
fi
task_run_id="$1"; shift
bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E6a_extension_report \
  "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/build_e6a_extension_report.py" \
  "$@" --output "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E6a_extension_report/artifacts"
