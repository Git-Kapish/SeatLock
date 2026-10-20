"""Pydantic schemas for authentication requests and responses."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for user registration."""

    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(
        ..., min_length=8, max_length=128, description="Password (minimum 8 characters)"
    )
    role: Literal["user", "admin"] = Field(default="user", description="Account authorization role")


class LoginRequest(BaseModel):
    """Payload for user login."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


class RefreshTokenRequest(BaseModel):
    """Payload for token refresh and rotation."""

    refresh_token: str = Field(..., description="Valid unrevoked refresh token")


class TokenResponse(BaseModel):
    """Token response containing access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="Access token expiration in seconds")


class UserResponse(BaseModel):
    """Public user profile schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    created_at: datetime
