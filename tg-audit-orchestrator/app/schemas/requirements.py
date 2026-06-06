from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    framework_id: Optional[str]
    ref_code: str
    text: str
    evidence_expectation: Optional[str]
    category: str
    created_at: datetime
    updated_at: datetime
