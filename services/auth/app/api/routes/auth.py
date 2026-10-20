"""Authentication API routes."""

import uuid

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import get_auth_service, get_current_user
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService
from ticketrush_common.security import UserClaims

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Creates a new user profile with email, password, and assigned role."""
    return await auth_service.register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive JWT token pair",
)
async def login(
    request: Request,
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Validates user credentials and issues an access token and refresh token."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    return await auth_service.login(payload, client_ip=client_ip)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and obtain new access token",
)
async def refresh(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Validates an active refresh token, revokes it, and returns a new token pair."""
    return await auth_service.refresh_tokens(payload)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out and invalidate refresh token",
)
async def logout(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """Revokes the submitted refresh token in both database and cache."""
    await auth_service.logout(payload.refresh_token)
    return {"message": "Successfully logged out"}


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
async def get_me(
    claims: UserClaims = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Returns profile details for the currently authenticated user."""
    return await auth_service.get_user_profile(uuid.UUID(claims.user_id))
