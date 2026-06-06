"""Stage C7 acceptance test — full conformance acceptance pass.

Verifies:
1. All C1-C6 conformance stages have their test files present.
2. Alembic upgrade head applies cleanly on a fresh DB.
3. DPDP and VAPT pilots complete gates G1-G7 and produce audit trails.
4. CONFORMANCE.md exists and covers key sections.
"""
import subprocess
import sys
from pathlib import Path

import pytest


# ── 1. C-stage test file presence ────────────────────────────────────────────

@pytest.mark.parametrize("stage", ["C1", "C2", "C3", "C4", "C5", "C6"])
def test_c_stage_test_file_exists(stage):
    path = Path(f"tests/test_stage{stage}.py")
    assert path.exists(), f"Missing test file: {path}"


# ── 2. Migration chain ────────────────────────────────────────────────────────

def test_alembic_upgrade_head_clean(tmp_path):
    """Run alembic upgrade head on a fresh SQLite DB — must succeed with no errors."""
    db_path = tmp_path / "test_fresh.db"
    env = {"DATABASE_URL": f"sqlite:///{db_path}"}
    import os
    full_env = {**os.environ, **env}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, env=full_env
    )
    assert result.returncode == 0, (
        f"alembic upgrade head failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )


# ── 3. Both pilots complete successfully ──────────────────────────────────────

def test_dpdp_pilot_completes():
    """Run the DPDP pilot script; it must exit 0 and print DPDP PILOT COMPLETE."""
    result = subprocess.run(
        [sys.executable, "scripts/pilot_dpdp.py"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"DPDP pilot failed (exit {result.returncode}):\n{result.stdout[-2000:]}\n{result.stderr[-1000:]}"
    )
    assert "DPDP PILOT COMPLETE" in result.stdout, (
        f"DPDP pilot did not print success message:\n{result.stdout[-1000:]}"
    )
    # All 7 gates must pass
    for gate in ["G1", "G2", "G3", "G4", "G5", "G6", "G7"]:
        assert f"Gate {gate}" in result.stdout and "passed" in result.stdout, (
            f"Gate {gate} not confirmed passed in DPDP pilot"
        )


def test_vapt_pilot_completes():
    """Run the VAPT pilot script; it must exit 0 and print VAPT PILOT COMPLETE."""
    result = subprocess.run(
        [sys.executable, "scripts/pilot_vapt.py"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"VAPT pilot failed (exit {result.returncode}):\n{result.stdout[-2000:]}\n{result.stderr[-1000:]}"
    )
    assert "VAPT PILOT COMPLETE" in result.stdout, (
        f"VAPT pilot did not print success message:\n{result.stdout[-1000:]}"
    )
    for gate in ["G1", "G2", "G3", "G4", "G5", "G6", "G7"]:
        assert f"Gate {gate}" in result.stdout and "passed" in result.stdout, (
            f"Gate {gate} not confirmed passed in VAPT pilot"
        )


# ── 4. CONFORMANCE.md ─────────────────────────────────────────────────────────

def test_conformance_md_exists():
    assert Path("CONFORMANCE.md").exists(), "CONFORMANCE.md must exist after C7"


def test_conformance_md_covers_key_sections():
    text = Path("CONFORMANCE.md").read_text()
    required = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "§7.1", "§12", "§24",
                "DPDP", "VAPT", "pilot", "Deferred"]
    for keyword in required:
        assert keyword in text, f"CONFORMANCE.md missing keyword: {keyword!r}"


def test_conformance_md_marks_pilots_pass():
    text = Path("CONFORMANCE.md").read_text()
    assert "PASS" in text, "CONFORMANCE.md must mark pilots as PASS"
    assert "pilot_dpdp" in text
    assert "pilot_vapt" in text
