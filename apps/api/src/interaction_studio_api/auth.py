"""Local unique accounts and server-enforced permissions for Development operations."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .config import Settings, get_settings
from .db import make_session_factory
from .models import StudioSession, StudioUser

COOKIE = "studio_session"
ROLES = {"ADMIN", "OPERATOR", "REVIEWER", "AUDITOR", "CUSTODIAN", "GATE_SIGNER"}


@lru_cache(maxsize=4)
def auth_factory(url: str):
    return make_session_factory(url)


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"pbkdf2-sha256$600000${salt}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, _ = encoded.split("$")
        if algorithm != "pbkdf2-sha256" or iterations != "600000":
            return False
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except ValueError:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def user_dict(user: StudioUser) -> dict:
    return {"id": user.id, "username": user.username, "roles": user.roles, "enabled": user.enabled}


def deny(code: str, status=403):
    raise HTTPException(status, detail={"code": code})


def authorize(request: Request, settings: Settings = Depends(get_settings)):  # noqa: B008
    path = request.url.path
    if not path.startswith("/api/") or path == "/api/v1/auth/login":
        return
    if settings.auth_mode == "local":
        request.state.principal = {"id": "LOCAL_DEVELOPER", "username": "LOCAL_DEVELOPER",
                                   "roles": ["ADMIN", "OPERATOR", "REVIEWER", "AUDITOR"]}
        return
    token = request.cookies.get(COOKIE, "")
    if len(token) != 64:
        deny("AUTH_REQUIRED", 401)
    try:
        with auth_factory(settings.database_url)() as session:
            record = session.get(StudioSession, token_hash(token))
            if record is None or aware(record.expires_at) <= datetime.now(UTC):
                deny("AUTH_REQUIRED", 401)
            user = session.get(StudioUser, record.user_id)
            if not user or not user.enabled:
                deny("AUTH_REQUIRED", 401)
            request.state.principal = user_dict(user)
    except SQLAlchemyError as exc:
        raise HTTPException(503, detail={"code": "AUTH_STORAGE_UNAVAILABLE"}) from exc
    roles = set(request.state.principal["roles"])
    if ((path.startswith("/api/v1/auth/users") or path == "/api/v1/auth/events")
            and "ADMIN" not in roles):
        deny("ROLE_FORBIDDEN")
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    # The custom header cannot be sent by a cross-origin HTML form. No CORS grants it.
    if request.headers.get("x-studio-request") != "1":
        deny("CSRF_CHECK_FAILED")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        deny("CSRF_CHECK_FAILED")
    if path.startswith("/api/v1/auth/"):
        return
    if path.startswith("/api/v1/development/"):
        allowed = {"OPERATOR", "REVIEWER"} if path.endswith("/reviews") else {"OPERATOR"}
        if not roles & allowed:
            deny("ROLE_FORBIDDEN")
        return
    # Existing validators are pure computations, not Formal actions.
    if path.startswith("/api/v1/contracts/") or path in {
        "/api/v1/manifests/validate", "/api/v1/readiness/evaluations",
    }:
        return
    deny("ROLE_FORBIDDEN")


def create_account(session, username: str, password: str, roles: list[str], actor: str):
    from .models import StudioSecurityEvent

    if not roles or not set(roles) <= ROLES or {"ADMIN", "GATE_SIGNER"} <= set(roles):
        raise ValueError("invalid role combination")
    if session.scalar(select(StudioUser).where(StudioUser.username == username)):
        raise ValueError("username already exists")
    user = StudioUser(username=username, password_hash=password_hash(password), roles=roles)
    session.add(user)
    session.add(StudioSecurityEvent(actor=actor, action="ACCOUNT_CREATED", subject=username))
    session.flush()
    return user
