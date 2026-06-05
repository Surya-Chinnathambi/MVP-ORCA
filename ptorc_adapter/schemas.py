"""Pydantic schemas for the PT-Orc export contract.

These are the four files 12_report_pack.sh must produce.
Both sides (PT-Orc and this adapter) depend on this contract — treat as frozen.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator

_VALID_SEVERITIES = {"info", "low", "medium", "high", "critical"}


class WindowSchema(BaseModel):
    start: str = ""
    end: str = ""


class ScopeImport(BaseModel):
    project_ref: str
    engagement_profile: str
    testing_depth: str
    auth_level: str
    targets: List[str]
    rules_of_engagement: str = ""
    window: Dict[str, Any] = {}


class EvidenceRecord(BaseModel):
    id: str
    phase: str
    source_file: str
    sha256: str
    summary: str = ""


class FindingRecord(BaseModel):
    id: str
    title: str
    severity: str
    phase: str
    evidence_ids: List[str] = []
    description: str = ""
    recommendation: str = ""

    @field_validator("severity")
    @classmethod
    def _check_severity(cls, v: str) -> str:
        if v not in _VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(_VALID_SEVERITIES)}, got '{v}'")
        return v


class ReportBundle(BaseModel):
    project_ref: str
    profile: str
    retest_status: str = "n/a"
    residual_risk: str = ""
    counts: Dict[str, Any] = {}
