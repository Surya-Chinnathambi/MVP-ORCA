# CLAUDE.md — TG Audit Orchestrator

Standing context for every Claude Code session. Read this before touching any code.

---

## Build rules (enforce strictly)

1. **One stage per session.** Prompt: *"Read CLAUDE.md and BUILD_INSTRUCTIONS.md. Implement Stage N only. Stop at the acceptance test."* Do not run ahead into Stage N+1.
2. **The stack is frozen (see below). Do not re-decide it.** Re-litigating the stack mid-build wastes tokens and breaks files.
3. **Pin every dependency.** All deps in `pyproject.toml` with `==` versions. No "latest."
4. **Schemas are contracts.** The DB models (17 objects), the pack JSON format, and the PT-Orc export format are fixed. Other code must conform to them — not the reverse.
5. **Each stage ends with a green acceptance test.** If `tests/test_stageN.py` does not pass, the stage is not done. Don't move on.
6. **Commit at every stage boundary** with format `stageN: <summary>`. This gives clean rollback points.
7. **Keep files < 300 lines.** If a file grows past that, split it. Small files = cheaper edits later.
8. **No secrets in code.** Everything sensitive comes from `.env` (loaded via `app/config.py` → pydantic-settings).

---

## Frozen tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Database (MVP) | SQLite at `data/app.db` |
| Schemas | Pydantic v2 |
| Web UI | Jinja2 + HTMX + Tailwind (CDN) — server-rendered |
| Auth | Session cookies + passlib[bcrypt] |
| Telegram bot | python-telegram-bot v21+ |
| Evidence processing | pdfplumber, PyMuPDF, python-docx, python-pptx, openpyxl, Pillow, pytesseract, deep-translator, langdetect |
| AI | anthropic (Claude Haiku for cost-effective vision + classification) |
| Tests | pytest + httpx TestClient |
| Lint | ruff |

**Deferred to post-MVP — do NOT build:**
Postgres, React client portal, LLM-based AI classification replacement, real auth/SSO provider, container orchestration.

---

## Evidence tracker — existing code (Stage 6)

The evidence processing engine comes from a working implementation at
`/home/kali/audit-evidence-processor-main_1/audit-evidence-processor-main/`.

Key files already copied to `app/services/evidence/`:
- `extract.py` — multi-format file conversion (PDF/DOCX/XLSX/PPTX/images/email/ZIP → UTF-8 text)
- `classify.py` — Claude Haiku AI classification into 40+ audit control domains
- `utils.py` — shared retry constants, env loader

**Stage 6 integrates these with the ORM** (EvidenceItem model, sha256 dedup, manifest.jsonl, reviewer workflow).
Do NOT rewrite the conversion/classification logic — adapt it.

---

## Central audit gateway (Stage 2 — enforce everywhere)

Every state-changing endpoint uses two functions from `app/services/audit.py`:
- `record_event(db, actor, action, target, before, after, reason)` → writes AuditTrailEvent
- `request_approval(db, target, before, after, reason, approver_role)` → writes ApprovalRequest(pending)
- `decide_approval(approval_id, decision, decider)` → resolves approval + records event

**Never mutate controlled state ad-hoc.** Use the gateway.

---

## Approval triggers (all must route through the gateway)

scope change · testing-window change · exclusion add/remove · material task change/cancel ·
client input altering conclusions · finding severity change · finding status change ·
finding impact/remediation change · evidence rejection/override · report release ·
closure / residual-risk acceptance

---

## Review gates (G1–G7, tracked per project)

G1 scope approved · G2 evidence request list approved · G3 evidence complete or exceptions approved ·
G4 findings approved · G5 draft report QA complete · G6 final report approved · G7 remediation/closure accepted

---

## Session prompt template (Phase 1, Stages 0–13)

```
Read CLAUDE.md and BUILD_INSTRUCTIONS.md.
Implement Stage <N> ONLY, using the frozen stack and data model.
Do not modify earlier stages unless a test fails.
Finish when tests/test_stage<N>.py passes. Then summarize what you built and stop.
```

---

## Phase 2 additional rules (Stages 14–30, from BUILD_INSTRUCTIONS_PHASE2.md)

9. **Stages 0–13 are frozen.** Do not refactor MVP code unless a Phase 2 stage explicitly says to.
10. **Phase 1 frozen stack still holds** plus Phase 2 additions (Postgres, Redis/RQ, pyotp, cryptography, Authlib, anthropic SDK, smtplib). See pyproject.toml for pinned versions.
11. **Migrations are forward-only.** Every schema change ships an Alembic migration with explicit backfills. Never drop a column that holds delivery data.
12. **The audit/approval gateway from Stage 2 is the single chokepoint.** New mutating paths route through `record_event` / `request_approval` — never ad-hoc.
13. **EngagementCore boundary is a hard rule.** Generic execution primitives go in `app/engagementcore/`. Anything VAPT/offensive-specific goes in the VAPT pack only.
14. **AI agents never approve.** No agent may approve scope, set/confirm severity, release reports, or read restricted evidence. Every agent action writes an AuditTrailEvent tagged `actor=agent`.

## Phase 2 3-layer architecture

```
┌─────────────────────────────────────────────┐
│  Methodology Packs (DPDP / VAPT / ISO / …)  │  Service-specific depth
│  pack.json → requirements, findings, tasks  │  Offensive concepts ONLY here
└───────────────────┬─────────────────────────┘
                    │ drives
┌───────────────────▼─────────────────────────┐
│  EngagementCore (app/engagementcore/)        │  Generic execution layer
│  EngagementState · Objectives · Context      │  Service-neutral, no VAPT specifics
└───────────────────┬─────────────────────────┘
                    │ persists via
┌───────────────────▼─────────────────────────┐
│  Platform Core (models / api / services/)    │  17 MVP objects + 7 Phase 2 objects
│  Auth · Audit · Evidence · Approvals · UI   │  Org tenant · RBAC · Deliverables
└─────────────────────────────────────────────┘
```

## Phase 2 session prompt template (Stages 14–30)

```
Read CLAUDE.md and BUILD_INSTRUCTIONS_PHASE2.md.
Implement Stage <N> ONLY, using the frozen stack (Phase 1 + Phase 2 Section 1)
and data model (17 MVP objects + Phase 2 Section 2).
Do not modify Stages 0–13 unless this stage explicitly says so or a test fails.
Keep offensive/VAPT-specific concepts inside the VAPT pack, never in EngagementCore or core.
Route every trigger-bound change through the audit/approval gateway.
Finish when tests/test_stage<N>.py passes. Then summarize what you built and stop.
```
