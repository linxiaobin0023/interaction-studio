from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .api.auth import router as auth_router
from .api.contracts import router as contracts_router
from .api.datasets import router as datasets_router
from .api.local_preview import router as local_preview_router
from .api.readiness import router as readiness_router
from .api.studio import router as studio_router
from .api.studio_jobs import router as studio_jobs_router
from .api.web import mount_studio
from .auth import authorize
from .config import get_settings
from .domain.manifests import AssetManifest
from .domain.state_machines import InvalidTransition

settings = get_settings()

app = FastAPI(
    dependencies=[Depends(authorize)],
    title="Interaction Studio API",
    version=__version__,
    description="G0/G1 domain and preflight API",
)
app.include_router(auth_router)
app.include_router(contracts_router)
app.include_router(datasets_router)
app.include_router(local_preview_router)
app.include_router(readiness_router)
app.include_router(studio_router)
app.include_router(studio_jobs_router)
mount_studio(app, settings)


@app.exception_handler(InvalidTransition)
def invalid_transition_handler(
    request: Request, exc: InvalidTransition
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "INVALID_STATE_TRANSITION",
                "message": str(exc),
                "request_path": request.url.path,
                "machine": exc.machine,
                "current_state": exc.current.value,
                "target_state": exc.target.value,
                "allowed_states": sorted(state.value for state in exc.allowed),
            }
        },
    )


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str | bool]:
    return {
        "status": "ready",
        "environment": settings.app_env,
        "external_inference_enabled": settings.external_inference_enabled,
    }


@app.post("/api/v1/manifests/validate", tags=["manifests"])
def validate_manifest(manifest: AssetManifest) -> dict[str, object]:
    return {"valid": True, "summary": manifest.summary()}
