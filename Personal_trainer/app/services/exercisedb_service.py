"""Fetch exercises from free-exercise-db (GitHub) and cache in the database."""
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.exercise import Exercise

# Completely free, no API key — static JSON dataset on GitHub
_FREE_EXERCISE_DB_URL = (
    "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
)
_IMAGE_BASE_URL = (
    "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises"
)

# Map exercise category → body_part label used in our DB
_CATEGORY_MAP = {
    "strength": "strength",
    "stretching": "stretching",
    "plyometrics": "plyometrics",
    "strongman": "strongman",
    "powerlifting": "powerlifting",
    "cardio": "cardio",
    "olympic weightlifting": "olympic weightlifting",
}


async def _fetch_all_exercises() -> list[dict]:
    """Download the full exercise dataset from free-exercise-db on GitHub."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(_FREE_EXERCISE_DB_URL)
        resp.raise_for_status()
        return resp.json()


def _image_url(images: list[str]) -> str:
    """Return URL to the first image for an exercise, or empty string."""
    if not images:
        return ""
    return f"{_IMAGE_BASE_URL}/{images[0]}"


async def sync_exercises(db: AsyncSession) -> int:
    """Fetch all exercises from free-exercise-db and upsert into the local cache."""
    raw = await _fetch_all_exercises()
    count = 0

    for item in raw:
        ex_id = str(item.get("id", ""))
        if not ex_id:
            continue

        name = (item.get("name") or "").lower()
        body_part = (item.get("category") or "").lower()
        equipment = (item.get("equipment") or "body only").lower()
        target_muscle = (item.get("primaryMuscles") or [""])[0].lower()
        secondary_muscles = [m.lower() for m in (item.get("secondaryMuscles") or [])]
        gif_url = _image_url(item.get("images") or [])
        instructions = item.get("instructions") or []

        result = await db.execute(select(Exercise).where(Exercise.id == ex_id))
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = name
            existing.body_part = body_part
            existing.equipment = equipment
            existing.target_muscle = target_muscle
            existing.secondary_muscles = secondary_muscles
            existing.gif_url = gif_url
            existing.instructions = instructions
            existing.cached_at = datetime.now(timezone.utc)
        else:
            db.add(Exercise(
                id=ex_id,
                name=name,
                body_part=body_part,
                equipment=equipment,
                target_muscle=target_muscle,
                secondary_muscles=secondary_muscles,
                gif_url=gif_url,
                instructions=instructions,
            ))
        count += 1

    await db.commit()
    return count


async def get_all_muscle_names(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Exercise.target_muscle).distinct()
    )
    primary = [r[0] for r in result.fetchall()]

    result2 = await db.execute(select(Exercise.secondary_muscles))
    secondary_all = set()
    for row in result2.fetchall():
        secondary_all.update(row[0] or [])

    return sorted(set(primary) | secondary_all)
