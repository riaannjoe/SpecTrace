"""
SpecTrace Analyzer — Main Orchestration Pipeline
=================================================
Coordinates the full analysis pipeline for a single project:

  1. Extract AST index from Python source files.
  2. Discover static test candidates.
  3. Attempt Gemini semantic matching (batched, per-requirement fallback).
  4. Build static-fallback results for requirements Gemini could not process.
  5. Apply rule-based risk classification to every result.
  6. Validate all evidence against actual source files and line ranges.
  7. Assemble and return the final EngineResponse-shaped dict.

Design constraints
------------------
* Gemini is optional: missing API key always triggers static_fallback.
* Each Gemini batch is independently recoverable; per-requirement provenance
  is preserved in the per-result `analysis_mode` field.
* Run-level `analysis_mode` is "hybrid" if ≥1 requirement used Gemini,
  "static_fallback" otherwise.
* `test_status` is always "not_run" — never modified by static discovery.
* Evidence is validated via source_validator before inclusion.
* This module never imports or executes uploaded project code.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ai_engine.ast_visitor import extract_ast_index
from ai_engine.gemini_matcher import match_requirements_with_gemini
from ai_engine.risk_analyzer import evaluate_risk
from ai_engine.source_validator import validate_evidence_with_reasons
from ai_engine.static_tests import discover_static_tests

logger = logging.getLogger("spectrace.analyzer")

_ENGINE_NAME = "SpecTrace AI Engine v1"


# ---------------------------------------------------------------------------
# Static fallback result builder
# ---------------------------------------------------------------------------

def _static_fallback_result(
    req: dict,
    test_index: dict,
    project_path: str,
) -> dict:
    """
    Build a conservative result for a requirement using only static signals.

    Status is always "not_verified" because static analysis alone cannot
    confirm or deny implementation; it can only surface test coverage candidates.
    """
    req_id = req["id"]
    req_desc = req["description"]

    # Extract per-requirement test coverage from the static test index
    test_covered = False
    raw_test_evidence: list[dict] = []

    for test in test_index.get("tests", []):
        if req_id in test.get("matches", []):
            test_covered = True
            ev = {
                "file": test.get("file", ""),
                "line_start": test.get("line_start", 1),
                "line_end": test.get("line_end"),
                "function": test.get("name"),
                "snippet": None,
                "description": f"Static test candidate: {test.get('name', '')}",
            }
            raw_test_evidence.append(ev)

    # Validate test evidence against disk
    validated_test_evidence, _ = validate_evidence_with_reasons(raw_test_evidence, project_path)

    risk_level, risk_reason = evaluate_risk(
        req_description=req_desc,
        status="not_verified",
        confidence=None,
        evidence=[],
        test_covered=test_covered and bool(validated_test_evidence),
    )

    return {
        "requirement_id": req_id,
        "status": "not_verified",
        "confidence": None,
        "risk": risk_level,
        "risk_reason": risk_reason,
        "evidence": [],
        "test_status": "not_run",
        "test_covered": test_covered and bool(validated_test_evidence),
        "test_evidence": validated_test_evidence,
        "analysis_mode": "static_fallback",
        "explanation": (
            "Static analysis only: no Gemini API key was available or Gemini "
            "could not process this requirement. Implementation status could not "
            "be determined without semantic analysis."
        ),
    }


# ---------------------------------------------------------------------------
# Gemini result builder
# ---------------------------------------------------------------------------

def _build_gemini_result(
    gemini_result: dict,
    req: dict,
    test_index: dict,
    project_path: str,
) -> dict:
    """
    Convert a raw Gemini matcher result into a final EngineResult-shaped dict.

    Validates all evidence against disk. Augments with static test coverage.
    Applies risk classification. Keeps Gemini confidence separate from static
    relevance scores.
    """
    req_id = req["id"]
    req_desc = req["description"]
    status = gemini_result.get("status", "not_verified")
    confidence = gemini_result.get("confidence")
    explanation = gemini_result.get("explanation", "")

    # Validate implementation evidence
    raw_evidence = gemini_result.get("evidence", [])
    # Normalise: gemini uses line_start; contract uses line (alias for line_start)
    normalised_evidence = []
    for ev in raw_evidence:
        normalised_evidence.append({
            "file": ev.get("file", ""),
            "line_start": ev.get("line_start") or ev.get("line", 1),
            "line_end": ev.get("line_end"),
            "function": ev.get("function"),
            "snippet": ev.get("snippet"),
            "description": ev.get("description", ""),
        })
    validated_evidence, rejected = validate_evidence_with_reasons(normalised_evidence, project_path)

    # Fix 1 & 2 — "missing" status policy
    # ─────────────────────────────────────────────────────────────────────────
    # Validated evidence items prove that code EXISTS at a specific file/line.
    # They cannot confirm that functionality is ABSENT.  Therefore:
    #   • "missing" + empty evidence  (Fix 2-B) → not_verified
    #   • "missing" + all evidence invalid (Fix 2-A) → not_verified
    #   • "missing" + valid evidence   (policy) → not_verified
    #     (valid snippets prove presence; they cannot establish absence)
    # Confidence is preserved so the caller can see Gemini's original score.
    # ─────────────────────────────────────────────────────────────────────────
    if status == "missing":
        logger.warning(
            "Req '%s': 'missing' downgraded to 'not_verified' — "
            "absence of functionality cannot be confirmed by source evidence validation.",
            req_id,
        )
        status = "not_verified"
        explanation += (
            " (Classified as 'missing' by semantic analysis but downgraded to"
            " 'not_verified': code-level evidence cannot confirm absence of functionality.)"
        )

    # For implemented / partially_implemented: if every evidence item was
    # rejected, no grounding remains — downgrade to not_verified.
    if rejected:
        logger.debug(
            "Req '%s': %d evidence item(s) rejected by validator: %s",
            req_id, len(rejected), [r["reason"] for r in rejected],
        )
        if not validated_evidence and status not in ("not_verified",):
            logger.warning(
                "Req '%s': all Gemini evidence was invalid; downgrading '%s' to not_verified",
                req_id, status,
            )
            status = "not_verified"
            confidence = 0.0
            explanation += " (All evidence items failed validation against source files.)"

    # Extract test coverage from static index
    test_covered = False
    raw_test_evidence: list[dict] = []

    for test in test_index.get("tests", []):
        if req_id in test.get("matches", []):
            test_covered = True
            ev = {
                "file": test.get("file", ""),
                "line_start": test.get("line_start", 1),
                "line_end": test.get("line_end"),
                "function": test.get("name"),
                "snippet": None,
                "description": f"Static test candidate: {test.get('name', '')}",
            }
            raw_test_evidence.append(ev)

    validated_test_evidence, _ = validate_evidence_with_reasons(raw_test_evidence, project_path)
    effective_test_covered = test_covered and bool(validated_test_evidence)

    risk_level, risk_reason = evaluate_risk(
        req_description=req_desc,
        status=status,
        confidence=confidence,
        evidence=validated_evidence,
        test_covered=effective_test_covered,
    )

    return {
        "requirement_id": req_id,
        "status": status,
        "confidence": confidence,
        "risk": risk_level,
        "risk_reason": risk_reason,
        "evidence": validated_evidence,
        "test_status": "not_run",
        "test_covered": effective_test_covered,
        "test_evidence": validated_test_evidence,
        "analysis_mode": "hybrid",
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_project(
    requirements: list[dict],
    project_path: str,
    python_files: list[str],
    api_key: str | None = None,
    model: str = "gemini-2.0-flash",
    timeout: int = 30,
) -> dict:
    """
    Full analysis pipeline for a project.

    Parameters
    ----------
    requirements : list[dict]
        Each entry has 'id' and 'description'.
    project_path : str
        Absolute path to the extracted project source directory.
    python_files : list[str]
        Relative paths (forward slashes) to Python files in the project.
    api_key : str | None
        Gemini API key. None → static_fallback mode for all requirements.
    model : str
        Gemini model name (configurable; never hardcoded in call sites).
    timeout : int
        Per-batch Gemini timeout in seconds.

    Returns
    -------
    dict
        EngineResponse-shaped dict suitable for EngineResponse.model_validate().
    """
    if not requirements:
        return {
            "engine_name": _ENGINE_NAME,
            "analysis_mode": "static_fallback",
            "is_mock": False,
            "results": [],
        }

    # --- Step 1: AST extraction ---
    logger.info("Extracting AST index from %d file(s)", len(python_files))
    try:
        ast_index = extract_ast_index(project_path, python_files)
    except Exception:
        logger.exception("AST extraction failed; continuing with empty index")
        ast_index = {}

    # --- Step 2: Static test discovery ---
    logger.info("Running static test discovery")
    try:
        test_index = discover_static_tests(project_path, python_files, ast_index, requirements)
    except Exception:
        logger.exception("Static test discovery failed; continuing without test index")
        test_index = {"tests": [], "coverage": {}}

    # --- Step 3: Gemini semantic matching (when API key is present) ---
    gemini_results_by_id: dict[str, dict] = {}
    failed_ids: set[str] = {r["id"] for r in requirements}  # pessimistic default

    if api_key:
        logger.info("Gemini API key present — attempting semantic matching")
        try:
            gemini_results, failed_ids = match_requirements_with_gemini(
                requirements=requirements,
                ast_index=ast_index,
                test_index=test_index,
                api_key=api_key,
                model=model,
                timeout=timeout,
            )
            gemini_results_by_id = {r["requirement_id"]: r for r in gemini_results}
        except Exception:
            logger.exception("Gemini matching raised unexpectedly; using static fallback")
            gemini_results_by_id = {}
            failed_ids = {r["id"] for r in requirements}
    else:
        logger.info("No Gemini API key — using static_fallback mode for all requirements")

    # --- Step 4: Assemble final results in original requirement order ---
    req_map = {r["id"]: r for r in requirements}
    final_results: list[dict] = []
    hybrid_count = 0

    for req in requirements:
        req_id = req["id"]
        gemini_result = gemini_results_by_id.get(req_id)

        if gemini_result is not None:
            result = _build_gemini_result(gemini_result, req, test_index, project_path)
            hybrid_count += 1
        else:
            result = _static_fallback_result(req, test_index, project_path)

        final_results.append(result)

    # --- Step 5: Determine run-level analysis mode ---
    run_mode = "hybrid" if hybrid_count > 0 else "static_fallback"

    logger.info(
        "Analysis complete: %d hybrid, %d static_fallback, run_mode=%s",
        hybrid_count,
        len(requirements) - hybrid_count,
        run_mode,
    )

    return {
        "engine_name": _ENGINE_NAME,
        "analysis_mode": run_mode,
        "is_mock": False,
        "results": final_results,
    }

