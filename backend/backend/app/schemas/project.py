from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProjectOut(BaseModel):
    id: str
    project_name: str
    filename: str
    language: str
    status: str  # uploaded | requirements_added | analyzing | analyzed | analysis_failed
    python_file_count: int
    total_file_count: int
    created_at: datetime
    last_analyzed_at: Optional[datetime] = None


class ProjectListOut(BaseModel):
    count: int
    projects: list[ProjectOut]
