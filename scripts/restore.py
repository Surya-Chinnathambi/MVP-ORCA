"""CLI restore script — restores DB + evidence from a backup archive.

Usage:
    python scripts/restore.py path/to/backup_20260605_120000.tar.gz

WARNING: This overwrites the current DB file and evidence store.
         Stop the application before running a restore.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.ops.backup import restore_sqlite


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/restore.py <archive.tar.gz>")
        sys.exit(1)

    archive_path = Path(sys.argv[1])
    if not archive_path.exists():
        print(f"Error: archive not found: {archive_path}")
        sys.exit(1)

    db_url: str = settings.database_url
    if not db_url.startswith("sqlite"):
        print("PostgreSQL detected — use pg_restore instead:")
        print(f"  gunzip -c {archive_path} | psql '{db_url}'")
        sys.exit(0)

    db_path = Path(db_url.replace("sqlite:///", ""))
    evidence_root = Path("data/evidence")

    print(f"Restoring from: {archive_path}")
    print(f"  DB target:       {db_path}")
    print(f"  Evidence target: {evidence_root}")
    print("  (stop the application before restoring)")

    confirm = input("Type YES to continue: ")
    if confirm.strip() != "YES":
        print("Aborted.")
        sys.exit(0)

    manifest = restore_sqlite(archive_path, db_path, evidence_root)
    print(f"Restore complete.")
    print(f"  Backup created at: {manifest.get('created_at', 'unknown')}")
    print(f"  Label: {manifest.get('label', '')}")


if __name__ == "__main__":
    main()
