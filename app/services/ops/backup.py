"""Backup and restore — SQLite DB file + evidence store → tar.gz archive.

For PostgreSQL deployments, use pg_dump / pg_restore instead; the CLI
scripts (scripts/backup.py, scripts/restore.py) detect the DB URL and
print the appropriate pg_dump command rather than attempting a Python-level
dump of a remote Postgres instance.
"""
from __future__ import annotations

import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_DB_MEMBER = "db/app.db"
_EVIDENCE_MEMBER = "evidence"
_MANIFEST_MEMBER = "manifest.json"


def backup_sqlite(
    src_db_path: Path,
    evidence_root: Path,
    archive_path: Path,
    *,
    label: Optional[str] = None,
) -> Path:
    """Create a tar.gz backup of a SQLite DB file + evidence directory.

    Args:
        src_db_path:   Path to the SQLite .db file.
        evidence_root: Path to the evidence store root directory.
        archive_path:  Destination .tar.gz path (parent dirs created if needed).
        label:         Optional human-readable label stored in the manifest.

    Returns:
        The path to the created archive.
    """
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label or "",
        "db_included": src_db_path.exists(),
        "evidence_included": evidence_root.exists(),
    }

    with tarfile.open(archive_path, "w:gz") as tar:
        # DB file
        if src_db_path.exists():
            tar.add(src_db_path, arcname=_DB_MEMBER)

        # Evidence tree (may be empty)
        if evidence_root.exists():
            tar.add(evidence_root, arcname=_EVIDENCE_MEMBER)

        # Manifest
        manifest_bytes = json.dumps(manifest, indent=2).encode()
        import io
        info = tarfile.TarInfo(name=_MANIFEST_MEMBER)
        info.size = len(manifest_bytes)
        tar.addfile(info, io.BytesIO(manifest_bytes))

    return archive_path


def restore_sqlite(
    archive_path: Path,
    dest_db_path: Path,
    dest_evidence_root: Path,
) -> dict:
    """Restore a SQLite DB and evidence tree from a tar.gz backup.

    Args:
        archive_path:      Path to the .tar.gz archive produced by backup_sqlite.
        dest_db_path:      Destination path for the restored .db file.
        dest_evidence_root: Destination root for the restored evidence tree.

    Returns:
        The manifest dict extracted from the archive.
    """
    dest_db_path.parent.mkdir(parents=True, exist_ok=True)
    dest_evidence_root.mkdir(parents=True, exist_ok=True)

    manifest: dict = {}

    with tarfile.open(archive_path, "r:gz") as tar:
        members = {m.name: m for m in tar.getmembers()}

        # Restore DB
        if _DB_MEMBER in members:
            member = members[_DB_MEMBER]
            f = tar.extractfile(member)
            if f:
                dest_db_path.write_bytes(f.read())

        # Restore evidence tree
        evidence_members = [
            m for m in tar.getmembers()
            if m.name.startswith(_EVIDENCE_MEMBER + "/") or m.name == _EVIDENCE_MEMBER
        ]
        for m in evidence_members:
            rel = m.name[len(_EVIDENCE_MEMBER):].lstrip("/")
            if not rel:
                continue
            dest = dest_evidence_root / rel
            if m.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            elif m.isfile():
                dest.parent.mkdir(parents=True, exist_ok=True)
                f = tar.extractfile(m)
                if f:
                    dest.write_bytes(f.read())

        # Read manifest
        if _MANIFEST_MEMBER in members:
            f = tar.extractfile(members[_MANIFEST_MEMBER])
            if f:
                manifest = json.loads(f.read())

    return manifest
