from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import array

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.exercise import Exercise
from app.models.user import User
from app.services.exercisedb_service import get_all_muscle_names, sync_exercises

router = APIRouter()


@router.get("", response_model=List[dict])
async def search_exercises(
    q: Optional[str] = Query(None, description="Search by name"),
    muscle: Optional[str] = Query(None, description="Filter by target or secondary muscle"),
    body_part: Optional[str] = Query(None, description="Filter by body part"),
    equipment: Optional[str] = Query(None, description="Filter by equipment"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Exercise)

    if q:
        stmt = stmt.where(Exercise.name.ilike(f"%{q.lower()}%"))
    if body_part:
        stmt = stmt.where(Exercise.body_part.ilike(f"%{body_part}%"))
    if equipment:
        stmt = stmt.where(Exercise.equipment.ilike(f"%{equipment}%"))
    if muscle:
        stmt = stmt.where(
            or_(
                Exercise.target_muscle.ilike(f"%{muscle}%"),
                Exercise.secondary_muscles.any(muscle.lower()),
            )
        )

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    exercises = result.scalars().all()

    return [
        {
            "id": e.id,
            "name": e.name,
            "body_part": e.body_part,
            "equipment": e.equipment,
            "target_muscle": e.target_muscle,
            "secondary_muscles": e.secondary_muscles,
            "gif_url": e.gif_url,
        }
        for e in exercises
    ]


@router.get("/muscles", response_model=List[str])
async def list_muscles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_all_muscle_names(db)


@router.get("/{exercise_id}", response_model=dict)
async def get_exercise(
    exercise_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Exercise).where(Exercise.id == exercise_id))
    exercise = result.scalar_one_or_none()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    return {
        "id": exercise.id,
        "name": exercise.name,
        "body_part": exercise.body_part,
        "equipment": exercise.equipment,
        "target_muscle": exercise.target_muscle,
        "secondary_muscles": exercise.secondary_muscles,
        "gif_url": exercise.gif_url,
        "instructions": exercise.instructions,
    }


@router.post("/sync", status_code=200)
async def trigger_sync(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await sync_exercises(db)
    return {"message": f"Synced {count} exercises from ExerciseDB"}
