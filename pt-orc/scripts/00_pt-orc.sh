#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:00_NAV_TOC — Section index | nav,toc,index | L5-60
# - MRK:00_ROOT — ROOT CHECK | root,check | L61-70 | ⚠ no-insert-before
# - MRK:00_CONF — ENGAGEMENT CONFIG | conf,engagement,config,edit,pt | L71-78 | ⚠ no-insert-before; propose-before-edit
# - MRK:00_LOG — COLOURS AND LOGGING + STEP BANNER | log,colours,logging,step,banner | L79-108 | ⚠ no-insert-before
# - MRK:00_DEFAULTS — DEFAULTS + STEP STATUS ACCUMULATORS | defaults,step,status,accumulators | L109-138 | ⚠ no-insert-before
# - MRK:00_USAGE — USAGE BANNER | usage,banner | L139-187 | ⚠ no-insert-before; read-toc-first
# - MRK:00_ARGS — ARGUMENT PARSING | args,argument,parsing | L188-215 | ⚠ no-insert-before
# - MRK:00_DISCOVER — SCRIPT DISCOVERY | discover,script,discovery,find,subscript | L216-245 | ⚠ no-insert-before
# - MRK:00_CONTROL — STEP CONTROL | control,step,should,run,skip | L246-265 | ⚠ no-insert-before
# - MRK:00_RUNNER — STEP RUNNER | runner,step,invoke,subscript,capture | L266-308 | ⚠ no-insert-before; read-toc-first
# - MRK:00_SUMMARY — SUMMARY TABLE | summary,table,final,status,overview | L309-371 | ⚠ no-insert-before; read-toc-first
# - MRK:00_MAIN — MAIN | main,banner,run,loop,summary | L372-485 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 11 entries | Integrity-hash: 55d31132029fd57e | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# 00_pt-orc.sh — PT-Orc Suite Orchestrator — runs steps 1–9 and 12 sequentially.
# TechGuard.
# =============================================================================
# Coordinates the full PT-Orc 10-script suite. Runs all steps sequentially,
# forwards flags to each subscript, and suppresses interactive prompts when
# --yes is passed.
#
# USAGE:
#   sudo ./00_pt-orc.sh [OPTIONS]
#
# OPTIONS:
#   --yes               Bypass all interactive scope prompts (required for
#                       unattended / automated runs)
#   --mode <pti|pte>    Engagement mode (default: from pt-orc.conf)
#   --tier <t>          ghost|normal|loud|evasion (default: from pt-orc.conf)
#   --from <N>          Start from step N (1-7); default 1
#   --only <N>          Run only step N; skip all others
#   --skip <N>          Skip step N; repeatable (--skip 1 --skip 2)
#   --dry-run           No packets sent; prints what would run
#   --skip-active       01: skip AXFR and DNS brute-force
#   --phase <name>      03: tcp|udp|enum|report|all (forwarded to 03 only)
#   --masscan-only      03: stop after Pass 1 fast scan (forwarded to 03 only)
#   --fast              04+05: headers/tech detection only; skip gobuster+nikto
#   --skip-gobuster     05: skip directory brute-force
#   --skip-nikto        05: skip Nikto scan
#   --no-wp-detect      06: skip WP detection sweep (use existing wp_targets.txt)
#   --continue-on-error Continue to next step even if a step fails
#   -h|--help           Show this help and exit
#
# EXAMPLES:
#   sudo ./00_pt-orc.sh --yes
#   sudo ./00_pt-orc.sh --yes --from 3 --tier ghost
#   sudo ./00_pt-orc.sh --yes --only 4
#   sudo ./00_pt-orc.sh --yes --skip 1 --skip 2
#   sudo ./00_pt-orc.sh --yes --mode pti --tier normal
#   sudo ./00_pt-orc.sh --dry-run --yes
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:00_ROOT — ROOT CHECK | root,check | L61-70
# NAV-RULE: no-insert-before
# =============================================================================
if [[ "$EUID" -ne 0 ]]; then
    echo "[ERROR] This script must be run as root."
    echo "        Run: sudo $0 $*"
    exit 1
fi

# =============================================================================
# MRK:00_CONF — ENGAGEMENT CONFIG | conf,engagement,config,edit,pt | L71-78
# NAV-RULE: no-insert-before; propose-before-edit
# =============================================================================
# shellcheck source=pt-orc.conf
[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found in ${SCRIPT_DIR} — script defaults in effect"

# =============================================================================
# MRK:00_LOG — COLOURS AND LOGGING + STEP BANNER | log,colours,logging,step,banner | L79-108
# NAV-RULE: no-insert-before
# =============================================================================
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

_now() { date +'%Y-%m-%d %H:%M:%S'; }
_ts()  { date +'%Y%m%d_%H%M%S'; }
SESSION_TS="$(_ts)"

mkdir -p working
LOG_FILE="working/pt-orc_${SESSION_TS}.log"

log()      { local m="[$(_now)] $1";     echo -e "${BLUE}${m}${NC}";           echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_ok()   { local m="[$(_now)] ✓ $1";  echo -e "${GREEN}${m}${NC}";           echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_warn() { local m="[$(_now)] ⚠ $1";  echo -e "${YELLOW}${m}${NC}";          echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_err()  { local m="[$(_now)] ✗ $1";  echo -e "${RED}${m}${NC}" >&2;         echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_step() {
    local n="$1" name="$2" script="$3"
    local line; line="$(printf '━%.0s' {1..52})"
    echo ""
    echo -e "${BOLD}${BLUE}${line}${NC}"
    echo -e "${BOLD}${BLUE}  STEP ${n} — ${name}${NC}"
    echo -e "${BOLD}${BLUE}  $(basename "${script:-?}")${NC}"
    echo -e "${BOLD}${BLUE}${line}${NC}"
    echo ""
    echo "[$(_now)] START step ${n} — ${name} — $(basename "${script:-?}")" >> "$LOG_FILE" 2>/dev/null || true
}

# =============================================================================
# MRK:00_DEFAULTS — DEFAULTS + STEP STATUS ACCUMULATORS | defaults,step,status,accumulators | L109-138
# NAV-RULE: no-insert-before
# =============================================================================
AUTO_YES=0
DRY_RUN=0
MODE="${MODE:-pte}"
GLOBAL_TIER="${GLOBAL_TIER:-normal}"
FROM_STEP=1
ONLY_STEP=0
SKIP_STEPS=()
OPT_SKIP_ACTIVE=0
OPT_SKIP_GOBUSTER=0
OPT_SKIP_NIKTO=0
OPT_FAST=0
OPT_NO_WP_DETECT=0
OPT_REUSE_WORKSPACE=0
OPT_PHASE_CONTINUE=0
CONTINUE_ON_ERROR=0
OPT_AGGRESSIVE=0
OPT_NUCLEI=0
OPT_RETEST=0
OPT_API_KEY=""
OPT_PROJECT_ID=""

# Profile-based step selection — sourced from pt-orc.conf; overridden by --profile CLI arg.
# Each profile maps to a pre-planned ordered step sequence so the operator does not run
# all 10 steps for every engagement type.
# Values: external | internal | web | api | ai_llm | cloud | ad | hybrid | retest | full
ENGAGEMENT_PROFILE="${ENGAGEMENT_PROFILE:-full}"

# Result tracking (steps 1-9 and 12)
declare -A STEP_STATUS
declare -A STEP_DURATION
declare -A STEP_SCRIPT
for _n in 1 2 3 4 5 6 7 8 9 12; do
    STEP_STATUS[$_n]="—"
    STEP_DURATION[$_n]="—"
    STEP_SCRIPT[$_n]="—"
done

# =============================================================================
# MRK:00_USAGE — USAGE BANNER | usage,banner | L139-187
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
usage() {
    cat <<EOF
Usage: sudo ./00_pt-orc.sh [OPTIONS]

  --yes                 Bypass all interactive scope prompts (required for
                        unattended runs)
  --mode <pti|pte>      Engagement mode (default: from pt-orc.conf)
  --tier <t>            ghost|normal|loud|evasion (default: from pt-orc.conf)
  --from <N>            Start from step N (1-9 or 12)
  --only <N>            Run only step N
  --skip <N>            Skip step N; repeatable: --skip 1 --skip 2
  --dry-run             No packets sent; prints what would run
  --skip-active         01: skip AXFR and DNS brute-force
  --phase <name>        03: tcp|udp|enum|report|all — forwarded to 03 only
  --continue            03: after --phase, continue subsequent phases (else just
                        that one phase runs)
  --masscan-only        03: stop after Pass 1 fast scan — forwarded to 03 only
  --reuse-workspace     03: reuse existing MSF workspace (no rename-to-archive);
                        keeps prior hosts/services for narrowing + resume
  --fast                04+05: headers/tech detection only; skip gobuster+nikto
  --skip-gobuster       05: skip directory brute-force
  --skip-nikto          05: skip Nikto scan
  --no-wp-detect        06: skip WP detection sweep (uses existing wp_targets.txt)
  --continue-on-error   Continue to next step if a step fails
  --aggressive          07: enable aggressive probe mode (more CVE checks, heavier payloads)
  --nuclei              07: run nuclei templates after service probes (requires nuclei installed)
  --api-key <key>       09: bearer / API key for authenticated LLM endpoint testing
  --project-id <uuid>   12: override ORCHESTRATOR_PROJECT_ID from pt-orc.conf
  --retest              12: set retest_status=pending in report_bundle (retest runs)
  --profile <name>      Pre-planned step workflow (overrides ENGAGEMENT_PROFILE in conf):
                          external  → 1 2 3 4 5 6 7 12    DNS→IP→scan→TLS→web→WP→svc→report
                          internal  → 2 3 7 12             IP→scan→svc→report
                          web       → 4 5 8 12             TLS→web→API review→report
                          api       → 8 12                 API review→report
                          ai_llm    → 9 12                 AI/LLM review→report
                          cloud     → 1 2 3 4 5 8 12       DNS→IP→scan→TLS→web→API→report
                          ad        → 2 3 7 12             IP→scan→svc→report (AD focus)
                          hybrid    → 1 2 3 4 5 6 7 8 9 12 full suite
                          retest    → 8 9 12               App+LLM+report
                          full      → 1 2 3 4 5 6 7 8 9 12 all steps (default)
  -h|--help             Show this help and exit

Steps:
  1  DNS Recon          (01_dns_recon)
  2  IP Analysis        (02_ip_analysis)
  3  Comprehensive Scan (03_comp_scan)
  4  TLS Scan           (04_tls_scan)
  5  Web Enumeration    (05_web_enum)
  6  WPScan             (06_wpscan)
  7  Service Verify     (07_service_verify)
  8  App / API Review   (08_app_api_review)
  9  AI / LLM Review    (09_ai_llm_review)
 12  Report Pack        (12_report_pack)   ← exports to TG Audit Orchestrator

Examples:
  sudo ./00_pt-orc.sh --yes
  sudo ./00_pt-orc.sh --yes --from 3 --tier ghost
  sudo ./00_pt-orc.sh --yes --only 4
  sudo ./00_pt-orc.sh --yes --skip 1 --skip 2
  sudo ./00_pt-orc.sh --dry-run --yes
  sudo ./00_pt-orc.sh --only 3 --phase tcp --masscan-only --yes
EOF
}

# =============================================================================
# MRK:00_ARGS — ARGUMENT PARSING | args,argument,parsing | L188-215
# NAV-RULE: no-insert-before
# =============================================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes)               AUTO_YES=1; shift ;;
        --dry-run)           DRY_RUN=1; shift ;;
        --mode)              MODE="$2"; shift 2 ;;
        --tier)              GLOBAL_TIER="$2"; shift 2 ;;
        --from)              FROM_STEP="$2"; shift 2 ;;
        --only)              ONLY_STEP="$2"; shift 2 ;;
        --skip)              SKIP_STEPS+=("$2"); shift 2 ;;
        --skip-active)       OPT_SKIP_ACTIVE=1; shift ;;
        --phase)             OPT_PHASE="$2"; shift 2 ;;
        --masscan-only)      OPT_MASSCAN_ONLY=1; shift ;;
        --reuse-workspace)   OPT_REUSE_WORKSPACE=1; shift ;;
        --continue)          OPT_PHASE_CONTINUE=1; shift ;;
        --skip-gobuster)     OPT_SKIP_GOBUSTER=1; shift ;;
        --skip-nikto)        OPT_SKIP_NIKTO=1; shift ;;
        --fast)              OPT_FAST=1; shift ;;
        --no-wp-detect)      OPT_NO_WP_DETECT=1; shift ;;
        --continue-on-error) CONTINUE_ON_ERROR=1; shift ;;
        --aggressive)        OPT_AGGRESSIVE=1; shift ;;
        --nuclei)            OPT_NUCLEI=1; shift ;;
        --api-key)           OPT_API_KEY="$2"; shift 2 ;;
        --project-id)        OPT_PROJECT_ID="$2"; shift 2 ;;
        --retest)            OPT_RETEST=1; shift ;;
        --profile)           ENGAGEMENT_PROFILE="$2"; shift 2 ;;
        -h|--help)           usage; exit 0 ;;
        *) log_err "Unknown argument: $1"; usage; exit 1 ;;
    esac
done

# =============================================================================
# MRK:00_PROFILE — PROFILE STEP RESOLUTION | profile,steps,workflow,sequence
# NAV-RULE: no-insert-before
# =============================================================================
# Maps ENGAGEMENT_PROFILE → ordered list of step numbers to run.
# Evaluated after argument parsing so --profile CLI override is respected.
# --skip / --from / --only flags still filter within the profile's step list.
_profile_steps() {
    case "${ENGAGEMENT_PROFILE:-full}" in
        external)  echo "1 2 3 4 5 6 7 12" ;;   # DNS→IP→scan→TLS→web→WPScan→svc→report
        internal)  echo "2 3 7 12" ;;            # IP→scan→svc→report (no DNS)
        web)       echo "4 5 8 12" ;;            # TLS→web enum→App/API→report
        api)       echo "8 12" ;;                # App/API review→report only
        ai_llm)    echo "9 12" ;;                # AI/LLM review→report only
        cloud)     echo "1 2 3 4 5 8 12" ;;      # DNS→IP→scan→TLS→web→API→report
        ad)        echo "2 3 7 12" ;;            # IP→scan→svc (AD service probes)→report
        hybrid)    echo "1 2 3 4 5 6 7 8 9 12" ;; # every step
        retest)    echo "8 9 12" ;;              # App/API + AI/LLM retest run
        full|*)    echo "1 2 3 4 5 6 7 8 9 12" ;; # default: all steps
    esac
}
read -ra PROFILE_STEPS <<< "$(_profile_steps)"

# =============================================================================
# MRK:00_DISCOVER — SCRIPT DISCOVERY | discover,script,discovery,find,subscript | L216-245
# NAV-RULE: no-insert-before
# =============================================================================
# Finds the subscript for step N. Prefers unversioned 0N_*.sh (normalised form);
# falls back to highest-versioned 0N_*_v*.sh if no unversioned variant exists.
# Excludes ACTUAL_RUN subdirectory.
find_script() {
    local n="$1"
    local prefix
    prefix="${SCRIPT_DIR}/$(printf '%02d' "$n")_"
    local unversioned=()
    local matches=()
    local f
    for f in "${prefix}"*_v*.sh; do
        [[ -f "$f" ]] || continue
        [[ "$f" == */ACTUAL_RUN/* ]] && continue
        matches+=("$f")
    done
    for f in "${prefix}"*.sh; do
        [[ -f "$f" ]] || continue
        [[ "$f" == */ACTUAL_RUN/* ]] && continue
        [[ "$f" == *_v*.sh ]] && continue
        unversioned+=("$f")
    done
    if [[ "${#unversioned[@]}" -gt 0 ]]; then
        printf '%s\n' "${unversioned[@]}" | sort | head -1
        return 0
    fi
    [[ "${#matches[@]}" -gt 0 ]] && printf '%s\n' "${matches[@]}" | sort | tail -1 || true
}

# =============================================================================
# MRK:00_CONTROL — STEP CONTROL | control,step,should,run,skip | L246-265
# NAV-RULE: no-insert-before
# =============================================================================
should_run() {
    local n="$1"
    # --only: run only that step
    if [[ "$ONLY_STEP" -ne 0 ]]; then
        [[ "$n" -eq "$ONLY_STEP" ]] && return 0 || return 1
    fi
    # --from: skip steps before FROM_STEP
    [[ "$n" -lt "$FROM_STEP" ]] && return 1
    # --skip: explicitly skipped steps
    local s
    for s in "${SKIP_STEPS[@]+"${SKIP_STEPS[@]}"}"; do
        [[ "$n" -eq "$s" ]] && return 1
    done
    return 0
}

# =============================================================================
# MRK:00_RUNNER — STEP RUNNER | runner,step,invoke,subscript,capture | L266-308
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# Usage: run_step <n> <name> [flags_to_pass...]
run_step() {
    local n="$1" name="$2"; shift 2

    local script
    script="$(find_script "$n")"

    if [[ -z "$script" ]]; then
        log_err "Step ${n} (${name}): script not found — ${SCRIPT_DIR}/0${n}_*.sh"
        STEP_STATUS[$n]="NOT FOUND"
        STEP_DURATION[$n]="—"
        return 1
    fi

    STEP_SCRIPT[$n]="$(basename "$script")"
    log_step "$n" "$name" "$script"
    log "Flags: $*"

    local t_start; t_start=$(date +%s)

    # Run subscript — CWD is SCRIPT_DIR (set in main); subscripts use relative paths
    bash "$script" "$@"
    local rc=$?

    local elapsed=$(( $(date +%s) - t_start ))
    local mm=$(( elapsed / 60 ))
    local ss=$(( elapsed % 60 ))
    STEP_DURATION[$n]="${mm}m${ss}s"

    if [[ $rc -eq 0 ]]; then
        STEP_STATUS[$n]="OK"
        log_ok "Step ${n} (${name}) completed — ${mm}m${ss}s"
    else
        STEP_STATUS[$n]="FAIL(rc=${rc})"
        log_err "Step ${n} (${name}) failed — rc=${rc}, elapsed=${mm}m${ss}s"
        return $rc
    fi
}

# =============================================================================
# MRK:00_SUMMARY — SUMMARY TABLE | summary,table,final,status,overview | L309-371
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
print_summary() {
    local total="${1:-}"
    local -A names=(
        [1]="DNS Recon"
        [2]="IP Analysis"
        [3]="Comprehensive Scan"
        [4]="TLS Scan"
        [5]="Web Enumeration"
        [6]="WPScan"
        [7]="Service Verify"
        [8]="App / API Review"
        [9]="AI / LLM Review"
        [12]="Report Pack"
    )
    local line; line="$(printf '━%.0s' {1..60})"

    echo ""
    echo -e "${BOLD}${GREEN}${line}${NC}"
    echo -e "${BOLD}${GREEN}  PT-Orc Suite Summary — ${PROJECT_NAME:-[project]}${NC}"
    [[ -n "$total" ]] && echo -e "${BOLD}${GREEN}  Total elapsed: ${total}${NC}"
    echo -e "${BOLD}${GREEN}${line}${NC}"
    printf "${BOLD}  %-4s  %-22s  %-26s  %-14s  %s${NC}\n" \
        "Step" "Name" "Script" "Status" "Duration"
    echo -e "  $(printf '─%.0s' {1..68})"

    local all_ok=1
    local n
    for n in "${PROFILE_STEPS[@]}"; do
        local status="${STEP_STATUS[$n]:-—}"
        local dur="${STEP_DURATION[$n]:-—}"
        local scr="${STEP_SCRIPT[$n]:-—}"
        local color
        case "$status" in
            OK)             color="$GREEN"  ;;
            SKIP|"—")       color="$CYAN"   ;;
            "NOT FOUND")    color="$YELLOW" ;;
            FAIL*)          color="$RED"; all_ok=0 ;;
            *)              color="$NC"     ;;
        esac
        printf "  ${color}%-4s  %-22s  %-26s  %-14s  %s${NC}\n" \
            "$n" "${names[$n]}" "${scr:0:26}" "$status" "$dur"
    done

    echo -e "  ${BOLD}${GREEN}${line}${NC}"
    echo -e "  Log:  ${LOG_FILE}"
    echo ""

    # Write summary to log
    {
        echo ""
        echo "=== PT-Orc Suite Summary ==="
        echo "Project: ${PROJECT_NAME:-[project]}"
        [[ -n "$total" ]] && echo "Total elapsed: ${total}"
        for n in "${PROFILE_STEPS[@]}"; do
            printf "  Step %-2s  %-22s  %-14s  %s\n" \
                "$n" "${names[$n]}" "${STEP_STATUS[$n]:-—}" "${STEP_DURATION[$n]:-—}"
        done
    } >> "$LOG_FILE" 2>/dev/null || true

    return $(( all_ok == 1 ? 0 : 1 ))
}

# =============================================================================
# MRK:00_MAIN — MAIN | main,banner,run,loop,summary | L372-485
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
main() {
    # Work from SCRIPT_DIR — all subscripts use relative paths for working/ scripts/ evidence/
    cd "${SCRIPT_DIR}"

    # ─── Banner ───────────────────────────────────────────────────────────────
    local line; line="$(printf '═%.0s' {1..52})"
    echo -e "${GREEN}"
    echo "${line}"
    echo "  PT-Orc Suite Orchestrator"
    echo "  TechGuard."
    printf "  %-22s %s\n" "Project:"   "${PROJECT_NAME:-[see pt-orc.conf]}"
    printf "  %-22s %s\n" "Mode:"      "${MODE}"
    printf "  %-22s %s\n" "Tier:"      "${GLOBAL_TIER}"
    printf "  %-22s %s\n" "Profile:"   "${ENGAGEMENT_PROFILE}"
    printf "  %-22s %s\n" "Steps:"     "${PROFILE_STEPS[*]}"
    printf "  %-22s %s\n" "Auto-yes:"  "$([ "$AUTO_YES" -eq 1 ] && echo 'YES — no prompts' || echo 'NO — prompts active')"
    printf "  %-22s %s\n" "Dry-run:"   "$([ "$DRY_RUN"  -eq 1 ] && echo 'YES' || echo 'no')"
    [[ "$FROM_STEP"  -gt 1 ]] && printf "  %-22s %s\n" "Starting from:" "step ${FROM_STEP}"
    [[ "$ONLY_STEP"  -ne 0 ]] && printf "  %-22s %s\n" "Only step:"    "${ONLY_STEP}"
    [[ "${#SKIP_STEPS[@]}" -gt 0 ]] && printf "  %-22s %s\n" "Skipping steps:" "${SKIP_STEPS[*]}"
    echo "${line}"
    echo -e "${NC}"

    [[ "$AUTO_YES" -ne 1 ]] && log_warn "No --yes flag — scripts will pause for scope confirmation prompts"

    {
        echo "=== PT-Orc Suite Start ==="
        echo "Project:   ${PROJECT_NAME:-[project]}"
        echo "Mode:      ${MODE}"
        echo "Tier:      ${GLOBAL_TIER}"
        echo "Profile:   ${ENGAGEMENT_PROFILE}"
        echo "Steps:     ${PROFILE_STEPS[*]}"
        echo "Session:   ${SESSION_TS}"
        echo "Auto-yes:  ${AUTO_YES}"
        echo "Dry-run:   ${DRY_RUN}"
    } >> "$LOG_FILE" 2>/dev/null || true

    # ─── Common flags forwarded to every subscript ────────────────────────────
    local common=()
    [[ "$AUTO_YES" -eq 1 ]] && common+=("--yes")
    [[ "$DRY_RUN"  -eq 1 ]] && common+=("--dry-run")

    # ─── Run loop ─────────────────────────────────────────────────────────────
    local suite_start; suite_start=$(date +%s)
    local n

    for n in "${PROFILE_STEPS[@]}"; do
        if ! should_run "$n"; then
            STEP_STATUS[$n]="SKIP"
            STEP_DURATION[$n]="—"
            STEP_SCRIPT[$n]="—"
            log "  Step ${n}: skipped"
            continue
        fi

        # Build per-step flags on top of common
        local flags=("${common[@]+"${common[@]}"}")

        case "$n" in
            1)
                [[ "$OPT_SKIP_ACTIVE" -eq 1 ]] && flags+=("--skip-active")
                ;;
            2)
                flags+=("--mode" "$MODE")
                ;;
            3)
                flags+=("--mode" "$MODE" "--tier" "$GLOBAL_TIER")
                [[ -n "${OPT_PHASE:-}"       ]] && flags+=("--phase" "$OPT_PHASE")
                [[ "${OPT_MASSCAN_ONLY:-0}" -eq 1 ]] && flags+=("--masscan-only")
                [[ "${OPT_REUSE_WORKSPACE:-0}" -eq 1 ]] && flags+=("--reuse-workspace")
                [[ "${OPT_PHASE_CONTINUE:-0}"  -eq 1 ]] && flags+=("--continue")
                ;;
            4)
                [[ "$OPT_FAST" -eq 1 ]] && flags+=("--fast")
                ;;
            5)
                flags+=("--tier" "$GLOBAL_TIER")
                [[ "$OPT_SKIP_GOBUSTER" -eq 1 ]] && flags+=("--skip-gobuster")
                [[ "$OPT_SKIP_NIKTO"    -eq 1 ]] && flags+=("--skip-nikto")
                [[ "$OPT_FAST"          -eq 1 ]] && flags+=("--fast")
                ;;
            6)
                flags+=("--mode" "$MODE" "--tier" "$GLOBAL_TIER")
                [[ "$OPT_NO_WP_DETECT" -eq 0 ]] && flags+=("--detect")
                ;;
            7)
                flags+=("--mode" "$MODE")
                [[ "$OPT_AGGRESSIVE" -eq 1 ]] && flags+=("--aggressive")
                [[ "$OPT_NUCLEI"     -eq 1 ]] && flags+=("--nuclei")
                ;;
            8)
                flags+=("--tier" "$GLOBAL_TIER")
                [[ "$OPT_FAST" -eq 1 ]] && flags+=("--fast")
                ;;
            9)
                flags+=("--tier" "$GLOBAL_TIER")
                [[ -n "$OPT_API_KEY" ]] && flags+=("--api-key" "$OPT_API_KEY")
                ;;
            12)
                [[ -n "$OPT_PROJECT_ID" ]] && flags+=("--project-id" "$OPT_PROJECT_ID")
                [[ "$OPT_RETEST" -eq 1  ]] && flags+=("--retest")
                ;;
        esac

        local step_names=([1]="DNS Recon" [2]="IP Analysis" [3]="Comprehensive Scan" [4]="TLS Scan" [5]="Web Enumeration" [6]="WPScan" [7]="Service Verify" [8]="App / API Review" [9]="AI / LLM Review" [12]="Report Pack")

        if ! run_step "$n" "${step_names[$n]}" "${flags[@]+"${flags[@]}"}"; then
            if [[ "$CONTINUE_ON_ERROR" -eq 1 ]]; then
                log_warn "Step ${n} failed — continuing (--continue-on-error)"
            else
                log_err "Suite aborted at step ${n}. Use --continue-on-error to proceed past failures."
                local suite_elapsed=$(( $(date +%s) - suite_start ))
                local mm=$(( suite_elapsed / 60 )); local ss=$(( suite_elapsed % 60 ))
                print_summary "${mm}m${ss}s"
                exit 1
            fi
        fi
    done

    local suite_elapsed=$(( $(date +%s) - suite_start ))
    local mm=$(( suite_elapsed / 60 ))
    local ss=$(( suite_elapsed % 60 ))
    print_summary "${mm}m${ss}s"
}

main

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
