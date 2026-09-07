import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import Field, model_validator
from sqlalchemy import delete, select

from ..auth import (
    COOKIE,
    ROLES,
    aware,
    create_account,
    deny,
    password_hash,
    token_hash,
    user_dict,
    verify_password,
)
from ..config import Settings, get_settings
from ..domain.resources import StrictContract
from ..models import StudioSecurityEvent, StudioSession, StudioUser
from .studio import studio_session

router = APIRouter(prefix="/api/v1/auth", tags=["accounts"])
DB = Annotated[object, Depends(studio_session, scope="function")]
Config = Annotated[Settings, Depends(get_settings)]


class Credentials(StrictContract):
    username: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$")
    password: str = Field(min_length=1, max_length=256)


class AccountCreate(Credentials):
    password: str = Field(min_length=12, max_length=256)
    roles: list[str] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def valid_roles(self):
        if (not set(self.roles) <= ROLES or len(set(self.roles)) != len(self.roles)
                or {"ADMIN", "GATE_SIGNER"} <= set(self.roles)):
            raise ValueError("invalid role combination")
        return self


class PasswordChange(StrictContract):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class AccountStatus(StrictContract):
    enabled: bool


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, session: DB,
          settings: Config):
    if settings.auth_mode != "authenticated":
        deny("LOCAL_MODE_HAS_NO_LOGIN", 409)
    origin = request.headers.get("origin")
    if (request.headers.get("x-studio-request") != "1"
            or origin and origin.rstrip("/") != str(request.base_url).rstrip("/")):
        deny("CSRF_CHECK_FAILED")
    user = session.scalar(select(StudioUser).where(
        StudioUser.username == body.username).with_for_update())
    now = datetime.now(UTC)
    valid = verify_password(body.password, user.password_hash) if user else verify_password(
        body.password, "pbkdf2-sha256$600000$unknown-user$" + "0" * 64)
    if (not user or not user.enabled or not valid
            or user.locked_until and aware(user.locked_until) > now):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now + timedelta(minutes=15)
        session.add(StudioSecurityEvent(actor="ANONYMOUS", action="LOGIN_FAILED",
                                        subject=body.username))
        # Return instead of raise so failed-login counters and events commit.
        return JSONResponse({"detail": {"code": "LOGIN_FAILED"}}, status_code=401)
    user.failed_logins, user.locked_until = 0, None
    token = secrets.token_hex(32)
    old_token = request.cookies.get(COOKIE)
    if old_token:
        session.execute(delete(StudioSession).where(
            StudioSession.token_hash == token_hash(old_token)))
    session.execute(delete(StudioSession).where(StudioSession.expires_at <= now))
    session.add(StudioSession(token_hash=token_hash(token), user_id=user.id,
                              expires_at=now + timedelta(hours=8)))
    session.add(StudioSecurityEvent(actor=user.id, action="LOGIN_SUCCEEDED", subject=user.id))
    response.set_cookie(COOKIE, token, max_age=8 * 3600, httponly=True,
                        secure=settings.session_cookie_secure, samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"
    return user_dict(user)


@router.get("/me")
def me(request: Request, settings: Config):
    return request.state.principal | {"auth_mode": settings.auth_mode}


@router.post("/logout")
def logout(request: Request, response: Response, session: DB):
    session.execute(delete(StudioSession).where(
        StudioSession.token_hash == token_hash(request.cookies.get(COOKIE, ""))))
    actor = request.state.principal["id"]
    session.add(StudioSecurityEvent(actor=actor, action="LOGOUT", subject=actor))
    response.delete_cookie(COOKIE, path="/")
    return {"logged_out": True}


@router.post("/password")
def change_password(body: PasswordChange, request: Request, response: Response, session: DB):
    user = session.get(StudioUser, request.state.principal["id"])
    if not user or not verify_password(body.current_password, user.password_hash):
        deny("CURRENT_PASSWORD_INCORRECT", 400)
    user.password_hash = password_hash(body.new_password)
    session.execute(delete(StudioSession).where(StudioSession.user_id == user.id))
    session.add(StudioSecurityEvent(actor=user.id, action="PASSWORD_CHANGED", subject=user.id))
    response.delete_cookie(COOKIE, path="/")
    return {"login_required": True}


@router.get("/users")
def users(session: DB):
    return {"users": [user_dict(user) for user in session.scalars(select(StudioUser).order_by(
        StudioUser.username))]}


@router.post("/users", status_code=201)
def add_user(body: AccountCreate, request: Request, session: DB, settings: Config):
    if settings.auth_mode != "authenticated":
        deny("AUTHENTICATION_REQUIRED_FOR_ACCOUNT_MANAGEMENT", 409)
    try:
        return user_dict(create_account(session, body.username, body.password, body.roles,
                                        request.state.principal["id"]))
    except ValueError:
        deny("ACCOUNT_CONFLICT", 409)


@router.put("/users/{user_id}/status")
def account_status(user_id: UUID, body: AccountStatus, request: Request, session: DB):
    # Serialize administrators so concurrent changes cannot disable every administrator.
    users = session.scalars(select(StudioUser).order_by(StudioUser.id).with_for_update()).all()
    user = next((u for u in users if u.id == str(user_id)), None)
    if not user:
        deny("ACCOUNT_NOT_FOUND", 404)
    if user.id == request.state.principal["id"]:
        deny("CANNOT_DISABLE_CURRENT_ACCOUNT", 409)
    if not body.enabled and "ADMIN" in user.roles and not any(
            u.enabled and "ADMIN" in u.roles and u.id != user.id for u in users):
        deny("LAST_ADMIN_REQUIRED", 409)
    user.enabled = body.enabled
    session.execute(delete(StudioSession).where(StudioSession.user_id == user.id))
    action = "ACCOUNT_ENABLED" if body.enabled else "ACCOUNT_DISABLED"
    session.add(StudioSecurityEvent(actor=request.state.principal["id"],
                                    action=action, subject=user.id))
    return user_dict(user)


@router.get("/events")
def security_events(session: DB):
    records = session.scalars(select(StudioSecurityEvent).order_by(
        StudioSecurityEvent.created_at.desc(), StudioSecurityEvent.id.desc()).limit(100))
    return {"events": [{"id": e.id, "actor": e.actor, "action": e.action, "subject": e.subject,
                        "created_at": e.created_at.isoformat()} for e in records]}
