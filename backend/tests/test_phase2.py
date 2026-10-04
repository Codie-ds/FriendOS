"""
Tests for FriendOS Phase 2 – PDF ingestion and material analysis.

All tests mock MongoDB and Gemma. No real API keys or database needed.
"""

import io
import json
from unittest.mock import patch, MagicMock

import pytest
import fitz  # PyMuPDF – used to create test PDFs in memory
from fastapi.testclient import TestClient


# ── Sample Gemma output (valid) ──────────────────────────────────────

VALID_GEMMA_JSON = json.dumps({
    "title": "Introduction to Data Structures",
    "topics": [
        {
            "name": "Arrays",
            "description": "Contiguous memory storage of elements",
            "difficulty": "beginner",
        },
        {
            "name": "Linked Lists",
            "description": "Node-based dynamic data structure",
            "difficulty": "intermediate",
        },
    ],
    "diagnostic_questions": [
        {
            "question": "What is the time complexity of accessing an element in an array by index?",
            "options": ["O(1)", "O(n)", "O(log n)", "O(n^2)"],
            "correct_answer": 0,
            "topic": "Arrays",
            "difficulty": "beginner",
        },
        {
            "question": "Which data structure uses nodes with pointers?",
            "options": ["Array", "Linked List", "Integer", "Boolean"],
            "correct_answer": 1,
            "topic": "Linked Lists",
            "difficulty": "beginner",
        },
        {
            "question": "What is the worst-case insertion time at the beginning of an array?",
            "options": ["O(1)", "O(log n)", "O(n)", "O(n^2)"],
            "correct_answer": 2,
            "topic": "Arrays",
            "difficulty": "intermediate",
        },
        {
            "question": "In a singly linked list, each node contains?",
            "options": [
                "Data only",
                "Data and one pointer",
                "Data and two pointers",
                "Pointers only",
            ],
            "correct_answer": 1,
            "topic": "Linked Lists",
            "difficulty": "beginner",
        },
        {
            "question": "What advantage does a linked list have over an array?",
            "options": [
                "Faster random access",
                "Dynamic size",
                "Less memory usage",
                "Simpler implementation",
            ],
            "correct_answer": 1,
            "topic": "Linked Lists",
            "difficulty": "intermediate",
        },
    ],
})


# ── Helpers ───────────────────────────────────────────────────────────

def _make_pdf(text: str = "Hello World") -> bytes:
    """Create a minimal in-memory PDF with the given text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_empty_pdf() -> bytes:
    """Create a PDF with a blank page (no text)."""
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


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


# ══════════════════════════════════════════════════════════════════════
# PDF SERVICE TESTS
# ══════════════════════════════════════════════════════════════════════

class TestPDFExtraction:
    """Unit tests for services.pdf_service.extract_text_from_pdf."""

    def test_valid_pdf_extraction(self):
        from services.pdf_service import extract_text_from_pdf

        pdf_bytes = _make_pdf("Arrays are a fundamental data structure.")
        result = extract_text_from_pdf(
            file=io.BytesIO(pdf_bytes),
            filename="dsa_notes.pdf",
        )
        assert result.page_count == 1
        assert "Arrays" in result.text
        assert len(result.pages) == 1
        assert result.pages[0]["page"] == 1

    def test_empty_pdf_no_text(self):
        from services.pdf_service import extract_text_from_pdf, PDFExtractionError

        pdf_bytes = _make_empty_pdf()
        with pytest.raises(PDFExtractionError, match="No extractable text"):
            extract_text_from_pdf(
                file=io.BytesIO(pdf_bytes),
                filename="blank.pdf",
            )

    def test_invalid_file_type(self):
        from services.pdf_service import extract_text_from_pdf, PDFExtractionError

        with pytest.raises(PDFExtractionError, match="Unsupported file type"):
            extract_text_from_pdf(
                file=io.BytesIO(b"not a pdf"),
                filename="notes.docx",
            )

    def test_oversized_pdf_rejected(self):
        from services.pdf_service import extract_text_from_pdf, PDFExtractionError

        pdf_bytes = _make_pdf("x")
        with pytest.raises(PDFExtractionError, match="too large"):
            extract_text_from_pdf(
                file=io.BytesIO(pdf_bytes),
                filename="huge.pdf",
                max_size=10,  # 10 bytes – any real PDF exceeds this
            )

    def test_empty_file(self):
        from services.pdf_service import extract_text_from_pdf, PDFExtractionError

        with pytest.raises(PDFExtractionError, match="empty"):
            extract_text_from_pdf(
                file=io.BytesIO(b""),
                filename="nothing.pdf",
            )


# ══════════════════════════════════════════════════════════════════════
# MATERIAL ANALYSIS TESTS
# ══════════════════════════════════════════════════════════════════════

class TestMaterialAnalysis:
    """Unit tests for services.material_service.analyze_material."""

    def test_valid_gemma_output(self):
        from services.material_service import analyze_material

        mock_ai = MagicMock()
        mock_ai.generate_response.return_value = VALID_GEMMA_JSON

        result = analyze_material("Some learning text", ai_service=mock_ai)
        assert result.title == "Introduction to Data Structures"
        assert len(result.topics) == 2
        assert 5 <= len(result.diagnostic_questions) <= 10

    def test_valid_gemma_output_with_markdown_fences(self):
        from services.material_service import analyze_material

        mock_ai = MagicMock()
        mock_ai.generate_response.return_value = f"```json\n{VALID_GEMMA_JSON}\n```"

        result = analyze_material("Some text", ai_service=mock_ai)
        assert result.title == "Introduction to Data Structures"

    def test_invalid_gemma_output_triggers_retry(self):
        from services.material_service import analyze_material

        mock_ai = MagicMock()
        # First call returns garbage, second call returns valid JSON
        mock_ai.generate_response.side_effect = [
            "This is not JSON at all!",
            VALID_GEMMA_JSON,
        ]

        result = analyze_material("Some text", ai_service=mock_ai)
        assert result.title == "Introduction to Data Structures"
        assert mock_ai.generate_response.call_count == 2

    def test_invalid_gemma_output_both_attempts_fail(self):
        from services.material_service import analyze_material, MaterialAnalysisError

        mock_ai = MagicMock()
        mock_ai.generate_response.return_value = "totally broken"

        with pytest.raises(MaterialAnalysisError, match="invalid output after retry"):
            analyze_material("Some text", ai_service=mock_ai)


# ══════════════════════════════════════════════════════════════════════
# ENDPOINT TESTS
# ══════════════════════════════════════════════════════════════════════

class TestMaterialUploadEndpoint:
    """Integration tests for POST /api/material/upload."""

    def test_upload_success(self, client):
        pdf_bytes = _make_pdf("Arrays and linked lists are data structures.")

        with patch("routes.material.analyze_material") as mock_analyze, \
             patch("routes.material.materials_collection") as mock_coll:

            # Mock Gemma analysis
            from models.material import GemmaAnalysisOutput
            mock_analyze.return_value = GemmaAnalysisOutput.model_validate(
                json.loads(VALID_GEMMA_JSON)
            )

            # Mock MongoDB insert
            mock_result = MagicMock()
            mock_result.inserted_id = "mat_abc123"
            mock_coll.return_value.insert_one.return_value = mock_result

            resp = client.post(
                "/api/material/upload",
                files={"file": ("dsa.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["material_id"] == "mat_abc123"
        assert body["title"] == "Introduction to Data Structures"
        assert len(body["topics"]) == 2
        assert len(body["diagnostic_questions"]) == 5

    def test_upload_invalid_file_type(self, client):
        resp = client.post(
            "/api/material/upload",
            files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    def test_upload_empty_pdf(self, client):
        pdf_bytes = _make_empty_pdf()
        resp = client.post(
            "/api/material/upload",
            files={"file": ("blank.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "No extractable text" in resp.json()["detail"]


class TestMaterialGetEndpoint:
    """Tests for GET /api/material/{material_id}."""

    def test_get_material_not_found(self, client):
        with patch("routes.material.materials_collection") as mock_coll:
            mock_coll.return_value.find_one.return_value = None

            resp = client.get("/api/material/000000000000000000000000")

        assert resp.status_code == 404

    def test_get_material_bad_id(self, client):
        resp = client.get("/api/material/not-a-valid-id")
        assert resp.status_code == 400
