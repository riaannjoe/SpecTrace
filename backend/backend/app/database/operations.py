"""All MongoDB reads/writes live here. Services call these functions; routes never touch the DB.

MongoDB stores the id in "_id". We rename it to "id" on the way out so React sees a normal field.
"""
from typing import Optional

from app.database.connection import get_db


def _out(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


# ---------- projects ----------
def insert_project(doc: dict) -> None:
    get_db().projects.insert_one(doc)


def get_project(project_id: str) -> Optional[dict]:
    return _out(get_db().projects.find_one({"_id": project_id}))


def list_projects() -> list[dict]:
    return [_out(d) for d in get_db().projects.find().sort("created_at", -1)]


def update_project(project_id: str, fields: dict) -> None:
    get_db().projects.update_one({"_id": project_id}, {"$set": fields})


# ---------- requirements ----------
def insert_requirements(docs: list[dict]) -> None:
    if docs:
        get_db().requirements.insert_many(docs)


def list_requirements(project_id: str) -> list[dict]:
    cursor = get_db().requirements.find({"project_id": project_id}).sort("created_at", 1)
    return [_out(d) for d in cursor]


def delete_requirements(project_id: str) -> None:
    get_db().requirements.delete_many({"project_id": project_id})


def set_requirement_status(requirement_id: str, status: str) -> None:
    get_db().requirements.update_one({"_id": requirement_id}, {"$set": {"status": status}})


# ---------- analysis results ----------
def replace_results(project_id: str, docs: list[dict]) -> None:
    """Re-running analysis replaces the old results for that project."""
    db = get_db()
    db.analysis_results.delete_many({"project_id": project_id})
    if docs:
        db.analysis_results.insert_many(docs)


def delete_results(project_id: str) -> None:
    get_db().analysis_results.delete_many({"project_id": project_id})


def list_results(project_id: str) -> list[dict]:
    cursor = get_db().analysis_results.find({"project_id": project_id}).sort("order", 1)
    return [_out(d) for d in cursor]
