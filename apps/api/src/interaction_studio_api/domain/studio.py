"""Transactional local Development drafts and immutable template versions."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import StudioDraft, StudioEvent, StudioTemplate
from .local_preview import PreviewProblem, PreviewRequest, recommendation, verified_inputs
from .resources import StrictContract


class DraftSave(StrictContract):
    expected_version: int = Field(ge=0)
    parameters: PreviewRequest
    action: Literal["SAVE", "RESET", "APPLY_TEMPLATE"] = "SAVE"


class TemplateSave(StrictContract):
    name: str = Field(min_length=1, max_length=80)
    parameters: PreviewRequest

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("template name cannot be blank")
        return value


def hash_json(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def normalize(root: Path, request: PreviewRequest) -> tuple[dict, dict, str]:
    snapshot, landmarks, provenance, views = verified_inputs(root, request.product_revision)
    case = next((c for c in snapshot["cases"] if c["case_id"] == request.case_id), None)
    if case is None:
        raise PreviewProblem("DEVELOPMENT_CASE_NOT_FOUND", 404)
    suggestion = recommendation(case, landmarks[case["case_id"]], views)
    parameters = request.model_dump()
    if request.product_revision == "v1":
        parameters.pop("product_revision", None)
    parameters["placement"] = parameters["placement"] or suggestion["placement"]
    parameters["product_view_id"] = parameters["product_view_id"] or suggestion["product_view_id"]
    if parameters["product_view_id"] not in {v["view_id"] for v in views}:
        raise PreviewProblem("PRODUCT_VIEW_NOT_FOUND", 404)
    return parameters, case, provenance["dataset_manifest_sha256"]


def draft_dict(draft: StudioDraft) -> dict:
    return {"case_id": draft.case_id, "resource_version": draft.resource_version,
            "manifest_sha256": draft.manifest_sha256, "case_base_sha256": draft.case_base_sha256,
            "parameters": draft.parameters}


def history(session: Session, case_id: str, draft: StudioDraft | None) -> list[dict]:
    events = list(session.scalars(select(StudioEvent).where(StudioEvent.case_id == case_id)
                                 .order_by(StudioEvent.sequence_no)))
    previous = None
    before = {}
    for sequence, event in enumerate(events, 1):
        payload = event.payload
        if (event.sequence_no != sequence or event.previous_hash != previous
                or payload.get("previous_hash") != previous
                or payload.get("sequence_no") != sequence or payload.get("case_id") != case_id
                or payload.get("before") != before or hash_json(payload) != event.event_hash):
            raise PreviewProblem("STUDIO_HISTORY_INTEGRITY_FAILED", 503)
        previous, before = event.event_hash, payload["after"]
    if draft and (len(events) != draft.resource_version or before != draft.parameters):
        raise PreviewProblem("STUDIO_HISTORY_INTEGRITY_FAILED", 503)
    if not draft and events:
        raise PreviewProblem("STUDIO_HISTORY_INTEGRITY_FAILED", 503)
    return [e.payload | {"event_hash": e.event_hash} for e in events]


def load_draft(session: Session, root: Path, case_id: str) -> dict:
    parameters, case, manifest_hash = normalize(
        root, PreviewRequest(case_id=case_id, product_revision="v2"))
    draft = session.scalar(select(StudioDraft).where(
        StudioDraft.case_id == case_id).with_for_update())
    if draft and (draft.manifest_sha256 != manifest_hash
                  or draft.case_base_sha256 != case["sha256"]):
        raise PreviewProblem("DRAFT_SOURCE_CHANGED")
    # First-save races are handled by the primary key on insert. Do not query
    # a concurrently created history after observing an absent draft.
    events = history(session, case_id, draft) if draft else []
    return {"draft": draft_dict(draft) if draft else {
        "case_id": case_id, "resource_version": 0, "manifest_sha256": manifest_hash,
        "case_base_sha256": case["sha256"], "parameters": parameters},
        "events": events, "history_verified": True, "scope": "LOCAL_DEVELOPMENT_ONLY"}


def save_draft(session: Session, root: Path, case_id: str, request: DraftSave) -> dict:
    if case_id != request.parameters.case_id:
        raise PreviewProblem("DRAFT_CASE_MISMATCH", 422)
    current = load_draft(session, root, case_id)
    if current["draft"]["resource_version"] != request.expected_version:
        raise PreviewProblem("DRAFT_VERSION_CONFLICT")
    parameters, case, manifest_hash = normalize(root, request.parameters)
    version = request.expected_version + 1
    before = current["draft"]["parameters"] if request.expected_version else {}
    previous_hash = current["events"][-1]["event_hash"] if current["events"] else None
    if request.expected_version:
        changed = session.execute(update(StudioDraft).where(
            StudioDraft.case_id == case_id,
            StudioDraft.resource_version == request.expected_version,
        ).values(resource_version=version, parameters=parameters))
        if changed.rowcount != 1:
            raise PreviewProblem("DRAFT_VERSION_CONFLICT")
    else:
        session.add(StudioDraft(case_id=case_id, resource_version=version,
                                manifest_sha256=manifest_hash, case_base_sha256=case["sha256"],
                                parameters=parameters))
        session.flush()
    payload = {"case_id": case_id, "sequence_no": version, "action": request.action,
               "operator": session.info.get("actor", "LOCAL_DEVELOPER"),
               "occurred_at": datetime.now(UTC).isoformat(),
               "before": before, "after": parameters, "previous_hash": previous_hash,
               "manifest_sha256": manifest_hash, "case_base_sha256": case["sha256"]}
    session.add(StudioEvent(case_id=case_id, sequence_no=version, payload=payload,
                           previous_hash=previous_hash, event_hash=hash_json(payload)))
    session.flush()
    # The caller commits the draft and its event in the same transaction.
    return {"draft": {"case_id": case_id, "resource_version": version,
                      "manifest_sha256": manifest_hash, "case_base_sha256": case["sha256"],
                      "parameters": parameters},
            "events": current["events"] + [payload | {"event_hash": hash_json(payload)}],
            "history_verified": True, "scope": "LOCAL_DEVELOPMENT_ONLY"}


def template_dict(template: StudioTemplate) -> dict:
    content = {"name": template.name, "version": template.version,
               "interaction": template.interaction, "manifest_sha256": template.manifest_sha256,
               "parameters": template.parameters}
    if hash_json(content) != template.content_sha256:
        raise PreviewProblem("TEMPLATE_INTEGRITY_FAILED", 503)
    return content | {"id": template.id, "created_by": template.created_by,
                      "content_sha256": template.content_sha256}


def list_templates(session: Session) -> list[dict]:
    return [template_dict(t) for t in session.scalars(select(StudioTemplate).order_by(
        StudioTemplate.name, StudioTemplate.version.desc()))]


def save_template(session: Session, root: Path, request: TemplateSave) -> dict:
    parameters, case, manifest_hash = normalize(root, request.parameters)
    current_version = session.scalar(select(func.max(StudioTemplate.version)).where(
        StudioTemplate.name == request.name)) or 0
    content = {"name": request.name, "version": current_version + 1,
               "interaction": case["interaction"], "manifest_sha256": manifest_hash,
               "parameters": parameters}
    template = StudioTemplate(**content, content_sha256=hash_json(content),
                              created_by=session.info.get("actor", "LOCAL_DEVELOPER"))
    session.add(template)
    session.flush()
    return template_dict(template)
