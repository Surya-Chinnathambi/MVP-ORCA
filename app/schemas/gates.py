"""Schemas for gate tracker and QA report."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class GateStatus(BaseModel):
    gates: Dict[str, bool]
    project_id: str


class QAIssueOut(BaseModel):
    rule: str
    severity: str
    message: str
    item_ids: List[str]


class QAReportOut(BaseModel):
    project_id: str
    pack_id: Optional[str]
    rules_run: List[str]
    passed: bool
    issues: List[QAIssueOut]
