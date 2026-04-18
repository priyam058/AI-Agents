from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.profile import OnboardingRequest, ProfileResponse, ProfileUpdateRequest
from app.services.profile_service import decrypt_profile, encrypt_profile_fields, encrypt_update_fields

router = APIRouter()


@router.post("/onboarding", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def onboarding(
    body: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Profile already created — use PATCH to update")

    encrypted = encrypt_profile_fields(body)
    profile = UserProfile(user_id=current_user.id, **encrypted)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return decrypt_profile(profile)


@router.get("/me", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found — complete onboarding first")
    return decrypt_profile(profile)


@router.patch("/me", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    updates = encrypt_update_fields(body)
    for field, value in updates.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return decrypt_profile(profile)


@router.delete("/me", status_code=200)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(User).where(User.id == current_user.id))
    await db.commit()
    return {"message": "account deleted"}
