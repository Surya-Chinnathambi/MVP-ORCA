# TG Audit Orchestrator

Compliance and security audit management platform for DPDP and VAPT engagements.

Manages the full audit lifecycle: scope definition → evidence collection → findings → human approval gates → deliverables → closure. Integrates with PT-Orc for VAPT recon import.

---

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env        # then fill in SECRET_KEY and CLAUDE_API_KEY
mkdir -p data
python scripts/seed.py      # after Stage 1
uvicorn app.main:app --reload
```

## System dependencies (install once)

```bash
sudo apt install -y tesseract-ocr poppler-utils
```

## Build stages

| Stage | Goal |
|---|---|
| 0 | Scaffold + env |
| 1 | Data model + migrations |
| 2 | Auth + audit/approval gateway |
| 3 | Clients / projects / scope |
| 4 | Framework library + methodology engine |
| 5 | Requirements / tasks / evidence-request tracker |
| 6 | Evidence manager + processor |
| 7 | Findings register |
| 8 | Approval workflow + QA agent |
| 9 | PT-Orc adapter |
| 10 | Deliverable builder |
| 11 | Web UI |
| 12 | Telegram bot |
| 13 | Pilot dry run + MVP acceptance |

See `BUILD_INSTRUCTIONS.md` for full stage specs and acceptance tests.

---

## Run a pilot

Two standalone scripts exercise the full audit chain against a fresh SQLite database.

### DPDP readiness pilot

```bash
source .venv/bin/activate
mkdir -p data
python scripts/pilot_dpdp.py
```

What it does:
1. Seeds roles + admin user
2. Creates client (Acme Fintech) + DPDP project
3. Adds and approves a scope item (Gate G1)
4. Loads DPDP pack, generates requirements / evidence requests / tasks
5. Marks evidence requests received (Gate G2)
6. Ingests a sample privacy notice text file, accepts it (Gate G3)
7. Creates a HIGH-severity finding linked to evidence, approves severity (Gate G4)
8. Runs the QA agent (Gate G5)
9. Generates gap matrix (XLSX+HTML), roadmap (MD+HTML), report (HTML)
10. Approves report release (Gate G6)
11. Closes engagement with residual risk approval (Gate G7)

Output files land in `data/pilot_dpdp_out/`.

### VAPT external assessment pilot

```bash
source .venv/bin/activate
mkdir -p data
python scripts/pilot_vapt.py
```

What it does:
1. Seeds roles + admin user
2. Creates client (Skyline Commerce) + VAPT project
3. Adds and approves a scope item (Gate G1)
4. Loads VAPT pack, generates plan
5. Imports a PT-Orc fixture run directory (scope, evidence, 2 findings) via the adapter
6. Approves imported scope items; marks evidence received + accepted (Gates G2 + G3)
7. Approves all imported findings (source=ptorc, no auto-approve), adds remediations (Gate G4)
8. Runs QA agent (Gate G5)
9. Generates deliverables, approves report release (Gate G6)
10. Closes with residual risk (Gate G7)

Output files land in `data/pilot_vapt_out/`.

### MVP acceptance criteria

Both pilots demonstrate the full chain:

| Step | DPDP | VAPT |
|---|---|---|
| Client + project setup | ✓ | ✓ |
| Scope definition + G1 approval | ✓ | ✓ |
| Pack selection + plan generation | ✓ | ✓ |
| Evidence request tracking + G2 | ✓ | ✓ |
| Evidence ingestion / PT-Orc import + G3 | ✓ | ✓ |
| Findings + severity approval + G4 | ✓ | ✓ |
| QA agent + G5 | ✓ | ✓ |
| Report + roadmap + gap matrix generation | ✓ | ✓ |
| Report release approval + G6 | ✓ | ✓ |
| Closure with residual risk + G7 | ✓ | ✓ |
| Complete audit trail for every change | ✓ | ✓ |

---

## Deployment (TechGuard Labs internal)

### Environment profiles

Set `APP_ENV` in `.env`:

| Value | Meaning |
|---|---|
| `dev` | Local development — no strict secret enforcement |
| `test` | Automated test runs — SQLite, fakeredis |
| `prod` | Production — enforces `SECRET_KEY` + `ENCRYPTION_KEY` at startup |

### Production checklist

```bash
# 1. Generate secrets
python -c "import secrets; print(secrets.token_hex(32))"          # → SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # → ENCRYPTION_KEY

# 2. Set APP_ENV=prod in .env

# 3. Run DB migrations from a clean state
alembic upgrade head

# 4. Seed roles + admin user
python scripts/seed.py

# 5. Start app
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

The application performs a startup self-check and will **refuse to start** in `prod`
mode if `SECRET_KEY` is the placeholder value or `ENCRYPTION_KEY` is not set.

### Backup & restore (SQLite)

```bash
# Create a timestamped archive of the DB + evidence store
python scripts/backup.py --label "pre-release"
# → data/backups/backup_20260605_120000.tar.gz

# Restore (stops the app first, then run):
python scripts/restore.py data/backups/backup_20260605_120000.tar.gz
```

For PostgreSQL, use `pg_dump` / `pg_restore`; the script prints the equivalent
command automatically when a Postgres `DATABASE_URL` is detected.

### Access review

Run periodically (or schedule via RQ) to produce a permission audit report:

```python
from app.services.ops.access_review import generate_access_report
report = generate_access_report(settings.database_url)
# report["permissions"] — full list; report["summary"]["roles"] — counts per role
```

### Audit-log retention

Old `AuditTrailEvent` rows are pruned by the retention job:

```python
from app.services.ops.retention import apply_retention_policy
deleted = apply_retention_policy(settings.database_url, retention_days=365)
```

Schedule via RQ-scheduler in `workers/worker.py` or run as a nightly cron.

### Alembic migration verification

```bash
# Verify migrations apply cleanly from a fresh database
alembic upgrade head

# Check current revision
alembic current

# Show pending migrations
alembic history --indicate-current
```

---

## Licence

Internal — TechGuard Labs
