#!/usr/bin/env bash
# =============================================================================
# vapt_run.sh — One-command automated VAPT pipeline
#
# Workflow:
#   1. Create TG Audit Orchestrator project (get UUID)
#   2. Patch pt-orc.conf with targets + mode
#   3. Run 00_pt-orc.sh --yes  (DNS → IP → scan → TLS → web → svc → API → report)
#   4. Auto-detect the run/ output directory from step 12
#   5. Import results via ptorc_adapter  (scope, evidence, findings → TG DB)
#   6. Auto-advance G1 (scope approved) and G2 (evidence requests approved)
#   7. Print summary + next manual steps
#
# Usage:
#   sudo ./scripts/vapt_run.sh \
#       --client  "Acme Corp" \
#       --domains "app.acme.com api.acme.com" \
#       --ips     "203.0.113.10" \
#       --mode    pte \
#       --profile external \
#       --depth   standard \
#       --roe     "No DoS. Agreed window 09:00-18:00 IST. No prod-data exfil." \
#       --start   "2026-06-07T09:00:00Z" \
#       --end     "2026-06-14T18:00:00Z"
#
# Flags:
#   --client    Client/company name (required)
#   --domains   Space-separated in-scope domains  (default: "")
#   --ips       Space-separated in-scope IPs      (default: "")
#   --mode      pte | pti                          (default: pte)
#   --profile   external | web | api | hybrid      (default: external)
#   --depth     standard | deep | comprehensive    (default: standard)
#   --auth      none | basic | advanced            (default: none)
#   --roe       Rules of engagement string         (default: from conf)
#   --start     Window start ISO8601               (default: "")
#   --end       Window end ISO8601                 (default: "")
#   --skip      Comma-separated step numbers to skip, e.g. "6,9"
#   --from      Start from step N (resume)
#   --tier      ghost | normal | loud | evasion    (default: normal)
#   --dry-run   Pass through to pt-orc (no packets)
#   --retest    Mark as retest run
#   --summary   Scope summary for the TG project
# =============================================================================

set -euo pipefail

# ── Paths ─────────────────────────────────────────────────────────────────────
PTORC_DIR="/home/kali/audit-orc-vapt/pt-orc/scripts"
PTORC_CONF="${PTORC_DIR}/pt-orc.conf"
PTORC_CONF_BAK="${PTORC_DIR}/pt-orc.conf.vapt_run_bak"
PTORC_RUN_DIR="${PTORC_DIR}/run"
TG_DIR="/home/kali/MVP_ORCA/tg-audit-orchestrator"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${CYAN}[vapt_run]${NC} $*"; }
ok()   { echo -e "${GREEN}[vapt_run] ✓${NC} $*"; }
warn() { echo -e "${YELLOW}[vapt_run] ⚠${NC}  $*"; }
die()  { echo -e "${RED}[vapt_run] ✗${NC} $*" >&2; exit 1; }

# ── Arg defaults ──────────────────────────────────────────────────────────────
CLIENT=""
DOMAINS=""
IPS=""
MODE="pte"
PROFILE="external"
DEPTH="standard"
AUTH="none"
ROE=""
WIN_START=""
WIN_END=""
SKIP_STEPS=""
FROM_STEP=""
TIER=""
SUMMARY=""
DRY_RUN=0
RETEST=0

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --client)   CLIENT="$2";  shift 2 ;;
        --domains)  DOMAINS="$2"; shift 2 ;;
        --ips)      IPS="$2";     shift 2 ;;
        --mode)     MODE="$2";    shift 2 ;;
        --profile)  PROFILE="$2"; shift 2 ;;
        --depth)    DEPTH="$2";   shift 2 ;;
        --auth)     AUTH="$2";    shift 2 ;;
        --roe)      ROE="$2";     shift 2 ;;
        --start)    WIN_START="$2"; shift 2 ;;
        --end)      WIN_END="$2";   shift 2 ;;
        --skip)     SKIP_STEPS="$2"; shift 2 ;;
        --from)     FROM_STEP="$2";  shift 2 ;;
        --tier)     TIER="$2";    shift 2 ;;
        --summary)  SUMMARY="$2"; shift 2 ;;
        --dry-run)  DRY_RUN=1;    shift ;;
        --retest)   RETEST=1;     shift ;;
        -h|--help)
            sed -n '/^# Usage:/,/^# =====$/p' "$0"
            exit 0 ;;
        *) die "Unknown flag: $1" ;;
    esac
done

[[ -z "$CLIENT" ]] && die "--client is required"
[[ -z "$DOMAINS" && -z "$IPS" ]] && die "Provide --domains and/or --ips"

# ── Sanitize input: strip http(s):// prefixes and trailing paths from domains ─
# pt-orc.conf requires bare hostnames only (e.g. "app.acme.com api.acme.com")
# filenames derived from domains must not contain :// or slashes
_strip_proto() {
    echo "$1" | tr ' ' '\n' \
      | sed 's|^\s*https\?://||g' \
      | sed 's|/.*||g' \
      | sed 's|\s*$||' \
      | grep -v '^$' \
      | tr '\n' ' ' \
      | xargs
}
DOMAINS="$(_strip_proto "$DOMAINS")"
IPS="$(echo "$IPS" | tr ' ' '\n' | sed 's|^\s*||;s|\s*$||' | grep -v '^$' | tr '\n' ' ' | xargs)"

# Warn if anything still looks like a URL (catches edge cases)
for _d in $DOMAINS; do
    if [[ "$_d" == *"/"* || "$_d" == *":"* ]]; then
        die "Domain still contains invalid characters after stripping: '$_d'  (pass bare hostname, not URL)"
    fi
done

# ── Preflight: filesystem ─────────────────────────────────────────────────────
[[ -d "$PTORC_DIR" ]]      || die "PT-Orc not found at $PTORC_DIR"
[[ -f "$PTORC_CONF" ]]     || die "pt-orc.conf not found at $PTORC_CONF"
[[ -f "${PTORC_DIR}/00_pt-orc.sh" ]] || die "00_pt-orc.sh not found"
[[ -d "$TG_DIR" ]]         || die "TG Orchestrator not found at $TG_DIR"
command -v python3 >/dev/null 2>&1 || die "python3 not found"
[[ $EUID -eq 0 ]] || die "Run as root (sudo scripts/vapt_run.sh …)"

# ── Preflight: MSF PostgreSQL database ───────────────────────────────────────
echo -e "${BOLD}── Preflight: MSF database ──${NC}"

MSF_DB_CONF="/usr/share/metasploit-framework/config/database.yml"
MSF_DB_NEEDS_INIT=0

if [[ ! -f "$MSF_DB_CONF" ]]; then
    warn "database.yml missing — MSF database has never been initialised"
    MSF_DB_NEEDS_INIT=1
fi

if ! systemctl is-active --quiet postgresql; then
    log "PostgreSQL is not running — starting..."
    if [[ $MSF_DB_NEEDS_INIT -eq 1 ]]; then
        log "Running 'msfdb init' (first-time setup — this takes ~30 s)..."
        msfdb init
    else
        log "Running 'msfdb start'..."
        msfdb start
    fi
    # Give postgres a moment to accept connections
    sleep 3
fi

# Verify the connection is live using the credentials from database.yml
_msf_db_check() {
    local yml="$MSF_DB_CONF"
    [[ -f "$yml" ]] || { warn "database.yml still missing after init"; return 1; }
    local user pass db port
    user=$(grep -m1 'username:' "$yml" | awk '{print $2}' | tr -d "'\"")
    pass=$(grep -m1 'password:' "$yml" | awk '{print $2}' | tr -d "'\"")
    db=$(grep -m1 'database:'  "$yml" | awk '{print $2}' | tr -d "'\"")
    port=$(grep -m1 'port:'    "$yml" | awk '{print $2}' | tr -d "'\"")
    port="${port:-5432}"
    local result
    result=$(PGPASSWORD="$pass" psql -h 127.0.0.1 -p "$port" -U "$user" -d "$db" \
             -t -A -c "SELECT 1;" 2>&1)
    [[ "$result" == *"1"* ]] && ! [[ "$result" == *"error"* || "$result" == *"FATAL"* ]]
}

if _msf_db_check; then
    ok "MSF database connected (PostgreSQL up, database.yml valid)"
else
    # One retry: try reinit if init was skipped
    warn "DB connection test failed — attempting msfdb reinit..."
    msfdb reinit <<< "yes"
    sleep 5
    if _msf_db_check; then
        ok "MSF database connected after reinit"
    else
        warn "MSF database still not reachable — PT-Orc will run but db_nmap results"
        warn "won't persist between phases. Scan output files (.xml) will still be written."
        warn "To fix manually: sudo msfdb init && sudo msfdb start"
    fi
fi

# ── Preflight: DNS recon tools ────────────────────────────────────────────────
echo -e "${BOLD}── Preflight: DNS/recon tools ──${NC}"

_install_if_missing() {
    local cmd="$1" pkg="${2:-$1}"
    if ! command -v "$cmd" &>/dev/null; then
        log "$cmd not found — installing $pkg..."
        apt-get install -y "$pkg" -qq 2>&1 | grep -v "^$" | tail -3
        if command -v "$cmd" &>/dev/null; then
            ok "$cmd installed"
        else
            warn "$cmd still not found after install attempt — step will skip it"
        fi
    else
        ok "$cmd found: $(command -v "$cmd")"
    fi
}

_install_if_missing subfinder subfinder
_install_if_missing dnsx dnsx
_install_if_missing httpx httpx

# puredns needs Go — install go then puredns if not present
if ! command -v puredns &>/dev/null; then
    warn "puredns not found — installing via Go..."
    if ! command -v go &>/dev/null; then
        apt-get install -y golang-go -qq 2>&1 | grep -v "^$" | tail -2
    fi
    if command -v go &>/dev/null; then
        GOPATH="${GOPATH:-/root/go}"
        GOBIN="${GOPATH}/bin"
        mkdir -p "$GOBIN"
        GOPATH="$GOPATH" GOBIN="$GOBIN" \
            go install github.com/d3mondev/puredns/v2@latest 2>&1 | tail -3
        # Add go bin to PATH for this session and future shells
        export PATH="${PATH}:${GOBIN}"
        if command -v puredns &>/dev/null; then
            ok "puredns installed: $(command -v puredns)"
        else
            warn "puredns install failed — brute-force DNS step will be skipped"
        fi
    else
        warn "Go install failed — puredns will remain unavailable"
    fi
else
    ok "puredns found: $(command -v puredns)"
fi

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  TG Audit Orchestrator — Automated VAPT Pipeline${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""
log "Client   : $CLIENT"
log "Domains  : ${DOMAINS:-<none>}"
log "IPs      : ${IPS:-<none>}"
log "Mode     : $MODE  Profile: $PROFILE  Depth: $DEPTH"
echo ""

# ── Step 1: Create TG project ─────────────────────────────────────────────────
echo -e "${BOLD}── Step 1: Creating TG Audit Orchestrator project ──${NC}"

SETUP_ARGS=(
    "--client"  "$CLIENT"
    "--domains" "$DOMAINS"
    "--ips"     "$IPS"
)
[[ -n "$SUMMARY" ]] && SETUP_ARGS+=("--summary" "$SUMMARY")

PROJECT_ID="$(
    cd "$TG_DIR"
    python3 scripts/create_vapt_project.py "${SETUP_ARGS[@]}" 2>&1 | tee /dev/stderr | tail -1
)"

# Validate UUID format
if ! echo "$PROJECT_ID" | grep -qE '^[0-9a-f-]{36}$'; then
    die "create_vapt_project.py did not return a valid UUID. Output was: $PROJECT_ID"
fi

ok "Project ID: $PROJECT_ID"

# ── Step 2: Patch pt-orc.conf ─────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 2: Configuring pt-orc.conf ──${NC}"

cp "$PTORC_CONF" "$PTORC_CONF_BAK"
log "Backup saved to $PTORC_CONF_BAK"

_patch_conf() {
    local key="$1" val="$2"
    # Replace the value between double-quotes for the given variable
    sed -i "s|^${key}=.*|${key}=\"${val}\"|" "$PTORC_CONF"
}

# Build a short project name slug from client name
PROJECT_SLUG="$(echo "$CLIENT" | tr '[:lower:]' '[:upper:]' | tr -cs 'A-Z0-9' '-' | sed 's/-*$//')"
_patch_conf "PROJECT_NAME" "TG-${PROJECT_SLUG}-$(date +%b%Y)-Orc"
_patch_conf "MODE"          "$MODE"
_patch_conf "TARGET_DOMAINS" "$DOMAINS"
_patch_conf "TARGET_IPS"     "$IPS"
_patch_conf "ENGAGEMENT_PROFILE" "$PROFILE"
_patch_conf "TESTING_DEPTH"  "$DEPTH"
_patch_conf "AUTH_LEVEL"     "$AUTH"

if [[ -n "$ROE" ]];       then _patch_conf "RULES_OF_ENGAGEMENT" "$ROE";   fi
if [[ -n "$WIN_START" ]]; then _patch_conf "WINDOW_START" "$WIN_START";    fi
if [[ -n "$WIN_END" ]];   then _patch_conf "WINDOW_END"   "$WIN_END";      fi
if [[ -n "$TIER" ]];      then _patch_conf "GLOBAL_TIER"  "$TIER";         fi

ok "pt-orc.conf patched"

# Restore conf on any exit (success or failure)
_restore_conf() {
    if [[ -f "$PTORC_CONF_BAK" ]]; then
        cp "$PTORC_CONF_BAK" "$PTORC_CONF"
        rm -f "$PTORC_CONF_BAK"
        log "pt-orc.conf restored from backup"
    fi
}
trap _restore_conf EXIT

# ── Step 3: Run the PT-Orc suite ──────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 3: Running PT-Orc suite (this takes 20-90 min) ──${NC}"
log "Command: 00_pt-orc.sh --yes --project-id $PROJECT_ID"
echo ""

PTORC_FLAGS=("--yes" "--project-id" "$PROJECT_ID")
[[ $DRY_RUN -eq 1 ]] && PTORC_FLAGS+=("--dry-run")
[[ $RETEST  -eq 1 ]] && PTORC_FLAGS+=("--retest")
[[ -n "$FROM_STEP" ]] && PTORC_FLAGS+=("--from" "$FROM_STEP")

# Build --skip flags from comma-separated list
if [[ -n "$SKIP_STEPS" ]]; then
    IFS=',' read -ra _skips <<< "$SKIP_STEPS"
    for s in "${_skips[@]}"; do
        PTORC_FLAGS+=("--skip" "${s// /}")
    done
fi

START_TS=$(date +%s)

# Run from PTORC_DIR so script-relative paths resolve correctly
cd "$PTORC_DIR"
if bash "00_pt-orc.sh" "${PTORC_FLAGS[@]}"; then
    SCAN_EXIT=0
else
    SCAN_EXIT=$?
    warn "00_pt-orc.sh exited with code $SCAN_EXIT"
fi

ELAPSED=$(( $(date +%s) - START_TS ))
ok "PT-Orc suite finished in ${ELAPSED}s"

cd "$TG_DIR"

[[ $DRY_RUN -eq 1 ]] && { log "Dry-run mode — skipping import"; exit 0; }

# ── Step 4: Find the run/ output directory ────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 4: Locating run/ output directory ──${NC}"

# 12_report_pack creates: <run_dir>/<PROJECT_ID>_<SESSION_TS>/
RUN_DIR=""
while IFS= read -r -d '' d; do
    if [[ -f "${d}/scope.json" && -f "${d}/findings.jsonl" ]]; then
        RUN_DIR="$d"
        break
    fi
done < <(find "$PTORC_RUN_DIR" -maxdepth 1 -type d -name "${PROJECT_ID}_*" \
    -printf "%T@\t%p\0" 2>/dev/null \
    | sort -z -rn | cut -z -f2-)

if [[ -z "$RUN_DIR" ]]; then
    die "No run/ output dir found for project $PROJECT_ID in $PTORC_RUN_DIR"
fi

ok "Run dir: $RUN_DIR"
log "Files  : $(ls "$RUN_DIR")"

# ── Step 5: Import into TG Audit Orchestrator ─────────────────────────────────
echo ""
echo -e "${BOLD}── Step 5: Importing PT-Orc results into TG platform ──${NC}"

cd "$TG_DIR"
python3 -m ptorc_adapter \
    --project "$PROJECT_ID" \
    --run-dir "$RUN_DIR"

ok "Import complete"

# ── Step 6: Auto-advance G1 + G2 ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Step 6: Auto-advancing gates G1 + G2 ──${NC}"

python3 - <<PYEOF
import sys, os
sys.path.insert(0, os.getcwd())
import app.models  # noqa
from app.db import SessionLocal
from app.models.clients import Project
from app.models.users import User
from app.models.workflow import ApprovalRequest, ApprovalStatus
from app.services.audit import record_event, decide_approval

PROJECT_ID = "${PROJECT_ID}"

with SessionLocal() as db:
    project = db.get(Project, PROJECT_ID)
    if project is None:
        print(f"[G1/G2] Project {PROJECT_ID} not found — skipping", file=sys.stderr)
        sys.exit(0)

    admin = db.query(User).filter_by(is_active=True).first()
    actor = admin.id if admin else "system"

    # Auto-approve all pending scope approvals (G1)
    pending_scope = (
        db.query(ApprovalRequest)
        .filter_by(project_id=PROJECT_ID, target_type="scope",
                   status=ApprovalStatus.requested.value)
        .all()
    )
    for ap in pending_scope:
        decide_approval(db, approval_id=ap.id, approved=True, decider_id=actor,
                        reason="Auto-approved: scope imported from PT-Orc run")

    # Advance G1
    gates = dict(project.gates or {})
    if not gates.get("G1_scope"):
        gates["G1_scope"] = True
        project.gates = gates
        record_event(db, action="gate.advanced.G1_scope",
                     target_type="project", target_id=PROJECT_ID,
                     actor_id=actor, project_id=PROJECT_ID,
                     before={"G1_scope": False}, after={"G1_scope": True})
        print(f"  Gate G1 (scope) advanced — {len(pending_scope)} scope items auto-approved")

    # Advance G2 (evidence request list generated by pack plan)
    if not gates.get("G2_evidence_requests"):
        gates["G2_evidence_requests"] = True
        project.gates = gates
        record_event(db, action="gate.advanced.G2_evidence_requests",
                     target_type="project", target_id=PROJECT_ID,
                     actor_id=actor, project_id=PROJECT_ID,
                     before={"G2_evidence_requests": False},
                     after={"G2_evidence_requests": True})
        print("  Gate G2 (evidence requests) advanced")

    db.commit()
    print("  G1 + G2 done")
PYEOF

ok "Gates G1 and G2 advanced"

# ── Step 7: Attach VAPT pack + generate plan ──────────────────────────────────
echo ""
echo -e "${BOLD}── Step 7: Attaching VAPT pack + generating task plan ──${NC}"

python3 - <<PYEOF
import sys, os
sys.path.insert(0, os.getcwd())
import app.models  # noqa
from app.db import SessionLocal
from app.models.clients import Project
from app.services.methodology.loader import load_pack
from app.services.methodology.plan import generate_plan

PROJECT_ID = "${PROJECT_ID}"
with SessionLocal() as db:
    project = db.get(Project, PROJECT_ID)
    project.pack_id = "vapt"
    db.flush()
    pack = load_pack("vapt")
    summary = generate_plan(db, project, pack)
    db.commit()
    print(f"  Pack attached  : {pack.title}")
    print(f"  Requirements   : {summary.requirements_created}")
    print(f"  Evidence reqs  : {summary.evidence_requests_created}")
    print(f"  Tasks          : {summary.tasks_created}")
PYEOF

ok "VAPT pack attached and plan generated"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  PIPELINE COMPLETE${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Project ID : ${GREEN}${PROJECT_ID}${NC}"
echo -e "  Client     : ${CLIENT}"
echo -e "  Run dir    : ${RUN_DIR}"
echo -e "  Scan time  : ${ELAPSED}s"
echo ""
echo -e "${BOLD}  What's in the platform now:${NC}"
python3 - <<PYEOF
import sys, os
sys.path.insert(0, os.getcwd())
import app.models  # noqa
from app.db import SessionLocal
from app.models.evidence import EvidenceItem
from app.models.scope import ScopeItem
from app.models.tasks import Finding
from app.models.workflow import ApprovalRequest, AuditTrailEvent
from collections import Counter

PROJECT_ID = "${PROJECT_ID}"
with SessionLocal() as db:
    findings = db.query(Finding).filter_by(project_id=PROJECT_ID).all()
    evidence = db.query(EvidenceItem).filter_by(project_id=PROJECT_ID).all()
    scope    = db.query(ScopeItem).filter_by(project_id=PROJECT_ID).all()
    approvals = db.query(ApprovalRequest).filter_by(project_id=PROJECT_ID).all()
    events    = db.query(AuditTrailEvent).filter_by(project_id=PROJECT_ID).all()
    sev_count = Counter(f.severity for f in findings)

    print(f"  Scope items    : {len(scope)}")
    print(f"  Evidence items : {len(evidence)}")
    print(f"  Findings       : {len(findings)}  (in_review — need human approval)")
    for sev in ["critical","high","medium","low","info"]:
        n = sev_count.get(sev, 0)
        if n: print(f"    {sev.upper():8s}: {n}")
    print(f"  Approvals      : {len(approvals)}")
    print(f"  Audit events   : {len(events)}")
PYEOF

echo ""
echo -e "${BOLD}  Next steps (manual review required):${NC}"
echo ""
echo "  3a. Review evidence items — accept or reject each:"
echo "      GET  /projects/$PROJECT_ID/evidence-items/"
echo "      POST /projects/$PROJECT_ID/evidence-items/<id>/review"
echo "           {\"reviewer_status\":\"accepted\"}"
echo "      → Then advance G3:"
echo "      POST /projects/$PROJECT_ID/gates/G3_evidence_complete/advance"
echo ""
echo "  3b. Review findings — change severity + approve each:"
echo "      GET  /projects/$PROJECT_ID/findings/"
echo "      POST /projects/$PROJECT_ID/findings/<id>/change-severity"
echo "      POST /projects/$PROJECT_ID/findings/<id>/change-status"
echo "           {\"new_status\":\"approved\"}"
echo "      → Then advance G4:"
echo "      POST /projects/$PROJECT_ID/gates/G4_findings/advance"
echo ""
echo "  3c. Run QA + advance G5:"
echo "      POST /projects/$PROJECT_ID/qa/run"
echo "      POST /projects/$PROJECT_ID/gates/G5_qa/advance"
echo ""
echo "  3d. Generate deliverables + release report (G6):"
echo "      POST /projects/$PROJECT_ID/deliverables/gap-matrix"
echo "      POST /projects/$PROJECT_ID/deliverables/roadmap"
echo "      POST /projects/$PROJECT_ID/deliverables/report"
echo "      POST /projects/$PROJECT_ID/deliverables/<id>/request-release"
echo "      POST /approvals/<id>/decide  {\"approved\":true}"
echo ""
echo "  3e. Closure (G7):"
echo "      PATCH /projects/$PROJECT_ID  {\"status\":\"closed\"}"
echo "      POST  /projects/$PROJECT_ID/gates/G7_closure/advance"
echo ""
echo -e "  Web UI: ${CYAN}http://localhost:8000/ui/${NC}"
echo ""
