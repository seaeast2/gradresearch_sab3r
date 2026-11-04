#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 4 ]]; then
  echo "usage: $0 OUTPUT_RUN_ID E1A_SOURCE_RUN_ID E2A_SOURCE_RUN_ID E3A_SOURCE_RUN_ID" >&2
  exit 2
fi
task_run_id="$1"; task_e1a_id="$2"; task_e2a_id="$3"; task_e3a_id="$4"
task_e1a="$task_root/runs/semantic_region_pointmap/$task_e1a_id/stages/E1a_multikeyframe_slam_export/artifacts"
task_e2a="$task_root/runs/semantic_region_pointmap/$task_e2a_id/stages/E2a_multikeyframe_semantics/artifacts"
task_e3a="$task_root/runs/semantic_region_pointmap/$task_e3a_id/stages/E3a_temporal_region_association/artifacts"
for required in "$task_e1a/pointmaps/export_manifest.json" "$task_e2a/keyframes_manifest.json" "$task_e3a/temporal_regions.json"; do
  if [[ ! -f "$required" ]]; then
    echo "required source artifact is missing: $required" >&2
    exit 2
  fi
done
bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E4a_error_guided_local_refinement \
  "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/refine_e4a_temporal_regions.py" \
  --e1a-artifacts "$task_e1a" \
  --e2a-artifacts "$task_e2a" \
  --e3a-artifacts "$task_e3a" \
  --config "$task_root/configs/e4a_error_guided_refinement.json" \
  --output "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E4a_error_guided_local_refinement/artifacts"
