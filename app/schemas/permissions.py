from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PermissionCreate(BaseModel):
    user_id: str
    role_id: str
    scope_level: str = "project"
    scope_id: Optional[str] = None


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    role_id: str
    scope_level: str
    scope_id: Optional[str]
    created_at: datetime
