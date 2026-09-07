import io
import zipfile
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..domain.studio_evidence import export_evidence
from ..domain.studio_jobs import (
    JobSubmit,
    ReviewSubmit,
    get_job,
    job_dict,
    reviews,
    save_review,
    submit_job,
    verified_output,
)
from ..models import StudioJob
from .studio import failure, studio_session

router = APIRouter(prefix="/api/v1/development/studio/jobs", tags=["development-jobs"])
DB = Annotated[Session, Depends(studio_session, scope="function")]
Config = Annotated[Settings, Depends(get_settings)]


@router.post("", status_code=202)
def post_job(request: JobSubmit, session: DB, settings: Config) -> dict:
    try:
        return submit_job(session, settings.artifact_root, request)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc


@router.get("")
def list_jobs(session: DB,
              case_id: Annotated[str | None, Query(
                  pattern=r"^DEV_(MOUTH|NEAR|HAND)_[0-9]{3}$")] = None,
              state: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"] | None = None,
              limit: Annotated[int, Query(ge=1, le=100)] = 20,
              offset: Annotated[int, Query(ge=0)] = 0) -> dict:
    query = select(StudioJob)
    if case_id is not None:
        query = query.where(StudioJob.case_id == case_id)
    if state is not None:
        query = query.where(StudioJob.state == state)
    jobs = session.scalars(query.order_by(
        StudioJob.created_at.desc(), StudioJob.id.desc()).offset(offset).limit(limit + 1)).all()
    return {"jobs": [job_dict(j) for j in jobs[:limit]], "has_more": len(jobs) > limit}


@router.get("/summary")
def job_summary(session: DB) -> dict:
    """Local queue and latest per-output human QC; never production pass metrics."""
    counts = dict(session.execute(select(StudioJob.state, func.count()).group_by(
        StudioJob.state)).all())
    latest = select(StudioJob).order_by(StudioJob.created_at.desc(), StudioJob.id.desc())
    pending = session.scalars(latest.where(StudioJob.state.in_(
        ["QUEUED", "RUNNING"])).limit(4)).all()
    failed = session.scalars(latest.where(StudioJob.state == "FAILED").limit(5)).all()
    unreviewed = session.scalar(select(func.count()).select_from(StudioJob).where(
        StudioJob.state == "SUCCEEDED", StudioJob.review_version == 0))
    dimensions = {name: {"passed": 0, "reviewed": 0, "rate": None}
                  for name in ("product", "interaction", "identity", "scene", "overall")}
    reviewed_jobs = session.scalars(select(StudioJob).where(
        StudioJob.state == "SUCCEEDED", StudioJob.review_version > 0).with_for_update())
    try:
        for job in reviewed_jobs:
            # Preserve the existing integrity check and count only the current review.
            review = reviews(session, job)[-1]
            for name, metric in dimensions.items():
                metric["reviewed"] += 1
                metric["passed"] += review["dimensions"][name]["decision"] == "PASS"
        for metric in dimensions.values():
            if metric["reviewed"]:
                metric["rate"] = round(100 * metric["passed"] / metric["reviewed"], 1)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc
    return {"scope": "LOCAL_DEVELOPMENT_ONLY",
            "counts": {state: counts.get(state, 0)
                       for state in ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED")},
            "pending_review": unreviewed,
            "queue": [job_dict(job) for job in pending],
            "recent_failures": [job_dict(job) for job in failed],
            "quality": dimensions,
            "technical_pass_rate": None, "attempt1_pass_rate": None,
            "average_manual_seconds": None}


@router.get("/{job_id}")
def job_detail(job_id: UUID, session: DB) -> dict:
    try:
        job = get_job(session, str(job_id), lock=True)
        output = verified_output(session, job) if job.state == "SUCCEEDED" else None
        return job_dict(job) | {"manifest": output.manifest if output else None,
                                "reviews": reviews(session, job)}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc


@router.get("/{job_id}/output")
def job_output(job_id: UUID, session: DB, format: Literal["bundle", "png"] = "bundle") -> Response:
    try:
        output = verified_output(session, get_job(session, str(job_id)))
        if format == "png":
            with zipfile.ZipFile(io.BytesIO(output.bundle)) as archive:
                data = archive.read("preview.png")
            return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})
        return Response(output.bundle, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{job_id}.zip"',
            "Cache-Control": "no-store", "X-Content-SHA256": output.sha256})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc


@router.post("/{job_id}/reviews", status_code=201)
def post_review(job_id: UUID, request: ReviewSubmit, session: DB) -> dict:
    try:
        return save_review(session, str(job_id), request)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc


@router.get("/{job_id}/evidence")
def job_evidence(job_id: UUID, session: DB) -> Response:
    try:
        data = export_evidence(session, str(job_id))
        return Response(data, media_type="application/zip", headers={
            "Content-Disposition": f'attachment; filename="{job_id}-evidence.zip"',
            "Cache-Control": "no-store"})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc
