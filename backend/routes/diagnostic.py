"""
Diagnostic assessment routes for FriendOS Phase 3.
"""

from datetime import datetime, timezone
from collections import defaultdict
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException

from database import materials_collection, learners_collection, diagnostic_sessions_collection
from models.diagnostic import (
    StartDiagnosticRequest,
    StartDiagnosticResponse,
    ClientQuestion,
    DiagnosticSessionInDB,
    SubmitDiagnosticRequest,
    SubmitDiagnosticResponse,
    QuestionResult,
    TopicScore
)

router = APIRouter(prefix="/api/diagnostic")


@router.post("/start", response_model=StartDiagnosticResponse)
def start_diagnostic(data: StartDiagnosticRequest):
    """
    Start a diagnostic session.
    Verifies learner and material exist, extracts questions from material,
    creates a session, and returns questions WITHOUT the correct answers.
    """
    # 1. Verify Learner
    try:
        learner_oid = ObjectId(data.learner_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid learner_id")
        
    learner = learners_collection().find_one({"_id": learner_oid})
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")

    # 2. Verify Material
    try:
        material_oid = ObjectId(data.material_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid material_id")
        
    material = materials_collection().find_one({"_id": material_oid})
    if not material:
        raise HTTPException(status_code=404, detail="Learning material not found")

    questions = material.get("diagnostic_questions", [])
    if not questions:
        raise HTTPException(status_code=400, detail="Material has no diagnostic questions")

    # 3. Create Session in DB
    session = DiagnosticSessionInDB(
        learner_id=data.learner_id,
        material_id=data.material_id,
        questions=questions
    )
    
    try:
        result = diagnostic_sessions_collection().insert_one(session.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
        
    session_id = str(result.inserted_id)

    # 4. Format questions for client (exclude correct_answer)
    client_questions = []
    for idx, q in enumerate(questions):
        client_questions.append(
            ClientQuestion(
                question_id=str(idx),
                question=q["question"],
                options=q["options"],
                topic=q["topic"],
                difficulty=q["difficulty"]
            )
        )

    return StartDiagnosticResponse(
        success=True,
        session_id=session_id,
        questions=client_questions
    )


@router.post("/{session_id}/submit", response_model=SubmitDiagnosticResponse)
def submit_diagnostic(session_id: str, data: SubmitDiagnosticRequest):
    """
    Evaluate submitted answers against the stored correct answers.
    Calculates overall and per-topic scores, updates the session and learner profile.
    """
    try:
        session_oid = ObjectId(session_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session_id")
        
    session_doc = diagnostic_sessions_collection().find_one({"_id": session_oid})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session_doc.get("completed_at"):
        raise HTTPException(status_code=400, detail="Session already completed")

    questions = session_doc["questions"]
    answers_map = {ans.question_id: ans.selected_answer for ans in data.answers}
    
    question_results = []
    topic_correct = defaultdict(int)
    topic_total = defaultdict(int)
    
    total_correct = 0
    total_questions = len(questions)

    # Evaluate each question
    for idx, q in enumerate(questions):
        qid = str(idx)
        topic = q["topic"]
        correct_idx = q["correct_answer"]
        
        selected_idx = answers_map.get(qid)
        
        # Validations
        if selected_idx is not None and (selected_idx < 0 or selected_idx > 3):
            raise HTTPException(status_code=400, detail=f"Invalid selected_answer {selected_idx} for question {qid}")

        is_correct = (selected_idx == correct_idx)
        
        question_results.append(
            QuestionResult(
                question_id=qid,
                topic=topic,
                selected_answer=selected_idx,
                correct_answer=correct_idx,
                is_correct=is_correct
            )
        )
        
        topic_total[topic] += 1
        if is_correct:
            topic_correct[topic] += 1
            total_correct += 1

    # Calculate overall and topic scores
    overall_score = total_correct / total_questions if total_questions > 0 else 0.0
    
    topic_scores = []
    skill_profile = {}
    
    for topic, total in topic_total.items():
        correct = topic_correct[topic]
        score = correct / total if total > 0 else 0.0
        
        topic_scores.append(TopicScore(
            topic=topic,
            correct=correct,
            total=total,
            score=score
        ))
        
        skill_profile[topic] = score

    # Update Session in DB
    completed_at = datetime.now(timezone.utc)
    
    diagnostic_sessions_collection().update_one(
        {"_id": session_oid},
        {"$set": {
            "answers": [a.model_dump() for a in data.answers],
            "question_results": [qr.model_dump() for qr in question_results],
            "overall_score": overall_score,
            "topic_scores": [ts.model_dump() for ts in topic_scores],
            "completed_at": completed_at
        }}
    )

    # Update Learner Profile
    learner_id = session_doc["learner_id"]
    try:
        learner_oid = ObjectId(learner_id)
        
        # We merge the new topic scores into the existing skill_profile
        # Note: this is a simple replacement for observed topics for Phase 3.
        # Future phases might use more complex rolling averages.
        update_fields = {
            f"skill_profile.{topic}": score for topic, score in skill_profile.items()
        }
        update_fields["last_diagnostic_session"] = session_id
        update_fields["last_diagnostic_score"] = overall_score
        update_fields["updated_at"] = completed_at
        
        learners_collection().update_one(
            {"_id": learner_oid},
            {"$set": update_fields}
        )
    except InvalidId:
        pass # Ignore if learner_id is somehow invalid

    return SubmitDiagnosticResponse(
        success=True,
        session_id=session_id,
        overall_score=overall_score,
        topic_scores=topic_scores,
        skill_profile=skill_profile
    )


@router.get("/{session_id}")
def get_diagnostic_session(session_id: str):
    """Retrieve a completed diagnostic session."""
    try:
        session_oid = ObjectId(session_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session_id")
        
    session_doc = diagnostic_sessions_collection().find_one({"_id": session_oid})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session_doc["session_id"] = str(session_doc["_id"])
    del session_doc["_id"]
    return session_doc
