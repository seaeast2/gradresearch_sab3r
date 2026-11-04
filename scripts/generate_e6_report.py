#!/usr/bin/env python3
"""Consolidate completed semantic-region pilot stages into an auditable E6 report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs" / "semantic_region_pointmap"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage(run_id: str, name: str) -> tuple[Path, dict]:
    directory = RUNS / run_id / "stages" / name
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing stage manifest: {manifest_path}")
    manifest = read_json(manifest_path)
    if manifest.get("status") != "completed":
        raise ValueError(f"{run_id}/{name} is {manifest.get('status')}, expected completed")
    for artifact in manifest.get("artifacts", []):
        path = directory / artifact["path"]
        if not path.is_file() or sha256(path) != artifact["sha256"]:
            raise ValueError(f"artifact missing or hash mismatch: {path}")
    return directory, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="run containing E3–E6")
    parser.add_argument("--e1-run-id", required=True)
    parser.add_argument("--e2-run-id", required=True)
    parser.add_argument("--e0a-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--docs-output", type=Path, required=True)
    args = parser.parse_args()

    links = {
        "E0_environment": (args.e0a_run_id, "E0_environment"),
        "E0a_preflight": (args.e0a_run_id, "E0a_preflight"),
        "E1_slam_export": (args.e1_run_id, "E1_slam_export"),
        "E2_sab3r_semantics": (args.e2_run_id, "E2_sab3r_semantics"),
        "E3_region_build": (args.run_id, "E3_region_build"),
        "E4_geometry_refinement": (args.run_id, "E4_geometry_refinement"),
        "E5_gt_evaluation": (args.run_id, "E5_gt_evaluation"),
    }
    source_records = {}
    for label, (source_run, stage_name) in links.items():
        directory, manifest = stage(source_run, stage_name)
        source_records[label] = {
            "run_id": source_run,
            "stage": stage_name,
            "manifest_sha256": sha256(directory / "manifest.json"),
            "artifacts": manifest.get("artifacts", []),
        }

    e1_dir, _ = stage(args.e1_run_id, "E1_slam_export")
    e2_dir, _ = stage(args.e2_run_id, "E2_sab3r_semantics")
    e3_dir, _ = stage(args.run_id, "E3_region_build")
    e4_dir, _ = stage(args.run_id, "E4_geometry_refinement")
    e5_dir, _ = stage(args.run_id, "E5_gt_evaluation")
    metrics = read_json(e5_dir / "artifacts" / "metrics.json")
    regions = read_json(e3_dir / "artifacts" / "regions.json")
    refinement = read_json(e4_dir / "artifacts" / "refinement.json")
    e1_manifest = read_json(e1_dir / "artifacts" / "pointmaps" / "export_manifest.json")
    e2_inference = read_json(e2_dir / "artifacts" / "inference.json")

    baseline = metrics["metrics"]["B0_original"]
    refined = metrics["metrics"]["B2_semantic_plane_refinement"]
    semantic_before = baseline["semantic_plane_candidates"]["rmse_m"]
    semantic_after = refined["semantic_plane_candidates"]["rmse_m"]
    relative_change = (semantic_after / semantic_before - 1.0) * 100.0
    all_before = baseline["all_valid_correspondences"]["rmse_m"]
    all_after = refined["all_valid_correspondences"]["rmse_m"]
    all_change = (all_after / all_before - 1.0) * 100.0

    summary = {
        "run_id": args.run_id,
        "source_stages": source_records,
        "keyframes": len(e1_manifest.get("keyframes", [])),
        "semantic_inference": e2_inference,
        "region_counts": {
            "valid_pixels": regions["valid_pixel_count"],
            "semantic_4conn": regions["semantic_4conn_region_count"],
            "semantic_geometry": regions["semantic_geometry_region_count"],
        },
        "refinement": {
            "candidate_regions": refinement["candidate_region_count"],
            "eligible_regions": refinement["eligible_region_count"],
            "modified_pixels": refinement["modified_pixel_count"],
            "modified_fraction": refinement["modified_fraction"],
            "outside_delta_max_abs": refinement["outside_delta_max_abs"],
        },
        "evaluation": {
            "valid_correspondences": metrics["valid_correspondence_pixels"],
            "semantic_candidates": baseline["semantic_plane_candidates"]["count"],
            "modified_points": baseline["modified_points"]["count"],
            "baseline_semantic_rmse_m": semantic_before,
            "refined_semantic_rmse_m": semantic_after,
            "semantic_rmse_relative_change_percent": relative_change,
            "baseline_all_rmse_m": all_before,
            "refined_all_rmse_m": all_after,
            "all_rmse_relative_change_percent": all_change,
            "metric_definition": metrics["metric_definition"],
        },
    }

    report = f"""# E6 — Semantic Region Pointmap pilot synthesis

**판정: E0a–E5 파일럿 파이프라인 완료. 계획서의 H1 예비 목표(여러 장면 중앙값 RMSE 10% 이상 감소)는 이 결과로 지지되지 않았습니다.** E6는 이미 완료된 단계의 산출물과 해시를 취합합니다. 새로운 모델 추론이나 3DGS 실험은 수행하지 않았습니다.

## 실행 범위

- Result run: `{args.run_id}`; E1: `{args.e1_run_id}`; E2: `{args.e2_run_id}`; E0a: `{args.e0a_run_id}`.
- Scene/frame: Replica office0, frame 0, {summary['keyframes']} exported Keyframe.
- E1 SLAM export와 E2 SAB3R semantic inference를 완료하고, E3에서 semantic/geometry Region 후보를 생성했습니다. E4는 고정 Pose로 선택된 평면 후보만 ray 방향으로 제한 보정했습니다. E5는 별도 Replica depth를 평가 전용으로 사용했습니다.
- E3 Region 수: semantic 4-연결 {regions['semantic_4conn_region_count']}, geometry gate 적용 {regions['semantic_geometry_region_count']}. E4는 후보 {refinement['candidate_region_count']}개 중 {refinement['eligible_region_count']}개를 보정해 {refinement['modified_pixel_count']:,}점을 변경했습니다.
- GT가 E3 Region 생성이나 E4 보정의 입력으로 쓰이지 않았습니다. B0/B2는 E5의 동일 전역 Sim(3)으로 평가됐습니다.

## 핵심 결과

| 지표 | B0 원본 | B2 semantic plane refinement |
|---|---:|---:|
| 전체 유효 대응 RMSE (m) | {all_before:.6f} | {all_after:.6f} |
| Semantic plane 후보 RMSE (m) | {semantic_before:.6f} | {semantic_after:.6f} |
| Semantic 후보 RMSE 변화 | — | {relative_change:+.3f}% |
| 보정된 점 수 | — | {summary['evaluation']['modified_points']:,} |

Semantic 후보 RMSE의 변화는 위 실험 계획의 10% 감소 기준에 미달합니다. E5 지표는 depth로 역투영한 같은 pixel 대응 오차이며 GT mesh까지의 point-to-surface 거리는 아닙니다. 보정된 subset은 E4 기하 규칙으로 선택되어 독립적인 효과 추정으로 해석하지 않습니다.

## 해석 및 다음 실험

이 파일럿은 고정된 단일 Keyframe에서 E1–E5 실행과 산출물 추적을 확인했습니다. 하나의 장면·시점만으로 H1을 지지할 수 없으며, semantic grouping의 geometry-only 대비 추가 가치(H2), 여러 Keyframe의 Region 연계와 temporal merge(H3)도 평가하지 않았습니다. geometry gate 뒤 작은 Region이 다수 생긴 점도 후속 개선 대상입니다.

다음 확장에서는 여러 장면/시점의 평가, B1 geometry-only와 B2 비교, B3 temporal merge, GT mesh 표면 지표, semantic 정답 평가를 별도 run으로 수행해야 합니다. 3DGS는 계획서에서 선택 실험으로 분리되어 있으므로 본 보고서의 결론에 포함하지 않았습니다.

## 추적 정보

단계별 입력 run, manifest SHA-256, artifact SHA-256은 [`e6_summary.json`](e6_summary.json)에 기록했습니다. 해당 manifest가 가리키는 모든 파일의 존재와 SHA-256을 생성 시점에 다시 확인했습니다. E0a–E5 상세 기록은 각 단계별 보고서와 run manifest를 기준으로 합니다.
"""

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.docs_output.parent.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "e6_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "E6-pilot-synthesis.md").write_text(report, encoding="utf-8")
    args.docs_output.write_text(report, encoding="utf-8")
    print(args.output_dir / "E6-pilot-synthesis.md")


if __name__ == "__main__":
    main()
