#!/usr/bin/env python3
"""Run MASt3R-SLAM and export final keyframe pointmaps into the active run stage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="RGB video or image-sequence directory")
    parser.add_argument("--config", required=True, help="upstream MASt3R-SLAM YAML configuration")
    parser.add_argument("--calib", help="optional upstream intrinsics YAML")
    parser.add_argument("--python", dest="python_exe", help="MASt3R-SLAM environment Python")
    parser.add_argument("--upstream-root", default=os.environ.get("MAST3R_SLAM_ROOT"))
    args = parser.parse_args()

    run_dir = Path(os.environ.get("EXPERIMENT_RUN_DIR", ""))
    stage_dir = Path(os.environ.get("EXPERIMENT_STAGE_DIR", ""))
    artifacts_dir = Path(os.environ.get("EXPERIMENT_ARTIFACTS_DIR", ""))
    if not run_dir.is_dir() or not stage_dir.is_dir() or not artifacts_dir.is_dir():
        parser.error("invoke through scripts/run_semantic_region_stage.sh")
    if os.environ.get("EXPERIMENT_STAGE") != "E1_slam_export":
        parser.error("this command only runs in the E1_slam_export stage")

    upstream = Path(args.upstream_root).expanduser().resolve() if args.upstream_root else None
    if upstream is None or not (upstream / "main.py").is_file():
        parser.error("set MAST3R_SLAM_ROOT to a checkout containing main.py")
    dataset = Path(args.dataset).expanduser().resolve()
    config = Path(args.config).expanduser().resolve()
    calib = Path(args.calib).expanduser().resolve() if args.calib else None
    for label, path in (("dataset", dataset), ("config", config), ("calibration", calib)):
        if path is not None and not path.exists():
            parser.error(f"{label} path does not exist: {path}")
    if not dataset.is_file() and not dataset.is_dir():
        parser.error(f"dataset must be a video file or directory: {dataset}")
    if not config.is_file():
        parser.error(f"config must be a file: {config}")

    python_exe = args.python_exe
    if not python_exe:
        settings = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        rel_python = settings.get("models", {}).get("mast3r_slam_python", ".venvs/mast3r-slam/bin/python")
        python_exe = str((ROOT / rel_python).resolve())
    python_path = shutil.which(python_exe) if not Path(python_exe).is_absolute() else python_exe
    if not python_path or not Path(python_path).is_file():
        parser.error(f"MASt3R-SLAM Python executable not found: {python_exe}")

    source_main = upstream / "main.py"
    source_text = source_main.read_text(encoding="utf-8")
    load_config_hook = "    load_config(args.config)\n"
    if source_text.count(load_config_hook) != 1:
        parser.error("upstream main.py has an unsupported configuration-loading section")
    load_guard = (
        "    load_config(args.config)\n"
        "    if os.environ.get(\"SEMANTIC_REGION_EXPORT_DIR\") and not config.get(\"single_thread\", False):\n"
        "        raise RuntimeError(\"final pointmap export requires single_thread: true\")\n"
    )
    source_text = "import os\n" + source_text.replace(load_config_hook, load_guard)
    drain_hook = "        if i == len(dataset):\n            states.set_mode(Mode.TERMINATED)\n"
    if source_text.count(drain_hook) != 1:
        parser.error("upstream main.py has an unsupported end-of-sequence section")
    drain = (
        "        if i == len(dataset):\n"
        "            if config.get(\"single_thread\", False):\n"
        "                while True:\n"
        "                    with states.lock:\n"
        "                        pending = len(states.global_optimizer_tasks) > 0 or states.reloc_sem.value > 0\n"
        "                    if not pending:\n"
        "                        break\n"
        "                    time.sleep(0.01)\n"
        "            states.set_mode(Mode.TERMINATED)\n"
    )
    source_text = source_text.replace(drain_hook, drain)
    hook = "    if dataset.save_results:\n        save_dir, seq_name = eval.prepare_savedir(args, dataset)\n        eval.save_traj("
    if source_text.count(hook) != 1:
        parser.error("upstream main.py does not match the supported final-save hook; pin/review its source first")
    injected = (
        "    export_dir = os.environ.get(\"SEMANTIC_REGION_EXPORT_DIR\")\n"
        "    if export_dir:\n"
        "        from semantic_region_export import export_keyframes\n"
        "        export_keyframes(keyframes, dataset.timestamps, export_dir)\n\n"
        + hook
    )
    launcher_dir = artifacts_dir / "launcher"
    launcher_dir.mkdir(exist_ok=True)
    effective_config = launcher_dir / "experiment_config.yaml"
    if effective_config.exists():
        parser.error(f"effective config already exists; use a new run ID: {effective_config}")
    effective_config.write_text(
        f"inherit: {json.dumps(str(config))}\nsingle_thread: true\n",
        encoding="utf-8",
    )
    launcher = launcher_dir / "main.py"
    if launcher.exists():
        parser.error(f"launcher already exists; use a new run ID: {launcher}")
    launcher.write_text(source_text.replace(hook, injected), encoding="utf-8")
    (launcher_dir / "source_main.py").write_bytes(source_main.read_bytes())

    upstream_output = artifacts_dir / "upstream_output"
    pointmap_output = artifacts_dir / "pointmaps"
    if upstream_output.exists() or pointmap_output.exists():
        parser.error("stage output directory already exists; use a new run ID to avoid mixing results")
    upstream_output.mkdir()

    command = [
        str(python_path), str(launcher),
        "--dataset", str(dataset),
        "--config", str(effective_config),
        "--save-as", str(upstream_output),
        "--no-viz",
    ]
    if calib is not None:
        command.extend(("--calib", str(calib)))
    env = os.environ.copy()
    previous_pythonpath = env.get("PYTHONPATH", "")
    source_paths = [
        ROOT / "src",
        upstream,
        upstream / "thirdparty" / "mast3r",
        upstream / "thirdparty" / "in3d",
    ]
    env["PYTHONPATH"] = os.pathsep.join(
        [str(path) for path in source_paths if path.exists()]
        + ([previous_pythonpath] if previous_pythonpath else [])
    )
    env["SEMANTIC_REGION_EXPORT_DIR"] = str(pointmap_output)
    provenance = {
        "command": command,
        "cwd": str(upstream),
        "dataset": str(dataset),
        "config": str(config),
        "effective_config": str(effective_config),
        "effective_config_sha256": sha256(effective_config),
        "calibration": str(calib) if calib else None,
        "upstream_main_sha256": sha256(source_main),
        "generated_launcher_sha256": sha256(launcher),
        "upstream_root": str(upstream),
        "python": str(python_path),
        "export_hook": "after final frame loop, before stock save_reconstruction; requires single_thread",
    }
    provenance_path = artifacts_dir / "run_arguments.json"
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completed = subprocess.run(command, cwd=upstream, env=env, check=False)
    if completed.returncode != 0:
        return completed.returncode

    manifest_path = pointmap_output / "export_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"MASt3R-SLAM exited successfully but keyframe export is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("keyframe_count", 0) < 1:
        raise RuntimeError("no keyframes were exported")
    print(f"Exported {manifest['keyframe_count']} keyframes to {pointmap_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
