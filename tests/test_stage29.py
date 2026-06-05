"""Stage 29 acceptance test — deployment & operations hardening.

Verifies:
1.  startup_check passes with valid dev-mode settings.
2.  startup_check raises RuntimeError when secret_key is empty (always).
3.  startup_check raises RuntimeError when environment=prod + default secret_key.
4.  startup_check raises RuntimeError when environment=prod + missing encryption_key.
5.  startup_check passes in prod when both secret_key and encryption_key are set.
6.  backup_sqlite creates a tar.gz containing the DB and evidence files.
7.  restore_sqlite reproduces DB content in a clean target location.
8.  restore_sqlite reproduces evidence files.
9.  generate_access_report returns expected structure and permissions.
10. apply_retention_policy deletes events older than the threshold.
11. Access-review can be enqueued as an RQ job and returns a report.
"""
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import fakeredis
import pytest
from rq import Queue
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.organization import Organization
from app.models.users import Permission, Role, RoleName, ScopeLevel, User
from app.models.workflow import AuditTrailEvent
from app.services.auth import hash_password
from app.services.ops.access_review import generate_access_report, run_access_review_job
from app.services.ops.backup import backup_sqlite, restore_sqlite
from app.services.ops.health import startup_check
from app.services.ops.retention import apply_retention_policy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cfg(**kwargs):
    """Build a simple settings-like namespace."""
    defaults = {
        "secret_key": "a-valid-secret-key-32-chars-xxxxx",
        "encryption_key": "",
        "environment": "dev",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── 1–5. Startup self-check ───────────────────────────────────────────────────

def test_startup_check_passes_dev():
    startup_check(_cfg(environment="dev"))  # no error


def test_startup_check_fails_empty_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        startup_check(_cfg(secret_key=""))


def test_startup_check_fails_prod_default_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        startup_check(_cfg(environment="prod", secret_key="change-me-in-production"))


def test_startup_check_fails_prod_missing_encryption():
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        startup_check(_cfg(
            environment="prod",
            secret_key="a-valid-non-default-secret-key-xx",
            encryption_key="",
        ))


def test_startup_check_passes_prod_with_all_secrets():
    startup_check(_cfg(
        environment="prod",
        secret_key="a-valid-non-default-secret-key-xx",
        encryption_key="SomeFernetKeyABCDEFGHIJKLMNOPQRSTUV==",
    ))


# ── 6–8. Backup + restore ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def file_db(tmp_path_factory):
    """File-based SQLite DB seeded with one Organisation and one Project."""
    tmp = tmp_path_factory.mktemp("s29_db")
    db_path = tmp / "app.db"

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        # Roles required for Permission FK later
        for rname in [r.value for r in RoleName]:
            db.add(Role(name=rname))
        org = Organization(name="S29 Org")
        db.add(org)
        db.flush()
        client = Client(name="S29 Client", organization_id=org.id)
        db.add(client)
        db.flush()
        proj = Project(
            client_id=client.id,
            service_type=ServiceType.vapt,
            status="active",
        )
        db.add(proj)
        db.commit()
        org_id = org.id
        proj_id = proj.id
    engine.dispose()
    return tmp, db_path, org_id, proj_id


@pytest.fixture(scope="module")
def evidence_dir(tmp_path_factory, file_db):
    """Tiny evidence directory with one file."""
    tmp, *_ = file_db
    ev = tmp / "evidence"
    ev.mkdir()
    (ev / "sample.txt").write_text("network topology evidence")
    sub = ev / "subdir"
    sub.mkdir()
    (sub / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return ev


def test_backup_creates_archive(tmp_path, file_db, evidence_dir):
    _, db_path, *_ = file_db
    archive = tmp_path / "backup.tar.gz"
    result = backup_sqlite(db_path, evidence_dir, archive)
    assert result == archive
    assert archive.exists()
    assert archive.stat().st_size > 0


def test_restore_reproduces_db(tmp_path, file_db, evidence_dir):
    _, db_path, org_id, proj_id = file_db
    archive = tmp_path / "restore_test.tar.gz"
    backup_sqlite(db_path, evidence_dir, archive)

    dest_db = tmp_path / "restored.db"
    dest_ev = tmp_path / "restored_evidence"
    manifest = restore_sqlite(archive, dest_db, dest_ev)

    assert dest_db.exists()
    assert "created_at" in manifest

    engine2 = create_engine(
        f"sqlite:///{dest_db}",
        connect_args={"check_same_thread": False},
    )
    with Session(engine2) as db:
        org = db.get(Organization, org_id)
        assert org is not None
        assert org.name == "S29 Org"
        proj = db.get(Project, proj_id)
        assert proj is not None
    engine2.dispose()


def test_restore_reproduces_evidence(tmp_path, file_db, evidence_dir):
    _, db_path, *_ = file_db
    archive = tmp_path / "ev_restore.tar.gz"
    backup_sqlite(db_path, evidence_dir, archive)

    dest_db = tmp_path / "ev_dest.db"
    dest_ev = tmp_path / "ev_restored"
    restore_sqlite(archive, dest_db, dest_ev)

    assert (dest_ev / "sample.txt").exists()
    assert (dest_ev / "sample.txt").read_text() == "network topology evidence"
    assert (dest_ev / "subdir" / "img.png").exists()


# ── 9–10. Access review + retention ──────────────────────────────────────────

@pytest.fixture(scope="module")
def mem_db_url(tmp_path_factory):
    """File-based SQLite (not in-memory) so the job can open its own connection."""
    tmp = tmp_path_factory.mktemp("s29_ops")
    db_path = tmp / "ops.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        for rname in [r.value for r in RoleName]:
            db.add(Role(name=rname))
        db.flush()
        analyst_role = db.query(Role).filter_by(name=RoleName.analyst.value).first()
        admin_role = db.query(Role).filter_by(name=RoleName.admin.value).first()

        u1 = User(
            email="alice@s29.local",
            password_hash=hash_password("pass"),
            full_name="Alice",
            is_active=True,
        )
        u2 = User(
            email="bob@s29.local",
            password_hash=hash_password("pass"),
            full_name="Bob",
            is_active=True,
        )
        db.add_all([u1, u2])
        db.flush()
        db.add(Permission(
            user_id=u1.id,
            role_id=analyst_role.id,
            scope_level=ScopeLevel.project.value,
        ))
        db.add(Permission(
            user_id=u2.id,
            role_id=admin_role.id,
            scope_level=ScopeLevel.organization.value,
        ))
        db.commit()

    engine.dispose()
    return db_url


def test_access_report_structure(mem_db_url):
    report = generate_access_report(mem_db_url)
    assert "generated_at" in report
    assert "permissions" in report
    assert "total_users" in report
    assert report["total_permissions"] >= 2
    emails = {p["user_email"] for p in report["permissions"]}
    assert "alice@s29.local" in emails
    assert "bob@s29.local" in emails
    roles = report["summary"]["roles"]
    assert "analyst" in roles
    assert "admin" in roles


def test_retention_deletes_old_events(mem_db_url):
    engine = create_engine(mem_db_url, connect_args={"check_same_thread": False})

    with Session(engine) as db:
        # Insert one old event and one recent event
        old_event = AuditTrailEvent(
            action="old_action",
            target_type="test",
            target_id="x",
        )
        recent_event = AuditTrailEvent(
            action="recent_action",
            target_type="test",
            target_id="y",
        )
        db.add_all([old_event, recent_event])
        db.flush()
        # Manually backdate the old event
        old_event.created_at = datetime.now(timezone.utc) - timedelta(days=400)
        db.commit()
        old_id = old_event.id
        recent_id = recent_event.id
    engine.dispose()

    deleted = apply_retention_policy(mem_db_url, retention_days=365)
    assert deleted >= 1

    engine2 = create_engine(mem_db_url, connect_args={"check_same_thread": False})
    with Session(engine2) as db:
        assert db.get(AuditTrailEvent, old_id) is None
        assert db.get(AuditTrailEvent, recent_id) is not None
    engine2.dispose()


# ── 11. Access review as RQ job ───────────────────────────────────────────────

def test_access_review_rq_job(mem_db_url):
    conn = fakeredis.FakeRedis()
    q = Queue(is_async=False, connection=conn)
    job = q.enqueue(run_access_review_job, mem_db_url)
    report = job.result
    assert report is not None
    assert "permissions" in report
    assert report["total_permissions"] >= 2
