"""
Adaptive recommendation Pydantic models for FriendOS Phase 5.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


RecommendationType = Literal[
    "REVIEW_CONCEPT",
    "PRACTICE_EASY",
    "PRACTICE_STANDARD",
    "PRACTICE_HARD",
    "MOVE_TO_NEXT_TOPIC",
    "REVIEW_WITH_HINT",
]

DifficultyType = Literal["beginner", "intermediate", "advanced"]


# ── AI Output Validation Models ───────────────────────────────────────

class AdaptiveRecommendation(BaseModel):
    """The structured recommendation expected from Gemma."""
    recommendation_type: RecommendationType
    topic: str
    difficulty: DifficultyType
    reason: str
    activity: str
    evidence: list[str] = Field(..., min_length=1)


# ── Database Models ───────────────────────────────────────────────────

class RecommendationInDB(BaseModel):
    """Document stored in the adaptive_recommendations collection."""
    learner_id: str
    material_id: str
    recommendation_type: RecommendationType
    topic: str
    difficulty: str
    reason: str
    activity: str
    evidence: list[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── API Models ────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    learner_id: str
    material_id: str


class RecommendResponse(BaseModel):
    success: bool
    recommendation: AdaptiveRecommendation


class HistoryResponse(BaseModel):
    learner_id: str
    history: list[dict]
