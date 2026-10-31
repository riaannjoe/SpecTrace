from fastapi import APIRouter

from app.schemas.requirement import RequirementsCreate, RequirementsOut
from app.services import requirement_service

router = APIRouter(prefix="/projects", tags=["Requirements"])


@router.post("/{project_id}/requirements", response_model=RequirementsOut, status_code=201)
def add_requirements(project_id: str, body: RequirementsCreate):
    return requirement_service.add_requirements(project_id, body.requirements, body.replace)


@router.get("/{project_id}/requirements", response_model=RequirementsOut)
def get_requirements(project_id: str):
    return requirement_service.get_requirements(project_id)
