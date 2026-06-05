"""Seed initial data: 8 roles + admin user. Safe to run multiple times."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import bcrypt as _bcrypt

from app.config import settings
from app.db import SessionLocal, engine, Base
import app.models  # noqa: F401
from app.models.users import Role, User, RoleName


def _hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()

ROLE_NAMES = [r.value for r in RoleName]


def seed() -> None:
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        # Upsert roles
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
            db.commit()
            print(f"Created admin user: {settings.admin_email}")
        else:
            db.commit()
            print(f"Admin user already exists: {settings.admin_email}")

        print(f"Roles seeded: {added_roles or '(all present)'}")


if __name__ == "__main__":
    seed()
