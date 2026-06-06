#!/usr/bin/env bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:06_NAV_TOC — Section index | nav,toc,index | L5-44
# - MRK:06_LOG — COLOURS AND LOGGING | log,colours,logging | L45-62 | ⚠ no-insert-before
# - MRK:06_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L63-105 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:06_USAGE — USAGE | usage,06 | L106-135 | ⚠ no-insert-before
# - MRK:06_ARGS — ARGUMENT PARSING | args,argument,parsing | L136-157 | ⚠ no-insert-before
# - MRK:06_DEPS — DEPENDENCY CHECK | deps,dependency,check | L158-189 | ⚠ no-insert-before; read-toc-first
# - MRK:06_DETECT — PHASE 1 WP DETECTION SWEEP | detect,phase,wp,detection,sweep | L190-298 | ⚠ no-insert-before; read-toc-first
# - MRK:06_LOAD — PHASE 2 TARGET LOADING | load,phase,target,loading,read | L299-328 | ⚠ no-insert-before
# - MRK:06_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L329-362 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:06_HELP — HELPERS | help,helpers,sanitize,label,url | L363-380 | ⚠ no-insert-before
# - MRK:06_STATE — PER-TARGET ACCUMULATORS | state,target,accumulators,indexed,url | L381-396 | ⚠ no-insert-before
# - MRK:06_ASSESS — PER-TARGET ASSESSMENT | assess,target,assessment,step,basic | L397-755 | ⚠ no-insert-before; read-toc-first
# - MRK:06_REPORT — CONSOLIDATED REPORT | report,consolidated,working,wpscan,ts | L756-923 | ⚠ no-insert-before; read-toc-first
# - MRK:06_MAIN — MAIN entry point | main,entry,point | L924-1003 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 13 entries | Integrity-hash: 8f78e30dcdebfea9 | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# 06_wpscan.sh — WordPress Detection & Security Assessment — TechGuard.
# =============================================================================
# Purpose:
#   Two-phase WordPress assessment:
#     Phase 1 — WP Detection sweep: quick curl-based checks across all web
#               targets from scripts/targets.txt to identify WordPress instances.
#               Populates scripts/wp_targets.txt for phase 2.
#     Phase 2 — WPScan full assessment: per-target deep scan with plugin/theme/
#               user/vulnerability enumeration, xmlrpc probe, wp-json exposure,
#               config file exposure, and security header validation.
#
#   script 05_web_enum.sh detects WordPress during web enumeration and appends
#   to scripts/wp_targets.txt — this script picks that up and runs full WPScan.
#   Can also run standalone with --detect to perform the detection sweep first.
#
# Prerequisites: wpscan, curl; nikto optional for wp-admin exposure check
# Evidence:      evidence/_wpscan/<sanitized_url>/ per-target + summary report
# Run after:     05_web_enum.sh (reads scripts/wp_targets.txt)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:06_LOG — COLOURS AND LOGGING | log,colours,logging | L45-62
# NAV-RULE: no-insert-before
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

_now() { date +'%Y-%m-%d %H:%M:%S'; }
_ts()  { date +'%Y%m%d_%H%M%S'; }
SESSION_TS="$(_ts)"

log()      { echo -e "${BLUE}[$(_now)]${NC} $*"; }
log_ok()   { echo -e "${GREEN}[$(_now)] ✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}[$(_now)] ⚠${NC} $*"; }
log_err()  { echo -e "${RED}[$(_now)] ✗${NC} $*" >&2; }
log_info() { echo -e "${CYAN}[$(_now)]   ${NC}$*"; }

# =============================================================================
# MRK:06_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L63-105
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

# Load shared engagement config (PROJECT_NAME, MODE, WPSCAN_API_TOKEN,
# WPSCAN_API_BUDGET, WP_TARGETS_FILE, …)
# shellcheck source=pt-orc.conf
[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found in ${SCRIPT_DIR} — set variables in pt-orc.conf"

# Shared helpers (logging, DB access, trail/notes writer)
# shellcheck source=orc-common-lib.sh
[[ -f "${SCRIPT_DIR}/orc-common-lib.sh" ]] && source "${SCRIPT_DIR}/orc-common-lib.sh" \
    || echo "[WARN] orc-common-lib.sh not found — trail/notes writes will be disabled"

EVIDENCE_BASE="evidence"
AUTO_YES=0
DRY_RUN=0

# ── Detection sweep config ────────────────────────────────────────────────────
# Targets file for detection sweep (--detect mode). Usually all web targets.
WEB_TARGETS_FILE="scripts/targets.txt"
DETECT_PORTS="80 443 8080 8443"
DETECT_TIMEOUT=8

# ── Stealth tier ──────────────────────────────────────────────────────────────
# Controls WPScan throttle, user-agent rotation, and request delay.
# normal / loud: standard scan
# ghost / evasion: throttle 2000ms + --random-user-agent
TIER="normal"

# ── WPScan options ────────────────────────────────────────────────────────────
WPSCAN_TIMEOUT=300        # seconds per target
# VAPT-enhanced: added ap=all plugins, at=all themes for aggressive coverage
# vp=vuln plugins, vt=vuln themes, u=users, tt=timthumbs, cb=config backups,
# dbe=db exports, er=error logs, ap=all plugins (aggressive), m=media
WPSCAN_ENUMERATE="vp,vt,u,tt,cb,dbe,er,m"
WPSCAN_ENUMERATE_AGGRESSIVE="ap,at,u1-100,tt,cb,dbe,er,m"  # --aggressive mode
WPSCAN_THREADS=5           # reduce for evasion
WPSCAN_MAX_THREADS_EVASION=1
WPSCAN_AGGRESSIVE=0        # set to 1 via --aggressive flag

# ── Runtime flags (set by arg parser) ────────────────────────────────────────
DO_DETECT=0
DETECT_ONLY=0

# =============================================================================
# MRK:06_USAGE — USAGE | usage,06 | L106-135
# NAV-RULE: no-insert-before
# =============================================================================

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --yes                   Skip scope confirmation prompt (AUTO_YES=1)
  --dry-run               Print commands without executing them
  --mode <pti|pte>        Set engagement mode (default: pte)
  --tier <ghost|normal|loud|evasion>
                          Stealth tier controlling throttle and threads (default: normal)
  --api-token <TOKEN>     WPScan API token (overrides WPSCAN_API_TOKEN in config)
  --detect                Run WP detection sweep first, then run WPScan
  --detect-only           Run WP detection sweep only; do not run WPScan
  --targets-file <FILE>   Override WP_TARGETS_FILE (default: scripts/wp_targets.txt)
  --aggressive            Enable aggressive enumeration (all plugins/themes, extended user range)
  -h, --help              Show this help message and exit

Examples:
  $0 --detect
  $0 --detect-only
  $0 --tier evasion --api-token YOUR_TOKEN
  $0 --targets-file /tmp/my_wp_targets.txt --yes
  $0 --dry-run --detect
EOF
}

# =============================================================================
# MRK:06_ARGS — ARGUMENT PARSING | args,argument,parsing | L136-157
# NAV-RULE: no-insert-before
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes)           AUTO_YES=1 ; shift ;;
            --dry-run)       DRY_RUN=1  ; shift ;;
            --mode)          MODE="$2"  ; shift 2 ;;
            --tier)          TIER="$2"  ; shift 2 ;;
            --api-token)     WPSCAN_API_TOKEN="$2" ; shift 2 ;;
            --detect)        DO_DETECT=1 ; shift ;;
            --detect-only)   DETECT_ONLY=1 ; DO_DETECT=1 ; shift ;;
            --targets-file)  WP_TARGETS_FILE="$2" ; shift 2 ;;
            --aggressive)    WPSCAN_AGGRESSIVE=1 ; shift ;;
            -h|--help)       usage ; exit 0 ;;
            *) log_err "Unknown argument: $1"; usage; exit 1 ;;
        esac
    done
}

# =============================================================================
# MRK:06_DEPS — DEPENDENCY CHECK | deps,dependency,check | L158-189
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

check_deps() {
    log "Checking dependencies..."
    local missing=0

    for tool in wpscan curl; do
        if command -v "$tool" &>/dev/null; then
            log_ok "  ${tool}: found"
        else
            log_err "  ${tool}: NOT FOUND — required"
            (( missing++ )) || true
        fi
    done

    for tool in nikto whatweb; do
        if command -v "$tool" &>/dev/null; then
            log_ok "  ${tool}: found (optional)"
        else
            log_warn "  ${tool}: not found — optional checks will be skipped"
        fi
    done

    if [[ "$missing" -gt 0 ]]; then
        log_err "Missing ${missing} required tool(s). Install and re-run."
        exit 1
    fi
}

# =============================================================================
# MRK:06_DETECT — PHASE 1 WP DETECTION SWEEP | detect,phase,wp,detection,sweep | L190-298
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

detect_wordpress() {
    log "Phase 1 — WordPress Detection Sweep"

    if [[ ! -f "$WEB_TARGETS_FILE" ]]; then
        log_err "Web targets file not found: ${WEB_TARGETS_FILE}"
        log_err "Run 01_dns_recon.sh / 03_comp_scan.sh first, or check WEB_TARGETS_FILE."
        return 1
    fi

    # Ensure wp_targets.txt directory exists
    local wp_dir
    wp_dir="$(dirname "$WP_TARGETS_FILE")"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        mkdir -p "$wp_dir"
        touch "$WP_TARGETS_FILE"
    fi

    local detected=0

    while IFS= read -r line; do
        # Skip comments and blank lines
        [[ -z "$line" || "$line" == \#* ]] && continue
        # Only accept IPv4 addresses
        [[ ! "$line" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] && continue

        local ip="$line"

        for port in $DETECT_PORTS; do
            # Build URL — use https for TLS ports
            local proto="http"
            [[ "$port" == "443" || "$port" == "8443" ]] && proto="https"
            local url="${proto}://${ip}:${port}"

            if [[ "$DRY_RUN" -eq 1 ]]; then
                log_info "  [DRY-RUN] curl -skL --max-time ${DETECT_TIMEOUT} -A 'Mozilla/5.0 (compatible; bot)' ${url}"
                log_info "  [DRY-RUN] curl -skL --max-time ${DETECT_TIMEOUT} -A 'Mozilla/5.0 (compatible; bot)' ${url}/wp-login.php"
                continue
            fi

            # ── Primary check: body indicators ───────────────────────────────
            local body
            body=$(curl -skL --max-time "$DETECT_TIMEOUT" \
                   -A "Mozilla/5.0 (compatible; bot)" \
                   "$url" 2>/dev/null || true)

            # ── Header check ─────────────────────────────────────────────────
            local headers
            headers=$(curl -skL --max-time "$DETECT_TIMEOUT" \
                      -A "Mozilla/5.0 (compatible; bot)" \
                      -I "$url" 2>/dev/null || true)

            local wp_found=0

            # Body indicators
            if echo "$body" | grep -qiE "wp-content|wp-includes|wp-login|wordpress|wlwmanifest"; then
                wp_found=1
            fi

            # Header indicator
            if echo "$headers" | grep -qi "X-Powered-By: WordPress"; then
                wp_found=1
            fi

            # Confirmation path probes (wp-login.php, wp-admin/, wp-json/)
            if [[ "$wp_found" -eq 0 ]]; then
                for path in "/wp-login.php" "/wp-admin/" "/wp-json/"; do
                    local probe_code
                    probe_code=$(curl -skL -o /dev/null -w "%{http_code}" \
                                 --max-time "$DETECT_TIMEOUT" \
                                 -A "Mozilla/5.0 (compatible; bot)" \
                                 "${url}${path}" 2>/dev/null || echo "000")
                    # 200 or redirect (301/302) on these paths suggests WP
                    if [[ "$probe_code" =~ ^(200|301|302)$ ]]; then
                        wp_found=1
                        break
                    fi
                done
            fi

            if [[ "$wp_found" -eq 1 ]]; then
                log_warn "  WordPress detected: ${url}"

                # Append to WP_TARGETS_FILE — idempotent (no duplicates)
                if ! grep -qxF "$url" "$WP_TARGETS_FILE" 2>/dev/null; then
                    echo "$url" >> "$WP_TARGETS_FILE"
                    log_info "  Added to ${WP_TARGETS_FILE}: ${url}"
                else
                    log_info "  Already in ${WP_TARGETS_FILE}: ${url} — skipped"
                fi
                (( detected++ )) || true
            fi
        done
    done < "$WEB_TARGETS_FILE"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] Detection sweep complete (no actual requests sent)"
        return 0
    fi

    log_ok "Phase 1 complete — ${detected} WordPress instance(s) found"
    log_info "  WP targets file: ${WP_TARGETS_FILE}"
    echo ""
}

# =============================================================================
# MRK:06_LOAD — PHASE 2 TARGET LOADING | load,phase,target,loading,read | L299-328
# NAV-RULE: no-insert-before
# =============================================================================

WP_TARGETS=()

load_wp_targets() {
    log "Loading WordPress targets from ${WP_TARGETS_FILE}..."

    if [[ ! -f "$WP_TARGETS_FILE" ]]; then
        log_warn "WP targets file not found: ${WP_TARGETS_FILE}"
        log_warn "Run with --detect first, or populate ${WP_TARGETS_FILE} manually."
        return 0
    fi

    while IFS= read -r line; do
        [[ -z "$line" || "$line" == \#* ]] && continue
        WP_TARGETS+=("$line")
    done < "$WP_TARGETS_FILE"

    if [[ "${#WP_TARGETS[@]}" -eq 0 ]]; then
        log_warn "No WordPress targets found in ${WP_TARGETS_FILE}."
        log_warn "Run with --detect first, or add URLs to ${WP_TARGETS_FILE}."
        return 0
    fi

    log_ok "Loaded ${#WP_TARGETS[@]} WordPress target(s)"
}

# =============================================================================
# MRK:06_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L329-362
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

scope_confirm() {
    local count="${1:-0}"
    [[ "$AUTO_YES" -eq 1 ]] && return 0

    echo ""
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  SCOPE CONFIRMATION — 06_wpscan.sh${NC}"
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════════${NC}"
    printf "  %-24s %s\n" "Project:"       "$PROJECT_NAME"
    printf "  %-24s %s\n" "Mode:"          "$MODE"
    printf "  %-24s %s\n" "Tier:"          "$TIER"
    printf "  %-24s %s\n" "WP targets:"    "$count"
    printf "  %-24s %s\n" "API token:"     "$([ -n "$WPSCAN_API_TOKEN" ] && echo "set (budget: ${WPSCAN_API_BUDGET})" || echo "not set — no CVE data")"
    printf "  %-24s %s\n" "Enumerate:"     "$WPSCAN_ENUMERATE"
    printf "  %-24s %s\n" "Dry run:"       "$([ "$DRY_RUN" -eq 1 ] && echo "YES" || echo "no")"
    echo ""
    echo -e "${BOLD}  WordPress targets:${NC}"
    for url in "${WP_TARGETS[@]}"; do
        printf "    %s\n" "$url"
    done
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}Confirm authorisation is in place and scope is correct.${NC}"
    echo -n "  Type YES to continue: "
    read -r answer
    [[ "$answer" != "YES" ]] && { echo "Aborted."; exit 0; }
    echo ""
}

# =============================================================================
# MRK:06_HELP — HELPERS | help,helpers,sanitize,label,url | L363-380
# NAV-RULE: no-insert-before
# =============================================================================

# sanitize_label <url> — strip protocol, replace /:. with _
sanitize_label() {
    local url="$1"
    # Remove protocol prefix
    local label="${url#http://}"
    label="${label#https://}"
    # Replace path separators, dots, colons with underscores
    label="${label//[:\/.]/_}"
    # Strip trailing underscore if present
    label="${label%_}"
    echo "$label"
}

# =============================================================================
# MRK:06_STATE — PER-TARGET ACCUMULATORS | state,target,accumulators,indexed,url | L381-396
# NAV-RULE: no-insert-before
# =============================================================================

declare -A WP_VERSION
declare -A WP_PLUGINS
declare -A WP_THEMES
declare -A WP_USERS
declare -A WP_VULN_COUNT
declare -A WP_XMLRPC
declare -A WP_JSON_USERS
declare -A WP_EXPOSED_FILES
declare -A WP_SEC_HEADERS
declare -A WP_API_USED

# =============================================================================
# MRK:06_ASSESS — PER-TARGET ASSESSMENT | assess,target,assessment,step,basic | L397-755
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

assess_wordpress() {
    local url="$1"
    local label
    label="$(sanitize_label "$url")"
    local outdir="${EVIDENCE_BASE}/_wpscan/${label}"
    local ts; ts="$(_ts)"

    if [[ "$DRY_RUN" -eq 0 ]]; then
        mkdir -p "$outdir"
    else
        log_info "  [DRY-RUN] mkdir -p ${outdir}"
    fi

    # Initialise accumulators
    WP_VERSION["$label"]="[unknown]"
    WP_PLUGINS["$label"]=""
    WP_THEMES["$label"]=""
    WP_USERS["$label"]=""
    WP_VULN_COUNT["$label"]="0"
    WP_XMLRPC["$label"]="not checked"
    WP_JSON_USERS["$label"]="not checked"
    WP_EXPOSED_FILES["$label"]=""
    WP_SEC_HEADERS["$label"]=""
    WP_API_USED["$label"]="no"

    # ── Build tier-specific WPScan flags ──────────────────────────────────────
    local throttle_flags=()
    local thread_flags=()
    case "$TIER" in
        ghost|evasion)
            throttle_flags=("--throttle" "2000")
            thread_flags=("--max-threads" "$WPSCAN_MAX_THREADS_EVASION")
            ;;
        normal|loud|*)
            thread_flags=("--max-threads" "$WPSCAN_THREADS")
            ;;
    esac

    # ── Step 1 — Basic WPScan (no API) ───────────────────────────────────────
    log "  [${url}] Step 1: Basic WPScan (version/info, no API)"
    local basic_out="${outdir}/wpscan_basic_${ts}.txt"

    local basic_cmd=(
        wpscan
        --url "$url"
        --no-banner
        --random-user-agent
        --disable-tls-checks
        --no-update
        "${throttle_flags[@]}"
        "${thread_flags[@]}"
    )

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] timeout ${WPSCAN_TIMEOUT} ${basic_cmd[*]} > ${basic_out}"
    else
        {
            echo "# WPScan Basic — ${url}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "# Tier:       ${TIER}"
            echo "---"
            timeout "$WPSCAN_TIMEOUT" "${basic_cmd[@]}" 2>&1 \
                || log_warn "  wpscan basic timed out or errored for ${url}"
        } > "$basic_out" || true

        # Parse WP version
        local wp_ver
        wp_ver=$(grep -oE "WordPress version [0-9][0-9a-zA-Z._-]*" "$basic_out" \
                 | head -1 | sed 's/WordPress version //' || true)
        [[ -n "$wp_ver" ]] && { WP_VERSION["$label"]="$wp_ver"; log_info "  WP Version: ${wp_ver}"; }

        log_ok "  Basic scan saved: ${basic_out}"
    fi

    # ── Step 2 — Full enumeration ─────────────────────────────────────────────
    local _enum_flags="$WPSCAN_ENUMERATE"
    [[ "$WPSCAN_AGGRESSIVE" -eq 1 ]] && _enum_flags="$WPSCAN_ENUMERATE_AGGRESSIVE"
    log "  [${url}] Step 2: Full enumeration (${_enum_flags}$([ "$WPSCAN_AGGRESSIVE" -eq 1 ] && echo ' — AGGRESSIVE'))"
    local full_out="${outdir}/wpscan_full_${ts}.txt"

    local api_flags=()
    if [[ -n "$WPSCAN_API_TOKEN" && "$WPSCAN_API_BUDGET" -gt 0 ]]; then
        api_flags=("--api-token" "$WPSCAN_API_TOKEN")
        (( WPSCAN_API_BUDGET-- )) || true
        WP_API_USED["$label"]="yes"
        log_info "  API token in use (budget remaining: ${WPSCAN_API_BUDGET})"
    elif [[ -n "$WPSCAN_API_TOKEN" && "$WPSCAN_API_BUDGET" -le 0 ]]; then
        log_warn "  API budget exhausted — running without API token for ${url}"
    else
        log_info "  No API token set — vulnerability data will not be available"
    fi

    local aggressive_scan_flags=()
    [[ "$WPSCAN_AGGRESSIVE" -eq 1 ]] && aggressive_scan_flags=("--plugins-detection" "aggressive" "--themes-detection" "aggressive")

    local full_cmd=(
        wpscan
        --url "$url"
        --enumerate "$_enum_flags"
        "${api_flags[@]}"
        "${aggressive_scan_flags[@]}"
        --no-banner
        --random-user-agent
        --disable-tls-checks
        --no-update
        "${throttle_flags[@]}"
        "${thread_flags[@]}"
    )

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] timeout ${WPSCAN_TIMEOUT} ${full_cmd[*]} > ${full_out}"
    else
        {
            echo "# WPScan Full — ${url}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "# Tier:       ${TIER}"
            echo "# Enumerate:  ${WPSCAN_ENUMERATE}"
            echo "---"
            timeout "$WPSCAN_TIMEOUT" "${full_cmd[@]}" 2>&1 \
                || log_warn "  wpscan full timed out or errored for ${url}"
        } > "$full_out" || true

        # Extract interesting findings and display inline
        local vuln_count=0
        while IFS= read -r line; do
            if echo "$line" | grep -qE "^\[!\]"; then
                log_warn "  FINDING: ${line}"
                (( vuln_count++ )) || true
            elif echo "$line" | grep -qE "^\[\+\]"; then
                log_info "  FOUND: ${line}"
            fi
        done < "$full_out" || true

        WP_VULN_COUNT["$label"]="$vuln_count"

        # Parse plugins
        local plugins
        plugins=$(grep -oE "Plugin: [a-zA-Z0-9_-]+" "$full_out" \
                  | sed 's/Plugin: //' | sort -u | tr '\n' ',' | sed 's/,$//' || true)
        [[ -n "$plugins" ]] && WP_PLUGINS["$label"]="$plugins"

        # Parse themes
        local themes
        themes=$(grep -oE "Theme: [a-zA-Z0-9_-]+" "$full_out" \
                 | sed 's/Theme: //' | sort -u | tr '\n' ',' | sed 's/,$//' || true)
        [[ -n "$themes" ]] && WP_THEMES["$label"]="$themes"

        # Parse usernames
        local users
        users=$(grep -oE "Username: [a-zA-Z0-9._@-]+" "$full_out" \
                | sed 's/Username: //' | sort -u | tr '\n' ',' | sed 's/,$//' || true)
        [[ -n "$users" ]] && WP_USERS["$label"]="$users"

        log_ok "  Full scan saved: ${full_out}"
    fi

    # ── Step 3 — XML-RPC probe ────────────────────────────────────────────────
    log "  [${url}] Step 3: XML-RPC probe"
    local xmlrpc_out="${outdir}/xmlrpc_${ts}.txt"
    local xmlrpc_payload='<?xml version="1.0"?><methodCall><methodName>system.listMethods</methodName></methodCall>'

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] curl -sk --max-time 10 -d '<xmlrpc payload>' ${url}/xmlrpc.php > ${xmlrpc_out}"
    else
        local xmlrpc_resp
        xmlrpc_resp=$(curl -sk --max-time 10 \
                      -d "$xmlrpc_payload" \
                      "${url}/xmlrpc.php" 2>/dev/null || true)
        echo "$xmlrpc_resp" > "$xmlrpc_out" || true

        if echo "$xmlrpc_resp" | grep -q "<methodResponse>"; then
            WP_XMLRPC["$label"]="EXPOSED"
            log_warn "  xmlrpc.php is enabled — potential brute-force and amplification vector"

            # VAPT: multicall amplification check (CVE-like: XML-RPC system.multicall DDoS amplifier)
            local multicall_payload='<?xml version="1.0"?><methodCall><methodName>system.multicall</methodName><params><param><value><array><data><value><struct><member><name>methodName</name><value><string>wp.getUsers</string></value></member><member><name>params</name><value><array><data></data></array></value></member></struct></value></data></array></value></param></params></methodCall>'
            local multicall_resp
            multicall_resp=$(curl -sk --max-time 8 \
                -d "$multicall_payload" "${url}/xmlrpc.php" 2>/dev/null || true)
            if echo "$multicall_resp" | grep -qiE "<array>|<struct>|<methodResponse>"; then
                log_warn "  system.multicall enabled — brute-force amplification possible (100s of auth attempts per request)"
                WP_XMLRPC["$label"]="EXPOSED+MULTICALL"
            fi

            # Check if wp.getUsersBlogs is available (user enum via XML-RPC)
            local userblog_payload='<?xml version="1.0"?><methodCall><methodName>wp.getUsersBlogs</methodName><params><param><value><string>admin</string></value></param><param><value><string>admin</string></value></param></params></methodCall>'
            local userblog_resp
            userblog_resp=$(curl -sk --max-time 8 \
                -d "$userblog_payload" "${url}/xmlrpc.php" 2>/dev/null || true)
            if echo "$userblog_resp" | grep -qiE "Incorrect username|faultCode"; then
                log_info "  wp.getUsersBlogs: auth required (user enum still possible via error message comparison)"
            fi
        else
            WP_XMLRPC["$label"]="not exposed"
            log_info "  xmlrpc.php: not accessible or disabled"
        fi
        log_ok "  XML-RPC probe saved: ${xmlrpc_out}"
    fi

    # ── Step 4 — REST API user enumeration ────────────────────────────────────
    log "  [${url}] Step 4: WP REST API user enumeration"
    local wpjson_out="${outdir}/wpjson_users_${ts}.txt"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] curl -sk --max-time 10 ${url}/wp-json/wp/v2/users > ${wpjson_out}"
    else
        local wpjson_resp
        wpjson_resp=$(curl -sk --max-time 10 \
                      "${url}/wp-json/wp/v2/users" 2>/dev/null || true)
        echo "$wpjson_resp" > "$wpjson_out" || true

        # Valid JSON array with user entries: starts with [ and contains "slug" or "name"
        if echo "$wpjson_resp" | grep -qE '^\s*\[' && \
           echo "$wpjson_resp" | grep -qE '"(slug|name)"'; then
            WP_JSON_USERS["$label"]="EXPOSED"
            log_warn "  wp-json users endpoint exposed — usernames enumerable"
        else
            WP_JSON_USERS["$label"]="not exposed"
            log_info "  wp-json/wp/v2/users: not accessible or empty"
        fi

        # VAPT: ?author= enumeration (classic method, often not blocked)
        local author_found=()
        for uid in 1 2 3; do
            local author_resp; local author_code
            author_code=$(curl -sk --max-time 8 -o /dev/null -w "%{http_code}" \
                "${url}/?author=${uid}" 2>/dev/null || echo "000")
            if [[ "$author_code" == "301" || "$author_code" == "302" ]]; then
                local author_loc
                author_loc=$(curl -sk --max-time 8 -D - -o /dev/null \
                    "${url}/?author=${uid}" 2>/dev/null | grep -i "^location:" | \
                    sed 's/[Ll]ocation:[[:space:]]*//' | tr -d '\r' || true)
                if echo "$author_loc" | grep -qE "/author/[^/]+"; then
                    local uname; uname=$(echo "$author_loc" | grep -oE "/author/[^/]+" | sed 's|/author/||' || true)
                    [[ -n "$uname" ]] && { author_found+=("$uname"); log_warn "  ?author=${uid} reveals username: ${uname}"; }
                fi
            fi
        done
        [[ "${#author_found[@]}" -gt 0 ]] && WP_JSON_USERS["$label"]="EXPOSED (${WP_JSON_USERS[$label]}+author_enum:$(IFS=,; echo "${author_found[*]}"))"

        # VAPT: additional wp-json endpoint discovery
        local wpjson_extra_out="${outdir}/wpjson_discovery_${ts}.txt"
        {
            echo "# WP REST API Endpoint Discovery — ${url}"
            echo "---"
            for ep in \
                "/wp-json/" "/wp-json/wp/v2/posts" "/wp-json/wp/v2/pages" \
                "/wp-json/wp/v2/media" "/wp-json/wp/v2/categories" \
                "/wp-json/wp/v2/settings" "/wp-json/wp/v2/plugins" \
                "/?rest_route=/wp/v2/users" "/?rest_route=/wp/v2/settings"; do
                local ep_code
                ep_code=$(curl -sk --max-time 6 -o /dev/null -w "%{http_code}" \
                    "${url}${ep}" 2>/dev/null || echo "000")
                echo "  [${ep_code}] ${ep}"
                [[ "$ep_code" == "200" ]] && log_info "  wp-json ACCESSIBLE: ${ep}"
            done
        } | tee "$wpjson_extra_out" >/dev/null
        log_ok "  WP REST API probe saved: ${wpjson_out}"
    fi

    # ── Step 5 — Config/sensitive file exposure ───────────────────────────────
    log "  [${url}] Step 5: Config file exposure check"
    local exposed_files=()
    local config_paths=(
        # WordPress core sensitive files
        "/wp-config.php"
        "/wp-config.php.bak"
        "/wp-config.php.orig"
        "/wp-config.php~"
        "/wp-config-sample.php"
        "/wp-config.bak"
        "/wp-config.old"
        "/wp-config.txt"
        "/wp-config.zip"
        "/readme.html"
        "/license.txt"
        "/debug.log"
        "/.htaccess"
        "/wp-content/debug.log"
        "/wp-content/uploads/debug.log"
        # Timthumb (CVE-2011-4106 — still relevant on old installations)
        "/wp-content/themes/default/timthumb.php"
        "/wp-content/plugins/timthumb.php"
        "/timthumb.php"
        # Admin/install paths
        "/wp-admin/install.php"
        "/wp-admin/upgrade.php"
        "/wp-admin/setup-config.php"
        "/wp-cron.php"
        # Backup files often created by plugins or manual backup
        "/backup.sql"
        "/backup.zip"
        "/wp-content/backup-db/"
        "/wp-content/uploads/backups/"
        # Error logs
        "/error_log"
        "/php_errorlog"
        "/.git/HEAD"
        "/.env"
        # phpinfo exposure
        "/phpinfo.php"
        "/info.php"
    )

    for path in "${config_paths[@]}"; do
        if [[ "$DRY_RUN" -eq 1 ]]; then
            log_info "  [DRY-RUN] curl -sk -o /dev/null -w '%{http_code}' --max-time 8 ${url}${path}"
        else
            local code
            code=$(curl -sk -o /dev/null -w "%{http_code}" \
                   --max-time 8 \
                   "${url}${path}" 2>/dev/null || echo "000")

            if [[ "$code" == "200" ]]; then
                log_warn "  EXPOSED [200]: ${path}"
                exposed_files+=("$path")
            elif [[ "$code" == "301" || "$code" == "302" ]]; then
                log_info "  REDIRECT [${code}]: ${path}"
            fi
        fi
    done

    if [[ "${#exposed_files[@]}" -gt 0 ]]; then
        WP_EXPOSED_FILES["$label"]="$(printf '%s,' "${exposed_files[@]}" | sed 's/,$//')"
    fi

    # ── Step 6 — Login page exposure ─────────────────────────────────────────
    log "  [${url}] Step 6: Login page / wp-admin exposure"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] curl -sk -o /dev/null -w '%{http_code}' --max-time 10 ${url}/wp-admin/"
    else
        local admin_resp_headers
        admin_resp_headers=$(curl -sk -D - -o /dev/null \
                             --max-time 10 \
                             "${url}/wp-admin/" 2>/dev/null || true)

        local admin_code
        admin_code=$(echo "$admin_resp_headers" | grep -oE "^HTTP[^ ]+ [0-9]+" \
                     | head -1 | awk '{print $2}' || echo "000")

        local location
        location=$(echo "$admin_resp_headers" | grep -i "^location:" \
                   | head -1 | sed 's/[Ll]ocation:[[:space:]]*//' | tr -d '\r' || true)

        # Check for rate-limiting headers
        local rate_limit
        rate_limit=$(echo "$admin_resp_headers" | grep -i "^X-RateLimit" || true)

        if [[ "$admin_code" == "200" ]]; then
            log_warn "  wp-admin/ returns 200 — admin panel directly accessible (possible auth bypass)"
        elif [[ "$admin_code" =~ ^(301|302)$ ]]; then
            if echo "$location" | grep -qi "wp-login"; then
                log_info "  wp-admin/ redirects to login page [${admin_code}] — normal behaviour"
            else
                log_info "  wp-admin/ redirects [${admin_code}] to: ${location}"
            fi
        elif [[ "$admin_code" == "403" ]]; then
            log_info "  wp-admin/ returns 403 — access restricted"
        else
            log_info "  wp-admin/ returned HTTP ${admin_code}"
        fi

        [[ -n "$rate_limit" ]] && log_info "  Rate-limiting headers detected: ${rate_limit}"
    fi

    # ── Step 6b — Malicious / abandoned plugin check ─────────────────────────
    log "  [${url}] Step 6b: Malicious / abandoned plugin detection"
    local KNOWN_MALICIOUS_PLUGINS=(
        "easy-wp-smtp"        # CVE-2023-6553 — admin account takeover
        "woocommerce-payments" # CVE-2023-28121 — authentication bypass
        "wp-automatic"        # CVE-2024-27956 — SQL injection leading to RCE
        "essential-addons-for-elementor"  # CVE-2023-32243 — priv esc
        "layerslider"         # CVE-2024-2879 — SQL injection
        "email-subscribers"   # CVE-2023-5765 — SQL injection
        "backup-migration"    # CVE-2023-6553 — RCE
        "wp-file-manager"     # CVE-2020-25213 — unauthenticated RCE (widely exploited)
        "wp-super-cache"      # CVE-2021-24209 — stored XSS in cache
        "wp-statistics"       # CVE-2023-48778 — SQLi
        "login-with-ajax"     # abandoned — no patches since 2019
        "revslider"           # CVE-2014-9734 — local file inclusion (still found in the wild)
        "gravity-forms"       # CVE-2024-4625 — priv esc
        "contact-form-7"      # CVE-2020-35489 — unrestricted file upload
        "duplicator"          # CVE-2020-11738 — path traversal + info disclosure
    )
    if [[ "$DRY_RUN" -eq 0 ]]; then
        local mal_plugin_out="${outdir}/malicious_plugins_${ts}.txt"
        {
            echo "# Malicious/Abandoned Plugin Probe — ${url}"
            echo "# Date/Time: $(_now)"
            echo "---"
            for plugin in "${KNOWN_MALICIOUS_PLUGINS[@]}"; do
                local plugin_url="${url}/wp-content/plugins/${plugin}/"
                local plugin_code
                plugin_code=$(curl -sk --max-time 6 -o /dev/null -w "%{http_code}" \
                    "$plugin_url" 2>/dev/null || echo "000")
                if [[ "$plugin_code" == "200" || "$plugin_code" == "403" ]]; then
                    log_warn "  PLUGIN DETECTED [${plugin_code}]: ${plugin} — CHECK FOR CVEs"
                    echo "  [${plugin_code}] ${plugin}"
                fi
            done
        } | tee "$mal_plugin_out" >/dev/null
        local mal_count; mal_count=$(grep -c "^\s*\[20" "$mal_plugin_out" 2>/dev/null || echo 0)
        [[ "$mal_count" -gt 0 ]] && log_warn "  ${mal_count} potentially vulnerable plugin(s) detected — review ${mal_plugin_out}" \
                                   || log_info "  No known-malicious plugins detected at common paths"
    fi

    # ── Step 7 — Security headers ─────────────────────────────────────────────
    log "  [${url}] Step 7: Security headers"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] curl -skI --max-time 10 ${url}"
    else
        local headers_resp
        headers_resp=$(curl -skI --max-time 10 "$url" 2>/dev/null || true)

        local missing_headers=()
        local present_headers=()

        for hdr in \
            "Content-Security-Policy" \
            "Strict-Transport-Security" \
            "X-Frame-Options" \
            "X-Content-Type-Options" \
            "Referrer-Policy"; do
            if echo "$headers_resp" | grep -qi "^${hdr}:"; then
                present_headers+=("$hdr")
                log_info "  HEADER OK:      ${hdr}"
            else
                missing_headers+=("$hdr")
                log_warn "  HEADER MISSING: ${hdr}"
            fi
        done

        if [[ "${#missing_headers[@]}" -gt 0 ]]; then
            WP_SEC_HEADERS["$label"]="missing: $(printf '%s,' "${missing_headers[@]}" | sed 's/,$//')"
        else
            WP_SEC_HEADERS["$label"]="all present"
        fi
    fi

    # ── Per-target summary markdown ───────────────────────────────────────────
    local summary_file="${outdir}/summary_${ts}.md"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] write ${summary_file}"
    else
        {
            cat <<EOF
# WPScan Assessment Summary — ${url}
*Engagement: ${PROJECT_NAME} | Date: $(_now) | Mode: ${MODE} | Tier: ${TIER}*

## Target
| Field              | Value |
|--------------------|-------|
| URL                | ${url} |
| WordPress Version  | ${WP_VERSION[$label]:-[unknown]} |
| Plugins Found      | ${WP_PLUGINS[$label]:-none detected} |
| Themes Found       | ${WP_THEMES[$label]:-none detected} |
| Users Found        | ${WP_USERS[$label]:-none detected} |
| Vulnerabilities    | ${WP_VULN_COUNT[$label]:-0} |

## Key Findings
| Check               | Result |
|---------------------|--------|
| XML-RPC             | ${WP_XMLRPC[$label]:-not checked} |
| WP-JSON Users       | ${WP_JSON_USERS[$label]:-not checked} |
| Exposed Files       | ${WP_EXPOSED_FILES[$label]:-none} |
| Security Headers    | ${WP_SEC_HEADERS[$label]:-not checked} |
| API Token Used      | ${WP_API_USED[$label]:-no} |

## Evidence Files
$(ls -1 "${outdir}/" 2>/dev/null | sed "s|^|  - evidence/_wpscan/${label}/|" || true)

---
*06_wpscan.sh | TechGuard | ${PROJECT_NAME}*
EOF
        } > "$summary_file" || true
        log_ok "  Per-target summary: ${summary_file}"
    fi

    log_ok "Assessment complete: ${url}"
    echo ""
}

# =============================================================================
# MRK:06_REPORT — CONSOLIDATED REPORT | report,consolidated,working,wpscan,ts | L756-923
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

write_report() {
    local report_file="working/wpscan_report_${SESSION_TS}.md"

    log "Writing consolidated report: ${report_file}"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] write ${report_file}"
        return 0
    fi

    local api_used_count=0
    for url in "${WP_TARGETS[@]}"; do
        local lbl
        lbl="$(sanitize_label "$url")"
        [[ "${WP_API_USED[$lbl]:-no}" == "yes" ]] && (( api_used_count++ )) || true
    done
    local api_remaining="$WPSCAN_API_BUDGET"

    {
        cat <<EOF
# WPScan Report — ${PROJECT_NAME}
*Generated: $(_now) | Session: ${SESSION_TS}*

---

## Engagement Information
| Field        | Value |
|--------------|-------|
| Project      | ${PROJECT_NAME} |
| Date         | $(_now) |
| Mode         | ${MODE} |
| Tier         | ${TIER} |
| Script       | 06_wpscan.sh |
| Targets      | ${#WP_TARGETS[@]} |
| API Token    | $([ -n "$WPSCAN_API_TOKEN" ] && echo "configured" || echo "not set") |

---

## WordPress Targets Assessed
| URL | WP Version | Plugins | Users Exposed | Vulns | Key Flags |
|-----|-----------|---------|---------------|-------|-----------|
EOF

        for url in "${WP_TARGETS[@]}"; do
            local lbl
            lbl="$(sanitize_label "$url")"
            local flags=""
            [[ "${WP_XMLRPC[$lbl]:-}" == "EXPOSED" ]]      && flags="${flags}xmlrpc-exposed "
            [[ "${WP_JSON_USERS[$lbl]:-}" == "EXPOSED" ]]  && flags="${flags}users-via-json "
            [[ -n "${WP_EXPOSED_FILES[$lbl]:-}" ]]          && flags="${flags}config-exposure "
            [[ "${WP_SEC_HEADERS[$lbl]:-}" != "all present" && -n "${WP_SEC_HEADERS[$lbl]:-}" ]] \
                && flags="${flags}missing-headers"
            [[ -z "$flags" ]] && flags="—"

            printf "| %s | %s | %s | %s | %s | %s |\n" \
                "$url" \
                "${WP_VERSION[$lbl]:-[unknown]}" \
                "${WP_PLUGINS[$lbl]:-—}" \
                "${WP_JSON_USERS[$lbl]:-—}" \
                "${WP_VULN_COUNT[$lbl]:-0}" \
                "$flags"
        done

        echo ""
        echo "---"
        echo ""
        echo "## Critical Findings"
        echo ""

        local crit_count=0
        for url in "${WP_TARGETS[@]}"; do
            local lbl
            lbl="$(sanitize_label "$url")"

            if [[ "${WP_XMLRPC[$lbl]:-}" == "EXPOSED" ]]; then
                echo "### XML-RPC Exposed — ${url}"
                echo "- **Risk:** Brute-force amplification via system.multicall; auth bypass vector."
                echo "- **Evidence:** \`evidence/_wpscan/${lbl}/xmlrpc_*.txt\`"
                echo "- **Remediation:** Disable XML-RPC via plugin or \`functions.php\` filter unless required."
                echo ""
                (( crit_count++ )) || true
            fi

            if [[ "${WP_JSON_USERS[$lbl]:-}" == "EXPOSED" ]]; then
                echo "### WP-JSON Users Endpoint Exposed — ${url}"
                echo "- **Risk:** Username enumeration via \`/wp-json/wp/v2/users\` facilitates credential attacks."
                echo "- **Evidence:** \`evidence/_wpscan/${lbl}/wpjson_users_*.txt\`"
                echo "- **Remediation:** Restrict REST API user endpoint; remove author archive if not needed."
                echo ""
                (( crit_count++ )) || true
            fi

            if [[ -n "${WP_EXPOSED_FILES[$lbl]:-}" ]]; then
                echo "### Sensitive File Exposure — ${url}"
                echo "- **Files:** \`${WP_EXPOSED_FILES[$lbl]}\`"
                echo "- **Risk:** wp-config.php exposure leaks DB credentials; debug.log may expose stack traces."
                echo "- **Remediation:** Block direct access to these files in \`.htaccess\` / nginx config."
                echo ""
                (( crit_count++ )) || true
            fi

            if [[ "${WP_SEC_HEADERS[$lbl]:-}" != "all present" && \
                  -n "${WP_SEC_HEADERS[$lbl]:-}" ]]; then
                echo "### Missing Security Headers — ${url}"
                echo "- **Missing:** ${WP_SEC_HEADERS[$lbl]}"
                echo "- **Risk:** Missing CSP/HSTS/X-Frame-Options increases XSS, clickjacking, and MITM exposure."
                echo "- **Remediation:** Add missing headers via server config or security plugin."
                echo ""
                (( crit_count++ )) || true
            fi
        done

        [[ "$crit_count" -eq 0 ]] && echo "No critical findings identified. Review per-target summaries for detail."

        echo ""
        echo "---"
        echo ""
        echo "## API Budget Usage"
        echo ""
        echo "| Metric | Value |"
        echo "|--------|-------|"
        printf "| Targets that consumed an API call | %s |\n" "$api_used_count"
        printf "| Budget remaining                  | %s |\n" "$api_remaining"
        printf "| API token status                  | %s |\n" \
            "$([ -n "$WPSCAN_API_TOKEN" ] && echo "configured" || echo "not set — no CVE data collected")"

        echo ""
        echo "---"
        echo ""
        echo "## Recommended Next Steps"
        echo ""
        cat <<'RECS'
- **Manual authentication testing:** Attempt login to /wp-admin/ with discovered usernames and
  common / leaked passwords if authorised; test lockout / rate-limiting behaviour.

- **Brute force (if in scope):** Use wpscan --passwords with a targeted wordlist against
  discovered usernames. Only with explicit written authorisation.

- **Plugin/theme CVE follow-up:** Cross-reference detected plugin versions against NVD / WPScan
  DB for unpatched CVEs; request PoC testing authorisation where applicable.

- **XML-RPC multicall abuse:** If xmlrpc.php is exposed and brute force is in scope, use
  system.multicall to amplify password guessing attempts.

- **REST API enumeration:** Explore additional /wp-json/wp/v2/ endpoints for further info
  disclosure (posts, categories, media filenames that leak internal structure).

- **Theme/plugin file inclusion:** For any detected vulnerable plugins, assess path traversal,
  arbitrary file read, or RCE vectors in controlled conditions.

- **wp-config.php backup files:** If any backup/~ files were accessible, retrieve and review
  for credentials, debug settings, and secret keys.
RECS

        echo ""
        echo "---"
        echo "*06_wpscan.sh | TechGuard | ${PROJECT_NAME}*"

    } > "$report_file" || true

    log_ok "Report written: ${report_file}"
}

# =============================================================================
# MRK:06_MAIN — MAIN entry point | main,entry,point | L924-1003
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    parse_args "$@"

    # DB connect (via orc-common-lib.sh; safe no-op if lib not sourced)
    declare -F parse_db_conf >/dev/null 2>&1 && parse_db_conf

    # Trail: phase start
    local _06_t_start; _06_t_start=$(date +%s)
    trail_phase_start phase "wpscan" project "${PROJECT_NAME:-}" mode "${MODE:-}" session "${SESSION_TS:-$(date +%Y%m%d_%H%M%S)}" tier "${TIER:-}" ts "$(date -u +%FT%TZ)" 2>/dev/null || true

    echo -e "${GREEN}"
    echo "════════════════════════════════════════════════"
    echo "  06_wpscan.sh"
    echo "  TechGuard."
    echo "  Project: ${PROJECT_NAME}"
    echo "  Mode:    ${MODE} | Tier: ${TIER}"
    echo "════════════════════════════════════════════════"
    echo -e "${NC}"

    check_deps

    # Phase 1 — detection sweep (--detect or --detect-only)
    if [[ "$DO_DETECT" -eq 1 ]]; then
        detect_wordpress || log_warn "Detection sweep encountered errors — continuing"
    fi

    # Phase 2 — WPScan assessment
    if [[ "$DETECT_ONLY" -eq 0 ]]; then
        load_wp_targets

        if [[ "${#WP_TARGETS[@]}" -eq 0 ]]; then
            log "No WordPress targets found."
            log "Run with --detect first, or populate ${WP_TARGETS_FILE} manually."
            exit 0
        fi

        scope_confirm "${#WP_TARGETS[@]}"

        mkdir -p "${EVIDENCE_BASE}/_wpscan"
        mkdir -p "working"

        local total="${#WP_TARGETS[@]}"
        local i=0

        for url in "${WP_TARGETS[@]}"; do
            (( i++ )) || true
            log "Assessing ${url} (${i}/${total})..."
            (
                set +e
                assess_wordpress "$url"
            ) || log_warn "Assessment failed for ${url} — continuing with remaining targets"
        done

        write_report

        echo ""
        echo -e "${GREEN}════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}  WPScan Assessment Complete — ${PROJECT_NAME}${NC}"
        echo -e "${GREEN}  Targets assessed: ${total}${NC}"
        echo -e "${GREEN}  Evidence base:    ${EVIDENCE_BASE}/_wpscan/${NC}"
        echo -e "${GREEN}  API budget left:  ${WPSCAN_API_BUDGET}${NC}"
        echo -e "${GREEN}════════════════════════════════════════════════${NC}"
        echo ""
        echo "Review: working/wpscan_report_${SESSION_TS}.md"
        echo ""
    fi

    # Trail: phase end (always emitted, even if no targets)
    local _06_t_end; _06_t_end=$(date +%s)
    trail_phase_end phase "wpscan" project "${PROJECT_NAME:-}" session "${SESSION_TS:-}" duration_sec "$((_06_t_end - _06_t_start))" ts "$(date -u +%FT%TZ)" 2>/dev/null || true
}

main "$@"

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
