from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ApprovalDecide(BaseModel):
    approved: bool
    reason: Optional[str] = None


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    target_type: str
    target_id: str
    change_before: Optional[Any]
    change_after: Optional[Any]
    reason: str
    requested_by: Optional[str]
    approver_role: str
    status: str
    decided_by: Optional[str]
    decided_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
