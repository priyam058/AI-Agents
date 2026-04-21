from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.nutrition import NutritionPlan
from app.models.profile import UserProfile
from app.models.user import User
from app.schemas.nutrition import NutritionGenerateRequest, NutritionPlanResponse
from app.services.claude_service import generate_nutrition_plan
from app.services.profile_service import decrypt_profile_for_prompt

router = APIRouter()


@router.post("/generate", response_model=NutritionPlanResponse, status_code=status.HTTP_201_CREATED)
async def generate_plan(
    body: NutritionGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete onboarding first")

    await db.execute(
        update(NutritionPlan)
        .where(NutritionPlan.user_id == current_user.id)
        .values(is_active=False)
    )

    profile_ctx = decrypt_profile_for_prompt(profile)
    plan_data = await generate_nutrition_plan(
        profile_ctx,
        body.dietary_restrictions,
        body.goal_override,
        body.available_ingredients,
    )

    plan = NutritionPlan(
        user_id=current_user.id,
        plan_data=plan_data,
        daily_calories=plan_data.get("daily_calories"),
        macros=plan_data.get("macros"),
        dietary_restrictions=body.dietary_restrictions,
        shopping_list=plan_data.get("shopping_list"),
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return NutritionPlanResponse.model_validate(plan)


@router.get("/plan", response_model=NutritionPlanResponse)
async def get_active_plan(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NutritionPlan)
        .where(NutritionPlan.user_id == current_user.id, NutritionPlan.is_active == True)
        .order_by(NutritionPlan.generated_at.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="No active nutrition plan — generate one first")
    return NutritionPlanResponse.model_validate(plan)
