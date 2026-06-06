"""Scan runner — executes PT-Orc phase scripts in a background thread,
then auto-imports the run directory into the project."""
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.scan import ScanJob, ScanJobStatus

SCRIPTS_DIR = Path("/home/kali/audit-orc-vapt/pt-orc/scripts")
LOGS_DIR = Path("data/scan_jobs")

# phase_key → (script_filename, label)
PHASE_SCRIPTS: dict[str, tuple[str, str]] = {
    "01": ("01_dns_recon.sh",       "DNS Recon"),
    "02": ("02_ip_analysis.sh",     "IP Analysis"),
    "03": ("03_comp_scan.sh",       "Comprehensive Scan"),
    "04": ("04_tls_scan.sh",        "TLS Review"),
    "05": ("05_web_enum.sh",        "Web Enumeration"),
    "06": ("06_wpscan.sh",          "WordPress Scan"),
    "07": ("07_service_verify.sh",  "Service Verification"),
    "08": ("08_app_api_review.sh",  "App / API Review"),
    "09": ("09_ai_llm_review.sh",   "AI / LLM Review"),
}

# Phases that use --host instead of --targets
_HOST_FLAG_PHASES = {"08", "09"}
# Phases that accept --tier
_TIER_PHASES = {"03", "04", "05", "08", "09"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_args(phase: str, host: str, tier: str, api_key: Optional[str]) -> list[str]:
    host_flag = "--host" if phase in _HOST_FLAG_PHASES else "--targets"
    args = [host_flag, host, "--yes"]
    if phase in _TIER_PHASES:
        args += ["--tier", tier]
    if phase == "09" and api_key:
        args += ["--api-key", api_key]
    return args


def _write_log(log_path: Path, text: str) -> None:
    with open(log_path, "a", encoding="utf-8") as f:
        ts = datetime.now().strftime("%H:%M:%S")
        f.write(f"[{ts}] {text}\n")


def _run_script(
    script: Path,
    args: list[str],
    log_path: Path,
    cwd: Path,
    extra_env: Optional[dict] = None,
) -> int:
    """Run a shell script, stream stdout+stderr to log_path. Returns exit code."""
    cmd = ["/bin/bash", str(script)] + args
    _write_log(log_path, f"$ {' '.join(cmd)}")
    env = extra_env if extra_env is not None else os.environ.copy()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        for line in iter(proc.stdout.readline, ""):
            _write_log(log_path, line.rstrip())
        proc.wait()
        _write_log(log_path, f"[exit {proc.returncode}]")
        return proc.returncode
    except Exception as exc:
        _write_log(log_path, f"[ERROR launching script: {exc}]")
        return 1


def _find_run_dir(project_id: str, search_roots: Optional[list[Path]] = None) -> Optional[Path]:
    """Return most recent run directory matching project_id across search_roots."""
    roots = search_roots if search_roots else [SCRIPTS_DIR / "run"]
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        candidates.extend(
            d for d in root.iterdir()
            if d.is_dir() and d.name.startswith(project_id)
        )
    if not candidates:
        return None
    return sorted(candidates, key=lambda d: d.stat().st_mtime, reverse=True)[0]


def _execute_job(job_id: str) -> None:
    """Background thread: runs all phases in a per-job workspace, then auto-imports."""
    db: Session = SessionLocal()
    try:
        job: ScanJob = db.get(ScanJob, job_id)
        if job is None:
            return

        # Per-job writable workspace — must be absolute so scripts don't double-prefix
        workspace = LOGS_DIR.resolve() / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        evidence_dir = workspace / "evidence"
        working_dir  = workspace / "working"
        run_dir_root = workspace / "run"
        for d in (evidence_dir, working_dir, run_dir_root):
            d.mkdir(parents=True, exist_ok=True)

        log_path = LOGS_DIR / f"{job_id}.log"
        job.log_path = str(log_path)
        job.status = ScanJobStatus.queued.value
        db.commit()

        _write_log(log_path, f"=== Scan job {job_id} starting ===")
        _write_log(log_path, f"    Host      : {job.host}")
        _write_log(log_path, f"    Phases    : {job.phases}")
        _write_log(log_path, f"    Tier      : {job.tier}")
        _write_log(log_path, f"    Workspace : {workspace}")

        job.status = ScanJobStatus.running.value
        job.started_at = _now()
        db.commit()

        # Base env: bypass root check + redirect all write paths to job workspace
        base_env = os.environ.copy()
        # Ensure ~/.local/bin is first in PATH so our Python jq shim is found
        local_bin = str(Path.home() / ".local" / "bin")
        base_env["PATH"] = f"{local_bin}:{base_env.get('PATH', '/usr/bin:/bin')}"
        base_env["PTORC_ALLOW_NON_ROOT"] = "1"
        base_env["SCAN_EVIDENCE_DIR"]    = str(evidence_dir)   # 08/09: evidence output
        base_env["EVIDENCE_BASE"]        = str(evidence_dir)   # report_pack: evidence read
        base_env["SCAN_WORKING_DIR"]     = str(working_dir)    # report_pack: findings read
        # Phase 08/09 write 'working/' relative to cwd → workspace/working/ ✓

        # Run each selected phase
        failed = False
        for phase in job.phases:
            if phase not in PHASE_SCRIPTS:
                _write_log(log_path, f"[WARN] Unknown phase '{phase}', skipping")
                continue
            script_name, label = PHASE_SCRIPTS[phase]
            script_path = SCRIPTS_DIR / script_name
            if not script_path.exists():
                _write_log(log_path, f"[WARN] Script not found: {script_path}, skipping")
                continue
            _write_log(log_path, f"\n{'='*50}")
            _write_log(log_path, f"  Phase {phase}: {label}")
            _write_log(log_path, f"{'='*50}")
            args = _build_args(phase, job.host, job.tier, job.api_key)
            rc = _run_script(script_path, args, log_path, cwd=workspace, extra_env=base_env)
            if rc != 0:
                _write_log(log_path, f"[WARN] Phase {phase} exited {rc} — continuing")

        # Run report pack (always, even if phases had warnings)
        report_script = SCRIPTS_DIR / "12_report_pack.sh"
        if report_script.exists():
            _write_log(log_path, f"\n{'='*50}")
            _write_log(log_path, "  Phase 12: Report Pack")
            _write_log(log_path, f"{'='*50}")
            rc = _run_script(
                report_script,
                ["--project-id", job.project_id, "--output-dir", str(run_dir_root)],
                log_path,
                cwd=workspace,
                extra_env=base_env,
            )
            if rc != 0:
                _write_log(log_path, f"[ERROR] report_pack.sh exited {rc}")
                failed = True
        else:
            _write_log(log_path, "[ERROR] 12_report_pack.sh not found")
            failed = True

        if not failed:
            # Find run directory (created by report_pack inside run_dir_root or SCRIPTS_DIR/run)
            run_dir = _find_run_dir(job.project_id, search_roots=[run_dir_root, SCRIPTS_DIR / "run"])
            if run_dir is None:
                _write_log(log_path, "[ERROR] Could not find run directory to import")
                failed = True
            else:
                job.run_dir = str(run_dir)
                db.commit()
                _write_log(log_path, f"\n{'='*50}")
                _write_log(log_path, f"  Auto-importing from {run_dir.name}")
                _write_log(log_path, f"{'='*50}")
                try:
                    from ptorc_adapter.importer import run_import
                    result = run_import(db, job.project_id, run_dir)
                    import_summary = {
                        "findings_created": len(result.findings_created),
                        "findings_updated": len(result.findings_updated),
                        "evidence_items":   len(result.evidence_items),
                        "scope_items":      len(result.scope_items),
                        "run_id":           result.run_id,
                    }
                    job.import_result = import_summary
                    _write_log(log_path, f"[OK] Import complete: {import_summary}")
                except Exception as exc:
                    _write_log(log_path, f"[ERROR] Import failed: {exc}")
                    job.error_message = f"Import error: {exc}"
                    failed = True

        job.status = ScanJobStatus.failed.value if failed else ScanJobStatus.completed.value
        job.finished_at = _now()
        db.commit()
        _write_log(log_path, f"\n=== Job {job.status.upper()} ===")

    except Exception as exc:
        try:
            job = db.get(ScanJob, job_id)
            if job:
                job.status = ScanJobStatus.failed.value
                job.error_message = str(exc)
                job.finished_at = _now()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def trigger_scan(
    db: Session,
    project_id: str,
    host: str,
    phases: list[str],
    tier: str,
    api_key: Optional[str],
    user_id: Optional[str],
) -> ScanJob:
    """Create a ScanJob row and start the background execution thread."""
    job = ScanJob(
        project_id=project_id,
        host=host,
        phases=phases,
        tier=tier,
        api_key=api_key or None,
        status=ScanJobStatus.queued.value,
        triggered_by=user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(target=_execute_job, args=(job.id,), daemon=True)
    thread.start()
    return job


def tail_log(job: ScanJob, lines: int = 80) -> str:
    """Return the last N lines from the combined scan log (launcher + sweep log)."""
    parts: list[str] = []

    # Main launcher log
    if job.log_path:
        try:
            parts.append(Path(job.log_path).read_text(encoding="utf-8", errors="replace"))
        except FileNotFoundError:
            pass
        except Exception as exc:
            parts.append(f"(launcher log error: {exc})")

    # PT-Orc sweep log (evidence/_sweep/*.log inside the workspace)
    workspace = Path(job.log_path).parent if job.log_path else None
    if workspace:
        sweep_logs = sorted(
            workspace.rglob("_sweep/*.log"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
        )
        for sl in sweep_logs[-1:]:  # only most recent sweep log
            try:
                parts.append(f"\n─── PT-Orc sweep log: {sl.name} ───\n")
                parts.append(sl.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass

    if not parts:
        return "(log not yet available)"
    combined = "\n".join(parts)
    all_lines = combined.splitlines()
    return "\n".join(all_lines[-lines:])
