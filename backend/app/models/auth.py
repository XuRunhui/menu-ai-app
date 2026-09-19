"""Request/response models for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]{3,32}$"


class RegisterRequest(BaseModel):
    username: str = Field(..., pattern=USERNAME_PATTERN)
    # Upper bound keeps a single request from burning excessive hashing time.
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class GoogleLoginRequest(BaseModel):
    # ID token (JWT) returned by the Google Identity Services button.
    credential: str = Field(..., min_length=20, max_length=4096)


class AuthConfigResponse(BaseModel):
    auth_enabled: bool = False
    google_client_id: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    created_at: datetime
