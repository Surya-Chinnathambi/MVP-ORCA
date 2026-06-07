# TG Audit Orchestrator

**Version 2.0 · TechGuard Labs**

A full-lifecycle cyber advisory, compliance, and security audit delivery platform. Manages every stage of a VAPT or compliance engagement — from scope definition and evidence collection through human review gates, findings approval, client reporting, and remediation tracking — with a complete immutable audit trail at every step.

Built for TechGuard Labs internal teams and their clients.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Prerequisites](#prerequisites)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [First Run](#first-run)
8. [User Roles](#user-roles)
9. [VAPT Workflow — Step by Step](#vapt-workflow--step-by-step)
10. [Review Gates G1–G7](#review-gates-g1g7)
11. [PT-Orc Integration](#pt-orc-integration)
12. [Client Portal](#client-portal)
13. [Methodology Packs](#methodology-packs)
14. [Pilot Scripts](#pilot-scripts)
15. [Deployment](#deployment)
16. [Troubleshooting](#troubleshooting)
17. [Licence](#licence)

---

## What It Does

TG Audit Orchestrator replaces ad-hoc spreadsheet-based audit management with a structured, auditable delivery platform:

- **Scope Builder** with Rules of Engagement, testing windows, escalation contacts, and data sensitivity classification
- **Evidence Manager** — ingests PDF, DOCX, XLSX, PPTX, images, emails, and ZIPs; deduplicates by SHA-256; runs OCR and AI-assisted classification into 40+ audit control domains
- **Findings Register** — full lifecycle from Draft → Approved → Client Shared → Remediation → Closed, with human approval required at every state transition
- **7-gate review process (G1–G7)** that enforces human sign-off before any stage can advance
- **PT-Orc adapter** — imports reconnaissance and vulnerability data from PT-Orc scan directories directly into findings and evidence
- **Deliverable Builder** — generates HTML/XLSX gap matrices, security roadmaps, VAPT reports, and management summaries
- **Client Portal** — secure, scoped portal for client teams to upload evidence, respond to questions, and review shared findings
- **Telegram Bot** — receive critical alerts and approve requests from mobile
- **AI-assisted features** (Claude Haiku) — evidence classification, finding drafts, QA review — all advisory-only, logged with `actor=agent`, never auto-approving

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Methodology Packs (DPDP / VAPT / ISO / …)  │  Service-specific depth
│  pack.json → requirements, findings, tasks  │
└───────────────────┬─────────────────────────┘
                    │ drives
┌───────────────────▼─────────────────────────┐
│  EngagementCore (app/engagementcore/)        │  Generic execution layer
│  EngagementState · Objectives · Context      │
└───────────────────┬─────────────────────────┘
                    │ persists via
┌───────────────────▼─────────────────────────┐
│  Platform Core (models / api / services/)    │  Auth · Audit · Evidence
│  17 core objects + RBAC + Approvals + UI     │
└─────────────────────────────────────────────┘
```

Every mutating action routes through a single audit gateway (`record_event` / `request_approval` / `decide_approval`) — there are no side-door state changes anywhere in the codebase.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| API framework | FastAPI 0.136 + Uvicorn 0.49 |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic 1.18 |
| Database | SQLite (dev/MVP) · PostgreSQL (production) |
| Schema validation | Pydantic v2 |
| Web UI | Jinja2 + HTMX 1.9 + Tailwind CSS (CDN) |
| Auth | Session cookies + passlib[bcrypt] |
| Telegram | python-telegram-bot v22 |
| Evidence processing | pdfplumber · PyMuPDF · python-docx · python-pptx · openpyxl · pytesseract · Pillow |
| AI | Anthropic Claude Haiku (classification, drafts, QA) |
| Background workers | RQ + RQ-scheduler + Redis |
| Tests | pytest + httpx |
| Lint | ruff |

---

## Prerequisites

### System packages

```bash
# Debian / Kali / Ubuntu
sudo apt update
sudo apt install -y \
    python3.11 python3.11-venv python3-pip \
    tesseract-ocr \
    poppler-utils \
    libmagic1
```

- **tesseract-ocr** — required for OCR on image-based evidence files
- **poppler-utils** — required for PDF page rendering (`pdfplumber` + `PyMuPDF`)
- **libmagic1** — required for MIME type detection on uploaded evidence

### Python version

Python **3.11 or newer** is required. Check your version:

```bash
python3 --version
```

### Redis (optional in dev, required in production)

```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
```

Redis is only needed if you run background workers (`workers/worker.py`). The web app runs fine without it in development.

---

## Installation

### 1. Navigate to the project directory

```bash
cd /home/kali/tg-audit-orchestrator
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install all dependencies

```bash
pip install -e ".[dev]"
```

This installs all runtime dependencies plus dev tools (`pytest`, `ruff`, `fakeredis`). The `-e` flag installs in editable mode so code changes take effect immediately without reinstalling.

### 4. Create the data directories

```bash
mkdir -p data data/evidence data/backups
```

### 5. Configure the environment

```bash
cp .env.example .env
```

Open `.env` and fill in the required values — see [Configuration](#configuration) below.

### 6. Run database migrations

```bash
alembic upgrade head
```

This creates `data/app.db` (SQLite) and applies all schema migrations. You should see output like:

```
INFO  [alembic.runtime.migration] Running upgrade ... -> d4e5f6a7b8c9, terms_roe_features
```

### 7. Seed the database

```bash
python scripts/seed.py
```

This creates:
- All 10 canonical RBAC roles
- An initial `platform_admin` user using `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`
- Default work modes (pm, analyst, reviewer, deliverable)

### 8. Start the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser — you will be redirected to the login page.

---

## Configuration

All configuration is loaded from `.env`. Never commit this file.

```bash
# ── Database ──────────────────────────────────────────────────────────────────
# SQLite (default for dev/MVP):
DATABASE_URL=sqlite:///data/app.db

# PostgreSQL (production):
# DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/tg_audit

# ── Security ──────────────────────────────────────────────────────────────────
# REQUIRED — generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=change-me-in-production-use-32-char-minimum

# ── Admin seed account ────────────────────────────────────────────────────────
ADMIN_EMAIL=admin@techguard.local
ADMIN_PASSWORD=changeme

# ── AI — Anthropic Claude ─────────────────────────────────────────────────────
# Used for evidence classification (Haiku), finding drafts, QA agent
CLAUDE_API_KEY=sk-ant-...

# ── Telegram bot ──────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=...

# ── Background workers (optional in dev) ──────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Encryption at rest ────────────────────────────────────────────────────────
# REQUIRED in prod — generate with:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=

# ── SSO / OIDC (disabled by default) ─────────────────────────────────────────
SSO_ENABLED=false
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=
SSO_TENANT_ID=

# ── Environment profile ───────────────────────────────────────────────────────
# dev | test | prod
# prod mode enforces SECRET_KEY + ENCRYPTION_KEY and refuses to start without them
APP_ENV=dev

# ── Operations ────────────────────────────────────────────────────────────────
BACKUP_DIR=data/backups
AUDIT_RETENTION_DAYS=365
DEBUG=false
```

### Generating secrets

```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## First Run

### 1. Login

Navigate to **http://localhost:8000** → redirects to `/ui/login`.

Use the admin credentials from your `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`).

### 2. Accept Terms & Conditions

On first login, all users are redirected to `/ui/terms` before accessing the platform. Read the 10-clause Terms & Conditions covering authorized use, evidence confidentiality, professional disclaimer, audit logging, and data retention. Click **Accept Terms & Continue**.

Acceptance is recorded as an immutable audit trail event (`terms.accepted`). Users who have not accepted T&C cannot access any platform functionality.

### 3. Create your first team member

Go to **Team & Roles** (`/ui/admin/users`) → **Invite User** → assign a role and scope.

---

## User Roles

| Role | Privilege | What they can do |
|---|---|---|
| `platform_admin` | 10 | Full platform access — configure system, manage all users and data |
| `partner` | 9 | Approve any action, release reports, close engagements, risk acceptance |
| `pm` | 8 | Create and manage projects and scope, assign team, approve scope changes |
| `lead_consultant` | 7 | Lead assessments, approve finding severity, generate deliverables |
| `analyst` | 6 | Conduct assessments, create findings and tasks, upload evidence |
| `senior_reviewer` | 5 | Review and approve findings |
| `qa` | 4 | QA sign-off on draft reports before release |
| `client_approver` | 3 | Client-side: review findings, request risk acceptance via portal |
| `client_contributor` | 2 | Client-side: upload evidence, respond to questions via portal |
| `readonly` | 1 | Read-only view of assigned project data |

Permissions are scoped: a user can hold different roles on different clients or projects simultaneously.

---

## VAPT Workflow — Step by Step

This section walks through a complete Vulnerability Assessment and Penetration Test (VAPT) engagement from kick-off to closure.

---

### Step 1 — Create Client

**Navigate:** Clients → **New Client**

Fill in:
- **Entity Name** — client's legal / trading name
- **Sector** — e.g. Financial Services, Healthcare, E-Commerce
- **Business Units** — list of business units that may be in scope
- **Regulatory Context** — applicable regulations (PCI-DSS, RBI, SEBI, SOC 2, etc.)
- **Contacts** — client-side contacts with name, email, phone, and role

> Contacts saved here are suggested automatically when adding escalation contacts in the Scope Builder.

---

### Step 2 — Create VAPT Project

**Navigate:** Client detail → **New Project**

Fill in:
- **Service Type** — select `VAPT`
- **Scope Summary** — one-line description (e.g. "External network + web app VAPT for Skyline Commerce")
- **Project Manager** — assign from your team

The project starts in **Draft** status. All work happens inside the project workspace.

---

### Step 3 — Scope Builder

**Navigate:** Project → **Scope Builder**

The Scope Builder has two tabs: **Scope Items** and **Rules of Engagement**.

#### Tab 1 — Scope Items

Add all assets and boundaries:

| Kind | Example |
|---|---|
| `asset` | `10.0.0.0/24`, `https://app.skyline.com`, `Skyline Payment API v3` |
| `inclusion` | `All public-facing web applications` |
| `exclusion` | `Third-party payment processor (PCI-DSS responsibility of provider)` |
| `business_unit` | `Digital Banking`, `Customer Portal` |
| `assumption` | `Testing from external internet — no VPN access provided` |
| `constraint` | `No testing between 09:00–18:00 IST on business days` |

Each item is submitted for **PM approval** (part of Gate G1).

#### Tab 2 — Rules of Engagement

Fill in all four RoE sections before testing begins.

**Authorization text** — Written authorization statement embedded verbatim in all deliverables:

```
TechGuard Labs is authorized to conduct security testing against the systems
described in this scope document on behalf of Skyline Commerce Pvt Ltd under
written agreement dated 2026-05-15. All testing is authorized for the duration
of the engagement period 2026-06-10 through 2026-06-22.
```

**Testing Windows** — Add one or more authorized time slots:

| Field | Example |
|---|---|
| Start | `2026-06-10T22:00` |
| End | `2026-06-11T06:00` |
| Description | `Overnight window — intrusive testing and active exploitation permitted` |

**Escalation Contacts** — At least two client contacts who must be reachable during testing:

| Field | Example |
|---|---|
| Name | `Priya Sharma` |
| Role | `CISO` |
| Phone | `+91 98765 43210` |
| Email | `priya.sharma@skyline.com` |

**Data Sensitivity** — Classify the data environment:

| Field | Options |
|---|---|
| Classification | Public / Internal / **Confidential** / Restricted |
| Personal Data Involved | Yes / No |
| Handling Notes | `Evidence files must not contain raw PII. Mask before storage.` |

---

### Step 4 — Gate G1: Scope Approval

**Navigate:** Project → **Approvals**

The PM (or partner) reviews all pending scope items and approves or rejects each one. Only approved scope items appear in the test plan and deliverables.

Once all scope items have a decision:
1. PM or partner clicks **Approve Gate G1**
2. Gate G1 is passed — project status advances from `Draft` → `Scoped`

> No testing, evidence collection, or billable work should begin before G1 is passed.

---

### Step 5 — Select Frameworks

**Navigate:** Project → **Frameworks**

Select all applicable assessment frameworks. For a standard VAPT engagement:

| Framework | Purpose |
|---|---|
| OWASP WSTG | Web application testing methodology |
| OWASP ASVS 4.0 | Application security verification requirements |
| OWASP API Top 10 | API-specific test cases |
| PTES | Overall penetration test structure |
| TG Baseline | TechGuard Labs internal minimum requirements |
| NIST CSF 2.0 | Risk framing for executive reporting |

Click **Save Framework Selection**. Selected frameworks drive requirement generation in the next step.

---

### Step 6 — Attach Methodology Pack

**Navigate:** Project → **Pack / Plan**

Click **Change Pack** → select **VAPT Assessment Pack v2**.

The VAPT pack includes:
- Test phases: Reconnaissance, Network Scanning, Web Application Testing, API Testing, Post-Exploitation, Reporting
- Finding templates for common vulnerability classes (SSRF, SQLi, XSS, Broken Auth, Misconfiguration, etc.)
- Review gate configuration (G1–G7) with required approver roles
- Default task templates for each phase

After attaching the pack, click **Generate Plan**. This creates:
- Requirements mapped to your selected frameworks
- Evidence requests for each test phase
- Tasks assigned to the project team
- Project status advances to **Active**

---

### Step 7 — Project Timeline (optional)

**Navigate:** Project → **Timeline**

Track the engagement schedule with milestones:

| Milestone | Date | Status |
|---|---|---|
| Kick-off call | 2026-06-09 | Completed |
| Reconnaissance phase | 2026-06-10 | In Progress |
| Active testing window | 2026-06-10 to 06-12 | Upcoming |
| Draft findings review | 2026-06-15 | Upcoming |
| Final report delivery | 2026-06-22 | Upcoming |
| Retest | 2026-07-07 | Upcoming |

---

### Step 8 — Gate G2: Evidence Request List Approval

**Navigate:** Project → **Approvals**

The PM reviews the auto-generated evidence request list. Any requests not applicable to this engagement can be rejected with a reason.

Once the list is approved:
- Gate G2 is passed
- Client portal users (if assigned) are notified that they can begin uploading evidence

---

### Step 9 — Evidence Collection

There are two ways to collect evidence — manual upload and PT-Orc import. Both can be used in the same engagement.

#### Option A — Manual upload

**Internal team:** Project → **Evidence Review** → **Upload Evidence**

Select the linked evidence request, attach the file, and submit. Supported formats:

| Format | How it's processed |
|---|---|
| PDF | Full text extraction (pdfplumber) + OCR fallback (tesseract) |
| DOCX / PPTX | Text extraction via python-docx / python-pptx |
| XLSX / XLS | Cell data extraction via openpyxl / xlrd |
| PNG / JPG / TIFF | OCR via tesseract |
| MSG / EML | Header + body extraction via extract-msg |
| ZIP | Recursively unpacked, each file processed |

After upload the platform automatically:
1. Calculates SHA-256 hash (deduplication — same file won't be stored twice)
2. Extracts full text
3. Classifies into 40+ audit control domains via Claude Haiku
4. Sets lifecycle state to `Intake` → `Verified`

**Client portal:** Clients log in at `/portal/` and upload files against open evidence requests.

#### Option B — PT-Orc import (recommended for VAPT)

If you ran PT-Orc externally, import the scan results directly:

**Navigate:** Project → **PT-Orc Commands** → **Import Scan** → enter the PT-Orc output directory path → click **Import**

The adapter imports scope items, evidence files, and findings in one operation. See [PT-Orc Integration](#pt-orc-integration) for the expected directory structure.

---

### Step 10 — Gate G3: Evidence Completeness

**Navigate:** Project → **Approvals**

The lead consultant reviews evidence coverage across all requests:
- Is each evidence request fulfilled or formally excepted?
- Is the quality and depth sufficient to support the findings?

For any gap, raise a formal exception with a written justification. Once all requests are resolved, approve Gate G3.

---

### Step 11 — Findings Register

**Navigate:** Project → **Findings**

#### Creating findings manually

Click **New Finding**:

| Field | Example |
|---|---|
| Title | `Unauthenticated SSRF in /api/fetch endpoint` |
| Severity | `Critical` |
| Description | Full technical description including affected component, proof of concept, and business impact |

The finding starts in **Draft** status.

#### Finding lifecycle

```
Draft → In Review → Approved → Client Shared → Remediation Planned → Retest Pending → Closed
                                                                                  ↘ Risk Accepted
```

Every transition requires a human action and is logged in the immutable audit trail.

#### Severity approval

Changing a finding's severity is an approval-gated action. A senior reviewer or lead consultant must confirm the severity — this prevents accidental downgrades or inflation of risk ratings.

#### Linking evidence

In the finding detail, attach supporting evidence items. Evidence links appear in the final report alongside the finding.

---

### Step 12 — Gate G4: Findings Approval

**Navigate:** Project → **Approvals**

The senior reviewer goes through each finding:
- Confirms the title, severity, and description are technically accurate
- Checks that evidence linkage is sufficient
- Approves or sends back for rework

Once all findings are approved, Gate G4 can be passed.

---

### Step 13 — QA Agent Review

**Navigate:** Project → **Pack / Plan** → **Run QA**

The QA agent (Claude Haiku) performs an automated consistency check:
- Checks all Critical / High findings have supporting evidence
- Flags severity inconsistencies (e.g. a finding described as RCE rated Medium)
- Checks findings against selected framework requirements for coverage gaps
- Produces a structured QA report with items that need attention

> The QA agent is **advisory only**. It cannot approve findings or advance gates. A human QA reviewer reads the output and makes every decision.

---

### Step 14 — Gate G5: QA Sign-off

**Navigate:** Project → **Approvals**

The QA reviewer (role: `qa`) reviews the agent's report, resolves any flagged issues, and approves Gate G5. This sign-off confirms the report is ready for partner review.

---

### Step 15 — Deliverable Builder

**Navigate:** Project → **Deliverables**

Generate the client deliverable package for a VAPT engagement:

| Deliverable | Contents |
|---|---|
| **VAPT Report (HTML)** | Executive summary, scope, RoE, methodology, all approved findings with evidence, risk matrix (5×5), remediation roadmap |
| **Management Summary** | Non-technical 2-pager with overall risk rating and top 5 priority recommendations |
| **Client Action Plan** | Prioritised remediation table with owners, effort estimates, and target dates |
| **Retest Report** | Pre-formatted template for the follow-up retest engagement |
| **Evidence Matrix (XLSX)** | All evidence items mapped to findings, requirements, and frameworks |

Click **Generate** for each deliverable. Files are saved to `data/deliverables/`.

---

### Step 16 — Gate G6: Report Release Approval

**Navigate:** Project → **Approvals**

The partner reviews the generated deliverables for quality and accuracy:
- Is the report factually correct and professionally written?
- Are all findings correctly attributed and evidenced?
- Is the executive summary appropriate for the client's audience?

On approval of Gate G6, deliverables are released to the client portal. Nothing reaches the client before this gate — it is the only mechanism that makes deliverables visible in the portal.

---

### Step 17 — Client Sharing via Portal

After G6 is approved:

1. Assign client users (role `client_approver` / `client_contributor`) to the project in **Team & Roles**
2. Share the login URL with them: `https://your-domain/ui/login`
3. Client logs in → accepts Client Portal T&C → lands at `/portal/dashboard`

Clients can then:
- Download released deliverables
- Request formal risk acceptance on findings they choose not to remediate
- Upload additional clarifying evidence
- Respond to open evidence request questions

Risk acceptance requests always route to the partner for approval — clients cannot self-approve.

---

### Step 18 — Remediation Tracking

**Navigate:** Project → **Remediation**

For each finding, create a remediation action:

| Field | Example |
|---|---|
| Action | `Apply vendor patch for CVE-2026-1234 on all affected hosts within 7 days` |
| Owner | `Infra Team — ops@skyline.com` |
| Target Date | `2026-07-07` |
| Status | `Open → In Progress → Resolved → Verified` |

When a fix is verified via retest, update status to `Resolved`. If the client formally accepts the risk:
- They request risk acceptance via the portal
- The request routes to the partner for approval via the audit gateway
- On approval, status becomes `Risk Accepted` and the finding is closed with the acceptance reason recorded

---

### Step 19 — Gate G7: Closure

**Navigate:** Project → **Approvals**

Final gate. The partner confirms:
- All findings are closed or formally risk-accepted with documented rationale
- The audit trail is complete and unbroken
- All agreed deliverables have been released to the client

On G7 approval:
- Project status advances to `Closed`
- Evidence enters the 90-day post-closure retention period
- No further state changes are possible without formal reopening

---

## Review Gates G1–G7

| Gate | When it triggers | Required approver | What it blocks |
|---|---|---|---|
| **G1** | Scope items submitted | pm / partner | Active testing cannot begin |
| **G2** | Evidence request list auto-generated by pack | pm | Client upload / evidence phase cannot begin |
| **G3** | All evidence requests resolved or excepted | lead_consultant | Findings cannot be finalised |
| **G4** | All findings reviewed by senior reviewer | senior_reviewer | Report cannot be drafted |
| **G5** | QA agent review completed | qa | Report cannot be released |
| **G6** | Deliverables generated and reviewed | partner | Deliverables cannot reach the client portal |
| **G7** | All remediations resolved or risk-accepted | partner | Project cannot be closed |

Gate state is tracked in `projects.gates` JSON and displayed as a status bar on every project dashboard.

---

## PT-Orc Integration

PT-Orc is TechGuard Labs' internal penetration testing orchestrator. TG Audit Orchestrator imports its output via the adapter in `ptorc_adapter/`.

### Expected directory structure

```
ptorc_run/
├── scope.json          # {"items": [{"kind": "asset", "value": "10.0.0.1"}]}
├── findings.json       # [{"title": "...", "severity": "high", "description": "...", "host": "..."}]
├── evidence/
│   ├── nmap_scan.xml
│   ├── burp_report.html
│   └── screenshot_01.png
└── run_metadata.json   # {"tool": "ptorc", "start_time": "...", "end_time": "..."}
```

### Import via Web UI

Project → **PT-Orc Commands** → enter the absolute path to the run directory → **Import**

### Import via script

```python
from ptorc_adapter.importer import import_ptorc_run
from app.db import SessionLocal

db = SessionLocal()
result = import_ptorc_run(
    db,
    project_id="your-project-uuid",
    run_dir="/path/to/ptorc_run",
    imported_by_id="analyst-user-uuid",
)
db.commit()
print(f"Imported: {result['findings']} findings, {result['evidence']} evidence files")
```

All imported findings arrive in **Draft** status with `source=ptorc`. A human analyst must review and approve every finding — nothing from PT-Orc auto-advances through gates.

---

## Client Portal

The client portal at `/portal/` provides a separate, restricted interface for client teams.

### Setup

1. Create a user account with role `client_approver` or `client_contributor`
2. Assign the role scoped to the relevant project (in **Team & Roles**)
3. Share the platform login URL with the client contact
4. Client logs in → accepts Client Portal T&C → arrives at `/portal/dashboard`

### What clients can do

| Action | Role required |
|---|---|
| View shared findings | All portal roles |
| Download released deliverables | All portal roles |
| View project tasks | All portal roles |
| Upload evidence files | client_contributor |
| Respond to evidence request questions | client_contributor |
| Request risk acceptance on a finding | client_approver |

### What clients cannot do

- View findings before G6 is approved (findings don't exist in the portal until released by the partner)
- Approve their own risk acceptance requests (always requires partner decision)
- Access internal QA reports, audit trail, or team notes
- View any other client's data

---

## Methodology Packs

Packs are JSON configuration files in `app/packs/` that define service-specific test plans.

### Available packs

| Pack key | Service |
|---|---|
| `vapt` | Vulnerability Assessment & Penetration Test |
| `dpdp` | India DPDP Act 2023 Readiness Assessment |
| `gdpr_gap` | EU GDPR Gap Assessment |
| `iso_27001_readiness` | ISO/IEC 27001:2022 Readiness Assessment |
| `iso_27002_control_review` | ISO/IEC 27002:2022 Control Review |
| `iso_27701_privacy` | ISO/IEC 27701:2019 Privacy Management |
| `incident_response` | Incident Response Capability Assessment |
| `cloud_posture` | Cloud Security Posture Review |
| `ai_governance` | AI Governance and Risk Assessment |
| `vendor_risk` | Third-Party and Vendor Risk Assessment |
| `cyber_strategy` | Cyber Strategy and Roadmap |
| `grc_maturity` | GRC Maturity Assessment |

### Pack structure

Each `pack.json` defines:
- `phases` — named delivery phases
- `tasks` — default tasks per phase
- `evidence_expectations` — evidence required per phase
- `review_gates` — G1–G7 gate IDs, labels, and required approver roles
- `finding_templates` — common finding classes with draft descriptions and suggested severity

See `app/packs/vapt/pack.json` for a full example.

---

## Pilot Scripts

Standalone scripts that run a full engagement end-to-end against a temporary SQLite database. Use these to verify your installation or to validate a new pack.

### VAPT pilot

```bash
source .venv/bin/activate
mkdir -p data
python scripts/pilot_vapt.py
```

Runs all 7 gates with a PT-Orc fixture import. Outputs deliverables to `data/pilot_vapt_out/`.

### DPDP pilot

```bash
source .venv/bin/activate
python scripts/pilot_dpdp.py
```

Runs a DPDP readiness assessment end-to-end. Outputs to `data/pilot_dpdp_out/`.

### Acceptance criteria

| Step | DPDP | VAPT |
|---|---|---|
| Client + project setup | ✓ | ✓ |
| Scope definition + G1 approval | ✓ | ✓ |
| Pack selection + plan generation | ✓ | ✓ |
| Evidence requests + G2 approval | ✓ | ✓ |
| Evidence ingestion / PT-Orc import + G3 | ✓ | ✓ |
| Findings + severity approval + G4 | ✓ | ✓ |
| QA agent review + G5 | ✓ | ✓ |
| Deliverable generation | ✓ | ✓ |
| Report release approval + G6 | ✓ | ✓ |
| Closure with residual risk + G7 | ✓ | ✓ |
| Complete audit trail throughout | ✓ | ✓ |

---

## Deployment

### Production checklist

```bash
# 1. Generate required secrets
python -c "import secrets; print(secrets.token_hex(32))"
# → paste output as SECRET_KEY in .env

python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# → paste output as ENCRYPTION_KEY in .env

# 2. Set production mode
# In .env: APP_ENV=prod

# 3. Apply all migrations
alembic upgrade head

# 4. Seed roles + admin user
python scripts/seed.py

# 5. Start with multiple Uvicorn workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

In `APP_ENV=prod`, the application **refuses to start** if `SECRET_KEY` is the default placeholder or `ENCRYPTION_KEY` is not set.

### Environment profiles

| `APP_ENV` | Behaviour |
|---|---|
| `dev` | Relaxed secrets enforcement, SQLite, verbose error pages |
| `test` | SQLite in-memory, fakeredis, no outbound email |
| `prod` | All secrets enforced, audit log retention, backup scheduling active |

### Running background workers

Required in production for evidence processing queue, notifications, and retention jobs:

```bash
# Ensure Redis is running
redis-cli ping   # should return PONG

# Start the RQ worker
python workers/worker.py
```

### Backup and restore

```bash
# Create a timestamped archive of DB + evidence store
python scripts/backup.py --label "pre-release-v2"
# → data/backups/backup_20260607_120000_pre-release-v2.tar.gz

# Restore (stop the application first)
python scripts/restore.py data/backups/backup_20260607_120000_pre-release-v2.tar.gz
```

### Alembic migration management

```bash
# Check current applied revision
alembic current

# Show full migration history
alembic history --indicate-current

# Upgrade to latest
alembic upgrade head

# Roll back one migration (use with care — some are data-destructive)
alembic downgrade -1
```

### Periodic access review

```python
from app.services.ops.access_review import generate_access_report
report = generate_access_report(settings.database_url)
# report["permissions"] — full permission list
# report["summary"]["roles"] — count per role
```

### Audit log retention

Old `AuditTrailEvent` rows are pruned by the retention service (default: 365 days):

```python
from app.services.ops.retention import apply_retention_policy
deleted = apply_retention_policy(settings.database_url, retention_days=365)
```

Schedule this via the RQ scheduler in `workers/worker.py` or run as a nightly cron.

---

## Troubleshooting

### App won't start — `SECRET_KEY` error

```
RuntimeError: SECRET_KEY must be changed from the default value in production
```

Generate a real key and update `.env`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Migration fails — `target database is not up to date`

```bash
alembic upgrade head
```

If there are multiple heads:

```bash
alembic heads          # list all branch heads
alembic upgrade heads  # upgrade all branches simultaneously
```

### `tesseract: command not found` during evidence upload

```bash
sudo apt install -y tesseract-ocr
which tesseract   # verify: /usr/bin/tesseract
```

### PDF processing fails with `pdfplumber` / `PyMuPDF` errors

```bash
sudo apt install -y poppler-utils
```

### Portal users see 403 Forbidden after login

The user needs a portal role (`client_approver` or `client_contributor`) scoped to a specific project. Go to **Team & Roles** → find the user → **Edit Roles** → assign the role with project-level scope.

### Alembic `Revision X is present more than once` warning

Two migration files have identical `revision:` values. Check `migrations/versions/` for duplicate IDs:

```bash
grep -r "^revision:" migrations/versions/ | sort -t: -k3 | uniq -D -f2
```

Remove or rename the conflicting file, then re-run `alembic upgrade head`.

### AI features return "not configured" placeholder

Check `CLAUDE_API_KEY` is set in `.env`. Evidence ingestion and finding creation still work without it — only AI-assisted classification, drafts, and QA are affected.

### Telegram bot not receiving messages

Check `TELEGRAM_BOT_TOKEN` is set and start the bot process:

```bash
python -m app.bot.main
```

---

## Licence

Internal — TechGuard Labs. All rights reserved.

Not licensed for external distribution or use outside TechGuard Labs engagements.
