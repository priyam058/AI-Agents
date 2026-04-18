from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel


WorkoutLevel = Literal["Beginner", "Intermediate", "Advanced"]


class OnboardingRequest(BaseModel):
    weight_kg: float
    height_cm: float
    age: int
    workout_level: WorkoutLevel
    goal: str
    injuries: Optional[str] = None
    gender: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    workout_level: Optional[WorkoutLevel] = None
    goal: Optional[str] = None
    injuries: Optional[str] = None
    gender: Optional[str] = None


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    weight_kg: float
    height_cm: float
    age: int
    workout_level: str
    goal: str
    injuries: Optional[str]
    gender: Optional[str]

    model_config = {"from_attributes": True}
