#!/usr/bin/env bash
# Run one supplied command inside one run/stage, with logs and artifacts isolated.
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 3 ]]; then
  echo "usage: $0 RUN_ID STAGE command [args...]" >&2
  exit 2
fi
task_run_id="$1"; task_stage="$2"; shift 2
task_run="$task_root/runs/semantic_region_pointmap/$task_run_id"
task_stage_dir="$task_run/stages/$task_stage"
if [[ ! -f "$task_run/run.json" || ! -d "$task_stage_dir/artifacts" ]]; then
  echo "unknown run or stage: $task_run_id / $task_stage" >&2
  exit 2
fi
task_manifest="$task_stage_dir/manifest.json"
task_status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$task_manifest")"
if [[ "$task_status" != planned ]]; then
  echo "stage can only run once (status '$task_status'); create a new run ID to preserve this attempt" >&2
  exit 2
fi
python3 "$task_root/scripts/experiment.py" stage "$task_run_id" "$task_stage" running
set +e
(cd "$task_root" && \
  EXPERIMENT_RUN_ID="$task_run_id" \
  EXPERIMENT_RUN_DIR="$task_run" \
  EXPERIMENT_STAGE="$task_stage" \
  EXPERIMENT_STAGE_DIR="$task_stage_dir" \
  EXPERIMENT_ARTIFACTS_DIR="$task_stage_dir/artifacts" \
  "$@") > >(tee "$task_stage_dir/logs/command.log") 2>&1
task_exit=$?
set -e
if [[ $task_exit -eq 0 ]]; then
  python3 "$task_root/scripts/experiment.py" stage "$task_run_id" "$task_stage" completed
else
  python3 "$task_root/scripts/experiment.py" stage "$task_run_id" "$task_stage" failed --note "command exited with status $task_exit"
fi
exit "$task_exit"
