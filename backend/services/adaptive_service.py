"""
Adaptive Service for FriendOS Phase 5.
Builds learner context, generates recommendations with Gemma, and validates outputs.
"""

import json
from pydantic import ValidationError
from fastapi import HTTPException
from models.adaptive import AdaptiveRecommendation
from services.ai_service import AIService


SYSTEM_PROMPT = """You are FriendOS, an adaptive learning companion.
Your job is to recommend the learner's next learning action.

Use ONLY the learner evidence supplied in the context.
Prioritize topics where the learner shows evidence of difficulty.

Consider:
- skill score
- accuracy
- attempts
- time taken
- hints
- skipped questions
- recent performance

If the learner demonstrates strong mastery, consider moving to the next topic.

Do not make psychological claims (e.g., "The learner is lazy"). Only use observable evidence.
Do not invent learner statistics. All numerical values are evidence and must not be modified or fabricated.
Do not invent topics that are not present in the supplied material.

Return ONLY valid JSON matching this schema:
{
    "recommendation_type": "REVIEW_CONCEPT" | "PRACTICE_EASY" | "PRACTICE_STANDARD" | "PRACTICE_HARD" | "MOVE_TO_NEXT_TOPIC" | "REVIEW_WITH_HINT",
    "topic": "<must be an exact topic name from the material>",
    "difficulty": "beginner" | "intermediate" | "advanced",
    "reason": "Clear explanation based entirely on evidence",
    "activity": "Actionable statement for the learner",
    "evidence": ["point 1", "point 2"]
}
"""

REPAIR_PROMPT = """The JSON you returned was invalid or did not match the required schema.
Please correct the errors and return ONLY valid JSON matching the exact required schema.
Do not include markdown code fences in your output.

Error encountered:
{error}

Previous invalid JSON:
{invalid_json}
"""


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def generate_recommendation(
    learner_profile: dict,
    behavior_summary: dict,
    recent_events: list,
    material: dict,
) -> AdaptiveRecommendation:
    """
    Constructs the prompt, queries Gemma, and validates the output.
    Attempts one repair on failure.
    """
    
    # Extract just the necessary topic strings from the material
    topics = [t["name"] for t in material.get("topics", [])]
    
    context = {
        "learner": {
            "learner_id": str(learner_profile["_id"]),
            "learning_goal": learner_profile.get("learning_goal"),
        },
        "skill_profile": learner_profile.get("skill_profile", {}),
        "behavior_summary": behavior_summary,
        "recent_events": recent_events,
        "learning_material": {
            "material_id": str(material["_id"]),
            "topics": topics
        }
    }
    
    prompt = f"{SYSTEM_PROMPT}\n\nLearner Context:\n{json.dumps(context, indent=2)}\n\nReturn ONLY the JSON recommendation."
    
    ai_service = AIService()
    
    # First attempt
    raw_response = ai_service.generate_response(prompt)
    cleaned_json = _extract_json(raw_response)
    
    try:
        parsed = json.loads(cleaned_json)
        rec = AdaptiveRecommendation(**parsed)
        # Enforce that the topic exists in the material
        if rec.topic not in topics:
            raise ValueError(f"Topic '{rec.topic}' is not in the allowed topics: {topics}")
        return rec
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        error_msg = str(exc)
        invalid_json = cleaned_json

    # Safe retry
    repair_prompt = f"{SYSTEM_PROMPT}\n\n{REPAIR_PROMPT.format(error=error_msg, invalid_json=invalid_json)}"
    repair_response = ai_service.generate_response(repair_prompt)
    cleaned_repair_json = _extract_json(repair_response)
    
    try:
        parsed_repair = json.loads(cleaned_repair_json)
        rec_repair = AdaptiveRecommendation(**parsed_repair)
        if rec_repair.topic not in topics:
            raise ValueError(f"Topic '{rec_repair.topic}' is not in the allowed topics: {topics}")
        return rec_repair
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate a valid adaptive recommendation: {str(exc)}"
        )
