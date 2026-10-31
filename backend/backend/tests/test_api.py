from app.analysis.contract import EngineRequest  # noqa: F401  (documents the contract under test)
from app.database.connection import get_db
from app.services import analysis_service
from app.utils.ids import new_id, utcnow
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
    assert body["analysis_mode"] == "mock"
    assert body["summary"] == {
        "total": 2,
        "implemented": 0,
        "partially_implemented": 0,
        "missing": 0,
        "not_verified": 2,
        "critical_risks": 0,
        "high_risks": 0,
        "medium_risks": 0,
        "low_risks": 0,
        "tests_covered": 0,
    }
    assert all(x["status"] == "not_verified" and "MOCK" in x["explanation"] for x in body["results"])
    assert all(x["analysis_mode"] == "mock" for x in body["results"])
    assert all(x["test_covered"] is False for x in body["results"])
    assert all(x["test_evidence"] == [] for x in body["results"])
    assert client.get(f"/projects/{project_id}").json()["status"] == "analyzed"
    # stored results can be fetched again
    again = client.get(f"/projects/{project_id}/results").json()
    assert again["summary"]["total"] == 2
    assert again["analysis_mode"] == "mock"


def test_analyze_with_fake_real_engine(client, project_id, monkeypatch):
    """Simulates the teammate's engine to prove the contract + storage + retrieval work."""
    reqs = client.post(f"/projects/{project_id}/requirements",
                       json={"requirements": ["Users must log in", "Users can reset password"]}).json()["requirements"]

    def fake_engine(request):
        return {
            "engine_name": "Fake test engine",
            "analysis_mode": "hybrid",
            "is_mock": False,
            "results": [{
                "requirement_id": reqs[0]["id"],
                "status": "implemented",
                "confidence": 0.95,
                "risk": "low",
                "risk_reason": "Verified with test suite",
                "test_status": "not_run",
                "test_covered": True,
                "evidence": [{
                    "file": "auth.py",
                    "line": 1,
                    "line_end": 10,
                    "function": "login",
                    "snippet": "def login(): pass",
                    "description": "login() found",
                }],
                "test_evidence": [{
                    "file": "tests/test_auth.py",
                    "line": 5,
                    "line_end": 8,
                    "function": "test_login",
                    "snippet": "def test_login(): assert True",
                    "description": "test_login verifies login",
                }],
                "explanation": "login found and verified",
            }],  # deliberately omits requirement 2
        }

    monkeypatch.setattr(analysis_service, "run_engine", fake_engine)
    body = client.post(f"/projects/{project_id}/analyze").json()
    assert body["is_mock"] is False
    assert body["analysis_mode"] == "hybrid"
    first, second = body["results"]
    assert first["status"] == "implemented" and first["file_name"] == "auth.py" and first["line_number"] == 1
    assert first["confidence"] == 0.95
    assert first["risk"] == "low"
    assert first["risk_reason"] == "Verified with test suite"
    assert first["test_covered"] is True
    assert first["evidence"][0]["line_end"] == 10
    assert first["evidence"][0]["function"] == "login"
    assert first["evidence"][0]["snippet"] == "def login(): pass"
    assert first["test_evidence"][0]["file"] == "tests/test_auth.py"

    assert second["status"] == "not_verified"  # skipped by engine -> honest fallback
    assert second["confidence"] is None
    assert second["risk"] is None
    assert second["test_covered"] is False

    assert body["summary"]["implemented"] == 1
    assert body["summary"]["not_verified"] == 1
    assert body["summary"]["low_risks"] == 1
    assert body["summary"]["tests_covered"] == 1


def test_summary_counts_all_four_risk_levels_and_test_covered(client, project_id, monkeypatch):
    """Verifies that all 4 risk levels (critical, high, medium, low) and tests_covered are accurately counted."""
    req_texts = ["Req Critical", "Req High", "Req Medium", "Req Low", "Req None"]
    reqs = client.post(f"/projects/{project_id}/requirements", json={"requirements": req_texts}).json()["requirements"]

    def risk_engine(request):
        return {
            "engine_name": "Risk Engine",
            "analysis_mode": "hybrid",
            "is_mock": False,
            "results": [
                {
                    "requirement_id": reqs[0]["id"],
                    "status": "missing",
                    "risk": "critical",
                    "risk_reason": "Security vulnerability",
                    "test_covered": False,
                },
                {
                    "requirement_id": reqs[1]["id"],
                    "status": "partially_implemented",
                    "risk": "high",
                    "risk_reason": "Incomplete implementation",
                    "test_covered": True,
                },
                {
                    "requirement_id": reqs[2]["id"],
                    "status": "implemented",
                    "risk": "medium",
                    "risk_reason": "Missing tests",
                    "test_covered": False,
                },
                {
                    "requirement_id": reqs[3]["id"],
                    "status": "implemented",
                    "risk": "low",
                    "risk_reason": "Fully covered",
                    "test_covered": True,
                },
                {
                    "requirement_id": reqs[4]["id"],
                    "status": "not_verified",
                    "risk": None,
                    "test_covered": False,
                },
            ],
        }

    monkeypatch.setattr(analysis_service, "run_engine", risk_engine)
    body = client.post(f"/projects/{project_id}/analyze").json()
    assert body["summary"]["critical_risks"] == 1
    assert body["summary"]["high_risks"] == 1
    assert body["summary"]["medium_risks"] == 1
    assert body["summary"]["low_risks"] == 1
    assert body["summary"]["tests_covered"] == 2
    assert body["summary"]["total"] == 5


def test_older_mongodb_documents_without_enhanced_fields_readable(client, project_id):
    """Simulates pre-existing database records that lack new Phase 1 fields."""
    db = get_db()
    # Insert older style document
    old_doc = {
        "_id": new_id("result"),
        "project_id": project_id,
        "requirement_id": "requirement_legacy",
        "requirement_description": "Legacy requirement",
        "status": "implemented",
        "evidence": [{"file": "legacy.py", "line": 10, "description": "old format"}],
        "file_name": "legacy.py",
        "line_number": 10,
        "test_status": "not_run",
        "explanation": "Legacy result created before Phase 1",
        "engine": "Legacy Engine",
        "is_mock": False,
        "order": 0,
        "analyzed_at": utcnow(),
    }
    db.analysis_results.insert_one(old_doc)

    r = client.get(f"/projects/{project_id}/results")
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["total"] == 1
    assert data["summary"]["implemented"] == 1
    assert data["summary"]["critical_risks"] == 0
    assert data["summary"]["high_risks"] == 0
    assert data["summary"]["medium_risks"] == 0
    assert data["summary"]["low_risks"] == 0
    assert data["summary"]["tests_covered"] == 0

    item = data["results"][0]
    assert item["requirement_id"] == "requirement_legacy"
    assert item["confidence"] is None
    assert item["risk"] is None
    assert item["risk_reason"] is None
    assert item["test_covered"] is None
    assert item["test_evidence"] == []
    assert item["analysis_mode"] is None


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


# ===========================================================================
# Stage 4-G: Integration smoke tests — real AI engine via backend_adapter
# ===========================================================================
# These tests switch ANALYSIS_ENGINE to "real" and ANALYSIS_ENGINE_MODULE to
# "ai_engine.backend_adapter". Gemini is fully mocked so no network calls are
# made. The purpose is to verify that the full FastAPI → adapter → analyzer
# → EngineResponse → storage → results pipeline works end-to-end.
# ===========================================================================

import json
from unittest.mock import patch, MagicMock


def _make_gemini_response(req_ids, statuses=None):
    """Build a mocked Gemini result list for the given requirement IDs."""
    if statuses is None:
        statuses = {rid: "implemented" for rid in req_ids}
    results = []
    for rid in req_ids:
        results.append({
            "requirement_id": rid,
            "status": statuses.get(rid, "not_verified"),
            "confidence": 0.85,
            "explanation": f"Gemini result for {rid}",
            "evidence": [],
        })
    return results, set()


def _real_engine_client(client_fixture, tmp_path_fixture, monkeypatch_fixture, settings_fixture):
    """Configure client to use the real engine (ai_engine.backend_adapter)."""
    from app.config import settings as s
    monkeypatch_fixture.setattr(s, "ANALYSIS_ENGINE", "real")
    monkeypatch_fixture.setattr(s, "ANALYSIS_ENGINE_MODULE", "ai_engine.backend_adapter")
    monkeypatch_fixture.setattr(s, "GEMINI_API_KEY", None)   # no key -> static_fallback
    monkeypatch_fixture.setattr(s, "GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch_fixture.setattr(s, "GEMINI_TIMEOUT_SECONDS", 30)


def test_real_engine_static_fallback_no_api_key(client, project_id, monkeypatch):
    """
    With ANALYSIS_ENGINE=real and no API key, the engine must run in
    static_fallback mode and return not_verified for all requirements.
    """
    from app.config import settings as s
    monkeypatch.setattr(s, "ANALYSIS_ENGINE", "real")
    monkeypatch.setattr(s, "ANALYSIS_ENGINE_MODULE", "ai_engine.backend_adapter")
    monkeypatch.setattr(s, "GEMINI_API_KEY", None)
    monkeypatch.setattr(s, "GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setattr(s, "GEMINI_TIMEOUT_SECONDS", 30)

    client.post(f"/projects/{project_id}/requirements",
                json={"requirements": ["Users must be able to log in", "Passwords must be validated"]})
    r = client.post(f"/projects/{project_id}/analyze")
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is False
    assert body["analysis_mode"] == "static_fallback"
    assert body["summary"]["total"] == 2
    assert body["summary"]["not_verified"] == 2
    for result in body["results"]:
        assert result["test_status"] == "not_run"
        assert result["analysis_mode"] == "static_fallback"
        assert result["status"] == "not_verified"
        assert result["risk"] in ("low", "medium", "high", "critical")


def test_real_engine_hybrid_with_mocked_gemini(client, project_id, monkeypatch):
    """
    With ANALYSIS_ENGINE=real and a mocked Gemini that returns successful results,
    the pipeline must return hybrid mode and store results correctly.
    """
    from app.config import settings as s
    monkeypatch.setattr(s, "ANALYSIS_ENGINE", "real")
    monkeypatch.setattr(s, "ANALYSIS_ENGINE_MODULE", "ai_engine.backend_adapter")
    monkeypatch.setattr(s, "GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(s, "GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setattr(s, "GEMINI_TIMEOUT_SECONDS", 30)

    reqs_resp = client.post(f"/projects/{project_id}/requirements",
                            json={"requirements": ["Users must be able to log in",
                                                   "System must validate passwords"]})
    req_ids = [r["id"] for r in reqs_resp.json()["requirements"]]

    gemini_results = [
        {"requirement_id": req_ids[0], "status": "implemented", "confidence": 0.9,
         "explanation": "login() found in auth.py", "evidence": []},
        {"requirement_id": req_ids[1], "status": "partially_implemented", "confidence": 0.6,
         "explanation": "partial validation found", "evidence": []},
    ]

    with patch("ai_engine.analyzer.match_requirements_with_gemini",
               return_value=(gemini_results, set())):
        r = client.post(f"/projects/{project_id}/analyze")

    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is False
    assert body["analysis_mode"] == "hybrid"
    assert body["summary"]["total"] == 2
    assert body["summary"]["implemented"] == 1
    assert body["summary"]["partially_implemented"] == 1

    r0 = next(x for x in body["results"] if x["requirement_id"] == req_ids[0])
    r1 = next(x for x in body["results"] if x["requirement_id"] == req_ids[1])
    assert r0["status"] == "implemented"
    assert r0["analysis_mode"] == "hybrid"
    assert r0["test_status"] == "not_run"
    assert r1["status"] == "partially_implemented"
    assert r1["analysis_mode"] == "hybrid"


def test_real_engine_partial_gemini_failure_mixed_provenance(client, project_id, monkeypatch):
    """
    When Gemini succeeds for one requirement and fails for another,
    the run-level mode is hybrid, per-requirement modes differ.
    """
    from app.config import settings as s
    monkeypatch.setattr(s, "ANALYSIS_ENGINE", "real")
    monkeypatch.setattr(s, "ANALYSIS_ENGINE_MODULE", "ai_engine.backend_adapter")
    monkeypatch.setattr(s, "GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(s, "GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setattr(s, "GEMINI_TIMEOUT_SECONDS", 30)

    reqs_resp = client.post(f"/projects/{project_id}/requirements",
                            json={"requirements": ["Login requirement", "Upload requirement"]})
    req_ids = [r["id"] for r in reqs_resp.json()["requirements"]]

    # Only first requirement got a Gemini result; second goes to failed_ids
    partial_results = [
        {"requirement_id": req_ids[0], "status": "implemented", "confidence": 0.8,
         "explanation": "found", "evidence": []},
    ]
    failed_ids = {req_ids[1]}

    with patch("ai_engine.analyzer.match_requirements_with_gemini",
               return_value=(partial_results, failed_ids)):
        r = client.post(f"/projects/{project_id}/analyze")

    assert r.status_code == 200
    body = r.json()
    assert body["analysis_mode"] == "hybrid"

    r0 = next(x for x in body["results"] if x["requirement_id"] == req_ids[0])
    r1 = next(x for x in body["results"] if x["requirement_id"] == req_ids[1])
    assert r0["analysis_mode"] == "hybrid"
    assert r1["analysis_mode"] == "static_fallback"
    assert r1["status"] == "not_verified"
    assert r1["test_status"] == "not_run"


def test_real_engine_test_status_never_passed_or_failed(client, project_id, monkeypatch):
    """
    No matter what Gemini returns, test_status must always be "not_run".
    """
    from app.config import settings as s
    monkeypatch.setattr(s, "ANALYSIS_ENGINE", "real")
    monkeypatch.setattr(s, "ANALYSIS_ENGINE_MODULE", "ai_engine.backend_adapter")
    monkeypatch.setattr(s, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(s, "GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setattr(s, "GEMINI_TIMEOUT_SECONDS", 30)

    reqs_resp = client.post(f"/projects/{project_id}/requirements",
                            json={"requirements": ["Users must log in"]})
    req_ids = [r["id"] for r in reqs_resp.json()["requirements"]]

    gemini_results = [
        {"requirement_id": req_ids[0], "status": "implemented", "confidence": 0.9,
         "explanation": "found", "evidence": []},
    ]
    with patch("ai_engine.analyzer.match_requirements_with_gemini",
               return_value=(gemini_results, set())):
        r = client.post(f"/projects/{project_id}/analyze")

    for result in r.json()["results"]:
        assert result["test_status"] == "not_run"


def test_real_engine_results_fetchable_after_analysis(client, project_id, monkeypatch):
    """Results stored by the real engine must be retrievable via GET /results."""
    from app.config import settings as s
    monkeypatch.setattr(s, "ANALYSIS_ENGINE", "real")
    monkeypatch.setattr(s, "ANALYSIS_ENGINE_MODULE", "ai_engine.backend_adapter")
    monkeypatch.setattr(s, "GEMINI_API_KEY", None)
    monkeypatch.setattr(s, "GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.setattr(s, "GEMINI_TIMEOUT_SECONDS", 30)

    client.post(f"/projects/{project_id}/requirements",
                json={"requirements": ["Users must log in", "Users can upload files"]})
    client.post(f"/projects/{project_id}/analyze")

    r = client.get(f"/projects/{project_id}/results")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total"] == 2
    assert body["analysis_mode"] == "static_fallback"


# ===========================================================================
# Fix 3 — Issue 3-A regression tests: not_verified excluded from risk counts
# ===========================================================================

def test_not_verified_excluded_from_all_risk_counts(client, project_id, monkeypatch):
    """
    Regression Fix 3-A: not_verified results must NOT contribute to
    critical_risks, high_risks, medium_risks, or low_risks even when
    the engine assigns them a risk value.
    """
    reqs = client.post(
        f"/projects/{project_id}/requirements",
        json={"requirements": ["Req implemented", "Req not_verified", "Req missing"]},
    ).json()["requirements"]

    def engine(request):
        return {
            "engine_name": "Test",
            "analysis_mode": "hybrid",
            "is_mock": False,
            "results": [
                # implemented → low risk (counted)
                {"requirement_id": reqs[0]["id"], "status": "implemented",
                 "risk": "low", "test_covered": True},
                # not_verified → medium risk assigned by engine (must NOT be counted)
                {"requirement_id": reqs[1]["id"], "status": "not_verified",
                 "risk": "medium", "test_covered": False},
                # missing → high risk (counted)
                {"requirement_id": reqs[2]["id"], "status": "missing",
                 "risk": "high", "test_covered": False},
            ],
        }

    monkeypatch.setattr(analysis_service, "run_engine", engine)
    body = client.post(f"/projects/{project_id}/analyze").json()
    s = body["summary"]

    assert s["low_risks"] == 1,     f"expected 1 low, got {s['low_risks']}"
    assert s["high_risks"] == 1,    f"expected 1 high, got {s['high_risks']}"
    assert s["medium_risks"] == 0,  f"expected 0 medium (not_verified excluded), got {s['medium_risks']}"
    assert s["critical_risks"] == 0, f"expected 0 critical, got {s['critical_risks']}"
    # Status counts unaffected
    assert s["not_verified"] == 1
    assert s["total"] == 3


def test_all_not_verified_all_risk_counts_zero(client, project_id, monkeypatch):
    """When every result is not_verified, all four risk counts must be zero."""
    reqs = client.post(
        f"/projects/{project_id}/requirements",
        json={"requirements": ["Alpha", "Beta"]},
    ).json()["requirements"]

    def engine(request):
        return {
            "engine_name": "Test",
            "analysis_mode": "static_fallback",
            "is_mock": False,
            "results": [
                {"requirement_id": reqs[0]["id"], "status": "not_verified", "risk": "medium"},
                {"requirement_id": reqs[1]["id"], "status": "not_verified", "risk": "medium"},
            ],
        }

    monkeypatch.setattr(analysis_service, "run_engine", engine)
    body = client.post(f"/projects/{project_id}/analyze").json()
    s = body["summary"]

    assert s["critical_risks"] == 0
    assert s["high_risks"] == 0
    assert s["medium_risks"] == 0
    assert s["low_risks"] == 0
    assert s["not_verified"] == 2
    assert s["total"] == 2


def test_not_verified_with_critical_risk_excluded(client, project_id, monkeypatch):
    """
    A not_verified result assigned critical risk must not inflate critical_risks.
    """
    reqs = client.post(
        f"/projects/{project_id}/requirements",
        json={"requirements": ["Auth requirement"]},
    ).json()["requirements"]

    def engine(request):
        return {
            "engine_name": "Test",
            "analysis_mode": "hybrid",
            "is_mock": False,
            "results": [
                {"requirement_id": reqs[0]["id"], "status": "not_verified", "risk": "critical"},
            ],
        }

    monkeypatch.setattr(analysis_service, "run_engine", engine)
    body = client.post(f"/projects/{project_id}/analyze").json()
    s = body["summary"]
    assert s["critical_risks"] == 0
    assert s["not_verified"] == 1


def test_legacy_doc_with_null_risk_excluded_from_risk_counts(client, project_id):
    """
    Legacy documents with risk=None must not raise an error, and must
    contribute 0 to all named risk-level counts.  The None value simply lands
    in the Counter's None key, which is never added to any named count.
    A 'status' field IS required by ResultOut, so the document includes one.
    """
    from app.database.connection import get_db
    from app.utils.ids import new_id, utcnow

    db = get_db()
    db.analysis_results.insert_one({
        "_id": new_id("result"),
        "project_id": project_id,
        "requirement_id": "requirement_legacy3",
        "requirement_description": "Legacy requirement with null risk",
        "status": "implemented",   # required by ResultOut
        "evidence": [],
        "file_name": None,
        "line_number": None,
        "test_status": "not_run",
        "explanation": "Old document",
        "engine": "Legacy Engine v0",
        "is_mock": False,
        "order": 0,
        "analyzed_at": utcnow(),
        # risk deliberately omitted (None) to test Counter robustness
    })

    r = client.get(f"/projects/{project_id}/results")
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["critical_risks"] == 0
    assert s["high_risks"] == 0
    assert s["medium_risks"] == 0
    assert s["low_risks"] == 0
    assert s["total"] == 1
