#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 11 ]]; then
  echo "usage: $0 OUTPUT_RUN_ID E1A_RUN E2A_RUN E3A_RUN E4A_RUN SOURCE_MANIFEST CAMERA_PARAMS DEPTH_ROOT TRAJECTORY SCENE_ID SCENE_SPLIT" >&2
  exit 2
fi
task_run_id="$1"; task_e1a_id="$2"; task_e2a_id="$3"; task_e3a_id="$4"; task_e4a_id="$5"
task_source_manifest="$6"; task_camera="$7"; task_depth_root="$8"; task_trajectory="$9"
task_scene_id="${10}"; task_scene_split="${11}"
task_e1a="$task_root/runs/semantic_region_pointmap/$task_e1a_id/stages/E1a_multikeyframe_slam_export/artifacts"
task_e2a="$task_root/runs/semantic_region_pointmap/$task_e2a_id/stages/E2a_multikeyframe_semantics/artifacts"
task_e3a="$task_root/runs/semantic_region_pointmap/$task_e3a_id/stages/E3a_temporal_region_association/artifacts"
task_e4a="$task_root/runs/semantic_region_pointmap/$task_e4a_id/stages/E4a_error_guided_local_refinement/artifacts"
for required in "$task_e1a/pointmaps/export_manifest.json" "$task_e2a/keyframes_manifest.json" "$task_e3a/temporal_regions.json" "$task_e4a/refinement_summary.json" "$task_source_manifest" "$task_camera" "$task_trajectory"; do
  if [[ ! -f "$required" ]]; then echo "required input is missing: $required" >&2; exit 2; fi
done
if [[ ! -d "$task_depth_root" ]]; then echo "depth root is missing: $task_depth_root" >&2; exit 2; fi
bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E5a_multikeyframe_gt_evaluation \
  "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/evaluate_e5a_multikeyframe.py" \
  --e1a-artifacts "$task_e1a" --e2a-artifacts "$task_e2a" --e3a-artifacts "$task_e3a" --e4a-artifacts "$task_e4a" \
  --source-manifest "$task_source_manifest" --camera-params "$task_camera" --depth-root "$task_depth_root" --trajectory "$task_trajectory" \
  --scene-id "$task_scene_id" --scene-split "$task_scene_split" \
  --config "$task_root/configs/e5a_multikeyframe_gt_evaluation.json" \
  --output "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E5a_multikeyframe_gt_evaluation/artifacts"
