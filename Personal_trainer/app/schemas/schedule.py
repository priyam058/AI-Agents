from datetime import time
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel

EventType = Literal["busy", "workout"]


class EventRequest(BaseModel):
    day: str  # Monday..Sunday
    start_time: time
    end_time: time
    label: Optional[str] = None
    event_type: EventType = "busy"
    is_recurring: bool = False


class EventUpdateRequest(BaseModel):
    day: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    label: Optional[str] = None
    event_type: Optional[EventType] = None
    is_recurring: Optional[bool] = None


class EventResponse(BaseModel):
    id: UUID
    day: str
    start_time: time
    end_time: time
    label: Optional[str]
    event_type: str
    is_recurring: bool = False

    model_config = {"from_attributes": True}


class ScheduleRequest(BaseModel):
    events: List[EventRequest]


class ScheduleResponse(BaseModel):
    events: List[EventResponse]


class VoiceEventRequest(BaseModel):
    text: str  # e.g. "I have a meeting Monday from 9 to 11am"


class OptimizeRequest(BaseModel):
    preferences: Optional[str] = None


class OptimizeDayRequest(BaseModel):
    day: str  # e.g. "Monday"
    preferences: Optional[str] = None


class SuggestedSlot(BaseModel):
    day: str
    start_time: str
    end_time: str
    workout_type: str
    reason: str


class OptimizeResponse(BaseModel):
    suggested_workout_slots: List[SuggestedSlot]
