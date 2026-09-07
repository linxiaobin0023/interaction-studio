import io
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from interaction_studio_api.config import Settings, get_settings
from interaction_studio_api.domain.studio import hash_json
from interaction_studio_api.main import app
from interaction_studio_api.models import StudioDraft, StudioEvent, StudioTemplate

PROJECT = Path(__file__).parents[3]
CASE = "DEV_MOUTH_001"
URL = f"/api/v1/development/studio/drafts/{CASE}"


@pytest.fixture
def storage(tmp_path):
    url = f"sqlite:///{tmp_path / 'studio.db'}"
    config = Config(PROJECT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    app.dependency_overrides[get_settings] = lambda: Settings(
        artifact_root=PROJECT, database_url=url)
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.pop(get_settings, None)
    engine.dispose()


def save(client, version=0, parameters=None):
    return client.put(URL, json={"expected_version": version,
                                "parameters": parameters or {"case_id": CASE}})


def test_draft_survives_new_session_and_records_hash_chain(storage):
    client, engine = storage
    initial = client.get(URL).json()
    assert initial["draft"]["resource_version"] == 0 and initial["events"] == []
    first = save(client)
    assert first.status_code == 200
    params = first.json()["draft"]["parameters"]
    params["placement"]["center_x"] = 0.42
    second = save(client, 1, params)
    assert second.status_code == 200
    with Session(engine) as new_session:
        assert new_session.get(StudioDraft, CASE).parameters["placement"]["center_x"] == 0.42
        assert len(list(new_session.scalars(select(StudioEvent)))) == 2
    loaded = client.get(URL).json()
    assert loaded["draft"]["resource_version"] == 2
    assert loaded["history_verified"] is True
    previous = None
    for event in loaded["events"]:
        event_hash = event.pop("event_hash")
        assert event["previous_hash"] == previous
        assert hash_json(event) == event_hash
        previous = event_hash


def test_stale_save_cannot_replace_draft_or_append_event(storage):
    client, engine = storage
    assert save(client).status_code == 200
    response = save(client, 0, {"case_id": CASE, "contact_radius_px": 25})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DRAFT_VERSION_CONFLICT"
    assert client.get(URL).json()["draft"]["parameters"]["contact_radius_px"] == 12
    with Session(engine) as session:
        assert len(list(session.scalars(select(StudioEvent)))) == 1


def test_invalid_save_has_no_partial_persistence(storage):
    client, engine = storage
    response = save(client, parameters={"case_id": CASE, "product_view_id": "NOT_A_VIEW"})
    assert response.status_code == 404
    with Session(engine) as session:
        assert session.get(StudioDraft, CASE) is None
        assert list(session.scalars(select(StudioEvent))) == []


def test_save_history_corruption_fails_closed(storage):
    client, engine = storage
    assert save(client).status_code == 200
    with engine.begin() as connection:
        connection.execute(text("UPDATE studio_events SET event_hash = :value"),
                           {"value": "0" * 64})
    assert client.get(URL).status_code == 503
    assert save(client, 1).status_code == 503


def test_missing_event_blocks_draft_replay(storage):
    client, engine = storage
    assert save(client).status_code == 200
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM studio_events"))
    response = client.get(URL)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "STUDIO_HISTORY_INTEGRITY_FAILED"


def test_template_versions_are_immutable_and_hash_bound(storage):
    client, engine = storage
    url = "/api/v1/development/studio/templates"
    body = {"name": "  正面定位  ", "parameters": {"case_id": CASE}}
    first = client.post(url, json=body)
    assert first.status_code == 201
    second = client.post(url, json=body)
    assert second.status_code == 201
    assert first.json()["version"] == 1 and second.json()["version"] == 2
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["name"] == "正面定位"
    with Session(engine) as session:
        one = session.get(StudioTemplate, first.json()["id"])
        assert one.content_sha256 == first.json()["content_sha256"]
    assert len(client.get(url).json()["templates"]) == 2
    assert client.put(f'{url}/{first.json()["id"]}', json=body).status_code == 404


def test_corrupt_template_is_not_loaded(storage):
    client, engine = storage
    url = "/api/v1/development/studio/templates"
    response = client.post(url, json={"name": "test", "parameters": {"case_id": CASE}})
    assert response.status_code == 201
    with engine.begin() as connection:
        connection.execute(text("UPDATE studio_templates SET name = 'tampered'"))
    assert client.get(url).status_code == 503


@pytest.mark.parametrize("case_id", ["VAL_MOUTH_001", "FORMAL_MOUTH_001", "INVALID"])
def test_non_development_draft_ids_are_rejected(storage, case_id):
    client, _ = storage
    assert client.get(f"/api/v1/development/studio/drafts/{case_id}").status_code == 422


def test_case_mismatch_and_blank_template_are_rejected(storage):
    client, _ = storage
    assert save(client, parameters={"case_id": "DEV_HAND_001"}).status_code == 422
    assert client.post("/api/v1/development/studio/templates", json={
        "name": "   ", "parameters": {"case_id": CASE}}).status_code == 422


def test_missing_database_returns_safe_error(tmp_path):
    app.dependency_overrides[get_settings] = lambda: Settings(
        artifact_root=PROJECT, database_url=f"sqlite:///{tmp_path / 'empty.db'}")
    try:
        with TestClient(app) as client:
            response = client.get(URL)
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "STUDIO_STORAGE_UNAVAILABLE"
            assert str(tmp_path) not in response.text
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_case_images_product_layers_and_masks_are_real_pngs(storage):
    client, _ = storage
    for path in [f"/api/v1/development/cases/{CASE}/image",
                 "/api/v1/development/product-views/FRONT_00/image"]:
        response = client.get(path)
        assert response.status_code == 200
        with Image.open(io.BytesIO(response.content)) as image:
            assert image.width >= 512
    response = client.post("/api/v1/development/previews/masks/M_contact", json={"case_id": CASE})
    assert response.status_code == 200
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.mode == "L"
        assert set(image.getdata()) == {0, 255}
    assert client.get("/api/v1/development/cases/VAL_MOUTH_001/image").status_code == 404
    assert client.post("/api/v1/development/previews/masks/UNKNOWN",
                       json={"case_id": CASE}).status_code == 422


def test_new_drafts_use_corrected_product_and_legacy_drafts_stay_unchanged(storage):
    client, _ = storage
    initial = client.get(URL).json()["draft"]["parameters"]
    assert initial["product_revision"] == "v2"
    legacy = save(client).json()["draft"]["parameters"]
    assert "product_revision" not in legacy
    assert client.get(URL).json()["draft"]["parameters"] == legacy
    updated = save(client, 1, legacy | {"product_revision": "v2"})
    assert updated.status_code == 200
    assert updated.json()["history_verified"] is True
    assert updated.json()["draft"]["parameters"]["product_revision"] == "v2"
