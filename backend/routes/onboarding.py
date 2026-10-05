"""
Onboarding route – creates a new learner profile in MongoDB.
"""

from fastapi import APIRouter, HTTPException

from models.learner import LearnerCreate, LearnerInDB, LearnerResponse
from database import learners_collection

router = APIRouter(prefix="/api")


@router.post("/onboard", response_model=LearnerResponse)
def onboard_learner(data: LearnerCreate):
    """
    Create a new learner profile.

    Initialises a skill_profile with default scores:
    - known_topics → 0.5
    - weak_topics  → 0.2
    """
    # Build initial skill profile
    skill_profile: dict[str, float] = {}
    for topic in data.known_topics:
        skill_profile[topic] = 0.5
    for topic in data.weak_topics:
        skill_profile[topic] = 0.2

    learner = LearnerInDB(
        name=data.name,
        learning_goal=data.learning_goal,
        known_topics=data.known_topics,
        weak_topics=data.weak_topics,
        skill_profile=skill_profile,
    )

    try:
        result = learners_collection().insert_one(learner.model_dump())
    except Exception:
        raise HTTPException(status_code=500, detail="A database error occurred. Please try again later.")

    return LearnerResponse(
        success=True,
        learner_id=str(result.inserted_id),
        message="Learner onboarded successfully",
    )
