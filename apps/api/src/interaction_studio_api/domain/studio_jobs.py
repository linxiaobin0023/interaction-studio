"""Development-only queue and QC. No provider calls, formal attempts or gate decisions."""

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import StudioJob, StudioJobOutput, StudioReview
from .local_preview import (
    PreviewProblem,
    PreviewRequest,
    bundle_bytes,
    render_preview,
    verified_inputs,
)
from .resources import StrictContract
from .studio import hash_json, normalize

SCOPE = "LOCAL_DEVELOPMENT_ONLY"
DIMENSIONS = ("product", "interaction", "identity", "scene", "overall")


class JobSubmit(StrictContract):
    idempotency_key: UUID
    parameters: PreviewRequest


class QCLabel(StrictContract):
    decision: Literal["PASS", "FAIL"]
    reason: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_failure_reason(self):
        self.reason = self.reason.strip()
        if self.decision == "FAIL" and not self.reason:
            raise ValueError("failed dimensions require a reason")
        return self


class QCDimensions(StrictContract):
    product: QCLabel
    interaction: QCLabel
    identity: QCLabel
    scene: QCLabel
    overall: QCLabel


class ReviewSubmit(StrictContract):
    expected_version: int = Field(ge=0)
    output_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    dimensions: QCDimensions


def job_dict(job: StudioJob) -> dict:
    return {"id": job.id, "created_by": job.created_by, "case_id": job.case_id, "state": job.state,
            "parameters": job.parameters, "sources": job.sources,
            "request_hash": job.request_hash, "execution_count": job.execution_count,
            "review_version": job.review_version,
            "created_at": job.created_at.isoformat(),
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "error_code": job.error_code, "output_sha256": job.output_sha256,
            "scope": SCOPE, "provider_execution_performed": False, "formal_eligible": False}


def get_job(session: Session, job_id: str, *, lock=False) -> StudioJob:
    query = select(StudioJob).where(StudioJob.id == job_id)
    job = session.scalar(query.with_for_update() if lock else query)
    if job is None:
        raise PreviewProblem("JOB_NOT_FOUND", 404)
    return job


def submit_job(session: Session, root: Path, request: JobSubmit) -> dict:
    parameters, case, manifest_hash = normalize(root, request.parameters)
    _, _, provenance, views = verified_inputs(root, request.parameters.product_revision)
    if provenance["dataset_manifest_sha256"] != manifest_hash:
        raise PreviewProblem("JOB_SOURCE_CHANGED")
    view = next(v for v in views if v["view_id"] == parameters["product_view_id"])
    sources = provenance | {"case_base_sha256": case["sha256"],
                            "product_layer_sha256": {o["layer"]: o["sha256"]
                                                     for o in view["outputs"]}}
    request_hash = hash_json({"parameters": parameters, "sources": sources})
    key = str(request.idempotency_key)
    existing = session.scalar(select(StudioJob).where(StudioJob.idempotency_key == key))
    if existing is None:
        try:
            with session.begin_nested():
                existing = StudioJob(created_by=session.info.get("actor", "LOCAL_DEVELOPER"),
                                     idempotency_key=key, case_id=parameters["case_id"],
                                     parameters=parameters, sources=sources,
                                     request_hash=request_hash)
                session.add(existing)
                session.flush()
        except IntegrityError:
            # A concurrent identical submission may already have committed.
            existing = session.scalar(select(StudioJob).where(StudioJob.idempotency_key == key))
            if existing is None:
                raise
    if existing.created_by != session.info.get("actor", "LOCAL_DEVELOPER"):
        raise PreviewProblem("JOB_IDEMPOTENCY_CONFLICT")
    if existing.request_hash != request_hash:
        raise PreviewProblem("JOB_IDEMPOTENCY_CONFLICT")
    return job_dict(existing)


def claim_job(session: Session, now: datetime | None = None) -> dict | None:
    """Commit this transaction before rendering. Expired workers are fenced by token."""
    now = now or datetime.now(UTC)
    job = session.scalar(select(StudioJob).where(or_(
        StudioJob.state == "QUEUED",
        and_(StudioJob.state == "RUNNING", StudioJob.lease_until <= now),
    )).order_by(StudioJob.created_at, StudioJob.id).with_for_update(skip_locked=True).limit(1))
    if job is None:
        return None
    if job.execution_count >= 3:
        job.state, job.error_code, job.finished_at = "FAILED", "WORKER_RETRY_EXHAUSTED", now
        job.lease_token, job.lease_until = None, None
        session.flush()
        return {"exhausted": True}
    job.state, job.execution_count = "RUNNING", job.execution_count + 1
    job.lease_token, job.lease_until = str(uuid4()), now + timedelta(minutes=5)
    session.flush()
    return {"id": job.id, "token": job.lease_token, "parameters": job.parameters,
            "sources": job.sources, "request_hash": job.request_hash}


def finish_job(session: Session, claim: dict, *, manifest=None, bundle=None,
               error_code: str | None = None) -> bool:
    job = get_job(session, claim["id"], lock=True)
    if job.state != "RUNNING" or job.lease_token != claim["token"]:
        return False
    if error_code:
        job.state, job.error_code = "FAILED", error_code
    else:
        sha = hashlib.sha256(bundle).hexdigest()
        session.add(StudioJobOutput(job_id=job.id, manifest=manifest, bundle=bundle, sha256=sha))
        job.state, job.output_sha256 = "SUCCEEDED", sha
    job.finished_at = datetime.now(UTC)
    job.lease_token, job.lease_until = None, None
    session.flush()
    return True


def run_one(factory, root: Path) -> bool:
    with factory.begin() as session:
        claim = claim_job(session)
    if not claim:
        return False
    if claim.get("exhausted"):
        return True
    manifest = bundle = error = None
    try:
        if hash_json({"parameters": claim["parameters"], "sources": claim["sources"]}) != claim[
                "request_hash"]:
            raise PreviewProblem("JOB_REQUEST_INTEGRITY_FAILED", 503)
        manifest, files = render_preview(root, PreviewRequest.model_validate(claim["parameters"]))
        if manifest["sources"] != claim["sources"]:
            raise PreviewProblem("JOB_SOURCE_CHANGED")
        bundle = bundle_bytes(files)
        if len(bundle) > 32 * 1024 * 1024:
            raise PreviewProblem("JOB_OUTPUT_TOO_LARGE", 503)
    except PreviewProblem as exc:
        error = exc.code
    except Exception:
        # Do not leak filesystem paths, source bytes or credentials through persisted errors.
        error = "LOCAL_RENDER_FAILED"
    with factory.begin() as session:
        finish_job(session, claim, manifest=manifest, bundle=bundle, error_code=error)
    return True


def verified_output(session: Session, job: StudioJob) -> StudioJobOutput:
    if job.state != "SUCCEEDED":
        raise PreviewProblem("JOB_OUTPUT_NOT_READY")
    if hash_json({"parameters": job.parameters, "sources": job.sources}) != job.request_hash:
        raise PreviewProblem("JOB_REQUEST_INTEGRITY_FAILED", 503)
    output = session.get(StudioJobOutput, job.id)
    if (output is None or output.sha256 != job.output_sha256
            or hashlib.sha256(output.bundle).hexdigest() != output.sha256):
        raise PreviewProblem("JOB_OUTPUT_INTEGRITY_FAILED", 503)
    try:
        with zipfile.ZipFile(io.BytesIO(output.bundle)) as archive:
            if json.loads(archive.read("manifest.json")) != output.manifest:
                raise ValueError("manifest mismatch")
            if (output.manifest["sources"] != job.sources
                    or output.manifest["request"] != job.parameters):
                raise ValueError("job binding mismatch")
            for ref in output.manifest["artifacts"]:
                data = archive.read(ref["path"])
                if len(data) != ref["bytes"] or hashlib.sha256(data).hexdigest() != ref["sha256"]:
                    raise ValueError("artifact mismatch")
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        raise PreviewProblem("JOB_OUTPUT_INTEGRITY_FAILED", 503) from exc
    return output


def reviews(session: Session, job: StudioJob) -> list[dict]:
    records = list(session.scalars(select(StudioReview).where(StudioReview.job_id == job.id)
                                  .order_by(StudioReview.version)))
    if len(records) != job.review_version:
        raise PreviewProblem("QC_HISTORY_INTEGRITY_FAILED", 503)
    result, previous = [], None
    for version, record in enumerate(records, 1):
        payload = record.payload
        if (record.version != version or payload.get("version") != version
                or payload.get("job_id") != job.id
                or payload.get("output_sha256") != job.output_sha256
                or payload.get("previous_hash") != previous
                or hash_json(payload) != record.content_sha256):
            raise PreviewProblem("QC_HISTORY_INTEGRITY_FAILED", 503)
        result.append(payload | {"id": record.id, "content_sha256": record.content_sha256})
        previous = record.content_sha256
    return result


def save_review(session: Session, job_id: str, request: ReviewSubmit) -> dict:
    job = get_job(session, job_id, lock=True)
    verified_output(session, job)
    if request.output_sha256 != job.output_sha256:
        raise PreviewProblem("QC_OUTPUT_MISMATCH")
    history = reviews(session, job)
    if request.expected_version != len(history):
        raise PreviewProblem("QC_VERSION_CONFLICT")
    dimensions = request.dimensions.model_dump()
    payload = {"job_id": job.id, "version": len(history) + 1,
               "output_sha256": job.output_sha256, "dimensions": dimensions,
               "decision": "PASS" if all(d["decision"] == "PASS" for d in dimensions.values())
               else "FAIL", "protocol": "development-five-dimensions-v1", "scope": SCOPE,
               "reviewer": session.info.get("actor", "LOCAL_DEVELOPER"),
               "occurred_at": datetime.now(UTC).isoformat(),
               "previous_hash": history[-1]["content_sha256"] if history else None}
    record = StudioReview(job_id=job.id, version=payload["version"], payload=payload,
                          content_sha256=hash_json(payload))
    session.add(record)
    job.review_version = payload["version"]
    session.flush()
    return payload | {"id": record.id, "content_sha256": record.content_sha256}
