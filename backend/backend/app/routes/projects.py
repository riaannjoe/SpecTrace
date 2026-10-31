from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.schemas.project import ProjectListOut, ProjectOut
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/upload", response_model=ProjectOut, status_code=201)
def upload_project(file: UploadFile = File(...), project_name: Optional[str] = Form(None)):
    """Upload a .zip Python project. Returns the project (including its `id`)."""
    return project_service.create_project_from_upload(file, project_name)


@router.get("", response_model=ProjectListOut)
def list_projects():
    return project_service.list_projects()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str):
    return project_service.get_project_or_404(project_id)
