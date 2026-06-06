from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ClientCreate(BaseModel):
    entity_name: str
    sector: Optional[str] = None
    contacts: Optional[Any] = None
    business_units: Optional[Any] = None
    reusable_context: Optional[Any] = None
    regulatory_context: Optional[str] = None


class ClientUpdate(BaseModel):
    entity_name: Optional[str] = None
    sector: Optional[str] = None
    contacts: Optional[Any] = None
    business_units: Optional[Any] = None
    reusable_context: Optional[Any] = None
    regulatory_context: Optional[str] = None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_name: str
    sector: Optional[str]
    contacts: Optional[Any]
    business_units: Optional[Any]
    reusable_context: Optional[Any]
    regulatory_context: Optional[str]
    created_at: datetime
    updated_at: datetime
