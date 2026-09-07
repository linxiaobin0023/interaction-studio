from fastapi import FastAPI
from fastapi.testclient import TestClient

from interaction_studio_api.api.web import mount_studio
from interaction_studio_api.config import Settings


def test_built_studio_serves_only_public_assets(tmp_path):
    public = tmp_path / "web"
    (public / "assets").mkdir(parents=True)
    (public / "index.html").write_text('<html lang="zh-CN">Interaction Studio</html>')
    (public / "assets/app.js").write_text('console.log("studio")')
    (tmp_path / "secret.txt").write_text("not public")
    app = FastAPI()
    mount_studio(app, Settings(web_dist_root=public))
    with TestClient(app) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert index.headers["cache-control"] == "no-store"
        explicit_index = client.get("/index.html")
        assert explicit_index.text == index.text
        assert explicit_index.headers["cache-control"] == "no-store"
        for path in ("/", "/index.html"):
            probe = client.head(path)
            assert probe.status_code == 200
            assert probe.headers["content-type"].startswith("text/html")
            assert probe.headers["cache-control"] == "no-store"
            assert probe.content == b""
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/%2e%2e/%2e%2e/secret.txt").status_code == 404
        assert client.get("/datasets/development/v1/seal.json").status_code == 404


def test_missing_frontend_build_returns_clear_unavailable_state(tmp_path):
    app = FastAPI()
    mount_studio(app, Settings(web_dist_root=tmp_path))
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 503
        assert response.json()["code"] == "STUDIO_BUILD_REQUIRED"
