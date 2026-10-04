"""
Learner Pydantic models for FriendOS.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class LearnerCreate(BaseModel):
    """Schema for the POST /api/onboard request body."""
    name: str
    learning_goal: str
    known_topics: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)


class LearnerInDB(BaseModel):
    """Internal representation stored in MongoDB."""
    name: str
    learning_goal: str
    known_topics: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    skill_profile: dict[str, float] = Field(default_factory=dict)
    last_diagnostic_session: Optional[str] = None
    last_diagnostic_score: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LearnerResponse(BaseModel):
    """Schema returned to the client after onboarding."""
    success: bool
    learner_id: str
    message: str
