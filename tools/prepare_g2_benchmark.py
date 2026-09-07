"""Prepare auditable G2 input selection without invoking an inference provider."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from admit_dataset import admit, verify_seal
from build_dataset_snapshot import safe_path, sha256_file
from interaction_studio_api.preflight.composite import choose_product, select_hand

CASE_IDS = [
    "DEV_MOUTH_001", "DEV_MOUTH_002", "DEV_MOUTH_003", "DEV_MOUTH_009", "DEV_MOUTH_010",
    "DEV_NEAR_001", "DEV_NEAR_002", "DEV_NEAR_007",
    "DEV_HAND_001", "DEV_HAND_002", "DEV_HAND_003", "DEV_HAND_004",
]
REQUIRED_LAYERS = {"RGBA", "DEPTH", "NORMAL", "TRANSMISSION", "SPECULAR"}


def prepare(project: Path) -> dict:
    root = project / "datasets/development/v1"
    if verify_seal(root / "seal.json", project) or admit(root, project, [])["errors"]:
        raise ValueError("Development release must pass admission and seal verification")
    manifest_path = root / "snapshot-manifest.json"
    snapshot = json.loads(manifest_path.read_text())
    cases = {c["case_id"]: c for c in snapshot["cases"]}
    evidence_path = root / "evidence/landmarks.json"
    landmarks = {c["asset_id"]: c for c in json.loads(evidence_path.read_text())["assets"]}
    master_path = safe_path(project, snapshot["product_master_manifest"])
    master = json.loads(master_path.read_text())
    products = []
    for view in master["views"]:
        if {out["layer"] for out in view["outputs"]} != REQUIRED_LAYERS:
            raise ValueError("product view lacks mandatory material layers")
        for out in view["outputs"]:
            if sha256_file(safe_path(project, out["path"])) != out["sha256"]:
                raise ValueError("product master layer hash mismatch")
        products.append({**view, "view_yaw": view["yaw"], "view_pitch": view["pitch"],
                         "max_residual_yaw": 12, "max_residual_pitch": 8})
    selected = []
    for case_id in CASE_IDS:
        case, evidence = cases[case_id], landmarks[case_id]
        view, residual = choose_product(evidence, products)
        pose = (select_hand(evidence["hand"]["candidates"])["measured_grip_pose_degrees"]
                if case["interaction"] == "HAND_HELD"
                else evidence["face"]["measured_pose_degrees"])
        selected.append({
            "case_id": case_id, "interaction": case["interaction"],
            "pose_zone": case["pose_zone"],
            "case_base": {"path": str(safe_path(root, case["path"]).relative_to(
                project.resolve())), "sha256": case["sha256"]},
            "target_pose": pose, "product_view_id": view["view_id"],
            "product_layers": view["outputs"], "residual": residual,
        })
    counts = dict(Counter(c["interaction"] for c in selected))
    if counts != {"MOUTH": 5, "NEAR_MOUTH": 3, "HAND_HELD": 4}:
        raise ValueError("benchmark interaction quota mismatch")
    if sum(c["pose_zone"] == "YELLOW" for c in selected) < 2:
        raise ValueError("benchmark needs at least two Yellow cases")
    return {
        "plan_version": "1.0.0", "status": "INPUT_SELECTION_PREPARED",
        "gate_decision": None, "source_dataset": "DEVELOPMENT", "formal_data_allowed": False,
        "selection_policy": "Explicit fixed IDs; no output-quality selection",
        "interaction_counts": counts, "cases": selected,
        "repeatability": {"distinct_cases": CASE_IDS[:2] + [CASE_IDS[5]] + CASE_IDS[-2:],
                          "repeats_per_case": 5, "parameter_change_allowed": False},
        "qc_dimensions": ["Product", "Interaction", "Identity", "Scene", "Overall"],
        "run_requirements": ["PINNED_PROVIDER_MODEL_REGION_AND_CREDENTIALS",
                             "FROZEN_EDIT_WORKFLOW_AND_IDENTICAL_MASKS_PER_PROVIDER",
                             "PRE_REGISTERED_REPEATABILITY_DECISION_RULE",
                             "RESIDUAL_FAILURES_RESOLVED_OR_DOCUMENTED_ROUTE"],
        "unresolved_residual_cases": [c["case_id"] for c in selected
                                      if not c["residual"]["within_gate"]],
        "provider_execution_performed": False,
        "evidence": [{"path": str(p.resolve().relative_to(project.resolve())),
                      "sha256": sha256_file(p)} for p in
                     (manifest_path, evidence_path, master_path, root / "seal.json")],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(args.project_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(plan, indent=2) + "\n"
    if args.output.exists() and args.output.read_text() != encoded:
        raise ValueError("benchmark plan exists with different inputs; use a new version")
    args.output.write_text(encoded)
    args.output.with_suffix(".json.sha256").write_text(
        f"{sha256_file(args.output)}  {args.output.name}\n"
    )
    print(json.dumps({"status": plan["status"], "case_count": len(plan["cases"]),
                      "unresolved_residual_cases": plan["unresolved_residual_cases"],
                      "provider_execution_performed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
