import io
import zipfile

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import connection
from app.main import app


def make_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """API client backed by an in-memory fake MongoDB and a temp upload folder (no Atlas needed)."""
    connection.set_db(mongomock.MongoClient()["spectrace_test"])
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "ANALYSIS_ENGINE", "mock")
    (tmp_path / "uploads").mkdir()
    yield TestClient(app)   # no "with": skips the startup hook that would contact Atlas
    connection.set_db(None)


@pytest.fixture()
def project_id(client):
    """An uploaded project, ready for requirements."""
    zip_bytes = make_zip({"auth.py": "def login(u, p):\n    return True\n", "README.md": "demo"})
    r = client.post("/projects/upload", files={"file": ("demo.zip", zip_bytes, "application/zip")},
                    data={"project_name": "Demo"})
    assert r.status_code == 201
    return r.json()["id"]
