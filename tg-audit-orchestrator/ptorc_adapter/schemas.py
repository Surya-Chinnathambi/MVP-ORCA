"""Pydantic schemas for the PT-Orc export contract v2.

v2 additions:
- ScopeImport: engagement_profile validated against known profiles
- FindingRecord: retest_status, residual_risk, pack_scoped_data (offensive narrative quarantine)
- EvidenceRecord: phase now accepts new phases 08_app_api, 09_ai_llm
- ReportBundle: retest_status, residual_risk (already present, now validated)
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator

_VALID_SEVERITIES = {"info", "low", "medium", "high", "critical"}

_VALID_PROFILES = {
    "external", "internal", "web", "api", "ai_llm", "cloud", "ad", "hybrid", "retest",
}

_VALID_RETEST_STATUSES = {"n/a", "pending", "in_progress", "passed", "failed", "partial"}

# Phases match PT-Orc script prefixes per vapt.md Step 4
# v1: 01_dns, 02_ip, 03_network, 04_tls, 05_web, 06_wordpress, 07_service
# v2: 08_app_api, 09_ai_llm, 12_report
_VALID_PHASES = {
    "01_dns", "02_ip", "03_network", "04_tls", "05_web",
    "06_wordpress", "07_service",
    "08_app_api", "09_ai_llm", "12_report",
}

# Offensive narrative keys that must never be promoted to core models.
# Stored in pack_scoped_data on the Finding, never in title/description/recommendation.
_OFFENSIVE_NARRATIVE_KEYS = frozenset({
    "attack_chain", "payload_details", "c2_config", "opsec_notes",
    "exploit_code", "killchain_step", "lateral_path",
})


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

    @field_validator("engagement_profile")
    @classmethod
    def _check_profile(cls, v: str) -> str:
        if v not in _VALID_PROFILES:
            raise ValueError(
                f"engagement_profile must be one of {sorted(_VALID_PROFILES)}, got '{v}'"
            )
        return v


class EvidenceRecord(BaseModel):
    id: str
    phase: str
    source_file: str
    sha256: str
    summary: str = ""

    @field_validator("phase")
    @classmethod
    def _check_phase(cls, v: str) -> str:
        if v not in _VALID_PHASES:
            raise ValueError(
                f"phase must be one of {sorted(_VALID_PHASES)}, got '{v}'"
            )
        return v


class FindingRecord(BaseModel):
    id: str
    title: str
    severity: str
    phase: str
    evidence_ids: List[str] = []
    description: str = ""
    recommendation: str = ""
    retest_status: str = "n/a"
    residual_risk: str = ""
    # Offensive narrative — quarantined; stored in pack_scoped_data only
    pack_scoped_data: Dict[str, Any] = {}

    @field_validator("severity")
    @classmethod
    def _check_severity(cls, v: str) -> str:
        if v not in _VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(_VALID_SEVERITIES)}, got '{v}'")
        return v

    @field_validator("phase")
    @classmethod
    def _check_phase(cls, v: str) -> str:
        if v not in _VALID_PHASES:
            raise ValueError(
                f"phase must be one of {sorted(_VALID_PHASES)}, got '{v}'"
            )
        return v

    @field_validator("retest_status")
    @classmethod
    def _check_retest(cls, v: str) -> str:
        if v not in _VALID_RETEST_STATUSES:
            raise ValueError(
                f"retest_status must be one of {sorted(_VALID_RETEST_STATUSES)}, got '{v}'"
            )
        return v

    def extract_offensive_narrative(self) -> Dict[str, Any]:
        """Return only the known offensive narrative keys from pack_scoped_data."""
        return {k: v for k, v in self.pack_scoped_data.items()
                if k in _OFFENSIVE_NARRATIVE_KEYS}


class ReportBundle(BaseModel):
    project_ref: str
    profile: str
    retest_status: str = "n/a"
    residual_risk: str = ""
    counts: Dict[str, Any] = {}

    @field_validator("profile")
    @classmethod
    def _check_profile(cls, v: str) -> str:
        if v not in _VALID_PROFILES:
            raise ValueError(
                f"profile must be one of {sorted(_VALID_PROFILES)}, got '{v}'"
            )
        return v

    @field_validator("retest_status")
    @classmethod
    def _check_retest(cls, v: str) -> str:
        if v not in _VALID_RETEST_STATUSES:
            raise ValueError(
                f"retest_status must be one of {sorted(_VALID_RETEST_STATUSES)}, got '{v}'"
            )
        return v
