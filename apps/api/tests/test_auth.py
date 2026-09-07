from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_studio import PROJECT
from test_studio import storage as studio_storage

from interaction_studio_api.auth import create_account
from interaction_studio_api.config import Settings, get_settings
from interaction_studio_api.main import app
from interaction_studio_api.models import StudioSecurityEvent, StudioSession, StudioUser

storage = studio_storage
PASSWORD = "test-password-for-accounts"
HEADERS = {"X-Studio-Request": "1"}


@pytest.fixture
def secured(storage):
    client, engine = storage
    app.dependency_overrides[get_settings] = lambda: Settings(
        artifact_root=PROJECT, database_url=str(engine.url), auth_mode="authenticated")
    with Session(engine) as session, session.begin():
        for name, roles in [("admin", ["ADMIN", "OPERATOR"]), ("reader", ["AUDITOR"]),
                            ("reviewer", ["REVIEWER"])]:
            create_account(session, name, PASSWORD, roles, "TEST")
    return client, engine


def login(client, username="admin", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password},
                       headers=HEADERS)


def test_anonymous_and_readonly_cannot_bypass_server(secured):
    client, _ = secured
    assert client.get("/api/v1/development/catalog").status_code == 401
    assert client.get("/api/v1/development/studio/jobs/summary").status_code == 401
    assert client.get("/api/v1/development/studio/jobs").status_code == 401
    assert client.get("/api/v1/development/cases/DEV_MOUTH_001/image").status_code == 401
    assert login(client, "reader").status_code == 200
    assert client.get("/api/v1/development/studio/jobs?case_id=DEV_MOUTH_001").status_code == 200
    assert client.get("/api/v1/development/studio/jobs/summary").status_code == 200
    assert client.get("/api/v1/development/studio/jobs").status_code == 200
    assert client.get("/api/v1/auth/users").status_code == 403
    assert client.post("/api/v1/development/previews", json={"case_id": "DEV_MOUTH_001"},
                       headers=HEADERS).status_code == 403
    assert client.put("/api/v1/development/studio/drafts/DEV_MOUTH_001", headers=HEADERS,
                      json={"expected_version": 0, "parameters": {
                          "case_id": "DEV_MOUTH_001"}}).status_code == 403


def test_real_actor_cookie_csrf_and_logout(secured):
    client, engine = secured
    response = login(client)
    actor = response.json()["id"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    body = {"expected_version": 0, "parameters": {"case_id": "DEV_MOUTH_001"}}
    url = "/api/v1/development/studio/drafts/DEV_MOUTH_001"
    assert client.put(url, json=body).status_code == 403
    assert client.put(url, json=body, headers=HEADERS | {"Origin": "https://evil.test"}
                      ).status_code == 403
    saved = client.put(url, json=body, headers=HEADERS)
    assert saved.status_code == 200
    assert saved.json()["events"][0]["operator"] == actor
    cookie = client.cookies.get("studio_session")
    with Session(engine) as session:
        record = session.scalar(select(StudioSession))
        assert record.token_hash != cookie
    assert client.post("/api/v1/auth/logout", headers=HEADERS).status_code == 200
    assert client.get(url).status_code == 401
    client.cookies.set("studio_session", cookie)
    assert client.get(url).status_code == 401


def test_role_separation_unique_accounts_and_revocation(secured):
    client, engine = secured
    login(client)
    url = "/api/v1/auth/users"
    body = {"username": "newuser", "password": PASSWORD, "roles": ["ADMIN", "GATE_SIGNER"]}
    assert client.post(url, json=body, headers=HEADERS).status_code == 422
    body["roles"] = ["AUDITOR"]
    assert client.post(url, json=body, headers=HEADERS).status_code == 201
    assert client.post(url, json=body, headers=HEADERS).status_code == 409
    with Session(engine) as session:
        reader_id = session.scalar(select(StudioUser).where(StudioUser.username == "reader")).id
    assert client.put(f"{url}/{reader_id}/status", json={"enabled": False},
                      headers=HEADERS).status_code == 200
    assert login(client, "reader").status_code == 401
    login(client)
    me = client.get("/api/v1/auth/me").json()
    assert client.put(f"{url}/{me['id']}/status", json={"enabled": False},
                      headers=HEADERS).status_code == 409


def test_login_failures_persist_lock_and_expired_sessions_fail(secured):
    client, engine = secured
    for _ in range(5):
        assert login(client, password="wrong-password").status_code == 401
    assert login(client).status_code == 401
    with Session(engine) as session, session.begin():
        user = session.scalar(select(StudioUser).where(StudioUser.username == "admin"))
        assert user.failed_logins == 6
        assert len(session.scalars(select(StudioSecurityEvent).where(
            StudioSecurityEvent.action == "LOGIN_FAILED")).all()) == 6
        user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    assert login(client).status_code == 200
    with Session(engine) as session, session.begin():
        session.scalar(select(StudioSession)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_change_revokes_all_sessions(secured):
    client, engine = secured
    login(client)
    assert client.post("/api/v1/auth/password", headers=HEADERS, json={
        "current_password": PASSWORD, "new_password": "a-new-test-password-123"}).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    assert login(client).status_code == 401
    assert login(client, password="a-new-test-password-123").status_code == 200
    with Session(engine) as session:
        assert len(session.scalars(select(StudioSession)).all()) == 1


def test_production_cannot_disable_auth_or_cookie_security():
    with pytest.raises(ValueError):
        Settings(app_env="production", auth_mode="local")
    with pytest.raises(ValueError):
        Settings(app_env="production", auth_mode="authenticated", session_cookie_secure=False)
