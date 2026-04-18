import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.rate_limit import limiter

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    hash_token,
    verify_password,
    verify_token_hash,
)
from app.core.config import settings
from app.models.user import PasswordResetToken, RefreshToken, User
from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RecoveryEmailRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.email_service import send_password_reset_email

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        name=body.name,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    refresh_token = create_refresh_token(user.id)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user and user.hashed_password is None:
        raise HTTPException(status_code=400, detail="This account uses Google sign-in. Please log in with Google.")

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    refresh_token = create_refresh_token(user.id)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    tokens = result.scalars().all()

    matched = next((t for t in tokens if verify_token_hash(body.refresh_token, t.token_hash)), None)
    if not matched:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Revoke old token (rotation)
    matched.revoked = True

    user_result = await db.execute(select(User).where(User.id == matched.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    new_refresh = create_refresh_token(user.id)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=200)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.revoked == False)
    )
    tokens = result.scalars().all()
    matched = next((t for t in tokens if verify_token_hash(body.refresh_token, t.token_hash)), None)
    if matched:
        matched.revoked = True
        await db.commit()
    return {"message": "logged out"}


@router.post("/google", response_model=TokenResponse)
async def google_auth(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """Sign in or register via Google ID token (obtained by the frontend via Google OAuth)."""
    google_user = await _verify_google_id_token(body.id_token)

    if not google_user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Google account email is not verified")

    google_email = google_user["email"]
    google_sub = google_user["sub"]
    google_name = google_user.get("name") or google_email.split("@")[0]

    # Look up by google_id first (returning Google user), then by email (account linking)
    result = await db.execute(select(User).where(User.google_id == google_sub))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == google_email))
        user = result.scalar_one_or_none()

        if user:
            # Existing email/password user — link Google to their account
            user.google_id = google_sub
        else:
            # Brand new user — create without password
            user = User(
                email=google_email,
                name=google_name,
                hashed_password=None,
                google_id=google_sub,
                auth_provider="google",
            )
            db.add(user)
            await db.flush()

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    refresh_token = create_refresh_token(user.id)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    ))
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=refresh_token,
    )


@router.put("/recovery-email", response_model=MessageResponse)
async def set_recovery_email(
    body: RecoveryEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set or update the recovery email for the authenticated user. Can be same as primary email."""
    current_user.recovery_email = body.recovery_email
    await db.commit()
    return MessageResponse(message="Recovery email updated")


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Send a password reset link. Always returns 200 to prevent email enumeration."""
    _generic = MessageResponse(message="If that email is registered, a reset link has been sent")

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or user.hashed_password is None:
        return _generic

    send_to = user.recovery_email if user.recovery_email else user.email

    # Invalidate any existing unused tokens for this user
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used == False)
        .values(used=True)
    )

    raw_token = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_expire_minutes),
    ))
    await db.commit()

    reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"
    try:
        await send_password_reset_email(send_to, reset_url, user.name)
    except Exception:
        pass  # Don't leak email failures; log in production

    return _generic


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using the token from the reset email."""
    from app.core.security import hash_reset_token as _hash

    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash(body.token),
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    reset_token = result.scalar_one_or_none()
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    user.hashed_password = hash_password(body.new_password)
    reset_token.used = True

    # Revoke all refresh tokens — force re-login everywhere
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
    )
    await db.commit()

    return MessageResponse(message="Password reset successfully. Please log in.")


async def _verify_google_id_token(id_token: str) -> dict:
    """
    Verify a Google ID token. Runs synchronously in a thread pool because
    google-auth uses the `requests` library internally (blocking I/O).
    """
    def _verify_sync():
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        request = google_requests.Request()
        return google_id_token.verify_oauth2_token(
            id_token,
            request,
            settings.google_client_id,
            clock_skew_in_seconds=10,
        )

    try:
        return await asyncio.to_thread(_verify_sync)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
