from fastapi import APIRouter

from app.schemas.result import ResultsOut
from app.services import analysis_service

router = APIRouter(prefix="/projects", tags=["Analysis"])


# Plain `def` (not async) so FastAPI runs this in a worker thread and a slow analysis
# doesn't block other requests.
@router.post("/{project_id}/analyze", response_model=ResultsOut)
def analyze_project(project_id: str):
    return analysis_service.run_analysis(project_id)


@router.get("/{project_id}/results", response_model=ResultsOut)
def get_results(project_id: str):
    return analysis_service.get_results(project_id)
