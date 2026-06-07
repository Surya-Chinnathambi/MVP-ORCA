"""Schemas for the Findings Register."""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.tasks import FindingSeverity, FindingSource, FindingStatus

_VALID_SEVERITIES = {s.value for s in FindingSeverity}
_VALID_STATUSES = {s.value for s in FindingStatus}
_VALID_SOURCES = {s.value for s in FindingSource}


class FindingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str
    requirement_id: Optional[str] = None
    evidence_item_ids: Optional[List[str]] = None
    source: str = FindingSource.manual.value
    owner_id: Optional[str] = None

    @field_validator("severity")
    @classmethod
    def _check_severity(cls, v: str) -> str:
        if v not in _VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(_VALID_SEVERITIES)}")
        return v

    @field_validator("source")
    @classmethod
    def _check_source(cls, v: str) -> str:
        if v not in _VALID_SOURCES:
            raise ValueError(f"source must be one of {sorted(_VALID_SOURCES)}")
        return v


class FindingUpdate(BaseModel):
    """Non-gated fields only — title, description, owner, evidence links."""
    title: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[str] = None
    evidence_item_ids: Optional[List[str]] = None


class ChangeSeverity(BaseModel):
    severity: str
    reason: str

    @field_validator("severity")
    @classmethod
    def _check(cls, v: str) -> str:
        if v not in _VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(_VALID_SEVERITIES)}")
        return v


class ChangeStatus(BaseModel):
    status: str
    reason: str

    @field_validator("status")
    @classmethod
    def _check(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    requirement_id: Optional[str]
    title: str
    description: Optional[str]
    severity: str
    status: str
    source: str
    owner_id: Optional[str]
    evidence_item_ids: Optional[Any]
    created_at: datetime
    updated_at: datetime
