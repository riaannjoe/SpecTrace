"""ID + time helpers. IDs are plain strings like 'project_3f9a1c2b7d10' - easy for React."""
import uuid
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
