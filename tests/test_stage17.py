"""Stage 17 acceptance test — EngagementCore execution layer.

Verifies:
1. 3-objective chain: blocked objective cannot complete until its prerequisite does
   and (where set) its acceptance criterion is met.
2. Topological sort detects cycles and orders correctly.
3. link_requirement / link_evidence helpers work; evidence serves multiple objectives.
4. context_snapshot reflects open tasks, pending approvals, progress workstreams.
5. refresh_snapshot persists progress to EngagementState.progress.
6. No offensive symbols leak into app/engagementcore/ (grep test).
"""
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.engagement import EngagementObjective, EngagementState
from app.models.organization import Organization
from app.models.users import Role, RoleName, User
from app.services.auth import hash_password
from app.engagementcore.objectives import (
    complete_objective,
    create_objective,
    link_evidence,
    link_requirement,
    sorted_plan,
    topological_sort,
)
from app.engagementcore.context import build_context_snapshot, refresh_snapshot


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
        email="s17_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage17 Admin",
        is_active=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    yield session, admin.id
    session.close()


@pytest.fixture(scope="module")
def project_fixture(db, engine):
    session, user_id = db
    org = Organization(name="S17 Org")
    session.add(org)
    session.flush()
    client = Client(entity_name="S17 Client", organization_id=org.id)
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


# ── Objective chain tests ─────────────────────────────────────────────────────

def test_three_objective_chain_blocks_until_prereq(db, project_fixture):
    """A → B → C chain: C is blocked until B completes, B is blocked until A completes."""
    session, _ = db
    proj = project_fixture

    a = create_objective(session, project_id=proj.id, title="Objective A")
    session.flush()
    b = create_objective(session, project_id=proj.id, title="Objective B", depends_on=[a.id])
    session.flush()
    c = create_objective(session, project_id=proj.id, title="Objective C", depends_on=[b.id])
    session.flush()
    session.commit()

    # C blocked by B
    with pytest.raises(ValueError, match="not complete"):
        complete_objective(session, c.id)

    # B blocked by A
    with pytest.raises(ValueError, match="not complete"):
        complete_objective(session, b.id)

    # Complete A → now B can be completed
    complete_objective(session, a.id)
    session.commit()
    assert a.status == "complete"

    complete_objective(session, b.id)
    session.commit()
    assert b.status == "complete"

    complete_objective(session, c.id)
    session.commit()
    assert c.status == "complete"


def test_acceptance_criteria_requires_linked_items(db, project_fixture):
    """An objective with acceptance_criteria cannot complete without linked evidence/requirement."""
    session, _ = db
    proj = project_fixture

    obj = create_objective(
        session,
        project_id=proj.id,
        title="Criteria Obj",
        acceptance_criteria="Evidence of policy review required",
    )
    session.flush()
    session.commit()

    # No linked evidence or requirement → blocked
    with pytest.raises(ValueError, match="acceptance_criteria"):
        complete_objective(session, obj.id)

    # Link a fake requirement ID → now allowed
    link_requirement(session, obj.id, "fake-req-id-1234")
    session.commit()

    complete_objective(session, obj.id)
    session.commit()
    assert obj.status == "complete"


def test_evidence_serves_multiple_objectives(db, project_fixture):
    """One evidence item can be linked to multiple objectives."""
    session, _ = db
    proj = project_fixture

    obj1 = create_objective(session, project_id=proj.id, title="Multi Ev Obj 1")
    session.flush()
    obj2 = create_objective(session, project_id=proj.id, title="Multi Ev Obj 2")
    session.flush()
    session.commit()

    fake_ev_id = "shared-evidence-uuid"
    link_evidence(session, obj1.id, fake_ev_id)
    link_evidence(session, obj2.id, fake_ev_id)
    session.commit()

    assert fake_ev_id in obj1.linked_evidence_ids
    assert fake_ev_id in obj2.linked_evidence_ids


# ── Topological sort ──────────────────────────────────────────────────────────

def test_topological_sort_correct_order(db, project_fixture):
    """sorted_plan returns prerequisites before dependants."""
    session, _ = db
    proj = project_fixture

    # Build independent chain X → Y
    x = create_objective(session, project_id=proj.id, title="Sort X")
    session.flush()
    y = create_objective(session, project_id=proj.id, title="Sort Y", depends_on=[x.id])
    session.flush()
    session.commit()

    objs = [y, x]  # pass in reverse order
    ordered = topological_sort(objs)
    ids = [o.id for o in ordered]
    assert ids.index(x.id) < ids.index(y.id)


def test_topological_sort_detects_cycle():
    """topological_sort raises ValueError on a dependency cycle."""
    # Build two fake objectives that point at each other
    class _FakeObj:
        def __init__(self, oid, deps):
            self.id = oid
            self.depends_on = deps

    a = _FakeObj("a", ["b"])
    b = _FakeObj("b", ["a"])
    with pytest.raises(ValueError, match="cycle"):
        topological_sort([a, b])


# ── Context snapshot ──────────────────────────────────────────────────────────

def test_context_snapshot_reflects_open_tasks(db, project_fixture):
    """context_snapshot.open_tasks lists non-done tasks for the project."""
    session, user_id = db
    proj = project_fixture

    from app.models.tasks import Task, TaskKind
    t1 = Task(project_id=proj.id, kind=TaskKind.review.value, title="Open Task 1", status="open")
    t2 = Task(project_id=proj.id, kind=TaskKind.review.value, title="Done Task", status="done")
    session.add_all([t1, t2])
    session.commit()

    snap = build_context_snapshot(session, proj.id)

    open_titles = {t["title"] for t in snap["open_tasks"]}
    assert "Open Task 1" in open_titles
    assert "Done Task" not in open_titles


def test_context_snapshot_reflects_pending_approvals(db, project_fixture):
    """context_snapshot.pending_approvals lists pending ApprovalRequests for the project."""
    session, user_id = db
    proj = project_fixture

    from app.services.audit import request_approval
    approval = request_approval(
        session,
        project_id=proj.id,
        target_type="scope",
        target_id=proj.id,
        reason="Scope change test",
        approver_role="admin",
        requested_by=user_id,
    )
    session.commit()

    snap = build_context_snapshot(session, proj.id)

    assert snap["pending_approvals"], "snapshot must list the pending approval"
    ap_ids = {a["id"] for a in snap["pending_approvals"]}
    assert approval.id in ap_ids


def test_refresh_snapshot_persists_progress(db, project_fixture):
    """refresh_snapshot writes progress to EngagementState.progress."""
    session, _ = db
    proj = project_fixture

    state = refresh_snapshot(session, proj.id)
    session.commit()

    assert isinstance(state.progress, dict), "progress must be persisted as a dict"
    assert "tasks" in state.progress
    assert "evidence" in state.progress
    assert "findings" in state.progress
    assert "objectives" in state.progress
    assert "gates_passed" in state.progress

    assert state.context_snapshot is not None
    assert "phase" in state.context_snapshot


# ── Boundary grep ─────────────────────────────────────────────────────────────

def test_no_offensive_symbols_in_engagementcore():
    """No VAPT/offensive-specific symbols must appear in app/engagementcore/."""
    OFFENSIVE = re.compile(r"\b(opsec|c2|killchain|exploit_phase|attack_narrative|c2_tier)\b", re.I)
    core_dir = Path(__file__).parent.parent / "app" / "engagementcore"
    violations = []
    for py_file in core_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if OFFENSIVE.search(line):
                violations.append(f"{py_file.name}:{lineno}: {line.strip()}")
    assert not violations, "Offensive symbols found in engagementcore:\n" + "\n".join(violations)
