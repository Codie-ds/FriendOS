"""
Tests for FriendOS Phase 5 – Adaptive Learning Engine.
All tests mock MongoDB and Gemma API.
"""

import json
from unittest.mock import patch, MagicMock
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from models.adaptive import AdaptiveRecommendation


# ── Sample Data ───────────────────────────────────────────────────────

MOCK_LEARNER_ID = "507f1f77bcf86cd799439011"
MOCK_MATERIAL_ID = "507f1f77bcf86cd799439012"

VALID_GEMMA_RESPONSE = """
```json
{
    "recommendation_type": "PRACTICE_EASY",
    "topic": "recursion",
    "difficulty": "beginner",
    "reason": "Low accuracy and many hints requested.",
    "activity": "Try a basic recursion problem.",
    "evidence": ["accuracy: 0.40"]
}
```
"""

INVALID_TOPIC_RESPONSE = """
{
    "recommendation_type": "PRACTICE_EASY",
    "topic": "quantum physics",
    "difficulty": "beginner",
    "reason": "Test",
    "activity": "Test",
    "evidence": ["Test"]
}
"""

INVALID_TYPE_RESPONSE = """
{
    "recommendation_type": "INVALID_TYPE",
    "topic": "recursion",
    "difficulty": "beginner",
    "reason": "Test",
    "activity": "Test",
    "evidence": ["Test"]
}
"""


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("GEMMA_API_KEY", "test-key")
    monkeypatch.setenv("GEMMA_MODEL", "test-model")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")


@pytest.fixture()
def client():
    with patch("database.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        mock_instance.admin.command.return_value = {"ok": 1}

        import importlib
        import config
        importlib.reload(config)
        import database
        importlib.reload(database)
        import routes.adaptive
        importlib.reload(routes.adaptive)
        import main
        importlib.reload(main)

        with TestClient(main.app) as tc:
            yield tc


# ══════════════════════════════════════════════════════════════════════
# ADAPTIVE ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestAdaptiveRecommendEndpoint:
    
    @patch("services.adaptive_service.AIService")
    def test_recommend_success(self, MockAIService, client):
        mock_ai = MagicMock()
        mock_ai.generate_response.return_value = VALID_GEMMA_RESPONSE
        MockAIService.return_value = mock_ai
        
        with patch("routes.adaptive.learners_collection") as mock_learners, \
             patch("routes.adaptive.materials_collection") as mock_materials, \
             patch("routes.adaptive.adaptive_recommendations_collection") as mock_recs, \
             patch("routes.adaptive.learning_events_collection") as mock_events:
            
            mock_learners.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_LEARNER_ID),
                "skill_profile": {"recursion": 0.25}
            }
            mock_materials.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_MATERIAL_ID),
                "topics": [{"name": "recursion"}]
            }
            mock_events.return_value.find.return_value.sort.return_value.limit.return_value = []
            
            resp = client.post("/api/adaptive/recommend", json={
                "learner_id": MOCK_LEARNER_ID,
                "material_id": MOCK_MATERIAL_ID
            })
            
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["recommendation"]["topic"] == "recursion"
        assert mock_recs.return_value.insert_one.called
        
        # Verify AI service was called with the correct prompt context
        args, _ = mock_ai.generate_response.call_args
        prompt = args[0]
        assert "skill_profile" in prompt
        assert "recursion" in prompt

    def test_recommend_invalid_learner(self, client):
        with patch("routes.adaptive.learners_collection") as mock_learners:
            mock_learners.return_value.find_one.return_value = None
            
            resp = client.post("/api/adaptive/recommend", json={
                "learner_id": MOCK_LEARNER_ID,
                "material_id": MOCK_MATERIAL_ID
            })
            
        assert resp.status_code == 404
        assert "Learner not found" in resp.json()["detail"]


class TestAdaptiveServiceLogic:
    
    @patch("services.adaptive_service.AIService")
    def test_invalid_topic_triggers_repair(self, MockAIService):
        from services.adaptive_service import generate_recommendation
        
        mock_ai = MagicMock()
        # First attempt returns invalid topic. Second returns valid.
        mock_ai.generate_response.side_effect = [INVALID_TOPIC_RESPONSE, VALID_GEMMA_RESPONSE]
        MockAIService.return_value = mock_ai
        
        rec = generate_recommendation(
            learner_profile={"_id": ObjectId(MOCK_LEARNER_ID)},
            behavior_summary={},
            recent_events=[],
            material={"_id": ObjectId(MOCK_MATERIAL_ID), "topics": [{"name": "recursion"}]}
        )
        
        # Ensures that the repair kicked in and parsed the second response successfully
        assert rec.topic == "recursion"
        assert mock_ai.generate_response.call_count == 2
        
    @patch("services.adaptive_service.AIService")
    def test_both_attempts_fail(self, MockAIService):
        from services.adaptive_service import generate_recommendation
        from fastapi import HTTPException
        
        mock_ai = MagicMock()
        mock_ai.generate_response.side_effect = [INVALID_TYPE_RESPONSE, INVALID_TYPE_RESPONSE]
        MockAIService.return_value = mock_ai
        
        with pytest.raises(HTTPException) as excinfo:
            generate_recommendation(
                learner_profile={"_id": ObjectId(MOCK_LEARNER_ID)},
                behavior_summary={},
                recent_events=[],
                material={"_id": ObjectId(MOCK_MATERIAL_ID), "topics": [{"name": "recursion"}]}
            )
            
        assert excinfo.value.status_code == 500
        assert "Failed to generate a valid adaptive recommendation" in str(excinfo.value.detail)


class TestRecommendationHistory:
    
    def test_get_history_success(self, client):
        with patch("routes.adaptive.adaptive_recommendations_collection") as mock_recs:
            mock_recs.return_value.find.return_value.sort.return_value.limit.return_value = [
                {
                    "_id": ObjectId("507f1f77bcf86cd799439019"),
                    "recommendation_type": "PRACTICE_EASY"
                }
            ]
            
            resp = client.get(f"/api/adaptive/history/{MOCK_LEARNER_ID}")
            
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["history"]) == 1
        assert body["history"][0]["recommendation_type"] == "PRACTICE_EASY"
        assert "recommendation_id" in body["history"][0]
