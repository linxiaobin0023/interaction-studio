from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import make_session_factory
from ..domain.local_preview import PreviewProblem
from ..domain.studio import (
    DraftSave,
    TemplateSave,
    list_templates,
    load_draft,
    save_draft,
    save_template,
)

router = APIRouter(prefix="/api/v1/development/studio", tags=["studio"])
DevCaseId = Annotated[str, Path(pattern=r"^DEV_(MOUTH|NEAR|HAND)_[0-9]{3}$")]


@lru_cache(maxsize=4)
def studio_factory(database_url: str):
    return make_session_factory(database_url)


def studio_session(
    request: Request, settings: Settings = Depends(get_settings),  # noqa: B008
) -> Iterator[Session]:
    with studio_factory(settings.database_url)() as session:
        try:
            session.info["actor"] = getattr(request.state, "principal", {}).get(
                "id", "LOCAL_DEVELOPER")
            yield session
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, detail={"code": "STUDIO_VERSION_CONFLICT"}) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise HTTPException(503, detail={"code": "STUDIO_STORAGE_UNAVAILABLE"}) from exc


def failure(exc: Exception) -> HTTPException:
    if isinstance(exc, PreviewProblem):
        return HTTPException(exc.status, detail={"code": exc.code})
    return HTTPException(503, detail={"code": "STUDIO_INPUT_UNAVAILABLE"})


@router.get("/drafts/{case_id}")
def get_draft(case_id: DevCaseId,
              session: Session = Depends(studio_session, scope="function"),  # noqa: B008
              settings: Settings = Depends(get_settings)) -> dict:  # noqa: B008
    try:
        return load_draft(session, settings.artifact_root, case_id)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc


@router.put("/drafts/{case_id}")
def put_draft(case_id: DevCaseId, request: DraftSave,
              session: Session = Depends(studio_session, scope="function"),  # noqa: B008
              settings: Settings = Depends(get_settings)) -> dict:  # noqa: B008
    try:
        return save_draft(session, settings.artifact_root, case_id, request)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc


@router.get("/templates")
def get_templates(session: Session = Depends(studio_session, scope="function")) -> dict:  # noqa: B008
    try:
        return {"templates": list_templates(session)}
    except (ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc


@router.post("/templates", status_code=201)
def post_template(request: TemplateSave,
                  session: Session = Depends(studio_session, scope="function"),  # noqa: B008
                  settings: Settings = Depends(get_settings)) -> dict:  # noqa: B008
    try:
        return save_template(session, settings.artifact_root, request)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise failure(exc) from exc
