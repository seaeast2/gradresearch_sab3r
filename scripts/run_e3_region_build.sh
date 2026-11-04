#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 3 ]]; then
  echo "usage: $0 OUTPUT_RUN_ID E1_SOURCE_RUN_ID E2_SOURCE_RUN_ID" >&2
  exit 2
fi
task_run_id="$1"
task_e1="$task_root/runs/semantic_region_pointmap/$2/stages/E1_slam_export/artifacts"
task_e2="$task_root/runs/semantic_region_pointmap/$3/stages/E2_sab3r_semantics/artifacts"
task_manifest="$task_e1/pointmaps/export_manifest.json"
task_scores="$task_e2/semantic_scores.npz"
if [[ ! -f "$task_manifest" || ! -f "$task_scores" ]]; then
  echo "required E1 or E2 input artifact is missing" >&2
  exit 2
fi
task_pointmap="$(.venvs/sab3r/bin/python - "$task_manifest" <<'PY'
import json, pathlib, sys
manifest = pathlib.Path(sys.argv[1])
record = json.loads(manifest.read_text())["keyframes"][0]
print(manifest.parent / record["file"])
PY
)"
if [[ ! -f "$task_pointmap" ]]; then
  echo "E1 pointmap file does not exist: $task_pointmap" >&2
  exit 2
fi

bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E3_region_build \
  "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/build_e3_regions.py" \
  --pointmap "$task_pointmap" \
  --scores "$task_scores" \
  --config "$task_root/configs/e3_region_build.json" \
  --output "$task_root/runs/semantic_region_pointmap/$task_run_id/stages/E3_region_build/artifacts"
