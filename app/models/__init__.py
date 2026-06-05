"""Import all models so SQLAlchemy mapper and Alembic can discover them."""

from app.models.users import User, Role, Permission, RoleName, ScopeLevel  # noqa: F401
from app.models.clients import Client, Project, ServiceType  # noqa: F401
from app.models.scope import ScopeItem, Framework, Requirement  # noqa: F401
from app.models.scope import ScopeItemKind, FrameworkKey  # noqa: F401
from app.models.evidence import EvidenceRequest, EvidenceItem  # noqa: F401
from app.models.evidence import EvidenceRequestStatus, ReviewerStatus  # noqa: F401
from app.models.tasks import Task, Finding  # noqa: F401
from app.models.tasks import TaskKind, FindingSeverity, FindingStatus, FindingSource  # noqa: F401
from app.models.workflow import ApprovalRequest, AuditTrailEvent, ApprovalStatus  # noqa: F401
from app.models.delivery import AdvisoryClinic, Deliverable, RemediationAction  # noqa: F401
from app.models.delivery import DeliverableKind  # noqa: F401

__all__ = [
    "User", "Role", "Permission", "RoleName", "ScopeLevel",
    "Client", "Project", "ServiceType",
    "ScopeItem", "Framework", "Requirement", "ScopeItemKind", "FrameworkKey",
    "EvidenceRequest", "EvidenceItem", "EvidenceRequestStatus", "ReviewerStatus",
    "Task", "Finding", "TaskKind", "FindingSeverity", "FindingStatus", "FindingSource",
    "ApprovalRequest", "AuditTrailEvent", "ApprovalStatus",
    "AdvisoryClinic", "Deliverable", "RemediationAction", "DeliverableKind",
]
