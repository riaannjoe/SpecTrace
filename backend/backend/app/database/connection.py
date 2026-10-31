"""MongoDB Atlas connection. The client is created lazily on first use and then reused."""
import logging

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

from app.config import settings
from app.utils.errors import AppError

logger = logging.getLogger("spectrace.db")

_client = None
_db = None


def set_db(db) -> None:
    """Inject a database object (used by tests to plug in an in-memory fake). Pass None to reset."""
    global _db
    _db = db


def get_db():
    """Return the 'spectrace' database, connecting on first call."""
    global _client, _db
    if _db is not None:
        return _db
    if not settings.MONGODB_URI:
        raise AppError(503, "MONGODB_URI is not set. Copy .env.example to .env and add your Atlas URI.")
    try:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000, tz_aware=True)
        _client.admin.command("ping")  # forces a real connection attempt now
    except PyMongoError as exc:
        _client = None
        logger.error("MongoDB connection failed: %s", exc)
        raise AppError(
            503,
            "Cannot connect to MongoDB Atlas. Check your URI, password and Atlas Network Access (IP allow-list).",
        ) from exc
    _db = _client[settings.MONGODB_DB_NAME]
    return _db


def check_connection() -> bool:
    """True if the database answers a simple request."""
    try:
        get_db().list_collection_names()
        return True
    except Exception:
        return False


def create_indexes() -> None:
    """Idempotent - safe to run on every startup."""
    db = get_db()
    db.projects.create_index([("created_at", DESCENDING)])
    db.requirements.create_index([("project_id", ASCENDING), ("created_at", ASCENDING)])
    db.analysis_results.create_index([("project_id", ASCENDING), ("order", ASCENDING)])
    db.analysis_results.create_index([("project_id", ASCENDING), ("requirement_id", ASCENDING)])
