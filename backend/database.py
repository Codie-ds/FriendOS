"""
FriendOS database connection helper.
Provides a thin wrapper around PyMongo for the 'friendos' database.
"""

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

from config import MONGODB_URI

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return (and cache) the MongoClient singleton."""
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
    return _client


def get_database() -> Database:
    """Return the 'friendos' database handle."""
    return get_client()["friendos"]


def get_collection(name: str) -> Collection:
    """Shortcut to get a collection from the friendos database."""
    return get_database()[name]


# ── Collection accessors ──────────────────────────────────────────────

def learners_collection() -> Collection:
    return get_collection("learners")


def sessions_collection() -> Collection:
    return get_collection("learning_sessions")


def materials_collection() -> Collection:
    return get_collection("learning_materials")


def diagnostic_sessions_collection() -> Collection:
    return get_collection("diagnostic_sessions")
