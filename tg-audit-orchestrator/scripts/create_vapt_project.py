"""
Create a new client + VAPT project in TG Audit Orchestrator.

Usage:
    python scripts/create_vapt_project.py \
        --client "Acme Corp" \
        --domains "app.acme.com api.acme.com" \
        --ips "203.0.113.10"

Prints the project UUID on stdout (last line).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app.models  # noqa: F401 — register all ORM models
from app.db import SessionLocal, engine, Base
from app.models.clients import Client, Project, ServiceType
from app.models.users import User


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client",  required=True, help="Client / company name")
    parser.add_argument("--domains", default="", help="Space-separated in-scope domains")
    parser.add_argument("--ips",     default="", help="Space-separated in-scope IPs")
    parser.add_argument("--summary", default="", help="Scope summary (optional)")
    args = parser.parse_args()

    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        # Find the admin user (owner for the project)
        admin = db.query(User).filter(User.is_active == True).first()  # noqa: E712
        if admin is None:
            print("[ERROR] No active user found. Run 'python scripts/seed.py' first.",
                  file=sys.stderr)
            sys.exit(1)

        # Upsert client
        client = db.query(Client).filter_by(entity_name=args.client).first()
        if client is None:
            client = Client(entity_name=args.client, sector="unknown")
            db.add(client)
            db.flush()
            print(f"  Client created : {client.entity_name}  (id={client.id[:8]}…)")
        else:
            print(f"  Client exists  : {client.entity_name}  (id={client.id[:8]}…)")

        # Scope summary
        domains = args.domains.strip()
        ips = args.ips.strip()
        parts = []
        if domains:
            parts.append(f"domains: {domains}")
        if ips:
            parts.append(f"IPs: {ips}")
        scope_summary = args.summary or (
            f"External VAPT — {', '.join(parts)}" if parts else "External VAPT"
        )

        # Create project
        project = Project(
            client_id=client.id,
            service_type=ServiceType.vapt,
            owner_id=admin.id,
            status="draft",
            scope_summary=scope_summary,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        print(f"  Project created: id={project.id}")
        print(f"  Scope summary  : {scope_summary}")
        print(f"  Owner          : {admin.email}")
        # Last line must be the bare UUID — vapt_run.sh reads it
        print(project.id)


if __name__ == "__main__":
    main()
