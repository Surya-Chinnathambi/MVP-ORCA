import enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.clients import Project
    from app.models.evidence import EvidenceRequest


class ScopeItemKind(str, enum.Enum):
    asset = "asset"
    business_unit = "business_unit"
    inclusion = "inclusion"
    exclusion = "exclusion"
    assumption = "assumption"
    constraint = "constraint"


class FrameworkKey(str, enum.Enum):
    dpdp_act = "dpdp_act"
    owasp_asvs = "owasp_asvs"
    owasp_wstg = "owasp_wstg"
    owasp_api10 = "owasp_api10"
    ptes = "ptes"


class ScopeItem(TimestampMixin, Base):
    __tablename__ = "scope_items"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        Enum(ScopeItemKind, name="scope_item_kind_enum"), nullable=False
    )
    value: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="scope_items")


class Framework(TimestampMixin, Base):
    __tablename__ = "frameworks"

    key: Mapped[str] = mapped_column(
        Enum(FrameworkKey, name="framework_key_enum"), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="framework"
    )


class Requirement(TimestampMixin, Base):
    __tablename__ = "requirements"

    framework_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("frameworks.id"), nullable=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    ref_code: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_expectation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    framework: Mapped[Optional["Framework"]] = relationship(back_populates="requirements")
    project: Mapped["Project"] = relationship(back_populates="requirements")
    evidence_requests: Mapped[list["EvidenceRequest"]] = relationship(
        back_populates="requirement"
    )
