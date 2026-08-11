from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request

from backend.auth.security import ACCESS_COOKIE, CSRF_COOKIE, decode_access_token
from data.auth_repository import AuthRepository


ROLE_RANK = {"VIEWER": 1, "ANALYST": 2, "ADMIN": 3, "OWNER": 4}


@dataclass(frozen=True)
class AuthContext:
    session_id: str
    user_id: int
    workspace_id: int
    role: str
    email: str
    full_name: str
    job_title: str
    phone: str
    workspace_name: str
    workspace_slug: str


def get_auth_repository(request: Request) -> AuthRepository:
    database_path = Path(request.app.state.database_path)
    return AuthRepository(database_path)


def require_csrf(request: Request) -> None:
    if request.headers.get("Authorization", "").startswith("Bearer "):
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or cookie != header:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def current_context(
    request: Request, repository: AuthRepository = Depends(get_auth_repository)
) -> AuthContext:
    authorization = request.headers.get("Authorization", "")
    token = (
        authorization[7:]
        if authorization.startswith("Bearer ")
        else request.cookies.get(ACCESS_COOKIE)
    )
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_access_token(token)
        user_id, session_id = int(payload["sub"]), str(payload["sid"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    record = repository.session_context(session_id, user_id)
    if not record:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")
    return AuthContext(**record)


def require_min_role(minimum_role: str) -> Callable:
    def dependency(context: AuthContext = Depends(current_context)) -> AuthContext:
        if ROLE_RANK.get(context.role, 0) < ROLE_RANK[minimum_role]:
            raise HTTPException(
                status_code=403, detail=f"{minimum_role} role or higher is required"
            )
        return context

    return dependency


require_viewer = require_min_role("VIEWER")
require_analyst = require_min_role("ANALYST")
require_admin = require_min_role("ADMIN")
require_owner = require_min_role("OWNER")
