from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class NutritionGenerateRequest(BaseModel):
    dietary_restrictions: Optional[str] = None
    goal_override: Optional[str] = None


class NutritionPlanResponse(BaseModel):
    id: UUID
    daily_calories: Optional[int]
    macros: Optional[Dict[str, Any]]
    plan_data: Dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}
