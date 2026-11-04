#!/usr/bin/env python3
"""Validate E1a-E5a provenance and synthesize scene/H4 results for E6a."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs" / "semantic_region_pointmap"
PRIMARY_STAGES = (
    "E0_environment", "E0a_preflight", "E1a_multikeyframe_slam_export",
    "E2a_multikeyframe_semantics", "E3a_temporal_region_association",
    "E4a_error_guided_local_refinement", "E5a_multikeyframe_gt_evaluation",
)
HASH_CACHE: dict[Path, str] = {}


def sha256(path: Path) -> str:
    path = path.resolve()
    if path not in HASH_CACHE:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        HASH_CACHE[path] = digest.hexdigest()
    return HASH_CACHE[path]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_dir(run_id: str) -> Path:
    path = RUNS / run_id
    if not (path / "run.json").is_file():
        raise FileNotFoundError(f"run metadata missing: {path / 'run.json'}")
    return path


def validate_stage(run_id: str, stage: str) -> dict[str, Any]:
    base = run_dir(run_id)
    manifest_path = base / "stages" / stage / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"{run_id}: missing stage manifest {stage}")
    manifest = load_json(manifest_path)
    if manifest.get("status") != "completed":
        raise ValueError(f"{run_id}/{stage}: expected completed, got {manifest.get('status')}")
    checked_artifacts = []
    for item in manifest.get("artifacts", []):
        artifact_path = base / "stages" / stage / item["path"]
        if not artifact_path.is_file():
            raise FileNotFoundError(f"{run_id}/{stage}: artifact missing: {item['path']}")
        actual_hash = sha256(artifact_path)
        if actual_hash != item.get("sha256"):
            raise ValueError(f"{run_id}/{stage}: artifact hash mismatch: {item['path']}")
        checked_artifacts.append({"path": item["path"], "sha256": actual_hash, "size_bytes": artifact_path.stat().st_size})
    return {
        "status": "completed", "manifest_sha256": sha256(manifest_path),
        "artifact_count": len(checked_artifacts), "artifacts": checked_artifacts,
    }


def stage_artifact(run_id: str, stage: str, filename: str) -> Path:
    return run_dir(run_id) / "stages" / stage / "artifacts" / filename


def compact_metrics(metrics_path: Path) -> dict[str, Any]:
    data = load_json(metrics_path)
    result: dict[str, Any] = {
        "scene": data["scene"], "scene_split": data["scene_split"],
        "keyframe_count": data["keyframe_count"],
        "frame_ids": [frame["frame_id"] for frame in data["keyframes"]],
        "sim3_scale": data["common_sim3"]["scale"],
        "metrics_sha256": sha256(metrics_path),
        "source_manifests": data.get("source_manifests", {}),
        "b4_status": "unavailable: Replica export has depth/poses but no GT semantic/plane masks",
        "methods": {},
    }
    for name, values in data["metrics"].items():
        all_points = values["all_keyframe_point_correspondences"]
        plane = values["semantic_plane_pixels"]
        normal = values["normal_error_degrees"]
        boundary = values["semantic_boundary_gap_error_m"]
        result["methods"][name] = {
            "all_point_rmse_m": all_points["rmse_m"],
            "all_point_outlier_rate_5cm": all_points["outlier_rate_over_threshold"],
            "semantic_plane_rmse_m": plane["rmse_m"],
            "semantic_plane_outlier_rate_5cm": plane["outlier_rate_over_threshold"],
            "normal_error_mean_deg": normal["mean"],
            "semantic_boundary_gap_mean_m": boundary["mean"],
            "scene_fscore_5cm": data["scene_surface_fscore"][name]["fscore_at_5cm"],
        }
    return result


def e4_summary(run_id: str) -> dict[str, Any]:
    path = stage_artifact(run_id, "E4a_error_guided_local_refinement", "refinement_summary.json")
    data = load_json(path)
    return {
        "summary_sha256": sha256(path),
        "selected_region_count": data["selected_region_count"],
        "rolled_back_region_count": data["rolled_back_region_count"],
        "modified_pixel_count": sum(item["modified_pixel_count"] for item in data["keyframes"]),
        "maximum_radial_displacement_world_units": data["maximum_radial_displacement_world_units"],
        "frozen_error_threshold_spacing_ratio": data["frozen_error_threshold_spacing_ratio"],
        "non_target_points_exactly_unchanged": data["non_target_points_exactly_unchanged"],
        "config": data["config"],
    }


def collect_run(run_id: str, required_stages: tuple[str, ...]) -> dict[str, Any]:
    base = run_dir(run_id)
    run_meta = load_json(base / "run.json")
    stages = {}
    for stage in required_stages:
        stages[stage] = validate_stage(run_id, stage)
    metrics = compact_metrics(stage_artifact(run_id, "E5a_multikeyframe_gt_evaluation", "metrics.json")) if "E5a_multikeyframe_gt_evaluation" in required_stages else None
    return {
        "run_id": run_id,
        "experiment_name": run_meta.get("experiment_name"),
        "run_config_sha256": run_meta.get("config_sha256"),
        "project_commit": run_meta.get("project", {}).get("commit"),
        "stages": stages,
        "metrics": metrics,
    }


def summarize_attempt(run_id: str) -> dict[str, Any]:
    base = run_dir(run_id)
    state = load_json(base / "run.json")
    stages = {}
    for stage, status in state.get("stages", {}).items():
        item: dict[str, Any] = {"status": status}
        manifest_path = base / "stages" / stage / "manifest.json"
        if manifest_path.is_file():
            item["manifest_sha256"] = sha256(manifest_path)
            manifest = load_json(manifest_path)
            if manifest.get("notes"):
                item["notes"] = manifest["notes"]
            if status == "completed":
                item["artifact_validation"] = validate_stage(run_id, stage)
        log_path = base / "stages" / stage / "logs" / "command.log"
        if log_path.is_file() and status in {"failed", "running"}:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            item["log_tail"] = lines[-8:]
        stages[stage] = item
    summary = {"run_id": run_id, "run_status": state.get("status"), "stages": stages}
    preflight = base / "stages" / "E0a_preflight" / "artifacts" / "preflight.json"
    if preflight.is_file():
        data = load_json(preflight)
        summary["ready_for_E1"] = data.get("ready_for_E1")
        summary["preflight_checks"] = data.get("checks")
    return summary


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# E6a multi-Keyframe experiment synthesis",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        "",
        "## Scene-level B0–B3 evaluation",
        "",
        "| Scene | Split | KFs | B0 RMSE (m) | B1 RMSE | B2 RMSE | B3 RMSE | B0 F@5cm | B3 F@5cm | B3 modified px | B3 selected / rollback |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scene in payload["scene_results"]:
        methods = scene["metrics"]["methods"]
        e4 = scene["e4_summary"]
        b0 = methods["B0_original"]
        lines.append(
            f"| {scene['metrics']['scene']} | {scene['metrics']['scene_split']} | {scene['metrics']['keyframe_count']} "
            f"| {b0['all_point_rmse_m']:.6f} | {methods['B1_geometry_only']['all_point_rmse_m']:.6f} "
            f"| {methods['B2_semantic_frame_local']['all_point_rmse_m']:.6f} | {methods['B3_semantic_temporal']['all_point_rmse_m']:.6f} "
            f"| {b0['scene_fscore_5cm']:.6f} | {methods['B3_semantic_temporal']['scene_fscore_5cm']:.6f} "
            f"| {e4['modified_pixel_count']} | {e4['selected_region_count']} / {e4['rolled_back_region_count']} |"
        )
    lines += [
        "",
        "## Validation reference",
        "",
        "| Scene | Split | KFs | B0 RMSE (m) | B2 RMSE (m) | B3 RMSE (m) | B0 F@5cm | B3 F@5cm |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for record in payload["validation_results"]:
        metrics = record["metrics"]
        methods = metrics["methods"]
        lines.append(
            f"| {metrics['scene']} | {metrics['scene_split']} | {metrics['keyframe_count']} "
            f"| {methods['B0_original']['all_point_rmse_m']:.6f} "
            f"| {methods['B2_semantic_frame_local']['all_point_rmse_m']:.6f} "
            f"| {methods['B3_semantic_temporal']['all_point_rmse_m']:.6f} "
            f"| {methods['B0_original']['scene_fscore_5cm']:.6f} "
            f"| {methods['B3_semantic_temporal']['scene_fscore_5cm']:.6f} |"
        )
    lines += [
        "",
        "B0–B3 use one B0-derived scene Sim(3), reused within each scene. GT is evaluation-only. These are same-pixel point distances and 5 cm nearest-neighbor F-scores on an image lattice, not mesh point-to-surface errors. B4 Oracle was unavailable because the provided Replica exports lack GT semantic/plane masks.",
        "",
        "## H4 ablations",
        "",
        "| Factor | Scene | Baseline B3 RMSE | Ablation B3 RMSE | Δ RMSE | Baseline F@5cm | Ablation F@5cm | Applied / rollback |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for ablation in payload["h4_ablations"]:
        lines.append(
            f"| {ablation['factor']} | {ablation['scene']} | {ablation['baseline_b3_rmse_m']:.6f} "
            f"| {ablation['ablation_b3_rmse_m']:.6f} | {ablation['delta_rmse_m']:+.6f} "
            f"| {ablation['baseline_b3_fscore_5cm']:.6f} | {ablation['ablation_b3_fscore_5cm']:.6f} "
            f"| {ablation['selected_region_count']} / {ablation['rolled_back_region_count']} |"
        )
    lines += ["", "## Interpretation and limitations", ""]
    lines += [f"- {item}" for item in payload["conclusions"]]
    gs = payload["optional_3dgs_feasibility"]
    lines += ["", "## Optional research E6: 3DGS feasibility", "", f"Status: **{gs['status']}**."]
    lines += [f"- {item}" for item in gs["evidence"]]
    lines += ["", "## Preserved attempts", ""]
    for attempt in payload["attempts"]:
        statuses = ", ".join(f"{stage}={value['status']}" for stage, value in attempt["stages"].items())
        lines.append(f"- `{attempt['run_id']}` ({attempt['run_status']}): {statuses}")
    lines += ["", "## Provenance index", "", "The adjacent `e6a_synthesis.json` contains the verified stage manifest SHA-256 values and artifact hashes for every included run.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-run", action="append", default=[], help="Full E0a-E5a scene run; repeat per scene")
    parser.add_argument("--support-run", action="append", default=[], help="Completed validation/pilot stage source run")
    parser.add_argument("--validation-metrics-run", action="append", default=[], help="Run with a completed E5a validation metrics stage")
    parser.add_argument("--ablation-run", action="append", default=[], help="H4 run with completed E4a/E5a stages")
    parser.add_argument("--attempt-run", action="append", default=[], help="Preserved failed or incomplete attempt")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.primary_run:
        parser.error("at least one --primary-run is required")

    primary = [collect_run(run_id, PRIMARY_STAGES) for run_id in args.primary_run]
    support = []
    support_stages = (
        "E0_environment", "E0a_preflight", "E1a_multikeyframe_slam_export",
        "E2a_multikeyframe_semantics", "E3a_temporal_region_association",
        "E4a_error_guided_local_refinement", "E5a_multikeyframe_gt_evaluation",
    )
    for run_id in args.support_run:
        state = load_json(run_dir(run_id) / "run.json")
        completed = tuple(stage for stage in support_stages if state.get("stages", {}).get(stage) == "completed")
        if not completed:
            raise ValueError(f"support run has no completed extension stage: {run_id}")
        support.append(collect_run(run_id, completed))
    validation = [collect_run(run_id, ("E5a_multikeyframe_gt_evaluation",)) for run_id in args.validation_metrics_run]
    ablation_runs = [collect_run(run_id, ("E4a_error_guided_local_refinement", "E5a_multikeyframe_gt_evaluation")) for run_id in args.ablation_run]

    all_runs = primary + support + validation + ablation_runs
    verified_artifact_hashes = {
        artifact["sha256"]
        for record in all_runs
        for stage in record["stages"].values()
        for artifact in stage["artifacts"]
    }
    for record in all_runs:
        metrics = record.get("metrics")
        if metrics is None:
            continue
        for source_name, expected_hash in metrics.get("source_manifests", {}).items():
            if expected_hash not in verified_artifact_hashes:
                raise ValueError(
                    f"{record['run_id']}: E5a source manifest {source_name}={expected_hash} "
                    "was not found among hash-verified included source artifacts"
                )

    scene_results = []
    for record in primary:
        summary = e4_summary(record["run_id"])
        scene_results.append({"run_id": record["run_id"], "metrics": record["metrics"], "e4_summary": summary})
    validation_results = []
    for record in validation:
        metrics = record["metrics"]
        validation_results.append({"run_id": record["run_id"], "metrics": metrics})
    all_baseline_metrics = {record["metrics"]["scene"]: record["metrics"] for record in primary + validation}

    h4 = []
    for record in ablation_runs:
        metrics = record["metrics"]
        scene = metrics["scene"]
        baseline = all_baseline_metrics.get(scene)
        if baseline is None:
            raise ValueError(f"no baseline E5a metrics for ablation scene {scene!r}")
        summary = e4_summary(record["run_id"])
        refinement = summary["config"]["refinement"]
        factor = (
            "robust_loss=" + str(refinement.get("robust_loss", "huber"))
            if "squared" in record["run_id"] else
            "confidence_weights=" + str(refinement.get("confidence_weights"))
            if "uniform" in record["run_id"] else
            "maximum_radial_displacement_over_global_spacing=" + str(refinement["maximum_radial_displacement_over_global_spacing"])
        )
        base_b3 = baseline["methods"]["B3_semantic_temporal"]
        ablation_b3 = metrics["methods"]["B3_semantic_temporal"]
        h4.append({
            "run_id": record["run_id"], "scene": scene, "factor": factor,
            "baseline_run_id": next(x["run_id"] for x in primary + validation if x["metrics"]["scene"] == scene),
            "baseline_b3_rmse_m": base_b3["all_point_rmse_m"],
            "ablation_b3_rmse_m": ablation_b3["all_point_rmse_m"],
            "delta_rmse_m": ablation_b3["all_point_rmse_m"] - base_b3["all_point_rmse_m"],
            "baseline_b3_outlier_rate_5cm": base_b3["all_point_outlier_rate_5cm"],
            "ablation_b3_outlier_rate_5cm": ablation_b3["all_point_outlier_rate_5cm"],
            "baseline_b3_fscore_5cm": base_b3["scene_fscore_5cm"],
            "ablation_b3_fscore_5cm": ablation_b3["scene_fscore_5cm"],
            "selected_region_count": summary["selected_region_count"],
            "rolled_back_region_count": summary["rolled_back_region_count"],
            "modified_pixel_count": summary["modified_pixel_count"],
            "metrics_sha256": metrics["metrics_sha256"],
            "e4a_summary_sha256": summary["summary_sha256"],
        })

    attempts = [summarize_attempt(run_id) for run_id in args.attempt_run]
    conclusions = [
        "Three independent Replica test scenes (room1, office1, office2) were evaluated; all are indoor scenes, so environment generalization remains untested.",
        "The E5a main comparisons show very small and mixed B1–B3 changes; the pre-set 10% RMSE improvement target was not reached. No positive H1–H3 claim is supported by these results.",
        "The three H4 factor ablations show small, scene-dependent changes. Huber versus squared loss and confidence versus uniform weights do not show a consistent scene-level accuracy advantage; halving the displacement bound preserves the configured safety limit but does not yield consistent metric gains.",
        "The local point-to-plane objective can improve while GT scene metrics remain unchanged or worsen. E4a rollback and exact non-target invariants are part of the result, not omitted failures.",
        "B4 Oracle and mesh point-to-surface evaluation were unavailable from the supplied Replica exports. E3a accepted edge counts have not been verified against GT associations.",
    ]
    payload = {
        "stage": "E6a_extension_report", "status": "completed",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "generator_sha256": sha256(Path(__file__)),
        "validation_results": validation_results,
        "scene_results": scene_results,
        "h4_ablations": h4,
        "support_runs": support,
        "attempts": attempts,
        "conclusions": conclusions,
        "optional_3dgs_feasibility": {
            "status": "deferred; prerequisites not yet pinned",
            "evidence": [
                "Replica RGB sequences, trajectories, and paired depth are present; office2 also has an `office2_mesh.ply` asset.",
                "The workspace has no checked-out 3DGS training/rasterizer implementation, and the SAB3R Python environment cannot import `gsplat`, `diff_gaussian_rasterization`, or `simple_knn`.",
                "No matched Gaussian initialization/training protocol, held-out rendering split, or Gaussian outlier/ghost annotation is configured. Installing and validating that stack would be a separate substantial experiment, so the optional E6 was not run in this E1a–E6a cycle.",
                "No claim is made that pointmap refinement reduces Gaussian outliers or improves rendering quality. Revisit E6 only after pinning a 3DGS implementation and protocol on validation scenes.",
            ],
        },
        "provenance_policy": "Each included completed stage manifest and every artifact listed by it were SHA-256 verified before synthesis.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "e6a_synthesis.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output / "E6a_summary.md").write_text(markdown_report(payload), encoding="utf-8")
    print(json.dumps({
        "stage": payload["stage"], "status": payload["status"],
        "primary_scene_count": len(scene_results), "validation_metrics_count": len(validation_results),
        "h4_ablation_count": len(h4), "support_run_count": len(support), "attempt_count": len(attempts),
        "json": str(args.output / "e6a_synthesis.json"), "markdown": str(args.output / "E6a_summary.md"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
