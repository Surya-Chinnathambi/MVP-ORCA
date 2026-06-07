"""
setup_team_vapt.py — Creates the full demo team, VAPT project, scope,
sample data, and prints a complete test credential sheet.

Run: python scripts/setup_team_vapt.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db import SessionLocal, engine
import app.models  # noqa — register all models
from app.models.base import TimestampMixin
from app.models.users import User, Role, Permission, RoleName, ScopeLevel
from app.models.clients import Client, Project
from app.models.scope import ScopeItem
from app.models.tasks import Finding, FindingSeverity, FindingStatus
from app.models.delivery import RemediationAction
from app.services.auth import hash_password
from app.services.audit import record_event, request_approval
from app.services.methodology.loader import load_pack
from app.services.methodology.plan import generate_plan

# ── Credentials ──────────────────────────────────────────────────────────────
TEAM = [
    dict(
        full_name="Hari Krishnamurthy",
        email="hari@techguard.lab",
        password="Hari@TG2026",
        role=RoleName.pm,
        title="Project Manager",
        colour="\033[1;33m",       # yellow
    ),
    dict(
        full_name="Surya Chinnathambi",
        email="surya.chinnathambi@techguardlabs.com",
        password="Surya@TG2026",
        role=RoleName.lead_consultant,
        title="Lead Consultant",
        colour="\033[1;36m",       # cyan
    ),
    dict(
        full_name="Shivani Reddy",
        email="shivani@techguard.lab",
        password="Shivani@TG2026",
        role=RoleName.analyst,
        title="Consultant",
        colour="\033[1;35m",       # magenta
    ),
    dict(
        full_name="Srimithila Nair",
        email="srimithila@techguard.lab",
        password="Sri@TG2026",
        role=RoleName.analyst,
        title="Consultant",
        colour="\033[1;32m",       # green
    ),
]

# ── Scope items for the demo project ─────────────────────────────────────────
SCOPE_ITEMS = [
    ("asset",       "testphp.vulnweb.com"),
    ("asset",       "10.10.9.1"),
    ("asset",       "demo.testfire.net"),
    ("inclusion",   "Full TCP/UDP port scan on all in-scope IPs"),
    ("inclusion",   "Web application testing OWASP Top-10 + API security"),
    ("exclusion",   "No Denial-of-Service attacks"),
    ("exclusion",   "No social engineering or phishing"),
    ("assumption",  "Testing window: Mon–Fri 09:00–18:00 IST"),
    ("constraint",  "All exploitation requires prior PM approval"),
]

# ── Sample findings (realistic VAPT findings) ─────────────────────────────────
SAMPLE_FINDINGS = [
    dict(title="SQL Injection in search parameter",       severity="critical",
         description="The `q` parameter on /search is injectable (error-based). Confirmed via SQLMap.",
         phase_tag="05_web", retest_status="pending"),
    dict(title="Reflected XSS on login error message",   severity="high",
         description="User-supplied `username` value reflected unsanitised in 401 error response.",
         phase_tag="05_web", retest_status="pending"),
    dict(title="TLS 1.0 still enabled",                  severity="medium",
         description="Server accepts TLS 1.0 connections. POODLE/BEAST attack surface.",
         phase_tag="04_tls", retest_status="n/a"),
    dict(title="Directory listing on /uploads/",          severity="medium",
         description="Apache directory listing is enabled; exposes uploaded file names.",
         phase_tag="05_web", retest_status="n/a"),
    dict(title="Missing Content-Security-Policy header",  severity="low",
         description="CSP header absent on all responses. Increases XSS impact.",
         phase_tag="05_web", retest_status="n/a"),
    dict(title="Server version disclosed in headers",     severity="info",
         description="Server: Apache/2.4.41 (Ubuntu) revealed. Facilitates targeted attacks.",
         phase_tag="05_web", retest_status="n/a"),
]

BOLD = "\033[1m"; RESET = "\033[0m"; RED = "\033[0;31m"; GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"; BLUE = "\033[1;34m"; CYAN = "\033[1;36m"


def _banner(text: str) -> None:
    line = "═" * 60
    print(f"\n{BOLD}{BLUE}{line}{RESET}")
    print(f"{BOLD}{BLUE}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{line}{RESET}")


def _ok(msg: str) -> None: print(f"  {GREEN}✓{RESET} {msg}")
def _info(msg: str) -> None: print(f"  {CYAN}·{RESET} {msg}")


def run() -> None:
    db = SessionLocal()

    # ── 1. UPSERT TEAM MEMBERS ────────────────────────────────────────────────
    _banner("Step 1 — Creating team members")
    user_objs: dict[str, User] = {}
    for member in TEAM:
        existing = db.query(User).filter_by(email=member["email"]).first()
        if existing is None:
            u = User(
                full_name=member["full_name"],
                email=member["email"],
                password_hash=hash_password(member["password"]),
                is_active=True,
            )
            db.add(u)
            db.flush()
            _ok(f"Created  {member['full_name']}  <{member['email']}>")
        else:
            u = existing
            _info(f"Exists   {member['full_name']}  <{member['email']}>")
        user_objs[member["email"]] = u
    db.flush()

    # ── 2. GET ADMIN USER ─────────────────────────────────────────────────────
    admin = db.query(User).filter_by(email="admin@techguard.local").first()
    if admin is None:
        print(f"{RED}ERROR: admin@techguard.local not found — run scripts/seed.py first{RESET}")
        sys.exit(1)

    # ── 3. CREATE CLIENT ──────────────────────────────────────────────────────
    _banner("Step 2 — Creating demo client & project")
    client = db.query(Client).filter_by(entity_name="AcmeCorp Digital").first()
    if client is None:
        client = Client(
            entity_name="AcmeCorp Digital",
            sector="E-commerce",
            regulatory_context="PCI-DSS, IT Act 2000, DPDP Act 2023",
        )
        db.add(client)
        db.flush()
        _ok("Created client: AcmeCorp Digital")
    else:
        _info("Client already exists: AcmeCorp Digital")

    # ── 4. CREATE VAPT PROJECT ────────────────────────────────────────────────
    project = (
        db.query(Project)
        .filter_by(client_id=client.id, service_type="vapt")
        .order_by(Project.created_at.desc())
        .first()
    )
    if project is None:
        project = Project(
            client_id=client.id,
            service_type="vapt",
            owner_id=user_objs["hari@techguard.lab"].id,
            scope_summary=(
                "External black-box VAPT of AcmeCorp e-commerce platform. "
                "Targets: testphp.vulnweb.com, demo.testfire.net, 10.10.9.1. "
                "Focus: OWASP Top-10, API security, TLS/SSL, authentication."
            ),
            gates={},
        )
        db.add(project)
        db.flush()
        record_event(db, action="project.created", target_type="project",
                     target_id=project.id, actor_id=admin.id,
                     after={"service_type": "vapt", "owner": "hari@techguard.lab"})
        _ok(f"Created project: {project.id}")
    else:
        _info(f"Project exists: {project.id}")

    # ── 5. ATTACH VAPT PACK + GENERATE PLAN ──────────────────────────────────
    if not project.pack_id:
        project.pack_id = "vapt"
        db.flush()
        try:
            pack = load_pack("vapt")
            generate_plan(db, project, pack)
            _ok("Attached VAPT pack and generated plan (requirements, ERs, tasks)")
        except Exception as e:
            _info(f"Pack gen skipped: {e}")
    else:
        _info("Pack already attached")

    # ── 6. ADD SCOPE ITEMS ────────────────────────────────────────────────────
    _banner("Step 3 — Adding scope items")
    existing_vals = {s.value for s in db.query(ScopeItem).filter_by(project_id=project.id).all()}
    for kind, value in SCOPE_ITEMS:
        if value not in existing_vals:
            item = ScopeItem(project_id=project.id, kind=kind, value=value, approved=False)
            db.add(item)
            db.flush()
            request_approval(db, project_id=project.id, target_type="scope_item",
                             target_id=item.id,
                             reason=f"Scope item: {kind} — {value}",
                             approver_role="pm",
                             requested_by=admin.id)
            _ok(f"[{kind:12s}] {value}")
        else:
            _info(f"[{kind:12s}] {value}  (exists)")
    db.flush()

    # Mark all scope items approved (demo shortcut)
    for si in db.query(ScopeItem).filter_by(project_id=project.id).all():
        si.approved = True
    db.flush()
    _ok("All scope items auto-approved for demo")

    # ── 7. ASSIGN TEAM ROLES AT PROJECT SCOPE ────────────────────────────────
    _banner("Step 4 — Assigning project roles")
    for member in TEAM:
        u = user_objs[member["email"]]
        role_obj = db.query(Role).filter_by(name=member["role"].value).first()
        if role_obj is None:
            _info(f"Role {member['role'].value} not found — skipping {member['full_name']}")
            continue
        already = (
            db.query(Permission)
            .filter_by(user_id=u.id, role_id=role_obj.id,
                       scope_level=ScopeLevel.project.value, scope_id=project.id)
            .first()
        )
        if already is None:
            perm = Permission(
                user_id=u.id,
                role_id=role_obj.id,
                scope_level=ScopeLevel.project.value,
                scope_id=project.id,
            )
            db.add(perm)
            _ok(f"{member['full_name']:20s} → {member['role'].value:20s} on project")
        else:
            _info(f"{member['full_name']:20s} → {member['role'].value:20s} (exists)")

    # Also give Hari partner at org scope (so he can approve scope/findings)
    hari = user_objs["hari@techguard.lab"]
    partner_role = db.query(Role).filter_by(name=RoleName.partner.value).first()
    if partner_role:
        already_partner = db.query(Permission).filter_by(
            user_id=hari.id, role_id=partner_role.id,
            scope_level=ScopeLevel.organization.value
        ).first()
        if not already_partner:
            db.add(Permission(user_id=hari.id, role_id=partner_role.id,
                              scope_level=ScopeLevel.organization.value))
            _ok("Hari also granted partner @ org scope (can approve gates)")
    db.flush()

    # Give Surya lead_consultant at org scope too
    surya = user_objs["surya.chinnathambi@techguardlabs.com"]
    lc_role = db.query(Role).filter_by(name=RoleName.lead_consultant.value).first()
    if lc_role:
        already_lc = db.query(Permission).filter_by(
            user_id=surya.id, role_id=lc_role.id,
            scope_level=ScopeLevel.organization.value
        ).first()
        if not already_lc:
            db.add(Permission(user_id=surya.id, role_id=lc_role.id,
                              scope_level=ScopeLevel.organization.value))
            _ok("Surya granted lead_consultant @ org scope")
    db.flush()

    # ── 8. CREATE SAMPLE FINDINGS ─────────────────────────────────────────────
    _banner("Step 5 — Creating sample VAPT findings")
    existing_titles = {f.title for f in db.query(Finding).filter_by(project_id=project.id).all()}
    finding_objs = []
    for fd in SAMPLE_FINDINGS:
        if fd["title"] not in existing_titles:
            f = Finding(
                project_id=project.id,
                title=fd["title"],
                severity=fd["severity"],
                status=FindingStatus.draft.value,
                owner_id=surya.id,
                description=fd["description"],
                phase_tag=fd["phase_tag"],
                retest_status=fd["retest_status"],
                source="manual",
            )
            db.add(f)
            db.flush()
            record_event(db, action="finding.created", target_type="finding",
                         target_id=f.id, actor_id=surya.id, project_id=project.id,
                         after={"title": fd["title"], "severity": fd["severity"]})
            finding_objs.append(f)
            _ok(f"[{fd['severity']:8s}] {fd['title']}")
        else:
            _info(f"[exists  ] {fd['title']}")
    db.flush()

    # ── 9. SAMPLE REMEDIATION ACTIONS ────────────────────────────────────────
    _banner("Step 6 — Adding sample remediation actions")
    critical_f = next((f for f in finding_objs if f.severity == "critical"), None)
    high_f = next((f for f in finding_objs if f.severity == "high"), None)

    from datetime import date, timedelta
    today = date.today()

    if critical_f:
        db.add(RemediationAction(
            project_id=project.id,
            finding_id=critical_f.id,
            action="Implement parameterised queries / prepared statements. Remove direct string concatenation in search_handler.php line 42.",
            owner_id=user_objs["shivani@techguard.lab"].id,
            status="open",
            target_date=today + timedelta(days=7),
            residual_risk="None if fix applied correctly. Verify via retest.",
        ))
        _ok("Remediation action for SQL Injection (7-day target)")

    if high_f:
        db.add(RemediationAction(
            project_id=project.id,
            finding_id=high_f.id,
            action="HTML-encode all user-supplied values before reflection. Apply Content-Security-Policy header.",
            owner_id=user_objs["srimithila@techguard.lab"].id,
            status="open",
            target_date=today + timedelta(days=14),
        ))
        _ok("Remediation action for XSS (14-day target)")

    db.commit()
    _ok("All changes committed")

    # ── PRINT CREDENTIAL SHEET ────────────────────────────────────────────────
    _banner("CREDENTIAL SHEET")
    print(f"""
  {BOLD}App URL:{RESET}       http://localhost:8000/ui/clients
  {BOLD}Project ID:{RESET}    {project.id}
  {BOLD}Direct link:{RESET}   http://localhost:8000/ui/projects/{project.id}
  {BOLD}Client:{RESET}        AcmeCorp Digital (E-commerce)
""")

    creds = [
        ("admin@techguard.local",                   "changeme",       "platform_admin", "Platform Admin", "\033[1;31m"),
        ("hari@techguard.lab",                       "Hari@TG2026",    "pm + partner",   "Project Manager (Hari)", YELLOW),
        ("surya.chinnathambi@techguardlabs.com",     "Surya@TG2026",   "lead_consultant","Lead Consultant (Surya)", CYAN),
        ("shivani@techguard.lab",                    "Shivani@TG2026", "analyst",        "Consultant (Shivani)", "\033[1;35m"),
        ("srimithila@techguard.lab",                 "Sri@TG2026",     "analyst",        "Consultant (Srimithila)", GREEN),
    ]

    col_w = (38, 16, 17)
    header = (
        f"  {BOLD}{'Email':38s}  {'Password':16s}  {'Role':17s}  Name{RESET}"
    )
    print(header)
    print("  " + "─" * 90)
    for email, pw, role, name, col in creds:
        print(f"  {col}{email:{col_w[0]}s}  {pw:{col_w[1]}s}  {role:{col_w[2]}s}  {name}{RESET}")

    # ── ROLE PERMISSIONS TABLE ────────────────────────────────────────────────
    _banner("RBAC CAPABILITY MATRIX")
    print(f"""
  {BOLD}{"Action":<40s} Admin   Hari    Surya   Shivani  Sri{RESET}
  {"─"*75}
  {"Login & view project dashboard":<40s} ✓       ✓       ✓       ✓        ✓
  {"Create client / project":<40s} ✓       ✓       ✗       ✗        ✗
  {"Add scope items (triggers approval)":<40s} ✓       ✓       ✓       ✗        ✗
  {"Approve scope / gate decisions":<40s} ✓       ✓(partner) ✗    ✗        ✗
  {"Create finding (draft)":<40s} ✓       ✓       ✓       ✓        ✓
  {"Move finding in_review → approved":<40s} ✓       ✓       ✓       ✗        ✗
  {"Generate deliverables":<40s} ✓       ✓       ✓       ✗        ✗
  {"Release deliverable":<40s} ✓       ✓(partner) ✗    ✗        ✗
  {"Accept/reject evidence items":<40s} ✓       ✓       ✓       ✓        ✓
  {"Assign task / change task status":<40s} ✓       ✓       ✓       ✓        ✓
  {"Create remediation action":<40s} ✓       ✓       ✓       ✓        ✓
  {"Admin panel (create users, roles)":<40s} ✓       ✗       ✗       ✗        ✗
""")

    # ── MANUAL TEST WORKFLOW STEPS ────────────────────────────────────────────
    _banner("MANUAL TEST WORKFLOW — Step by Step")
    print(f"""
  {BOLD}PRE-CONDITION:{RESET} Server running at http://localhost:8000

  ┌─ PHASE 1: PROJECT SETUP (Hari — PM) ──────────────────────────────────────┐
  │ 1. Login as  hari@techguard.lab / Hari@TG2026                             │
  │ 2. Clients → AcmeCorp Digital → Open project {project.id[:8]}…           │
  │ 3. Dashboard: verify gate badges G1–G7 shown (all unlit)                  │
  │ 4. Scope Builder → confirm {len(SCOPE_ITEMS)} scope items shown, all "Approved"     │
  │ 5. Pack / Plan → confirm VAPT pack attached → click "Generate Plan"        │
  │    • Requirements, Evidence Requests, Tasks should appear                  │
  │ 6. Approvals (top nav) → approve any pending scope items                   │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ PHASE 2: EVIDENCE & FINDINGS (Surya — Lead) ─────────────────────────────┐
  │ 1. Login as  surya.chinnathambi@techguardlabs.com / Surya@TG2026          │
  │ 2. Open project → Task Board                                               │
  │    • Create a new task: kind=test, title="Run Nikto scan on vulnweb"       │
  │    • Set status: planned → in_progress                                     │
  │ 3. Findings → verify 6 sample findings exist                               │
  │    • Click "→ in_review" on SQL Injection (critical)                       │
  │    • Click "→ in_review" on XSS finding (high)                             │
  │ 4. Evidence Review → if any items present, Accept them                     │
  │ 5. Try adding scope item → should create pending approval (not auto-approve)│
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ PHASE 3: APPROVAL GATE (Hari — PM) ──────────────────────────────────────┐
  │ 1. Login as  hari@techguard.lab / Hari@TG2026                             │
  │ 2. Approvals → should see pending items from Surya's scope add             │
  │ 3. Approve the scope item → returns to Approvals list                      │
  │ 4. Findings → move in_review findings to "approved"                        │
  │    (Hari has partner role → can approve findings)                          │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ PHASE 4: CONSULTANT WORK (Shivani & Srimithila) ─────────────────────────┐
  │ Shivani: shivani@techguard.lab / Shivani@TG2026                           │
  │ 1. Open project → Findings → create new finding (severity: medium)         │
  │ 2. Remediation Tracker → update SQL Injection action status to in_progress │
  │ 3. Task Board → change "Run Nikto scan" task to complete                   │
  │ 4. Try Approvals → should be accessible but no approve button (analyst)    │
  │                                                                            │
  │ Srimithila: srimithila@techguard.lab / Sri@TG2026                         │
  │ 1. Open project → Findings → add finding (severity: low)                  │
  │ 2. Remediation → update XSS action to in_progress                         │
  │ 3. Evidence Review → accept/reject evidence items                          │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ PHASE 5: DELIVERABLES (Surya — Lead) ────────────────────────────────────┐
  │ 1. Login as Surya                                                          │
  │ 2. Deliverables → generate: Gap Matrix, Full Report, Mgmt Summary          │
  │ 3. Evidence Matrix → generate                                              │
  │ 4. Try to Release a deliverable → should work (lead_consultant CAN release)│
  │    or trigger approval if gated                                            │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ PHASE 6: PT-ORC INTEGRATION TEST ────────────────────────────────────────┐
  │ 1. cd /home/kali/audit-orc-vapt/pt-orc/scripts                            │
  │ 2. Edit pt-orc.conf → set ORCHESTRATOR_PROJECT_ID={project.id}            │
  │ 3. sudo ./08_app_api_review.sh --host testphp.vulnweb.com:80 --yes         │
  │ 4. sudo ./09_ai_llm_review.sh --host testphp.vulnweb.com:80 --yes          │
  │ 5. ./12_report_pack.sh --project-id {project.id}                          │
  │ 6. python -m ptorc_adapter.import --project {project.id} \\               │
  │         --run-dir run/{project.id}_<timestamp>/                            │
  │ 7. Back in web UI → Findings should show new ptorc-sourced findings        │
  │    Evidence Review → new items from PT-Orc manifest                        │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ PHASE 7: AUDIT TRAIL CHECK (Any user) ───────────────────────────────────┐
  │ 1. Dashboard → Audit Trail link                                            │
  │ 2. Verify events appear for:                                               │
  │    • project.created, finding.created (×6), remediation.created (×2)      │
  │    • finding.status_changed entries from workflow steps above              │
  │ 3. Confirm actor names shown (not raw UUIDs)                               │
  └───────────────────────────────────────────────────────────────────────────┘

  ┌─ PHASE 8: RBAC BOUNDARY TEST ─────────────────────────────────────────────┐
  │ 1. Login as Shivani (analyst)                                              │
  │ 2. Try going to /ui/admin/users → redirects to login (no admin access)     │
  │    (actually may load but she should not see create-user form — check)     │
  │ 3. Try to approve an approval → click Approve button                       │
  │    → Should get "Decider does not hold required approver role" error        │
  │    (or the button may simply not appear if UI enforces it)                 │
  │ 4. Confirm she cannot create a new client via Clients page                 │
  └───────────────────────────────────────────────────────────────────────────┘
""")

    print(f"\n  {BOLD}{GREEN}Setup complete.{RESET}  Project: {project.id}\n")
    print(f"  PT-Orc conf update command:")
    print(f"  {CYAN}sed -i 's/ORCHESTRATOR_PROJECT_ID=\"\"/ORCHESTRATOR_PROJECT_ID=\"{project.id}\"/' \\")
    print(f"    /home/kali/audit-orc-vapt/pt-orc/scripts/pt-orc.conf{RESET}\n")


if __name__ == "__main__":
    run()
