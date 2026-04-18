from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class WorkoutGenerateRequest(BaseModel):
    focus: Optional[str] = None
    duration_weeks: int = 4


class WorkoutSessionRequest(BaseModel):
    plan_id: Optional[UUID] = None
    date: date
    completed_exercises: List[Dict[str, Any]]
    notes: Optional[str] = None


class WorkoutPlanResponse(BaseModel):
    id: UUID
    focus: Optional[str]
    duration_weeks: int
    plan_data: Dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


class WorkoutSessionResponse(BaseModel):
    id: UUID
    date: date
    completed_exercises: List[Dict[str, Any]]
    notes: Optional[str]

    model_config = {"from_attributes": True}
