# MVP_ORCA — TechGuard Labs Pentest Audit Platform

Complete bundle of all components required to run the TG Audit Orchestrator MVP.

---

## Directory Structure

```
MVP_ORCA/
├── tg-audit-orchestrator/   ← Main web platform (FastAPI + SQLite + HTMX)
├── pt-orc/                  ← PT-Orc scan engine (bash phase scripts)
└── tools/
    └── jq                   ← Python jq shim (required by PT-Orc scripts)
```

---

## Quick Start

### 1. Install the jq shim

```bash
cp tools/jq ~/.local/bin/jq
chmod +x ~/.local/bin/jq
```

### 2. Set up the Python environment

```bash
cd tg-audit-orchestrator
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Initialize the database

```bash
alembic upgrade head
# or first-run bootstrap:
python -m app.bootstrap
```

### 4. Start the platform

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 — default admin: `admin` / `admin123`

---

## PT-Orc Integration

The web UI triggers PT-Orc scans from **Projects → PT-Orc Scans → New Scan**.

The scan runner (`tg-audit-orchestrator/app/services/scan_runner.py`) expects the PT-Orc scripts at:

```
/home/kali/audit-orc-vapt/pt-orc/scripts/
```

If you move this bundle, update the `SCRIPTS_DIR` constant in `scan_runner.py` to point to `MVP_ORCA/pt-orc/scripts/`.

### Phase scripts included

| Phase | Script | Description |
|-------|--------|-------------|
| 01 | `01_dns_recon.sh` | DNS Reconnaissance |
| 02 | `02_ip_analysis.sh` | IP Analysis |
| 03 | `03_comp_scan.sh` | Comprehensive Scan |
| 04 | `04_tls_scan.sh` | TLS Review |
| 05 | `05_web_enum.sh` | Web Enumeration |
| 06 | `06_wpscan.sh` | WordPress Scan |
| 07 | `07_service_verify.sh` | Service Verification |
| 08 | `08_app_api_review.sh` | App / API Review |
| 09 | `09_ai_llm_review.sh` | AI / LLM Review |
| 12 | `12_report_pack.sh` | Report Packaging + Import |

---

## Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `PTORC_ALLOW_NON_ROOT=1` | Bypasses root check in all phase scripts |
| `SCAN_EVIDENCE_DIR` | Redirect evidence output to job workspace |
| `EVIDENCE_BASE` | Where report_pack reads evidence from |
| `SCAN_WORKING_DIR` | Where report_pack reads findings from |

These are set automatically by the scan runner for each job.

---

## Team Credentials (VAPT Demo Project)

| User | Role | Email | Password |
|------|------|-------|----------|
| Hari | Manager/PM | hari@acmecorp.local | Hari@2024! |
| Surya | Lead Consultant | surya@techguardlabs.com | Surya@2024! |
| Shivani | Consultant | shivani@techguardlabs.com | Shivani@2024! |
| Srimithila | Consultant | srimithila@techguardlabs.com | Srimithila@2024! |

Recreate users + sample project: `python scripts/setup_team_vapt.py`

---

## Components Summary

| Component | Version | Location |
|-----------|---------|----------|
| TG Audit Orchestrator | v0.8.1 | `tg-audit-orchestrator/` |
| PT-Orc Scripts | VAPT-enhanced | `pt-orc/scripts/` |
| Python jq shim | v2 | `tools/jq` |
