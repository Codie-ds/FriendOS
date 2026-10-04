"""
Learning behavior tracking routes for FriendOS Phase 4.
"""

from datetime import datetime, timezone
from collections import defaultdict
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException

from database import (
    learners_collection,
    materials_collection,
    learning_sessions_collection,
    learning_events_collection,
)
from models.learning import (
    StartLearningSessionRequest,
    LearningSessionResponse,
    LearningSessionInDB,
    RecordEventRequest,
    LearningEventInDB,
    RecordEventResponse,
    CompleteSessionResponse,
    LearnerBehaviorSummary,
    TopicSummary,
)

router = APIRouter(prefix="/api/learning")


# ── 1. Start Session ───────────────────────────────────────────────────

@router.post("/session/start", response_model=LearningSessionResponse)
def start_session(data: StartLearningSessionRequest):
    """Start a new learning/practice session."""
    try:
        learner_oid = ObjectId(data.learner_id)
        material_oid = ObjectId(data.material_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format.")

    if not learners_collection().find_one({"_id": learner_oid}):
        raise HTTPException(status_code=404, detail="Learner not found.")

    if not materials_collection().find_one({"_id": material_oid}):
        raise HTTPException(status_code=404, detail="Material not found.")

    session = LearningSessionInDB(
        learner_id=data.learner_id,
        material_id=data.material_id,
        topic=data.topic,
    )

    try:
        result = learning_sessions_collection().insert_one(session.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return LearningSessionResponse(success=True, session_id=str(result.inserted_id))


# ── 2. Record Event ────────────────────────────────────────────────────

@router.post("/event", response_model=RecordEventResponse)
def record_event(data: RecordEventRequest):
    """Record an observable learning event (answer, hint, skip)."""
    try:
        session_oid = ObjectId(data.session_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session_id.")

    session = learning_sessions_collection().find_one({"_id": session_oid})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.get("status") == "completed":
        raise HTTPException(
            status_code=400, detail="Cannot record events for a completed session."
        )

    event = LearningEventInDB(
        learner_id=session["learner_id"],
        session_id=data.session_id,
        material_id=session["material_id"],
        topic=session["topic"],
        question_id=data.question_id,
        event_type=data.event_type,
        is_correct=data.is_correct,
        attempt_number=data.attempt_number,
        time_taken_seconds=data.time_taken_seconds,
        hint_requested=data.hint_requested,
        skipped=data.skipped,
    )

    try:
        result = learning_events_collection().insert_one(event.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return RecordEventResponse(success=True, event_id=str(result.inserted_id))


# ── 3. Complete Session ────────────────────────────────────────────────

@router.post("/session/{session_id}/complete", response_model=CompleteSessionResponse)
def complete_session(session_id: str):
    """Mark a learning session as completed and return a quick summary."""
    try:
        session_oid = ObjectId(session_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session_id.")

    session = learning_sessions_collection().find_one({"_id": session_oid})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.get("status") == "completed":
        raise HTTPException(status_code=400, detail="Session already completed.")

    learning_sessions_collection().update_one(
        {"_id": session_oid},
        {
            "$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
            }
        },
    )

    events = list(learning_events_collection().find({"session_id": session_id}))
    
    events_recorded = len(events)
    # We count unique questions that had an "answer" event where skipped=False
    answered_qs = {
        e["question_id"]
        for e in events
        if e.get("event_type") == "answer" and not e.get("skipped")
    }
    # We count unique questions that had a "skip" event or skipped=True
    skipped_qs = {
        e["question_id"]
        for e in events
        if e.get("event_type") == "skip" or e.get("skipped")
    }

    return CompleteSessionResponse(
        success=True,
        session_id=session_id,
        events_recorded=events_recorded,
        questions_answered=len(answered_qs),
        questions_skipped=len(skipped_qs),
    )


# ── 4. Retrieve Session ────────────────────────────────────────────────

@router.get("/session/{session_id}")
def get_session(session_id: str):
    """Retrieve details of a specific session."""
    try:
        session_oid = ObjectId(session_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session_id.")

    session = learning_sessions_collection().find_one({"_id": session_oid})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    session["session_id"] = str(session["_id"])
    del session["_id"]
    return session


# ── 5. Retrieve Learner History ────────────────────────────────────────

@router.get("/history/{learner_id}")
def get_learner_history(learner_id: str):
    """Retrieve all learning sessions for a learner."""
    # Just validate ID format
    try:
        ObjectId(learner_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid learner_id.")

    cursor = learning_sessions_collection().find({"learner_id": learner_id}).sort("started_at", -1)
    sessions = []
    for doc in cursor:
        doc["session_id"] = str(doc["_id"])
        del doc["_id"]
        sessions.append(doc)

    return {"learner_id": learner_id, "sessions": sessions}


# ── 6. Learner Behavior Summary ────────────────────────────────────────

@router.get("/summary/{learner_id}", response_model=LearnerBehaviorSummary)
def get_learner_summary(learner_id: str):
    """
    Calculate a deterministic behavior summary in Python from all recorded events.
    Does NOT use Gemma.
    """
    try:
        ObjectId(learner_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid learner_id.")

    events = list(learning_events_collection().find({"learner_id": learner_id}))

    total_correct = 0
    total_incorrect = 0
    total_hints = 0
    total_time = 0.0
    time_events_count = 0
    
    # We define total_questions as unique questions interacted with
    unique_questions = set()
    skipped_questions = set()
    
    # Per-topic accumulators
    topic_attempts = defaultdict(int)
    topic_correct = defaultdict(int)
    topic_time = defaultdict(float)
    topic_time_count = defaultdict(int)
    topic_hints = defaultdict(int)
    topic_skipped = defaultdict(set)

    for e in events:
        topic = e["topic"]
        qid = e["question_id"]
        unique_questions.add(qid)

        # Track skips
        if e.get("event_type") == "skip" or e.get("skipped"):
            skipped_questions.add(qid)
            topic_skipped[topic].add(qid)

        # Track hints
        if e.get("event_type") == "hint" or e.get("hint_requested"):
            total_hints += 1
            topic_hints[topic] += 1

        # Track time
        t = e.get("time_taken_seconds")
        if t is not None:
            total_time += t
            time_events_count += 1
            topic_time[topic] += t
            topic_time_count[topic] += 1

        # Track correctness & attempts (only on answers)
        if e.get("event_type") == "answer" and e.get("is_correct") is not None:
            topic_attempts[topic] += 1
            if e["is_correct"]:
                total_correct += 1
                topic_correct[topic] += 1
            else:
                total_incorrect += 1

    total_q = len(unique_questions)
    accuracy = total_correct / (total_correct + total_incorrect) if (total_correct + total_incorrect) > 0 else 0.0
    avg_time = total_time / time_events_count if time_events_count > 0 else 0.0

    topic_summary_dict = {}
    for topic in topic_attempts.keys() | topic_hints.keys() | topic_skipped.keys() | topic_time.keys():
        attempts = topic_attempts[topic]
        correct = topic_correct[topic]
        t_acc = correct / attempts if attempts > 0 else 0.0
        tc = topic_time_count[topic]
        t_avg_time = topic_time[topic] / tc if tc > 0 else 0.0
        
        topic_summary_dict[topic] = TopicSummary(
            attempts=attempts,
            accuracy=t_acc,
            average_time_seconds=t_avg_time,
            hints_requested=topic_hints[topic],
            skipped=len(topic_skipped[topic])
        )

    return LearnerBehaviorSummary(
        learner_id=learner_id,
        total_questions=total_q,
        correct_answers=total_correct,
        incorrect_answers=total_incorrect,
        accuracy=accuracy,
        average_time_seconds=avg_time,
        hints_requested=total_hints,
        questions_skipped=len(skipped_questions),
        topic_summary=topic_summary_dict
    )
