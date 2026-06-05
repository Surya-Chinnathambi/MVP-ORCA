"""Schemas for EvidenceItem endpoints."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class EvidenceItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    evidence_request_id: Optional[str]
    source_file: str
    sha256: str
    mime: str
    classification: Optional[str]
    sensitivity: Optional[str]
    reviewer_status: str
    extracted_text: Optional[str]
    item_metadata: Optional[Any]
    created_at: datetime
    updated_at: datetime


class EvidenceItemLink(BaseModel):
    """Link an evidence item to an evidence request (and implicitly its requirement)."""
    evidence_request_id: str


class ReviewDecide(BaseModel):
    accepted: bool
    reason: Optional[str] = None
