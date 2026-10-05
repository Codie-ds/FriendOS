"""
Learning behavior and session Pydantic models for FriendOS Phase 4.
"""

from datetime import datetime, timezone
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator


# ── Models for Learning Sessions ──────────────────────────────────────

class StartLearningSessionRequest(BaseModel):
    learner_id: str
    material_id: str
    topic: str


class LearningSessionResponse(BaseModel):
    success: bool
    session_id: str


class LearningSessionInDB(BaseModel):
    """Document stored in the learning_sessions collection."""
    learner_id: str
    material_id: str
    topic: str
    status: Literal["active", "completed"] = "active"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class CompleteSessionResponse(BaseModel):
    success: bool
    session_id: str
    events_recorded: int
    questions_answered: int
    questions_skipped: int


# ── Models for Learning Events ────────────────────────────────────────

class RecordEventRequest(BaseModel):
    session_id: str
    question_id: str
    event_type: Literal["answer", "hint", "skip", "start", "complete"]
    is_correct: Optional[bool] = None
    attempt_number: int = Field(default=1, ge=1)
    time_taken_seconds: Optional[float] = Field(default=None, ge=0.0)
    hint_requested: bool = False
    skipped: bool = False

    @field_validator("time_taken_seconds")
    @classmethod
    def validate_time(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v != v):  # check for NaN
            raise ValueError("time_taken_seconds cannot be NaN")
        return v


class LearningEventInDB(BaseModel):
    """Document stored in the learning_events collection."""
    learner_id: str
    session_id: str
    material_id: str
    topic: str
    question_id: str
    event_type: str
    is_correct: Optional[bool] = None
    attempt_number: int
    time_taken_seconds: Optional[float] = None
    hint_requested: bool
    skipped: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RecordEventResponse(BaseModel):
    success: bool
    event_id: str


# ── Models for Summaries ──────────────────────────────────────────────

class TopicSummary(BaseModel):
    attempts: int
    accuracy: float
    average_time_seconds: float
    hints_requested: int
    skipped: int


class LearnerBehaviorSummary(BaseModel):
    learner_id: str
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    accuracy: float
    average_time_seconds: float
    hints_requested: int
    questions_skipped: int
    topic_summary: dict[str, TopicSummary]


# ── Models for Practice Flow ──────────────────────────────────────────

class PracticeQuestion(BaseModel):
    question_id: str
    question: str
    options: list[str]
    topic: str
    difficulty: str


class PracticeAnswerRequest(BaseModel):
    question_id: str
    selected_answer: int
    attempt_number: int = Field(default=1, ge=1)
    time_taken_seconds: Optional[float] = Field(default=None, ge=0.0)

    @field_validator("time_taken_seconds")
    @classmethod
    def validate_time(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (v != v):
            raise ValueError("time_taken_seconds cannot be NaN")
        return v


class PracticeAnswerResponse(BaseModel):
    success: bool
    is_correct: bool
    event_id: str
