"""CLI backup script — creates a timestamped archive of DB + evidence.

Usage:
    python scripts/backup.py [--label "pre-release"]

For PostgreSQL databases the script prints the equivalent pg_dump command
instead of attempting a Python-level dump.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.ops.backup import backup_sqlite


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup DB + evidence store")
    parser.add_argument("--label", default="", help="Human-readable label for the backup")
    parser.add_argument("--out", default="", help="Archive path (default: BACKUP_DIR/backup_<ts>.tar.gz)")
    args = parser.parse_args()

    db_url: str = settings.database_url

    if not db_url.startswith("sqlite"):
        print("PostgreSQL detected — use pg_dump instead:")
        print(f"  pg_dump '{db_url}' | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz")
        sys.exit(0)

    db_path = Path(db_url.replace("sqlite:///", ""))
    evidence_root = Path("data/evidence")
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = Path(args.out) if args.out else backup_dir / f"backup_{ts}.tar.gz"

    result = backup_sqlite(db_path, evidence_root, archive_path, label=args.label or ts)
    print(f"Backup created: {result}")
    print(f"  DB: {db_path} (exists={db_path.exists()})")
    print(f"  Evidence: {evidence_root} (exists={evidence_root.exists()})")


if __name__ == "__main__":
    main()
