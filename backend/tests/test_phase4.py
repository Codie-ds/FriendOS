"""
Tests for FriendOS Phase 4 – Behavior Tracking System.
All tests mock MongoDB. No real API keys or databases needed.
"""

from unittest.mock import patch, MagicMock
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient


# ── Sample Data ───────────────────────────────────────────────────────

MOCK_LEARNER_ID = "507f1f77bcf86cd799439011"
MOCK_MATERIAL_ID = "507f1f77bcf86cd799439012"
MOCK_SESSION_ID = "507f1f77bcf86cd799439013"

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
        import routes.learning
        importlib.reload(routes.learning)
        import main
        importlib.reload(main)

        with TestClient(main.app) as tc:
            yield tc


# ══════════════════════════════════════════════════════════════════════
# LEARNING SESSION TESTS
# ══════════════════════════════════════════════════════════════════════

class TestStartLearningSession:
    
    def test_start_session_success(self, client):
        with patch("routes.learning.learners_collection") as mock_learners, \
             patch("routes.learning.materials_collection") as mock_materials, \
             patch("routes.learning.learning_sessions_collection") as mock_sessions:
            
            mock_learners.return_value.find_one.return_value = {"_id": ObjectId(MOCK_LEARNER_ID)}
            mock_materials.return_value.find_one.return_value = {"_id": ObjectId(MOCK_MATERIAL_ID)}
            
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId(MOCK_SESSION_ID)
            mock_sessions.return_value.insert_one.return_value = mock_result
            
            resp = client.post("/api/learning/session/start", json={
                "learner_id": MOCK_LEARNER_ID,
                "material_id": MOCK_MATERIAL_ID,
                "topic": "recursion"
            })
            
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["session_id"] == MOCK_SESSION_ID

    def test_start_session_invalid_learner(self, client):
        with patch("routes.learning.learners_collection") as mock_learners:
            mock_learners.return_value.find_one.return_value = None
            
            resp = client.post("/api/learning/session/start", json={
                "learner_id": MOCK_LEARNER_ID,
                "material_id": MOCK_MATERIAL_ID,
                "topic": "recursion"
            })
            
        assert resp.status_code == 404
        assert "Learner not found" in resp.json()["detail"]


class TestRecordEvent:
    
    def test_record_event_success(self, client):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions, \
             patch("routes.learning.learning_events_collection") as mock_events:
            
            mock_sessions.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_SESSION_ID),
                "learner_id": MOCK_LEARNER_ID,
                "material_id": MOCK_MATERIAL_ID,
                "topic": "recursion",
                "status": "active"
            }
            
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId("507f1f77bcf86cd799439014")
            mock_events.return_value.insert_one.return_value = mock_result
            
            resp = client.post("/api/learning/event", json={
                "session_id": MOCK_SESSION_ID,
                "question_id": "q1",
                "event_type": "answer",
                "is_correct": True,
                "attempt_number": 1,
                "time_taken_seconds": 15.5
            })
            
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    def test_record_event_negative_time_fails(self, client):
        resp = client.post("/api/learning/event", json={
            "session_id": MOCK_SESSION_ID,
            "question_id": "q1",
            "event_type": "answer",
            "time_taken_seconds": -5.0
        })
        assert resp.status_code == 422 # Pydantic validation

    def test_record_event_completed_session_fails(self, client):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions:
            mock_sessions.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_SESSION_ID),
                "status": "completed"
            }
            
            resp = client.post("/api/learning/event", json={
                "session_id": MOCK_SESSION_ID,
                "question_id": "q1",
                "event_type": "answer"
            })
            
        assert resp.status_code == 400
        assert "Cannot record events for a completed session" in resp.json()["detail"]


class TestCompleteSession:
    
    def test_complete_session_success(self, client):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions, \
             patch("routes.learning.learning_events_collection") as mock_events:
            
            mock_sessions.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_SESSION_ID),
                "status": "active"
            }
            
            # Mock some events
            mock_events.return_value.find.return_value = [
                {"event_type": "answer", "question_id": "q1", "skipped": False},
                {"event_type": "hint", "question_id": "q2", "skipped": False},
                {"event_type": "skip", "question_id": "q2", "skipped": True}
            ]
            
            resp = client.post(f"/api/learning/session/{MOCK_SESSION_ID}/complete")
            
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["events_recorded"] == 3
        assert body["questions_answered"] == 1
        assert body["questions_skipped"] == 1


class TestLearnerSummary:
    
    def test_learner_summary_deterministic_logic(self, client):
        with patch("routes.learning.learning_events_collection") as mock_events:
            # Provide a specific set of events to test calculation logic
            mock_events.return_value.find.return_value = [
                {"topic": "recursion", "question_id": "q1", "event_type": "start", "skipped": False},
                # Answer wrong, 10s
                {"topic": "recursion", "question_id": "q1", "event_type": "answer", "is_correct": False, "time_taken_seconds": 10.0, "skipped": False},
                # Hint
                {"topic": "recursion", "question_id": "q1", "event_type": "hint", "hint_requested": True, "skipped": False},
                # Answer right, 5s
                {"topic": "recursion", "question_id": "q1", "event_type": "answer", "is_correct": True, "time_taken_seconds": 5.0, "skipped": False},
                # Skip another question
                {"topic": "recursion", "question_id": "q2", "event_type": "skip", "skipped": True}
            ]
            
            resp = client.get(f"/api/learning/summary/{MOCK_LEARNER_ID}")
            
        assert resp.status_code == 200
        body = resp.json()
        
        assert body["total_questions"] == 2 # q1, q2
        assert body["correct_answers"] == 1
        assert body["incorrect_answers"] == 1
        assert body["accuracy"] == 0.5 # 1 correct / (1 correct + 1 incorrect)
        assert body["average_time_seconds"] == 7.5 # (10 + 5) / 2
        assert body["hints_requested"] == 1
        assert body["questions_skipped"] == 1
        
        topic_sum = body["topic_summary"]["recursion"]
        assert topic_sum["attempts"] == 2
        assert topic_sum["accuracy"] == 0.5
        assert topic_sum["average_time_seconds"] == 7.5
        assert topic_sum["hints_requested"] == 1
        assert topic_sum["skipped"] == 1
