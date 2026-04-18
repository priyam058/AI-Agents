from datetime import time as dt_time
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.schedule import Schedule, ScheduleEvent
from app.models.user import User
from app.models.profile import UserProfile
from app.schemas.schedule import (
    EventRequest,
    EventResponse,
    EventUpdateRequest,
    OptimizeRequest,
    OptimizeResponse,
    ScheduleRequest,
    ScheduleResponse,
    VoiceEventRequest,
)
from app.services.claude_service import extract_schedule_events, optimize_schedule
from app.services.profile_service import decrypt_profile_for_prompt

router = APIRouter()


async def _get_or_create_schedule(user_id, db: AsyncSession) -> Schedule:
    result = await db.execute(select(Schedule).where(Schedule.user_id == user_id))
    schedule = result.scalar_one_or_none()
    if not schedule:
        schedule = Schedule(user_id=user_id)
        db.add(schedule)
        await db.flush()
    return schedule


@router.get("", response_model=ScheduleResponse)
async def get_schedule(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await _get_or_create_schedule(current_user.id, db)
    result = await db.execute(
        select(ScheduleEvent).where(ScheduleEvent.schedule_id == schedule.id)
    )
    events = result.scalars().all()
    await db.commit()
    return ScheduleResponse(events=[EventResponse.model_validate(e) for e in events])


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_events(
    body: ScheduleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await _get_or_create_schedule(current_user.id, db)
    new_events = [
        ScheduleEvent(
            schedule_id=schedule.id,
            day=e.day,
            start_time=e.start_time,
            end_time=e.end_time,
            label=e.label,
            event_type=e.event_type,
        )
        for e in body.events
    ]
    db.add_all(new_events)
    await db.commit()
    for event in new_events:
        await db.refresh(event)
    return ScheduleResponse(events=[EventResponse.model_validate(e) for e in new_events])


@router.post("/text", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def add_events_from_text(
    body: VoiceEventRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add calendar events from natural language text.
    e.g. 'I have a meeting Monday 9 to 11am and yoga Wednesday 6 to 7pm'"""
    extracted = await extract_schedule_events(body.text)
    if not extracted:
        raise HTTPException(status_code=422, detail="Could not extract any events from the text")

    def _parse_time(t) -> dt_time:
        if isinstance(t, dt_time):
            return t
        h, m = str(t).split(":")[:2]
        return dt_time(int(h), int(m))

    schedule = await _get_or_create_schedule(current_user.id, db)
    new_events = [
        ScheduleEvent(
            schedule_id=schedule.id,
            day=e["day"],
            start_time=_parse_time(e["start_time"]),
            end_time=_parse_time(e["end_time"]),
            label=e.get("label"),
            event_type="busy",
        )
        for e in extracted
    ]
    db.add_all(new_events)
    await db.commit()
    for event in new_events:
        await db.refresh(event)
    return ScheduleResponse(events=[EventResponse.model_validate(e) for e in new_events])


@router.post("/voice", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def add_events_from_voice(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add calendar events via voice. Speak naturally: 'Add a meeting Monday 9 to 11am'"""
    from app.services.whisper_service import transcribe_audio

    def _parse_time(t) -> dt_time:
        if isinstance(t, dt_time):
            return t
        h, m = str(t).split(":")[:2]
        return dt_time(int(h), int(m))

    audio_bytes = await audio.read()
    try:
        transcript = transcribe_audio(audio_bytes, filename=audio.filename or "audio.webm")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not transcribe audio: {str(e)}")

    extracted = await extract_schedule_events(transcript)
    if not extracted:
        raise HTTPException(
            status_code=422,
            detail=f"Transcribed '{transcript}' but could not extract schedule events from it"
        )

    schedule = await _get_or_create_schedule(current_user.id, db)
    new_events = [
        ScheduleEvent(
            schedule_id=schedule.id,
            day=e["day"],
            start_time=_parse_time(e["start_time"]),
            end_time=_parse_time(e["end_time"]),
            label=e.get("label"),
            event_type="busy",
        )
        for e in extracted
    ]
    db.add_all(new_events)
    await db.commit()
    for event in new_events:
        await db.refresh(event)
    return ScheduleResponse(events=[EventResponse.model_validate(e) for e in new_events])


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    body: EventUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await _get_or_create_schedule(current_user.id, db)
    result = await db.execute(
        select(ScheduleEvent).where(
            ScheduleEvent.id == event_id,
            ScheduleEvent.schedule_id == schedule.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)
    return EventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=200)
async def delete_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedule = await _get_or_create_schedule(current_user.id, db)
    result = await db.execute(
        select(ScheduleEvent).where(
            ScheduleEvent.id == event_id,
            ScheduleEvent.schedule_id == schedule.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    await db.delete(event)
    await db.commit()
    return {"message": "event removed"}


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize(
    body: OptimizeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Based on your busy calendar, the PT suggests the best times to work out."""
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding before optimizing schedule")

    schedule = await _get_or_create_schedule(current_user.id, db)
    events_result = await db.execute(
        select(ScheduleEvent).where(
            ScheduleEvent.schedule_id == schedule.id,
            ScheduleEvent.event_type == "busy",
        )
    )
    events = [
        {"day": e.day, "start_time": str(e.start_time), "end_time": str(e.end_time), "label": e.label}
        for e in events_result.scalars().all()
    ]
    await db.commit()

    profile_ctx = decrypt_profile_for_prompt(profile)
    result = await optimize_schedule(profile_ctx, events, body.preferences)
    return OptimizeResponse(**result)
