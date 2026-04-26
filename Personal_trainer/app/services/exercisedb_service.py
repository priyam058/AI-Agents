"""Fetch exercises from ExerciseDB open-source API and cache in the database."""
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.exercise import Exercise

_EXERCISEDB_BASE = "https://exercisedb-api.vercel.app/api/v1"


async def _fetch_all_exercises() -> list[dict]:
    """Fetch all exercises in one request (ExerciseDB supports limit up to 2000)."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(
            f"{_EXERCISEDB_BASE}/exercises",
            params={"limit": 1500, "offset": 0},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("exercises", [])


async def sync_exercises(db: AsyncSession) -> int:
    """Fetch all exercises from ExerciseDB and upsert into the local cache. Returns count synced."""
    raw = await _fetch_all_exercises()
    count = 0
    for item in raw:
        ex_id = str(item.get("exerciseId", item.get("id", "")))
        if not ex_id:
            continue

        result = await db.execute(select(Exercise).where(Exercise.id == ex_id))
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = item.get("name", "").lower()
            existing.body_part = item.get("bodyPart", "")
            existing.equipment = item.get("equipment", "")
            existing.target_muscle = item.get("target", "")
            existing.secondary_muscles = item.get("secondaryMuscles", [])
            existing.gif_url = item.get("gifUrl", "")
            existing.instructions = item.get("instructions", [])
            existing.cached_at = datetime.now(timezone.utc)
        else:
            db.add(Exercise(
                id=ex_id,
                name=item.get("name", "").lower(),
                body_part=item.get("bodyPart", ""),
                equipment=item.get("equipment", ""),
                target_muscle=item.get("target", ""),
                secondary_muscles=item.get("secondaryMuscles", []),
                gif_url=item.get("gifUrl", ""),
                instructions=item.get("instructions", []),
            ))
        count += 1

    await db.commit()
    return count


async def get_all_muscle_names(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Exercise.target_muscle).distinct()
    )
    primary = [r[0] for r in result.fetchall()]

    # Also gather unique secondary muscles
    result2 = await db.execute(select(Exercise.secondary_muscles))
    secondary_all = set()
    for row in result2.fetchall():
        secondary_all.update(row[0] or [])

    return sorted(set(primary) | secondary_all)
