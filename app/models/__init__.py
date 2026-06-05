"""Import all models so SQLAlchemy mapper and Alembic can discover them."""

from app.models.organization import Organization  # noqa: F401 — before clients (FK target)
from app.models.users import User, Role, Permission, RoleName, ScopeLevel  # noqa: F401
from app.models.clients import Client, Project, ServiceType  # noqa: F401
from app.models.scope import ScopeItem, Framework, Requirement  # noqa: F401
from app.models.scope import ScopeItemKind, FrameworkKey  # noqa: F401
from app.models.evidence import EvidenceRequest, EvidenceItem  # noqa: F401
from app.models.evidence import EvidenceRequestStatus, ReviewerStatus  # noqa: F401
from app.models.evidence import EvidenceLifecycleEvent, EvidenceLifecycleState  # noqa: F401
from app.models.tasks import Task, Finding  # noqa: F401
from app.models.tasks import TaskKind, FindingSeverity, FindingStatus, FindingSource  # noqa: F401
from app.models.workflow import ApprovalRequest, AuditTrailEvent, ApprovalStatus  # noqa: F401
from app.models.delivery import AdvisoryClinic, Deliverable, RemediationAction  # noqa: F401
from app.models.delivery import DeliverableKind  # noqa: F401
from app.models.engagement import EngagementState, EngagementObjective  # noqa: F401
from app.models.methodology import MethodologyPack, PackLifecycle  # noqa: F401
from app.models.workmode import WorkMode, UserLastContext, WorkModeName  # noqa: F401
from app.models.notification import Notification, NotificationChannel, NotificationEventType  # noqa: F401
from app.models.agent import AgentDraft, AgentType, DraftStatus  # noqa: F401

# Activate auto-create listener: fires after every Project insert
from app.engagementcore.state import register_listeners as _rl
_rl()

__all__ = [
    "Organization",
    "User", "Role", "Permission", "RoleName", "ScopeLevel",
    "Client", "Project", "ServiceType",
    "ScopeItem", "Framework", "Requirement", "ScopeItemKind", "FrameworkKey",
    "EvidenceRequest", "EvidenceItem", "EvidenceRequestStatus", "ReviewerStatus",
    "EvidenceLifecycleEvent", "EvidenceLifecycleState",
    "Task", "Finding", "TaskKind", "FindingSeverity", "FindingStatus", "FindingSource",
    "ApprovalRequest", "AuditTrailEvent", "ApprovalStatus",
    "AdvisoryClinic", "Deliverable", "RemediationAction", "DeliverableKind",
    "EngagementState", "EngagementObjective",
    "MethodologyPack", "PackLifecycle",
    "WorkMode", "UserLastContext", "WorkModeName",
    "Notification", "NotificationChannel", "NotificationEventType",
    "AgentDraft", "AgentType", "DraftStatus",
]
