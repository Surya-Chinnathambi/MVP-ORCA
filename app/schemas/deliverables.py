"""Pydantic schemas for the Deliverables API."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DeliverableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: str
    format: Optional[str] = None
    file_path: Optional[str] = None
    generated_at: Optional[datetime] = None
    version: int
    created_at: datetime


class ReleaseRequest(BaseModel):
    reason: str
