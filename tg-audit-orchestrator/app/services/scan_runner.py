"""PT-Orc command builder and import helper.

Scans are run manually in a terminal by the analyst/lead.
This module only: generates the shell commands to copy-paste,
and registers/imports results once the operator points us at a run directory.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.scan import ScanJob, ScanJobStatus

# ── Phase catalogue ────────────────────────────────────────────────────────────
PHASE_SCRIPTS: dict[str, tuple[str, str, str]] = {
    # key: (script, label, role)  role = who normally runs this
    "01": ("01_dns_recon.sh",      "DNS Recon",            "analyst"),
    "02": ("02_ip_analysis.sh",    "IP & ASN Analysis",    "analyst"),
    "03": ("03_comp_scan.sh",      "Comprehensive Port Scan","lead"),
    "04": ("04_tls_scan.sh",       "TLS / Certificate Review","analyst"),
    "05": ("05_web_enum.sh",       "Web Enumeration",      "analyst"),
    "06": ("06_wpscan.sh",         "WordPress Scan",       "analyst"),
    "07": ("07_service_verify.sh", "Service Verification", "analyst"),
    "08": ("08_app_api_review.sh", "App / API Review",     "lead"),
    "09": ("09_ai_llm_review.sh",  "AI / LLM Review",      "lead"),
}

# Phases that take --host instead of --targets
_HOST_FLAG = {"08", "09"}
# Phases that accept --tier
_TIER_PHASES = {"03", "04", "05", "08", "09"}

# Role → which phases are pre-selected by default
ROLE_DEFAULT_PHASES: dict[str, list[str]] = {
    "lead_consultant":  ["01","02","03","04","05","07","08","09"],
    "analyst":          ["01","02","04","05","07"],
    "senior_reviewer":  [],   # reviewer does not scan; imports results only
    "pm":               [],
    "default":          ["08","09"],
}


def build_command(
    scripts_dir: str,
    phase: str,
    host: str,
    tier: str = "standard",
    api_key: Optional[str] = None,
    output_dir: str = "./run",
) -> str:
    """Return the full bash command string for a single phase."""
    if phase not in PHASE_SCRIPTS:
        return f"# Unknown phase: {phase}"
    script, _, _ = PHASE_SCRIPTS[phase]
    host_flag = "--host" if phase in _HOST_FLAG else "--targets"
    parts = [f"bash {scripts_dir}/{script}", f"{host_flag} {host}", "--yes"]
    if phase in _TIER_PHASES:
        parts.append(f"--tier {tier}")
    if phase == "09" and api_key:
        parts.append(f"--api-key {api_key}")
    return " ".join(parts)


def build_report_pack_command(
    scripts_dir: str,
    project_id: str,
    output_dir: str = "./run",
) -> str:
    return (
        f"bash {scripts_dir}/12_report_pack.sh"
        f" --project-id {project_id}"
        f" --output-dir {output_dir}"
    )


def register_import(
    db: Session,
    project_id: str,
    run_dir: str,
    host: str,
    phases: list[str],
    tier: str,
    user_id: Optional[str],
) -> ScanJob:
    """Create a ScanJob record for a completed manual scan and import its results."""
    job = ScanJob(
        project_id=project_id,
        host=host,
        phases=phases,
        tier=tier,
        status=ScanJobStatus.running.value,
        triggered_by=user_id,
        run_dir=run_dir,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    run_path = Path(run_dir)
    try:
        from ptorc_adapter.importer import run_import
        result = run_import(db, project_id, run_path)
        job.import_result = {
            "findings_created": len(result.findings_created),
            "findings_updated": len(result.findings_updated),
            "evidence_items":   len(result.evidence_items),
            "scope_items":      len(result.scope_items),
            "run_id":           result.run_id,
        }
        job.status = ScanJobStatus.completed.value
    except Exception as exc:
        job.status = ScanJobStatus.failed.value
        job.error_message = str(exc)[:500]

    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def tail_log(job: ScanJob, lines: int = 80) -> str:
    """Return last N lines of the import log for a job."""
    if job.log_path:
        try:
            text = Path(job.log_path).read_text(encoding="utf-8", errors="replace")
            all_lines = text.splitlines()
            return "\n".join(all_lines[-lines:])
        except FileNotFoundError:
            pass
    if job.error_message:
        return f"Error: {job.error_message}"
    if job.import_result:
        import json
        return json.dumps(job.import_result, indent=2)
    return "(no log available)"
