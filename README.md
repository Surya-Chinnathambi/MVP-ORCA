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

## Licence

Internal — TechGuard Labs
