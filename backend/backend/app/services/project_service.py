from pathlib import Path
from typing import Optional

from app.config import settings
from app.database import operations as db
from app.utils import file_handler
from app.utils.errors import AppError
from app.utils.ids import new_id, utcnow


def get_project_or_404(project_id: str) -> dict:
    project = db.get_project(project_id)
    if project is None:
        raise AppError(404, f"Project '{project_id}' not found.")
    return project


def create_project_from_upload(upload, project_name: Optional[str]) -> dict:
    """Validate -> save -> safely extract -> store metadata. Cleans up the folder if anything fails."""
    filename = Path(upload.filename or "").name[:200]
    if not filename.lower().endswith(".zip"):
        raise AppError(400, "Only .zip files are accepted.")

    project_id = new_id("project")
    project_dir = settings.UPLOAD_DIR / project_id   # every project gets its own isolated folder
    source_dir = project_dir / "source"
    zip_path = project_dir / "upload.zip"

    try:
        project_dir.mkdir(parents=True)
        file_handler.save_upload_with_limit(upload, zip_path, settings.MAX_UPLOAD_BYTES)
        extraction = file_handler.safe_extract_zip(zip_path, source_dir)
        if not extraction.python_files:
            raise AppError(400, "No Python (.py) files found in the ZIP. SpecTrace currently supports Python projects only.")

        doc = {
            "_id": project_id,
            "project_name": (project_name or "").strip()[:100] or Path(filename).stem,
            "filename": filename,
            "language": "Python",
            "status": "uploaded",
            "python_file_count": len(extraction.python_files),
            "total_file_count": extraction.extracted_count,
            "storage_path": str(source_dir),   # internal only - never returned by the API
            "created_at": utcnow(),
            "last_analyzed_at": None,
        }
        db.insert_project(doc)
    except Exception:
        file_handler.remove_dir(project_dir)
        raise
    finally:
        zip_path.unlink(missing_ok=True)  # keep only extracted files

    return db.get_project(project_id)


def list_projects() -> dict:
    projects = db.list_projects()
    return {"count": len(projects), "projects": projects}
