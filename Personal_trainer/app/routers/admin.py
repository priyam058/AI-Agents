"""Admin endpoints — internal maintenance tasks, not exposed to regular users."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.post("/cleanup-audio", tags=["admin"])
async def cleanup_old_audio(x_admin_key: str = Header(...)):
    """
    Delete voice-response MP3 files older than 24 hours from Supabase Storage.
    Protected by a static admin key set in the environment.
    Call this on a schedule (e.g. daily via Railway cron or an external cron job).
    """
    if x_admin_key != settings.admin_key:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not settings.supabase_url or not settings.supabase_service_key:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    import asyncio
    deleted, errors = await asyncio.to_thread(_cleanup_sync)

    return {"deleted": deleted, "errors": errors}


def _cleanup_sync() -> tuple[int, int]:
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_service_key)
    bucket = client.storage.from_("voice-responses")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    deleted = 0
    errors = 0

    # List all top-level "folders" (user IDs)
    try:
        folders = bucket.list("")
    except Exception:
        return 0, 1

    for folder in folders:
        folder_name = folder.get("name", "")
        if not folder_name:
            continue

        try:
            files = bucket.list(folder_name)
        except Exception:
            errors += 1
            continue

        to_delete = []
        for f in files:
            created_raw = f.get("created_at") or f.get("updated_at")
            if not created_raw:
                continue
            # Supabase returns ISO 8601 strings
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            if created_at < cutoff:
                to_delete.append(f"{folder_name}/{f['name']}")

        if to_delete:
            try:
                bucket.remove(to_delete)
                deleted += len(to_delete)
            except Exception:
                errors += len(to_delete)

    return deleted, errors


@router.post("/send-weekly-summary", tags=["admin"])
async def send_weekly_summary(
    x_admin_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Send the weekly summary email to all active users who have a profile.
    Protected by x-admin-key header.
    Trigger manually or via cron-job.org every Sunday.
    """
    if x_admin_key != settings.admin_key:
        raise HTTPException(status_code=403, detail="Forbidden")

    from app.models.nutrition import NutritionPlan
    from app.models.profile import UserProfile
    from app.models.user import User
    from app.models.workout import WorkoutPlan
    from app.services.claude_service import generate_weekly_summary
    from app.services.email_service import send_weekly_summary_email
    from app.services.profile_service import decrypt_profile_for_prompt

    # Get all active users with a profile
    users_result = await db.execute(
        select(User).where(User.is_active == True)
    )
    users = users_result.scalars().all()

    sent = 0
    failed = 0
    skipped = 0

    for user in users:
        try:
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            profile = profile_result.scalar_one_or_none()
            if not profile:
                skipped += 1
                continue

            workout_result = await db.execute(
                select(WorkoutPlan)
                .where(WorkoutPlan.user_id == user.id, WorkoutPlan.is_active == True)
                .order_by(WorkoutPlan.generated_at.desc())
                .limit(1)
            )
            workout_plan = workout_result.scalar_one_or_none()

            nutrition_result = await db.execute(
                select(NutritionPlan)
                .where(NutritionPlan.user_id == user.id, NutritionPlan.is_active == True)
                .order_by(NutritionPlan.generated_at.desc())
                .limit(1)
            )
            nutrition_plan = nutrition_result.scalar_one_or_none()

            profile_ctx = decrypt_profile_for_prompt(profile)
            summary = await generate_weekly_summary(
                profile_ctx,
                workout_plan.plan_data if workout_plan else None,
                nutrition_plan.plan_data if nutrition_plan else None,
            )

            app_url = settings.frontend_url or "https://alex-pt.app"
            await send_weekly_summary_email(
                to_email=user.email,
                user_name=user.name or "there",
                workout_summary=summary["workout_summary"],
                nutrition_summary=summary["nutrition_summary"],
                alex_note=summary["alex_note"],
                app_url=app_url,
            )
            sent += 1

        except Exception:
            failed += 1

    return {"sent": sent, "skipped": skipped, "failed": failed}
