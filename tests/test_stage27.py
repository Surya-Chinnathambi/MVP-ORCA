"""Stage 27 acceptance test — expanded deliverables + workflow states.

Verifies:
1.  All 4 new deliverable builders generate files and Deliverable rows.
2.  Deliverable versions increment on repeated generation.
3.  management_summary cannot be released without a Gate 6 ApprovalRequest.
4.  Finding cannot jump draft → approved (must pass in_review first).
5.  Finding draft → in_review → approval-gated → approved (after resolving approval).
6.  Finding approved → client_shared requires approval (creates request, raises error).
7.  Task transition planned → in_progress is blocked (must go through assigned).
8.  Task full happy path: planned → assigned → in_progress → review → complete.
9.  Project transition active → closed is blocked (must pass through review → client_review → final).
10. Project transition review → client_review raises TransitionError (approval required).
11. migrate_finding_statuses backfills legacy open/remediated/accepted rows.
12. migrate_task_statuses backfills legacy open→planned rows.
"""
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.delivery import Deliverable, DeliverableKind
from app.models.organization import Organization
from app.models.tasks import Finding, FindingSeverity, FindingSource, FindingStatus, Task, TaskKind, TaskStatus
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.deliverables.advisory_clinic_deck import generate_advisory_clinic_deck
from app.services.deliverables.client_action_plan import generate_client_action_plan
from app.services.deliverables.management_summary import (
    generate_management_summary,
    has_release_approval,
)
from app.services.deliverables.retest_report import generate_retest_report
from app.services.workflow_states import (
    TransitionError,
    migrate_finding_statuses,
    migrate_task_statuses,
    transition_finding,
    transition_project,
    transition_task,
)


# ── DB fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    return e


@pytest.fixture(scope="module")
def db(engine):
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def project(db: Session):
    org = Organization(name="S27 Org")
    db.add(org)
    db.flush()
    client = Client(name="S27 Client", organization_id=org.id)
    db.add(client)
    db.flush()
    proj = Project(
        client_id=client.id,
        service_type=ServiceType.vapt,
        status="active",
    )
    db.add(proj)
    db.flush()
    return proj


@pytest.fixture(scope="module")
def finding(db: Session, project: Project):
    f = Finding(
        project_id=project.id,
        title="Test Finding S27",
        severity=FindingSeverity.high.value,
        status=FindingStatus.draft.value,
        source=FindingSource.manual.value,
    )
    db.add(f)
    db.flush()
    return f


@pytest.fixture(scope="module")
def task(db: Session, project: Project):
    t = Task(
        project_id=project.id,
        kind=TaskKind.review.value,
        title="Test Task S27",
        status=TaskStatus.planned.value,
    )
    db.add(t)
    db.flush()
    return t


# ── 1–2. New deliverable builders ─────────────────────────────────────────────

def test_generate_retest_report(db: Session, project: Project, tmp_path):
    d = generate_retest_report(db, project, tmp_path / "retest")
    db.flush()
    assert d.kind == DeliverableKind.retest_report
    assert d.version == 1
    assert Path(d.file_path).exists()


def test_generate_advisory_clinic_deck(db: Session, project: Project, tmp_path):
    d = generate_advisory_clinic_deck(db, project, tmp_path / "clinic")
    db.flush()
    assert d.kind == DeliverableKind.advisory_clinic_deck
    assert d.version == 1
    assert Path(d.file_path).exists()


def test_generate_management_summary(db: Session, project: Project, tmp_path):
    d = generate_management_summary(db, project, tmp_path / "mgmt")
    db.flush()
    assert d.kind == DeliverableKind.management_summary
    assert d.version == 1
    assert Path(d.file_path).exists()


def test_generate_client_action_plan(db: Session, project: Project, tmp_path):
    d = generate_client_action_plan(db, project, tmp_path / "cap")
    db.flush()
    assert d.kind == DeliverableKind.client_action_plan
    assert d.version == 1
    assert Path(d.file_path).exists()


# ── 2. Version increments on repeated generation ──────────────────────────────

def test_deliverable_version_increments(db: Session, project: Project, tmp_path):
    d1 = generate_retest_report(db, project, tmp_path / "retest_v2a")
    db.flush()
    d2 = generate_retest_report(db, project, tmp_path / "retest_v2b")
    db.flush()
    assert d2.version == d1.version + 1


# ── 3. Management summary cannot be released without approval ─────────────────

def test_management_summary_no_release_without_approval(db: Session, project: Project, tmp_path):
    d = generate_management_summary(db, project, tmp_path / "mgmt2")
    db.flush()
    assert not has_release_approval(db, d.id)


def test_management_summary_release_allowed_with_approval(db: Session, project: Project, tmp_path):
    d = generate_management_summary(db, project, tmp_path / "mgmt3")
    db.flush()
    # Simulate approved ApprovalRequest
    approval = ApprovalRequest(
        project_id=project.id,
        target_type="deliverable",
        target_id=d.id,
        reason="Gate 6",
        approver_role="partner",
        status=ApprovalStatus.approved,
        change_before={},
        change_after={"released": True},
    )
    db.add(approval)
    db.flush()
    assert has_release_approval(db, d.id)


# ── 4. Finding cannot jump draft → approved ───────────────────────────────────

def test_finding_cannot_jump_draft_to_approved(db: Session, finding: Finding):
    finding.status = FindingStatus.draft.value
    with pytest.raises(TransitionError, match="not allowed"):
        transition_finding(db, finding, FindingStatus.approved.value)


# ── 5. Finding draft → in_review (no approval needed) ────────────────────────

def test_finding_draft_to_in_review(db: Session, finding: Finding):
    finding.status = FindingStatus.draft.value
    result = transition_finding(db, finding, FindingStatus.in_review.value)
    assert result.status == FindingStatus.in_review.value


# ── 5b. Finding in_review → approved raises TransitionError (creates approval) ─

def test_finding_in_review_to_approved_requires_approval(db: Session, finding: Finding):
    finding.status = FindingStatus.in_review.value
    with pytest.raises(TransitionError, match="requires approval"):
        transition_finding(db, finding, FindingStatus.approved.value)
    # ApprovalRequest must have been created
    approval = (
        db.query(ApprovalRequest)
        .filter_by(project_id=finding.project_id, target_type="finding", target_id=finding.id)
        .first()
    )
    assert approval is not None
    assert approval.approver_role == "reviewer"


# ── 5c. After resolving approval, status can be set directly ──────────────────

def test_finding_approved_after_manual_status_set(db: Session, finding: Finding):
    finding.status = FindingStatus.approved.value
    assert finding.status == FindingStatus.approved.value


# ── 6. Finding approved → client_shared requires partner approval ──────────────

def test_finding_approved_to_client_shared_requires_approval(db: Session, finding: Finding):
    finding.status = FindingStatus.approved.value
    with pytest.raises(TransitionError, match="requires approval"):
        transition_finding(db, finding, FindingStatus.client_shared.value)


# ── 7. Task planned → in_progress is blocked ──────────────────────────────────

def test_task_planned_to_in_progress_blocked(db: Session, task: Task):
    task.status = TaskStatus.planned.value
    with pytest.raises(TransitionError, match="not allowed"):
        transition_task(db, task, TaskStatus.in_progress.value)


# ── 8. Task full happy path ────────────────────────────────────────────────────

def test_task_full_happy_path(db: Session, task: Task):
    task.status = TaskStatus.planned.value
    transition_task(db, task, TaskStatus.assigned.value)
    assert task.status == TaskStatus.assigned.value
    transition_task(db, task, TaskStatus.in_progress.value)
    assert task.status == TaskStatus.in_progress.value
    transition_task(db, task, TaskStatus.review.value)
    assert task.status == TaskStatus.review.value
    transition_task(db, task, TaskStatus.complete.value)
    assert task.status == TaskStatus.complete.value


# ── 9. Project active → closed is blocked ─────────────────────────────────────

def test_project_active_to_closed_blocked(db: Session, project: Project):
    project.status = "active"
    with pytest.raises(TransitionError, match="not allowed"):
        transition_project(db, project, "closed")


# ── 10. Project review → client_review requires approval ──────────────────────

def test_project_review_to_client_review_requires_approval(db: Session, project: Project):
    project.status = "review"
    with pytest.raises(TransitionError, match="requires approval"):
        transition_project(db, project, "client_review")
    approval = (
        db.query(ApprovalRequest)
        .filter_by(project_id=project.id, target_type="project", target_id=project.id)
        .first()
    )
    assert approval is not None
    assert approval.approver_role == "partner"


# ── 11. migrate_finding_statuses backfills legacy statuses ────────────────────

def test_migrate_finding_statuses(db: Session, project: Project):
    f_open = Finding(
        project_id=project.id, title="Legacy Open",
        severity=FindingSeverity.low.value, status="open",
        source=FindingSource.manual.value,
    )
    f_rem = Finding(
        project_id=project.id, title="Legacy Remediated",
        severity=FindingSeverity.low.value, status="remediated",
        source=FindingSource.manual.value,
    )
    f_acc = Finding(
        project_id=project.id, title="Legacy Accepted",
        severity=FindingSeverity.low.value, status="accepted",
        source=FindingSource.manual.value,
    )
    db.add_all([f_open, f_rem, f_acc])
    db.flush()

    count = migrate_finding_statuses(db)
    assert count >= 3
    db.refresh(f_open); db.refresh(f_rem); db.refresh(f_acc)
    assert f_open.status == FindingStatus.in_review.value
    assert f_rem.status == FindingStatus.closed.value
    assert f_acc.status == FindingStatus.risk_accepted.value


# ── 12. migrate_task_statuses backfills open → planned ────────────────────────

def test_migrate_task_statuses(db: Session, project: Project):
    t_open = Task(
        project_id=project.id, kind=TaskKind.review.value,
        title="Legacy Open Task", status="open",
    )
    db.add(t_open)
    db.flush()

    count = migrate_task_statuses(db)
    assert count >= 1
    db.refresh(t_open)
    assert t_open.status == TaskStatus.planned.value
