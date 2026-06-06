"""Canonical pack schema — Full Spec §7.1.

Every pack JSON must conform to this Pydantic v2 model before it can be loaded.
The loader raises a clear error naming any missing required field.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class IntakeQuestion(BaseModel):
    id: str
    text: str


class ScopeTemplate(BaseModel):
    kind: str
    prompt: str


class PackRequirement(BaseModel):
    ref_code: str
    category: str
    text: str
    evidence_expectation: Optional[str] = None


class EvidenceRequestTemplate(BaseModel):
    requirement_ref: str
    title: str
    description: Optional[str] = None


class TaskTemplate(BaseModel):
    kind: str
    title: str


class FindingTemplate(BaseModel):
    category: str
    title_pattern: str


class SeverityModel(BaseModel):
    critical: Optional[str] = None
    high: Optional[str] = None
    medium: Optional[str] = None
    low: Optional[str] = None
    informational: Optional[str] = None


class ReviewGate(BaseModel):
    id: str
    label: str
    required_role: Optional[str] = None


class AdvisoryClinicTemplate(BaseModel):
    category: str
    title: str
    guidance: Optional[str] = None


class RoleResponsibility(BaseModel):
    role: str
    responsibilities: List[str] = []


class AssessmentProcedure(BaseModel):
    ref_code: str
    title: str
    steps: List[str] = []


class CanonicalPack(BaseModel):
    """Full Spec §7.1 canonical pack schema."""

    # Pack metadata
    key: str
    title: str
    version: str
    lifecycle: str

    # Service description
    service_description: str

    # Frameworks referenced
    frameworks: List[str] = []

    # Intake
    intake_questions: List[IntakeQuestion] = []
    scope_template: List[ScopeTemplate] = []

    # Roles
    role_responsibility_model: List[RoleResponsibility] = []

    # Core work
    requirements: List[PackRequirement]
    evidence_requests: List[EvidenceRequestTemplate] = []
    assessment_procedures: List[AssessmentProcedure] = []
    task_templates: List[TaskTemplate] = []
    finding_templates: List[FindingTemplate] = []

    # Severity and quality
    severity_model: Optional[SeverityModel] = None
    review_gates: List[ReviewGate] = []

    # Approvals and reports
    approval_triggers: List[str] = []
    report_templates: List[str] = []

    # Advisory clinics
    advisory_clinic_templates: List[AdvisoryClinicTemplate] = []

    # QA
    qa_rules: List[str] = Field(..., min_length=1)
