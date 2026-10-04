"""
FriendOS AI Service – thin wrapper around the Google GenAI SDK.

Keeps the LLM provider isolated so it can be swapped later without
touching the rest of the application.
"""

from typing import Optional

from google import genai

from config import GEMMA_API_KEY, GEMMA_MODEL

_client = genai.Client(api_key=GEMMA_API_KEY)


class AIService:
    """Stateless helper that sends prompts to the configured Gemma model."""

    def __init__(self, model: str = GEMMA_MODEL):
        self.model = model

    def generate_response(self, prompt: str, context: Optional[str] = None) -> str:
        """
        Generate a text response from the model.

        Parameters
        ----------
        prompt : str
            The user-facing prompt.
        context : str, optional
            Additional system/background context prepended to the prompt.

        Returns
        -------
        str
            The model's text output.
        """
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        response = _client.models.generate_content(
            model=self.model,
            contents=full_prompt,
        )
        return response.text
