from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ScopeItemCreate(BaseModel):
    kind: str          # asset | business_unit | inclusion | exclusion | assumption | constraint
    value: str
    reason: Optional[str] = None   # reason for the approval request


class ScopeItemUpdate(BaseModel):
    value: Optional[str] = None
    reason: Optional[str] = None


class ScopeItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: str
    value: str
    approved: bool
    created_at: datetime
    updated_at: datetime
