import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMMA_API_KEY")
model = os.getenv("GEMMA_MODEL")

if not api_key:
    raise ValueError("GEMMA_API_KEY is missing from .env")

if not model:
    raise ValueError("GEMMA_MODEL is missing from .env")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model=model,
    contents="Say hello and explain what FriendOS is in one sentence."
)

print("\n==============================")
print("✅ GEMMA API RESPONSE")
print("==============================")
print(response.text)
print("==============================\n")