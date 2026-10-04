"""
Tests for FriendOS Phase 1 endpoints.

All tests mock the MongoDB and AI service so they run without
real credentials or a live database.
"""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    """Ensure config loads without real secrets during tests."""
    monkeypatch.setenv("GEMMA_API_KEY", "test-key")
    monkeypatch.setenv("GEMMA_MODEL", "test-model")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")


@pytest.fixture()
def client():
    """
    Return a TestClient with MongoDB ping mocked so the lifespan
    succeeds without a real database.
    """
    with patch("database.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance
        # Make the admin ping succeed
        mock_instance.admin.command.return_value = {"ok": 1}

        # Force module reimport so config & database pick up test env vars
        import importlib
        import config
        importlib.reload(config)
        import database
        importlib.reload(database)
        import services.ai_service
        importlib.reload(services.ai_service)
        import routes.health
        importlib.reload(routes.health)
        import routes.onboarding
        importlib.reload(routes.onboarding)
        import routes.ai_test
        importlib.reload(routes.ai_test)
        import routes.material
        importlib.reload(routes.material)
        import main
        importlib.reload(main)

        with TestClient(main.app) as tc:
            yield tc


# ── Health ────────────────────────────────────────────────────────────

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "FriendOS"


# ── Onboarding ───────────────────────────────────────────────────────

def test_onboard_success(client):
    with patch("routes.onboarding.learners_collection") as mock_coll:
        mock_result = MagicMock()
        mock_result.inserted_id = "abc123"
        mock_coll.return_value.insert_one.return_value = mock_result

        resp = client.post("/api/onboard", json={
            "name": "Dev",
            "learning_goal": "Learn DSA",
            "known_topics": ["arrays", "strings"],
            "weak_topics": ["recursion", "trees"],
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["learner_id"] == "abc123"
    assert "onboarded" in body["message"].lower()


def test_onboard_validation_error(client):
    """Missing required fields should return 422."""
    resp = client.post("/api/onboard", json={})
    assert resp.status_code == 422


# ── AI Test ──────────────────────────────────────────────────────────

def test_ai_test_endpoint(client):
    with patch("routes.ai_test._ai") as mock_ai:
        mock_ai.generate_response.return_value = "Hello from FriendOS!"

        resp = client.post("/api/ai/test", json={
            "prompt": "Say hello",
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["response"] == "Hello from FriendOS!"


def test_ai_test_missing_prompt(client):
    """Missing prompt should return 422."""
    resp = client.post("/api/ai/test", json={})
    assert resp.status_code == 422
