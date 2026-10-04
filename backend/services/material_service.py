"""
FriendOS Material Analysis Service.

Takes extracted PDF text, sends it to Gemma with a structured prompt,
validates the JSON response with Pydantic, and retries once on failure.
"""

import json
import re
from typing import Optional

from pydantic import ValidationError

from models.material import GemmaAnalysisOutput
from services.ai_service import AIService


_ANALYSIS_PROMPT = """\
You are FriendOS, an adaptive learning companion.

Analyze the following learning material carefully.

Your task:
1. Give the material a short, descriptive title.
2. Identify the major learning topics covered (at least 1).
3. For each topic, provide a name, a brief description, and a difficulty level (beginner, intermediate, or advanced).
4. Generate 5 to 10 diagnostic multiple-choice questions that measure a learner's current understanding of the material.

Rules for questions:
- Each question MUST have exactly 4 options.
- correct_answer MUST be an integer from 0 to 3 (index of the correct option).
- Questions must be answerable from the supplied material.
- Do NOT invent information that is not in the material.
- Cover different topics and difficulty levels when possible.

Return ONLY valid JSON matching this exact schema (no markdown, no explanation, no extra text):

{
  "title": "...",
  "topics": [
    {"name": "...", "description": "...", "difficulty": "beginner|intermediate|advanced"}
  ],
  "diagnostic_questions": [
    {
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "correct_answer": 0,
      "topic": "...",
      "difficulty": "beginner|intermediate|advanced"
    }
  ]
}

MATERIAL:
"""

_REPAIR_PROMPT = """\
The previous JSON you returned was invalid. Here is the error:

{error}

Here is the invalid JSON you returned:

{bad_json}

Please fix it and return ONLY valid JSON matching the original schema.
No markdown fences, no explanation — just the JSON object.
"""


class MaterialAnalysisError(Exception):
    """Raised when Gemma output cannot be parsed/validated after retries."""
    pass


def _extract_json_from_text(text: str) -> str:
    """
    Try to pull a JSON object out of the model's response.
    Handles cases where Gemma wraps JSON in markdown fences.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # Find the first { ... } block
    start = cleaned.find("{")
    if start == -1:
        return cleaned  # let json.loads fail with a clear error
    # Find matching closing brace
    depth = 0
    for i, ch in enumerate(cleaned[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : i + 1]
    return cleaned[start:]  # return what we have


def analyze_material(
    extracted_text: str,
    ai_service: Optional[AIService] = None,
    max_text_chars: int = 15_000,
) -> GemmaAnalysisOutput:
    """
    Send extracted PDF text to Gemma and return validated structured output.

    Parameters
    ----------
    extracted_text : str
        The text extracted from the PDF.
    ai_service : AIService, optional
        An AIService instance (defaults to a new one).
    max_text_chars : int
        Truncate input text to this many characters to stay within
        model context limits.

    Returns
    -------
    GemmaAnalysisOutput
        Pydantic-validated structured analysis.

    Raises
    ------
    MaterialAnalysisError
        If the model output cannot be parsed after one retry.
    """
    if ai_service is None:
        ai_service = AIService()

    # Truncate very long text to fit model context
    trimmed = extracted_text[:max_text_chars]
    prompt = _ANALYSIS_PROMPT + trimmed

    # ── First attempt ─────────────────────────────────────────────────
    raw_response = ai_service.generate_response(prompt)
    result, error = _try_parse(raw_response)
    if result is not None:
        return result

    # ── Retry with repair prompt ──────────────────────────────────────
    repair = _REPAIR_PROMPT.format(error=error, bad_json=raw_response[:3000])
    raw_retry = ai_service.generate_response(repair)
    result, error2 = _try_parse(raw_retry)
    if result is not None:
        return result

    raise MaterialAnalysisError(
        f"Gemma returned invalid output after retry. Last error: {error2}"
    )


def _try_parse(raw: str) -> tuple[Optional[GemmaAnalysisOutput], Optional[str]]:
    """
    Attempt to parse and validate raw model output.

    Returns (result, None) on success or (None, error_message) on failure.
    """
    try:
        json_str = _extract_json_from_text(raw)
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as exc:
        return None, f"JSON parse error: {exc}"

    try:
        validated = GemmaAnalysisOutput.model_validate(data)
        return validated, None
    except ValidationError as exc:
        return None, f"Pydantic validation error: {exc}"
