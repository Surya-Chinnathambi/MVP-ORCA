from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

VALID_STATUSES = {"open", "in_progress", "blocked", "done", "cancelled"}


class TaskCreate(BaseModel):
    kind: str
    title: str
    assignee_id: Optional[str] = None
    due_date: Optional[date] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[date] = None
    title: Optional[str] = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: str
    title: str
    status: str
    assignee_id: Optional[str]
    due_date: Optional[date]
    created_at: datetime
    updated_at: datetime
