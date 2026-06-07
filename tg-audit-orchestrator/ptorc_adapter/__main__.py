"""CLI entry point: python -m ptorc_adapter --project <id> --run-dir <path>"""
import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a PT-Orc run directory into TG Audit Orchestrator"
    )
    parser.add_argument("--project", required=True, help="Project ID (UUID)")
    parser.add_argument("--run-dir", required=True, help="Path to PT-Orc run directory")
    args = parser.parse_args()

    from app.db import SessionLocal
    from ptorc_adapter.importer import run_import

    db = SessionLocal()
    try:
        result = run_import(db, args.project, Path(args.run_dir))
    except (ValueError, FileNotFoundError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

    print("PT-Orc import complete")
    print(f"  Scope items : {len(result.scope_items)} (pending approval)")
    print(f"  Evidence    : {len(result.evidence_items)}")
    print(f"  Findings    : {len(result.findings)} (in_review)")
    print(f"  Deliverable : {result.deliverable_id}")


if __name__ == "__main__":
    main()
