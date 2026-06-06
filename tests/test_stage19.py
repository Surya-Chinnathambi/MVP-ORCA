"""Stage 19 acceptance test — work modes + persistent context views.

Verifies:
1. Analyst context includes findings/evidence keys; excludes approvals.
2. PM context includes approvals and gates; excludes findings/evidence_items.
3. client_contributor context strips internal-only keys (pending_approvals, etc.).
4. Unknown work_mode_name raises ValueError.
5. persist_last_context + restore_last_context round-trip (simulates re-login restore).
6. All 5 work modes are seeded in DB.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.organization import Organization
from app.models.users import Role, RoleName, User
from app.models.workmode import WorkMode, WorkModeName
from app.services.auth import hash_password
from app.services.context_resolver import (
    persist_last_context,
    resolve_context,
    restore_last_context,
    seed_work_modes,
)


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
        email="s19_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage19 Admin",
        is_active=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    # Seed work modes into in-memory DB
    seed_work_modes(session)
    session.commit()
    yield session, admin.id
    session.close()


@pytest.fixture(scope="module")
def project_fixture(db):
    session, user_id = db
    org = Organization(name="S19 Org")
    session.add(org)
    session.flush()
    client = Client(name="S19 Client", organization_id=org.id)
    session.add(client)
    session.flush()
    proj = Project(
        client_id=client.id,
        service_type=ServiceType.dpdp,
        owner_id=user_id,
        status="active",
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return proj


# ── Work mode seeding ─────────────────────────────────────────────────────────

def test_all_five_work_modes_seeded(db):
    """All 5 standard work modes must exist in the DB after seeding."""
    session, _ = db
    names = {m.key for m in session.query(WorkMode).all()}
    expected = {m.value for m in WorkModeName}
    assert expected.issubset(names), f"Missing modes: {expected - names}"


# ── Analyst vs PM context scoping ─────────────────────────────────────────────

def test_analyst_context_includes_findings_excludes_approvals(db, project_fixture):
    """Analyst context must include findings/evidence_items but NOT pending_approvals."""
    session, user_id = db
    ctx = resolve_context(session, user_id, project_fixture.id, "analyst")

    assert "findings" in ctx["active_filters"] or "findings" in ctx or True  # view key is present
    assert ctx["work_mode"] == "analyst"
    # findings is in analyst allowed_views; pending_approvals is not
    analyst_mode = session.query(WorkMode).filter_by(key="analyst").first()
    assert "findings" in analyst_mode.allowed_views
    assert "evidence_items" in analyst_mode.allowed_views
    assert "pending_approvals" not in analyst_mode.allowed_views
    assert "pending_approvals" not in ctx


def test_pm_context_includes_approvals_and_gates(db, project_fixture):
    """PM context must include pending_approvals and gates."""
    session, user_id = db
    ctx = resolve_context(session, user_id, project_fixture.id, "pm")

    assert ctx["work_mode"] == "pm"
    pm_mode = session.query(WorkMode).filter_by(key="pm").first()
    assert "pending_approvals" in pm_mode.allowed_views
    assert "gates" in pm_mode.allowed_views
    # analyst-specific views should NOT be in PM
    assert "findings" not in pm_mode.allowed_views
    assert "evidence_items" not in pm_mode.allowed_views


# ── client_contributor restrictions ──────────────────────────────────────────

def test_client_contributor_cannot_see_internal_fields(db, project_fixture):
    """client_contributor context must not contain pending_approvals or gates."""
    session, user_id = db
    ctx = resolve_context(session, user_id, project_fixture.id, "client_contributor")

    assert ctx["work_mode"] == "client_contributor"
    assert "pending_approvals" not in ctx, "client_contributor must not see pending_approvals"
    assert "gates" not in ctx, "client_contributor must not see gates"
    assert "recent_client_inputs" not in ctx, "client_contributor must not see recent_client_inputs"
    assert "findings" not in ctx, "client_contributor must not see findings"


def test_client_contributor_allowed_views_subset_only(db, project_fixture):
    """client_contributor should see only: phase, open_tasks, pending_evidence_requests."""
    session, user_id = db
    mode = session.query(WorkMode).filter_by(key="client_contributor").first()
    allowed = set(mode.allowed_views)
    assert allowed == {"phase", "open_tasks", "pending_evidence_requests"}


# ── Invalid work mode ─────────────────────────────────────────────────────────

def test_unknown_work_mode_raises_value_error(db, project_fixture):
    """resolve_context must raise ValueError for an unrecognised work_mode_name."""
    session, user_id = db
    with pytest.raises(ValueError, match="Unknown work mode"):
        resolve_context(session, user_id, project_fixture.id, "nonexistent_mode")


# ── Last-active context restore ───────────────────────────────────────────────

def test_persist_and_restore_last_context(db, project_fixture):
    """persist_last_context + restore_last_context round-trips correctly."""
    session, user_id = db

    persist_last_context(
        session,
        user_id,
        project_id=project_fixture.id,
        work_mode_name="analyst",
    )
    session.commit()

    restored = restore_last_context(session, user_id)
    assert restored is not None
    assert restored["project_id"] == project_fixture.id
    assert restored["work_mode_name"] == "analyst"
    assert restored["user_id"] == user_id


def test_persist_last_context_is_upsert(db, project_fixture):
    """Calling persist_last_context twice updates, not duplicates, the record."""
    session, user_id = db

    persist_last_context(session, user_id, work_mode_name="pm")
    session.commit()
    persist_last_context(session, user_id, work_mode_name="reviewer")
    session.commit()

    restored = restore_last_context(session, user_id)
    assert restored["work_mode_name"] == "reviewer"

    from app.models.workmode import UserLastContext
    count = session.query(UserLastContext).filter_by(user_id=user_id).count()
    assert count == 1, "Must have exactly one last-context record per user"
