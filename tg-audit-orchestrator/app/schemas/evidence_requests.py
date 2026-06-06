from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EvidenceRequestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    requirement_id: Optional[str] = None
    owner_id: Optional[str] = None
    due_date: Optional[date] = None


class EvidenceRequestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None      # open | received (waive via /waive endpoint)
    owner_id: Optional[str] = None
    due_date: Optional[date] = None


class WaiveRequest(BaseModel):
    reason: str


class EvidenceRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    requirement_id: Optional[str]
    title: str
    description: Optional[str]
    status: str
    owner_id: Optional[str]
    due_date: Optional[date]
    created_at: datetime
    updated_at: datetime
