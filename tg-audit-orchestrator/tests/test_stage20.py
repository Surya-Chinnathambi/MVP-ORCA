"""Stage 20 acceptance test — expanded RBAC + sensitive evidence.

Verifies:
1. All 13 roles (8 MVP + 5 Phase 2) exist in DB.
2. All 5 scope levels exist in ScopeLevel enum.
3. Analyst without evidence_item permission gets PermissionError on restricted item export.
4. Redaction creates a new EvidenceItem with is_restricted=False; original becomes is_restricted=True.
5. Export of restricted evidence writes an audit event and is blocked without evidence_item scope.
6. Export succeeds and writes an audit event when user has evidence_item permission.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.evidence import EvidenceItem, ReviewerStatus
from app.models.organization import Organization
from app.models.users import Permission, Role, RoleName, ScopeLevel, User
from app.services.auth import hash_password
from app.services.evidence.export import export_evidence
from app.services.evidence.redaction import redact_evidence
from app.deps import check_evidence_access


# ── DB fixture ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="module")
def db(engine):
    Sess = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Sess()
    for name in [r.value for r in RoleName]:
        session.add(Role(name=name))
    admin = User(
        email="s20_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage20 Admin",
        is_active=True,
    )
    analyst_user = User(
        email="s20_analyst@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage20 Analyst",
        is_active=True,
    )
    session.add_all([admin, analyst_user])
    session.commit()
    session.refresh(admin)
    session.refresh(analyst_user)
    yield session, admin.id, analyst_user.id
    session.close()


@pytest.fixture(scope="module")
def project_fixture(db):
    session, admin_id, _ = db
    org = Organization(name="S20 Org")
    session.add(org)
    session.flush()
    client = Client(entity_name="S20 Client", organization_id=org.id)
    session.add(client)
    session.flush()
    proj = Project(
        client_id=client.id,
        service_type=ServiceType.dpdp,
        owner_id=admin_id,
        status="active",
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return proj


def _make_item(session: Session, project_id: str, *, is_restricted: bool = False) -> EvidenceItem:
    item = EvidenceItem(
        project_id=project_id,
        source_file="sensitive_doc.txt",
        sha256="b" * 64,
        mime="text/plain",
        reviewer_status=ReviewerStatus.accepted.value,
        is_restricted=is_restricted,
    )
    session.add(item)
    session.flush()
    return item


# ── Role / enum coverage ──────────────────────────────────────────────────────

def test_all_thirteen_roles_exist(db):
    """All 8 MVP + 5 Phase 2 roles must be in the RoleName enum and DB."""
    session, _, _ = db
    expected = {r.value for r in RoleName}
    assert "platform_admin" in expected
    assert "lead_consultant" in expected
    assert "senior_reviewer" in expected
    assert "client_approver" in expected
    assert "client_contributor" in expected
    db_names = {r.name for r in session.query(Role).all()}
    assert expected == db_names, f"DB roles mismatch: {expected ^ db_names}"


def test_all_five_scope_levels_in_enum():
    """ScopeLevel must include the 3 new Phase 2 levels."""
    levels = {s.value for s in ScopeLevel}
    assert "organization" in levels
    assert "evidence_item" in levels
    assert "deliverable" in levels
    assert "client" in levels
    assert "project" in levels


# ── Restricted evidence access ────────────────────────────────────────────────

def test_analyst_without_permission_blocked_on_restricted_item(db, project_fixture):
    """Analyst user without evidence_item permission cannot export a restricted item."""
    session, admin_id, analyst_id = db
    item = _make_item(session, project_fixture.id, is_restricted=True)
    session.commit()

    with pytest.raises(PermissionError, match="lacks evidence_item permission"):
        export_evidence(session, item.id, actor_id=analyst_id)

    session.rollback()


def test_check_evidence_access_denies_restricted_without_perm(db, project_fixture):
    """check_evidence_access returns False for restricted item with no permission."""
    session, admin_id, analyst_id = db
    item = _make_item(session, project_fixture.id, is_restricted=True)
    analyst_user = session.get(User, analyst_id)
    session.commit()

    assert not check_evidence_access(item, analyst_user, session)


def test_check_evidence_access_allows_unrestricted(db, project_fixture):
    """check_evidence_access returns True for any non-restricted item."""
    session, admin_id, analyst_id = db
    item = _make_item(session, project_fixture.id, is_restricted=False)
    analyst_user = session.get(User, analyst_id)
    session.commit()

    assert check_evidence_access(item, analyst_user, session)


# ── Redaction ─────────────────────────────────────────────────────────────────

def test_redaction_creates_sanitised_copy_original_stays_restricted(db, project_fixture, tmp_path):
    """redact_evidence: original becomes restricted=True; new item is restricted=False."""
    session, admin_id, _ = db

    import app.services.evidence.redaction as red_mod
    original_storage = red_mod._EVIDENCE_ROOT
    red_mod._EVIDENCE_ROOT = tmp_path  # redirect writes to tmp

    try:
        original = _make_item(session, project_fixture.id, is_restricted=False)
        original.extracted_text = "Top-secret audit finding details"
        session.flush()
        original_id = original.id

        redacted = redact_evidence(session, original_id, actor_id=admin_id, reason="Scope review")
        session.commit()
    finally:
        red_mod._EVIDENCE_ROOT = original_storage

    # Original must be marked restricted
    session.refresh(original)
    assert original.is_restricted is True

    # Redacted copy must exist and NOT be restricted
    assert redacted.id != original_id
    assert redacted.is_restricted is False
    assert redacted.classification == "redacted"
    assert "REDACTED" in redacted.extracted_text
    assert "REDACTED_" in redacted.source_file


# ── Export with / without permission ─────────────────────────────────────────

def test_export_restricted_writes_audit_event_and_blocks_without_scope(db, project_fixture):
    """Blocked export still writes an AuditTrailEvent tagged evidence.export.blocked."""
    session, admin_id, analyst_id = db

    from app.models.workflow import AuditTrailEvent

    item = _make_item(session, project_fixture.id, is_restricted=True)
    session.commit()
    item_id = item.id
    before_count = session.query(AuditTrailEvent).count()

    with pytest.raises(PermissionError):
        export_evidence(session, item_id, actor_id=analyst_id)

    after_count = session.query(AuditTrailEvent).count()
    assert after_count > before_count, "Blocked export must write an audit event"

    last = (
        session.query(AuditTrailEvent)
        .order_by(AuditTrailEvent.created_at.desc())
        .first()
    )
    assert last.action == "evidence.export.blocked"
    session.rollback()


def test_export_succeeds_and_writes_audit_event_with_evidence_item_scope(db, project_fixture):
    """User with evidence_item permission can export; audit event written."""
    session, admin_id, analyst_id = db

    from app.models.workflow import AuditTrailEvent

    # Grant analyst evidence_item scope for this project (scope_id=None = org-wide)
    analyst_role = session.query(Role).filter_by(name=RoleName.analyst.value).first()
    perm = Permission(
        user_id=analyst_id,
        role_id=analyst_role.id,
        scope_level=ScopeLevel.evidence_item.value,
        scope_id=None,
    )
    session.add(perm)

    item = _make_item(session, project_fixture.id, is_restricted=True)
    session.commit()
    item_id = item.id
    before_count = session.query(AuditTrailEvent).count()

    # Should not raise
    path = export_evidence(session, item_id, actor_id=analyst_id)
    session.commit()

    after_count = session.query(AuditTrailEvent).count()
    assert after_count > before_count, "Successful export must write an audit event"

    last = (
        session.query(AuditTrailEvent)
        .order_by(AuditTrailEvent.created_at.desc())
        .first()
    )
    assert last.action == "evidence.export.success"
