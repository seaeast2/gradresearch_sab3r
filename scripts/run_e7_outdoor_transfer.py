#!/usr/bin/env python3
"""Summarize the completed outdoor semantic-region transfer stages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if not (run_dir / "run.json").is_file():
        parser.error(f"not an experiment run: {run_dir}")
    output = run_dir / "stages/E7_outdoor_transfer/artifacts"
    if any(output.iterdir()):
        parser.error(f"refusing to mix with existing E7 artifacts: {output}")

    run_config = read_json(run_dir / "config.json")
    source_runs = run_config.get("source_runs", {})
    e1a_run_id = source_runs.get("e1a", run_dir.name)
    e1a_run_dir = (run_dir.parent / e1a_run_id).resolve()
    stages = {
        "E1a": e1a_run_dir / "stages/E1a_multikeyframe_slam_export",
        "E2a": run_dir / "stages/E2a_multikeyframe_semantics",
        "E3a": run_dir / "stages/E3a_temporal_region_association",
        "E4a": run_dir / "stages/E4a_error_guided_local_refinement",
    }
    for label, stage_dir in stages.items():
        manifest = read_json(stage_dir / "manifest.json")
        if manifest.get("status") != "completed":
            parser.error(f"{label} stage is not completed")

    e1a = stages["E1a"] / "artifacts"
    e2a = stages["E2a"] / "artifacts"
    e3a = stages["E3a"] / "artifacts"
    e4a = stages["E4a"] / "artifacts"
    export_path = e1a / "pointmaps/export_manifest.json"
    tagging_path = e2a / "keyframes_manifest.json"
    regions_path = e3a / "temporal_regions.json"
    refinement_path = e4a / "refinement_summary.json"
    export, tagging, regions, refinement = map(
        read_json, (export_path, tagging_path, regions_path, refinement_path)
    )
    if tagging.get("source_e1a_export_manifest_sha256") != sha256(export_path):
        parser.error("E2a output does not reference the E1a export in this run")
    if regions.get("source_manifests", {}).get("e1a_sha256") != sha256(export_path):
        parser.error("E3a output does not reference the E1a export in this run")
    if regions.get("source_manifests", {}).get("e2a_sha256") != sha256(tagging_path):
        parser.error("E3a output does not reference the E2a tags in this run")
    if refinement.get("sources", {}).get("e3a_temporal_regions_sha256") != sha256(regions_path):
        parser.error("E4a output does not reference the E3a regions in this run")

    source_manifest = e1a / "input_rgb/source_manifest.json"
    source = read_json(source_manifest)
    result = {
        "experiment_code": "E7",
        "stage": "E7_outdoor_transfer",
        "status": "completed",
        "scene": "UAVScenes/AMtown01",
        "e1a_source_run_id": e1a_run_id,
        "interpretation": "qualitative outdoor-domain transfer; no paired LiDAR accuracy metric was computed",
        "source_rgb_count": source["rgb_frame_count"],
        "keyframe_count": len(export["keyframes"]),
        "semantic_keyframe_count": len(tagging["keyframes"]),
        "temporal_region_count": len(regions.get("global_regions", [])),
        "candidate_edge_count": len(regions.get("candidate_edges", [])),
        "accepted_edge_count": sum(x.get("decision") == "accepted" for x in regions.get("candidate_edges", [])),
        "refinement_candidate_count": refinement["candidate_region_count"],
        "selected_region_count": refinement["selected_region_count"],
        "rolled_back_region_count": refinement["rolled_back_region_count"],
        "modified_pixel_count": sum(x["modified_pixel_count"] for x in refinement["keyframes"]),
        "non_target_points_exactly_unchanged": refinement["non_target_points_exactly_unchanged"],
        "sources": {
            "input_manifest_sha256": sha256(source_manifest),
            "e1a_export_manifest_sha256": sha256(export_path),
            "e2a_manifest_sha256": sha256(tagging_path),
            "e3a_regions_sha256": sha256(regions_path),
            "e4a_summary_sha256": sha256(refinement_path),
        },
        "limitations": [
            "This is one outdoor UAVScenes scene and cannot establish broad outdoor generalization.",
            "The report checks semantic tagging, region association, and bounded-refinement behavior; it does not establish metric accuracy.",
            "LiDAR is excluded from mapping, but no timestamped paired LiDAR evaluator is included in this E7 run.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "e7_outdoor_transfer.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# E7 outdoor transfer report: UAVScenes AMtown01",
        "",
        "Status: **completed; qualitative transfer evidence only**.",
        "",
        f"- Source RGB frames: {result['source_rgb_count']}",
        f"- Exported Keyframes: {result['keyframe_count']}",
        f"- Persistent Regions: {result['temporal_region_count']}",
        f"- Accepted temporal links: {result['accepted_edge_count']} / {result['candidate_edge_count']}",
        f"- Refinement candidates: {result['refinement_candidate_count']}; selected: {result['selected_region_count']}; rolled back: {result['rolled_back_region_count']}",
        f"- Modified pixels: {result['modified_pixel_count']}",
        "",
        "The report does not claim metric accuracy. No paired LiDAR evaluation was run.",
        "See `e7_outdoor_transfer.json` for source hashes and limitations.",
    ]
    (output / "e7_outdoor_transfer.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
