"""
Tests for FriendOS Phase 3 – Diagnostic Assessment System.
All tests mock MongoDB. No real API keys or databases needed.
"""

import json
from unittest.mock import patch, MagicMock
from bson import ObjectId

import pytest
from fastapi.testclient import TestClient


# ── Sample Data ───────────────────────────────────────────────────────

MOCK_LEARNER_ID = "507f1f77bcf86cd799439011"
MOCK_MATERIAL_ID = "507f1f77bcf86cd799439012"
MOCK_SESSION_ID = "507f1f77bcf86cd799439013"

MOCK_QUESTIONS = [
    {
        "question": "Q1",
        "options": ["A", "B", "C", "D"],
        "correct_answer": 0,
        "topic": "Topic A",
        "difficulty": "beginner"
    },
    {
        "question": "Q2",
        "options": ["A", "B", "C", "D"],
        "correct_answer": 2,
        "topic": "Topic A",
        "difficulty": "intermediate"
    },
    {
        "question": "Q3",
        "options": ["A", "B", "C", "D"],
        "correct_answer": 1,
        "topic": "Topic B",
        "difficulty": "beginner"
    }
]


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    """Ensure config loads without real secrets during tests."""
    monkeypatch.setenv("GEMMA_API_KEY", "test-key")
    monkeypatch.setenv("GEMMA_MODEL", "test-model")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")


@pytest.fixture()
def client():
    """TestClient with mocked MongoDB."""
    with patch("database.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        mock_instance.admin.command.return_value = {"ok": 1}

        import importlib
        import config
        importlib.reload(config)
        import database
        importlib.reload(database)
        import routes.diagnostic
        importlib.reload(routes.diagnostic)
        import main
        importlib.reload(main)

        with TestClient(main.app) as tc:
            yield tc


# ══════════════════════════════════════════════════════════════════════
# DIAGNOSTIC TESTS
# ══════════════════════════════════════════════════════════════════════

class TestDiagnosticStartEndpoint:
    """Tests for POST /api/diagnostic/start"""

    def test_start_success(self, client):
        with patch("routes.diagnostic.learners_collection") as mock_learners, \
             patch("routes.diagnostic.materials_collection") as mock_materials, \
             patch("routes.diagnostic.diagnostic_sessions_collection") as mock_sessions:
            
            mock_learners.return_value.find_one.return_value = {"_id": ObjectId(MOCK_LEARNER_ID)}
            mock_materials.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_MATERIAL_ID),
                "diagnostic_questions": MOCK_QUESTIONS
            }
            
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId(MOCK_SESSION_ID)
            mock_sessions.return_value.insert_one.return_value = mock_result
            
            resp = client.post("/api/diagnostic/start", json={
                "learner_id": MOCK_LEARNER_ID,
                "material_id": MOCK_MATERIAL_ID
            })
            
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["session_id"] == MOCK_SESSION_ID
        assert len(body["questions"]) == 3
        
        # Verify correct_answer is NOT exposed
        for q in body["questions"]:
            assert "correct_answer" not in q
            assert "question_id" in q
            assert "options" in q

    def test_start_invalid_learner(self, client):
        with patch("routes.diagnostic.learners_collection") as mock_learners:
            mock_learners.return_value.find_one.return_value = None
            
            resp = client.post("/api/diagnostic/start", json={
                "learner_id": MOCK_LEARNER_ID,
                "material_id": MOCK_MATERIAL_ID
            })
        assert resp.status_code == 404
        assert "Learner not found" in resp.json()["detail"]


class TestDiagnosticSubmitEndpoint:
    """Tests for POST /api/diagnostic/{session_id}/submit"""

    def test_submit_success_all_correct(self, client):
        with patch("routes.diagnostic.diagnostic_sessions_collection") as mock_sessions, \
             patch("routes.diagnostic.learners_collection") as mock_learners:
            
            mock_sessions.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_SESSION_ID),
                "learner_id": MOCK_LEARNER_ID,
                "questions": MOCK_QUESTIONS,
                "completed_at": None
            }
            
            resp = client.post(f"/api/diagnostic/{MOCK_SESSION_ID}/submit", json={
                "answers": [
                    {"question_id": "0", "selected_answer": 0},
                    {"question_id": "1", "selected_answer": 2},
                    {"question_id": "2", "selected_answer": 1}
                ]
            })
            
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["overall_score"] == 1.0
        
        scores = {ts["topic"]: ts["score"] for ts in body["topic_scores"]}
        assert scores["Topic A"] == 1.0
        assert scores["Topic B"] == 1.0
        
        assert body["skill_profile"]["Topic A"] == 1.0
        
        # Ensure session was updated
        assert mock_sessions.return_value.update_one.called
        assert mock_learners.return_value.update_one.called

    def test_submit_partial_correct(self, client):
        with patch("routes.diagnostic.diagnostic_sessions_collection") as mock_sessions, \
             patch("routes.diagnostic.learners_collection") as mock_learners:
            
            mock_sessions.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_SESSION_ID),
                "learner_id": MOCK_LEARNER_ID,
                "questions": MOCK_QUESTIONS,
                "completed_at": None
            }
            
            resp = client.post(f"/api/diagnostic/{MOCK_SESSION_ID}/submit", json={
                "answers": [
                    {"question_id": "0", "selected_answer": 0}, # correct
                    {"question_id": "1", "selected_answer": 1}, # incorrect
                    {"question_id": "2", "selected_answer": 1}  # correct
                ]
            })
            
        assert resp.status_code == 200
        body = resp.json()
        
        # 2 out of 3 correct
        assert abs(body["overall_score"] - 0.666) < 0.01
        
        scores = {ts["topic"]: ts["score"] for ts in body["topic_scores"]}
        # Topic A: 1 out of 2 correct (0.5)
        assert abs(scores["Topic A"] - 0.5) < 0.01
        # Topic B: 1 out of 1 correct (1.0)
        assert abs(scores["Topic B"] - 1.0) < 0.01

    def test_submit_invalid_answer_option(self, client):
        with patch("routes.diagnostic.diagnostic_sessions_collection") as mock_sessions:
            mock_sessions.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_SESSION_ID),
                "learner_id": MOCK_LEARNER_ID,
                "questions": MOCK_QUESTIONS,
                "completed_at": None
            }
            
            resp = client.post(f"/api/diagnostic/{MOCK_SESSION_ID}/submit", json={
                "answers": [
                    {"question_id": "0", "selected_answer": 5}, # Invalid, options are 0-3
                ]
            })
        assert resp.status_code == 422 # Pydantic validation error

    def test_submit_already_completed(self, client):
        with patch("routes.diagnostic.diagnostic_sessions_collection") as mock_sessions:
            mock_sessions.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_SESSION_ID),
                "learner_id": MOCK_LEARNER_ID,
                "questions": MOCK_QUESTIONS,
                "completed_at": "2024-01-01T00:00:00Z" # Already done
            }
            
            resp = client.post(f"/api/diagnostic/{MOCK_SESSION_ID}/submit", json={
                "answers": []
            })
        assert resp.status_code == 400
        assert "already completed" in resp.json()["detail"]


class TestDiagnosticGetEndpoint:
    """Tests for GET /api/diagnostic/{session_id}"""
    
    def test_get_session_success(self, client):
        with patch("routes.diagnostic.diagnostic_sessions_collection") as mock_sessions:
            mock_sessions.return_value.find_one.return_value = {
                "_id": ObjectId(MOCK_SESSION_ID),
                "learner_id": MOCK_LEARNER_ID,
                "overall_score": 0.8
            }
            
            resp = client.get(f"/api/diagnostic/{MOCK_SESSION_ID}")
            
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == MOCK_SESSION_ID
        assert body["overall_score"] == 0.8
