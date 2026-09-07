import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from interaction_studio_api.domain.resources import (
    AttemptContract,
    EvidenceManifestContract,
    FormalRunContract,
    QCResultContract,
)
from interaction_studio_api.main import app

client = TestClient(app)
HASH = "a" * 64


def test_openapi_exposes_all_eight_core_resources() -> None:
    schema = client.get("/openapi.json").json()["components"]["schemas"]

    assert {
        "DatasetContract",
        "CaseContract",
        "DatasetRunContract",
        "AttemptContract",
        "OutputContract",
        "QCResultContract",
        "GateResultContract",
        "FormalRunContract",
        "EvidenceManifestContract",
    }.issubset(schema)


def test_attempt_contract_requires_exactly_one_run() -> None:
    with pytest.raises(ValidationError):
        AttemptContract(
            attempt_id="attempt-1",
            formal_run_id=None,
            dataset_run_id=None,
            case_id="case-1",
            business_attempt_no=1,
            state="CREATED",
            request_hash=HASH,
            idempotency_key="idempotency-1",
            resource_version=1,
            infra_retry_count=0,
        )


def test_qc_pass_requires_all_five_dimensions() -> None:
    with pytest.raises(ValidationError):
        QCResultContract(
            qc_result_id="qc-1",
            formal_run_id="formal-1",
            output_id="output-1",
            qc_protocol_version="qc-v1",
            reviewer_id="reviewer-1",
            decision="PASS",
            identity_pass=True,
            product_pass=True,
            interaction_pass=False,
            geometry_pass=True,
            artifact_pass=True,
            failure_codes=["INTERACTION_FAIL"],
            result_sha256=HASH,
        )


def test_completed_formal_run_cannot_self_supersede() -> None:
    with pytest.raises(ValidationError):
        FormalRunContract(
            formal_run_id="formal-1",
            dataset_manifest_hash=HASH,
            build_id="build-1",
            qc_protocol_version="qc-v1",
            analysis_spec_sha256=HASH,
            state="COMPLETED",
            resource_version=2,
            supersedes_run_id="formal-1",
        )


def test_ready_evidence_requires_lock() -> None:
    with pytest.raises(ValidationError):
        EvidenceManifestContract(
            evidence_manifest_id="evidence-1",
            formal_run_id="formal-1",
            manifest_sha256=HASH,
            chain_head_sha256=HASH,
            status="READY",
            object_refs=["s3://bucket/object?version=1"],
            object_lock_verified=False,
        )


def test_formal_invalidation_requires_reason() -> None:
    run = FormalRunContract(
        formal_run_id="formal-1",
        dataset_manifest_hash=HASH,
        build_id="build-1",
        qc_protocol_version="qc-v1",
        analysis_spec_sha256=HASH,
        state="INVALIDATED",
        resource_version=2,
        invalidation_reason="provider drift",
    )

    assert run.invalidation_reason == "provider drift"
