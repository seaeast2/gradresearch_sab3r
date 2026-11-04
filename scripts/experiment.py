#!/usr/bin/env python3
"""Create and track isolated runs for the semantic region pointmap study."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "semantic_region_experiment.json"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run_command(args: list[str], cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(args, cwd=cwd, check=False, capture_output=True, text=True)
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_info(path: Path | None) -> dict[str, str | None]:
    if path is None or not path.is_dir():
        return {"path": str(path) if path else None, "commit": None, "dirty": None}
    commit = run_command(["git", "rev-parse", "HEAD"], cwd=path)
    dirty = run_command(["git", "status", "--porcelain"], cwd=path)
    return {
        "path": str(path.resolve()),
        "commit": commit,
        "dirty": None if dirty is None else bool(dirty),
    }


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {"experiment_name", "run_root", "stages", "models"}
    missing = required - config.keys()
    if missing:
        raise ValueError(f"config missing required keys: {', '.join(sorted(missing))}")
    if not isinstance(config["stages"], list) or not config["stages"]:
        raise ValueError("config.stages must be a non-empty list")
    return config


def resolve_repo_from_env(config: dict[str, Any], key: str) -> Path | None:
    env_name = config.get("models", {}).get(key)
    value = os.environ.get(env_name, "") if env_name else ""
    return Path(value).expanduser() if value else None


def resolve_python(config: dict[str, Any], path_key: str, env_key: str) -> Path | None:
    models = config.get("models", {})
    env_name = models.get(env_key)
    value = os.environ.get(env_name, "") if env_name else ""
    value = value or models.get(path_key, "")
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def init_run(args: argparse.Namespace) -> None:
    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)
    run_id = args.run_id or dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run ID may contain only letters, digits, dot, underscore, and hyphen")
    run_root = Path(config["run_root"])
    if not run_root.is_absolute():
        run_root = PROJECT_ROOT / run_root
    run_dir = (run_root / run_id).resolve()
    if run_dir.exists():
        raise FileExistsError(f"run already exists; choose a new --run-id: {run_dir}")

    run_dir.mkdir(parents=True)
    config_copy = run_dir / "config.json"
    shutil.copy2(config_path, config_copy)
    state = {
        "run_id": run_id,
        "experiment_name": config["experiment_name"],
        "created_at_utc": now(),
        "status": "initialized",
        "config_sha256": sha256_file(config_copy),
        "project": git_info(PROJECT_ROOT),
        "stages": {},
    }
    for stage in config["stages"]:
        if not RUN_ID_RE.fullmatch(stage):
            raise ValueError(f"invalid stage name: {stage}")
        stage_dir = run_dir / "stages" / stage
        (stage_dir / "artifacts").mkdir(parents=True)
        (stage_dir / "logs").mkdir()
        json_dump(stage_dir / "manifest.json", {
            "stage": stage,
            "status": "planned",
            "created_at_utc": now(),
            "artifacts": [],
        })
        state["stages"][stage] = "planned"
    json_dump(run_dir / "run.json", state)
    print(run_dir)


def get_run_dir(run_arg: str) -> Path:
    path = Path(run_arg).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / "runs" / "semantic_region_pointmap" / path
    path = path.resolve()
    if not (path / "run.json").is_file():
        raise FileNotFoundError(f"not an initialized experiment run: {path}")
    return path


def capture_environment(args: argparse.Namespace) -> None:
    run_dir = get_run_dir(args.run)
    config = load_config(run_dir / "config.json")
    python_paths = {
        "mast3r_slam": resolve_python(config, "mast3r_slam_python", "mast3r_slam_python_env"),
        "sab3r": resolve_python(config, "sab3r_python", "sab3r_python_env"),
    }
    env = {
        "captured_at_utc": now(),
        "execution_context": os.environ.get("EXPERIMENT_EXECUTION_CONTEXT", "sandbox"),
        "host": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "executable": sys.executable,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "nvidia_smi": run_command([
            "nvidia-smi", "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]),
        "nvcc": run_command(["nvcc", "--version"]),
        "project": git_info(PROJECT_ROOT),
        "mast3r_slam": git_info(resolve_repo_from_env(config, "mast3r_slam_path_env")),
        "sab3r": git_info(resolve_repo_from_env(config, "sab3r_path_env")),
        "model_environments": {},
    }
    package_probe = (
        "import json; import torch; "
        "print(json.dumps({'torch': torch.__version__, 'torch_cuda': torch.version.cuda, "
        "'cuda_available': torch.cuda.is_available(), "
        "'gpu_count': torch.cuda.device_count()}))"
    )
    for name, python_path in python_paths.items():
        python_text = str(python_path) if python_path else None
        env["model_environments"][name] = {
            "python_path": python_text,
            "python_version": run_command([python_text, "--version"]) if python_text else None,
            "torch_cuda": run_command([python_text, "-c", package_probe]) if python_text else None,
        }
    target = run_dir / "stages" / "E0_environment" / "artifacts" / "environment.json"
    if target.exists():
        raise FileExistsError(f"environment snapshot already exists: {target}")
    mark_stage(run_dir, "E0_environment", "running", note="capturing host and model environments")
    json_dump(target, env)
    for name, python_path in python_paths.items():
        if python_path:
            package_list = run_command([str(python_path), "-m", "pip", "freeze"])
            if package_list is not None:
                (target.parent / f"{name}_pip_freeze.txt").write_text(package_list + "\n", encoding="utf-8")
    mark_stage(run_dir, "E0_environment", "completed", note="environment snapshot captured")
    print(target)


def mark_stage(run_dir: Path, stage: str, status: str, note: str = "") -> None:
    config = load_config(run_dir / "config.json")
    if stage not in config["stages"]:
        raise ValueError(f"unknown stage {stage!r}; expected one of {config['stages']}")
    run_state_path = run_dir / "run.json"
    run_state = json.loads(run_state_path.read_text(encoding="utf-8"))
    stage_path = run_dir / "stages" / stage / "manifest.json"
    manifest = json.loads(stage_path.read_text(encoding="utf-8"))
    allowed = {"planned": {"running"}, "running": {"completed", "failed"}, "failed": set(), "completed": set()}
    old_status = manifest["status"]
    if status not in allowed.get(old_status, set()):
        raise ValueError(f"invalid stage transition {old_status!r} -> {status!r} for {stage}")
    stamp = now()
    if status == "running":
        manifest["started_at_utc"] = stamp
    else:
        manifest["finished_at_utc"] = stamp
        manifest["artifacts"] = [
            {"path": p.relative_to(run_dir / "stages" / stage).as_posix(), "sha256": sha256_file(p)}
            for p in sorted((run_dir / "stages" / stage / "artifacts").rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        ]
    manifest["status"] = status
    if note:
        manifest.setdefault("notes", []).append({"at_utc": stamp, "text": note})
    json_dump(stage_path, manifest)
    run_state["stages"][stage] = status
    stage_states = list(run_state["stages"].values())
    if any(s == "failed" for s in stage_states):
        run_state["status"] = "failed"
    elif all(s == "completed" for s in stage_states):
        run_state["status"] = "completed"
    elif all(s == "planned" for s in stage_states):
        run_state["status"] = "initialized"
    else:
        run_state["status"] = "running"
    json_dump(run_state_path, run_state)


def stage_command(args: argparse.Namespace) -> None:
    run_dir = get_run_dir(args.run)
    mark_stage(run_dir, args.stage, args.status, args.note)
    print(f"{args.stage}: {args.status}")


def show_status(args: argparse.Namespace) -> None:
    run_dir = get_run_dir(args.run)
    state = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    print(json.dumps({"run_dir": str(run_dir), **state}, indent=2))


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create a new, isolated run directory")
    init.add_argument("--config", default=str(DEFAULT_CONFIG))
    init.add_argument("--run-id", help="unique ID; defaults to current local timestamp")
    init.set_defaults(func=init_run)
    capture = commands.add_parser("capture-env", help="record software, GPU, and source revisions")
    capture.add_argument("run", help="run ID or absolute run directory")
    capture.set_defaults(func=capture_environment)
    stage = commands.add_parser("stage", help="record a stage state transition")
    stage.add_argument("run")
    stage.add_argument("stage")
    stage.add_argument("status", choices=("running", "completed", "failed"))
    stage.add_argument("--note", default="")
    stage.set_defaults(func=stage_command)
    status = commands.add_parser("status", help="show stage completion status")
    status.add_argument("run")
    status.set_defaults(func=show_status)
    return parser


if __name__ == "__main__":
    parser = make_parser()
    parsed = parser.parse_args()
    try:
        parsed.func(parsed)
    except (ValueError, FileExistsError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
