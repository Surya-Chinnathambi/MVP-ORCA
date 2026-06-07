"""Shared pytest fixtures for Stage 14+.

Provides an org → client → project factory so later tests don't have
to re-implement the boilerplate tenant setup.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers models + listeners
from app.db import Base
from app.models.clients import Client, Project, ServiceType
from app.models.organization import Organization
from app.models.users import Role, RoleName, User
from app.services.auth import hash_password


@pytest.fixture(scope="session")
def shared_engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)


@pytest.fixture(scope="session")
def shared_session(shared_engine):
    Sess = sessionmaker(bind=shared_engine, autocommit=False, autoflush=False)
    db = Sess()
    # Seed roles once
    for name in [r.value for r in RoleName]:
        db.add(Role(name=name))
    admin = User(
        email="conftest_admin@test.local",
        password_hash=hash_password("testpass"),
        full_name="Conftest Admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    yield db, admin.id
    db.close()


def make_org(db: Session, *, name: str = "Test Org") -> Organization:
    org = Organization(name=name, display_name=name)
    db.add(org)
    db.flush()
    return org


def make_client(db: Session, *, org: Organization, name: str = "Test Client") -> Client:
    client = Client(entity_name=name, organization_id=org.id)
    db.add(client)
    db.flush()
    return client


def make_project(
    db: Session,
    *,
    client: Client,
    owner_id: str,
    service_type: ServiceType = ServiceType.dpdp,
    status: str = "setup",
) -> Project:
    project = Project(
        client_id=client.id,
        service_type=service_type,
        owner_id=owner_id,
        status=status,
    )
    db.add(project)
    db.flush()
    return project
