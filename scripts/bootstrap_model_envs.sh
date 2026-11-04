#!/usr/bin/env bash
# Create separate empty virtual environments; install model dependencies per upstream docs.
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
task_env_root="$task_root/.venvs"
mkdir -p "$task_env_root"
task_mast3r_python="${PYTHON_MAST3R:-python3.11}"
task_sab3r_python="${PYTHON_SAB3R:-python3.11}"
task_log="$task_env_root/bootstrap.log"
exec > >(tee -a "$task_log") 2>&1

for task_item in "mast3r-slam:$task_mast3r_python" "sab3r:$task_sab3r_python"; do
  task_name="${task_item%%:*}"
  task_python="${task_item#*:}"
  task_venv="$task_env_root/$task_name"
  if [[ -e "$task_venv" ]]; then
    echo "Preserving existing environment: $task_venv"
  else
    "$task_python" -m venv "$task_venv"
  fi
  "$task_venv/bin/python" --version
  "$task_venv/bin/python" -m pip --version
done

cat <<EOF
Created isolated Python environments (dependencies not installed):
  MASt3R-SLAM: $task_env_root/mast3r-slam
  SAB3R:       $task_env_root/sab3r
Install each project's pinned dependencies by following its own README.
EOF
