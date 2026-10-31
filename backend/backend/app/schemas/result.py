from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["implemented", "partially_implemented", "missing", "not_verified"]
TestStatus = Literal["passed", "failed", "not_run"]
RiskLevel = Literal["low", "medium", "high", "critical"]
AnalysisMode = Literal["hybrid", "static_fallback", "mock"]


class Evidence(BaseModel):
    file: str
    line: Optional[int] = Field(default=None, ge=1)
    line_end: Optional[int] = Field(default=None, ge=1)
    function: Optional[str] = None
    snippet: Optional[str] = None
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
    # Additive fields for SpecTrace AI Engine
    confidence: Optional[float] = None
    risk: Optional[RiskLevel] = None
    risk_reason: Optional[str] = None
    test_covered: Optional[bool] = None
    test_evidence: list[Evidence] = Field(default_factory=list)
    analysis_mode: Optional[AnalysisMode] = None


class SummaryOut(BaseModel):
    total: int = 0
    implemented: int = 0
    partially_implemented: int = 0
    missing: int = 0
    not_verified: int = 0
    critical_risks: int = 0
    high_risks: int = 0
    medium_risks: int = 0
    low_risks: int = 0
    tests_covered: int = 0


class ResultsOut(BaseModel):
    """Returned by both POST /analyze and GET /results, so React handles one shape."""
    project_id: str
    project_name: str
    project_status: str
    analyzed_at: Optional[datetime] = None
    engine: Optional[str] = None
    analysis_mode: Optional[AnalysisMode] = None
    is_mock: bool = False
    summary: SummaryOut
    results: list[ResultOut]
