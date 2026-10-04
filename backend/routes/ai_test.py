"""
AI test route – development-only endpoint for testing the Gemma integration.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.ai_service import AIService

router = APIRouter(prefix="/api/ai")

_ai = AIService()


class AITestRequest(BaseModel):
    prompt: str


class AITestResponse(BaseModel):
    success: bool
    response: str


@router.post("/test", response_model=AITestResponse)
def ai_test(data: AITestRequest):
    """Send a prompt to Gemma and return the response. Dev/testing only."""
    try:
        text = _ai.generate_response(data.prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}")

    return AITestResponse(success=True, response=text)
