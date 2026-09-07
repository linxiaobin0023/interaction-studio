"""Admit Development/Validation inventories using bound local evidence; seal once."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from build_dataset_snapshot import build_snapshot, safe_path, sha256_file


def pose_zone(pose: dict) -> str:
    yaw, pitch = abs(float(pose["yaw"])), abs(float(pose["pitch"]))
    if not all(math.isfinite(x) for x in (yaw, pitch)):
        raise ValueError("nonfinite pose")
    if yaw > 60 or pitch > 25:
        return "RED"
    return "GREEN" if yaw <= 45 and pitch <= 15 else "YELLOW"


def unique_map(items: list[dict], key: str) -> dict:
    result = {item[key]: item for item in items}
    if len(result) != len(items):
        raise ValueError(f"duplicate {key}")
    return result


def admit(root: Path, project_root: Path, peer_roots: list[Path]) -> dict:
    """Read only explicitly supplied non-Formal roots. Return all admission failures."""
    snapshot_path = root / "snapshot-manifest.json"
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot["dataset"] not in {"DEVELOPMENT", "VALIDATION"}:
        raise ValueError("admission is restricted to Development/Validation")
    errors: list[str] = []
    plan_path = project_root / "datasets/registry/v1/dataset-plan.json"
    plan = json.loads(plan_path.read_text())
    quota = next(d for d in plan["datasets"] if d["dataset"] == snapshot["dataset"])
    actual = build_snapshot(root / "case-index.json", root)
    if actual != snapshot:
        errors.append("SNAPSHOT_STALE_OR_ASSET_CHANGED")
    if (actual["actual_case_count"] != quota["case_count"]
            or actual["target_case_count"] != quota["case_count"]):
        errors.append("CASE_QUOTA_INCOMPLETE")
    if actual["interaction_counts"] != quota["interaction_counts"]:
        errors.append("INTERACTION_QUOTA_MISMATCH")
    cases = unique_map(actual["cases"], "case_id")
    for key in ("prompt_id", "generation_job_id"):
        unique_map(actual["cases"], key)
    evidence_path = root / "evidence/landmarks.json"
    review_path = root / "evidence/visual-review.json"
    evidence = json.loads(evidence_path.read_text())
    review = json.loads(review_path.read_text())
    expected_hash = sha256_file(snapshot_path)
    for label, data in (("LANDMARK", evidence), ("REVIEW", review)):
        if data.get("manifest_sha256") != expected_hash:
            errors.append(f"{label}_NOT_BOUND_TO_SNAPSHOT")
    model_path = project_root / "workers/landmarks/models.json"
    models = json.loads(model_path.read_text())["models"]
    if evidence.get("model_sha256") != {m["filename"]: m["sha256"] for m in models}:
        errors.append("UNPINNED_LANDMARK_MODELS")
    if evidence.get("analyzer") != "MediaPipe Tasks Vision 0.10.35":
        errors.append("UNPINNED_LANDMARK_ANALYZER")
    if not review.get("reviewer") or not review.get("reviewed_at"):
        errors.append("REVIEW_ATTRIBUTION_MISSING")
    canonical = project_root / "assets/production/character/v1/character_front_v1.png"
    if not (sha256_file(canonical) == actual["character_canonical_sha256"]
            == review.get("canonical_sha256")):
        errors.append("CANONICAL_IDENTITY_HASH_MISMATCH")
    landmarks = unique_map(evidence["assets"], "asset_id")
    reviews = unique_map(review["cases"], "case_id")
    if set(cases) != set(landmarks) or set(cases) != set(reviews):
        errors.append("EVIDENCE_CASE_SET_MISMATCH")
    measured: Counter = Counter()
    for case_id, case in cases.items():
        face = landmarks.get(case_id, {}).get("face", {})
        if not (face.get("detected") and face.get("candidate_count") == 1
                and face.get("landmark_count", 0) >= 478):
            errors.append(f"{case_id}: FACE_NOT_SINGLE_OR_COMPLETE")
        try:
            zone = pose_zone(face["measured_pose_degrees"])
            measured[zone] += 1
            if zone != case["pose_zone"] or zone == "RED":
                errors.append(f"{case_id}: POSE_MISMATCH_OR_RED")
        except (KeyError, ValueError, TypeError):
            errors.append(f"{case_id}: POSE_MISSING_OR_INVALID")
        item = reviews.get(case_id, {})
        checks = ["identity_consistent", "product_absent", "mouth_visible", "anatomy_natural"]
        if case["interaction"] == "HAND_HELD":
            checks += ["five_fingers", "grip_space_usable"]
            hand = landmarks.get(case_id, {}).get("hand", {})
            if not (hand.get("detected") and any(
                c.get("landmark_count") == 21 for c in hand.get("candidates", [])
            )):
                errors.append(f"{case_id}: HAND_LANDMARKS_MISSING")
        if item.get("asset_sha256") != case["sha256"]:
            errors.append(f"{case_id}: REVIEW_ASSET_HASH_MISMATCH")
        if any(item.get(check) is not True for check in checks):
            errors.append(f"{case_id}: VISUAL_REVIEW_INCOMPLETE_OR_FAILED")
        if case.get("prompt_family", quota["prompt_family"]) != quota["prompt_family"]:
            errors.append(f"{case_id}: PROMPT_FAMILY_MISMATCH")
    if dict(measured) != {k: v for k, v in quota["pose_counts"].items() if v}:
        errors.append("MEASURED_POSE_QUOTA_MISMATCH")
    peers = []
    for peer_root in peer_roots:
        peer_path = peer_root / "snapshot-manifest.json"
        peer = json.loads(peer_path.read_text())
        if peer["dataset"] not in {"DEVELOPMENT", "VALIDATION"}:
            raise ValueError("Formal/Generalization cannot be used as admission peers")
        if peer["dataset"] == actual["dataset"]:
            raise ValueError("peer must belong to the other dataset")
        if build_snapshot(peer_root / "case-index.json", peer_root) != peer:
            errors.append("PEER_SNAPSHOT_STALE")
        for key in ("sha256", "case_id", "prompt_id", "generation_job_id"):
            if {c[key] for c in actual["cases"]} & {c[key] for c in peer["cases"]}:
                errors.append(f"CROSS_DATASET_REUSE_{key.upper()}")
        peers.append({"dataset": peer["dataset"], "manifest_sha256": sha256_file(peer_path)})
    if snapshot["dataset"] == "VALIDATION" and not peers:
        errors.append("VALIDATION_REQUIRES_DEVELOPMENT_INDEPENDENCE_CHECK")
    refs = [snapshot_path, root / "case-index.json", evidence_path, review_path,
            plan_path, model_path, canonical]
    for relative in review.get("lineage_paths", []):
        refs.append(safe_path(root, relative))
    if not review.get("lineage_paths"):
        errors.append("GENERATION_LINEAGE_MISSING")
    return {
        "report_version": "1.0.0", "dataset": snapshot["dataset"],
        "status": "READY" if not errors else "BLOCKED", "errors": errors,
        "manifest_sha256": expected_hash, "case_count": len(cases),
        "interaction_counts": actual["interaction_counts"], "measured_pose_counts": dict(measured),
        "peers": peers, "formal_eligible": False,
        "limitations": ["Visual identity/anatomy review is engineering review, not Formal QC.",
                        "Independence uses hashes and generation lineage; no semantic proof.",
                        "Built-in image generation is not a pinned inference benchmark."],
        "evidence": [{"path": str(p.resolve().relative_to(project_root.resolve())),
                      "sha256": sha256_file(p)} for p in refs],
    }


def verify_seal(seal_path: Path, project_root: Path) -> list[str]:
    seal = json.loads(seal_path.read_text())
    if not seal.get("evidence"):
        return ["SEAL_EVIDENCE_EMPTY"]
    errors = []
    for ref in seal["evidence"]:
        path = safe_path(project_root, ref["path"])
        if not path.is_file() or sha256_file(path) != ref["sha256"]:
            errors.append(f"SEALED_OBJECT_CHANGED: {ref['path']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--peer", type=Path, action="append", default=[])
    parser.add_argument("--seal", action="store_true")
    parser.add_argument("--verify-seal", action="store_true")
    args = parser.parse_args()
    seal_path = args.root / "seal.json"
    if args.verify_seal:
        errors = verify_seal(seal_path, args.project_root)
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
        return int(bool(errors))
    report = admit(args.root, args.project_root, args.peer)
    if seal_path.exists():
        raise ValueError("dataset already sealed; use --verify-seal or create a new version")
    report_path = args.root / "evidence/admission.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    if args.seal and report["status"] == "READY":
        snapshot = json.loads((args.root / "snapshot-manifest.json").read_text())
        refs = report["evidence"] + [{
            "path": str(report_path.resolve().relative_to(args.project_root.resolve())),
            "sha256": sha256_file(report_path),
        }] + [{"path": str(safe_path(args.root, c["path"]).relative_to(
            args.project_root.resolve())), "sha256": c["sha256"]} for c in snapshot["cases"]]
        seal = {"seal_version": "1.0.0", "dataset": report["dataset"],
                "sealed_at": datetime.now(UTC).isoformat(), "sealed_by": "CODEX_PROJECT_LEAD",
                "manifest_sha256": report["manifest_sha256"], "evidence": refs,
                "storage_guarantee": "LOCAL_HASH_SEAL_NOT_OBJECT_LOCK",
                "parameter_selection_started": False, "formal_eligible": False}
        with seal_path.open("x") as stream:
            stream.write(json.dumps(seal, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "evidence"}, indent=2))
    return int(report["status"] != "READY")


if __name__ == "__main__":
    raise SystemExit(main())
