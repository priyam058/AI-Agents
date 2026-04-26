from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class NutritionGenerateRequest(BaseModel):
    available_ingredients: Optional[List[str]] = None
    ingredients_text: Optional[str] = None  # free-text alternative to available_ingredients list
    dietary_restrictions: Optional[str] = None
    goal_override: Optional[str] = None


class NutritionPlanResponse(BaseModel):
    id: UUID
    daily_calories: Optional[int]
    macros: Optional[Dict[str, Any]]
    plan_data: Dict[str, Any]
    shopping_list: Optional[List[Dict[str, Any]]] = None
    is_active: bool

    model_config = {"from_attributes": True}
