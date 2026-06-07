"""Seed initial data: 10 canonical roles + admin user + agent sentinel. Safe to re-run."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import bcrypt as _bcrypt

from app.config import settings
from app.db import SessionLocal, engine, Base
import app.models  # noqa: F401
from app.models.users import Role, User, RoleName

AGENT_SENTINEL_EMAIL = "agent@system.internal"
AGENT_SENTINEL_NAME = "System Agent"

def _hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()

# Exactly the 10 roles from RBAC.md §1
ROLE_NAMES = [r.value for r in RoleName]


def seed() -> None:
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        # Upsert the 10 canonical roles
        existing_roles = {r.name for r in db.query(Role).all()}
        added_roles = []
        for name in ROLE_NAMES:
            if name not in existing_roles:
                db.add(Role(name=name))
                added_roles.append(name)
        db.flush()

        # Upsert admin user
        admin = db.query(User).filter_by(email=settings.admin_email).first()
        if admin is None:
            admin = User(
                email=settings.admin_email,
                password_hash=_hash_password(settings.admin_password),
                full_name="TG Admin",
                is_active=True,
            )
            db.add(admin)
            print(f"Created admin user: {settings.admin_email}")
        else:
            print(f"Admin user already exists: {settings.admin_email}")

        # Upsert agent sentinel user (inactive — cannot log in)
        sentinel = db.query(User).filter_by(email=AGENT_SENTINEL_EMAIL).first()
        if sentinel is None:
            sentinel = User(
                email=AGENT_SENTINEL_EMAIL,
                password_hash=_hash_password(os.urandom(32).hex()),
                full_name=AGENT_SENTINEL_NAME,
                is_active=False,
            )
            db.add(sentinel)
            print(f"Created agent sentinel user: {AGENT_SENTINEL_EMAIL}")
        else:
            print(f"Agent sentinel already exists: {AGENT_SENTINEL_EMAIL}")

        db.commit()
        print(f"Roles seeded: {added_roles or '(all present)'}")


if __name__ == "__main__":
    seed()
