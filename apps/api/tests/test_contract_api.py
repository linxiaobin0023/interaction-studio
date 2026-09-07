from fastapi.testclient import TestClient

from interaction_studio_api.main import app

client = TestClient(app)


def transition_payload(current: str, target: str, *, is_formal: bool = True) -> dict:
    return {
        "current_state": current,
        "target_state": target,
        "is_formal": is_formal,
        "expected_resource_version": 1,
        "idempotency_key": "idem-0001",
        "request_id": "request-0001",
    }


def test_contract_exposes_state_machines() -> None:
    response = client.get("/api/v1/contracts/state-machines")

    assert response.status_code == 200
    assert response.json()["formal_run"]["COMPLETED"] == []
    assert "VALID_OUTPUT" in response.json()["attempt"]


def test_valid_attempt_transition() -> None:
    response = client.post(
        "/api/v1/contracts/attempt-transitions/validate",
        json=transition_payload("CREATED", "PREPARED"),
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_formal_attempt_cancel_returns_auditable_conflict() -> None:
    response = client.post(
        "/api/v1/contracts/attempt-transitions/validate",
        json=transition_payload("CREATED", "CANCELLED"),
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INVALID_STATE_TRANSITION"
    assert error["machine"] == "attempt"
    assert "CANCELLED" not in error["allowed_states"]


def test_completed_formal_run_cannot_restart() -> None:
    payload = transition_payload("COMPLETED", "RUNNING")
    payload.pop("is_formal")

    response = client.post(
        "/api/v1/contracts/formal-run-transitions/validate",
        json=payload,
    )

    assert response.status_code == 409
    assert response.json()["error"]["allowed_states"] == []


def test_transition_contract_requires_concurrency_fields() -> None:
    payload = transition_payload("CREATED", "PREPARED")
    payload.pop("expected_resource_version")

    response = client.post(
        "/api/v1/contracts/attempt-transitions/validate",
        json=payload,
    )

    assert response.status_code == 422


def test_openapi_is_31_and_has_named_operations() -> None:
    schema = client.get("/openapi.json").json()

    assert schema["openapi"].startswith("3.1.")
    operation = schema["paths"]["/api/v1/contracts/attempt-transitions/validate"]["post"]
    assert operation["operationId"] == "validateAttemptTransition"
