import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_studio import PROJECT
from test_studio import storage as studio_storage

from interaction_studio_api.domain import studio_jobs as jobs
from interaction_studio_api.models import StudioJob, StudioJobOutput, StudioReview

storage = studio_storage

URL = "/api/v1/development/studio/jobs"


def submit(client, case="DEV_MOUTH_001", key=None, **parameters):
    return client.post(URL, json={"idempotency_key": key or str(uuid4()),
                                 "parameters": {"case_id": case, **parameters}})


def successful(client, engine):
    response = submit(client)
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    assert jobs.run_one(sessionmaker(engine), PROJECT)
    detail = client.get(f"{URL}/{job_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["state"] == "SUCCEEDED", detail.text
    return detail.json()


def review_body(detail, version=0):
    return {"expected_version": version, "output_sha256": detail["output_sha256"],
            "dimensions": {key: {"decision": "PASS"} for key in jobs.DIMENSIONS}}


def test_queue_survives_session_and_worker_persists_verified_bundle(storage):
    client, engine = storage
    response = submit(client)
    job_id = response.json()["id"]
    with Session(engine) as session:
        assert session.get(StudioJob, job_id).state == "QUEUED"
    assert client.get(f"{URL}/{job_id}/output").status_code == 409
    assert jobs.run_one(sessionmaker(engine), PROJECT)
    detail = client.get(f"{URL}/{job_id}").json()
    assert detail["state"] == "SUCCEEDED" and detail["execution_count"] == 1
    assert detail["provider_execution_performed"] is False and detail["formal_eligible"] is False
    output = client.get(f"{URL}/{job_id}/output")
    assert hashlib.sha256(output.content).hexdigest() == detail["output_sha256"]
    assert client.get(f"{URL}/{job_id}/output?format=png").content.startswith(b"\x89PNG")
    assert not jobs.run_one(sessionmaker(engine), PROJECT)


def test_idempotency_replay_and_conflicting_parameters(storage):
    client, engine = storage
    key = str(uuid4())
    one, two = submit(client, key=key), submit(client, key=key)
    assert one.json()["id"] == two.json()["id"]
    assert submit(client, key=key, contact_radius_px=20).status_code == 409
    with Session(engine) as session:
        assert len(session.scalars(select(StudioJob)).all()) == 1


def test_failed_geometry_is_terminal_and_cannot_be_reviewed(storage):
    client, engine = storage
    job_id = submit(client, case="DEV_MOUTH_011").json()["id"]
    assert jobs.run_one(sessionmaker(engine), PROJECT)
    detail = client.get(f"{URL}/{job_id}").json()
    assert detail["state"] == "FAILED" and detail["error_code"] == "PRODUCT_RESIDUAL_EXCEEDED"
    assert client.get(f"{URL}/{job_id}/output").status_code == 409
    body = review_body(detail) | {"output_sha256": "a" * 64}
    assert client.post(f"{URL}/{job_id}/reviews", json=body).status_code == 409


def test_expired_lease_recovery_fences_old_worker_and_bounds_retries(storage):
    client, engine = storage
    job_id = submit(client).json()["id"]
    start = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        first = jobs.claim_job(session, start)
    with Session(engine) as session, session.begin():
        assert jobs.claim_job(session, start + timedelta(minutes=1)) is None
        second = jobs.claim_job(session, start + timedelta(minutes=6))
        assert second["token"] != first["token"]
    with Session(engine) as session, session.begin():
        assert not jobs.finish_job(session, first, error_code="STALE_WORKER")
        assert jobs.claim_job(session, start + timedelta(minutes=12))
    with Session(engine) as session, session.begin():
        assert jobs.claim_job(session, start + timedelta(minutes=18)) == {"exhausted": True}
    detail = client.get(f"{URL}/{job_id}").json()
    assert detail["execution_count"] == 3 and detail["error_code"] == "WORKER_RETRY_EXHAUSTED"


def test_changed_sources_and_tampered_request_fail_closed(storage, monkeypatch):
    client, engine = storage
    job_id = submit(client).json()["id"]
    render = jobs.render_preview

    def changed(*args):
        manifest, files = render(*args)
        manifest["sources"]["case_base_sha256"] = "0" * 64
        return manifest, files

    monkeypatch.setattr(jobs, "render_preview", changed)
    jobs.run_one(sessionmaker(engine), PROJECT)
    assert client.get(f"{URL}/{job_id}").json()["error_code"] == "JOB_SOURCE_CHANGED"
    second = submit(client).json()["id"]
    with Session(engine) as session, session.begin():
        session.get(StudioJob, second).request_hash = "0" * 64
    jobs.run_one(sessionmaker(engine), PROJECT)
    assert client.get(f"{URL}/{second}").json()["error_code"] == "JOB_REQUEST_INTEGRITY_FAILED"


def test_five_dimensions_are_required_and_failed_dimension_requires_reason(storage):
    client, engine = storage
    detail = successful(client, engine)
    url = f"{URL}/{detail['id']}/reviews"
    body = review_body(detail)
    del body["dimensions"]["scene"]
    assert client.post(url, json=body).status_code == 422
    body = review_body(detail)
    body["dimensions"]["interaction"] = {"decision": "FAIL", "reason": "  "}
    assert client.post(url, json=body).status_code == 422
    body["dimensions"]["interaction"]["reason"] = "接触关系不自然"
    response = client.post(url, json=body)
    assert response.status_code == 201 and response.json()["decision"] == "FAIL"
    assert response.json()["scope"] == "LOCAL_DEVELOPMENT_ONLY"


def test_qc_versions_output_binding_and_hash_chain(storage):
    client, engine = storage
    detail = successful(client, engine)
    url = f"{URL}/{detail['id']}/reviews"
    wrong = review_body(detail) | {"output_sha256": "0" * 64}
    assert client.post(url, json=wrong).status_code == 409
    first = client.post(url, json=review_body(detail))
    assert first.status_code == 201 and first.json()["decision"] == "PASS"
    assert client.post(url, json=review_body(detail)).status_code == 409
    second = client.post(url, json=review_body(detail, 1))
    assert second.status_code == 201
    assert second.json()["previous_hash"] == first.json()["content_sha256"]
    loaded = client.get(f"{URL}/{detail['id']}").json()
    assert len(loaded["reviews"]) == 2
    with Session(engine) as session, session.begin():
        session.delete(session.scalar(select(StudioReview).where(StudioReview.version == 2)))
    assert client.get(f"{URL}/{detail['id']}").status_code == 503
    assert client.post(url, json=review_body(detail, 1)).status_code == 503


@pytest.mark.parametrize("target", ["bundle", "manifest", "review"])
def test_corruption_blocks_result_and_qc(storage, target):
    client, engine = storage
    detail = successful(client, engine)
    url = f"{URL}/{detail['id']}"
    assert client.post(url + "/reviews", json=review_body(detail)).status_code == 201
    with Session(engine) as session, session.begin():
        output = session.get(StudioJobOutput, detail["id"])
        if target == "bundle":
            output.bundle = b"corrupt"
        elif target == "manifest":
            output.manifest = {"tampered": True}
        else:
            session.scalar(select(StudioReview)).content_sha256 = "0" * 64
    assert client.get(url).status_code == 503
    assert client.post(url + "/reviews", json=review_body(detail, 1)).status_code == 503
    if target != "review":
        assert client.get(url + "/output").status_code == 503


def test_case_scope_and_pagination(storage):
    client, _ = storage
    assert submit(client, case="VAL_MOUTH_001").status_code == 422
    assert submit(client, case="DEV_MOUTH_999").status_code == 404
    submit(client)
    submit(client)
    submit(client, case="DEV_HAND_001")
    one = client.get(URL + "?case_id=DEV_MOUTH_001&limit=1").json()
    two = client.get(URL + "?case_id=DEV_MOUTH_001&limit=1&offset=1").json()
    assert one["has_more"] and not two["has_more"]
    assert one["jobs"][0]["id"] != two["jobs"][0]["id"]
    assert client.get(URL + "?case_id=VAL_MOUTH_001").status_code == 422
    assert client.get(URL + f"/{uuid4()}").status_code == 404


def test_portable_evidence_replay_and_tamper_rejection(storage):
    import io
    import json
    import zipfile

    from interaction_studio_api.domain.local_preview import PreviewProblem, bundle_bytes
    from interaction_studio_api.domain.studio_evidence import verify_evidence

    client, engine = storage
    detail = successful(client, engine)
    url = f"{URL}/{detail['id']}"
    assert client.post(url + "/reviews", json=review_body(detail)).status_code == 201
    package = client.get(url + "/evidence")
    assert package.status_code == 200
    assert verify_evidence(package.content)["review_count"] == 1
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    records = json.loads(files["reviews.json"])
    records[0]["decision"] = "FAIL"
    files["reviews.json"] = json.dumps(records).encode()
    with pytest.raises(PreviewProblem, match="EVIDENCE_INTEGRITY_FAILED"):
        verify_evidence(bundle_bytes(files))


def test_corrected_product_revision_is_bound_through_worker_and_download(storage):
    client, engine = storage
    key = str(uuid4())
    response = submit(client, key=key, product_revision="v2")
    assert response.status_code == 202
    job = response.json()
    assert job["parameters"]["product_revision"] == "v2"
    assert jobs.run_one(sessionmaker(engine), PROJECT)
    detail = client.get(f"{URL}/{job['id']}").json()
    assert detail["state"] == "SUCCEEDED"
    assert detail["sources"] == job["sources"]
    assert client.get(f"{URL}/{job['id']}/output").status_code == 200
    assert submit(client, key=key, product_revision="v1").status_code == 409


def test_console_summary_empty_and_global_task_pagination(storage):
    client, _ = storage
    response = client.get(URL + "/summary")
    assert response.status_code == 200
    empty = response.json()
    assert empty["counts"] == {"QUEUED": 0, "RUNNING": 0, "SUCCEEDED": 0, "FAILED": 0}
    assert empty["queue"] == [] and empty["recent_failures"] == []
    assert empty["pending_review"] == 0
    assert all(m["rate"] is None and m["reviewed"] == 0 for m in empty["quality"].values())
    for metric in ("technical_pass_rate", "attempt1_pass_rate", "average_manual_seconds"):
        assert empty[metric] is None
    first = submit(client).json()["id"]
    second = submit(client, case="DEV_HAND_001").json()["id"]
    one = client.get(URL + "?state=QUEUED&limit=1").json()
    two = client.get(URL + "?state=QUEUED&limit=1&offset=1").json()
    assert one["has_more"] and not two["has_more"]
    assert {one["jobs"][0]["id"], two["jobs"][0]["id"]} == {first, second}
    assert one["jobs"][0]["review_version"] == 0
    assert client.get(URL + "?state=SUCCEEDED").json()["jobs"] == []
    assert client.get(URL + "?state=INVALID").status_code == 422
    summary = client.get(URL + "/summary").json()
    assert summary["counts"]["QUEUED"] == 2 and len(summary["queue"]) == 2


def test_console_quality_counts_latest_review_once_and_preserves_integrity(storage):
    client, engine = storage
    detail = successful(client, engine)
    assert client.get(URL + "/summary").json()["pending_review"] == 1
    url = f"{URL}/{detail['id']}/reviews"
    assert client.post(url, json=review_body(detail)).status_code == 201
    amended = review_body(detail, 1)
    amended["dimensions"]["interaction"] = {"decision": "FAIL", "reason": "接触不自然"}
    assert client.post(url, json=amended).status_code == 201
    result = client.get(URL + "/summary").json()
    assert result["pending_review"] == 0
    assert result["quality"]["interaction"] == {"passed": 0, "reviewed": 1, "rate": 0.0}
    assert result["quality"]["product"] == {"passed": 1, "reviewed": 1, "rate": 100.0}
    failed_id = submit(client, case="DEV_MOUTH_011").json()["id"]
    assert jobs.run_one(sessionmaker(engine), PROJECT)
    result = client.get(URL + "/summary").json()
    assert result["counts"]["FAILED"] == 1
    assert result["recent_failures"][0]["id"] == failed_id
    assert result["quality"]["product"]["reviewed"] == 1
    with Session(engine) as session, session.begin():
        record = session.scalar(select(StudioReview).where(StudioReview.version == 2))
        record.content_sha256 = "0" * 64
    assert client.get(URL + "/summary").status_code == 503
