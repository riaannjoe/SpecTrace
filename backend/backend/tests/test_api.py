from app.analysis.contract import EngineRequest  # noqa: F401  (documents the contract under test)
from app.services import analysis_service
from tests.conftest import make_zip


# ---------- health ----------
def test_health_check(client):
    body = client.get("/").json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


# ---------- upload ----------
def test_upload_valid_zip(client):
    z = make_zip({"auth.py": "def login(): pass", "pkg/models.py": "class User: pass", "logo.png": "x"})
    r = client.post("/projects/upload", files={"file": ("shop.zip", z, "application/zip")})
    assert r.status_code == 201
    body = r.json()
    assert body["id"].startswith("project_")
    assert body["project_name"] == "shop"
    assert body["python_file_count"] == 2
    assert "storage_path" not in body  # server paths are never exposed


def test_reject_non_zip_extension(client):
    r = client.post("/projects/upload", files={"file": ("code.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    assert "error" in r.json()


def test_reject_corrupted_zip(client):
    r = client.post("/projects/upload", files={"file": ("fake.zip", b"this is not a zip", "application/zip")})
    assert r.status_code == 400


def test_reject_path_traversal(client):
    z = make_zip({"../evil.py": "print('pwned')"})
    r = client.post("/projects/upload", files={"file": ("evil.zip", z, "application/zip")})
    assert r.status_code == 400
    assert "Unsafe path" in r.json()["error"]["message"]


def test_reject_zip_without_python(client):
    z = make_zip({"README.md": "no code here"})
    r = client.post("/projects/upload", files={"file": ("docs.zip", z, "application/zip")})
    assert r.status_code == 400


def test_reject_oversized_upload(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 10)
    z = make_zip({"a.py": "x = 1"})
    r = client.post("/projects/upload", files={"file": ("big.zip", z, "application/zip")})
    assert r.status_code == 413


def test_projects_list_and_detail(client, project_id):
    assert client.get("/projects").json()["count"] == 1
    assert client.get(f"/projects/{project_id}").json()["id"] == project_id
    r = client.get("/projects/project_doesnotexist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


# ---------- requirements ----------
def test_add_and_get_requirements(client, project_id):
    r = client.post(f"/projects/{project_id}/requirements",
                    json={"requirements": ["Users must be able to register", "  Users must be able to log in  "]})
    assert r.status_code == 201
    assert r.json()["count"] == 2
    got = client.get(f"/projects/{project_id}/requirements").json()
    assert [x["description"] for x in got["requirements"]][1] == "Users must be able to log in"  # trimmed
    assert got["requirements"][0]["status"] == "pending"


def test_reject_empty_requirements(client, project_id):
    assert client.post(f"/projects/{project_id}/requirements", json={"requirements": ["ok", "   "]}).status_code == 422
    assert client.post(f"/projects/{project_id}/requirements", json={"requirements": []}).status_code == 422


def test_requirements_for_unknown_project(client):
    r = client.post("/projects/project_nope/requirements", json={"requirements": ["x"]})
    assert r.status_code == 404


# ---------- analysis + results ----------
def test_analyze_requires_requirements(client, project_id):
    assert client.post(f"/projects/{project_id}/analyze").status_code == 400


def test_results_empty_before_analysis(client, project_id):
    body = client.get(f"/projects/{project_id}/results").json()
    assert body["summary"]["total"] == 0 and body["results"] == []


def test_analyze_with_mock_is_labelled_and_not_verified(client, project_id):
    client.post(f"/projects/{project_id}/requirements", json={"requirements": ["Users must log in", "Passwords validated"]})
    r = client.post(f"/projects/{project_id}/analyze")
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is True
    assert body["summary"] == {"total": 2, "implemented": 0, "partially_implemented": 0, "missing": 0, "not_verified": 2}
    assert all(x["status"] == "not_verified" and "MOCK" in x["explanation"] for x in body["results"])
    assert client.get(f"/projects/{project_id}").json()["status"] == "analyzed"
    # stored results can be fetched again
    again = client.get(f"/projects/{project_id}/results").json()
    assert again["summary"]["total"] == 2


def test_analyze_with_fake_real_engine(client, project_id, monkeypatch):
    """Simulates the teammate's engine to prove the contract + storage + retrieval work."""
    reqs = client.post(f"/projects/{project_id}/requirements",
                       json={"requirements": ["Users must log in", "Users can reset password"]}).json()["requirements"]

    def fake_engine(request):
        return {
            "engine_name": "Fake test engine", "is_mock": False,
            "results": [{
                "requirement_id": reqs[0]["id"], "status": "implemented", "test_status": "passed",
                "evidence": [{"file": "auth.py", "line": 1, "description": "login() found"}],
                "explanation": "login found",
            }],  # deliberately omits requirement 2
        }

    monkeypatch.setattr(analysis_service, "run_engine", fake_engine)
    body = client.post(f"/projects/{project_id}/analyze").json()
    assert body["is_mock"] is False
    first, second = body["results"]
    assert first["status"] == "implemented" and first["file_name"] == "auth.py" and first["line_number"] == 1
    assert second["status"] == "not_verified"  # skipped by engine -> honest fallback
    assert body["summary"]["implemented"] == 1 and body["summary"]["not_verified"] == 1


def test_invalid_engine_output_is_rejected(client, project_id, monkeypatch):
    client.post(f"/projects/{project_id}/requirements", json={"requirements": ["Users must log in"]})
    monkeypatch.setattr(analysis_service, "run_engine", lambda req: {"results": "garbage"})
    r = client.post(f"/projects/{project_id}/analyze")
    assert r.status_code == 502
    assert client.get(f"/projects/{project_id}").json()["status"] == "analysis_failed"


def test_engine_result_for_unknown_requirement_rejected(client, project_id, monkeypatch):
    client.post(f"/projects/{project_id}/requirements", json={"requirements": ["Users must log in"]})
    bad = {"engine_name": "x", "results": [{"requirement_id": "requirement_fake", "status": "implemented"}]}
    monkeypatch.setattr(analysis_service, "run_engine", lambda req: bad)
    assert client.post(f"/projects/{project_id}/analyze").status_code == 502
