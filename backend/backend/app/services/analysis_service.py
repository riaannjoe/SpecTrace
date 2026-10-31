"""Coordinates one analysis run: load inputs -> call engine -> VALIDATE output -> store -> respond."""
import logging
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from app.analysis.adapter import run_engine
from app.analysis.contract import EngineRequest, EngineRequirement, EngineResponse
from app.database import operations as db
from app.services.project_service import get_project_or_404
from app.utils import file_handler
from app.utils.errors import AppError
from app.utils.ids import new_id, utcnow

logger = logging.getLogger("spectrace.analysis")


def run_analysis(project_id: str) -> dict:
    project = get_project_or_404(project_id)
    if project["status"] == "analyzing":
        raise AppError(409, "Analysis is already running for this project.")

    requirements = db.list_requirements(project_id)
    if not requirements:
        raise AppError(400, "This project has no requirements yet. Add requirements before analysing.")

    source_dir = Path(project["storage_path"])
    if not source_dir.is_dir():
        raise AppError(500, "The extracted project files are missing on the server. Please upload the project again.")

    request = EngineRequest(
        project_id=project_id,
        project_path=str(source_dir),
        python_files=file_handler.list_python_files(source_dir),
        requirements=[EngineRequirement(id=r["id"], description=r["description"]) for r in requirements],
    )

    db.update_project(project_id, {"status": "analyzing"})
    try:
        raw = run_engine(request)
        docs, response = _validate_and_build_docs(project_id, requirements, raw)
        db.replace_results(project_id, docs)
        for doc in docs:
            db.set_requirement_status(doc["requirement_id"], doc["status"])
        db.update_project(project_id, {"status": "analyzed", "last_analyzed_at": utcnow()})
    except Exception:
        db.update_project(project_id, {"status": "analysis_failed"})
        raise

    return get_results(project_id)


def _validate_and_build_docs(project_id: str, requirements: list[dict], raw: dict):
    """Never trust engine output: check its structure, then turn it into MongoDB documents."""
    try:
        response = EngineResponse.model_validate(raw)
    except ValidationError as exc:
        logger.error("Invalid engine output: %s", exc)
        raise AppError(502, "The analysis engine returned output that does not match the contract.") from exc

    known_ids = {r["id"] for r in requirements}
    by_req = {}
    for result in response.results:
        if result.requirement_id not in known_ids:
            raise AppError(502, f"Engine returned a result for unknown requirement '{result.requirement_id}'.")
        by_req[result.requirement_id] = result

    now = utcnow()
    docs = []
    for order, req in enumerate(requirements):
        res = by_req.get(req["id"])
        if res is None:  # engine skipped it -> be honest, mark not_verified
            status, evidence, test_status = "not_verified", [], "not_run"
            explanation = "The analysis engine returned no result for this requirement."
        else:
            status, evidence, test_status, explanation = res.status, res.evidence, res.test_status, res.explanation
        first = evidence[0] if evidence else None
        docs.append({
            "_id": new_id("result"),
            "project_id": project_id,
            "requirement_id": req["id"],
            "requirement_description": req["description"],
            "status": status,
            "evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in evidence],
            "file_name": first.file if first else None,
            "line_number": first.line if first else None,
            "test_status": test_status,
            "explanation": explanation,
            "engine": response.engine_name,
            "is_mock": response.is_mock,
            "order": order,
            "analyzed_at": now,
        })
    return docs, response


def get_results(project_id: str) -> dict:
    project = get_project_or_404(project_id)
    results = db.list_results(project_id)
    counts = Counter(r["status"] for r in results)
    return {
        "project_id": project_id,
        "project_name": project["project_name"],
        "project_status": project["status"],
        "analyzed_at": results[0]["analyzed_at"] if results else None,
        "engine": results[0]["engine"] if results else None,
        "is_mock": results[0]["is_mock"] if results else False,
        "summary": {
            "total": len(results),
            "implemented": counts["implemented"],
            "partially_implemented": counts["partially_implemented"],
            "missing": counts["missing"],
            "not_verified": counts["not_verified"],
        },
        "results": results,
    }
