#!/usr/bin/env bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:ORC_COMMON_LIB_NAV_TOC — Section index | nav,toc,index | L5-53
# - MRK:COM_DB — MSF / POSTGRES DIRECT ACCESS | com,db,msf,postgres,direct | L54-179
# - MRK:COM_TRAIL — MSF NOTES WRITER | com,trail,msf,notes,writer | L180-387
# - MRK:COM_BANNER — standalone banner | com,banner,standalone | L388-454
# - MRK:COM_SELFTEST — reserved for future --test mode | com,selftest,reserved,future,test | L455-476
# NAV-LEN: 4 entries | Integrity-hash: 8c2b4f7b2de9ee5b | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# orc-common-lib.sh -- PT-Orc shared helper library
# TechGuard. | Suite v0.92
# =============================================================================
# Purpose: single source of truth for cross-script helpers. Source once per script:
#   source "$(dirname "$0")/orc-common-lib.sh"
# Executed standalone: prints a banner describing the library and exits 0.
#
# v1 scope: logging, direct PostgreSQL access, trail/notes writer.
# Follow-up commits will migrate MSF-workspace, tier, and target helpers here.
# =============================================================================

if ! declare -F log_ok >/dev/null 2>&1; then
    [[ -z "${RED:-}"    ]] && RED='\033[0;31m'
    [[ -z "${GREEN:-}"  ]] && GREEN='\033[0;32m'
    [[ -z "${YELLOW:-}" ]] && YELLOW='\033[1;33m'
    [[ -z "${BLUE:-}"   ]] && BLUE='\033[0;34m'
    [[ -z "${CYAN:-}"   ]] && CYAN='\033[0;36m'
    [[ -z "${NC:-}"     ]] && NC='\033[0m'

    _ts()  { date +'%Y%m%d_%H%M%S'; }
    _now() { date +'%Y-%m-%d %H:%M:%S'; }

    log()      { local m="[$(_now)] $1";         echo -e "${BLUE}${m}${NC}"   >&2; echo "${m}" >> "${LOG_FILE:-/dev/null}" 2>/dev/null || true; }
    log_ok()   { local m="[$(_now)] [OK] $1";    echo -e "${GREEN}${m}${NC}"  >&2; echo "${m}" >> "${LOG_FILE:-/dev/null}" 2>/dev/null || true; }
    log_warn() { local m="[$(_now)] [WARN] $1";  echo -e "${YELLOW}${m}${NC}" >&2; echo "${m}" >> "${LOG_FILE:-/dev/null}" 2>/dev/null || true; }
    log_err()  { local m="[$(_now)] [ERR] $1";   echo -e "${RED}${m}${NC}"    >&2; echo "${m}" >> "${LOG_FILE:-/dev/null}" 2>/dev/null || true; }
    log_info() { local m="[$(_now)]   $1";       echo -e "${CYAN}${m}${NC}"   >&2; echo "${m}" >> "${LOG_FILE:-/dev/null}" 2>/dev/null || true; }
fi

# Red loud alert  used when a class-invariant assumption breaks (e.g. DB unreachable).
# Per user directive: "should never happen. we count on DB to be there."
# Visual: bold red background with bright foreground to stand out in log stream.
_alert() {
    local msg="$1"
    local bold_red='\033[1;97;41m'  # bright white on red background
    local m="[$(_now)] [ALERT] ${msg}"
    echo -e "${bold_red}${m}${NC}" >&2
    echo "${m}" >> "${LOG_FILE:-/dev/null}" 2>/dev/null || true
}

# =============================================================================
# MRK:COM_DB — MSF / POSTGRES DIRECT ACCESS | com,db,msf,postgres,direct | L54-179
# =============================================================================
# Direct TCP psql against the MSF DB. Reads credentials from database.yml.
# NEVER uses Unix socket (peer auth fails under root / non-msf users on Kali).
# On failure: _alert() loud red log line, callers receive empty string/0 rc.

# Defaults if pt-orc.conf / caller didn't export these
: "${MSF_DB_CONF:=/usr/share/metasploit-framework/config/database.yml}"
: "${MSF_DB_USER:=msf}"
: "${MSF_DB_NAME:=msf}"
: "${MSF_DB_HOST:=127.0.0.1}"
: "${MSF_DB_PORT:=5432}"
# Set to 0 by parse_db_conf() if psql cannot reach DB  callers may fall back.
: "${DB_DIRECT_AVAILABLE:=1}"

parse_db_conf() {
    if [[ -f "$MSF_DB_CONF" ]]; then
        MSF_DB_USER=$(grep -m1 'username:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" 2>/dev/null || echo "msf")
        MSF_DB_NAME=$(grep -m1 'database:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" 2>/dev/null || echo "msf")
        MSF_DB_PORT=$(grep -m1 'port:'     "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" 2>/dev/null || echo "5432")
        MSF_DB_HOST="127.0.0.1"  # force TCP; ignore yaml's host: field
        if [[ -z "${MSF_DB_PASS:-}" ]]; then
            MSF_DB_PASS=$(grep -m1 'password:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" 2>/dev/null || true)
        fi
        export MSF_DB_PASS
    fi

    # TCP connection test
    local _test
    _test=$(PGPASSWORD="${MSF_DB_PASS:-}" psql \
        -h "$MSF_DB_HOST" -p "$MSF_DB_PORT" \
        -U "$MSF_DB_USER" -d "$MSF_DB_NAME" \
        -t -A -c "SELECT 1;" 2>&1)
    if [[ "$_test" == *"1"* && "$_test" != *"error"* && "$_test" != *"FATAL"* ]]; then
        log_ok "DB direct: TCP OK (${MSF_DB_HOST}:${MSF_DB_PORT}, user=${MSF_DB_USER}, db=${MSF_DB_NAME})"
        DB_DIRECT_AVAILABLE=1
        return 0
    fi
    _alert "DB direct: TCP connection FAILED -- psql: $(echo "$_test" | head -1)"
    _alert "  Trail-lib writes will be suppressed. Fix: start postgresql + match creds in ${MSF_DB_CONF}"
    DB_DIRECT_AVAILABLE=0
    return 1
}

# db_query <sql> -> prints result to stdout (one value per line, no headers).
# Non-blocking on error: logs via _alert, returns empty string, rc=0 so callers
# never abort mid-flow.
db_query() {
    local sql="$1"
    local _out
    _out=$(PGPASSWORD="${MSF_DB_PASS:-}" psql \
        -h "$MSF_DB_HOST" -p "$MSF_DB_PORT" \
        -U "$MSF_DB_USER" -d "$MSF_DB_NAME" -t -A -c "$sql" 2>&1) || true
    if echo "$_out" | grep -qiE 'error|fatal|could not connect|password'; then
        _alert "db_query: psql error -- $(echo "$_out" | head -1 | cut -c1-200)"
        return 0
    fi
    echo "$_out"
}

# db_exec <sql> -> executes a write query (INSERT/UPDATE/DELETE). Returns rc 0 on
# success, 1 on psql error. Error path emits _alert.
db_exec() {
    local sql="$1"
    local _out _rc
    _out=$(PGPASSWORD="${MSF_DB_PASS:-}" psql \
        -h "$MSF_DB_HOST" -p "$MSF_DB_PORT" \
        -U "$MSF_DB_USER" -d "$MSF_DB_NAME" -t -A -c "$sql" 2>&1)
    _rc=$?
    if [[ $_rc -ne 0 ]] || echo "$_out" | grep -qiE 'error|fatal|could not connect'; then
        _alert "db_exec: psql error -- $(echo "$_out" | head -1 | cut -c1-200)"
        return 1
    fi
    return 0
}

# Workspace-id cache: lookup once per PROJECT_NAME, reuse.
declare -g _TRAIL_WS_ID_CACHE=""
declare -g _TRAIL_WS_ID_NAME=""

_db_get_workspace_id() {
    local name="${1:-${PROJECT_NAME:-}}"
    [[ -z "$name" ]] && { _alert "_db_get_workspace_id: PROJECT_NAME empty"; return 1; }
    if [[ "$_TRAIL_WS_ID_NAME" == "$name" && -n "$_TRAIL_WS_ID_CACHE" ]]; then
        echo "$_TRAIL_WS_ID_CACHE"
        return 0
    fi
    local wsid
    wsid=$(db_query "SELECT id FROM workspaces WHERE name = '$(_sql_esc "$name")' LIMIT 1;")
    wsid=$(echo "$wsid" | tr -d ' \n')
    if [[ -z "$wsid" ]]; then
        _alert "_db_get_workspace_id: no workspace found for name='${name}'"
        return 1
    fi
    _TRAIL_WS_ID_CACHE="$wsid"
    _TRAIL_WS_ID_NAME="$name"
    echo "$wsid"
}

# Host-id cache: lookup by (workspace_id, address), cache per-session.
declare -gA _TRAIL_HOST_ID_CACHE

_db_get_host_id() {
    local addr="$1"
    local wsid; wsid="$(_db_get_workspace_id)" || return 1
    local key="${wsid}:${addr}"
    if [[ -n "${_TRAIL_HOST_ID_CACHE[$key]:-}" ]]; then
        echo "${_TRAIL_HOST_ID_CACHE[$key]}"
        return 0
    fi
    local hid
    hid=$(db_query "SELECT id FROM hosts WHERE workspace_id = ${wsid} AND address = '$(_sql_esc "$addr")' LIMIT 1;")
    hid=$(echo "$hid" | tr -d ' \n')
    if [[ -n "$hid" ]]; then
        _TRAIL_HOST_ID_CACHE["$key"]="$hid"
        echo "$hid"
        return 0
    fi
    # Miss: by design (Q5=b) fall back to NULL host_id (session-scope note)
    return 2
}

# SQL single-quote escape (doubles any embedded single quotes)
_sql_esc() { local s="${1//\'/\'\'}"; echo -n "$s"; }

# =============================================================================
# MRK:COM_TRAIL — MSF NOTES WRITER | com,trail,msf,notes,writer | L180-387
# =============================================================================
# Design (confirmed 2026-04-21):
#   Q1 a = one psql INSERT per trail_* call (no batching)
#   Q4 b = on DB error, _alert loud red, continue (never abort caller)
#   Q5 b = on host_id miss, insert with NULL host_id (session-scope fallback)
#   a+a  = JSON in data column, host_id resolved+cached
# =============================================================================

# Build a JSON object from key/value pairs. Values are ALL strings (use jq's
# --arg which auto-quotes). For numeric/boolean values, convert after with
# _trail_json_patch (or just leave as strings  JSON permits).
# Usage: _trail_json key1 val1 key2 val2 ... -> prints compact JSON to stdout
_trail_json() {
    if ! command -v jq >/dev/null 2>&1; then
        # Soft-fail fallback (Q7 a preference: jq required). Crude hand-build.
        _alert "_trail_json: jq not found (soft-fail) -- using crude JSON builder"
        local out='{' sep=''
        while [[ $# -ge 2 ]]; do
            local k="$1" v="$2"
            v="${v//\\/\\\\}"   # escape backslash
            v="${v//\"/\\\"}"   # escape double quote
            v="${v//$'\n'/\\n}" # escape newline
            out+="${sep}\"${k}\":\"${v}\""
            sep=','
            shift 2
        done
        echo "${out}}"
        return
    fi
    local jq_args=() jq_expr='{' sep=''
    while [[ $# -ge 2 ]]; do
        jq_args+=(--arg "$1" "$2")
        jq_expr+="${sep}$1: \$$1"
        sep=', '
        shift 2
    done
    jq_expr+='}'
    jq -nc "${jq_args[@]}" "$jq_expr"
}

# Core INSERT primitive. Callers don't use this directly -- use trail_* wrappers.
#   _trail_insert <ntype> <data_json> [<host_address>]
# If host_address given and resolvable -> host_id populated; else NULL.
_trail_insert() {
    local ntype="$1" data="$2" addr="${3:-}"
    [[ "${DB_DIRECT_AVAILABLE:-1}" -ne 1 ]] && return 0   # silently skip if DB dead
    local wsid; wsid="$(_db_get_workspace_id)" || return 1

    local hid_sql="NULL"
    if [[ -n "$addr" ]]; then
        local hid; hid="$(_db_get_host_id "$addr")"
        local _rc=$?
        if [[ $_rc -eq 0 && -n "$hid" ]]; then
            hid_sql="$hid"
        fi
        # _rc=2 (miss) -> stay as NULL, no alert (Q5 b design)
        # _rc=1 (hard error) -> already alerted, stay as NULL
    fi

    local ntype_esc; ntype_esc="$(_sql_esc "$ntype")"
    local data_esc;  data_esc="$(_sql_esc "$data")"

    db_exec "INSERT INTO notes (workspace_id, host_id, ntype, data, created_at, updated_at, critical, seen) VALUES (${wsid}, ${hid_sql}, '${ntype_esc}', '${data_esc}', NOW(), NOW(), false, false);"
}

# ------------- Session-scope wrappers (row 1-3 of table) ---------------------

# trail_session_start -- emit orc.session.start + orc.scope
# Args (flat key=value pairs for _trail_json): proj=$PROJECT_NAME mode=$MODE ...
trail_session_start() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.session.start" "$data"
}

trail_session_end() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.session.end" "$data"
}

trail_scope() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.scope" "$data"
}

# ------------- Step-scope (row 4-5) ------------------------------------------

trail_step_start() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.step.start" "$data"
}

trail_step_end() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.step.end" "$data"
}

# ------------- Phase-scope (row 6-12) ----------------------------------------

trail_phase_start() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.phase.start" "$data"
}

trail_phase_end() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.phase.end" "$data"
}

trail_discovery_summary() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.discovery.summary" "$data"
}

trail_tcp_pass1() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.tcp.pass1" "$data"
}

trail_tcp_pass2() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.tcp.pass2" "$data"
}

trail_tcp_nse() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.tcp.nse" "$data"
}

trail_udp_summary() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.udp.summary" "$data"
}

# ------------- Per-host scope (row 13-14) ------------------------------------
# First positional arg is the host address; remaining are JSON key/value pairs.

trail_host_tcp_complete() {
    local host="$1"; shift
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.host.tcp.complete" "$data" "$host"
}

trail_host_udp_complete() {
    local host="$1"; shift
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.host.udp.complete" "$data" "$host"
}

# ------------- Per-(host,port) service wrappers (row 15-22) ------------------
# Convention: first arg = host, second = port. Port is embedded in the JSON
# data (msf's notes table has no port column; port linkage is via service_id
# which we don't populate -- rely on data.port for operator filtering).
# Convenience: pass port as-is; wrapper auto-adds it to data.

_trail_svc_insert() {
    # _trail_svc_insert <ntype> <host> <port> <extra-json-kv-pairs...>
    local ntype="$1" host="$2" port="$3"; shift 3
    local data; data="$(_trail_json port "$port" "$@")"
    _trail_insert "$ntype" "$data" "$host"
}

trail_svc_tls_testssl()  { _trail_svc_insert "orc.svc.tls.testssl"  "$@"; }
trail_svc_tls_headers()  { _trail_svc_insert "orc.svc.tls.headers"  "$@"; }
trail_svc_tls_screens()  { _trail_svc_insert "orc.svc.tls.screens"  "$@"; }
trail_svc_web_scan()     { _trail_svc_insert "orc.svc.web.scan"     "$@"; }
trail_svc_web_headers()  { _trail_svc_insert "orc.svc.web.headers"  "$@"; }
trail_svc_wp_detect()    { _trail_svc_insert "orc.svc.wp.detect"    "$@"; }
trail_svc_wp_scan()      { _trail_svc_insert "orc.svc.wp.scan"      "$@"; }

# Generic per-probe wrapper for 07. probe=<probe-name> (e.g. redis, mysql, ssh).
# ntype becomes orc.svc.<probe>.complete
trail_svc_probe_complete() {
    local probe="$1" host="$2" port="$3"; shift 3
    _trail_svc_insert "orc.svc.${probe}.complete" "$host" "$port" "$@"
}

# ------------- VAPT-specific trail wrappers ----------------------------------

# CVE finding record. host required (what was found vulnerable).
# Usage: trail_vapt_cve <host> cve <CVE-YYYY-NNNNN> severity <HIGH|CRITICAL> ...
trail_vapt_cve() {
    local host="$1"; shift
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.vapt.cve" "$data" "$host"
}

# Threat intel lookup result (AbuseIPDB / VirusTotal / Shodan CVE query).
trail_svc_threat_intel() {
    local host="$1"; shift
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.vapt.threat_intel" "$data" "$host"
}

# Subdomain takeover candidate.
trail_svc_dns_takeover() {
    local host="$1"; shift
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.vapt.dns_takeover" "$data" "$host"
}

# VAPT probe result (generic). Stores probe=<name>, result=<VULN|SAFE|INFO>.
trail_vapt_probe() {
    local host="$1" port="$2" probe="$3"; shift 3
    local data; data="$(_trail_json probe "$probe" port "$port" "$@")"
    _trail_insert "orc.vapt.probe" "$data" "$host"
}

# ------------- VAPT helper functions -----------------------------------------

# rate_limit_wait <seconds> — sleep with a log message; respects DRY_RUN.
rate_limit_wait() {
    local delay="${1:-1}"
    [[ "${DRY_RUN:-0}" -eq 1 ]] && { log_info "  [DRY-RUN] rate_limit_wait ${delay}s"; return 0; }
    sleep "$delay"
}

# tool_available <tool> — returns 0 if binary exists, logs a warning if not.
tool_available() {
    local tool="$1"
    command -v "$tool" &>/dev/null && return 0
    log_warn "  Tool not found: ${tool} — step skipped (install for full VAPT coverage)"
    return 1
}

# ------------- Meta (row 23-25) ----------------------------------------------

# MSF module invocation record. host optional (some modules are workspace-wide).
trail_msf_module() {
    local host="${1:-}"; shift
    local data; data="$(_trail_json "$@")"
    if [[ -n "$host" ]]; then
        _trail_insert "orc.msf.module" "$data" "$host"
    else
        _trail_insert "orc.msf.module" "$data"
    fi
}

# Tool error / timeout / unexpected condition. host optional.
trail_error() {
    local host="${1:-}"; shift
    local data; data="$(_trail_json "$@")"
    if [[ -n "$host" ]]; then
        _trail_insert "orc.error" "$data" "$host"
    else
        _trail_insert "orc.error" "$data"
    fi
}

# Export event (when 03/07 write a CSV from the workspace)
trail_export() {
    local data; data="$(_trail_json "$@")"
    _trail_insert "orc.export.csv" "$data"
}

# =============================================================================
# MRK:COM_BANNER — standalone banner | com,banner,standalone | L388-454
# =============================================================================

_orc_common_banner() {
    local line; line="$(printf '═%.0s' {1..70})"
    echo -e "${CYAN}${line}${NC}" >&2
    echo -e "${CYAN}  orc-common-lib  —  PT-Orc shared helper library${NC}" >&2
    echo -e "${CYAN}  TechGuard.   |   Suite v0.92${NC}" >&2
    echo -e "${CYAN}${line}${NC}" >&2
    cat <<'EOF' >&2

Purpose: single-source helpers for PT-Orc scripts -- logging, direct
PostgreSQL access, MSF DB "trail" notes writer.

Usage (from a script):
  source "$(dirname "$0")/orc-common-lib.sh"

  parse_db_conf                              # test + establish DB connection
  trail_session_start proj "$PROJECT_NAME" mode "$MODE" backend "db_nmap"
  trail_phase_start phase "tcp" ts "$(date -u +%FT%TZ)"
  trail_tcp_pass1 tier "ghost" targets 60 open_ports 12 duration 240
  trail_host_tcp_complete 192.168.10.160 pass1_done true pass2_done true
  trail_svc_tls_testssl 192.168.10.160 443 duration 45 output "/path/..."
  trail_error 192.168.10.160 phase tcp tool nmap reason "host_timeout 2m hit"

Design (v1):
  * One psql INSERT per trail_* call (no batching; connections are cheap)
  * Data stored as JSON in notes.data (jq-built; bash fallback if jq missing)
  * workspace_id + host_id resolved + cached per session
  * On DB failure: ALERT logged in red, callers continue (never abort)
  * Host_id miss: NULL (session-scope note, data not lost)

Event types provided (orc.* namespace):
  session.start / session.end / scope
  step.start / step.end
  phase.start / phase.end
  discovery.summary / tcp.pass1 / tcp.pass2 / tcp.nse / udp.summary
  host.tcp.complete / host.udp.complete
  svc.tls.{testssl|headers|screens}
  svc.web.{scan|headers}
  svc.wp.{detect|scan}
  svc.<probe>.complete      (generic 07 probe wrapper)
  msf.module / error / export.csv

Requirements:
  * bash 4+, psql (postgresql-client), jq (optional; soft-fail)
  * pt-orc.conf sourced into env (for PROJECT_NAME) before calling trail_*

Query examples (from shell or another script):
  # All events from one session:
  psql -h 127.0.0.1 -U msf -d msf -c \
    "SELECT created_at, ntype, data FROM notes
       WHERE ntype LIKE 'orc.%' AND data::text LIKE '%SESSION_TS_HERE%'
     ORDER BY created_at;"

  # All TCP Pass 1 summaries across this project:
  psql ... -c "SELECT data FROM notes WHERE ntype = 'orc.tcp.pass1';"

  # Extract + pretty-print with jq:
  psql ... -t -A -c "SELECT data FROM notes WHERE ntype LIKE 'orc.phase.%'" \
    | while read -r j; do echo "$j" | jq .; done

EOF
    echo -e "${CYAN}${line}${NC}" >&2
}

# =============================================================================
# MRK:COM_SELFTEST — reserved for future --test mode | com,selftest,reserved,future,test | L455-476
# =============================================================================
# TODO: add --test flag that runs:
#   1. parse_db_conf (connection test)
#   2. SELECT workspace id resolution
#   3. dummy INSERT + rollback (or INSERT with ntype=orc._selftest, DELETE after)
#   4. jq presence + JSON build test
# For now: not implemented. Banner-only on standalone execute.

# =============================================================================
# Sourced-vs-executed detection
# =============================================================================
# If executed standalone (not sourced), print banner and exit.
# Detection: when sourced, $0 is the sourcing script; BASH_SOURCE[0] is us.
# When executed, both are the same.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    _orc_common_banner
    exit 0
fi

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
