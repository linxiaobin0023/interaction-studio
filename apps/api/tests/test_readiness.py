import json
from pathlib import Path

from fastapi.testclient import TestClient

from interaction_studio_api.domain.readiness import (
    ReadinessEvaluationRequest,
    evaluate_readiness,
)
from interaction_studio_api.main import app

client = TestClient(app)


def mock_manifest_payload() -> dict:
    project_root = Path(__file__).parents[3]
    path = project_root / "mock_assets/v0/metadata/asset_manifest.json"
    return json.loads(path.read_text())


def test_mock_pack_clears_manifest_blockers_but_stays_pilot_only() -> None:
    request = ReadinessEvaluationRequest(
        manifest=mock_manifest_payload(),
        hand_in_core_scope=True,
        include_side_views=True,
    )

    result = evaluate_readiness(request)

    assert result.technical_status == "WARN"
    assert result.readiness_status == "PILOT_ONLY"
    assert result.formal_gate_eligible is False
    assert result.blocking_conditions == []


def test_readiness_api_publishes_evidence_not_just_boolean() -> None:
    response = client.post(
        "/api/v1/readiness/evaluations",
        json={
            "manifest": mock_manifest_payload(),
            "hand_in_core_scope": True,
            "include_side_views": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["technical_status"] == "WARN"
    assert len(payload["checks"]) == 10
    alpha_check = next(
        item for item in payload["checks"] if item["check_id"] == "PRODUCT_ALPHA_REQUIRED"
    )
    assert alpha_check["observed"] == "has_alpha assets=6"


def test_disabling_hand_scope_keeps_manifest_without_blockers() -> None:
    request = ReadinessEvaluationRequest(
        manifest=mock_manifest_payload(),
        hand_in_core_scope=False,
        include_side_views=True,
    )

    result = evaluate_readiness(request)

    assert "HAND_BASE_COVERAGE" not in result.blocking_conditions
    assert result.blocking_conditions == []


def test_missing_angle_metadata_becomes_blocker_instead_of_exception() -> None:
    payload = mock_manifest_payload()
    payload["assets"][0].pop("declared_yaw")
    next(
        asset
        for asset in payload["assets"]
        if asset["asset_id"] == "SKU_MOCK_LEFT90_WHITE_00"
    ).pop("view_yaw")
    request = ReadinessEvaluationRequest(manifest=payload)

    result = evaluate_readiness(request)

    assert "CANONICAL_VIEW_COVERAGE" in result.blocking_conditions
    assert "PRODUCT_VIEW_COVERAGE" in result.blocking_conditions
