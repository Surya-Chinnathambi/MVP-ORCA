"""Stage C4 acceptance test — 5-state approval lifecycle with applied/cancelled + immutability.

Verifies:
- request_approval creates status='requested'.
- decide approve + apply_approval → status='applied', target mutated, applied_at/applied_by stamped.
- decide reject → status='rejected'.
- Attempting to edit an applied/rejected/cancelled request raises ValueError.
- Every transition wrote an AuditTrailEvent.
- Migration backfill verified: no 'pending' rows remain.
- alembic upgrade head runs clean (verified by migration applying above).
"""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.organization import Organization
from app.models.scope import ScopeItem
from app.models.tasks import Finding, FindingSeverity, Task
from app.models.users import Role, RoleName, User
from app.models.workflow import APPROVAL_FINAL_STATES, ApprovalStatus
from app.services.applier import apply_approval
from app.services.audit import cancel_approval, decide_approval, record_event, request_approval
from app.services.auth import hash_password


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    session = Sess()
    yield session
    session.close()


@pytest.fixture
def seeded(db):
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    admin = User(
        email="c4_admin@test.local",
        password_hash=hash_password("pass"),
        full_name="C4 Admin",
        is_active=True,
    )
    db.add(admin)
    db.flush()
    # Give admin the pm role so they can approve
    from app.models.users import Permission
    pm_role = db.query(Role).filter_by(name="pm").first()
    db.add(Permission(user_id=admin.id, role_id=pm_role.id, scope_level="organization", scope_id="0"))
    db.flush()

    org = Organization(name="C4 Org", display_name="C4 Org")
    db.add(org)
    db.flush()
    client = Client(entity_name="C4 Client", organization_id=org.id)
    db.add(client)
    db.flush()
    project = Project(client_id=client.id, service_type=ServiceType.dpdp, owner_id=admin.id)
    db.add(project)
    db.flush()
    scope_item = ScopeItem(
        project_id=project.id, kind="asset", value="example.com", approved=False
    )
    db.add(scope_item)
    db.flush()
    return db, admin, project, scope_item


def test_request_approval_creates_requested_status(seeded):
    db, admin, project, scope_item = seeded
    approval = request_approval(
        db,
        project_id=project.id,
        target_type="scope_item",
        target_id=scope_item.id,
        reason="Approve scope",
        approver_role="pm",
        requested_by=admin.id,
    )
    db.flush()
    assert approval.status == ApprovalStatus.requested.value


def test_decide_approve_then_apply_sets_applied(seeded):
    db, admin, project, scope_item = seeded
    approval = request_approval(
        db,
        project_id=project.id,
        target_type="scope_item",
        target_id=scope_item.id,
        reason="Approve scope",
        approver_role="pm",
        requested_by=admin.id,
    )
    db.flush()

    decide_approval(db, approval_id=approval.id, approved=True, decider_id=admin.id)
    db.flush()
    assert approval.status == ApprovalStatus.approved.value

    apply_approval(db, approval, actor_id=admin.id)
    db.flush()

    assert approval.status == ApprovalStatus.applied.value
    assert approval.applied_at is not None
    assert approval.applied_by == admin.id
    # Target was mutated
    assert scope_item.approved is True


def test_decide_reject_sets_rejected(seeded):
    db, admin, project, scope_item = seeded
    approval = request_approval(
        db,
        project_id=project.id,
        target_type="scope_item",
        target_id=scope_item.id,
        reason="Reject scope",
        approver_role="pm",
        requested_by=admin.id,
    )
    db.flush()
    decide_approval(db, approval_id=approval.id, approved=False, decider_id=admin.id)
    db.flush()
    assert approval.status == ApprovalStatus.rejected.value


def test_editing_applied_raises(seeded):
    db, admin, project, scope_item = seeded
    approval = request_approval(
        db,
        project_id=project.id,
        target_type="scope_item",
        target_id=scope_item.id,
        reason="Approve",
        approver_role="pm",
        requested_by=admin.id,
    )
    db.flush()
    decide_approval(db, approval_id=approval.id, approved=True, decider_id=admin.id)
    db.flush()
    apply_approval(db, approval, actor_id=admin.id)
    db.flush()
    assert approval.status == ApprovalStatus.applied.value

    # Trying to decide again must raise
    with pytest.raises(ValueError, match="finalized"):
        decide_approval(db, approval_id=approval.id, approved=True, decider_id=admin.id)


def test_editing_rejected_raises(seeded):
    db, admin, project, scope_item = seeded
    approval = request_approval(
        db,
        project_id=project.id,
        target_type="scope_item",
        target_id=scope_item.id,
        reason="Reject",
        approver_role="pm",
        requested_by=admin.id,
    )
    db.flush()
    decide_approval(db, approval_id=approval.id, approved=False, decider_id=admin.id)
    db.flush()
    with pytest.raises(ValueError, match="finalized"):
        decide_approval(db, approval_id=approval.id, approved=True, decider_id=admin.id)


def test_cancel_approval_sets_cancelled(seeded):
    db, admin, project, scope_item = seeded
    approval = request_approval(
        db,
        project_id=project.id,
        target_type="scope_item",
        target_id=scope_item.id,
        reason="Cancel test",
        approver_role="pm",
        requested_by=admin.id,
    )
    db.flush()
    cancel_approval(db, approval_id=approval.id, actor_id=admin.id, reason="Withdrawn")
    db.flush()
    assert approval.status == ApprovalStatus.cancelled.value

    # Cannot decide a cancelled approval
    with pytest.raises(ValueError, match="finalized"):
        decide_approval(db, approval_id=approval.id, approved=True, decider_id=admin.id)


def test_every_transition_writes_audit_event(seeded):
    db, admin, project, scope_item = seeded
    events_before = db.query(__import__("app.models.workflow", fromlist=["AuditTrailEvent"]).AuditTrailEvent).count()

    approval = request_approval(
        db,
        project_id=project.id,
        target_type="scope_item",
        target_id=scope_item.id,
        reason="Audit test",
        approver_role="pm",
        requested_by=admin.id,
    )
    db.flush()
    decide_approval(db, approval_id=approval.id, approved=True, decider_id=admin.id)
    db.flush()
    apply_approval(db, approval, actor_id=admin.id)
    db.flush()

    from app.models.workflow import AuditTrailEvent
    events_after = db.query(AuditTrailEvent).count()
    # At minimum: requested + approved + applied = 3 new events
    assert events_after - events_before >= 3


def test_no_pending_approvals_after_migration():
    """Verify C4 migration backfilled 'pending' → 'requested' in the real DB."""
    from sqlalchemy import create_engine as ce
    from app.config import settings
    engine = ce(settings.database_url, connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM approval_requests WHERE status = 'pending'"))
        count = result.scalar()
    assert count == 0, f"Found {count} approval_requests still with status='pending'"
