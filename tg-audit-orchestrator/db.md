# TG Audit Orchestrator — Database Schema Reference (`db.md`)

**Purpose:** the single source of truth for the database schema. Claude Code reads this to check **which tables already exist**, what columns/enums/relationships they must have, and **which stage creates or alters each one**. If a model in `app/models/` disagrees with this file, this file wins — fix the model, not this doc (schemas are contracts).

**Two phases:**
- **MVP (Stages 0–13):** 17 core objects — built in `instructions.md`.
- **Phase 2 (Stages 14–30):** +7 objects → **24 total** — built in `BUILD_INSTRUCTIONS_PHASE2.md`. Phase 2 also **alters** a few MVP tables (see "Phase 2 alterations").

---

## Conventions

- Every table has: `id` (PK), `created_at` (DateTime), `updated_at` (DateTime) — **except append-only tables** (`AuditTrailEvent`, `EvidenceLifecycleEvent`) which use `ts` instead of `updated_at`.
- `JSON` = SQLite JSON / Postgres `JSONB` (Stage 15 switches the backend; JSONB columns gain GIN indexes there).
- `FK→Table` = foreign key. `(nullable)` marks optional FKs.
- Enum value sets are **fixed**; use SQLAlchemy `Enum` (or a `CHECK`-constrained string). Don't invent new values without a schema change here.
- Default `DATABASE_URL`: `sqlite:///data/app.db` (MVP) → Postgres (Stage 15).

---

## Table checklist (mark off as built)

| # | Table | Created in | Altered in | Append-only |
|---|---|---|---|---|
| 1 | Client | Stage 1 | Stage 14 (+`organization_id`) | — |
| 2 | Project | Stage 1 | Stage 14 (+`engagement_state`), Stage 16 (`pack_id`→MethodologyPack), Stage 27 (states) | — |
| 3 | User | Stage 1 | Stage 19 (last-active context), Stage 21 (MFA fields) | — |
| 4 | Role | Stage 1 | Stage 20 (10-role enum) | — |
| 5 | Permission | Stage 1 | Stage 20 (+scope levels) | — |
| 6 | ScopeItem | Stage 1 | — | — |
| 7 | Framework | Stage 1 | Stage 24/25 (new keys) | — |
| 8 | Requirement | Stage 1 | — | — |
| 9 | EvidenceRequest | Stage 1 | — | — |
| 10 | EvidenceItem | Stage 1 | Stage 18 (+`internal_lifecycle_state`) | — |
| 11 | Task | Stage 1 | Stage 27 (states) | — |
| 12 | Finding | Stage 1 | Stage 27 (states), Stage 26 (`retest_status`) | — |
| 13 | ApprovalRequest | Stage 1 | — | partly (immutable after decision) |
| 14 | AdvisoryClinic | Stage 1 | — | — |
| 15 | Deliverable | Stage 1 | Stage 27 (kinds) | — |
| 16 | RemediationAction | Stage 1 | — | — |
| 17 | AuditTrailEvent | Stage 1 | — | **yes** |
| 18 | Organization | Stage 14 | — | — |
| 19 | EngagementState | Stage 14 | Stage 17 (progress/context) | — |
| 20 | EngagementObjective | Stage 14 (model) / 17 (logic) | — | — |
| 21 | MethodologyPack | Stage 16 | — | — |
| 22 | WorkMode | Stage 19 | — | — |
| 23 | EvidenceLifecycleEvent | Stage 18 | — | **yes** |
| 24 | Notification | Stage 22 | — | — |

---

# MVP tables (17) — Stages 0–13

### 1. Client  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| organization_id | FK→Organization | **added Stage 14**; backfilled to default "Tech Guard" org |
| entity_name | String | legal/display name |
| sector | String | industry/sector |
| contacts | JSON | list of contacts |
| business_units | JSON | |
| reusable_context | JSON | reused across projects only when allowed |
| regulatory_context | String/Text | |
| created_at / updated_at | DateTime | |

### 2. Project  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| client_id | FK→Client | |
| service_type | Enum `dpdp \| vapt` | extended by new packs via `pack_id` rather than this enum |
| owner_id | FK→User | |
| status | Enum (see Project States) | MVP: simple; **Stage 27** expands to full state machine |
| scope_summary | Text | |
| timeline | JSON | milestones |
| pack_id | FK→MethodologyPack | MVP: directory key; **Stage 16** repoints to MethodologyPack row (version-pinned) |
| framework_ids | JSON | selected frameworks |
| created_at / updated_at | DateTime | |

> 1:1 `EngagementState` relationship added in **Stage 14**.

### 3. User  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| email | String (unique) | |
| password_hash | String | passlib[bcrypt] |
| full_name | String | |
| is_active | Boolean | |
| last_client_id / last_project_id / last_work_mode | nullable | **added Stage 19** (context restore) |
| mfa_secret / mfa_enabled / recovery_codes | nullable | **added Stage 21** (TOTP) |
| created_at / updated_at | DateTime | |

### 4. Role  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| name | Enum | MVP: `admin\|partner\|pm\|analyst\|reviewer\|qa\|client\|readonly` → **Stage 20** expands to `platform_admin\|partner\|pm\|lead_consultant\|analyst\|senior_reviewer\|qa\|client_approver\|client_contributor\|readonly` |

### 5. Permission  — *Stage 1*  (join: who-can-do-what-where)
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| user_id | FK→User | |
| scope_level | Enum | MVP: `client\|project` → **Stage 20**: `organization\|client\|project\|evidence_item\|deliverable` |
| scope_id | Integer | id of the scoped object |
| role_id | FK→Role | |

### 6. ScopeItem  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| kind | Enum `asset\|business_unit\|inclusion\|exclusion\|assumption\|constraint` | |
| value | Text | |
| approved | Boolean | flips true only via approval gateway (Gate 1) |
| created_at / updated_at | DateTime | |

### 7. Framework  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| key | Enum/String | MVP keys: `dpdp_act\|owasp_asvs\|owasp_wstg\|owasp_api10\|ptes`; **Stage 24/25** add `nist\|iso_27001\|iso_27002\|iso_27701\|eu_gdpr\|isaca\|tg_baseline` |
| title | String | |
| version | String | |

### 8. Requirement  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| framework_id | FK→Framework | |
| project_id | FK→Project | |
| ref_code | String | e.g. `DPDP-NOTICE-01` |
| text | Text | |
| evidence_expectation | Text | |
| category | String | pack category |

### 9. EvidenceRequest  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| requirement_id | FK→Requirement | |
| title | String | |
| description | Text | |
| status | Enum `open\|received\|waived` | waiving requires approval |
| owner_id | FK→User | |
| due_date | Date | |

### 10. EvidenceItem  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| evidence_request_id | FK→EvidenceRequest (nullable) | |
| source_file | String | path under `data/evidence/<project>/` |
| sha256 | String | content hash |
| mime | String | |
| ingested_at | DateTime | |
| classification | String | pack category (rule-based MVP; LLM in Stage 23) |
| sensitivity | String | restricted handling (Stage 20) |
| reviewer_status | Enum `pending\|accepted\|rejected` | **user-facing** track |
| internal_lifecycle_state | Enum `intake\|verified\|classified\|packaged\|delivered\|archived` | **added Stage 18**; linked to but distinct from `reviewer_status` |
| extracted_text | Text | |
| metadata | JSON | |
| created_at / updated_at | DateTime | |

### 11. Task  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| kind | Enum `interview\|workshop\|test\|evidence_request\|review\|remediation` | |
| title | String | |
| status | Enum | MVP simple; **Stage 27**: `Planned\|Assigned\|In Progress\|Blocked\|Review\|Complete\|Cancelled` |
| assignee_id | FK→User | |
| due_date | Date | |

### 12. Finding  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| requirement_id | FK→Requirement (nullable) | |
| title | String | |
| description | Text | |
| severity | Enum `info\|low\|medium\|high\|critical` | change → approval (trigger) |
| status | Enum | MVP: `open\|in_review\|approved\|remediated\|accepted`; **Stage 27**: `Draft\|In Review\|Approved\|Client Shared\|Remediation Planned\|Retest Pending\|Closed/Risk Accepted` |
| owner_id | FK→User | |
| evidence_item_ids | JSON | list |
| source | Enum `manual\|ptorc` | |
| retest_status | String (nullable) | **added Stage 26** |

### 13. ApprovalRequest  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| target_type | String | object type being changed |
| target_id | Integer | |
| change_before | JSON | |
| change_after | JSON | |
| reason | Text | |
| requested_by | FK→User | |
| approver_role | Enum (Role.name) | |
| status | Enum `pending\|approved\|rejected` | |
| decided_by | FK→User (nullable) | |
| decided_at | DateTime (nullable) | **immutable after finalization** |

### 14. AdvisoryClinic  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| topic | String | |
| agenda | JSON | |
| linked_finding_ids | JSON | |
| scheduled_for | DateTime | |

### 15. Deliverable  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| kind | Enum | MVP: `gap_matrix\|roadmap\|report\|summary\|tracker`; **Stage 27** adds `retest_report\|advisory_clinic_deck\|management_summary\|client_action_plan\|evidence_matrix` |
| format | String | xlsx/html/pdf/md |
| file_path | String | |
| generated_at | DateTime | |
| version | Integer | increments per regeneration |

### 16. RemediationAction  — *Stage 1*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| finding_id | FK→Finding | |
| project_id | FK→Project | |
| action | Text | |
| owner_id | FK→User | |
| status | Enum | |
| target_date | Date | |
| residual_risk | Text | |

### 17. AuditTrailEvent  — *Stage 1*  **(append-only)**
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| actor_id | FK→User | use sentinel/`actor=agent` tag for AI actions (Stage 23) |
| action | String | |
| target_type | String | |
| target_id | Integer | |
| before | JSON | |
| after | JSON | |
| reason | Text | |
| ts | DateTime | no `updated_at` — append-only |

---

# Phase 2 tables (+7) — Stages 14–30

### 18. Organization  — *Stage 14*  (top tenant, above Client)
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| name | String | legal name |
| display_name | String | |
| settings | JSON | org-level config/feature flags |
| created_at / updated_at | DateTime | backfill one "Tech Guard" org on migration |

### 19. EngagementState  — *Stage 14 (model) / 17 (logic)*  (1:1 with Project)
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project (unique, 1:1) | |
| phase | String | derived from project status on backfill |
| progress | JSON | gates passed + % per workstream (Stage 17) |
| blockers | JSON | |
| context_snapshot | JSON | active pack, open tasks, pending evidence/approvals, recent client inputs |
| created_at / updated_at | DateTime | persistent-context store for UI/agent/bot |

### 20. EngagementObjective  — *Stage 14 (model) / 17 (logic)*  (EngagementCore, service-neutral)
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| project_id | FK→Project | |
| title | String | |
| description | Text | |
| acceptance_criteria | Text | must be met before `complete` |
| depends_on | JSON | list of objective ids; cycle-checked |
| status | Enum | |
| linked_requirement_ids | JSON | |
| linked_evidence_ids | JSON | |
| created_at / updated_at | DateTime | **no offensive fields here** — those stay in the VAPT pack |

### 21. MethodologyPack  — *Stage 16*  (versioned, lifecycle-governed)
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| organization_id | FK→Organization | |
| key | String | e.g. `dpdp`, `vapt`, `iso_27001_readiness`, `gdpr_gap`, `vendor_risk` … |
| title | String | |
| version | String | |
| lifecycle | Enum `draft\|internal_review\|approved\|active\|deprecated\|archived` | transitions route through approval gateway |
| source_json | JSONB | validated pack body (frozen pack JSON format) |
| checksum | String | of source_json |
| approved_by | FK→User (nullable) | |
| approved_at | DateTime (nullable) | |
| created_at / updated_at | DateTime | only `active` packs deliver to projects |

### 22. WorkMode  — *Stage 19*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| key | Enum `pm\|analyst\|reviewer\|deliverable_builder\|client_contributor` | |
| title | String | |
| allowed_views | JSON | which views/pages this mode loads |
| default_filters | JSON | |
| created_at / updated_at | DateTime | does **not** grant access — RBAC still governs |

### 23. EvidenceLifecycleEvent  — *Stage 18*  **(append-only)**
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| evidence_item_id | FK→EvidenceItem | |
| from_state | Enum (internal states) | |
| to_state | Enum `intake\|verified\|classified\|packaged\|delivered\|archived` | |
| actor_id | FK→User | |
| reason | Text | |
| supersedes_id | FK→EvidenceItem (nullable) | supersede chain; old item retained, never deleted |
| ts | DateTime | append-only |

### 24. Notification  — *Stage 22*
| Column | Type | Notes |
|---|---|---|
| id | PK | |
| organization_id | FK→Organization | |
| project_id | FK→Project (nullable) | |
| recipient_user_id | FK→User | |
| channel | Enum `web\|email\|telegram` | |
| kind | Enum `approval_needed\|evidence_reminder\|deadline\|finding_status\|escalation\|status_summary` | |
| payload | JSON | scoped — never includes restricted context |
| status | Enum `pending\|sent\|read\|failed` | |
| scheduled_for | DateTime (nullable) | rq-scheduler |
| sent_at | DateTime (nullable) | |
| created_at / updated_at | DateTime | |

---

## Enum reference (quick lookup)

| Enum | Values |
|---|---|
| Project.service_type | `dpdp` `vapt` (packs beyond these are selected via `pack_id`, not this field) |
| Project.status (Stage 27) | `Draft` `Scoped` `Active` `Review` `Client Review` `Final` `Closed` `Archived` |
| Role.name (Stage 20) | `platform_admin` `partner` `pm` `lead_consultant` `analyst` `senior_reviewer` `qa` `client_approver` `client_contributor` `readonly` |
| Permission.scope_level (Stage 20) | `organization` `client` `project` `evidence_item` `deliverable` |
| ScopeItem.kind | `asset` `business_unit` `inclusion` `exclusion` `assumption` `constraint` |
| EvidenceRequest.status | `open` `received` `waived` |
| EvidenceItem.reviewer_status | `pending` `accepted` `rejected` |
| EvidenceItem.internal_lifecycle_state | `intake` `verified` `classified` `packaged` `delivered` `archived` |
| Task.kind | `interview` `workshop` `test` `evidence_request` `review` `remediation` |
| Task.status (Stage 27) | `Planned` `Assigned` `In Progress` `Blocked` `Review` `Complete` `Cancelled` |
| Finding.severity | `info` `low` `medium` `high` `critical` |
| Finding.status (Stage 27) | `Draft` `In Review` `Approved` `Client Shared` `Remediation Planned` `Retest Pending` `Closed/Risk Accepted` |
| Finding.source | `manual` `ptorc` |
| ApprovalRequest.status | `pending` `approved` `rejected` |
| MethodologyPack.lifecycle | `draft` `internal_review` `approved` `active` `deprecated` `archived` |
| WorkMode.key | `pm` `analyst` `reviewer` `deliverable_builder` `client_contributor` |
| Notification.channel | `web` `email` `telegram` |
| Notification.kind | `approval_needed` `evidence_reminder` `deadline` `finding_status` `escalation` `status_summary` |
| Notification.status | `pending` `sent` `read` `failed` |

---

## Foreign-key / relationship map

```
Organization ─1:N─> Client ─1:N─> Project
                                   │
   Project ─1:1─> EngagementState
   Project ─1:N─> EngagementObjective, ScopeItem, Requirement, EvidenceRequest,
                  EvidenceItem, Task, Finding, ApprovalRequest, AdvisoryClinic,
                  Deliverable, RemediationAction, AuditTrailEvent, Notification(nullable)
   Project ─N:1─> MethodologyPack (pack_id, version-pinned)
   Project ─N:1─> User (owner_id)

Organization ─1:N─> MethodologyPack
Framework ─1:N─> Requirement
Requirement ─1:N─> EvidenceRequest
EvidenceRequest ─1:N─> EvidenceItem (nullable link)
EvidenceItem ─1:N─> EvidenceLifecycleEvent ; EvidenceItem.supersedes_id ─> EvidenceItem
Finding ─1:N─> RemediationAction
Finding.evidence_item_ids ─(JSON list)─> EvidenceItem
User ─1:N─> Permission ─N:1─> Role
```

---

## Phase 2 alterations to MVP tables (don't miss on migration)

1. **Client** +`organization_id` (FK, backfill default org) — Stage 14.
2. **Project** +`engagement_state` 1:1 (auto-create per existing project) — Stage 14; **`pack_id`** repointed to MethodologyPack rows — Stage 16; **status** enum expanded — Stage 27.
3. **EvidenceItem** +`internal_lifecycle_state` — Stage 18.
4. **Role.name** enum expanded to 10 roles (map old 8, don't drop) — Stage 20.
5. **Permission.scope_level** expanded to 5 levels — Stage 20.
6. **User** +context-restore fields (Stage 19) and +MFA fields (Stage 21).
7. **Finding** +`retest_status` (Stage 26); **status** enum expanded (Stage 27).
8. **Task.status** / **Deliverable.kind** enums expanded — Stage 27.

> All alterations ship as **forward-only Alembic migrations with explicit backfills**. Never drop a column holding delivery data.

---

## Framework-library decision (Full Spec §6.7, §8.2) — stageC6

**Decision: JSON-as-library (option b).**

Framework metadata (description, requirement text, evidence expectations, assessment procedures,
risk themes, related frameworks, applicable packs) lives in `app/frameworks/*.json` — one file
per framework key. The `Framework` DB table stores only the lightweight identity (`id`, `key`,
`title`, `version`) needed for relational linking.

**Why:** In-DB querying of framework content is not required for the MVP. The JSON files are
the canonical source; the loader reads them on demand. Moving framework bodies into the DB
would require a large migration and a new many-to-many schema without clear MVP benefit.

**§8.2 many-to-many mapping:**

| Relationship | Storage | Notes |
|---|---|---|
| Evidence item → many requirements | `EvidenceRequest` rows (one per requirement) | Relational; each EvidenceItem links to one EvidenceRequest |
| Finding → many frameworks | `Finding.pack_scoped_data["frameworks"]` (JSON array of framework keys) | JSON-array linkage — **tech debt** (not relationally enforced). Future: add `finding_frameworks` join table. |
| Project → selected frameworks | `Project.framework_ids` (JSON array of framework keys) | JSON-array; relational enforcement deferred to post-MVP. |

**Tech debt note:** `Finding.pack_scoped_data["frameworks"]` and `Project.framework_ids` are
JSON arrays, not FK-enforced join tables. Queries spanning frameworks and findings require
application-layer joins. A `finding_frameworks` join table should be added post-MVP to support
cross-framework analytics.
