#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 3 ]]; then
  echo "usage: $0 OUTPUT_RUN_ID E1_SOURCE_RUN_ID E3_SOURCE_RUN_ID" >&2
  exit 2
fi
task_run_id="$1"
task_e1_source="$2"
task_e3_source="$3"
task_e1="$task_root/runs/semantic_region_pointmap/$task_e1_source/stages/E1_slam_export/artifacts"
task_e3="$task_root/runs/semantic_region_pointmap/$task_e3_source/stages/E3_region_build/artifacts"
task_manifest="$task_e1/pointmaps/export_manifest.json"
task_regions="$task_e3/region_local.npz"
task_stats="$task_e3/regions.json"
if [[ ! -f "$task_manifest" || ! -f "$task_regions" || ! -f "$task_stats" ]]; then
  echo "required E1/E3 input artifact is missing" >&2
  exit 2
fi
mapfile -t task_inputs < <("$task_root/.venvs/sab3r/bin/python" - "$task_manifest" "$task_e1" <<'PY'
import json, pathlib, sys
manifest = pathlib.Path(sys.argv[1])
artifacts = pathlib.Path(sys.argv[2])
record = json.loads(manifest.read_text())["keyframes"][0]
sequence = pathlib.Path(json.loads((artifacts / "run_arguments.json").read_text())["dataset"]).name
rgb = artifacts / "upstream_output" / "keyframes" / sequence / f"{record['timestamp']}.png"
print(manifest.parent / record["file"])
print(rgb)
PY
)
if [[ ! -f "${task_inputs[0]}" || ! -f "${task_inputs[1]}" ]]; then
  echo "could not locate E1 pointmap or keyframe RGB" >&2
  exit 2
fi

bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E4_geometry_refinement \
  "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/refine_e4_geometry.py" \
  --pointmap "${task_inputs[0]}" \
  --regions "$task_regions" \
  --region-stats "$task_stats" \
  --config "$task_root/configs/e4_geometry_refinement.json" \
  --rgb "${task_inputs[1]}" \
  --output "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E4_geometry_refinement/artifacts"
