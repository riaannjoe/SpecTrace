"""Chooses which engine runs. Switch with ANALYSIS_ENGINE=mock|real in .env - no code changes needed."""
import importlib
import logging

from app.analysis import mock_adapter
from app.analysis.contract import EngineRequest
from app.config import settings
from app.utils.errors import AppError

logger = logging.getLogger("spectrace.analysis")


def run_engine(request: EngineRequest) -> dict:
    """Call the selected engine and return its RAW output (validated later by analysis_service)."""
    payload = request.model_dump()

    if settings.ANALYSIS_ENGINE == "mock":
        return mock_adapter.analyze(payload)

    if settings.ANALYSIS_ENGINE == "real":
        try:
            module = importlib.import_module(settings.ANALYSIS_ENGINE_MODULE)
        except ImportError as exc:
            raise AppError(
                500,
                f"Real analysis engine module '{settings.ANALYSIS_ENGINE_MODULE}' could not be imported. "
                "Place your teammate's package inside backend/ or set ANALYSIS_ENGINE=mock.",
            ) from exc
        if not hasattr(module, "analyze"):
            raise AppError(500, f"Module '{settings.ANALYSIS_ENGINE_MODULE}' has no analyze(request) function.")
        try:
            return module.analyze(payload)
        except Exception as exc:  # the engine is someone else's code: never let it crash the API
            logger.exception("Analysis engine crashed")
            raise AppError(502, f"The analysis engine failed: {exc}") from exc

    raise AppError(500, f"Unknown ANALYSIS_ENGINE '{settings.ANALYSIS_ENGINE}'. Use 'mock' or 'real'.")
