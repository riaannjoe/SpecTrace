"""Runs against your REAL Atlas database. Skipped automatically if MONGODB_URI is not set."""
import pytest

from app.config import settings
from app.database import connection

pytestmark = pytest.mark.skipif(
    not settings.MONGODB_URI or "<password>" in settings.MONGODB_URI,
    reason="MONGODB_URI not configured in .env",
)


def test_atlas_connectivity_and_indexes():
    connection.set_db(None)  # make sure we use the real connection
    assert connection.check_connection() is True
    connection.create_indexes()
    assert connection.get_db().name == settings.MONGODB_DB_NAME
