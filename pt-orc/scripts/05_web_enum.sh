#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:05_NAV_TOC — Section index | nav,toc,index | L5-51
# - MRK:05_ROOT — ROOT CHECK | root,check,db,nmap,requires | L52-61 | ⚠ no-insert-before
# - MRK:05_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L62-106 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:05_LOG — COLOURS AND LOGGING | log,colours,logging | L107-131 | ⚠ no-insert-before
# - MRK:05_ARGS — ARGUMENT PARSING | args,argument,parsing | L132-153 | ⚠ no-insert-before
# - MRK:05_DB — MSF DB HELPERS | db,msf,helpers,tcp,host | L154-223 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:05_SCAN — SCAN EXECUTION MODEL | scan,execution,model,rc,spool | L224-293 | ⚠ no-insert-before; read-toc-first
# - MRK:05_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L294-320 | ⚠ no-insert-before; propose-before-edit
# - MRK:05_TARGETS — TARGET ASSEMBLY | targets,target,assembly,db,host | L321-360 | ⚠ no-insert-before; read-toc-first
# - MRK:05_TLS — TLS DETECTION | tls,detection,fast,path,port | L361-378 | ⚠ no-insert-before
# - MRK:05_ENUM — PER-HOST WEB ENUMERATION | enum,host,web,enumeration,headers | L379-668 | ⚠ no-insert-before; read-toc-first
# - MRK:05_MAIN — MAIN entry point | main,entry,point | L669-750 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 11 entries | Integrity-hash: c739ef8caa977642 | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# 05_web_enum.sh — TechGuard. [VAPT-Enhanced v1.0 — 2026-06-05]
# Web service enumeration — DB-driven, per-host output, stealth-aware
# VAPT Enhancements: expanded API endpoints, GraphQL introspection, sensitive
# file exposure (CWE-538), Spring Boot Actuator, admin panel detection,
# OAuth2/OIDC discovery, backup file discovery.
# Consumes: MSF DB (web hosts from 03_comp_scan.sh)
# Or:       --targets <file>  or  --host <IP:PORT>
# =============================================================================
# USAGE:
#   ./05_web_enum.sh [OPTIONS]
#
# OPTIONS:
#   --targets <file>    File with host:port entries (one per line)
#   --host <IP:PORT>    Single target (can repeat)
#   --from-db           Pull web hosts from MSF DB (default if no targets given)
#   --tier <n>          ghost|normal|loud — controls gobuster threads and nikto aggressiveness
#   --skip-gobuster     Skip directory brute force
#   --skip-nikto        Skip Nikto scan
#   --skip-api          Skip API endpoint probing
#   --fast              Skip gobuster + nikto; headers + tech detection only
#   --wordlist <path>   Gobuster wordlist (default: /usr/share/wordlists/dirb/common.txt)
#   --dry-run           Print what would run without executing db_nmap
#
# ENVIRONMENT VARS:
#   PROJECT_NAME        MSF workspace name
#   EVIDENCE_BASE       Base evidence directory (default: evidence)
#   GOBUSTER_TIMEOUT    Seconds per host (default: 180)
#   NIKTO_TIMEOUT       Seconds per host (default: 180)
#   WHATWEB_TIMEOUT     Seconds per host (default: 30)
set -uo pipefail

# Location of this script — keep evidence inside this PT-Orc directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:05_ROOT — ROOT CHECK | root,check,db,nmap,requires | L52-61
# NAV-RULE: no-insert-before
# =============================================================================
if [[ "$EUID" -ne 0 ]] && [[ "${PTORC_ALLOW_NON_ROOT:-0}" != "1" ]]; then
    echo "[ERROR] This script must be run as root (required for db_nmap)."
    echo "        Run: sudo $0 $*"
    exit 1
fi

# =============================================================================
# MRK:05_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L62-106
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

# Load shared engagement config (PROJECT_NAME, MODE, …)
# shellcheck source=pt-orc.conf
[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found in ${SCRIPT_DIR} — set variables in pt-orc.conf"

# Shared helpers (logging, DB access, trail/notes writer)
# shellcheck source=orc-common-lib.sh
[[ -f "${SCRIPT_DIR}/orc-common-lib.sh" ]] && source "${SCRIPT_DIR}/orc-common-lib.sh" \
    || echo "[WARN] orc-common-lib.sh not found — trail/notes writes will be disabled"

EVIDENCE_BASE="${EVIDENCE_BASE:-${SCRIPT_DIR}/evidence}"

GOBUSTER_TIMEOUT="${GOBUSTER_TIMEOUT:-180}"
NIKTO_TIMEOUT="${NIKTO_TIMEOUT:-180}"
WHATWEB_TIMEOUT="${WHATWEB_TIMEOUT:-30}"
CURL_TIMEOUT=10
CURL_CONNECT=5

WORDLIST="${WORDLIST:-/usr/share/wordlists/dirb/common.txt}"

TIER="normal"
FROM_DB=1
SKIP_GOBUSTER=0
SKIP_NIKTO=0
SKIP_API=0
FAST_MODE=0
AUTO_YES=0
DRY_RUN=0

EXTRA_HOSTS=()
TARGETS_FILE=""

# Tier → gobuster threads
gobuster_threads() { case "$1" in ghost) echo 5;; normal) echo 20;; loud) echo 50;; evasion) echo 1;; esac; }
# Tier → whatweb aggressiveness (1-4)
whatweb_aggression() { case "$1" in ghost) echo 1;; normal) echo 3;; loud) echo 4;; evasion) echo 1;; esac; }

# Known TLS ports (auto-detected anyway, but fast-path)
TLS_PORTS="443 8443 4443 9443 10443"

# =============================================================================
# MRK:05_LOG — COLOURS AND LOGGING | log,colours,logging | L107-131
# NAV-RULE: no-insert-before
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

_ts()  { date +'%Y%m%d_%H%M%S'; }
_now() { date +'%Y-%m-%d %H:%M:%S'; }

SESSION_TS="$(_ts)"
[[ "$EVIDENCE_BASE" != /* ]] && EVIDENCE_BASE="$(pwd)/${EVIDENCE_BASE}"
mkdir -p "${EVIDENCE_BASE}/_sweep" working
LOG_FILE="${EVIDENCE_BASE}/_sweep/web_enum_${SESSION_TS}.log"

# Colored to stderr, plain to logfile
log()     { local m="[$(_now)] $1"; echo -e "${BLUE}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_ok()  { local m="[$(_now)] ✓ $1"; echo -e "${GREEN}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_warn(){ local m="[$(_now)] ⚠ $1"; echo -e "${YELLOW}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_err() { local m="[$(_now)] ✗ $1"; echo -e "${RED}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_info(){ local m="[$(_now)]   $1"; echo -e "${CYAN}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }

# Ownership helper removed per operator preference; leave ownership as-is

# =============================================================================
# MRK:05_ARGS — ARGUMENT PARSING | args,argument,parsing | L132-153
# NAV-RULE: no-insert-before
# =============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --targets)       TARGETS_FILE="$2"; FROM_DB=0; shift 2 ;;
        --host)          EXTRA_HOSTS+=("$2"); FROM_DB=0; shift 2 ;;
        --from-db)       FROM_DB=1; shift ;;
        --tier)          TIER="$2"; shift 2 ;;
        --skip-gobuster) SKIP_GOBUSTER=1; shift ;;
        --skip-nikto)    SKIP_NIKTO=1; shift ;;
        --skip-api)      SKIP_API=1; shift ;;
        --fast)          FAST_MODE=1; SKIP_GOBUSTER=1; SKIP_NIKTO=1; shift ;;
        --wordlist)      WORDLIST="$2"; shift 2 ;;
        --yes)           AUTO_YES=1; shift ;;
        --dry-run)       DRY_RUN=1; shift ;;
        *) log_err "Unknown argument: $1"; exit 1 ;;
    esac
done

# =============================================================================
# MRK:05_DB — MSF DB HELPERS | db,msf,helpers,tcp,host | L154-223
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

MSF_DB_CONF="/usr/share/metasploit-framework/config/database.yml"
# Always 127.0.0.1 — Unix socket requires peer auth (fails as root). TCP uses password auth.
MSF_DB_USER="msf"; MSF_DB_NAME="msf"; MSF_DB_HOST="127.0.0.1"; MSF_DB_PORT="5432"
MSF_DB_PASS="${MSF_DB_PASS:-}"

parse_db_conf() {
    [[ -f "$MSF_DB_CONF" ]] || return
    MSF_DB_USER=$(grep -m1 'username:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "msf")
    MSF_DB_NAME=$(grep -m1 'database:'  "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "msf")
    MSF_DB_PORT=$(grep -m1 'port:'      "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "5432")
    MSF_DB_HOST="127.0.0.1"   # intentionally ignore yaml 'host:' — always TCP
    if [[ -z "${MSF_DB_PASS}" ]]; then
        MSF_DB_PASS=$(grep -m1 'password:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" 2>/dev/null || true)
    fi
    export MSF_DB_PASS
}

db_query() {
    PGPASSWORD="${MSF_DB_PASS:-}" psql -h "$MSF_DB_HOST" -p "$MSF_DB_PORT" \
        -U "$MSF_DB_USER" -d "$MSF_DB_NAME" -t -A -c "$1" 2>/dev/null || true
}

get_web_hosts_from_db() {
    local wid; wid=$(db_query \
        "SELECT id FROM workspaces WHERE name='${PROJECT_NAME}' LIMIT 1;")
    if [[ -z "$wid" ]]; then
        log_warn "get_web_hosts_from_db: workspace '${PROJECT_NAME}' not found — trying CSV fallback"
        _get_web_hosts_csv
        return
    fi

    # Pull all open services on known web ports.
    # host(h.address) extracts IP string from inet column — split_part does not work on inet.
    local web_ports="80,443,8080,8443,4443,8888,9443,9200,10443,8006"
    local result
    result=$(db_query "SELECT host(h.address) || ':' || s.port \
              FROM services s JOIN hosts h ON s.host_id = h.id \
              WHERE h.workspace_id=${wid} \
              AND s.proto='tcp' AND s.state='open' \
              AND s.port IN (${web_ports}) \
              ORDER BY host(h.address), s.port;")
    if [[ -n "$result" ]]; then
        echo "$result"
    else
        log_warn "get_web_hosts_from_db: workspace empty or no web ports in DB — trying CSV fallback"
        _get_web_hosts_csv
    fi
}

# Extract web IP:port pairs from the most recent services TCP CSV export.
_get_web_hosts_csv() {
    local csv
    csv=$(find "${EVIDENCE_BASE}/_exports" -name 'services_tcp_*.csv' 2>/dev/null | sort | tail -1)
    [[ -z "$csv" ]] && return
    # CSV columns: host,port,proto,name,state,info — all double-quoted
    # Web ports: 80,443,8080,8443,4443,8888,9443,9200,10443,8006
    awk -F',' 'NR>1 {
        gsub(/"/, "", $1); gsub(/"/, "", $2); gsub(/"/, "", $3); gsub(/"/, "", $5)
        if ($3=="tcp" && $5=="open" && \
            ($2=="80"||$2=="443"||$2=="8080"||$2=="8443"||$2=="4443"|| \
             $2=="8888"||$2=="9443"||$2=="9200"||$2=="10443"||$2=="8006"))
            print $1":"$2
    }' "$csv" 2>/dev/null | sort -u
}

# =============================================================================
# MRK:05_SCAN — SCAN EXECUTION MODEL | scan,execution,model,rc,spool | L224-293
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

RC_DIR="${EVIDENCE_BASE}/_msf"

# Run db_nmap via msfconsole resource script. Spool captures full session.
# NSE output → notes table. rc file kept as evidence.
# Usage: run_rc_scan <label> <nmap_args...>
run_rc_scan() {
    local label="${1//\//_}"; shift   # sanitize: slashes in IPs must not become path separators
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        log "  [DRY RUN] would run: db_nmap $*"
        return 0
    fi
    local ts; ts="$(_ts)"
    local rc_file="${RC_DIR}/${label}_${ts}.rc"
    local spool_file="${RC_DIR}/${label}_${ts}.log"

    mkdir -p "$RC_DIR"

    {
        printf 'spool %s\n'        "$spool_file"
        printf 'workspace -a %s\n'  "$PROJECT_NAME"
        printf 'db_nmap %s\n'      "$*"
        printf 'spool off\n'
        printf 'exit\n'
    } > "$rc_file"

    log "  rc_scan [${label}] → ${rc_file}"
    log "  spool  [${label}] → ${spool_file}  (tail -f to follow)"

    PGPASSWORD="${MSF_DB_PASS:-}" msfconsole -q -r "$rc_file" </dev/null
    local rc=$?
    [[ $rc -ne 0 ]] \
        && log_warn "  msfconsole rc=${rc} [${label}] — check: ${spool_file}" \
        || log_ok   "  rc_scan done [${label}]"
    return $rc
}

# Export MSF DB via rc file. Uses `workspace -a` for idempotent create+switch
# (matches 03/04 pattern; v0.75 fix).
# Usage: export_db <phase_label>
export_db() {
    local phase="${1:-web}"
    local ts; ts="$(_ts)"
    local label="${phase}_${ts}"
    local rc_file="${RC_DIR}/export_${label}.rc"
    local spool_file="${RC_DIR}/export_${label}.log"

    mkdir -p "$RC_DIR" "${EVIDENCE_BASE}/_exports"

    {
        printf 'spool %s\n'     "$spool_file"
        printf 'workspace -a %s\n' "$PROJECT_NAME"
        printf 'hosts    -o %s/_exports/hosts_%s.csv\n'    "$EVIDENCE_BASE" "$label"
        printf 'services -o %s/_exports/services_%s.csv\n' "$EVIDENCE_BASE" "$label"
        printf 'notes    -o %s/_exports/notes_%s.csv\n'    "$EVIDENCE_BASE" "$label"
        printf 'spool off\n'
        printf 'exit\n'
    } > "$rc_file"

    log "Exporting MSF DB (${phase})..."
    PGPASSWORD="${MSF_DB_PASS:-}" msfconsole -q -r "$rc_file" </dev/null >/dev/null 2>&1 \
        && log_ok "Exported: hosts_${label}.csv | services_${label}.csv | notes_${label}.csv" \
        || log_warn "MSF export may have partial results (${phase}) — check ${spool_file}"
}


# =============================================================================
# MRK:05_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L294-320
# NAV-RULE: no-insert-before; propose-before-edit
# =============================================================================
scope_confirm() {
    local target_count="${1:-0}"
    [[ "${AUTO_YES:-0}" -eq 1 ]] && return 0
    echo ""
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    echo -e "\033[1m  SCOPE CONFIRMATION — 05_web_enum.sh\033[0m"
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    printf "  %-22s %s\n" "Project:"     "${PROJECT_NAME}"
    printf "  %-22s %s\n" "Tier:"        "${TIER}"
    printf "  %-22s %s\n" "Targets:"     "${target_count}"
    printf "  %-22s %s\n" "Gobuster:"    "$([ "$SKIP_GOBUSTER" -eq 1 ] && echo "skip" || echo "enabled")"
    printf "  %-22s %s\n" "Nikto:"       "$([ "$TIER" == "evasion" ] || [ "$SKIP_NIKTO" -eq 1 ] && echo "skip" || echo "enabled")"
    printf "  %-22s %s\n" "API probe:"   "$([ "$SKIP_API" -eq 1 ] && echo "skip" || echo "enabled")"
    printf "  %-22s %s\n" "Dry run:"     "$([ "${DRY_RUN:-0}" -eq 1 ] && echo "YES" || echo "no")"
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    echo ""
    echo -e "\033[1mConfirm authorisation is in place and scope is correct.\033[0m"
    echo -n "  Type YES to continue: "
    read -r answer
    [[ "$answer" != "YES" ]] && { echo "Aborted."; exit 0; }
    echo ""
}

# =============================================================================
# MRK:05_TARGETS — TARGET ASSEMBLY | targets,target,assembly,db,host | L321-360
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

assemble_targets() {
    local targets=()

    if [[ "$FROM_DB" -eq 1 ]]; then
        local db_hosts; db_hosts="$(get_web_hosts_from_db 2>/dev/null || true)"
        if [[ -n "$db_hosts" ]]; then
            while IFS= read -r h; do
                [[ -n "$h" ]] && targets+=("$h")
            done <<< "$db_hosts"
            log_ok "Pulled ${#targets[@]} web targets from MSF DB"
        else
            log_warn "No web targets in DB — check workspace or use --targets"
        fi
    fi

    if [[ -n "$TARGETS_FILE" && -f "$TARGETS_FILE" ]]; then
        while IFS= read -r line; do
            [[ -z "$line" || "$line" == \#* ]] && continue
            targets+=("$line")
        done < "$TARGETS_FILE"
    fi

    set +u
    for h in "${EXTRA_HOSTS[@]}"; do
        targets+=("$h")
    done
    set -u

    set +u
    if [[ ${#targets[@]} -gt 0 ]]; then
        printf '%s\n' "${targets[@]}" | sort -u
    fi
    set -u
}

# =============================================================================
# MRK:05_TLS — TLS DETECTION | tls,detection,fast,path,port | L361-378
# NAV-RULE: no-insert-before
# =============================================================================

detect_tls() {
    local ip="$1" port="$2"
    # Fast-path: known TLS ports
    for p in $TLS_PORTS; do
        [[ "$port" == "$p" ]] && return 0
    done
    # Active probe
    timeout 6 bash -c \
        "echo | openssl s_client -connect '${ip}:${port}' \
         -servername '${ip}' 2>/dev/null | grep -q 'SSL-Session'" \
        >/dev/null 2>&1
}

# =============================================================================
# MRK:05_ENUM — PER-HOST WEB ENUMERATION | enum,host,web,enumeration,headers | L379-668
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

enumerate_host() {
    local target="$1"
    local ip="${target%%:*}"
    ip="${ip%%/*}"            # strip CIDR suffix if present (e.g. 10.0.0.1/32 → 10.0.0.1)
    local port="${target##*:}"
    local dir="${EVIDENCE_BASE}/${ip}"
    local ts; ts="$(_ts)"

    mkdir -p "$dir"

    # Determine protocol
    local proto="http"
    detect_tls "$ip" "$port" && proto="https"
    local url="${proto}://${ip}:${port}"

    log "Web enum: ${url} [${TIER}]"

    # ── 1. HTTP Headers (always) ────────────────────────────────────────────
    local headers_out="${dir}/headers_${port}_${ts}.txt"
    {
        echo "# HTTP Headers — ${url}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        curl --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT" \
             -sk -I "${url}" 2>/dev/null || \
            echo "[WARN] curl -I failed"
    } | tee "$headers_out"

    # ── 2. Security Headers Analysis (always) — 10 headers, matches 04 ─────
    local sec_out="${dir}/sec_headers_${port}_${ts}.txt"
    {
        echo "# Security Headers Analysis — ${url}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local raw; raw=$(cat "$headers_out")
        local missing=()
        local present=()
        for h in \
            "Strict-Transport-Security" \
            "Content-Security-Policy" \
            "X-Frame-Options" \
            "X-Content-Type-Options" \
            "X-XSS-Protection" \
            "Referrer-Policy" \
            "Permissions-Policy" \
            "Cross-Origin-Opener-Policy" \
            "Cross-Origin-Resource-Policy" \
            "Cross-Origin-Embedder-Policy"; do
            local val; val=$(echo "$raw" | grep -i "^${h}:" | head -1 || true)
            if [[ -n "$val" ]]; then
                present+=("$h")
                echo "  PRESENT: ${val}"
            else
                missing+=("$h")
                echo "  MISSING: ${h}"
            fi
        done
        echo ""
        set +u
        echo "Present: ${#present[@]} / Missing: ${#missing[@]}"
        echo "Missing headers: ${missing[*]:-none}"
        set -u
    } | tee "$sec_out"
    log_ok "  Security headers: ${sec_out}"

    # ── 2b. CORS Misconfiguration Check ────────────────────────────────────
    # Sends Origin: headers with attacker-controlled domains and null.
    # Flags: reflected origin (ACAO = Origin), ACAO=* with credentials, ACAO=null.
    # These are common high-severity PTE findings — fast curl-only, no extra deps.
    local cors_out="${dir}/cors_${port}_${ts}.txt"
    {
        echo "# CORS Misconfiguration Check — ${url}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local test_origins=(
            "https://evil.com"
            "null"
            "https://${ip}.evil.com"
        )
        local cors_finding=0
        for origin in "${test_origins[@]}"; do
            local cors_resp
            cors_resp=$(curl --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT" \
                 -sk -I -H "Origin: ${origin}" "${url}" 2>/dev/null || true)
            local acao; acao=$(echo "$cors_resp" | grep -i "^access-control-allow-origin:" | head -1 | tr -d '\r' || true)
            local acac; acac=$(echo "$cors_resp" | grep -i "^access-control-allow-credentials:" | head -1 | tr -d '\r' || true)
            if [[ -n "$acao" ]]; then
                echo "  Origin tested:          ${origin}"
                echo "  ACAO response:          ${acao}"
                [[ -n "$acac" ]] && echo "  ACAC:                   ${acac}"
                # Flag reflected origin or wildcard with credentials
                if echo "$acao" | grep -qiE "evil\.com|null"; then
                    echo "  *** POTENTIAL CORS MISCONFIGURATION — attacker origin reflected ***"
                    log_warn "  CORS: attacker origin reflected on ${url} with Origin: ${origin}"
                    cors_finding=1
                elif echo "$acao" | grep -q '\*' && echo "$acac" | grep -qi "true"; then
                    echo "  *** CORS MISCONFIGURATION — wildcard ACAO with credentials allowed ***"
                    log_warn "  CORS: wildcard + credentials=true on ${url}"
                    cors_finding=1
                else
                    echo "  (ACAO present but not misconfigured for this origin)"
                fi
                echo ""
            fi
        done
        [[ "$cors_finding" -eq 0 ]] && echo "No CORS misconfiguration detected for tested origins."
    } | tee "$cors_out"
    log_ok "  CORS check: ${cors_out}"

    # ── 3. Technology Detection (WhatWeb) ───────────────────────────────────
    local tech_out="${dir}/whatweb_${port}_${ts}.txt"
    {
        echo "# Technology Detection — ${url}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        if command -v whatweb &>/dev/null; then
            timeout "$WHATWEB_TIMEOUT" whatweb \
                --color=never \
                -a "$(whatweb_aggression "$TIER")" \
                "${url}" 2>&1 || echo "[WARN] whatweb timed out or errored"
        else
            echo "[WARN] whatweb not found"
            # Fallback: curl for Server and X-Powered-By headers
            curl --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT" \
                 -sk -I "${url}" 2>/dev/null | grep -iE "server:|x-powered-by:|via:" || true
        fi
    } | tee "$tech_out"
    log_ok "  Tech detection: ${tech_out}"

    # ── 4. Directory Brute Force (Gobuster) ─────────────────────────────────
    if [[ "$SKIP_GOBUSTER" -eq 0 ]]; then
        if [[ ! -f "$WORDLIST" ]]; then
            log_warn "  Wordlist not found: ${WORDLIST} — skipping gobuster"
        elif command -v gobuster &>/dev/null; then
            local gobuster_out="${dir}/gobuster_${port}_${ts}.txt"
            # Evasion: single thread, 3s delay between requests, randomised UA
            local -a extra_flags=()
            local ua_list=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                           "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
                           "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0")
            local rand_ua="${ua_list[$((RANDOM % ${#ua_list[@]}))]}"
            [[ "$TIER" == "evasion" ]] && extra_flags=("--delay" "3000ms" "--useragent" "$rand_ua")
            {
                echo "# Directory Enumeration — ${url}"
                echo "# Engagement: ${PROJECT_NAME}"
                echo "# Date/Time:  $(_now)"
                echo "# Wordlist:   ${WORDLIST}"
                echo "# Tier:       ${TIER}"
                echo "---"
                # Shuffle wordlist in evasion mode to avoid sequential pattern signature
                local wordlist_input="$WORDLIST"
                if [[ "$TIER" == "evasion" ]]; then
                    local shuffled; shuffled=$(mktemp)
                    shuf "$WORDLIST" > "$shuffled"
                    wordlist_input="$shuffled"
                fi
                set +u
                timeout "$GOBUSTER_TIMEOUT" gobuster dir \
                    -u "${url}" \
                    -w "$wordlist_input" \
                    -q -k \
                    -t "$(gobuster_threads "$TIER")" \
                    --timeout "${CURL_TIMEOUT}s" \
                    "${extra_flags[@]}" \
                    2>&1 || log_warn "  gobuster ended early (timeout/error)"
                set -u
                [[ "$TIER" == "evasion" && -f "${shuffled:-}" ]] && rm -f "$shuffled"
            } | tee "$gobuster_out"
            log_ok "  Gobuster: ${gobuster_out}"
        else
            log_warn "  gobuster not found"
        fi
    fi

    # ── 5. Nikto ────────────────────────────────────────────────────────────
    # Nikto skipped in evasion tier — too noisy for WAF/IDS environments
    if [[ "$SKIP_NIKTO" -eq 0 && "$TIER" != "evasion" ]]; then
        if command -v nikto &>/dev/null; then
            local nikto_out="${dir}/nikto_${port}_${ts}.txt"
            {
                echo "# Nikto Scan — ${url}"
                echo "# Engagement: ${PROJECT_NAME}"
                echo "# Date/Time:  $(_now)"
                echo "---"
                timeout "$NIKTO_TIMEOUT" nikto \
                    -h "${url}" \
                    -ask no \
                    -nointeractive \
                    -maxtime "${NIKTO_TIMEOUT}s" \
                    2>&1 || log_warn "  nikto ended early (timeout/error)"
            } | tee "$nikto_out"
            log_ok "  Nikto: ${nikto_out}"
        else
            log_warn "  nikto not found"
        fi
    fi

    # ── 6. API Endpoint Discovery (VAPT-Enhanced) ──────────────────────────
    if [[ "$SKIP_API" -eq 0 ]]; then
        local api_out="${dir}/api_endpoints_${port}_${ts}.txt"
        {
            echo "# API Endpoint Discovery — ${url}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "# VAPT-Enhanced: expanded coverage for 2024-2025 common attack surfaces"
            echo "---"
            local api_endpoints=(
                # Core API paths
                "/api" "/api/v1" "/api/v2" "/api/v3" "/api/v4"
                "/rest" "/rest/v1" "/rest/api/1.0" "/rest/api/2"
                "/v1" "/v2" "/v3"
                # GraphQL (CVE-2021-31159 and general introspection abuse)
                "/graphql" "/graphiql" "/graphql/console" "/graphql/explorer"
                "/api/graphql" "/gql"
                # OpenAPI / Swagger (credential/schema exposure)
                "/swagger" "/swagger-ui" "/swagger-ui.html" "/swagger-ui/index.html"
                "/swagger.json" "/swagger.yaml" "/swagger/v1/swagger.json"
                "/openapi.json" "/openapi.yaml" "/openapi/v1/openapi.json"
                "/api-docs" "/api-docs/swagger.json" "/.well-known/openapi"
                "/docs" "/documentation" "/redoc" "/scalar"
                # Spring Boot Actuator (CWE-200 — credential/heap exposure)
                "/actuator" "/actuator/health" "/actuator/env" "/actuator/beans"
                "/actuator/mappings" "/actuator/heapdump" "/actuator/loggers"
                "/actuator/metrics" "/actuator/httptrace" "/actuator/threaddump"
                "/manage/actuator" "/manage/health"
                # Admin/Management panels
                "/admin" "/admin/" "/admin/login" "/administrator"
                "/manage" "/management" "/console" "/dashboard"
                "/wp-admin" "/wp-login.php" "/.git/HEAD"
                # OAuth2 / OIDC discovery (token endpoint exposure)
                "/.well-known/openid-configuration" "/.well-known/oauth-authorization-server"
                "/oauth/authorize" "/oauth/token" "/auth" "/auth/login"
                # Web services / WSDL
                "/wsdl" "/service.wsdl" "/api/wsdl" "/ws" "/services"
                # Health / status endpoints
                "/health" "/healthz" "/status" "/ping" "/ready" "/live"
                "/_health" "/_status" "/info" "/_cat"
                # Sensitive paths
                "/.env" "/config" "/config.json" "/settings" "/settings.json"
                "/debug" "/trace" "/metrics" "/server-status" "/server-info"
                # Jenkins (CVE-2024-23897)
                "/script" "/jnlpJars/jenkins-cli.jar" "/cli" "/computer" "/asynchPeople"
                # Node.js / Express debug
                "/node_modules" "/__webpack_hmr" "/sockjs-node"
                # Kubernetes / cloud
                "/version" "/api/v1/namespaces" "/metrics/cadvisor"
            )
            echo "Endpoint probing (${#api_endpoints[@]} paths):"
            for endpoint in "${api_endpoints[@]}"; do
                local code
                code=$(curl --max-time "$CURL_TIMEOUT" \
                            --connect-timeout "$CURL_CONNECT" \
                            -sk -o /dev/null \
                            -w "%{http_code}" \
                            "${url}${endpoint}" 2>/dev/null)
                code="${code:-000}"
                if [[ "$code" != "404" && "$code" != "000" && "$code" != "410" ]]; then
                    echo "  [${code}] ${endpoint}"
                    log_info "    API hit [${code}]: ${endpoint}"
                fi
                [[ "$TIER" == "evasion" ]] && sleep 2
            done
        } | tee "$api_out"
        log_ok "  API endpoints: ${api_out}"
    fi

    # ── 6b. GraphQL Introspection Check (VAPT-ADDED) ───────────────────────
    # GraphQL introspection exposes full schema — types, queries, mutations, fields.
    # Should be disabled in production. CWE-200: Information Exposure.
    if [[ "$SKIP_API" -eq 0 ]]; then
        local gql_out="${dir}/graphql_introspection_${port}_${ts}.txt"
        {
            echo "# GraphQL Introspection Check — ${url}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "# CWE-200: Introspection exposes full API schema to unauthenticated users"
            echo "---"
            local gql_query='{"query":"{ __schema { queryType { name } types { name kind } } }"}'
            local gql_endpoints=("/graphql" "/api/graphql" "/gql" "/graphql/console")
            local gql_hit=0
            for gql_ep in "${gql_endpoints[@]}"; do
                local gql_resp
                gql_resp=$(curl --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT" \
                    -sk -X POST -H "Content-Type: application/json" \
                    -d "$gql_query" "${url}${gql_ep}" 2>/dev/null || true)
                if echo "$gql_resp" | grep -qiE '"__schema"|"queryType"|"types".*"name"'; then
                    echo "  [INTROSPECTION ENABLED] ${gql_ep}"
                    echo "  Response (first 20 lines):"
                    echo "$gql_resp" | head -20
                    log_warn "  GraphQL introspection enabled at ${url}${gql_ep}"
                    gql_hit=1
                elif echo "$gql_resp" | grep -qiE '"data"|"errors"'; then
                    echo "  [GraphQL endpoint detected but introspection may be disabled] ${gql_ep}"
                fi
            done
            [[ "$gql_hit" -eq 0 ]] && echo "No GraphQL introspection enabled detected."
        } | tee "$gql_out"
        log_ok "  GraphQL check: ${gql_out}"
    fi

    # ── 6c. Sensitive File Exposure (VAPT-ADDED) ───────────────────────────
    # CWE-538 / CWE-312: Sensitive files accessible via web server
    # Common in misconfigured deployments, leaked via git, backup processes
    local sensfile_out="${dir}/sensitive_files_${port}_${ts}.txt"
    {
        echo "# Sensitive File Exposure — ${url}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "# CWE-538/CWE-312: Sensitive files accessible without authentication"
        echo "---"
        local sensitive_files=(
            ".env" ".env.local" ".env.production" ".env.backup"
            ".git/HEAD" ".git/config" ".gitignore" ".git/COMMIT_EDITMSG"
            "phpinfo.php" "info.php" "test.php" "php.php"
            "backup.sql" "db.sql" "database.sql" "dump.sql" "data.sql"
            "backup.zip" "backup.tar.gz" "site.zip" "www.zip"
            "config.php.bak" "wp-config.php.bak" "config.bak" "settings.bak"
            ".htpasswd" ".htaccess" "web.config.bak" "web.config~"
            "composer.json" "composer.lock" "package.json" "package-lock.json"
            "Dockerfile" ".dockerenv" "docker-compose.yml"
            "id_rsa" "id_rsa.pub" ".ssh/id_rsa" "server.key"
            "crossdomain.xml" "clientaccesspolicy.xml"
            "robots.txt" "sitemap.xml" "security.txt" "/.well-known/security.txt"
        )
        local found_count=0
        for sf in "${sensitive_files[@]}"; do
            local sf_code
            sf_code=$(curl --max-time 5 --connect-timeout 3 -sk \
                -o /dev/null -w "%{http_code}" "${url}/${sf}" 2>/dev/null || echo "000")
            if [[ "$sf_code" == "200" || "$sf_code" == "301" || "$sf_code" == "302" ]]; then
                echo "  [HIT ${sf_code}] /${sf}"
                log_warn "    SENSITIVE FILE: ${url}/${sf} → HTTP ${sf_code}"
                (( found_count++ )) || true
            fi
            [[ "$TIER" == "evasion" ]] && sleep 1
        done
        echo ""
        echo "Sensitive files found: ${found_count} / ${#sensitive_files[@]} probed"
    } | tee "$sensfile_out"
    log_ok "  Sensitive files: ${sensfile_out}"

    # ── 7. Default Credentials Check (nmap) ────────────────────────────────
    local defcreds_out="${dir}/nmap_webcreds_${port}_${ts}"
    # Respect tier timing — evasion uses T1, ghost T2, others T3
    local nmap_timing="-T3"
    case "$TIER" in evasion) nmap_timing="-T1";; ghost) nmap_timing="-T2";; esac
    run_rc_scan "webcreds_${ip}_${port}" \
         -Pn -p "$port" \
         --script "http-default-accounts" \
         --script-timeout 60s \
         "$nmap_timing" \
         "$ip" \
         -oA "$defcreds_out"
    log_ok "  Default creds check: ${defcreds_out}.nmap"

    # ── 8. CMS Detection ───────────────────────────────────────────────────
    # WordPress indicator from whatweb output.
    # WPScan itself is handled by 06_wpscan.sh — this step only flags presence
    # and registers the URL in scripts/wp_targets.txt for that script to consume.
    if grep -qi "wordpress\|wp-content\|wp-login" "$tech_out" 2>/dev/null; then
        log_warn "  WordPress detected on ${url}"
        local wp_targets_file="scripts/wp_targets.txt"
        # Append idempotently — only add if not already listed
        if ! grep -qxF "${url}" "${wp_targets_file}" 2>/dev/null; then
            echo "${url}" >> "${wp_targets_file}"
            log_ok "  Registered for WPScan: ${wp_targets_file}"
        else
            log_info "  Already in wp_targets.txt — skipping duplicate"
        fi
        log_warn "  Run 06_wpscan.sh for full WordPress assessment"
    fi

    # ── 9. Append to web summary ────────────────────────────────────────────
    local missing_count
    missing_count=$(grep -c "MISSING:" "$sec_out" 2>/dev/null || echo "?")
    echo "| ${ip} | ${port} | ${proto} | ${missing_count} missing | ${dir} |" \
        >> "working/web_summary_${SESSION_TS}.md"

    log_ok "Done: ${url}"
    echo ""
}

# =============================================================================
# MRK:05_MAIN — MAIN entry point | main,entry,point | L669-750
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    echo -e "${GREEN}"
    echo "════════════════════════════════════════════════"
    echo "  05_web_enum.sh"
    echo "  TechGuard."
    echo "  Project: ${PROJECT_NAME}"
    echo "  Tier:    ${TIER}"
    echo "  Mode:    $([ "$FAST_MODE" -eq 1 ] && echo "fast (headers+tech only)" || echo "full")"
    echo "════════════════════════════════════════════════"
    echo -e "${NC}"

    # Initialise web summary
    cat > "working/web_summary_${SESSION_TS}.md" << EOF
# Web Enumeration Summary — ${PROJECT_NAME}
*Generated: $(_now) | Session: ${SESSION_TS} | Tier: ${TIER}*

| IP | Port | Protocol | Sec Headers | Evidence Dir |
|----|------|----------|-------------|--------------|
EOF

    parse_db_conf

    # Trail: phase start
    local _05_t_start; _05_t_start=$(date +%s)
    trail_phase_start phase "web" project "${PROJECT_NAME:-}" mode "${MODE:-}" session "${SESSION_TS:-$(_ts)}" ts "$(date -u +%FT%TZ)" fast "${FAST:-0}" 2>/dev/null || true

    local targets; targets="$(assemble_targets)"

    if [[ -z "$targets" ]]; then
        log_err "No web targets found. Use --from-db, --targets <file>, or --host <IP:PORT>"
        exit 1
    fi

    local count; count=$(echo "$targets" | grep -c '[0-9]' || echo 0)
    log "Web targets: ${count}"
    scope_confirm "$count"

    # Evasion: randomise target order to avoid sequential scan signature
    if [[ "$TIER" == "evasion" ]]; then
        targets=$(echo "$targets" | shuf)
        log "Evasion mode: target order randomised"
    fi
    while IFS= read -r target; do
        [[ -z "$target" ]] && continue
        enumerate_host "$target"
    done <<< "$targets"

    # Finalise summary
    {
        echo ""
        echo "## Evidence Files"
        find "${EVIDENCE_BASE}" -maxdepth 2 \( \
             -name "headers_*" -o \
             -name "whatweb_*" -o \
             -name "gobuster_*" -o \
             -name "nikto_*" -o \
             -name "api_endpoints_*" \) 2>/dev/null | \
             sort | sed 's/^/- /'
        echo ""
        echo "---"
        echo "*05_web_enum.sh | TechGuard.*"
    } >> "working/web_summary_${SESSION_TS}.md"

    export_db "web"

    # Trail: phase end
    local _05_t_end; _05_t_end=$(date +%s)
    trail_phase_end phase "web" project "${PROJECT_NAME:-}" session "${SESSION_TS:-}" duration_sec "$((_05_t_end - _05_t_start))" ts "$(date -u +%FT%TZ)" 2>/dev/null || true

    log_ok "Web enumeration complete"
    log_ok "Summary: working/web_summary_${SESSION_TS}.md"
    log_ok "Per-host output: ${EVIDENCE_BASE}/<IP>/"
}

main

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
