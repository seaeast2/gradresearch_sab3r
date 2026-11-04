#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 3 ]]; then
  echo "usage: $0 OUTPUT_RUN_ID E1A_SOURCE_RUN_ID E2A_SOURCE_RUN_ID" >&2
  exit 2
fi
task_run_id="$1"
task_e1a="$task_root/runs/semantic_region_pointmap/$2/stages/E1a_multikeyframe_slam_export/artifacts"
task_e2a="$task_root/runs/semantic_region_pointmap/$3/stages/E2a_multikeyframe_semantics/artifacts"
if [[ ! -f "$task_e1a/pointmaps/export_manifest.json" || ! -f "$task_e2a/keyframes_manifest.json" ]]; then
  echo "required completed E1a/E2a artifacts are missing" >&2
  exit 2
fi
bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E3a_temporal_region_association \
  "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/build_e3a_temporal_regions.py" \
  --e1a-artifacts "$task_e1a" \
  --e2a-artifacts "$task_e2a" \
  --config "$task_root/configs/e3a_temporal_region_association.json" \
  --output "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E3a_temporal_region_association/artifacts"
