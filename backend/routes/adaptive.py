"""
Adaptive learning engine routes for FriendOS Phase 5.
"""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException

from database import (
    learners_collection,
    materials_collection,
    learning_events_collection,
    adaptive_recommendations_collection,
)
from models.adaptive import (
    RecommendRequest,
    RecommendResponse,
    RecommendationInDB,
    HistoryResponse,
)
from services.adaptive_service import generate_recommendation
from routes.learning import get_learner_summary

router = APIRouter(prefix="/api/adaptive")


@router.post("/recommend", response_model=RecommendResponse)
def recommend(data: RecommendRequest):
    """
    Generate an adaptive recommendation based on the learner's skill profile,
    overall behavior summary, and recent learning events.
    """
    try:
        learner_oid = ObjectId(data.learner_id)
        material_oid = ObjectId(data.material_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format.")

    # 1. Load Learner Data
    learner = learners_collection().find_one({"_id": learner_oid})
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found.")

    # 2. Load Material Data
    material = materials_collection().find_one({"_id": material_oid})
    if not material:
        raise HTTPException(status_code=404, detail="Learning material not found.")

    # 3. Load Behavior Summary
    # We reuse the deterministic Python summary logic from Phase 4
    try:
        summary_model = get_learner_summary(data.learner_id)
        behavior_summary = summary_model.model_dump()
    except HTTPException:
        behavior_summary = {}

    # 4. Load Recent Events (Limit 20)
    cursor = (
        learning_events_collection()
        .find({"learner_id": data.learner_id, "material_id": data.material_id})
        .sort("timestamp", -1)
        .limit(20)
    )
    recent_events = []
    for doc in cursor:
        doc["event_id"] = str(doc["_id"])
        del doc["_id"]
        # Convert datetime to ISO format for JSON serialization in the prompt
        if "timestamp" in doc:
            doc["timestamp"] = doc["timestamp"].isoformat()
        recent_events.append(doc)

    # 5. Call Adaptive Service (Gemma)
    recommendation = generate_recommendation(
        learner_profile=learner,
        behavior_summary=behavior_summary,
        recent_events=recent_events,
        material=material,
    )

    # 6. Save Recommendation History
    rec_db = RecommendationInDB(
        learner_id=data.learner_id,
        material_id=data.material_id,
        recommendation_type=recommendation.recommendation_type,
        topic=recommendation.topic,
        difficulty=recommendation.difficulty,
        reason=recommendation.reason,
        activity=recommendation.activity,
        evidence=recommendation.evidence,
    )
    
    try:
        adaptive_recommendations_collection().insert_one(rec_db.model_dump())
    except Exception as exc:
        # We still return the recommendation even if logging fails, but log it
        print(f"Failed to log adaptive recommendation: {exc}")

    return RecommendResponse(success=True, recommendation=recommendation)


@router.get("/history/{learner_id}", response_model=HistoryResponse)
def get_recommendation_history(learner_id: str):
    """Retrieve the recent recommendation history for a learner."""
    try:
        ObjectId(learner_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid learner_id.")

    cursor = (
        adaptive_recommendations_collection()
        .find({"learner_id": learner_id})
        .sort("created_at", -1)
        .limit(20)
    )
    
    history = []
    for doc in cursor:
        doc["recommendation_id"] = str(doc["_id"])
        del doc["_id"]
        history.append(doc)

    return HistoryResponse(learner_id=learner_id, history=history)
