#!/usr/bin/env python3
"""Host-side readiness audit for the E1 MASt3R-SLAM pilot."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from experiment import get_run_dir, git_info, mark_stage


def sha256_file(path: Path) -> str:
    digest = __import__("hashlib").sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def command_result(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> dict:
    try:
        result = subprocess.run(args, cwd=cwd, env=env, check=False, capture_output=True, text=True)
    except (OSError, FileNotFoundError) as exc:
        return {"available": False, "error": str(exc), "returncode": None}
    return {
        "available": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--mast3r-root", default=os.environ.get("MAST3R_SLAM_ROOT"), required=False)
    parser.add_argument("--mast3r-python", default=os.environ.get("MAST3R_SLAM_PYTHON"), required=False)
    parser.add_argument("--dataset", default=os.environ.get("E1_DATASET"), required=False)
    parser.add_argument("--config", default=os.environ.get("E1_CONFIG"), required=False)
    parser.add_argument(
        "--allow-dirty-patch-sha256",
        help="allow a dirty tracked MASt3R-SLAM checkout only when its git diff HEAD hash matches",
    )
    args = parser.parse_args()
    if os.environ.get("EXPERIMENT_EXECUTION_CONTEXT") != "host":
        parser.error("E0a must run outside the sandbox with EXPERIMENT_EXECUTION_CONTEXT=host")
    missing = [name for name, value in (
        ("--mast3r-root / MAST3R_SLAM_ROOT", args.mast3r_root),
        ("--mast3r-python / MAST3R_SLAM_PYTHON", args.mast3r_python),
        ("--dataset / E1_DATASET", args.dataset),
        ("--config / E1_CONFIG", args.config),
    ) if not value]
    if missing:
        parser.error("missing E1 preflight inputs: " + ", ".join(missing))

    run_dir = get_run_dir(args.run_id)
    stage_dir = run_dir / "stages" / "E0a_preflight"
    artifact = stage_dir / "artifacts" / "preflight.json"
    if artifact.exists():
        parser.error(f"preflight already exists; use a new run ID: {artifact}")
    root = Path(args.mast3r_root).expanduser().resolve()
    python_path = Path(args.mast3r_python).expanduser().resolve()
    dataset = Path(args.dataset).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    stage_manifest = json.loads((stage_dir / "manifest.json").read_text(encoding="utf-8"))
    if stage_manifest["status"] == "planned":
        mark_stage(run_dir, "E0a_preflight", "running", note="host-side E1 readiness checks")
    elif stage_manifest["status"] != "running":
        parser.error(f"E0a stage must be planned or running, got {stage_manifest['status']!r}")
    upstream_info = git_info(root)
    dirty_patch_hash = None
    dirty_patch_match = False
    untracked_paths = []
    if upstream_info.get("dirty"):
        diff_result = subprocess.run(
            ["git", "diff", "HEAD", "--binary"], cwd=root, check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        status_result = command_result(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root)
        if diff_result.returncode == 0:
            dirty_patch_hash = __import__("hashlib").sha256(
                diff_result.stdout
            ).hexdigest()
        status_lines = status_result.get("stdout", "").splitlines()
        untracked_paths = [line for line in status_lines if line.startswith("??")]
        dirty_patch_match = bool(
            args.allow_dirty_patch_sha256
            and dirty_patch_hash == args.allow_dirty_patch_sha256
            and not untracked_paths
        )
    python_version = command_result([str(python_path), "--version"])
    nvidia = command_result([
        "nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"
    ])
    torch_probe = command_result([
        str(python_path), "-c",
        "import json,torch; print(json.dumps({'torch':torch.__version__,"
        "'cuda_runtime':torch.version.cuda,'cuda_available':torch.cuda.is_available(),"
        "'gpu_count':torch.cuda.device_count(),"
        "'gpus':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}))",
    ])
    import_env = os.environ.copy()
    prior_pythonpath = import_env.get("PYTHONPATH", "")
    source_paths = [root, root / "thirdparty" / "mast3r", root / "thirdparty" / "in3d"]
    import_env["PYTHONPATH"] = os.pathsep.join(
        [str(path) for path in source_paths if path.exists()]
        + ([prior_pythonpath] if prior_pythonpath else [])
    )
    import_probe = command_result([
        str(python_path), "-c",
        "import json,pathlib,main,mast3r_slam,dust3r; "
        "print(json.dumps({'main':str(pathlib.Path(main.__file__).resolve()),"
        "'mast3r_slam':str(pathlib.Path(mast3r_slam.__file__).resolve()),"
        "'dust3r':str(pathlib.Path(dust3r.__file__).resolve())}))",
    ], cwd=root, env=import_env)
    import_paths = {}
    try:
        import_paths = json.loads(import_probe.get("stdout", ""))
    except json.JSONDecodeError:
        pass
    try:
        source_matches = all(
            Path(import_paths[name]).is_relative_to(root)
            for name in ("main", "mast3r_slam", "dust3r")
        )
    except OSError:
        source_matches = False
    except KeyError:
        source_matches = False

    checkpoint_names = (
        "MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth",
        "MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric_retrieval_trainingfree.pth",
        "MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric_retrieval_codebook.pkl",
    )
    checkpoints = {}
    for name in checkpoint_names:
        path = root / "checkpoints" / name
        checkpoints[name] = {
            "path": str(path),
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256_file(path) if path.is_file() else None,
        }
    checkpoints_available = all(item["exists"] for item in checkpoints.values())

    image_count = None
    if dataset.is_dir():
        image_count = sum(1 for p in dataset.rglob("*") if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    elif dataset.is_file() and dataset.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi"}:
        image_count = "video"
    checks = {
        "host_execution_context": True,
        "mast3r_root_exists": (root / "main.py").is_file(),
        "mast3r_checkout_clean": upstream_info.get("dirty") is False,
        "mast3r_source_snapshot_valid": upstream_info.get("dirty") is False or dirty_patch_match,
        "mast3r_python_available": python_version["available"],
        "python_imports_pinned_checkout": source_matches,
        "required_checkpoints_available": checkpoints_available,
        "nvidia_smi_gpu_visible": nvidia["available"],
        "torch_cuda_available": torch_probe["available"] and '"cuda_available": true' in torch_probe.get("stdout", "").lower(),
        "dataset_exists": dataset.exists(),
        "dataset_has_images_or_video": bool(image_count) if isinstance(image_count, int) else image_count == "video",
        "config_exists": config_path.is_file(),
    }
    input_manifest = dataset / "source_manifest.json" if dataset.is_dir() else None
    input_manifest_info = None
    if input_manifest is not None and input_manifest.is_file():
        import hashlib
        input_manifest_info = {
            "path": str(input_manifest),
            "sha256": hashlib.sha256(input_manifest.read_bytes()).hexdigest(),
            "content": json.loads(input_manifest.read_text(encoding="utf-8")),
        }
    ready = all(value for name, value in checks.items() if name != "mast3r_checkout_clean")
    report = {
        "run_id": args.run_id,
        "stage": "E0a_preflight",
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "execution_context": "host",
        "host": platform.node(),
        "checks": checks,
        "ready_for_E1": ready,
        "mast3r": upstream_info,
        "mast3r_dirty_source": {
            "diff_head_sha256": dirty_patch_hash,
            "expected_sha256": args.allow_dirty_patch_sha256,
            "hash_matches": dirty_patch_match,
            "untracked_paths": untracked_paths,
        },
        "python": {"path": str(python_path), "version": python_version, "torch_cuda": torch_probe,
                   "import_paths": import_paths, "import_probe": import_probe},
        "gpu": nvidia,
        "dataset": {"path": str(dataset), "exists": dataset.exists(),
                    "image_count_or_video": image_count, "source_manifest": input_manifest_info},
        "config": {"path": str(config_path), "exists": config_path.is_file()},
        "checkpoints": checkpoints,
        "limitations": [
            "E0a is a readiness audit; it does not run SLAM inference.",
            "Dataset semantic/GT suitability is not evaluated by this file-presence check.",
        ],
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mark_stage(run_dir, "E0a_preflight", "completed", note=f"ready_for_E1={ready}")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
