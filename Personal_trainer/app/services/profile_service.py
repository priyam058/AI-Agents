"""Handles encrypt-before-write and decrypt-after-read for user profile health fields."""
from app.core.encryption import decrypt, decrypt_optional, encrypt, encrypt_optional
from app.models.profile import UserProfile
from app.schemas.profile import OnboardingRequest, ProfileResponse, ProfileUpdateRequest


def encrypt_profile_fields(data: OnboardingRequest) -> dict:
    return {
        "weight_kg": encrypt(str(data.weight_kg)),
        "height_cm": encrypt(str(data.height_cm)),
        "age": encrypt(str(data.age)),
        "injuries": encrypt_optional(data.injuries),
        "workout_level": encrypt(data.workout_level),
        "goal": encrypt(data.goal),
        "gender": encrypt_optional(data.gender),
    }


def encrypt_update_fields(data: ProfileUpdateRequest) -> dict:
    updates = {}
    if data.weight_kg is not None:
        updates["weight_kg"] = encrypt(str(data.weight_kg))
    if data.height_cm is not None:
        updates["height_cm"] = encrypt(str(data.height_cm))
    if data.age is not None:
        updates["age"] = encrypt(str(data.age))
    if data.injuries is not None:
        updates["injuries"] = encrypt(data.injuries)
    if data.workout_level is not None:
        updates["workout_level"] = encrypt(data.workout_level)
    if data.goal is not None:
        updates["goal"] = encrypt(data.goal)
    if data.gender is not None:
        updates["gender"] = encrypt(data.gender)
    return updates


def decrypt_profile(profile: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        weight_kg=float(decrypt(profile.weight_kg)),
        height_cm=float(decrypt(profile.height_cm)),
        age=int(decrypt(profile.age)),
        injuries=decrypt_optional(profile.injuries),
        workout_level=decrypt(profile.workout_level),
        goal=decrypt(profile.goal),
        gender=decrypt_optional(profile.gender),
    )


def decrypt_profile_for_prompt(profile: UserProfile) -> dict:
    """Return decrypted profile as a plain dict for injecting into Claude prompts."""
    return {
        "weight_kg": float(decrypt(profile.weight_kg)),
        "height_cm": float(decrypt(profile.height_cm)),
        "age": int(decrypt(profile.age)),
        "injuries": decrypt_optional(profile.injuries) or "none",
        "workout_level": decrypt(profile.workout_level),
        "goal": decrypt(profile.goal),
        "gender": decrypt_optional(profile.gender) or "not specified",
    }
