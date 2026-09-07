import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from interaction_studio_api.config import Settings, get_settings
from interaction_studio_api.main import app

PROJECT = Path(__file__).parents[3]


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=PROJECT)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_settings, None)


@pytest.mark.parametrize("dataset,count", [("development", 30), ("validation", 20)])
def test_release_summary_verifies_seal_and_hides_case_content(client, dataset, count):
    response = client.get(f"/api/v1/datasets/{dataset}/release")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY"
    assert body["case_count"] == count
    assert body["seal_verified"] is True
    assert body["full_implementation_allowed"] is False
    assert body["formal_eligible"] is False
    assert "cases" not in body and "evidence" not in body and "path" not in body


def test_formal_is_not_a_release_endpoint(client):
    assert client.get("/api/v1/datasets/formal/release").status_code == 422


def test_missing_release_fails_closed(client, tmp_path):
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=tmp_path)
    response = client.get("/api/v1/datasets/development/release")
    assert response.status_code == 503
    assert str(tmp_path) not in response.text


def test_changed_admission_cannot_publish_ready(client, tmp_path):
    # Only small metadata files are copied; evidence still has original hashes.
    root = tmp_path / "datasets/development/v1"
    (root / "evidence").mkdir(parents=True)
    for name in ("snapshot-manifest.json", "seal.json", "evidence/admission.json"):
        shutil.copy2(PROJECT / "datasets/development/v1" / name, root / name)
    report_path = root / "evidence/admission.json"
    report = json.loads(report_path.read_text())
    report["status"] = "BLOCKED"
    report["errors"] = ["REVIEW_FAILED"]
    report_path.write_text(json.dumps(report))
    app.dependency_overrides[get_settings] = lambda: Settings(artifact_root=tmp_path)
    response = client.get("/api/v1/datasets/development/release")
    assert response.status_code == 200
    assert response.json()["status"] == "BLOCKED"
