"""
SpecTrace AI Engine — Backend Adapter
======================================
Thin bridge between the FastAPI analysis service and the AI engine.

This module exposes exactly ONE public function:

    def analyze(request: dict) -> dict

It is loaded by the backend via importlib:

    module = importlib.import_module(settings.ANALYSIS_ENGINE_MODULE)
    raw    = module.analyze(payload_dict)

Contract
--------
* Input:  dict shaped like EngineRequest (project_id, project_path,
          python_files, requirements).
* Output: dict shaped like EngineResponse (engine_name, analysis_mode,
          is_mock, results[]).
* Never raises: all exceptions are caught and a safe static_fallback
  EngineResponse dict is returned so the backend can still store results.
* The Gemini API key is read here from environment / settings.
  It is NEVER logged, never included in the response, and never forwarded
  to the user in error messages.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("spectrace.backend_adapter")

_ENGINE_NAME = "SpecTrace AI Engine v1"


def analyze(request: dict) -> dict:
    """
    Entry point called by the FastAPI analysis service.

    Parameters
    ----------
    request : dict
        Must contain:
            project_id   : str
            project_path : str   — absolute path to uploaded project source
            python_files : list[str] — relative paths with forward slashes
            requirements : list[dict] — each has 'id' and 'description'

    Returns
    -------
    dict
        EngineResponse-shaped dict. Always returns a valid structure; never
        raises so that the backend can handle failures gracefully.
    """
    try:
        return _run_analysis(request)
    except Exception:
        logger.exception(
            "Backend adapter encountered an unexpected error; returning static_fallback skeleton"
        )
        # Build a minimal valid skeleton so the backend validator doesn't crash
        requirements = request.get("requirements", [])
        return _build_emergency_response(requirements)


def _run_analysis(request: dict) -> dict:
    """Inner implementation — may raise; _analyze catches."""
    from ai_engine.analyzer import analyze_project  # local import keeps adapter thin

    project_path: str = request["project_path"]
    python_files: list[str] = request.get("python_files", [])
    requirements: list[dict] = request.get("requirements", [])

    # Resolve Gemini settings from environment (settings object may not be
    # importable in all deployment contexts, so we read env vars directly).
    api_key: str | None = _get_api_key()
    model: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    timeout: int = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "30"))

    # Try to import settings for a richer config path (backend deployment).
    try:
        from app.config import settings as _settings  # type: ignore[import]
        if api_key is None:
            api_key = _settings.GEMINI_API_KEY
        model = _settings.GEMINI_MODEL
        timeout = _settings.GEMINI_TIMEOUT_SECONDS
    except ImportError:
        pass  # running outside FastAPI context — env vars are sufficient

    return analyze_project(
        requirements=requirements,
        project_path=project_path,
        python_files=python_files,
        api_key=api_key,
        model=model,
        timeout=timeout,
    )


def _get_api_key() -> str | None:
    """Read the Gemini API key from the environment. Returns None if not set."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return key if key else None


def _build_emergency_response(requirements: list[dict]) -> dict:
    """
    Minimal valid EngineResponse when everything else fails.
    All requirements are marked not_verified / static_fallback.
    """
    results = []
    for req in requirements:
        results.append({
            "requirement_id": req.get("id", "unknown"),
            "status": "not_verified",
            "confidence": None,
            "risk": "medium",
            "risk_reason": "Analysis engine encountered an unexpected error.",
            "evidence": [],
            "test_status": "not_run",
            "test_covered": False,
            "test_evidence": [],
            "analysis_mode": "static_fallback",
            "explanation": (
                "The analysis engine encountered an internal error and could not "
                "complete the analysis. This result is a safe placeholder."
            ),
        })
    return {
        "engine_name": _ENGINE_NAME,
        "analysis_mode": "static_fallback",
        "is_mock": False,
        "results": results,
    }

