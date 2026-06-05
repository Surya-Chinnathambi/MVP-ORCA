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

## Licence

Internal — TechGuard Labs
