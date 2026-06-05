"""Stage 18 acceptance test — hybrid evidence lifecycle.

Verifies:
1. Packaging un-verified evidence (intake state) is blocked.
2. verify → classify → package happy path succeeds.
3. Releasing a deliverable promotes all packaged evidence to delivered.
4. Supersede creates new item with supersedes_id; old item retained and chain queryable.
5. Lifecycle events are appended to EvidenceLifecycleEvent on each transition.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all models
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.evidence import (
    EvidenceItem,
    EvidenceLifecycleEvent,
    EvidenceLifecycleState,
    ReviewerStatus,
)
from app.models.organization import Organization
from app.models.users import Role, RoleName, User
from app.services.auth import hash_password
from app.services.evidence.lifecycle import (
    archive_evidence,
    classify_evidence,
    deliver_evidence,
    mark_project_evidence_delivered,
    package_evidence,
    supersede_evidence,
    verify_evidence,
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
        email="s18_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage18 Admin",
        is_active=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    yield session, admin.id
    session.close()


@pytest.fixture(scope="module")
def project_fixture(db):
    session, user_id = db
    org = Organization(name="S18 Org")
    session.add(org)
    session.flush()
    client = Client(name="S18 Client", organization_id=org.id)
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


def _make_item(session: Session, project_id: str, *, classification: str = None) -> EvidenceItem:
    """Create a bare EvidenceItem in intake state without touching disk."""
    item = EvidenceItem(
        project_id=project_id,
        source_file="test_doc.txt",
        sha256="a" * 64,
        mime="text/plain",
        reviewer_status=ReviewerStatus.pending.value,
        internal_lifecycle_state=EvidenceLifecycleState.intake.value,
        classification=classification,
    )
    session.add(item)
    session.flush()
    return item


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_package_unverified_blocked(db, project_fixture):
    """Packaging evidence still in 'intake' state must raise ValueError."""
    session, user_id = db
    item = _make_item(session, project_fixture.id)
    session.commit()

    with pytest.raises(ValueError, match="intake"):
        package_evidence(session, item.id, actor_id=user_id)

    session.rollback()


def test_verify_classify_package_allowed(db, project_fixture):
    """intake → verified → classified → packaged happy path succeeds."""
    session, user_id = db
    item = _make_item(session, project_fixture.id, classification="policy")
    session.commit()

    # intake → verified
    verify_evidence(session, item.id, actor_id=user_id)
    session.flush()
    assert item.internal_lifecycle_state == EvidenceLifecycleState.verified.value
    assert item.reviewer_status == ReviewerStatus.accepted.value

    # verified → classified
    classify_evidence(session, item.id, actor_id=user_id)
    session.flush()
    assert item.internal_lifecycle_state == EvidenceLifecycleState.classified.value

    # classified → packaged
    package_evidence(session, item.id, actor_id=user_id)
    session.commit()
    assert item.internal_lifecycle_state == EvidenceLifecycleState.packaged.value


def test_classify_without_classification_field_blocked(db, project_fixture):
    """classify_evidence must raise if item.classification is not set."""
    session, user_id = db
    item = _make_item(session, project_fixture.id)  # no classification
    session.commit()

    verify_evidence(session, item.id, actor_id=user_id)
    session.flush()

    with pytest.raises(ValueError, match="classification"):
        classify_evidence(session, item.id, actor_id=user_id)

    session.rollback()


def test_release_delivers_packaged_evidence(db, project_fixture):
    """mark_project_evidence_delivered promotes packaged → delivered for all project items."""
    session, user_id = db

    # Create two items in packaged state
    i1 = _make_item(session, project_fixture.id, classification="network")
    i2 = _make_item(session, project_fixture.id, classification="access_control")
    # Fast-forward both to packaged without writing events (direct ORM set)
    i1.internal_lifecycle_state = EvidenceLifecycleState.packaged.value
    i2.internal_lifecycle_state = EvidenceLifecycleState.packaged.value
    session.commit()

    count = mark_project_evidence_delivered(session, project_fixture.id, actor_id=user_id)
    session.commit()

    assert count >= 2  # may be higher if earlier tests left packaged items
    session.refresh(i1)
    session.refresh(i2)
    assert i1.internal_lifecycle_state == EvidenceLifecycleState.delivered.value
    assert i2.internal_lifecycle_state == EvidenceLifecycleState.delivered.value


def test_supersede_retains_old_item_and_chain_queryable(db, project_fixture, tmp_path):
    """supersede_evidence creates a new item; old item is retained with supersedes_id FK."""
    session, user_id = db

    # Create old item in intake state
    old = _make_item(session, project_fixture.id, classification="logs")
    session.commit()
    old_id = old.id

    # Write a tiny temp file for the new item content (supersede_evidence calls ingest_file)
    fake_file = tmp_path / "replacement.txt"
    fake_file.write_bytes(b"replacement evidence content")

    # Monkeypatch storage_path to write to tmp_path so tests don't pollute disk
    import app.services.evidence.ingest as ingest_mod
    original_storage_path = ingest_mod.storage_path

    def _patched_storage_path(project_id: str, sha256: str, filename: str):
        dest = tmp_path / f"{sha256}{fake_file.suffix}"
        return dest

    ingest_mod.storage_path = _patched_storage_path
    try:
        new_item = supersede_evidence(
            session,
            old_id,
            project_id=project_fixture.id,
            data=b"replacement evidence content",
            filename="replacement.txt",
            actor_id=user_id,
        )
        session.commit()
    finally:
        ingest_mod.storage_path = original_storage_path

    new_id = new_item.id
    assert new_id != old_id

    # Old item must still exist in DB
    old_retrieved = session.get(EvidenceItem, old_id)
    assert old_retrieved is not None, "Old item must not be deleted"

    # New item must reference old via supersedes_id
    new_retrieved = session.get(EvidenceItem, new_id)
    assert new_retrieved.supersedes_id == old_id

    # Chain queryable: new.supersedes → old
    assert new_retrieved.supersedes is not None
    assert new_retrieved.supersedes.id == old_id


def test_lifecycle_events_recorded(db, project_fixture):
    """EvidenceLifecycleEvent rows are appended on each transition."""
    session, user_id = db
    item = _make_item(session, project_fixture.id, classification="firewall")
    session.commit()

    verify_evidence(session, item.id, actor_id=user_id, reason="test verify")
    classify_evidence(session, item.id, actor_id=user_id, reason="test classify")
    session.commit()

    events = (
        session.query(EvidenceLifecycleEvent)
        .filter_by(evidence_item_id=item.id)
        .order_by(EvidenceLifecycleEvent.ts)
        .all()
    )
    assert len(events) == 2
    assert events[0].from_state == EvidenceLifecycleState.intake.value
    assert events[0].to_state == EvidenceLifecycleState.verified.value
    assert events[0].reason == "test verify"
    assert events[1].from_state == EvidenceLifecycleState.verified.value
    assert events[1].to_state == EvidenceLifecycleState.classified.value
    assert events[1].reason == "test classify"
