import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

TOOLS = Path(__file__).parents[3] / "tools"
sys.path.insert(0, str(TOOLS))
admission = importlib.import_module("admit_dataset")
snapshot_tool = importlib.import_module("build_dataset_snapshot")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


@pytest.fixture
def inventory(tmp_path):
    root = tmp_path / "datasets/development/v1"
    root.mkdir(parents=True)
    canonical = tmp_path / "assets/production/character/v1/character_front_v1.png"
    canonical.parent.mkdir(parents=True)
    Image.new("RGB", (16, 16), "red").save(canonical)
    Image.new("RGB", (16, 16), "blue").save(root / "base.png")
    canonical_hash = admission.sha256_file(canonical)
    index = {
        "dataset": "DEVELOPMENT", "dataset_version": "v1", "target_case_count": 1,
        "character_id": "C", "character_canonical_sha256": canonical_hash,
        "product_sku": "P", "product_master_manifest": "master.json",
        "cases": [{"case_id": "D1", "path": "base.png", "interaction": "MOUTH",
                   "pose_zone": "GREEN", "prompt_id": "P1", "generation_job_id": "J1",
                   "prompt_family": "DEV"}],
    }
    write_json(root / "case-index.json", index)
    snapshot = snapshot_tool.build_snapshot(root / "case-index.json", root)
    write_json(root / "snapshot-manifest.json", snapshot)
    digest = admission.sha256_file(root / "snapshot-manifest.json")
    write_json(tmp_path / "datasets/registry/v1/dataset-plan.json", {"datasets": [{
        "dataset": "DEVELOPMENT", "case_count": 1, "interaction_counts": {"MOUTH": 1},
        "pose_counts": {"GREEN": 1, "YELLOW": 0, "RED": 0}, "prompt_family": "DEV",
    }]})
    write_json(tmp_path / "workers/landmarks/models.json", {
        "models": [{"filename": "face.task", "sha256": "a" * 64}],
    })
    write_json(root / "evidence/landmarks.json", {
        "manifest_sha256": digest, "model_sha256": {"face.task": "a" * 64},
        "analyzer": "MediaPipe Tasks Vision 0.10.35", "assets": [{
            "asset_id": "D1", "face": {"detected": True, "candidate_count": 1,
                "landmark_count": 478, "measured_pose_degrees": {"yaw": 0, "pitch": 0}},
        }],
    })
    (root / "PROMPTS.md").write_text("Independent job J1 prompt P1")
    write_json(root / "evidence/visual-review.json", {
        "manifest_sha256": digest, "canonical_sha256": canonical_hash,
        "reviewer": "engineer", "reviewed_at": "2026-09-05T00:00:00Z",
        "lineage_paths": ["PROMPTS.md"], "cases": [{
            "case_id": "D1", "asset_sha256": snapshot["cases"][0]["sha256"],
            "identity_consistent": True, "product_absent": True,
            "mouth_visible": True, "anatomy_natural": True,
        }],
    })
    return tmp_path, root


def test_count_complete_is_not_admission(inventory):
    project, root = inventory
    snapshot = json.loads((root / "snapshot-manifest.json").read_text())
    assert snapshot["readiness_status"] == "CANDIDATE_COMPLETE"
    assert admission.admit(root, project, [])["status"] == "READY"
    path = root / "evidence/visual-review.json"
    review = json.loads(path.read_text())
    review["cases"][0]["identity_consistent"] = False
    write_json(path, review)
    assert admission.admit(root, project, [])["status"] == "BLOCKED"


@pytest.mark.parametrize("yaw,pitch,expected", [
    (45, 15, "GREEN"), (45.01, 0, "YELLOW"), (0, 15.01, "YELLOW"),
    (-60, -25, "YELLOW"), (60.01, 0, "RED"), (0, -25.01, "RED"),
])
def test_frozen_pose_boundaries(yaw, pitch, expected):
    assert admission.pose_zone({"yaw": yaw, "pitch": pitch}) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_pose_is_rejected(value):
    with pytest.raises(ValueError):
        admission.pose_zone({"yaw": value, "pitch": 0})


def test_actual_pose_overrides_declared_green(inventory):
    project, root = inventory
    path = root / "evidence/landmarks.json"
    data = json.loads(path.read_text())
    data["assets"][0]["face"]["measured_pose_degrees"]["yaw"] = 70
    write_json(path, data)
    errors = admission.admit(root, project, [])["errors"]
    assert "D1: POSE_MISMATCH_OR_RED" in errors
    assert "MEASURED_POSE_QUOTA_MISMATCH" in errors


def test_changed_image_invalidates_snapshot_and_review(inventory):
    project, root = inventory
    Image.new("RGB", (16, 16), "green").save(root / "base.png")
    errors = admission.admit(root, project, [])["errors"]
    assert "SNAPSHOT_STALE_OR_ASSET_CHANGED" in errors
    assert "D1: REVIEW_ASSET_HASH_MISMATCH" in errors


def test_unbound_landmark_report_is_rejected(inventory):
    project, root = inventory
    path = root / "evidence/landmarks.json"
    data = json.loads(path.read_text())
    data["manifest_sha256"] = "0" * 64
    data["model_sha256"] = {}
    write_json(path, data)
    errors = admission.admit(root, project, [])["errors"]
    assert "LANDMARK_NOT_BOUND_TO_SNAPSHOT" in errors
    assert "UNPINNED_LANDMARK_MODELS" in errors


def test_seal_detects_changed_object(inventory):
    project, root = inventory
    asset = root / "base.png"
    seal_path = root / "seal.json"
    write_json(seal_path, {"evidence": [{
        "path": str(asset.relative_to(project)), "sha256": admission.sha256_file(asset),
    }]})
    assert admission.verify_seal(seal_path, project) == []
    asset.write_bytes(b"tampered")
    assert admission.verify_seal(seal_path, project)


def test_development_release_is_ready_and_unchanged():
    project = Path(__file__).parents[3]
    root = project / "datasets/development/v1"
    assert admission.admit(root, project, [])["errors"] == []
    assert admission.verify_seal(root / "seal.json", project) == []


def test_cross_dataset_reused_image_and_jobs_are_rejected(inventory):
    project, root = inventory
    peer = project / "datasets/validation/v1"
    peer.mkdir(parents=True)
    shutil.copy2(root / "base.png", peer / "base.png")
    index = json.loads((root / "case-index.json").read_text())
    index["dataset"] = "VALIDATION"
    write_json(peer / "case-index.json", index)
    write_json(peer / "snapshot-manifest.json", snapshot_tool.build_snapshot(
        peer / "case-index.json", peer))
    errors = admission.admit(root, project, [peer])["errors"]
    assert "CROSS_DATASET_REUSE_SHA256" in errors
    assert "CROSS_DATASET_REUSE_GENERATION_JOB_ID" in errors


def test_empty_seal_is_not_valid(inventory):
    project, root = inventory
    write_json(root / "seal.json", {"evidence": []})
    assert admission.verify_seal(root / "seal.json", project) == ["SEAL_EVIDENCE_EMPTY"]


def test_rebuilding_sealed_dataset_with_changed_inputs_is_rejected(inventory, monkeypatch):
    _, root = inventory
    output = root / "snapshot-manifest.json"
    original = output.read_bytes()
    write_json(root / "seal.json", {"sealed": True})
    index = json.loads((root / "case-index.json").read_text())
    index["cases"][0]["generation_job_id"] = "CHANGED"
    write_json(root / "case-index.json", index)
    monkeypatch.setattr(sys, "argv", ["build_dataset_snapshot.py", str(root / "case-index.json"),
        "--dataset-root", str(root), "--output", str(output)])
    with pytest.raises(ValueError, match="sealed dataset"):
        snapshot_tool.main()
    assert output.read_bytes() == original


def test_validation_release_is_independent_and_sealed():
    project = Path(__file__).parents[3]
    root = project / "datasets/validation/v1"
    report = admission.admit(root, project, [project / "datasets/development/v1"])
    assert report["errors"] == []
    assert report["measured_pose_counts"] == {"GREEN": 16, "YELLOW": 4}
    assert admission.verify_seal(root / "seal.json", project) == []
