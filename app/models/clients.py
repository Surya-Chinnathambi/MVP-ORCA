import enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.scope import ScopeItem, Requirement
    from app.models.evidence import EvidenceRequest, EvidenceItem
    from app.models.tasks import Task, Finding
    from app.models.workflow import ApprovalRequest, AuditTrailEvent
    from app.models.delivery import AdvisoryClinic, Deliverable, RemediationAction
    from app.models.users import User
    from app.models.organization import Organization
    from app.models.engagement import EngagementState, EngagementObjective
    from app.models.methodology import MethodologyPack


class ServiceType(str, enum.Enum):
    dpdp = "dpdp"
    vapt = "vapt"


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contacts: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    business_units: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    reusable_context: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    regulatory_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organization_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=True
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="client")
    organization: Mapped[Optional["Organization"]] = relationship(back_populates="clients")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    client_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("clients.id"), nullable=False
    )
    service_type: Mapped[str] = mapped_column(
        Enum(ServiceType, name="service_type_enum"), nullable=False
    )
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="setup", nullable=False)
    scope_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeline: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    pack_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("methodology_packs.id"), nullable=True
    )
    framework_ids: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    gates: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="projects")
    owner: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[owner_id]
    )
    scope_items: Mapped[list["ScopeItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    evidence_requests: Mapped[list["EvidenceRequest"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditTrailEvent"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    advisory_clinics: Mapped[list["AdvisoryClinic"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    deliverables: Mapped[list["Deliverable"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    remediation_actions: Mapped[list["RemediationAction"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    engagement_state: Mapped[Optional["EngagementState"]] = relationship(
        back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    objectives: Mapped[list["EngagementObjective"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    methodology_pack: Mapped[Optional["MethodologyPack"]] = relationship(
        "MethodologyPack", back_populates="projects", foreign_keys=[pack_id]
    )
