"""Owner sign-in for the Control Center (see app/services/owner_auth.py)."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services import owner_auth
from app.services.audit import log_audit_event

router = APIRouter(prefix="/owner", tags=["Owner session (Control Center)"])


class LoginBody(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


class SessionOut(BaseModel):
    auth_enabled: bool
    authenticated: bool
    misconfigured: bool


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/session", response_model=SessionOut, summary="Whether owner sign-in is on and this browser is signed in")
def session(request: Request):
    enabled = owner_auth.auth_enabled()
    return SessionOut(
        auth_enabled=enabled or owner_auth.misconfigured(),
        authenticated=(not enabled and not owner_auth.misconfigured())
        or owner_auth.token_valid(request.cookies.get(owner_auth.COOKIE_NAME)),
        misconfigured=owner_auth.misconfigured(),
    )


@router.post("/login", response_model=SessionOut, summary="Sign in as the owner")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    if owner_auth.misconfigured():
        raise HTTPException(503, detail={"code": "OWNER_AUTH_NOT_CONFIGURED",
                                         "message": "Owner sign-in is required but OWNER_PASSWORD is not set on the server."})
    if not owner_auth.auth_enabled():
        return SessionOut(auth_enabled=False, authenticated=True, misconfigured=False)
    client = _client(request)
    if owner_auth.throttle.blocked(client):
        raise HTTPException(429, detail={"code": "TOO_MANY_ATTEMPTS", "message": "Too many attempts. Try again in a few minutes."})
    if not owner_auth.password_ok(body.password):
        owner_auth.throttle.fail(client)
        log_audit_event(db, "OWNER_LOGIN_FAILED", "Owner", "owner", {"client": client})
        raise HTTPException(401, detail={"code": "OWNER_LOGIN_FAILED", "message": "Wrong password."})
    owner_auth.throttle.reset(client)
    response.set_cookie(
        owner_auth.COOKIE_NAME, owner_auth.issue_token(),
        max_age=get_settings().OWNER_SESSION_HOURS * 3600, httponly=True, samesite="lax",
        secure=get_settings().app_base_url.startswith("https://"), path="/",
    )
    log_audit_event(db, "OWNER_SIGNED_IN", "Owner", "owner", {"client": client})
    return SessionOut(auth_enabled=True, authenticated=True, misconfigured=False)


@router.post("/logout", response_model=SessionOut, summary="Sign out")
def logout(response: Response):
    response.delete_cookie(owner_auth.COOKIE_NAME, path="/")
    return SessionOut(auth_enabled=owner_auth.auth_enabled(), authenticated=not owner_auth.auth_enabled(),
                      misconfigured=owner_auth.misconfigured())
