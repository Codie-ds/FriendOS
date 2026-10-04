"""
Diagnostic session Pydantic models for FriendOS Phase 3.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from models.material import DiagnosticQuestion


# ── Client-facing Models (No Answers Exposed) ─────────────────────────

class ClientQuestion(BaseModel):
    """A question sent to the client (excludes correct_answer)."""
    question_id: str
    question: str
    options: list[str] = Field(..., min_length=4, max_length=4)
    topic: str
    difficulty: str


class StartDiagnosticRequest(BaseModel):
    learner_id: str
    material_id: str


class StartDiagnosticResponse(BaseModel):
    success: bool
    session_id: str
    questions: list[ClientQuestion]


# ── Answer Evaluation Models ──────────────────────────────────────────

class LearnerAnswer(BaseModel):
    """An answer submitted by the learner for a specific question."""
    question_id: str
    selected_answer: Optional[int] = Field(default=None, ge=0, le=3)
    # selected_answer is None if the question was skipped.


class SubmitDiagnosticRequest(BaseModel):
    answers: list[LearnerAnswer]


class QuestionResult(BaseModel):
    """The evaluated result of a single question."""
    question_id: str
    topic: str
    selected_answer: Optional[int]
    correct_answer: int
    is_correct: bool


class TopicScore(BaseModel):
    """Performance summary for a specific topic."""
    topic: str
    correct: int
    total: int
    score: float  # correct / total


class SubmitDiagnosticResponse(BaseModel):
    success: bool
    session_id: str
    overall_score: float
    topic_scores: list[TopicScore]
    skill_profile: dict[str, float]


# ── Database Models ───────────────────────────────────────────────────

class DiagnosticSessionInDB(BaseModel):
    """Internal representation stored in the diagnostic_sessions collection."""
    learner_id: str
    material_id: str
    
    # Store questions with internal IDs (e.g., str(index)) so answers can map to them
    questions: list[DiagnosticQuestion]
    
    # Initially None, updated on submission
    answers: Optional[list[LearnerAnswer]] = None
    question_results: Optional[list[QuestionResult]] = None
    overall_score: Optional[float] = None
    topic_scores: Optional[list[TopicScore]] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
