"""Stateless, model-free preview endpoints for the Development dataset only."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response

from ..config import Settings, get_settings
from ..domain.dataset_releases import local_path
from ..domain.local_preview import (
    PreviewFormat,
    PreviewProblem,
    PreviewRequest,
    bundle_bytes,
    catalog,
    checked_bytes,
    render_preview,
    verified_inputs,
)

router = APIRouter(prefix="/api/v1/development", tags=["local-development"])


@router.get("/cases/{case_id}/image")
def case_image(case_id: str, settings: Settings = Depends(get_settings)) -> Response:  # noqa: B008
    try:
        snapshot, _, _, _ = verified_inputs(settings.artifact_root)
        case = next((c for c in snapshot["cases"] if c["case_id"] == case_id), None)
        if case is None:
            raise PreviewProblem("DEVELOPMENT_CASE_NOT_FOUND", 404)
        path = local_path(settings.artifact_root / "datasets/development/v1", case["path"])
        return Response(checked_bytes(path, case["sha256"]), media_type="image/png",
                        headers={"Cache-Control": "no-store"})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise unavailable(exc) from exc


@router.get("/product-views/{view_id}/image")
def product_image(view_id: str, product_revision: Literal["v1", "v2"] = "v1",
                  settings: Settings = Depends(get_settings)) -> Response:  # noqa: B008
    try:
        _, _, _, views = verified_inputs(settings.artifact_root, product_revision)
        view = next((v for v in views if v["view_id"] == view_id), None)
        if view is None:
            raise PreviewProblem("PRODUCT_VIEW_NOT_FOUND", 404)
        layer = next(o for o in view["outputs"] if o["layer"] == "RGBA")
        data = checked_bytes(local_path(settings.artifact_root, layer["path"]), layer["sha256"])
        return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise unavailable(exc) from exc


def unavailable(exc: Exception) -> HTTPException:
    if isinstance(exc, PreviewProblem):
        return HTTPException(status_code=exc.status, detail={"code": exc.code})
    return HTTPException(status_code=503, detail={"code": "LOCAL_PREVIEW_INPUT_UNAVAILABLE"})


@router.get("/catalog", operation_id="getDevelopmentCatalog")
def get_catalog(settings: Settings = Depends(get_settings)) -> dict:  # noqa: B008
    try:
        return catalog(settings.artifact_root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise unavailable(exc) from exc


@router.post(
    "/previews", operation_id="renderLocalDevelopmentPreview",
    responses={200: {"description": "Local placement preview, manifest or ZIP bundle",
                     "content": {"application/zip": {}, "image/png": {},
                                 "application/json": {}}},
               409: {"description": "Placement, residual or visible-core constraint failed"}},
)
def create_preview(
    request: PreviewRequest,
    format: PreviewFormat = "bundle",
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    try:
        manifest, files = render_preview(settings.artifact_root, request)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise unavailable(exc) from exc
    headers = {"X-Preview-ID": manifest["preview_id"], "Cache-Control": "no-store"}
    if format == "manifest":
        return Response(files["manifest.json"], media_type="application/json", headers=headers)
    if format == "png":
        return Response(files["preview.png"], media_type="image/png", headers=headers)
    headers["Content-Disposition"] = f'attachment; filename="{request.case_id}-preview.zip"'
    return Response(bundle_bytes(files), media_type="application/zip", headers=headers)


@router.post("/previews/masks/{mask_name}", responses={200: {"content": {"image/png": {}}}})
def preview_mask(
    mask_name: Literal["M_product", "M_core", "M_transition", "M_contact",
                       "M_occlusion", "M_visible_core"],
    request: PreviewRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Response:
    try:
        manifest, files = render_preview(settings.artifact_root, request)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise unavailable(exc) from exc
    return Response(files[f"masks/{mask_name}.png"], media_type="image/png",
                    headers={"Cache-Control": "no-store", "X-Preview-ID": manifest["preview_id"]})
