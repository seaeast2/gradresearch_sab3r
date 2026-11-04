#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 2 ]]; then
  echo "usage: $0 OUTPUT_RUN_ID E1A_SOURCE_RUN_ID" >&2
  exit 2
fi
task_run_id="$1"
task_e1a="$task_root/runs/semantic_region_pointmap/$2/stages/E1a_multikeyframe_slam_export/artifacts"
task_e1a_manifest="$task_e1a/pointmaps/export_manifest.json"
task_e1a_stage_manifest="$(dirname "$task_e1a")/manifest.json"
task_checkpoint="$(find "$task_root/third_party/sab-3r/checkpoints/hf-home/hub/models--uva-cv-lab--SAB3R/snapshots" -path '*/demo_ckpt/base/base.pt' -print -quit)"
if [[ ! -f "$task_e1a_manifest" || -z "$task_checkpoint" ]]; then
  echo "completed E1a export or SAB3R checkpoint is missing" >&2
  exit 2
fi
if [[ "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$task_e1a_stage_manifest")" != completed ]]; then
  echo "E2a requires a completed E1a stage" >&2
  exit 2
fi

export EXPERIMENT_EXECUTION_CONTEXT=host
bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E2a_multikeyframe_semantics \
  env PYTHONPATH="$task_root/third_party/sab-3r:$task_root/third_party/FeatUp" \
      MPLCONFIGDIR=/tmp/sab3r-mpl-cache \
      "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/run_e2a_multikeyframe.py" \
      --e1a-artifacts "$task_e1a" \
      --repo "$task_root/third_party/sab-3r" \
      --featup "$task_root/third_party/FeatUp" \
      --checkpoint "$task_checkpoint" \
      --output "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E2a_multikeyframe_semantics/artifacts"
