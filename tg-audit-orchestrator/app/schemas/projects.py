from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    client_id: str
    service_type: str          # "dpdp" | "vapt"
    owner_id: Optional[str] = None
    scope_summary: Optional[str] = None
    timeline: Optional[Any] = None
    pack_id: Optional[str] = None
    framework_ids: Optional[Any] = None


class ProjectUpdate(BaseModel):
    owner_id: Optional[str] = None
    status: Optional[str] = None
    scope_summary: Optional[str] = None
    timeline: Optional[Any] = None
    pack_id: Optional[str] = None
    framework_ids: Optional[Any] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    service_type: str
    owner_id: Optional[str]
    status: str
    scope_summary: Optional[str]
    timeline: Optional[Any]
    pack_id: Optional[str]
    framework_ids: Optional[Any]
    gates: Optional[Any]
    created_at: datetime
    updated_at: datetime
