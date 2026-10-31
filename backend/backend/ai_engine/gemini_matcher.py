"""
SpecTrace Gemini Matcher
========================
Wraps the Google Gemini API to perform batched semantic requirement matching
against a project's AST index and static test index.

Design principles
-----------------
* One Gemini call per batch, not one call per requirement.
* Batch size is controlled by a character-budget cap so that oversized projects
  are handled without forcing an all-or-nothing static_fallback.
* Invalid API keys, timeouts, rate limits, and malformed JSON responses are
  caught here and result in an empty list for the affected batch; the caller
  (analyzer.py) decides whether to fall back to static analysis.
* Evidence produced by Gemini is NOT validated here — the caller passes it
  through validate_evidence_with_reasons() before trusting any file/line refs.
* The Gemini model name is always configurable via the `model` argument.
* API keys are never logged or included in any return value.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger("spectrace.gemini_matcher")

# Import google.genai at module level so tests can patch `ai_engine.gemini_matcher.genai`.
# If the package is not installed the attribute is set to None; callers check before use.
try:
    import google.genai as genai  # type: ignore[import]
    import google.genai.types as genai_types  # type: ignore[import]
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Prompt budget
# ---------------------------------------------------------------------------

# Maximum characters allowed in a single Gemini prompt (conservative estimate
# relative to the 1M-token context window; keeps latency predictable).
_PROMPT_BUDGET_CHARS: int = 50_000

# Maximum characters allowed per file snippet in the AST summary section.
_SNIPPET_CHAR_LIMIT: int = 300

# Maximum characters allowed for the full code-index section of the prompt.
_CODE_INDEX_BUDGET: int = 30_000

# ---------------------------------------------------------------------------
# JSON response schema (passed to Gemini as response_schema)
# ---------------------------------------------------------------------------

_RESPONSE_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "requirement_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": [
                    "implemented",
                    "partially_implemented",
                    "missing",
                    "not_verified",
                ],
            },
            "confidence": {"type": "number"},
            "explanation": {"type": "string"},
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file": {"type": "string"},
                        "line_start": {"type": "integer"},
                        "line_end": {"type": "integer"},
                        "function": {"type": "string"},
                        "snippet": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["file", "line_start", "description"],
                },
            },
        },
        "required": [
            "requirement_id",
            "status",
            "confidence",
            "explanation",
            "evidence",
        ],
    },
}

# ---------------------------------------------------------------------------
# Prompt building helpers
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTIONS = """\
You are a software traceability analyst performing static analysis on a Python project.
You will receive:
  1. A list of software requirements with unique IDs.
  2. A structured code index (functions, classes, call sites, docstrings) derived
     from AST analysis of the project source — no code is executed.
  3. A static test-coverage index listing discovered test candidates and their
     associations with requirements.

Your task is to determine, for each requirement, whether it appears to be
implemented in the provided code index.

STRICT RULES:
- Base your analysis ONLY on evidence present in the code index.
- Do NOT invent file names, line numbers, function names, or code snippets that
  are not present in the index.
- Do NOT classify a requirement as "missing" solely because a keyword or function
  name is absent. Use "not_verified" when evidence is genuinely ambiguous or
  insufficient.
- "missing" should be used only when there is a clear positive signal of absence
  (e.g., the codebase explicitly delegates a function elsewhere or the index
  contains notes that this area is unimplemented).
- Keep confidence scores honest: use values below 0.5 when evidence is weak.
- Return exactly one result object per requirement_id listed in the input.
- Evidence file paths must exactly match paths from the code index.
- Evidence line numbers must be plausible integers from the indexed file ranges.
"""


def _summarise_ast_index(ast_index: dict, budget: int) -> str:
    """
    Produce a compact text summary of the AST index within the character budget.

    Per-file, includes: function names + line ranges, class names + method names,
    and a truncated version of any docstrings. Body snippets are shortened to
    _SNIPPET_CHAR_LIMIT characters each.
    """
    lines: list[str] = []
    remaining = budget

    for file_path, info in ast_index.items():
        if not isinstance(info, dict):
            continue

        header = f"\n--- {file_path} ---"
        if len(header) > remaining:
            break
        lines.append(header)
        remaining -= len(header)

        # Functions
        for fn in info.get("functions", []):
            name = fn.get("name", "?")
            lr = f"L{fn.get('line_start', '?')}-{fn.get('line_end', '?')}"
            doc = (fn.get("docstring") or "")[:80].replace("\n", " ")
            entry = f"  def {name}() [{lr}]" + (f"  # {doc}" if doc else "")
            if len(entry) > remaining:
                lines.append("  ... (truncated)")
                break
            lines.append(entry)
            remaining -= len(entry)

            # Snippet (truncated)
            snippet = (fn.get("snippet") or "")[:_SNIPPET_CHAR_LIMIT]
            if snippet and len(snippet) + 4 < remaining:
                lines.append(f"    {snippet[:200]}")
                remaining -= len(snippet)

        # Classes
        for cls in info.get("classes", []):
            cname = cls.get("name", "?")
            lr = f"L{cls.get('line_start', '?')}-{cls.get('line_end', '?')}"
            entry = f"  class {cname} [{lr}]"
            if len(entry) > remaining:
                break
            lines.append(entry)
            remaining -= len(entry)
            for method in cls.get("methods", []):
                mname = method.get("name", "?")
                mlr = f"L{method.get('line_start', '?')}-{method.get('line_end', '?')}"
                m_entry = f"    def {mname}() [{mlr}]"
                if len(m_entry) > remaining:
                    break
                lines.append(m_entry)
                remaining -= len(m_entry)

        # Call sites (top 10 per file)
        calls = info.get("calls", [])[:10]
        if calls:
            call_summary = "  calls: " + ", ".join(
                f"{c.get('name', '?')}@L{c.get('line', '?')}" for c in calls
            )
            if len(call_summary) <= remaining:
                lines.append(call_summary)
                remaining -= len(call_summary)

        if remaining <= 0:
            lines.append("\n... (code index truncated due to budget)")
            break

    return "\n".join(lines)


def _summarise_test_index(test_index: dict, budget: int) -> str:
    """Compact text summary of the static test index."""
    lines: list[str] = []
    remaining = budget

    tests = test_index.get("tests", [])
    for t in tests:
        tid = t.get("id", "?")
        file_ = t.get("file", "?")
        name = t.get("name", "?")
        matches = t.get("matches", [])
        entry = f"  {tid}: {name} in {file_}"
        if matches:
            entry += f" => matches: {', '.join(matches[:3])}"
        if len(entry) > remaining:
            break
        lines.append(entry)
        remaining -= len(entry)

    return "\n".join(lines) if lines else "  (no test candidates discovered)"


def build_prompt(
    requirements: list[dict],
    ast_index: dict,
    test_index: dict,
) -> str:
    """
    Build the full analysis prompt for a single batch.

    Parameters
    ----------
    requirements : list[dict]
        Each entry has 'id' and 'description'.
    ast_index : dict
        Output of extract_ast_index().
    test_index : dict
        Output of discover_static_tests().

    Returns
    -------
    str
        The prompt string to send to Gemini.
    """
    req_json = json.dumps(
        [{"id": r["id"], "description": r["description"]} for r in requirements],
        indent=2,
    )

    code_summary = _summarise_ast_index(ast_index, _CODE_INDEX_BUDGET)
    test_budget = max(2000, _PROMPT_BUDGET_CHARS - len(_SYSTEM_INSTRUCTIONS) - len(req_json) - len(code_summary) - 500)
    test_summary = _summarise_test_index(test_index, test_budget)

    prompt = (
        f"{_SYSTEM_INSTRUCTIONS}\n\n"
        f"=== REQUIREMENTS ===\n{req_json}\n\n"
        f"=== CODE INDEX ===\n{code_summary}\n\n"
        f"=== TEST COVERAGE INDEX ===\n{test_summary}\n"
    )
    return prompt


# ---------------------------------------------------------------------------
# Batch splitting
# ---------------------------------------------------------------------------

def _split_into_batches(
    requirements: list[dict],
    ast_index: dict,
    test_index: dict,
    max_batch_chars: int = _PROMPT_BUDGET_CHARS,
) -> list[list[dict]]:
    """
    Split requirements into batches such that each batch's prompt stays within
    the character budget.

    Returns a list of batches (each batch is a list of requirement dicts).
    Falls back to single-requirement batches if a lone requirement already
    exceeds the budget (the caller still attempts the call in that case).
    """
    if not requirements:
        return []

    # Pre-compute the fixed overhead (instructions + code index + test index)
    fixed_prompt = build_prompt([], ast_index, test_index)
    fixed_overhead = len(fixed_prompt) + 200  # 200-char safety margin

    batches: list[list[dict]] = []
    current_batch: list[dict] = []
    current_size = fixed_overhead

    for req in requirements:
        req_chars = len(json.dumps({"id": req["id"], "description": req["description"]})) + 5
        if current_batch and current_size + req_chars > max_batch_chars:
            batches.append(current_batch)
            current_batch = [req]
            current_size = fixed_overhead + req_chars
        else:
            current_batch.append(req)
            current_size += req_chars

    if current_batch:
        batches.append(current_batch)

    return batches


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_gemini_response(
    raw_text: str,
    requirement_ids: list[str],
) -> list[dict]:
    """
    Parse the JSON array returned by Gemini.

    Returns a list of per-requirement result dicts. On any parse failure,
    returns an empty list (the caller must fall back to static analysis for
    the affected requirements).
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("Gemini response is not valid JSON: %s", exc)
        return []

    if not isinstance(data, list):
        logger.warning("Gemini response is not a JSON array (got %s)", type(data).__name__)
        return []

    valid_ids = set(requirement_ids)
    results: list[dict] = []

    for item in data:
        if not isinstance(item, dict):
            continue
        rid = item.get("requirement_id")
        if rid not in valid_ids:
            logger.warning("Gemini returned result for unknown requirement_id '%s'; discarding", rid)
            continue
        status = item.get("status", "not_verified")
        if status not in {"implemented", "partially_implemented", "missing", "not_verified"}:
            logger.warning("Gemini returned invalid status '%s' for '%s'; defaulting to not_verified", status, rid)
            status = "not_verified"
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
            confidence = 0.0

        evidence: list[dict] = []
        for ev in item.get("evidence", []):
            if not isinstance(ev, dict):
                continue
            file_ = ev.get("file")
            line_start = ev.get("line_start")
            desc = ev.get("description", "")
            if not file_ or not isinstance(line_start, int):
                continue  # drop malformed evidence items
            evidence.append({
                "file": str(file_),
                "line_start": int(line_start),
                "line_end": ev.get("line_end"),
                "function": ev.get("function"),
                "snippet": ev.get("snippet"),
                "description": str(desc),
            })

        results.append({
            "requirement_id": rid,
            "status": status,
            "confidence": float(confidence),
            "explanation": str(item.get("explanation", "")),
            "evidence": evidence,
        })

    return results


# ---------------------------------------------------------------------------
# Main Gemini call
# ---------------------------------------------------------------------------

def _call_gemini_once(
    client: Any,
    model: str,
    prompt: str,
    timeout: int,
) -> str | None:
    """
    Make one Gemini generate_content call.
    Returns the raw response text on success, None on failure.
    Caller is responsible for retry logic.
    """
    try:
        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        return response.text
    except Exception as exc:
        return _classify_exception(exc)


def _classify_exception(exc: Exception) -> None:
    """Log the exception without exposing the API key or sensitive details."""
    msg = str(exc)
    if "429" in msg or "resource_exhausted" in msg.lower() or "quota" in msg.lower():
        logger.warning("Gemini rate limit / quota exceeded: %s", type(exc).__name__)
    elif "timeout" in msg.lower() or "deadline" in msg.lower():
        logger.warning("Gemini request timed out: %s", type(exc).__name__)
    elif "invalid" in msg.lower() and "key" in msg.lower():
        logger.warning("Gemini API key appears invalid: %s", type(exc).__name__)
    else:
        logger.warning("Gemini call failed (%s)", type(exc).__name__)
    return None


def _call_gemini_with_retry(
    client: Any,
    model: str,
    prompt: str,
    timeout: int,
    max_retries: int,
) -> str | None:
    """Call Gemini with exponential backoff on failure."""
    for attempt in range(max_retries + 1):
        raw = _call_gemini_once(client, model, prompt, timeout)
        if raw is not None:
            return raw
        if attempt < max_retries:
            delay = 2 ** attempt  # 1s, 2s
            logger.info("Retrying Gemini call in %ds (attempt %d/%d)", delay, attempt + 1, max_retries)
            time.sleep(delay)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_requirements_with_gemini(
    requirements: list[dict],
    ast_index: dict,
    test_index: dict,
    api_key: str,
    model: str = "gemini-2.0-flash",
    timeout: int = 30,
    max_retries: int = 2,
    batch_char_limit: int = _PROMPT_BUDGET_CHARS,
) -> tuple[list[dict], set[str]]:
    """
    Semantically match requirements against the project's AST and test index
    using Gemini. Splits large requirement sets into bounded batches; each
    batch is independently recoverable.

    Parameters
    ----------
    requirements : list[dict]
        Each entry must have 'id' and 'description' keys.
    ast_index : dict
        Output of extract_ast_index().
    test_index : dict
        Output of discover_static_tests().
    api_key : str
        Gemini API key. Must not be empty (checked by caller).
    model : str
        Gemini model name (configurable, never hardcoded in call sites).
    timeout : int
        Per-call timeout in seconds.
    max_retries : int
        Maximum retry attempts per batch on transient failures.
    batch_char_limit : int
        Maximum prompt characters per batch. Exposed for testing.

    Returns
    -------
    (results, failed_ids) : tuple[list[dict], set[str]]
        results     — Successfully matched requirement result dicts.
        failed_ids  — IDs for which Gemini failed; caller uses static fallback.
    """
    if genai is None:
        logger.error("google-genai is not installed; cannot use Gemini matching")
        return [], {r["id"] for r in requirements}

    client = genai.Client(api_key=api_key)
    batches = _split_into_batches(requirements, ast_index, test_index, batch_char_limit)
    logger.info("Gemini matching: %d requirement(s) split into %d batch(es)", len(requirements), len(batches))

    all_results: list[dict] = []
    failed_ids: set[str] = set()

    for batch_idx, batch in enumerate(batches):
        batch_req_ids = [r["id"] for r in batch]
        prompt = build_prompt(batch, ast_index, test_index)
        logger.debug("Batch %d: %d requirements, prompt %d chars", batch_idx, len(batch), len(prompt))

        raw_text = _call_gemini_with_retry(client, model, prompt, timeout, max_retries)
        if raw_text is None:
            logger.warning("Batch %d failed entirely; falling back to static for: %s", batch_idx, batch_req_ids)
            failed_ids.update(batch_req_ids)
            continue

        batch_results = _parse_gemini_response(raw_text, batch_req_ids)
        returned_ids = {r["requirement_id"] for r in batch_results}
        missing_from_response = set(batch_req_ids) - returned_ids
        if missing_from_response:
            logger.warning(
                "Batch %d: Gemini omitted results for: %s; falling back to static",
                batch_idx, missing_from_response,
            )
            failed_ids.update(missing_from_response)

        all_results.extend(batch_results)

    return all_results, failed_ids
