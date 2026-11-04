#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 5 ]]; then
  echo "usage: $0 OUTPUT_RUN_ID E1_SOURCE_RUN_ID E2_SOURCE_RUN_ID E4_SOURCE_RUN_ID E0A_SOURCE_RUN_ID" >&2
  exit 2
fi
task_run_id="$1"
task_e1="$task_root/runs/semantic_region_pointmap/$2/stages/E1_slam_export/artifacts"
task_e2="$task_root/runs/semantic_region_pointmap/$3/stages/E2_sab3r_semantics/artifacts"
task_e4="$task_root/runs/semantic_region_pointmap/$4/stages/E4_geometry_refinement/artifacts"
task_preflight="$task_root/runs/semantic_region_pointmap/$5/stages/E0a_preflight/artifacts"
task_manifest="$task_e1/pointmaps/export_manifest.json"
task_scores="$task_e2/semantic_scores.npz"
task_refinement="$task_e4/refinement.npz"
task_source_manifest="$task_preflight/replica_office0_rgb30/source_manifest.json"
task_dataset_root="/home/hlee221212/works/gradresearch/data/Replica/office0/results"
task_camera_params="/home/hlee221212/works/gradresearch/data/Replica/cam_params.json"
if [[ ! -f "$task_manifest" || ! -f "$task_scores" || ! -f "$task_refinement" || ! -f "$task_source_manifest" ]]; then
  echo "required frozen E1/E2/E4/E0a input artifact is missing" >&2
  exit 2
fi
task_pointmap="$(.venvs/sab3r/bin/python - "$task_manifest" <<'PY'
import json, pathlib, sys
manifest = pathlib.Path(sys.argv[1])
record = json.loads(manifest.read_text())["keyframes"][0]
print(manifest.parent / record["file"])
PY
)"

bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E5_gt_evaluation \
  "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/evaluate_e5_gt.py" \
  --pointmap "$task_pointmap" \
  --semantic-scores "$task_scores" \
  --refinement "$task_refinement" \
  --source-manifest "$task_source_manifest" \
  --camera-params "$task_camera_params" \
  --depth-root "$task_dataset_root" \
  --config "$task_root/configs/e5_gt_evaluation.json" \
  --output "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E5_gt_evaluation/artifacts"
