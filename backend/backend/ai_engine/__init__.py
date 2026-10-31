"""
SpecTrace AI Engine
===================
Independent static analysis and requirement traceability package.
Analyzes Python projects without importing or executing their code.

Public API
----------
Phase 2 — AST analysis & evidence validation:
    extract_ast_index, validate_evidence_bounds, validate_evidence_with_reasons

Phase 3 — Static test discovery:
    discover_static_tests

Phase 4 — Semantic analysis pipeline:
    analyze_project       (orchestrator)
    evaluate_risk         (rule-based risk classifier)
    match_requirements_with_gemini  (Gemini semantic matcher)

Backend integration entry point:
    ai_engine.backend_adapter.analyze(request: dict) -> dict
"""

from ai_engine.ast_visitor import extract_ast_index
from ai_engine.source_validator import validate_evidence_bounds, validate_evidence_with_reasons
from ai_engine.static_tests import discover_static_tests
from ai_engine.risk_analyzer import evaluate_risk
from ai_engine.analyzer import analyze_project
from ai_engine.gemini_matcher import match_requirements_with_gemini

__all__ = [
    # Phase 2
    "extract_ast_index",
    "validate_evidence_bounds",
    "validate_evidence_with_reasons",
    # Phase 3
    "discover_static_tests",
    # Phase 4
    "evaluate_risk",
    "analyze_project",
    "match_requirements_with_gemini",
]
