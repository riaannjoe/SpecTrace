from app.database import operations as db
from app.services.project_service import get_project_or_404
from app.utils.errors import AppError
from app.utils.ids import new_id, utcnow


def add_requirements(project_id: str, descriptions: list[str], replace: bool) -> dict:
    project = get_project_or_404(project_id)
    if project["status"] == "analyzing":
        raise AppError(409, "Analysis is currently running for this project. Try again shortly.")

    if replace:
        db.delete_requirements(project_id)
        db.delete_results(project_id)  # old results would point at deleted requirements

    now = utcnow()
    docs = [
        {
            "_id": new_id("requirement"),
            "project_id": project_id,
            "description": text,
            "status": "pending",
            "created_at": now,
        }
        for text in descriptions
    ]
    db.insert_requirements(docs)
    db.update_project(project_id, {"status": "requirements_added"})
    return get_requirements(project_id)


def get_requirements(project_id: str) -> dict:
    get_project_or_404(project_id)
    items = db.list_requirements(project_id)
    return {"project_id": project_id, "count": len(items), "requirements": items}
