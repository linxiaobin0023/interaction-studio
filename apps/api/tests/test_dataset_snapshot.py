import hashlib
import json
from pathlib import Path


def test_development_snapshot_reports_actual_progress() -> None:
    project_root = Path(__file__).parents[3]
    snapshot = json.loads(
        (project_root / "datasets/development/v1/snapshot-manifest.json").read_text()
    )

    assert snapshot["readiness_status"] == "CANDIDATE_COMPLETE"
    assert snapshot["actual_case_count"] == 30
    assert snapshot["target_case_count"] == 30
    assert snapshot["remaining_case_count"] == 0
    assert snapshot["interaction_counts"] == {
        "HAND_HELD": 10,
        "MOUTH": 12,
        "NEAR_MOUTH": 8,
    }
    assert len({item["sha256"] for item in snapshot["cases"]}) == 30


def test_development_landmarks_are_bound_and_complete() -> None:
    project_root = Path(__file__).parents[3]
    snapshot_path = project_root / "datasets/development/v1/snapshot-manifest.json"
    evidence = json.loads(
        (project_root / "datasets/development/v1/evidence/landmarks.json").read_text()
    )
    assert evidence["manifest_sha256"] == hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    assert len(evidence["assets"]) == 30
    assert all(item["face"]["landmark_count"] >= 478 for item in evidence["assets"])
