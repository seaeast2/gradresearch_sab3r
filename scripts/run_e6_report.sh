#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 4 ]]; then
  echo "usage: $0 RESULT_RUN_ID E1_SOURCE_RUN_ID E2_SOURCE_RUN_ID E0A_SOURCE_RUN_ID" >&2
  exit 2
fi
task_run_id="$1"
task_docs="$task_root/docs/experiments/E6_report/E6-${task_run_id}.md"

bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E6_report \
  python3 "$task_root/scripts/generate_e6_report.py" \
  --run-id "$task_run_id" \
  --e1-run-id "$2" \
  --e2-run-id "$3" \
  --e0a-run-id "$4" \
  --output-dir "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E6_report/artifacts" \
  --docs-output "$task_docs"
