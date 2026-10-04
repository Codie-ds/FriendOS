"""
FriendOS – Adaptive AI Learning Companion
==========================================
FastAPI application entry-point.

Start with:
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS
from database import get_client
from routes.health import router as health_router
from routes.onboarding import router as onboarding_router
from routes.ai_test import router as ai_test_router
from routes.material import router as material_router
from routes.diagnostic import router as diagnostic_router
from routes.learning import router as learning_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify MongoDB connectivity on startup; clean up on shutdown."""
    client = get_client()
    # Quick connectivity check (will raise if unreachable)
    client.admin.command("ping")
    print("✅ Connected to MongoDB")
    yield
    client.close()
    print("🛑 MongoDB connection closed")


app = FastAPI(
    title="FriendOS",
    description="Adaptive AI Learning Companion – backend API",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(onboarding_router)
app.include_router(ai_test_router)
app.include_router(material_router)
app.include_router(diagnostic_router)
app.include_router(learning_router)
