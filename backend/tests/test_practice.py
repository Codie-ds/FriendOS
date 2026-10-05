"""
Tests for the new Practice Flow (Phase 6+ backend capability).
Ensures the server remains the source of truth for answer correctness,
and that correct answers are not exposed to the client.
All tests mock MongoDB to match Phase 1-5 test style.
"""

from unittest.mock import patch, MagicMock
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

MOCK_LEARNER_ID = "507f1f77bcf86cd799439011"
MOCK_MATERIAL_ID = "507f1f77bcf86cd799439012"
MOCK_SESSION_ID = "507f1f77bcf86cd799439013"
MOCK_EVENT_ID = "507f1f77bcf86cd799439014"

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

@pytest.fixture
def mock_material_data():
    return {
        "_id": ObjectId(MOCK_MATERIAL_ID),
        "filename": "practice.pdf",
        "title": "Practice Material",
        "page_count": 1,
        "topics": [{"name": "topicA", "description": "A", "difficulty": "beginner"}],
        "diagnostic_questions": [
            {
                "question": "Q1",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 1,
                "topic": "topicA",
                "difficulty": "beginner"
            },
            {
                "question": "Q2",
                "options": ["W", "X", "Y", "Z"],
                "correct_answer": 2,
                "topic": "topicA",
                "difficulty": "beginner"
            }
        ]
    }

@pytest.fixture
def mock_session_data():
    return {
        "_id": ObjectId(MOCK_SESSION_ID),
        "learner_id": MOCK_LEARNER_ID,
        "material_id": MOCK_MATERIAL_ID,
        "topic": "topicA",
        "status": "active"
    }

class TestPracticeFlow:
    def test_get_practice_question_success(self, client, mock_session_data, mock_material_data):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions, \
             patch("routes.learning.materials_collection") as mock_materials, \
             patch("routes.learning.learning_events_collection") as mock_events:
            
            mock_sessions.return_value.find_one.return_value = mock_session_data
            mock_materials.return_value.find_one.return_value = mock_material_data
            
            # Mock find to return empty list (no events yet)
            mock_events.return_value.find.return_value = []
            
            resp = client.get(f"/api/learning/session/{MOCK_SESSION_ID}/question")
            
        assert resp.status_code == 200
        data = resp.json()
        assert "question_id" in data
        assert "correct_answer" not in data  # CRITICAL: not exposed
        assert data["question_id"] == "0"
        assert data["question"] == "Q1"
        assert data["topic"] == "topicA"

    def test_get_practice_question_skips_answered(self, client, mock_session_data, mock_material_data):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions, \
             patch("routes.learning.materials_collection") as mock_materials, \
             patch("routes.learning.learning_events_collection") as mock_events:
            
            mock_sessions.return_value.find_one.return_value = mock_session_data
            mock_materials.return_value.find_one.return_value = mock_material_data
            
            # Mock find to return one event for question "0"
            mock_events.return_value.find.return_value = [{"question_id": "0", "event_type": "answer"}]
            
            resp = client.get(f"/api/learning/session/{MOCK_SESSION_ID}/question")
            
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_id"] == "1"  # Skipped 0, returns 1
        assert data["question"] == "Q2"

    def test_submit_practice_answer_correct(self, client, mock_session_data, mock_material_data):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions, \
             patch("routes.learning.materials_collection") as mock_materials, \
             patch("routes.learning.learning_events_collection") as mock_events:
            
            mock_sessions.return_value.find_one.return_value = mock_session_data
            mock_materials.return_value.find_one.return_value = mock_material_data
            
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId(MOCK_EVENT_ID)
            mock_events.return_value.insert_one.return_value = mock_result
            
            # Q1 correct_answer is 1
            resp = client.post(f"/api/learning/session/{MOCK_SESSION_ID}/answer", json={
                "question_id": "0",
                "selected_answer": 1,
                "time_taken_seconds": 10.0
            })
            
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["is_correct"] is True
        
        # Verify event was inserted correctly
        call_args = mock_events.return_value.insert_one.call_args[0][0]
        assert call_args["is_correct"] is True
        assert call_args["event_type"] == "answer"
        assert call_args["question_id"] == "0"

    def test_submit_practice_answer_incorrect(self, client, mock_session_data, mock_material_data):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions, \
             patch("routes.learning.materials_collection") as mock_materials, \
             patch("routes.learning.learning_events_collection") as mock_events:
            
            mock_sessions.return_value.find_one.return_value = mock_session_data
            mock_materials.return_value.find_one.return_value = mock_material_data
            
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId(MOCK_EVENT_ID)
            mock_events.return_value.insert_one.return_value = mock_result
            
            # Q1 correct_answer is 1, submitting 2
            resp = client.post(f"/api/learning/session/{MOCK_SESSION_ID}/answer", json={
                "question_id": "0",
                "selected_answer": 2
            })
            
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is False
        
        call_args = mock_events.return_value.insert_one.call_args[0][0]
        assert call_args["is_correct"] is False

    def test_submit_practice_answer_client_cannot_inject_correctness(self, client, mock_session_data, mock_material_data):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions, \
             patch("routes.learning.materials_collection") as mock_materials, \
             patch("routes.learning.learning_events_collection") as mock_events:
            
            mock_sessions.return_value.find_one.return_value = mock_session_data
            mock_materials.return_value.find_one.return_value = mock_material_data
            
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId(MOCK_EVENT_ID)
            mock_events.return_value.insert_one.return_value = mock_result
            
            # Intentionally inject "correct": True in the payload with a wrong answer
            resp = client.post(f"/api/learning/session/{MOCK_SESSION_ID}/answer", json={
                "question_id": "0",
                "selected_answer": 2, # wrong
                "correct": True,      # injection attempt
                "is_correct": True    # injection attempt
            })
            
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is False  # Server side evaluation overwrites

    def test_submit_practice_answer_invalid_question_id(self, client, mock_session_data, mock_material_data):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions, \
             patch("routes.learning.materials_collection") as mock_materials:
            
            mock_sessions.return_value.find_one.return_value = mock_session_data
            mock_materials.return_value.find_one.return_value = mock_material_data
            
            resp = client.post(f"/api/learning/session/{MOCK_SESSION_ID}/answer", json={
                "question_id": "99",
                "selected_answer": 0
            })
            
        assert resp.status_code == 400
        assert "Invalid question_id" in resp.json()["detail"]

    def test_submit_practice_answer_completed_session(self, client, mock_session_data, mock_material_data):
        with patch("routes.learning.learning_sessions_collection") as mock_sessions:
            
            completed_session = dict(mock_session_data)
            completed_session["status"] = "completed"
            mock_sessions.return_value.find_one.return_value = completed_session
            
            resp = client.post(f"/api/learning/session/{MOCK_SESSION_ID}/answer", json={
                "question_id": "0",
                "selected_answer": 1
            })
            
        assert resp.status_code == 400
        assert "Session already completed" in resp.json()["detail"]

