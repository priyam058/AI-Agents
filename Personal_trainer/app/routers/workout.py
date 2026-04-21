from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.profile import UserProfile
from app.models.user import User
from app.models.workout import WorkoutPlan, WorkoutSession
from app.schemas.workout import (
    WorkoutGenerateRequest,
    WorkoutPlanResponse,
    WorkoutSessionRequest,
    WorkoutSessionResponse,
)
from app.services.claude_service import generate_workout_plan
from app.services.profile_service import decrypt_profile_for_prompt

router = APIRouter()

_DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@router.get("/today")
async def get_todays_workout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return today's workout from the active plan based on current day of week."""
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == current_user.id, WorkoutPlan.is_active == True)
        .order_by(WorkoutPlan.generated_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No active workout plan — generate one first")

    today_name = datetime.now(timezone.utc).strftime("%A")  # "Monday", "Tuesday", etc.

    # Search all weeks for today's day entry
    weeks = plan.plan_data.get("weeks", [])
    today_day = None
    for week in weeks:
        for day_entry in week.get("days", []):
            if day_entry.get("day", "").strip().capitalize() == today_name:
                today_day = day_entry
                break
        if today_day:
            break

    if today_day is None:
        return {
            "day": today_name,
            "is_rest_day": True,
            "workout_type": "Rest",
            "duration_minutes": 0,
            "exercises": [],
        }

    exercises = today_day.get("exercises", [])
    return {
        "day": today_name,
        "is_rest_day": len(exercises) == 0,
        "workout_type": today_day.get("workout_type", "Training"),
        "duration_minutes": today_day.get("duration_minutes", 45),
        "exercises": exercises,
    }


@router.post("/generate", response_model=WorkoutPlanResponse, status_code=status.HTTP_201_CREATED)
async def generate_plan(
    body: WorkoutGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    # Deactivate previous plans
    await db.execute(
        update(WorkoutPlan)
        .where(WorkoutPlan.user_id == current_user.id)
        .values(is_active=False)
    )

    profile_ctx = decrypt_profile_for_prompt(profile)
    plan_data = await generate_workout_plan(profile_ctx, body.focus, body.duration_weeks)

    plan = WorkoutPlan(
        user_id=current_user.id,
        plan_data=plan_data,
        focus=body.focus,
        duration_weeks=body.duration_weeks,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return WorkoutPlanResponse.model_validate(plan)


@router.get("/plan", response_model=WorkoutPlanResponse)
async def get_active_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == current_user.id, WorkoutPlan.is_active == True)
        .order_by(WorkoutPlan.generated_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No active workout plan — generate one first")
    return WorkoutPlanResponse.model_validate(plan)


@router.post("/sessions", response_model=WorkoutSessionResponse, status_code=status.HTTP_201_CREATED)
async def log_session(
    body: WorkoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = WorkoutSession(
        user_id=current_user.id,
        plan_id=body.plan_id,
        date=body.date,
        completed_exercises=body.completed_exercises,
        notes=body.notes,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return WorkoutSessionResponse.model_validate(session)


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == current_user.id)
        .order_by(WorkoutSession.date.desc())
    )
    sessions = result.scalars().all()
    return {"sessions": [WorkoutSessionResponse.model_validate(s) for s in sessions]}
