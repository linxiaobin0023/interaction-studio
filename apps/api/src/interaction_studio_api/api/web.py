"""Serve the built local Studio UI without exposing source or dataset directories."""

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import Settings


def mount_studio(app: FastAPI, settings: Settings) -> None:
    root = settings.web_dist_root.resolve()
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="studio-assets")

    @app.api_route("/index.html", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def studio_index():
        if not (root / "index.html").is_file():
            return JSONResponse(status_code=503, content={"code": "STUDIO_BUILD_REQUIRED"})
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})
