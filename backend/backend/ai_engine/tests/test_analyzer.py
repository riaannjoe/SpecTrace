"""
Tests for ai_engine.analyzer
==============================
Gemini is always mocked. A real temporary project directory is used so that
evidence validation (source_validator) can work against actual files.
Tests cover: static_fallback mode (no API key), hybrid mode (partial Gemini
success), full Gemini failure, per-requirement provenance, invalid evidence
handling, empty inputs, and run-level analysis_mode determination.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_engine.analyzer import analyze_project

# ---------------------------------------------------------------------------
# Helpers — build a minimal on-disk project for evidence validation
# ---------------------------------------------------------------------------

_SAMPLE_PY = """\
\"\"\"Sample module for testing.\"\"\"


def login(username: str, password: str) -> bool:
    \"\"\"Authenticate a user.\"\"\"
    return username == "admin" and password == "secret"


def upload_file(path: str) -> bool:
    \"\"\"Handle file upload.\"\"\"
    return True
"""

_SAMPLE_TEST_PY = """\
\"\"\"Tests for sample module.\"\"\"


def test_login_valid():
    from sample import login
    assert login("admin", "secret") is True


def test_upload():
    from sample import upload_file
    assert upload_file("/tmp/f.txt") is True
"""


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal on-disk project for testing."""
    (tmp_path / "sample.py").write_text(_SAMPLE_PY, encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(_SAMPLE_TEST_PY, encoding="utf-8")
    return tmp_path


REQS = [
    {"id": "REQ-001", "description": "Users must be able to log in with valid credentials"},
    {"id": "REQ-002", "description": "Users can upload files up to 50 MB"},
]

PYTHON_FILES = ["sample.py", "tests/test_sample.py"]


def _gemini_ok_response(req_ids: list[str], project_path: str) -> tuple[list[dict], set[str]]:
    """Valid Gemini results with evidence pointing at real lines in sample.py."""
    results = []
    for rid in req_ids:
        if rid == "REQ-001":
            results.append({
                "requirement_id": "REQ-001",
                "status": "implemented",
                "confidence": 0.92,
                "explanation": "login() found",
                "evidence": [
                    {"file": "sample.py", "line_start": 4, "line_end": 6,
                     "function": "login", "snippet": "def login(...):", "description": "login func"},
                ],
            })
        else:
            results.append({
                "requirement_id": rid,
                "status": "not_verified",
                "confidence": 0.3,
                "explanation": "not found",
                "evidence": [],
            })
    return results, set()


# ---------------------------------------------------------------------------
# Static fallback (no API key)
# ---------------------------------------------------------------------------

class TestStaticFallbackMode:
    def test_no_api_key_returns_static_fallback(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        assert result["analysis_mode"] == "static_fallback"

    def test_no_api_key_all_results_static_fallback(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        for r in result["results"]:
            assert r["analysis_mode"] == "static_fallback"

    def test_no_api_key_status_not_verified(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        for r in result["results"]:
            assert r["status"] == "not_verified"

    def test_no_api_key_test_status_always_not_run(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        for r in result["results"]:
            assert r["test_status"] == "not_run"

    def test_no_api_key_is_not_mock(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        assert result["is_mock"] is False

    def test_result_ids_match_requirements(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        returned_ids = [r["requirement_id"] for r in result["results"]]
        assert returned_ids == [r["id"] for r in REQS]

    def test_original_order_preserved(self, project_dir):
        """Results must appear in the same order as the input requirements."""
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        assert [r["requirement_id"] for r in result["results"]] == ["REQ-001", "REQ-002"]

    def test_risk_field_is_set(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        for r in result["results"]:
            assert r["risk"] in ("low", "medium", "high", "critical")

    def test_engine_name_present(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        assert "engine_name" in result
        assert len(result["engine_name"]) > 0


# ---------------------------------------------------------------------------
# Hybrid mode (Gemini succeeds)
# ---------------------------------------------------------------------------

class TestHybridMode:
    def _run_with_gemini(self, project_dir, gemini_return):
        with patch("ai_engine.analyzer.match_requirements_with_gemini") as mock_match:
            mock_match.return_value = gemini_return
            return analyze_project(
                requirements=REQS,
                project_path=str(project_dir),
                python_files=PYTHON_FILES,
                api_key="test-key",
                model="gemini-2.0-flash",
            )

    def test_full_gemini_success_is_hybrid(self, project_dir):
        gemini_results, failed = _gemini_ok_response(["REQ-001", "REQ-002"], str(project_dir))
        result = self._run_with_gemini(project_dir, (gemini_results, failed))
        assert result["analysis_mode"] == "hybrid"

    def test_gemini_result_mode_per_requirement(self, project_dir):
        gemini_results, failed = _gemini_ok_response(["REQ-001", "REQ-002"], str(project_dir))
        result = self._run_with_gemini(project_dir, (gemini_results, failed))
        for r in result["results"]:
            assert r["analysis_mode"] == "hybrid"

    def test_test_status_always_not_run_in_hybrid(self, project_dir):
        gemini_results, failed = _gemini_ok_response(["REQ-001", "REQ-002"], str(project_dir))
        result = self._run_with_gemini(project_dir, (gemini_results, failed))
        for r in result["results"]:
            assert r["test_status"] == "not_run"

    def test_confidence_from_gemini_preserved(self, project_dir):
        gemini_results, failed = _gemini_ok_response(["REQ-001", "REQ-002"], str(project_dir))
        result = self._run_with_gemini(project_dir, (gemini_results, failed))
        req1 = next(r for r in result["results"] if r["requirement_id"] == "REQ-001")
        assert req1["confidence"] == pytest.approx(0.92)

    def test_invalid_evidence_file_is_discarded(self, project_dir):
        """Evidence pointing at a non-existent file must be silently dropped."""
        gemini_results = [
            {
                "requirement_id": "REQ-001",
                "status": "implemented",
                "confidence": 0.8,
                "explanation": "found",
                "evidence": [
                    {"file": "nonexistent_module.py", "line_start": 1,
                     "description": "phantom evidence"},
                ],
            },
            {
                "requirement_id": "REQ-002",
                "status": "not_verified",
                "confidence": 0.3,
                "explanation": "nope",
                "evidence": [],
            },
        ]
        result = self._run_with_gemini(project_dir, (gemini_results, set()))
        req1 = next(r for r in result["results"] if r["requirement_id"] == "REQ-001")
        # Evidence for nonexistent file is discarded; status downgrades to not_verified
        assert req1["evidence"] == []
        assert req1["status"] == "not_verified"

    def test_valid_evidence_kept(self, project_dir):
        """Evidence pointing at a real file with valid line range must be kept."""
        gemini_results = [
            {
                "requirement_id": "REQ-001",
                "status": "implemented",
                "confidence": 0.9,
                "explanation": "found",
                "evidence": [
                    {"file": "sample.py", "line_start": 4, "line_end": 6,
                     "function": "login", "description": "login func"},
                ],
            },
            {
                "requirement_id": "REQ-002",
                "status": "not_verified",
                "confidence": 0.3,
                "explanation": "",
                "evidence": [],
            },
        ]
        result = self._run_with_gemini(project_dir, (gemini_results, set()))
        req1 = next(r for r in result["results"] if r["requirement_id"] == "REQ-001")
        assert len(req1["evidence"]) == 1
        assert req1["status"] == "implemented"


# ---------------------------------------------------------------------------
# Partial hybrid / mixed fallback
# ---------------------------------------------------------------------------

class TestPartialFallback:
    def test_partial_gemini_failure_mixed_modes(self, project_dir):
        """When Gemini succeeds for some and fails for others, run-level is hybrid."""
        gemini_results = [
            {"requirement_id": "REQ-001", "status": "implemented",
             "confidence": 0.9, "explanation": "found", "evidence": []},
        ]
        failed_ids = {"REQ-002"}  # REQ-002 batch failed
        with patch("ai_engine.analyzer.match_requirements_with_gemini") as mock_match:
            mock_match.return_value = (gemini_results, failed_ids)
            result = analyze_project(
                requirements=REQS,
                project_path=str(project_dir),
                python_files=PYTHON_FILES,
                api_key="test-key",
            )
        assert result["analysis_mode"] == "hybrid"
        r1 = next(r for r in result["results"] if r["requirement_id"] == "REQ-001")
        r2 = next(r for r in result["results"] if r["requirement_id"] == "REQ-002")
        assert r1["analysis_mode"] == "hybrid"
        assert r2["analysis_mode"] == "static_fallback"
        assert r2["status"] == "not_verified"

    def test_all_gemini_batches_fail_is_static_fallback(self, project_dir):
        """When all Gemini batches fail, run-level analysis_mode is static_fallback."""
        with patch("ai_engine.analyzer.match_requirements_with_gemini") as mock_match:
            mock_match.return_value = ([], {"REQ-001", "REQ-002"})
            result = analyze_project(
                requirements=REQS,
                project_path=str(project_dir),
                python_files=PYTHON_FILES,
                api_key="test-key",
            )
        assert result["analysis_mode"] == "static_fallback"

    def test_gemini_crash_falls_back_gracefully(self, project_dir):
        """Unexpected exception from match_requirements_with_gemini => static_fallback."""
        with patch("ai_engine.analyzer.match_requirements_with_gemini") as mock_match:
            mock_match.side_effect = RuntimeError("unexpected crash")
            result = analyze_project(
                requirements=REQS,
                project_path=str(project_dir),
                python_files=PYTHON_FILES,
                api_key="test-key",
            )
        assert result["analysis_mode"] == "static_fallback"
        assert len(result["results"]) == len(REQS)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_requirements_returns_empty_results(self, project_dir):
        result = analyze_project(
            requirements=[],
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        assert result["results"] == []

    def test_empty_python_files_does_not_raise(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=[],
            api_key=None,
        )
        assert len(result["results"]) == len(REQS)

    def test_nonexistent_project_path_does_not_raise(self, tmp_path):
        """AST extraction failure must be caught; analysis still produces results."""
        result = analyze_project(
            requirements=REQS,
            project_path=str(tmp_path / "nonexistent"),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        assert len(result["results"]) == len(REQS)

    def test_model_name_forwarded_to_gemini(self, project_dir):
        """The model argument must be forwarded to match_requirements_with_gemini."""
        with patch("ai_engine.analyzer.match_requirements_with_gemini") as mock_match:
            mock_match.return_value = ([], {"REQ-001", "REQ-002"})
            analyze_project(
                requirements=REQS,
                project_path=str(project_dir),
                python_files=PYTHON_FILES,
                api_key="test-key",
                model="gemini-1.5-pro",
            )
        _, call_kwargs = mock_match.call_args
        assert call_kwargs.get("model") == "gemini-1.5-pro" or mock_match.call_args[0][3] == "gemini-1.5-pro"

    def test_result_count_equals_requirement_count(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        assert len(result["results"]) == len(REQS)

    def test_risk_field_never_none(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        for r in result["results"]:
            assert r["risk"] is not None

    def test_risk_reason_never_empty(self, project_dir):
        result = analyze_project(
            requirements=REQS,
            project_path=str(project_dir),
            python_files=PYTHON_FILES,
            api_key=None,
        )
        for r in result["results"]:
            assert isinstance(r["risk_reason"], str)
            assert len(r["risk_reason"]) > 0

    def test_api_key_not_in_output(self, project_dir):
        """The API key must never appear in the result dict."""
        with patch("ai_engine.analyzer.match_requirements_with_gemini") as mock_match:
            mock_match.return_value = ([], {"REQ-001", "REQ-002"})
            result = analyze_project(
                requirements=REQS,
                project_path=str(project_dir),
                python_files=PYTHON_FILES,
                api_key="super-secret-key-12345",
            )
        result_str = json.dumps(result)
        assert "super-secret-key-12345" not in result_str



# ---------------------------------------------------------------------------
# Fix 1 & 2 — "missing" status downgrade regression tests
# ---------------------------------------------------------------------------

class TestMissingStatusDowngrade:
    """
    Covers all four cases from the Phase 4 audit fix specification.

    Policy: "missing" can only arise from Gemini's semantic reasoning.
    Code-level evidence validation can confirm that code EXISTS at a file/line,
    but it CANNOT confirm that functionality is ABSENT.
    Therefore every "missing" result from Gemini is downgraded to "not_verified"
    regardless of whether evidence is present, absent, or partially valid.
    """

    def _run_single(self, project_dir, gemini_result_dict):
        """Run analyze_project with one mocked Gemini result."""
        with patch("ai_engine.analyzer.match_requirements_with_gemini") as mock_match:
            mock_match.return_value = ([gemini_result_dict], set())
            return analyze_project(
                requirements=[{"id": "REQ-001", "description": "Users must log in"}],
                project_path=str(project_dir),
                python_files=["sample.py", "tests/test_sample.py"],
                api_key="test-key",
            )

    # Fix 2-B: missing + empty evidence → not_verified
    def test_missing_empty_evidence_downgraded(self, project_dir):
        """Regression: Fix 2-B — 'missing' with an empty evidence list → 'not_verified'."""
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "missing",
            "confidence": 0.1,
            "explanation": "No login function found anywhere.",
            "evidence": [],
        })
        assert r["results"][0]["status"] == "not_verified"

    # Fix 2-A: missing + all evidence invalid → not_verified
    def test_missing_all_evidence_invalid_downgraded(self, project_dir):
        """Regression: Fix 2-A — 'missing' with entirely invalid evidence → 'not_verified'."""
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "missing",
            "confidence": 0.1,
            "explanation": "Phantom file reference.",
            "evidence": [
                {"file": "does_not_exist.py", "line_start": 5,
                 "description": "hallucinated reference"},
            ],
        })
        result = r["results"][0]
        assert result["status"] == "not_verified"
        assert result["evidence"] == []

    # Policy: missing + valid evidence still → not_verified
    def test_missing_valid_evidence_downgraded(self, project_dir):
        """
        Regression (policy): 'missing' + valid file/line evidence → 'not_verified'.

        A code snippet that validates against disk proves the code EXISTS at that
        location. It does not prove that the required functionality is absent.
        Treating an existing snippet as evidence of absence would produce a
        misleading 'missing' conclusion.
        """
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "missing",
            "confidence": 0.2,
            "explanation": "Stub present but no real implementation.",
            "evidence": [
                # sample.py L4–6 genuinely exists on disk
                {"file": "sample.py", "line_start": 4, "line_end": 6,
                 "function": "login", "description": "incomplete stub"},
            ],
        })
        result = r["results"][0]
        # Even though the evidence is valid, absence cannot be confirmed
        assert result["status"] == "not_verified"

    # Specification case 4: explicit "evidence policy" — absence is not confirmable
    def test_missing_downgrade_is_always_applied(self, project_dir):
        """
        Regression (case 4): no combination of evidence can upgrade 'missing'
        to a confirmed absence conclusion.  The policy is unconditional.
        """
        for evidence_list in [
            [],
            [{"file": "ghost.py", "line_start": 1, "description": "invalid"}],
            [{"file": "sample.py", "line_start": 4, "line_end": 6,
              "description": "real line, valid evidence"}],
        ]:
            r = self._run_single(project_dir, {
                "requirement_id": "REQ-001",
                "status": "missing",
                "confidence": 0.05,
                "explanation": "Not implemented.",
                "evidence": evidence_list,
            })
            assert r["results"][0]["status"] == "not_verified", (
                f"Expected not_verified but got {r['results'][0]['status']} "
                f"for evidence={evidence_list}"
            )

    def test_missing_downgrade_appends_explanation(self, project_dir):
        """Downgrade must augment the explanation string, not erase it."""
        original_explanation = "Requirement not found in codebase."
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "missing",
            "confidence": 0.1,
            "explanation": original_explanation,
            "evidence": [],
        })
        exp = r["results"][0]["explanation"]
        assert original_explanation in exp, "Original explanation must be preserved"
        assert len(exp) > len(original_explanation), "Downgrade note must be appended"

    def test_missing_confidence_preserved_after_downgrade(self, project_dir):
        """Confidence from Gemini is preserved after 'missing' → 'not_verified' downgrade."""
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "missing",
            "confidence": 0.15,
            "explanation": "Not found.",
            "evidence": [],
        })
        result = r["results"][0]
        assert result["status"] == "not_verified"
        # confidence is preserved (not zeroed) because the downgrade is policy-based,
        # not evidence-quality-based
        assert result["confidence"] == pytest.approx(0.15)

    # ── Pre-existing behaviour preserved ───────────────────────────────────

    def test_implemented_all_evidence_invalid_still_downgraded(self, project_dir):
        """Pre-existing Fix 1 behaviour: implemented + all-invalid evidence → not_verified."""
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "implemented",
            "confidence": 0.9,
            "explanation": "Found in ghost file.",
            "evidence": [
                {"file": "ghost.py", "line_start": 1, "description": "phantom"},
            ],
        })
        assert r["results"][0]["status"] == "not_verified"

    def test_implemented_valid_evidence_not_downgraded(self, project_dir):
        """implemented + valid evidence must NOT be changed."""
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "implemented",
            "confidence": 0.9,
            "explanation": "Found login() in sample.py.",
            "evidence": [
                {"file": "sample.py", "line_start": 4, "line_end": 6,
                 "function": "login", "description": "login func"},
            ],
        })
        assert r["results"][0]["status"] == "implemented"

    def test_partially_implemented_valid_evidence_not_downgraded(self, project_dir):
        """partially_implemented + valid evidence must NOT be changed."""
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "partially_implemented",
            "confidence": 0.55,
            "explanation": "Partial stub in sample.py.",
            "evidence": [
                {"file": "sample.py", "line_start": 4, "line_end": 6,
                 "description": "partial stub"},
            ],
        })
        assert r["results"][0]["status"] == "partially_implemented"

    def test_not_verified_from_gemini_passes_through_unchanged(self, project_dir):
        """not_verified from Gemini must pass through without modification."""
        r = self._run_single(project_dir, {
            "requirement_id": "REQ-001",
            "status": "not_verified",
            "confidence": 0.3,
            "explanation": "Ambiguous evidence.",
            "evidence": [],
        })
        assert r["results"][0]["status"] == "not_verified"
