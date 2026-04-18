"""All Claude API interactions: PT chat, workout generation, nutrition generation, schedule optimization."""
from typing import List

import anthropic

from app.core.config import settings

_PT_SYSTEM_PROMPT = """You are Alex, an expert certified personal trainer with 10+ years of experience.
You are speaking directly to your client in a voice conversation.
Keep responses concise (2-4 sentences max) since they will be spoken aloud.
Always be encouraging, specific, and safety-conscious.
Never recommend exercises that conflict with the client's stated injuries."""

_WORKOUT_SYSTEM_PROMPT = """You are an expert certified personal trainer creating a structured workout plan.
Respond with valid JSON only — no markdown, no extra text.
The JSON must follow this exact shape:
{
  "weeks": [
    {
      "week": 1,
      "days": [
        {
          "day": "Monday",
          "workout_type": "Push",
          "exercises": [
            {
              "name": "Barbell Bench Press",
              "sets": 4,
              "reps": "8-10",
              "rest_seconds": 90,
              "notes": "Keep elbows at 45 degrees"
            }
          ]
        }
      ]
    }
  ]
}"""

_NUTRITION_SYSTEM_PROMPT = """You are a certified nutritionist creating a personalized meal plan.
Respond with valid JSON only — no markdown, no extra text.
The JSON must follow this exact shape:
{
  "daily_calories": 2200,
  "macros": {"protein_g": 165, "carbs_g": 220, "fat_g": 73},
  "meals": [
    {
      "name": "Breakfast",
      "time": "7:00 AM",
      "foods": [
        {"item": "Oatmeal", "amount": "1 cup", "calories": 300, "protein_g": 10}
      ]
    }
  ],
  "hydration_ml": 3000,
  "notes": "..."
}"""

_SCHEDULE_SYSTEM_PROMPT = """You are a fitness scheduling expert. Given a user's weekly BUSY commitments and fitness profile,
identify the FREE gaps in their schedule and suggest optimal workout time slots within those gaps.
Workouts should be 45-90 minutes. Respond with valid JSON only.
{
  "suggested_workout_slots": [
    {
      "day": "Monday",
      "start_time": "07:00",
      "end_time": "08:00",
      "workout_type": "Strength",
      "reason": "You have a free morning before your 9am meeting — perfect for a strength session."
    }
  ]
}"""

_EVENT_EXTRACTION_SYSTEM_PROMPT = """You are a calendar assistant. Extract schedule events from natural language.
Respond with valid JSON only — an array of events.
Each event must have: day (Monday-Sunday), start_time (HH:MM 24h), end_time (HH:MM 24h), label (short description).
Example input: "I have a team meeting Monday from 9 to 10:30 and lunch with client Wednesday 12 to 1pm"
Example output:
[
  {"day": "Monday", "start_time": "09:00", "end_time": "10:30", "label": "Team meeting"},
  {"day": "Wednesday", "start_time": "12:00", "end_time": "13:00", "label": "Client lunch"}
]
If no valid events can be extracted, return an empty array: []"""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def chat_with_pt(
    profile_context: dict,
    message_history: List[dict],
    user_message: str,
) -> str:
    system = (
        f"{_PT_SYSTEM_PROMPT}\n\n"
        f"Client profile: Level: {profile_context['workout_level']}, "
        f"Goal: {profile_context['goal']}, "
        f"Injuries/limitations: {profile_context['injuries']}, "
        f"Age: {profile_context['age']}, "
        f"Weight: {profile_context['weight_kg']}kg, "
        f"Height: {profile_context['height_cm']}cm."
    )

    messages = message_history + [{"role": "user", "content": user_message}]

    client = _client()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=512,
        system=system,
        messages=messages,
    )
    return response.content[0].text


async def generate_workout_plan(profile_context: dict, focus: str | None, duration_weeks: int) -> dict:
    prompt = (
        f"Create a {duration_weeks}-week workout plan for a client with the following profile:\n"
        f"- Fitness level: {profile_context['workout_level']}\n"
        f"- Goal: {profile_context['goal']}\n"
        f"- Age: {profile_context['age']}\n"
        f"- Weight: {profile_context['weight_kg']}kg, Height: {profile_context['height_cm']}cm\n"
        f"- Injuries/limitations: {profile_context['injuries']}\n"
        f"- Focus area: {focus or 'general fitness'}\n\n"
        "Include 3-5 workout days per week with rest days. Use exercise names that match the ExerciseDB library."
    )

    client = _client()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=_WORKOUT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_response(response.content[0].text)


async def generate_nutrition_plan(
    profile_context: dict,
    dietary_restrictions: str | None,
    goal_override: str | None,
) -> dict:
    goal = goal_override or profile_context["goal"]
    prompt = (
        f"Create a daily nutrition plan for:\n"
        f"- Goal: {goal}\n"
        f"- Age: {profile_context['age']}, Weight: {profile_context['weight_kg']}kg, "
        f"Height: {profile_context['height_cm']}cm\n"
        f"- Fitness level: {profile_context['workout_level']}\n"
        f"- Dietary restrictions: {dietary_restrictions or 'none'}\n"
    )

    client = _client()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=_NUTRITION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_response(response.content[0].text)


async def optimize_schedule(profile_context: dict, events: list, preferences: str | None) -> dict:
    if events:
        events_text = "\n".join(
            f"- {e['day']}: {e['start_time']} to {e['end_time']} ({e.get('label', 'commitment')})"
            for e in events
        )
    else:
        events_text = "No commitments entered — treat the full week as available."

    prompt = (
        f"User's busy commitments this week:\n{events_text}\n\n"
        f"Client profile: Level: {profile_context['workout_level']}, Goal: {profile_context['goal']}, "
        f"Injuries: {profile_context['injuries']}\n"
        f"Additional preferences: {preferences or 'none'}\n\n"
        "Find the free gaps between these commitments and suggest 3-5 workout time slots that fit."
    )

    client = _client()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=_SCHEDULE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json_response(response.content[0].text)


def _parse_json_response(text: str):
    """Parse JSON from Claude response, stripping markdown code fences if present."""
    import json
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


async def extract_schedule_events(text: str) -> list[dict]:
    """Extract structured calendar events from natural language text."""
    client = _client()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=512,
        system=_EVENT_EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return _parse_json_response(response.content[0].text)
