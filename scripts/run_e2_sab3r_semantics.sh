#!/usr/bin/env bash
set -euo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "usage: $0 RUN_ID [E1_SOURCE_RUN_ID]" >&2
  exit 2
fi
task_run_id="$1"
task_source_run_id="${2:-$task_run_id}"
task_run="$task_root/runs/semantic_region_pointmap/$task_run_id"
task_e1="$task_root/runs/semantic_region_pointmap/$task_source_run_id/stages/E1_slam_export/artifacts"
task_manifest="$task_e1/pointmaps/export_manifest.json"
task_args="$task_e1/run_arguments.json"
task_checkpoint="$(find "$task_root/third_party/sab-3r/checkpoints/hf-home/hub/models--uva-cv-lab--SAB3R/snapshots" -path '*/demo_ckpt/base/base.pt' -print -quit)"
if [[ ! -f "$task_manifest" || ! -f "$task_args" || -z "$task_checkpoint" ]]; then
  echo "E1 export or the downloaded SAB3R checkpoint is missing for $task_run_id" >&2
  exit 2
fi
mapfile -t task_inputs < <("$task_root/.venvs/sab3r/bin/python" - "$task_manifest" "$task_args" <<'PY'
import json
import pathlib
import sys

e1 = pathlib.Path(sys.argv[1]).parent.parent
record = json.loads(pathlib.Path(sys.argv[1]).read_text())["keyframes"][0]
sequence_name = pathlib.Path(json.loads(pathlib.Path(sys.argv[2]).read_text())["dataset"]).name
image = e1 / "upstream_output" / "keyframes" / sequence_name / f"{record['timestamp']}.png"
npz = e1 / "pointmaps" / record["file"]
print(npz)
print(image)
PY
)
if [[ ! -f "${task_inputs[0]}" || ! -f "${task_inputs[1]}" ]]; then
  echo "could not locate exported E1 NPZ/RGB inputs" >&2
  exit 2
fi

export EXPERIMENT_EXECUTION_CONTEXT=host
bash "$task_root/scripts/run_semantic_region_stage.sh" "$task_run_id" E2_sab3r_semantics \
  env PYTHONPATH="$task_root/third_party/sab-3r:$task_root/third_party/FeatUp" \
      MPLCONFIGDIR=/tmp/sab3r-mpl-cache \
      "$task_root/.venvs/sab3r/bin/python" "$task_root/scripts/run_e2_sab3r.py" \
      --repo "$task_root/third_party/sab-3r" \
      --featup "$task_root/third_party/FeatUp" \
      --checkpoint "$task_checkpoint" \
      --input-npz "${task_inputs[0]}" \
      --input-image "${task_inputs[1]}" \
      --output "$task_run/stages/E2_sab3r_semantics/artifacts"
