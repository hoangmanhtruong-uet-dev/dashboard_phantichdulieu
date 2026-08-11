import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.auth.dependencies import (
    AuthContext,
    current_context,
    get_auth_repository,
    require_admin,
    require_csrf,
    require_owner,
)
from backend.auth.rate_limit import login_rate_limiter
from backend.auth.schemas import (
    ForgotPasswordRequest,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    LoginRequest,
    MemberRoleUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    WorkspaceSwitchRequest,
)
from backend.auth.security import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    create_access_token,
    hash_password,
    new_token,
    safe_redirect,
    set_auth_cookies,
    validate_password,
    verify_password,
)
from backend.config import settings
from backend.responses import success_response
from data.auth_repository import AuthRepository


router = APIRouter(prefix="/api/auth", tags=["authentication"])
workspace_router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _client_info(request: Request) -> tuple[str, str]:
    return (
        request.client.host if request.client else "unknown",
        request.headers.get("user-agent", "unknown"),
    )


def _public_session(context: AuthContext, repository: AuthRepository) -> dict:
    return {
        "user": {
            "id": context.user_id,
            "email": context.email,
            "full_name": context.full_name,
            "job_title": context.job_title,
            "phone": context.phone,
        },
        "workspace": {
            "id": context.workspace_id,
            "name": context.workspace_name,
            "slug": context.workspace_slug,
            "role": context.role,
        },
        "workspaces": repository.memberships(context.user_id),
    }


def _issue_session_response(
    request: Request,
    repository: AuthRepository,
    user: dict,
    workspace: dict,
    *,
    redirect_to: str | None = None,
    status_code: int = 200,
) -> JSONResponse:
    ip, agent = _client_info(request)
    session_id, refresh_token = repository.create_session(
        user["id"], workspace["id"], ip, agent
    )
    access_token, access_expires = create_access_token(user["id"], session_id)
    csrf_token = new_token()
    response = JSONResponse(
        success_response(
            {
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user["full_name"],
                },
                "workspace": workspace,
                "access_expires_at": access_expires.isoformat(),
                "redirect_to": safe_redirect(redirect_to),
            }
        ),
        status_code=status_code,
    )
    set_auth_cookies(response, access_token, refresh_token, csrf_token)
    return response


@router.post("/register", status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    repository: AuthRepository = Depends(get_auth_repository),
):
    try:
        password_hash = hash_password(payload.password)
        user, workspace = repository.register_owner(
            payload.email, payload.full_name, password_hash, payload.workspace_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        )
    if payload.invitation_token:
        invited_workspace = repository.accept_invitation(
            payload.invitation_token, user["id"]
        )
        if invited_workspace:
            workspace = (
                repository.membership(user["id"], invited_workspace) or workspace
            )
    return _issue_session_response(
        request, repository, user, workspace, status_code=201
    )


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    repository: AuthRepository = Depends(get_auth_repository),
):
    ip, _ = _client_info(request)
    key = f"{ip}:{payload.email.lower()}"
    if login_rate_limiter.is_blocked(key):
        raise HTTPException(
            status_code=429, detail="Too many login attempts. Try again later"
        )
    user = repository.find_user_by_email(payload.email)
    if (
        not user
        or not user["is_active"]
        or not verify_password(payload.password, user["password_hash"])
    ):
        login_rate_limiter.fail(key)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    memberships = repository.memberships(user["id"])
    if not memberships:
        raise HTTPException(status_code=403, detail="No workspace access")
    login_rate_limiter.success(key)
    return _issue_session_response(
        request, repository, user, memberships[0], redirect_to=payload.redirect_to
    )


@router.post("/refresh", dependencies=[Depends(require_csrf)])
def refresh(
    request: Request, repository: AuthRepository = Depends(get_auth_repository)
):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    record, replacement, status = repository.rotate_refresh(token)
    if status != "ok" or not record or not replacement:
        response = JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Refresh token is invalid, expired or revoked",
                },
            },
        )
        clear_auth_cookies(response)
        return response
    access_token, expires = create_access_token(record["user_id"], record["session_id"])
    response = JSONResponse(
        success_response({"access_expires_at": expires.isoformat()})
    )
    set_auth_cookies(
        response,
        access_token,
        replacement,
        request.cookies.get("nexus_csrf_token") or new_token(),
    )
    return response


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(
    context: AuthContext = Depends(current_context),
    repository: AuthRepository = Depends(get_auth_repository),
):
    repository.revoke_session(context.session_id)
    response = JSONResponse(success_response({"logged_out": True}))
    clear_auth_cookies(response)
    return response


@router.get("/session")
def session(
    context: AuthContext = Depends(current_context),
    repository: AuthRepository = Depends(get_auth_repository),
):
    return success_response(_public_session(context, repository))


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    repository: AuthRepository = Depends(get_auth_repository),
):
    user = repository.find_user_by_email(payload.email)
    reset_token = (
        repository.create_password_reset(user["id"])
        if user and user["is_active"]
        else None
    )
    meta = (
        {"reset_token": reset_token}
        if reset_token and settings.app_env == "test"
        else None
    )
    return success_response(
        {
            "message": "If the account exists, password reset instructions have been prepared"
        },
        meta=meta,
    )


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    repository: AuthRepository = Depends(get_auth_repository),
):
    try:
        validate_password(payload.password)
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not repository.consume_password_reset(payload.token, password_hash):
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
    return success_response({"password_reset": True, "sessions_invalidated": True})


@workspace_router.get("")
def list_workspaces(
    context: AuthContext = Depends(current_context),
    repository: AuthRepository = Depends(get_auth_repository),
):
    return success_response(repository.memberships(context.user_id))


@workspace_router.post("/switch", dependencies=[Depends(require_csrf)])
def switch_workspace(
    payload: WorkspaceSwitchRequest,
    request: Request,
    context: AuthContext = Depends(current_context),
    repository: AuthRepository = Depends(get_auth_repository),
):
    if not repository.switch_workspace(
        context.session_id, context.user_id, payload.workspace_id
    ):
        raise HTTPException(status_code=403, detail="Workspace access denied")
    repository.revoke_session(context.session_id)
    user = repository.find_user(context.user_id)
    workspace = repository.membership(context.user_id, payload.workspace_id)
    if not user or not workspace:
        raise HTTPException(status_code=403, detail="Workspace access denied")
    return _issue_session_response(request, repository, user, workspace)


@workspace_router.get("/current/members")
def list_members(
    context: AuthContext = Depends(require_admin),
    repository: AuthRepository = Depends(get_auth_repository),
):
    return success_response(repository.list_members(context.workspace_id))


@workspace_router.post(
    "/current/invitations", status_code=201, dependencies=[Depends(require_csrf)]
)
def invite_member(
    payload: InvitationCreateRequest,
    context: AuthContext = Depends(require_admin),
    repository: AuthRepository = Depends(get_auth_repository),
):
    try:
        invite, token = repository.create_invitation(
            context.workspace_id, payload.email, payload.role, context.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    # No email provider is connected in Phase 2; an authorized admin receives a copyable token.
    return success_response({**invite, "invitation_token": token})


@workspace_router.post("/invitations/accept", dependencies=[Depends(require_csrf)])
def accept_invitation(
    payload: InvitationAcceptRequest,
    context: AuthContext = Depends(current_context),
    repository: AuthRepository = Depends(get_auth_repository),
):
    workspace_id = repository.accept_invitation(payload.token, context.user_id)
    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Invitation is invalid, expired or belongs to another email",
        )
    return success_response({"accepted": True, "workspace_id": workspace_id})


@workspace_router.patch(
    "/current/members/{user_id}", dependencies=[Depends(require_csrf)]
)
def update_member_role(
    user_id: int,
    payload: MemberRoleUpdateRequest,
    context: AuthContext = Depends(require_owner),
    repository: AuthRepository = Depends(get_auth_repository),
):
    if not repository.update_member_role(context.workspace_id, user_id, payload.role):
        raise HTTPException(
            status_code=404, detail="Member not found or owner role cannot be changed"
        )
    return success_response({"user_id": user_id, "role": payload.role})
