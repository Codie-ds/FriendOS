# FriendOS Backend

Adaptive AI Learning Companion – FastAPI backend (Phase 1).

## Quick Start

### 1. Create virtual environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in the `backend/` directory with:

```
GEMMA_API_KEY=your-api-key
GEMMA_MODEL=gemma-4-31b-it
MONGODB_URI=mongodb+srv://...
```

All three variables are **required**. The app will fail on startup if any are missing.

### 4. Start the server

```bash
uvicorn main:app --reload
```

Server runs at `http://127.0.0.1:8000`.

Interactive API docs at `http://127.0.0.1:8000/docs`.

---

## API Endpoints

### `GET /health`

Health check.

**Response:**
```json
{
  "status": "ok",
  "service": "FriendOS"
}
```

### `POST /api/onboard`

Create a new learner profile.

**Request:**
```json
{
  "name": "Dev",
  "learning_goal": "Learn DSA",
  "known_topics": ["arrays", "strings"],
  "weak_topics": ["recursion", "trees"]
}
```

**Response:**
```json
{
  "success": true,
  "learner_id": "...",
  "message": "Learner onboarded successfully"
}
```

### `POST /api/ai/test`

Test the Gemma AI integration (development only).

**Request:**
```json
{
  "prompt": "Say hello to FriendOS"
}
```

**Response:**
```json
{
  "success": true,
  "response": "Hello, FriendOS! ..."
}
```

---

## Running Tests

Tests are fully mocked – no API keys or live database required.

```bash
python -m pytest tests/ -v
```

---

## Project Structure

```
backend/
├── .env                  # Environment variables (not in git)
├── requirements.txt      # Python dependencies
├── main.py               # FastAPI entry-point
├── config.py             # Environment config loader
├── database.py           # MongoDB connection helper
├── test_gemma.py         # Standalone Gemma API test
├── services/
│   ├── __init__.py
│   └── ai_service.py     # Gemma AI service abstraction
├── models/
│   ├── __init__.py
│   └── learner.py        # Pydantic learner models
├── routes/
│   ├── __init__.py
│   ├── health.py         # GET /health
│   ├── onboarding.py     # POST /api/onboard
│   └── ai_test.py        # POST /api/ai/test
└── tests/
    ├── __init__.py
    └── test_phase1.py    # Phase 1 endpoint tests
```
