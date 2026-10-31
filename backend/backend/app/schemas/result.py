from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["implemented", "partially_implemented", "missing", "not_verified"]
TestStatus = Literal["passed", "failed", "not_run"]


class Evidence(BaseModel):
    file: str
    line: Optional[int] = Field(default=None, ge=1)
    description: str = ""


class ResultOut(BaseModel):
    id: str
    project_id: str
    requirement_id: str
    requirement_description: str
    status: Status
    evidence: list[Evidence]
    file_name: Optional[str] = None      # first evidence file (handy for table display)
    line_number: Optional[int] = None    # first evidence line
    test_status: TestStatus
    explanation: str
    engine: str                          # which engine produced this result
    is_mock: bool                        # True => placeholder output, NOT a real verification
    analyzed_at: datetime


class SummaryOut(BaseModel):
    total: int = 0
    implemented: int = 0
    partially_implemented: int = 0
    missing: int = 0
    not_verified: int = 0


class ResultsOut(BaseModel):
    """Returned by both POST /analyze and GET /results, so React handles one shape."""
    project_id: str
    project_name: str
    project_status: str
    analyzed_at: Optional[datetime] = None
    engine: Optional[str] = None
    is_mock: bool = False
    summary: SummaryOut
    results: list[ResultOut]
