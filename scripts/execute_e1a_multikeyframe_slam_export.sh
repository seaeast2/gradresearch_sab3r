#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 || $# -gt 5 ]]; then
  echo "usage: $0 SOURCE_RGB_DIR UPSTREAM_CONFIG KEYFRAME_BUFFER MAST3R_PYTHON [CALIB_YAML]" >&2
  exit 2
fi
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
task_source="$1"
task_config="$2"
task_buffer="$3"
task_python="$4"
task_calib="${5:-}"
if [[ "${EXPERIMENT_STAGE:-}" != "E1a_multikeyframe_slam_export" || -z "${EXPERIMENT_ARTIFACTS_DIR:-}" ]]; then
  echo "invoke through run_semantic_region_stage.sh for E1a_multikeyframe_slam_export" >&2
  exit 2
fi

task_staged_rgb="$EXPERIMENT_ARTIFACTS_DIR/input_rgb"
"$task_python" "$task_root/scripts/prepare_e1a_sequence.py" \
  "$task_source" "$task_staged_rgb" --minimum-frames 2

task_run_config="$EXPERIMENT_RUN_DIR/config.json"
task_frame_time_csv=""
task_time_table="$(python3 - "$task_run_config" <<'PY'
import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text())
print(config.get("dataset", {}).get("source_frame_table", ""))
PY
)"
if [[ -n "$task_time_table" ]]; then
  task_frame_time_csv="$task_staged_rgb/frame_times.csv"
  python3 - "$task_staged_rgb/source_manifest.json" "$task_time_table" "$task_frame_time_csv" <<'PY'
import csv, json, pathlib, sys
manifest_path, table_path, output_path = map(pathlib.Path, sys.argv[1:])
manifest = json.loads(manifest_path.read_text())
with table_path.open(newline="") as stream:
    rows = {row["filename"]: row for row in csv.DictReader(stream)}
records = manifest["frames"]
with output_path.open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=["input_index", "png_filename", "rgb_timestamp"])
    writer.writeheader()
    for item in records:
        row = rows.get(item["source_filename"])
        if row is None:
            raise SystemExit(f"source timestamp row missing for {item['source_filename']}")
        writer.writerow({
            "input_index": item["sequence_index"],
            "png_filename": item["staged_filename"],
            "rgb_timestamp": row["rgb_timestamp"],
        })
print(f"timestamp rows: {len(records)}")
PY
fi

task_args=(
  --stage-name E1a_multikeyframe_slam_export
  --dataset "$task_staged_rgb"
  --config "$task_config"
  --keyframe-buffer "$task_buffer"
  --python "$task_python"
)
if [[ -n "$task_frame_time_csv" ]]; then
  task_min_interval="$(python3 - "$task_run_config" <<'PY'
import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text())
print(config["dataset"]["keyframe_policy"]["minimum_keyframe_interval_seconds"])
PY
)"
  task_force_periodic="$(python3 - "$task_run_config" <<'PY'
import json, pathlib, sys
config = json.loads(pathlib.Path(sys.argv[1]).read_text())
print(str(config["dataset"]["keyframe_policy"]["force_periodic_keyframes"]).lower())
PY
)"
  task_args+=(--frame-time-csv "$task_frame_time_csv" --min-keyframe-seconds "$task_min_interval")
  if [[ "$task_force_periodic" == "true" ]]; then
    task_args+=(--force-periodic-keyframes)
  fi
fi
if [[ -n "$task_calib" ]]; then
  task_args+=(--calib "$task_calib")
fi
python3 "$task_root/scripts/run_slam_export.py" "${task_args[@]}"

python3 - "$EXPERIMENT_ARTIFACTS_DIR/pointmaps/export_manifest.json" <<'PY'
import json, pathlib, sys
manifest = json.loads(pathlib.Path(sys.argv[1]).read_text())
count = manifest.get("keyframe_count", 0)
if count < 2:
    raise SystemExit(f"E1a requires at least 2 exported Keyframes; got {count}. Artifacts are retained as a failed attempt.")
print(f"E1a multi-Keyframe gate passed: {count} Keyframes")
PY
