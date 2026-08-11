from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]
Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]
Role = Literal["OWNER", "ADMIN", "ANALYST", "VIEWER"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictModel):
    email: Email
    password: Password
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
    ]
    workspace_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
    ] = "My Workspace"
    invitation_token: Optional[str] = Field(default=None, min_length=32, max_length=256)


class LoginRequest(StrictModel):
    email: Email
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    redirect_to: Optional[str] = Field(default=None, max_length=500)


class ForgotPasswordRequest(StrictModel):
    email: Email


class ResetPasswordRequest(StrictModel):
    token: Annotated[str, StringConstraints(min_length=32, max_length=256)]
    password: Password


class WorkspaceSwitchRequest(StrictModel):
    workspace_id: int = Field(gt=0)


class InvitationCreateRequest(StrictModel):
    email: Email
    role: Literal["ADMIN", "ANALYST", "VIEWER"]


class InvitationAcceptRequest(StrictModel):
    token: Annotated[str, StringConstraints(min_length=32, max_length=256)]


class MemberRoleUpdateRequest(StrictModel):
    role: Literal["ADMIN", "ANALYST", "VIEWER"]
