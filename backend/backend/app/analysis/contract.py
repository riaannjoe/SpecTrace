"""
THE ANALYSIS ENGINE CONTRACT
============================
Your teammate's engine must expose ONE function:

    def analyze(request: dict) -> dict

INPUT  (a dict shaped like EngineRequest):
    {
      "project_id": "project_ab12cd34ef56",
      "project_path": "/abs/path/to/uploads/project_ab12.../source",
      "python_files": ["auth.py", "app/models.py"],           # relative to project_path
      "requirements": [{"id": "requirement_x1", "description": "Users must be able to log in"}]
    }

OUTPUT (a dict shaped like EngineResponse):
    {
      "engine_name": "SpecTrace AST Engine v1",
      "is_mock": false,
      "results": [
        {
          "requirement_id": "requirement_x1",
          "status": "implemented",            # implemented | partially_implemented | missing | not_verified
          "evidence": [{"file": "auth.py", "line": 25, "description": "login() function found"}],
          "test_status": "not_run",           # passed | failed | not_run
          "explanation": "Found login() that checks credentials."
        }
      ]
    }

The backend validates this output. Unknown requirement_ids => rejected. Requirements the engine
forgets to answer are stored as "not_verified". The engine must only READ files, never run them.
"""
from pydantic import BaseModel, Field

from app.schemas.result import Evidence, Status, TestStatus


class EngineRequirement(BaseModel):
    id: str
    description: str


class EngineRequest(BaseModel):
    project_id: str
    project_path: str
    python_files: list[str]
    requirements: list[EngineRequirement]


class EngineResult(BaseModel):
    requirement_id: str
    status: Status
    evidence: list[Evidence] = Field(default_factory=list)
    test_status: TestStatus = "not_run"
    explanation: str = ""


class EngineResponse(BaseModel):
    engine_name: str
    is_mock: bool = False
    results: list[EngineResult]
