"""Stage 14 acceptance test — Organization tenant + EngagementCore skeleton.

Verifies:
1. Every client resolves to the default org (org_id is populated).
2. Creating a project auto-creates exactly one EngagementState.
3. No offensive-concept symbols exist inside app/engagementcore/ (grep test).
4. The org → client → project factory in conftest works end-to-end.
5. EngagementState phase is derived from project status correctly.
6. EngagementObjective can be created and listed.
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
from tests.conftest import make_client, make_org, make_project


# ── DB fixture ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="module")
def _db(_engine):
    Sess = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    db = Sess()
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    admin = User(
        email="s14_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Stage14 Admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    yield db, admin.id
    db.close()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestOrganizationTenant:
    def test_client_with_org_id(self, _db):
        db, admin_id = _db
        org = make_org(db, name="TechGuard Labs")
        client = make_client(db, org=org, name="Org Test Corp")
        db.commit()
        db.refresh(client)
        assert client.organization_id == org.id
        assert client.organization is not None
        assert client.organization.name == "TechGuard Labs"

    def test_clients_resolve_to_org(self, _db):
        """Every client that has an org_id resolves the relationship correctly."""
        db, admin_id = _db
        org = make_org(db, name="Second Org")
        for i in range(3):
            c = Client(name=f"MultiClient {i}", organization_id=org.id)
            db.add(c)
        db.commit()

        clients = db.query(Client).filter_by(organization_id=org.id).all()
        assert len(clients) == 3
        for c in clients:
            assert c.organization.id == org.id

    def test_org_lists_clients(self, _db):
        db, admin_id = _db
        org = db.query(Organization).filter_by(name="TechGuard Labs").first()
        assert org is not None
        assert len(org.clients) >= 1


class TestEngagementStateAutoCreate:
    def test_project_auto_creates_one_engagement_state(self, _db):
        """Creating a project must auto-create exactly one EngagementState."""
        db, admin_id = _db
        org = make_org(db, name="AutoState Org")
        client = make_client(db, org=org)
        project = make_project(db, client=client, owner_id=admin_id)
        db.commit()

        states = (
            db.query(EngagementState)
            .filter_by(project_id=project.id)
            .all()
        )
        assert len(states) == 1, f"Expected 1 EngagementState, got {len(states)}"

    def test_engagement_state_not_duplicated(self, _db):
        """A second flush/commit for the same project must not create a duplicate."""
        db, admin_id = _db
        org = make_org(db, name="NoDupe Org")
        client = make_client(db, org=org)
        project = make_project(db, client=client, owner_id=admin_id)
        db.commit()

        # touch the project again
        project.status = "active"
        db.commit()

        count = (
            db.query(EngagementState)
            .filter_by(project_id=project.id)
            .count()
        )
        assert count == 1

    def test_phase_derived_from_status(self, _db):
        """EngagementState phase should reflect the project's initial status."""
        db, admin_id = _db
        org = make_org(db, name="PhaseOrg")
        client = make_client(db, org=org)

        for proj_status, expected_phase in [
            ("setup", "setup"),
            ("active", "active"),
            ("closed", "closed"),
        ]:
            project = make_project(
                db, client=client, owner_id=admin_id, status=proj_status
            )
            db.commit()
            state = (
                db.query(EngagementState)
                .filter_by(project_id=project.id)
                .first()
            )
            assert state is not None
            assert state.phase == expected_phase, (
                f"Status {proj_status!r} → expected phase {expected_phase!r}, "
                f"got {state.phase!r}"
            )

    def test_engagement_state_accessible_via_project(self, _db):
        db, admin_id = _db
        org = make_org(db, name="RelOrg")
        client = make_client(db, org=org)
        project = make_project(db, client=client, owner_id=admin_id)
        db.commit()
        db.refresh(project)

        assert project.engagement_state is not None
        assert project.engagement_state.project_id == project.id


class TestEngagementObjective:
    def test_create_and_list_objectives(self, _db):
        db, admin_id = _db
        from app.engagementcore.objectives import create_objective, list_objectives

        org = make_org(db, name="ObjOrg")
        client = make_client(db, org=org)
        project = make_project(db, client=client, owner_id=admin_id)
        db.commit()

        create_objective(
            db, project_id=project.id,
            title="Define data processing scope",
            acceptance_criteria="All BUs listed and approved",
        )
        create_objective(
            db, project_id=project.id,
            title="Collect evidence",
        )
        db.commit()

        objs = list_objectives(db, project.id)
        assert len(objs) == 2
        titles = {o.title for o in objs}
        assert "Define data processing scope" in titles

    def test_complete_objective(self, _db):
        db, admin_id = _db
        from app.engagementcore.objectives import complete_objective, create_objective

        org = make_org(db, name="CompleteOrg")
        client = make_client(db, org=org)
        project = make_project(db, client=client, owner_id=admin_id)
        db.commit()

        obj = create_objective(db, project_id=project.id, title="Complete me")
        db.commit()

        complete_objective(db, obj.id)
        db.commit()

        db.refresh(obj)
        assert obj.status == "complete"


class TestContextSnapshot:
    def test_build_context_snapshot(self, _db):
        db, admin_id = _db
        from app.engagementcore.context import build_context_snapshot

        org = make_org(db, name="CtxOrg")
        client = make_client(db, org=org)
        project = make_project(db, client=client, owner_id=admin_id)
        db.commit()

        snapshot = build_context_snapshot(db, project.id)
        assert "open_tasks" in snapshot
        assert "pending_approvals" in snapshot
        assert "gates" in snapshot


class TestConftestFactory:
    def test_org_client_project_chain(self, _db):
        db, admin_id = _db
        org = make_org(db, name="Factory Org")
        client = make_client(db, org=org, name="Factory Client")
        project = make_project(
            db, client=client, owner_id=admin_id, service_type=ServiceType.vapt
        )
        db.commit()

        assert client.organization_id == org.id
        assert project.client_id == client.id
        assert project.service_type == ServiceType.vapt
        state = db.query(EngagementState).filter_by(project_id=project.id).first()
        assert state is not None


class TestBoundaryGrep:
    """Verify no offensive-concept symbols live inside app/engagementcore/."""

    _FORBIDDEN = re.compile(
        r"\b(opsec|c2\b|killchain|kill_chain|exploit_phase|attack_narrative"
        r"|offensive_specialist|c2_tier)\b",
        re.IGNORECASE,
    )
    _CORE_DIR = Path("app/engagementcore")

    def test_no_offensive_symbols_in_engagementcore(self):
        violations = []
        for py_file in self._CORE_DIR.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for lineno, line in enumerate(content.splitlines(), 1):
                if self._FORBIDDEN.search(line):
                    violations.append(f"{py_file}:{lineno}: {line.strip()}")

        assert not violations, (
            "Offensive symbols found in engagementcore — move them to the VAPT pack:\n"
            + "\n".join(violations)
        )
