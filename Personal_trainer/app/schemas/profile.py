from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class OnboardingRequest(BaseModel):
    weight_kg: float
    height_cm: float
    age: int
    workout_level: str
    goal: str
    injuries: Optional[str] = None
    gender: Optional[str] = None

    @field_validator("workout_level")
    @classmethod
    def normalize_workout_level(cls, v: str) -> str:
        normalized = v.strip().capitalize()
        if normalized not in ("Beginner", "Intermediate", "Advanced"):
            raise ValueError("workout_level must be Beginner, Intermediate, or Advanced")
        return normalized

    @field_validator("goal", "gender", mode="before")
    @classmethod
    def normalize_title_case(cls, v):
        if isinstance(v, str):
            return v.strip().capitalize()
        return v


class ProfileUpdateRequest(BaseModel):
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    age: Optional[int] = None
    workout_level: Optional[str] = None
    goal: Optional[str] = None
    injuries: Optional[str] = None
    gender: Optional[str] = None

    @field_validator("workout_level")
    @classmethod
    def normalize_workout_level(cls, v):
        if v is None:
            return v
        normalized = v.strip().capitalize()
        if normalized not in ("Beginner", "Intermediate", "Advanced"):
            raise ValueError("workout_level must be Beginner, Intermediate, or Advanced")
        return normalized

    @field_validator("goal", "gender", mode="before")
    @classmethod
    def normalize_title_case(cls, v):
        if isinstance(v, str):
            return v.strip().capitalize()
        return v


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
