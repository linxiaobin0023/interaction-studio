from fastapi.testclient import TestClient

from interaction_studio_api.main import app

client = TestClient(app)


def test_live_health() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_rejects_synthetic_formal_manifest() -> None:
    payload = {
        "manifest_version": "0.1.0",
        "pack_id": "bad-formal-pack",
        "created_at": "2026-09-03T00:00:00Z",
        "dataset": "FORMAL",
        "provenance": "SYNTHETIC_MOCK",
        "model_revision": "test",
        "formal_eligible": False,
        "readiness_status": "PASS",
        "character_id": "character",
        "product_sku": "sku",
        "assets": [
            {
                "asset_id": "asset-1",
                "type": "CASE_BASE",
                "path": "case.png",
                "sha256": "0" * 64,
                "width": 64,
                "height": 64,
            }
        ],
    }

    response = client.post("/api/v1/manifests/validate", json=payload)
    assert response.status_code == 422


def test_rejects_invalid_created_at() -> None:
    payload = {
        "manifest_version": "0.1.0",
        "pack_id": "bad-date-pack",
        "created_at": "not-a-date",
        "dataset": "DEVELOPMENT",
        "provenance": "SYNTHETIC_MOCK",
        "model_revision": "test",
        "formal_eligible": False,
        "readiness_status": "PILOT_ONLY",
        "character_id": "character",
        "product_sku": "sku",
        "assets": [
            {
                "asset_id": "asset-1",
                "type": "CASE_BASE",
                "path": "case.png",
                "sha256": "0" * 64,
                "width": 64,
                "height": 64,
            }
        ],
    }

    response = client.post("/api/v1/manifests/validate", json=payload)
    assert response.status_code == 422


def test_rejects_created_at_without_timezone() -> None:
    payload = {
        "manifest_version": "0.1.0",
        "pack_id": "naive-time-pack",
        "created_at": "2026-09-03T10:00:00",
        "dataset": "DEVELOPMENT",
        "provenance": "REAL_DEVELOPMENT",
        "model_revision": "camera",
        "formal_eligible": False,
        "readiness_status": "BLOCKED",
        "character_id": "character",
        "product_sku": "sku",
        "assets": [
            {
                "asset_id": "asset-1",
                "type": "CASE_BASE",
                "path": "case.png",
                "sha256": "0" * 64,
                "width": 64,
                "height": 64,
            }
        ],
    }

    response = client.post("/api/v1/manifests/validate", json=payload)
    assert response.status_code == 422


def test_rejects_path_traversal() -> None:
    payload = {
        "manifest_version": "0.1.0",
        "pack_id": "bad-path-pack",
        "created_at": "2026-09-03T00:00:00Z",
        "dataset": "DEVELOPMENT",
        "provenance": "SYNTHETIC_MOCK",
        "model_revision": "test",
        "formal_eligible": False,
        "readiness_status": "PILOT_ONLY",
        "character_id": "character",
        "product_sku": "sku",
        "assets": [
            {
                "asset_id": "asset-1",
                "type": "CASE_BASE",
                "path": "../case.png",
                "sha256": "0" * 64,
                "width": 64,
                "height": 64,
            }
        ],
    }

    response = client.post("/api/v1/manifests/validate", json=payload)
    assert response.status_code == 422
