from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RequirementsCreate(BaseModel):
    """Body of POST /projects/{id}/requirements"""
    requirements: list[str] = Field(..., min_length=1, max_length=50)
    replace: bool = False  # True = delete the project's old requirements (and old results) first

    @field_validator("requirements")
    @classmethod
    def clean_requirements(cls, items: list[str]) -> list[str]:
        cleaned = []
        for item in items:
            text = item.strip()
            if not text:
                raise ValueError("Requirements must not be empty")
            if len(text) > 500:
                raise ValueError("Each requirement must be 500 characters or fewer")
            cleaned.append(text)
        return cleaned


class RequirementOut(BaseModel):
    id: str
    project_id: str
    description: str
    status: str  # pending until analysed, then implemented | partially_implemented | missing | not_verified
    created_at: datetime


class RequirementsOut(BaseModel):
    project_id: str
    count: int
    requirements: list[RequirementOut]
