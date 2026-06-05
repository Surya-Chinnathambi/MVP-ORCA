"""Stage 15 acceptance test — Postgres support, RQ background workers, scheduler.

Verifies:
1. `_make_engine` accepts both sqlite and postgres URL patterns.
2. Evidence-extraction job enqueued via RQ produces the same `extracted_text`
   as the synchronous ingest path (uses fakeredis + Queue(is_async=False)).
3. `register_heartbeat` registers exactly one repeating heartbeat job in the scheduler.
"""
import fakeredis
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers models + event listeners
from app.db import Base, _make_engine
from app.models.clients import Client, Project, ServiceType
from app.models.evidence import EvidenceItem
from app.models.organization import Organization
from app.models.users import Role, RoleName, User
from app.services.auth import hash_password
from app.services.evidence.ingest import ingest_file


# ── Shared fixtures ───────────────────────────────────────────────────────────

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
def db_session(engine):
    Sess = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Sess()
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    user = User(
        email="s15_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage15 Admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield db, user.id
    db.close()


@pytest.fixture(scope="module")
def project_fixture(db_session, engine):
    session, user_id = db_session
    org = Organization(name="S15 Org")
    session.add(org)
    session.flush()
    client = Client(name="S15 Client", organization_id=org.id)
    session.add(client)
    session.flush()
    proj = Project(
        client_id=client.id,
        service_type=ServiceType.dpdp,
        owner_id=user_id,
        status="setup",
    )
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return proj


@pytest.fixture(scope="module")
def fake_redis_conn():
    return fakeredis.FakeRedis()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_make_engine_sqlite():
    """_make_engine returns a working engine for a sqlite:// URL."""
    eng = _make_engine("sqlite:///:memory:")
    assert "sqlite" in str(eng.url)
    eng.dispose()


def test_make_engine_postgres_url():
    """_make_engine returns an engine for a postgresql+psycopg:// URL without connecting."""
    eng = _make_engine("postgresql+psycopg://user:pw@localhost:5432/testdb")
    assert "postgresql" in str(eng.url)
    eng.dispose()


def test_evidence_extraction_job_matches_sync_path(
    project_fixture, engine, monkeypatch, tmp_path
):
    """RQ job produces the same extracted_text as the synchronous ingest path."""
    import app.services.jobs as jmod
    import app.services.jobs_impl as impl
    from rq import Queue

    # Build a fresh session factory pointing at the test engine
    Sess = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Patch SessionLocal inside jobs_impl so the job function uses the test DB
    monkeypatch.setattr(impl, "SessionLocal", Sess)

    # Inject fakeredis into the jobs enqueue helper
    conn = fakeredis.FakeRedis()
    jmod._override_redis(conn)

    session, _ = project_fixture, None
    proj = project_fixture

    # Ingest a plain-text file synchronously
    txt_bytes = b"DPDP audit evidence: breach notification and consent management procedures."
    db = Sess()
    item = ingest_file(db, project_id=proj.id, data=txt_bytes, filename="s15_evidence.txt")
    sync_text = item.extracted_text
    item_id = item.id
    assert sync_text, "ingest_file must extract text from a plain text file"

    # Reset extracted_text to simulate a re-extraction run
    item.extracted_text = None
    db.commit()
    db.close()

    # Enqueue — Queue(is_async=False) runs the job synchronously in this process
    q = Queue("evidence", connection=conn, is_async=False)
    job = q.enqueue("app.services.jobs_impl.run_evidence_extraction", item_id)

    assert job.get_status().value in ("finished", "stopped"), (
        f"Job did not finish: {job.get_status()}\n{job.exc_info}"
    )

    # Verify the background job restored extracted_text to the same value
    verify_db = Sess()
    ev = verify_db.get(EvidenceItem, item_id)
    assert ev.extracted_text == sync_text, (
        f"Async path produced different text.\n  sync: {sync_text!r}\n  async: {ev.extracted_text!r}"
    )
    verify_db.close()


def test_scheduler_registers_heartbeat(fake_redis_conn):
    """register_heartbeat enqueues exactly one repeating heartbeat scheduled job."""
    from rq_scheduler import Scheduler
    from workers.worker import register_heartbeat

    register_heartbeat(fake_redis_conn)

    scheduler = Scheduler(queue_name="default", connection=fake_redis_conn)
    heartbeat_jobs = [
        j for j in scheduler.get_jobs()
        if getattr(j, "meta", {}).get("heartbeat")
    ]
    assert len(heartbeat_jobs) == 1, (
        f"Expected 1 heartbeat job, found {len(heartbeat_jobs)}"
    )
    meta = heartbeat_jobs[0].meta
    assert meta.get("interval") == 60, f"Unexpected interval: {meta}"


def test_scheduler_no_duplicate_heartbeats(fake_redis_conn):
    """Calling register_heartbeat twice results in exactly one heartbeat job."""
    from rq_scheduler import Scheduler
    from workers.worker import register_heartbeat

    # Second registration should cancel the first and create a new one
    register_heartbeat(fake_redis_conn)

    scheduler = Scheduler(queue_name="default", connection=fake_redis_conn)
    heartbeat_jobs = [
        j for j in scheduler.get_jobs()
        if getattr(j, "meta", {}).get("heartbeat")
    ]
    assert len(heartbeat_jobs) == 1
