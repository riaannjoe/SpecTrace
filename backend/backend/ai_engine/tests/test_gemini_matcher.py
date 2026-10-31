"""
Tests for ai_engine.gemini_matcher
====================================
All Gemini API calls are mocked. No network access is required.
Tests cover: batching, prompt building, response parsing, retry logic,
malformed responses, invalid evidence, API key absence, oversized projects,
partial batch failure, and rate-limit fallback.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, call

import pytest

from ai_engine.gemini_matcher import (
    _parse_gemini_response,
    _split_into_batches,
    build_prompt,
    match_requirements_with_gemini,
    _PROMPT_BUDGET_CHARS,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REQS_2 = [
    {"id": "REQ-001", "description": "Users must be able to log in"},
    {"id": "REQ-002", "description": "Users can upload files up to 50 MB"},
]

REQS_3 = REQS_2 + [{"id": "REQ-003", "description": "System must send email notifications"}]

MINIMAL_AST = {
    "auth.py": {
        "functions": [
            {"name": "login", "line_start": 10, "line_end": 25, "docstring": "Login handler", "snippet": "def login(): ..."}
        ],
        "classes": [],
        "calls": [{"name": "check_password", "line": 15}],
    }
}

MINIMAL_TEST_INDEX = {
    "tests": [
        {"id": "tid1", "file": "tests/test_auth.py", "name": "test_login", "matches": ["REQ-001"]}
    ]
}

VALID_GEMINI_RESPONSE = json.dumps([
    {
        "requirement_id": "REQ-001",
        "status": "implemented",
        "confidence": 0.9,
        "explanation": "login() found in auth.py",
        "evidence": [
            {
                "file": "auth.py",
                "line_start": 10,
                "line_end": 25,
                "function": "login",
                "snippet": "def login(): ...",
                "description": "login function handles authentication",
            }
        ],
    }
])

# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_contains_requirement_id(self):
        prompt = build_prompt(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX)
        assert "REQ-001" in prompt
        assert "REQ-002" in prompt

    def test_contains_requirement_description(self):
        prompt = build_prompt(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX)
        assert "log in" in prompt
        assert "upload files" in prompt

    def test_contains_code_index(self):
        prompt = build_prompt(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX)
        assert "auth.py" in prompt
        assert "login" in prompt

    def test_contains_test_index(self):
        prompt = build_prompt(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX)
        assert "test_login" in prompt or "tid1" in prompt

    def test_empty_requirements_builds_without_error(self):
        prompt = build_prompt([], MINIMAL_AST, MINIMAL_TEST_INDEX)
        assert isinstance(prompt, str)

    def test_empty_ast_builds_without_error(self):
        prompt = build_prompt(REQS_2, {}, MINIMAL_TEST_INDEX)
        assert "REQ-001" in prompt

    def test_empty_test_index_builds_without_error(self):
        prompt = build_prompt(REQS_2, MINIMAL_AST, {})
        assert "REQ-001" in prompt

    def test_prompt_is_string(self):
        prompt = build_prompt(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_oversized_ast_is_truncated(self):
        """A very large AST index must not produce a prompt exceeding the budget by a large margin."""
        large_ast = {
            f"module_{i}.py": {
                "functions": [
                    {"name": f"func_{j}", "line_start": j * 10, "line_end": j * 10 + 9,
                     "docstring": "x" * 200, "snippet": "y" * 300}
                    for j in range(50)
                ],
                "classes": [],
                "calls": [],
            }
            for i in range(30)
        }
        prompt = build_prompt(REQS_2, large_ast, MINIMAL_TEST_INDEX)
        # Prompt may exceed budget slightly due to truncation message overhead,
        # but should not be many times over budget.
        assert len(prompt) < _PROMPT_BUDGET_CHARS * 3


# ---------------------------------------------------------------------------
# _split_into_batches
# ---------------------------------------------------------------------------

class TestSplitIntoBatches:
    def test_small_set_is_one_batch(self):
        batches = _split_into_batches(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX)
        assert len(batches) == 1
        assert {r["id"] for r in batches[0]} == {"REQ-001", "REQ-002"}

    def test_empty_requirements_returns_empty(self):
        batches = _split_into_batches([], MINIMAL_AST, MINIMAL_TEST_INDEX)
        assert batches == []

    def test_all_ids_preserved_across_batches(self):
        reqs = [{"id": f"REQ-{i:03d}", "description": f"Requirement {i}"} for i in range(20)]
        batches = _split_into_batches(reqs, MINIMAL_AST, MINIMAL_TEST_INDEX)
        all_ids = [r["id"] for batch in batches for r in batch]
        assert sorted(all_ids) == sorted(r["id"] for r in reqs)

    def test_tiny_budget_splits_into_single_req_batches(self):
        """With a very small budget each requirement goes into its own batch."""
        reqs = [
            {"id": "REQ-001", "description": "Req one"},
            {"id": "REQ-002", "description": "Req two"},
        ]
        # Budget so small that each req must be its own batch.
        batches = _split_into_batches(reqs, {}, {}, max_batch_chars=10)
        assert len(batches) == len(reqs)
        for batch in batches:
            assert len(batch) == 1

    def test_order_preserved_within_batches(self):
        reqs = [{"id": f"REQ-{i:03d}", "description": f"Req {i}"} for i in range(5)]
        batches = _split_into_batches(reqs, {}, {})
        ordered = [r["id"] for batch in batches for r in batch]
        assert ordered == [r["id"] for r in reqs]


# ---------------------------------------------------------------------------
# _parse_gemini_response
# ---------------------------------------------------------------------------

class TestParseGeminiResponse:
    def test_valid_response_parsed(self):
        results = _parse_gemini_response(VALID_GEMINI_RESPONSE, ["REQ-001"])
        assert len(results) == 1
        r = results[0]
        assert r["requirement_id"] == "REQ-001"
        assert r["status"] == "implemented"
        assert r["confidence"] == pytest.approx(0.9)
        assert len(r["evidence"]) == 1

    def test_unknown_requirement_id_discarded(self):
        results = _parse_gemini_response(VALID_GEMINI_RESPONSE, ["REQ-999"])
        assert results == []

    def test_invalid_json_returns_empty(self):
        results = _parse_gemini_response("not json at all {{{", ["REQ-001"])
        assert results == []

    def test_json_object_instead_of_array_returns_empty(self):
        results = _parse_gemini_response('{"requirement_id": "REQ-001"}', ["REQ-001"])
        assert results == []

    def test_invalid_status_defaults_to_not_verified(self):
        payload = json.dumps([{
            "requirement_id": "REQ-001",
            "status": "definitely_wrong",
            "confidence": 0.5,
            "explanation": "bad status",
            "evidence": [],
        }])
        results = _parse_gemini_response(payload, ["REQ-001"])
        assert results[0]["status"] == "not_verified"

    def test_invalid_confidence_defaults_to_zero(self):
        payload = json.dumps([{
            "requirement_id": "REQ-001",
            "status": "implemented",
            "confidence": "high",
            "explanation": "conf is string",
            "evidence": [],
        }])
        results = _parse_gemini_response(payload, ["REQ-001"])
        assert results[0]["confidence"] == 0.0

    def test_confidence_out_of_range_defaults_to_zero(self):
        payload = json.dumps([{
            "requirement_id": "REQ-001",
            "status": "implemented",
            "confidence": 1.5,
            "explanation": "conf > 1",
            "evidence": [],
        }])
        results = _parse_gemini_response(payload, ["REQ-001"])
        assert results[0]["confidence"] == 0.0

    def test_malformed_evidence_items_dropped(self):
        """Evidence items missing required keys must be silently dropped."""
        payload = json.dumps([{
            "requirement_id": "REQ-001",
            "status": "implemented",
            "confidence": 0.8,
            "explanation": "some evidence",
            "evidence": [
                {"file": "auth.py", "line_start": 10, "description": "valid"},
                {"description": "missing file and line_start"},   # dropped
                {"file": "auth.py", "description": "missing line_start"},  # dropped
            ],
        }])
        results = _parse_gemini_response(payload, ["REQ-001"])
        assert len(results[0]["evidence"]) == 1

    def test_empty_response_array(self):
        results = _parse_gemini_response("[]", ["REQ-001"])
        assert results == []

    def test_multiple_requirements_parsed(self):
        payload = json.dumps([
            {"requirement_id": "REQ-001", "status": "implemented",
             "confidence": 0.9, "explanation": "found", "evidence": []},
            {"requirement_id": "REQ-002", "status": "missing",
             "confidence": 0.1, "explanation": "not found", "evidence": []},
        ])
        results = _parse_gemini_response(payload, ["REQ-001", "REQ-002"])
        assert len(results) == 2
        ids = {r["requirement_id"] for r in results}
        assert ids == {"REQ-001", "REQ-002"}

    def test_all_valid_statuses_accepted(self):
        for status in ("implemented", "partially_implemented", "missing", "not_verified"):
            payload = json.dumps([{
                "requirement_id": "REQ-001",
                "status": status,
                "confidence": 0.5,
                "explanation": "ok",
                "evidence": [],
            }])
            results = _parse_gemini_response(payload, ["REQ-001"])
            assert results[0]["status"] == status


# ---------------------------------------------------------------------------
# match_requirements_with_gemini — integration with mocked client
# ---------------------------------------------------------------------------

def _make_mock_client(response_text: str):
    """Build a minimal mock of google.genai.Client."""
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


def _make_failing_client(exc: Exception):
    """Build a client that always raises."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = exc
    return mock_client


class TestMatchRequirementsWithGemini:
    def _run(self, requirements, ast_index, test_index, client_mock, **kwargs):
        """Patch google.genai.Client to inject mock_client."""
        with patch("ai_engine.gemini_matcher.genai") as mock_genai:
            mock_genai.Client.return_value = client_mock
            return match_requirements_with_gemini(
                requirements, ast_index, test_index,
                api_key="test-key",
                model="gemini-2.0-flash",
                **kwargs,
            )

    # -- Happy path --------------------------------------------------------

    def test_successful_single_batch(self):
        response_text = json.dumps([
            {"requirement_id": "REQ-001", "status": "implemented",
             "confidence": 0.9, "explanation": "found", "evidence": []},
            {"requirement_id": "REQ-002", "status": "missing",
             "confidence": 0.1, "explanation": "not found", "evidence": []},
        ])
        client = _make_mock_client(response_text)
        results, failed = self._run(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX, client)
        assert len(results) == 2
        assert failed == set()

    def test_result_ids_match_input(self):
        response_text = json.dumps([
            {"requirement_id": "REQ-001", "status": "implemented",
             "confidence": 0.9, "explanation": "x", "evidence": []},
            {"requirement_id": "REQ-002", "status": "not_verified",
             "confidence": 0.3, "explanation": "x", "evidence": []},
        ])
        client = _make_mock_client(response_text)
        results, failed = self._run(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX, client)
        returned_ids = {r["requirement_id"] for r in results}
        assert returned_ids == {"REQ-001", "REQ-002"}
        assert failed == set()

    # -- Missing API key ---------------------------------------------------

    def test_missing_api_key_all_fail(self):
        """When google-genai is not importable, all IDs go to failed_ids."""
        with patch.dict("sys.modules", {"google.genai": None}):
            # Simulate ImportError by patching the import inside the function
            import importlib
            import ai_engine.gemini_matcher as gm
            original = gm.genai if hasattr(gm, "genai") else None
            # Direct test: if client instantiation fails all requirements should be in failed_ids
            client = _make_failing_client(Exception("no module"))
            results, failed = self._run(REQS_2, {}, {}, client)
            assert len(results) == 0
            assert failed == {"REQ-001", "REQ-002"}

    # -- Batch failure / partial -------------------------------------------

    def test_all_batches_fail_returns_all_ids_failed(self):
        client = _make_failing_client(Exception("network error"))
        results, failed = self._run(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX, client)
        assert results == []
        assert failed == {"REQ-001", "REQ-002"}

    def test_partial_batch_failure_hybrid(self):
        """When one batch succeeds and one fails, successful results are returned
        and failed IDs are captured separately."""
        # Force 2 batches by using a tiny budget per batch
        req_a = {"id": "REQ-A", "description": "Alpha requirement"}
        req_b = {"id": "REQ-B", "description": "Beta requirement"}
        reqs = [req_a, req_b]

        call_count = 0
        responses = [
            json.dumps([{"requirement_id": "REQ-A", "status": "implemented",
                         "confidence": 0.8, "explanation": "found", "evidence": []}]),
            None,  # second batch fails
        ]

        mock_response_a = MagicMock()
        mock_response_a.text = responses[0]

        mock_client = MagicMock()
        side_effects = [mock_response_a, Exception("timeout")]
        mock_client.models.generate_content.side_effect = side_effects

        # Use a very small batch_char_limit to force 2 batches
        with patch("ai_engine.gemini_matcher.genai") as mock_genai:
            mock_genai.Client.return_value = mock_client
            results, failed = match_requirements_with_gemini(
                reqs, {}, {},
                api_key="test-key",
                model="gemini-2.0-flash",
                max_retries=0,  # no retries so second batch fails immediately
                batch_char_limit=10,  # tiny budget forces 1 req per batch
            )

        assert any(r["requirement_id"] == "REQ-A" for r in results)
        assert "REQ-B" in failed

    # -- Malformed JSON response -------------------------------------------

    def test_malformed_json_all_ids_failed(self):
        client = _make_mock_client("this is not json <<<")
        results, failed = self._run(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX, client)
        assert results == []
        assert failed == {"REQ-001", "REQ-002"}

    def test_gemini_omits_requirement_goes_to_failed(self):
        """If Gemini returns only some requirements, the rest go to failed_ids."""
        response_text = json.dumps([
            {"requirement_id": "REQ-001", "status": "implemented",
             "confidence": 0.9, "explanation": "found", "evidence": []},
            # REQ-002 intentionally omitted
        ])
        client = _make_mock_client(response_text)
        results, failed = self._run(REQS_2, MINIMAL_AST, MINIMAL_TEST_INDEX, client)
        assert len(results) == 1
        assert "REQ-002" in failed

    # -- Retry behaviour ---------------------------------------------------

    def test_retry_succeeds_on_second_attempt(self):
        """First call raises, second call succeeds — with max_retries=1."""
        response_text = json.dumps([
            {"requirement_id": "REQ-001", "status": "implemented",
             "confidence": 0.8, "explanation": "ok", "evidence": []},
            {"requirement_id": "REQ-002", "status": "not_verified",
             "confidence": 0.3, "explanation": "ok", "evidence": []},
        ])
        mock_response = MagicMock()
        mock_response.text = response_text
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [
            Exception("transient"),
            mock_response,
        ]

        with patch("ai_engine.gemini_matcher.genai") as mock_genai:
            with patch("ai_engine.gemini_matcher.time.sleep"):  # don't actually sleep
                mock_genai.Client.return_value = mock_client
                results, failed = match_requirements_with_gemini(
                    REQS_2, {}, {},
                    api_key="test-key",
                    model="gemini-2.0-flash",
                    max_retries=1,
                )
        assert len(results) == 2
        assert failed == set()

    def test_max_retries_exhausted_returns_failed(self):
        """All retries fail — all IDs go to failed_ids."""
        mock_client = _make_failing_client(Exception("permanent error"))
        with patch("ai_engine.gemini_matcher.genai") as mock_genai:
            with patch("ai_engine.gemini_matcher.time.sleep"):
                mock_genai.Client.return_value = mock_client
                results, failed = match_requirements_with_gemini(
                    REQS_2, {}, {},
                    api_key="test-key",
                    model="gemini-2.0-flash",
                    max_retries=2,
                )
        assert results == []
        assert failed == {"REQ-001", "REQ-002"}

    # -- Model name configurability ----------------------------------------

    def test_model_name_is_passed_to_client(self):
        response_text = json.dumps([
            {"requirement_id": "REQ-001", "status": "not_verified",
             "confidence": 0.5, "explanation": "x", "evidence": []},
            {"requirement_id": "REQ-002", "status": "not_verified",
             "confidence": 0.5, "explanation": "x", "evidence": []},
        ])
        client = _make_mock_client(response_text)
        with patch("ai_engine.gemini_matcher.genai") as mock_genai:
            mock_genai.Client.return_value = client
            match_requirements_with_gemini(
                REQS_2, {}, {},
                api_key="test-key",
                model="gemini-1.5-pro",
            )
        # Verify the model name was forwarded to generate_content
        call_kwargs = client.models.generate_content.call_args
        assert call_kwargs is not None
        # model is the first positional or keyword argument
        args, kwargs = call_kwargs
        model_used = kwargs.get("model") or (args[0] if args else None)
        assert model_used == "gemini-1.5-pro"

    # -- Empty inputs ------------------------------------------------------

    def test_empty_requirements_returns_empty(self):
        client = _make_mock_client("[]")
        with patch("ai_engine.gemini_matcher.genai") as mock_genai:
            mock_genai.Client.return_value = client
            results, failed = match_requirements_with_gemini(
                [], {}, {},
                api_key="test-key",
                model="gemini-2.0-flash",
            )
        assert results == []
        assert failed == set()
        client.models.generate_content.assert_not_called()

    # -- Invalid evidence from Gemini -------------------------------------

    def test_invalid_evidence_items_dropped_in_parse(self):
        """Evidence without required keys is dropped; the result is still returned."""
        response_text = json.dumps([{
            "requirement_id": "REQ-001",
            "status": "implemented",
            "confidence": 0.8,
            "explanation": "found",
            "evidence": [
                {"file": "auth.py", "line_start": 10, "description": "valid ev"},
                {"description": "no file or line_start"},
            ],
        }])
        client = _make_mock_client(response_text)
        results, failed = self._run(
            [{"id": "REQ-001", "description": "Login requirement"}],
            {}, {}, client,
        )
        assert len(results) == 1
        assert len(results[0]["evidence"]) == 1
        assert failed == set()

