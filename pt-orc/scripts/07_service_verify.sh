#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:07_NAV_TOC — Section index | nav,toc,index | L5-68
# - MRK:07_ROOT — ROOT CHECK | root,check | L69-78 | ⚠ no-insert-before
# - MRK:07_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L79-119 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:07_LOG — COLOURS AND LOGGING | log,colours,logging | L120-141 | ⚠ no-insert-before
# - MRK:07_ARGS — ARGUMENT PARSING | args,argument,parsing | L142-166 | ⚠ no-insert-before
# - MRK:07_DB — MSF DB + MODULE RUNNER | db,msf,module,runner,tcp | L167-231 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:07_RESULTS — RESULT TRACKING  "STATUS | results,result,tracking,status,ip | L232-249 | ⚠ no-insert-before
# - MRK:07_PARSE — INPUT PARSING | parse,input,parsing,manual,followup | L250-529 | ⚠ no-insert-before; read-toc-first
# - MRK:07_TOOLS — TOOL AVAILABILITY | tools,tool,availability,check,startup | L530-554 | ⚠ no-insert-before
# - MRK:07_DIR — EVIDENCE DIR HELPER | dir,evidence,helper | L555-566 | ⚠ no-insert-before
# - MRK:07_P_REDIS — PROBE: REDIS NOAUTH | redis,probe,noauth,cli,ping | L567-631 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_MYSQL — PROBE: MYSQL NOAUTH / ANONYMOUS LOGIN | mysql,probe,noauth,anonymous,login | L632-686 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_PG — PROBE: POSTGRESQL NOAUTH | pg,probe,postgresql,noauth,postgres | L687-751 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_MONGO — PROBE: MONGODB NOAUTH | mongo,probe,mongodb,noauth,listdatabases | L752-811 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_SSH — PROBE: SSH VERSION | ssh,probe,version,cve,regresshion | L812-913 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_FTP — PROBE: FTP ANONYMOUS LOGIN | ftp,probe,anonymous,login | L914-979 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_SMB — PROBE: SMB NULL SESSION (PTI) | smb,probe,null,session,pti | L980-1031 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_SNMP — PROBE: SNMP DEFAULT COMMUNITY | snmp,probe,default,community,v1 | L1032-1087 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_SMTP — PROBE: SMTP OPEN RELAY | smtp,probe,open,relay,swaks | L1088-1148 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_SSRF — PROBE: SSRF → IMDS (PTE) | ssrf,probe,imds,pte,aws | L1149-1223 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_TLS — PROBE: TLS CERT VALIDITY | tls,probe,cert,validity,expiry | L1224-1289 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_WEBH — PROBE: HTTP SECURITY HEADERS | webh,probe,http,security,headers | L1290-1337 | ⚠ no-insert-before; read-toc-first
# - MRK:07_ENUM — POST-VULN ENUMERATION | enum,post,vuln,enumeration,redis | L1338-1509 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_MSSQL — PROBE: MSSQL | mssql,probe,unauthenticated,sa,empty | L1510-1556 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_NFS — PROBE: NFS | nfs,probe,showmount,world,accessible | L1557-1595 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_TELNET — PROBE: Telnet | telnet,probe,banner,grab,cleartext | L1596-1626 | ⚠ no-insert-before
# - MRK:07_P_IPMI — PROBE: IPMI | ipmi,probe,version,cipher,zero | L1627-1675 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_RDP — PROBE: RDP | rdp,probe,nla,check,encryption | L1676-1713 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_WINRM — PROBE: WinRM | winrm,probe,auth,exposure,check | L1714-1758 | ⚠ no-insert-before; read-toc-first
# - MRK:07_P_WEBGEN — PROBE: Web generic | webgen,probe,web,generic,banner | L1759-1842 | ⚠ no-insert-before; read-toc-first
# - MRK:07_INGEST — PHASE 0 INGEST STUBS | ingest,phase,stubs,parse,prior | L1843-1923 | ⚠ insert-here
# - MRK:07_DISPATCH — PROBE DISPATCHER | dispatch,probe,dispatcher,svc,function | L1924-2016 | ⚠ no-insert-before; read-toc-first
# - MRK:07_REPORT — REPORT WRITER | report,writer,working,verify,summary | L2017-2124 | ⚠ no-insert-before; read-toc-first
# - MRK:07_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L2125-2152 | ⚠ no-insert-before; propose-before-edit
# - MRK:07_MAIN — MAIN entry point | main,entry,point | L2153-2215 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 34 entries | Integrity-hash: a5da244216294dab | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# 07_service_verify.sh — TechGuard. [VAPT-Enhanced v1.0 — 2026-06-05]
# Intelligent targeted verification — driven by 03 manual_followup + scan_summary
# Reads what 01-06 flagged; runs targeted probes in priority order.
#
# VAPT ENHANCEMENTS (2024-2025 CVEs):
#   • CVE-2024-6387 regreSSHion (updated) + CVE-2024-6409 + CVE-2023-48795 Terrapin
#   • Elasticsearch/OpenSearch no-auth (port 9200) — CWE-306
#   • Kibana no-auth (port 5601)
#   • etcd no-auth (port 2379) — Kubernetes secret exposure
#   • Spring Boot Actuator /env credential leak — CWE-200
#   • Jenkins CVE-2024-23897 arbitrary file read (< 2.442)
#   • CUPS CVE-2024-47076/47175/47176/47177 IPP exposure chain
#   • MS17-010 EternalBlue detection via nmap NSE (SMB probe)
#   • Sensitive file exposure (.env, .git, phpinfo) in web probe
#   • CVE-2024-4577 PHP CGI argument injection detection
# =============================================================================
# USAGE:
#   sudo ./07_service_verify.sh [OPTIONS]
#
# OPTIONS:
#   --followup <file>   manual_followup MD to parse (default: latest in working/)
#   --summary <file>    scan_summary MD to supplement followup (default: latest)
#   --mode <pti|pte>    Override engagement mode from config
#   --tier <t>          ghost|normal|loud — controls timeouts/aggressiveness
#   --probe <category>  Run only: db|ssh|ftp|smb|snmp|smtp|ssrf|tls|headers|all (default: all)
#   --severity <level>  critical|high|medium|all — which MD severity flags to probe (default: critical)
#   --tls <file>        tls_summary MD to parse for cert/TLS probes (default: latest in working/)
#   --web <file>        web_summary MD to parse for header probes (default: latest in working/)
#   --host <IP:PORT:SVC> Add explicit target (can repeat; SVC: redis/mysql/pg/ssh/tls/http-headers/...)
#   --yes               Skip scope confirmation
#   --dry-run           Print probes without executing
#   --no-msf            Skip MSF auxiliary modules (use native tools only)
#   --msf-only          Skip native tools, use MSF modules only
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:07_ROOT — ROOT CHECK | root,check | L69-78
# NAV-RULE: no-insert-before
# =============================================================================
if [[ "$EUID" -ne 0 ]] && [[ "${PTORC_ALLOW_NON_ROOT:-0}" != "1" ]]; then
    echo "[ERROR] This script must be run as root."
    echo "        Run: sudo $0 $*"
    exit 1
fi

# =============================================================================
# MRK:07_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L79-119
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found — defaults used"

# Shared helpers (logging, DB access, trail/notes writer)
# shellcheck source=orc-common-lib.sh
[[ -f "${SCRIPT_DIR}/orc-common-lib.sh" ]] && source "${SCRIPT_DIR}/orc-common-lib.sh" \
    || echo "[WARN] orc-common-lib.sh not found — trail/notes writes will be disabled"

EVIDENCE_BASE="${EVIDENCE_BASE:-${SCRIPT_DIR}/evidence}"
[[ "$EVIDENCE_BASE" != /* ]] && EVIDENCE_BASE="$(pwd)/${EVIDENCE_BASE}"

TIER="${GLOBAL_TIER:-normal}"
MODE="${MODE:-pte}"
DRY_RUN=0
AUTO_YES=0
NO_MSF=0
MSF_ONLY=0
DEBUG_QUEUE=0
PROBE_FILTER="all"
SEVERITY_FILTER="critical"   # critical|high|medium|all — controls which MD flags to probe

FOLLOWUP_FILE=""
SUMMARY_FILE=""
TLS_SUMMARY_FILE=""
WEB_SUMMARY_FILE=""
WP_REPORT_FILE=""
DNS_SUMMARY_FILE=""
EXTRA_HOSTS=()

# Per-tier probe timeouts (seconds)
tier_timeout() { case "$1" in ghost) echo 10;; normal) echo 6;; loud) echo 3;; evasion) echo 15;; *) echo 6;; esac; }
tier_connect()  { case "$1" in ghost) echo 5;;  normal) echo 3;; loud) echo 2;; evasion) echo 8;;  *) echo 3;; esac; }

PROBE_TIMEOUT="$(tier_timeout "$TIER")"
CONNECT_TIMEOUT="$(tier_connect "$TIER")"

# =============================================================================
# MRK:07_LOG — COLOURS AND LOGGING | log,colours,logging | L120-141
# NAV-RULE: no-insert-before
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

_ts()  { date +'%Y%m%d_%H%M%S'; }
_now() { date +'%Y-%m-%d %H:%M:%S'; }

SESSION_TS="$(_ts)"

mkdir -p "${EVIDENCE_BASE}/_verify" working
LOG_FILE="${EVIDENCE_BASE}/_verify/verify_${SESSION_TS}.log"

log()     { local m="[$(_now)] $1";    echo -e "${BLUE}${m}${NC}"   >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_ok()  { local m="[$(_now)] ✓ $1"; echo -e "${GREEN}${m}${NC}"  >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_warn(){ local m="[$(_now)] ⚠ $1"; echo -e "${YELLOW}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_err() { local m="[$(_now)] ✗ $1"; echo -e "${RED}${m}${NC}"    >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_info(){ local m="[$(_now)]   $1"; echo -e "${CYAN}${m}${NC}"   >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }

# =============================================================================
# MRK:07_ARGS — ARGUMENT PARSING | args,argument,parsing | L142-166
# NAV-RULE: no-insert-before
# =============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --followup)  FOLLOWUP_FILE="$2"; shift 2 ;;
        --summary)   SUMMARY_FILE="$2";  shift 2 ;;
        --tls)       TLS_SUMMARY_FILE="$2"; shift 2 ;;
        --web)       WEB_SUMMARY_FILE="$2"; shift 2 ;;
        --mode)      MODE="$2";          shift 2 ;;
        --tier)      TIER="$2"; PROBE_TIMEOUT="$(tier_timeout "$TIER")"; CONNECT_TIMEOUT="$(tier_connect "$TIER")"; shift 2 ;;
        --probe)     PROBE_FILTER="$2";  shift 2 ;;
        --severity)  SEVERITY_FILTER="$2"; shift 2 ;;
        --host)      EXTRA_HOSTS+=("$2"); shift 2 ;;
        --yes)       AUTO_YES=1;         shift ;;
        --dry-run)   DRY_RUN=1;          shift ;;
        --no-msf)      NO_MSF=1;         shift ;;
        --msf-only)    MSF_ONLY=1;       shift ;;
        --debug-queue) DEBUG_QUEUE=1; DRY_RUN=1; AUTO_YES=1; shift ;;
        *) log_err "Unknown argument: $1"; exit 1 ;;
    esac
done

# =============================================================================
# MRK:07_DB — MSF DB + MODULE RUNNER | db,msf,module,runner,tcp | L167-231
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

MSF_DB_CONF="/usr/share/metasploit-framework/config/database.yml"
MSF_DB_USER="msf"; MSF_DB_NAME="msf"; MSF_DB_HOST="127.0.0.1"; MSF_DB_PORT="5432"
MSF_DB_PASS="${MSF_DB_PASS:-}"
RC_DIR="${EVIDENCE_BASE}/_msf"

parse_db_conf() {
    [[ -f "$MSF_DB_CONF" ]] || return
    MSF_DB_USER=$(grep -m1 'username:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "msf")
    MSF_DB_NAME=$(grep -m1 'database:'  "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "msf")
    MSF_DB_PORT=$(grep -m1 'port:'      "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "5432")
    MSF_DB_HOST="127.0.0.1"
    [[ -z "${MSF_DB_PASS}" ]] && \
        MSF_DB_PASS=$(grep -m1 'password:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" 2>/dev/null || true)
    export MSF_DB_PASS
}

db_query() {
    PGPASSWORD="${MSF_DB_PASS:-}" psql -h "$MSF_DB_HOST" -p "$MSF_DB_PORT" \
        -U "$MSF_DB_USER" -d "$MSF_DB_NAME" -t -A -c "$1" 2>/dev/null || true
}

# Run an MSF auxiliary module via RC file + spool.
# Usage: run_msf_module <label> <module_path> [KEY VALUE ...]
# Returns spool file path (stdout). Caller parses for success strings.
# NOTE: see action-plan MRK:SUITE "MSF module call quality audit" — some modules
# reject RPORT (mssql_ping, mssql_login, postgres_login confirmed bad in MSF 6.4+).
run_msf_module() {
    local label="$1" module="$2"; shift 2
    mkdir -p "$RC_DIR"
    local ts; ts="$(_ts)"
    local rc_file="${RC_DIR}/verify_${label}_${ts}.rc"
    local spool_file="${RC_DIR}/verify_${label}_${ts}.log"

    {
        printf 'spool %s\n'          "$spool_file"
        printf 'workspace -a %s\n'   "${PROJECT_NAME:-verify}"
        printf 'use %s\n'            "$module"
        while [[ $# -gt 0 ]]; do
            printf 'set %s %s\n' "$1" "$2"
            shift 2
        done
        printf 'set VERBOSE false\n'
        printf 'run\n'
        printf 'spool off\n'
        printf 'exit\n'
    } > "$rc_file"

    log_info "  MSF [${module}] → ${spool_file}"
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] msfconsole -q -r ${rc_file}"
        echo "/dev/null"
        return 0
    fi
    # Synchronous run — module completes before exit; timeout prevents hangs
    timeout $(( PROBE_TIMEOUT + 15 )) \
        bash -c "PGPASSWORD='${MSF_DB_PASS:-}' msfconsole -q -r '$rc_file'" \
        </dev/null >/dev/null 2>&1 || true
    echo "$spool_file"
}

# =============================================================================
# MRK:07_RESULTS — RESULT TRACKING  "STATUS | results,result,tracking,status,ip | L232-249
# NAV-RULE: no-insert-before
# =============================================================================

RESULTS=()

add_result() {
    local status="$1" ip="$2" port="$3" service="$4" detail="$5" evidence="${6:-}"
    RESULTS+=("${status}|${ip}|${port}|${service}|${detail}|${evidence}")
    case "$status" in
        VULN)    log_ok  "  [VULN]    ${service}:${port} @ ${ip} — ${detail}" ;;
        SAFE)    log_info "  [SAFE]    ${service}:${port} @ ${ip} — ${detail}" ;;
        UNKNOWN) log_warn "  [UNKNOWN] ${service}:${port} @ ${ip} — ${detail}" ;;
        MANUAL)  log_warn "  [MANUAL]  ${service}:${port} @ ${ip} — ${detail}" ;;
    esac
}

# =============================================================================
# MRK:07_PARSE — INPUT PARSING | parse,input,parsing,manual,followup | L250-529
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

# Auto-discover latest file matching a glob pattern in working/
latest_working() {
    local pattern="$1"
    find "$(pwd)/working" -maxdepth 1 -name "$pattern" 2>/dev/null \
        | sort | tail -1
}

# Parse manual_followup MD → emit one IP per line for a given keyword category.
# Handles three formats: pipe-delimited table, inline on keyword line, block list
# after a section header. $1=file $2=keyword
# Parse a pipe-delimited markdown table and return "ip|reason" for each row
# whose Reason column ($3) matches keyword. IP is always field $2.
# This is the primary parser for manual_followup_*.md (format: | IP | Reason | Action |)
parse_table_row() {
    local file="$1" keyword="$2"
    grep -iE "$keyword" "$file" 2>/dev/null \
    | awk -F'|' '
        NF >= 4 {
            ip = $2; reason = $3
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", ip)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", reason)
            if (ip ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/)
                print ip "|" reason
        }
    ' 2>/dev/null
}

# Returns one IP per line from pipe-table rows matching keyword — for callers
# that only need the IP (port/service hardcoded). Also used for tls/web summary.
parse_followup_category() {
    local file="$1" keyword="$2"
    parse_table_row "$file" "$keyword" | cut -d'|' -f1 | sort -u
}

# Build probe queue from followup + MSF DB + extras.
# Queue entry format: "CATEGORY:ip port svc"
# Reads manual_followup_*.md (pipe table: | IP | Reason | Action |)
build_probe_queue() {
    local followup="$1"
    local queue=()
    local seen=()   # dedup tracker "ip:port:svc"

    add_to_queue() {
        local cat="$1" ip="$2" port="$3" svc="$4"
        [[ -z "$ip" || -z "$port" || -z "$svc" ]] && return
        local key="${ip}:${port}:${svc}"
        # skip duplicates
        local k; for k in "${seen[@]+"${seen[@]}"}"; do [[ "$k" == "$key" ]] && return; done
        seen+=("$key")
        queue+=("${cat}:${ip} ${port} ${svc}")
    }

    # ── 1. CRITICAL: Externally exposed DB services (PTE) ──────────────────────
    # Reason column contains "Service:Port EXTERNALLY EXPOSED"
    while IFS='|' read -r ip reason; do
        local svc_port; svc_port=$(echo "$reason" | grep -oP '[A-Za-z]+:[0-9]+' | head -1)
        [[ -z "$svc_port" ]] && continue
        local svc; svc=$(echo "$svc_port" | cut -d: -f1 | tr '[:upper:]' '[:lower:]')
        local port; port=$(echo "$svc_port" | cut -d: -f2)
        # normalise service names
        case "$svc" in
            postgresql) svc="postgres" ;;
        esac
        add_to_queue CRITICAL "$ip" "$port" "$svc"
    done < <(parse_table_row "$followup" "EXTERNALLY EXPOSED")

    # ── 2. DB services by port pattern (PTI: "PostgreSQL port 5432 open") ──────
    while IFS='|' read -r ip reason; do
        # Extract port from reason text: "PostgreSQL port 5432 open" → 5432
        local port; port=$(echo "$reason" | grep -oP '\b(6379|6380|3306|3307|5432|5433|27017|27018|1433|1434)\b' | head -1)
        [[ -z "$port" ]] && continue
        local svc
        case "$port" in
            6379|6380)      svc="redis" ;;
            3306|3307)      svc="mysql" ;;
            5432|5433)      svc="postgres" ;;
            27017|27018)    svc="mongodb" ;;
            1433|1434)      svc="mssql" ;;
        esac
        add_to_queue CRITICAL "$ip" "$port" "$svc"
    done < <(parse_table_row "$followup" \
        "port [0-9]+ open|database.*open|db.*open|Redis|MySQL|PostgreSQL|MongoDB|MSSQL|MariaDB")

    # ── 3. SSH (both "SSH detected" / PTE and "SSH version detected" / PTI) ─────
    while IFS='|' read -r ip reason; do
        # Check if a non-default port is mentioned in the reason
        local port; port=$(echo "$reason" | grep -oP '\b(22|2222|2200)\b' | head -1)
        add_to_queue SSH "$ip" "${port:-22}" "ssh"
    done < <(parse_table_row "$followup" \
        "SSH detected|SSH version detected|SSH open|SSH.*CVE|ssh.*port")

    # ── 4. SMTP / Mail ──────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(25|465|587|2525)\b' | head -1)
        add_to_queue SMTP "$ip" "${port:-25}" "smtp"
    done < <(parse_table_row "$followup" \
        "Mail service|SMTP|mail.*open|mail.*relay|open relay")

    # ── 5. FTP ──────────────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(21|990|2121)\b' | head -1)
        add_to_queue FTP "$ip" "${port:-21}" "ftp"
    done < <(parse_table_row "$followup" "FTP open|FTP detected|ftp.*port|anonymous ftp")

    # ── 6. SMB ──────────────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(139|445)\b' | head -1)
        add_to_queue SMB "$ip" "${port:-445}" "smb"
    done < <(parse_table_row "$followup" \
        "SMB|Samba|CIFS|NetBIOS|smb.*open|smb.*null")

    # ── 7. SNMP ─────────────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        add_to_queue SNMP "$ip" "161" "snmp"
    done < <(parse_table_row "$followup" "SNMP responding|SNMP open|snmp.*detected")

    # ── 8. Telnet ───────────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(23|992|2323)\b' | head -1)
        add_to_queue TELNET "$ip" "${port:-23}" "telnet"
    done < <(parse_table_row "$followup" "Telnet open|telnet.*cleartext|telnet.*detected")

    # ── 9. IPMI ─────────────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        add_to_queue IPMI "$ip" "623" "ipmi"
    done < <(parse_table_row "$followup" "IPMI|iDRAC|BMC.*detected|ipmi.*port")

    # ── 10. RDP ─────────────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(3389|3388)\b' | head -1)
        add_to_queue RDP "$ip" "${port:-3389}" "rdp"
    done < <(parse_table_row "$followup" "RDP detected|RDP open|rdp.*port|Remote Desktop")

    # ── 11. WinRM ───────────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(5985|5986)\b' | head -1)
        add_to_queue WINRM "$ip" "${port:-5985}" "winrm"
    done < <(parse_table_row "$followup" "WinRM open|WinRM detected|winrm.*port|5985|5986")

    # ── 12. NFS ─────────────────────────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        add_to_queue NFS "$ip" "2049" "nfs"
    done < <(parse_table_row "$followup" "NFS export|NFS detected|nfs.*open|showmount")

    # ── 13. SSRF / IMDS (PTE web hosts) ────────────────────────────────────────
    if [[ "$MODE" == "pte" ]]; then
        while IFS='|' read -r ip reason; do
            add_to_queue SSRF "$ip" "80" "ssrf"
        done < <(parse_table_row "$followup" \
            "SSRF|cloud metadata|IMDS|169\.254|metadata.*probe")
    fi

    # ── 13b. Elasticsearch/OpenSearch (VAPT-ADDED) ──────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(9200|9201|9300)\b' | head -1)
        add_to_queue ES "$ip" "${port:-9200}" "elasticsearch"
    done < <(parse_table_row "$followup" \
        "Elasticsearch|OpenSearch|elasticsearch.*open|9200.*open")

    # ── 13c. Kibana (VAPT-ADDED) ────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(5601|5602)\b' | head -1)
        add_to_queue KIBANA "$ip" "${port:-5601}" "kibana"
    done < <(parse_table_row "$followup" "Kibana|kibana.*open|5601.*open")

    # ── 13d. etcd (VAPT-ADDED) ──────────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(2379|2380)\b' | head -1)
        add_to_queue ETCD "$ip" "${port:-2379}" "etcd"
    done < <(parse_table_row "$followup" "etcd|2379.*open|kubernetes.*secret.*store")

    # ── 13e. Jenkins (VAPT-ADDED) ───────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        local port; port=$(echo "$reason" | grep -oP '\b(8080|8090|9090|8888)\b' | head -1)
        add_to_queue JENKINS "$ip" "${port:-8080}" "jenkins"
    done < <(parse_table_row "$followup" \
        "Jenkins|jenkins.*detected|CI.*server|8080.*build|X-Jenkins")

    # ── 13f. CUPS/IPP (VAPT-ADDED) ──────────────────────────────────────────
    while IFS='|' read -r ip reason; do
        add_to_queue CUPS "$ip" "631" "cups"
    done < <(parse_table_row "$followup" "CUPS|IPP|cups.*printing|631.*open|printing.*service")

    # ── 14. Web services — generic header+banner check for all web hosts ────────
    #   PTE: "Web service(s): 80 443 8080"  PTI: "Web service(s) on 80 10443"
    while IFS='|' read -r ip reason; do
        # Extract all port numbers from the reason field
        local ports_raw; ports_raw=$(echo "$reason" | grep -oP '\b\d{2,5}\b')
        local p
        for p in $ports_raw; do
            case "$p" in
                80|443|8080|8443|8000|8888|10443|3000|4443|9443)
                    add_to_queue WEB "$ip" "$p" "web" ;;
            esac
        done
    done < <(parse_table_row "$followup" \
        "Web service|web.*port|HTTP|HTTPS|http.*open|https.*open")

    # ── 15. MSF DB sweep (PTI — supplements followup; covers anything missed) ──
    if [[ "$MODE" == "pti" ]]; then
        local wid=""
        wid=$(db_query "SELECT id FROM workspaces WHERE name='${PROJECT_NAME:-}' LIMIT 1;" 2>/dev/null)
        if [[ -z "$wid" && -n "${PROJECT_NAME:-}" ]]; then
            wid=$(db_query "SELECT id FROM workspaces WHERE name ILIKE '${PROJECT_NAME}%' LIMIT 1;" 2>/dev/null)
        fi
        if [[ -z "$wid" ]]; then
            wid=$(db_query "SELECT id FROM workspaces ORDER BY id DESC LIMIT 1;" 2>/dev/null)
            [[ -n "$wid" ]] && log_warn "  PTI: MSF workspace name mismatch — using most recent (id=${wid})"
        fi

        if [[ -n "$wid" ]]; then
            local all_ports="21,22,23,25,80,139,443,445,465,587,631,1433,2049,2222,2379,2525,3306,3389,5432,5601,5985,5986,6379,6380,8080,8200,8443,8500,9200,10443,27017"
            while IFS= read -r entry; do
                [[ -z "$entry" ]] && continue
                local ip; ip=$(echo "$entry" | cut -d: -f1)
                local port; port=$(echo "$entry" | cut -d: -f2)
                case "$port" in
                    6379|6380)          add_to_queue CRITICAL "$ip" "$port" "redis" ;;
                    3306)               add_to_queue CRITICAL "$ip" "$port" "mysql" ;;
                    5432)               add_to_queue CRITICAL "$ip" "$port" "postgres" ;;
                    27017)              add_to_queue CRITICAL "$ip" "$port" "mongodb" ;;
                    1433)               add_to_queue CRITICAL "$ip" "$port" "mssql" ;;
                    9200)               add_to_queue ES "$ip" "$port" "elasticsearch" ;;
                    2379)               add_to_queue ETCD "$ip" "$port" "etcd" ;;
                    5601)               add_to_queue KIBANA "$ip" "$port" "kibana" ;;
                    8500)               add_to_queue CONSUL "$ip" "$port" "consul" ;;
                    8200)               add_to_queue VAULT "$ip" "$port" "vault" ;;
                    22|2222)            add_to_queue SSH "$ip" "$port" "ssh" ;;
                    21)                 add_to_queue FTP "$ip" "$port" "ftp" ;;
                    25|465|587|2525)    add_to_queue SMTP "$ip" "$port" "smtp" ;;
                    139|445)            add_to_queue SMB "$ip" "$port" "smb" ;;
                    23)                 add_to_queue TELNET "$ip" "$port" "telnet" ;;
                    3389)               add_to_queue RDP "$ip" "$port" "rdp" ;;
                    5985|5986)          add_to_queue WINRM "$ip" "$port" "winrm" ;;
                    2049)               add_to_queue NFS "$ip" "$port" "nfs" ;;
                    631)                add_to_queue CUPS "$ip" "$port" "cups" ;;
                    80|443|8080|8443|10443) add_to_queue WEB "$ip" "$port" "web" ;;
                esac
            done < <(db_query "SELECT host(h.address)||':'||s.port \
                FROM services s JOIN hosts h ON s.host_id=h.id \
                WHERE h.workspace_id=${wid} AND s.proto='tcp' AND s.state='open' \
                AND s.port IN (${all_ports});" 2>/dev/null)
            # SNMP UDP
            while IFS= read -r entry; do
                [[ -z "$entry" ]] && continue
                local ip; ip=$(echo "$entry" | cut -d: -f1)
                add_to_queue SNMP "$ip" "161" "snmp"
            done < <(db_query "SELECT host(h.address)||':'||s.port \
                FROM services s JOIN hosts h ON s.host_id=h.id \
                WHERE h.workspace_id=${wid} AND s.proto='udp' AND s.state='open' \
                AND s.port IN (161,623);" 2>/dev/null)
        fi

        # scan_summary fallback when MSF DB empty / unavailable
        if [[ "${#queue[@]}" -eq 0 && -f "$SUMMARY_FILE" ]]; then
            log_warn "  PTI: MSF DB empty — falling back to scan_summary"
            while IFS= read -r line; do
                local ip; ip=$(echo "$line" | grep -oP '\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b' | head -1)
                local port; port=$(echo "$line" | grep -oP '\b(21|22|23|25|80|139|443|445|1433|2049|3306|3389|5432|5985|5986|6379|8080|8443|27017)\b' | head -1)
                [[ -z "$ip" || -z "$port" ]] && continue
                case "$port" in
                    6379) add_to_queue CRITICAL "$ip" "$port" "redis" ;;
                    3306) add_to_queue CRITICAL "$ip" "$port" "mysql" ;;
                    5432) add_to_queue CRITICAL "$ip" "$port" "postgres" ;;
                    27017) add_to_queue CRITICAL "$ip" "$port" "mongodb" ;;
                    1433) add_to_queue CRITICAL "$ip" "$port" "mssql" ;;
                    22|2222) add_to_queue SSH "$ip" "$port" "ssh" ;;
                    21) add_to_queue FTP "$ip" "$port" "ftp" ;;
                    25|465|587) add_to_queue SMTP "$ip" "$port" "smtp" ;;
                    139|445) add_to_queue SMB "$ip" "$port" "smb" ;;
                    23) add_to_queue TELNET "$ip" "$port" "telnet" ;;
                    3389) add_to_queue RDP "$ip" "$port" "rdp" ;;
                    5985|5986) add_to_queue WINRM "$ip" "$port" "winrm" ;;
                    2049) add_to_queue NFS "$ip" "$port" "nfs" ;;
                    80|443|8080|8443|10443) add_to_queue WEB "$ip" "$port" "web" ;;
                esac
            done < <(grep -P '\b(21|22|23|25|80|139|443|445|1433|2049|3306|3389|5432|5985|5986|6379|8080|8443|27017)\b' \
                "$SUMMARY_FILE" 2>/dev/null)
        fi
    fi

    # ── 16. HIGH severity: TLS cert + HTTP header checks ───────────────────────
    if [[ "$SEVERITY_FILTER" == "high" || "$SEVERITY_FILTER" == "medium" || \
          "$SEVERITY_FILTER" == "all" ]]; then
        if [[ -f "$TLS_SUMMARY_FILE" ]]; then
            while IFS= read -r tls_ip; do
                [[ -z "$tls_ip" ]] && continue
                add_to_queue TLS "$tls_ip" "443" "tls"
            done < <(parse_followup_category "$TLS_SUMMARY_FILE" \
                "EXPIRED|SELF.SIGNED|SHA1|WEAK|HIGH|expired|self-signed")
        fi
        if [[ -f "$WEB_SUMMARY_FILE" ]]; then
            while IFS= read -r web_ip; do
                [[ -z "$web_ip" ]] && continue
                add_to_queue HEADERS "$web_ip" "80" "http-headers"
                add_to_queue HEADERS "$web_ip" "443" "http-headers"
            done < <(parse_followup_category "$WEB_SUMMARY_FILE" \
                "missing.*header|security header|HSTS|X-Frame|CSP")
        fi
    fi

    # ── 17. Explicit --host overrides ──────────────────────────────────────────
    for h in "${EXTRA_HOSTS[@]+"${EXTRA_HOSTS[@]}"}"; do
        local ip; ip=$(echo "$h" | cut -d: -f1)
        local port; port=$(echo "$h" | cut -d: -f2)
        local svc; svc=$(echo "$h" | cut -d: -f3 | tr '[:upper:]' '[:lower:]')
        add_to_queue EXTRA "$ip" "$port" "$svc"
    done

    printf '%s\n' "${queue[@]+"${queue[@]}"}"
}

# =============================================================================
# MRK:07_TOOLS — TOOL AVAILABILITY | tools,tool,availability,check,startup | L530-554
# NAV-RULE: no-insert-before
# =============================================================================

have() { command -v "$1" >/dev/null 2>&1; }

check_tools() {
    local missing=()
    have redis-cli  || missing+=("redis-cli (apt install redis-tools)")
    have mysql      || missing+=("mysql (apt install default-mysql-client)")
    have psql       || missing+=("psql (apt install postgresql-client)")
    have mongosh    || have mongo || missing+=("mongosh (apt install mongodb-mongosh) — MongoDB probe will use MSF")
    have nc         || missing+=("nc (apt install netcat-openbsd)")
    have smbclient  || missing+=("smbclient (apt install smbclient)")
    have snmpwalk   || missing+=("snmpwalk (apt install snmp)")
    have swaks      || missing+=("swaks (apt install swaks) — SMTP relay probe degraded")
    have curl       || missing+=("curl")
    have openssl    || missing+=("openssl — TLS cert probe degraded")
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_warn "Missing tools (probes will fall back to MSF or MANUAL):"
        for t in "${missing[@]}"; do log_warn "  - $t"; done
    fi
}

# =============================================================================
# MRK:07_DIR — EVIDENCE DIR HELPER | dir,evidence,helper | L555-566
# NAV-RULE: no-insert-before
# =============================================================================

verify_dir_for() {
    local ip="$1"
    local d="${EVIDENCE_BASE}/_verify/${ip}"
    mkdir -p "$d"
    echo "$d"
}

# =============================================================================
# MRK:07_P_REDIS — PROBE: REDIS NOAUTH | redis,probe,noauth,cli,ping | L567-631
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_redis() {
    local ip="$1" port="${2:-6379}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/redis_noauth_${SESSION_TS}.txt"
    log "  Probing Redis NOAUTH @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] redis-cli -h ${ip} -p ${port} PING; INFO server"; return
    fi

    local result=""

    if [[ "${MSF_ONLY}" -eq 0 ]] && have redis-cli; then
        result=$(timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" \
            --no-auth-warning PING 2>&1 || true)
        {
            echo "# redis-cli PING @ ${ip}:${port} — $(_now)"
            echo "$result"
            echo ""
            # If PING succeeded, also grab server info
            if echo "$result" | grep -qi "^PONG$"; then
                echo "# INFO server"
                timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" \
                    --no-auth-warning INFO server 2>&1 || true
                echo ""
                echo "# CONFIG GET maxmemory (confirm read access)"
                timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" \
                    --no-auth-warning CONFIG GET maxmemory 2>&1 || true
            fi
        } > "$evfile" 2>&1

        if echo "$result" | grep -qi "^PONG$"; then
            enumerate_redis_vuln "$ip" "$port" "$evfile"
            add_result VULN "$ip" "$port" "redis" "NOAUTH — PONG returned; unauthenticated read/write access confirmed. See evidence for full INFO/CONFIG/KEYS dump." "$evfile"
            return
        elif echo "$result" | grep -qi "NOAUTH"; then
            add_result SAFE "$ip" "$port" "redis" "Authentication required (NOAUTH response)" "$evfile"
            return
        elif echo "$result" | grep -qi "refused\|timeout\|unreachable"; then
            add_result UNKNOWN "$ip" "$port" "redis" "Connection failed — port may be filtered or closed" "$evfile"
            return
        fi
    fi

    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "6379" ]]; then
            local spool; spool=$(run_msf_module "redis_${ip//./_}" \
                "auxiliary/scanner/redis/redis_server" \
                RHOSTS "$ip" RPORT "$port" THREADS 1)
            cp "$spool" "$evfile" 2>/dev/null || true
            if grep -qi "Redis server\|redis_version\|PONG" "$spool" 2>/dev/null; then
                add_result VULN "$ip" "$port" "redis" "NOAUTH — MSF redis_server module confirmed unauthenticated access" "$evfile"
            else
                add_result UNKNOWN "$ip" "$port" "redis" "MSF probe inconclusive — manual verification required" "$evfile"
            fi
            return
        else
            add_result MANUAL "$ip" "$port" "redis" \
                "Non-default Redis port (${port}); MSF redis_server rejects RPORT in 6.4+. Check manually: redis-cli -h ${ip} -p ${port} PING" ""
            return
        fi
    fi

    add_result MANUAL "$ip" "$port" "redis" "redis-cli and msfconsole unavailable — probe not run" ""
}

# =============================================================================
# MRK:07_P_MYSQL — PROBE: MYSQL NOAUTH / ANONYMOUS LOGIN | mysql,probe,noauth,anonymous,login | L632-686
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_mysql() {
    local ip="$1" port="${2:-3306}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/mysql_noauth_${SESSION_TS}.txt"
    log "  Probing MySQL NOAUTH @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] mysql -h ${ip} -P ${port} -u '' -e 'show databases;'"; return
    fi

    if [[ "${MSF_ONLY}" -eq 0 ]] && have mysql; then
        local result
        result=$(timeout "${PROBE_TIMEOUT}" mysql \
            -h "$ip" -P "$port" -u '' \
            --connect-timeout="${CONNECT_TIMEOUT}" \
            --skip-ssl 2>/dev/null \
            -e "show databases; select user();" 2>&1 || true)
        echo "# mysql NOAUTH @ ${ip}:${port} — $(_now)" > "$evfile"
        echo "$result" >> "$evfile"

        if echo "$result" | grep -qi "^Database$\|information_schema\|mysql\|performance_schema"; then
            enumerate_mysql_vuln "$ip" "$port" "$evfile"
            add_result VULN "$ip" "$port" "mysql" "NOAUTH — anonymous login succeeded; database listing + schema enumeration in evidence." "$evfile"
            return
        elif echo "$result" | grep -qi "Access denied"; then
            add_result SAFE "$ip" "$port" "mysql" "Access denied for anonymous user — authentication required" "$evfile"
            return
        fi
    fi

    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "3306" ]]; then
            local spool; spool=$(run_msf_module "mysql_${ip//./_}" \
                "auxiliary/scanner/mysql/mysql_login" \
                RHOSTS "$ip" RPORT "$port" \
                USERNAME "" PASSWORD "" BLANK_PASSWORDS true \
                STOP_ON_SUCCESS true THREADS 1)
            cp "$spool" "$evfile" 2>/dev/null || true
            if grep -qi "Login Successful\|logged in\|success" "$spool" 2>/dev/null; then
                add_result VULN "$ip" "$port" "mysql" "NOAUTH — MSF mysql_login confirmed anonymous access" "$evfile"
            elif grep -qi "Login Failed\|Access denied" "$spool" 2>/dev/null; then
                add_result SAFE "$ip" "$port" "mysql" "MSF login probe — authentication required" "$evfile"
            else
                add_result UNKNOWN "$ip" "$port" "mysql" "MSF probe inconclusive — manual verification required" "$evfile"
            fi
            return
        else
            add_result MANUAL "$ip" "$port" "mysql" \
                "Non-default MySQL port (${port}); MSF mysql_login rejects RPORT in 6.4+. Check manually: mysql -h ${ip} -P ${port} -u '' -e 'show databases;'" ""
            return
        fi
    fi

    add_result MANUAL "$ip" "$port" "mysql" "mysql client and msfconsole unavailable — probe not run" ""
}

# =============================================================================
# MRK:07_P_PG — PROBE: POSTGRESQL NOAUTH | pg,probe,postgresql,noauth,postgres | L687-751
# NAV-RULE: no-insert-before; read-toc-first
# NOTE: MSF postgres_login RPORT confirmed bad (MSF 6.4+) — see action-plan.
# =============================================================================

probe_postgres() {
    local ip="$1" port="${2:-5432}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/postgres_noauth_${SESSION_TS}.txt"
    log "  Probing PostgreSQL NOAUTH @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] psql -h ${ip} -p ${port} -U postgres -c '\l'"; return
    fi

    if [[ "${MSF_ONLY}" -eq 0 ]] && have psql; then
        local result
        # Try postgres user first (most common misconfiguration), then anonymous
        result=$(PGPASSWORD="" PGCONNECT_TIMEOUT="${CONNECT_TIMEOUT}" \
            timeout "${PROBE_TIMEOUT}" psql \
            -h "$ip" -p "$port" -U postgres \
            -c '\l' 2>&1 || true)
        echo "# psql NOAUTH @ ${ip}:${port} (user=postgres) — $(_now)" > "$evfile"
        echo "$result" >> "$evfile"

        if echo "$result" | grep -qi "List of databases\|template0\|template1"; then
            enumerate_postgres_vuln "$ip" "$port" "$evfile"
            add_result VULN "$ip" "$port" "postgres" "NOAUTH — postgres user accepted without password; database + role enumeration in evidence." "$evfile"
            return
        elif echo "$result" | grep -qi "password authentication failed\|authentication failed\|pg_hba"; then
            add_result SAFE "$ip" "$port" "postgres" "Password authentication required for postgres user" "$evfile"
            return
        fi
    fi

    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        # FIX 2026-04-20: postgres_login rejects RPORT in MSF 6.4+ — silently probes default 5432.
        # Only call MSF when probe port IS 5432 (then module default matches). For any other port,
        # MSF would probe 5432 (wrong host:port); fall through to MANUAL instead.
        if [[ "$port" == "5432" ]]; then
            local spool; spool=$(run_msf_module "pg_${ip//./_}" \
                "auxiliary/scanner/postgres/postgres_login" \
                RHOSTS "$ip" \
                USERNAME "postgres" PASSWORD "" BLANK_PASSWORDS true \
                STOP_ON_SUCCESS true THREADS 1)
            cp "$spool" "$evfile" 2>/dev/null || true
            if grep -qi "Login Successful\|logged in\|success" "$spool" 2>/dev/null; then
                add_result VULN "$ip" "$port" "postgres" "NOAUTH — MSF postgres_login confirmed access without password" "$evfile"
            elif grep -qi "Login Failed\|authentication failed" "$spool" 2>/dev/null; then
                add_result SAFE "$ip" "$port" "postgres" "MSF login probe — authentication required" "$evfile"
            else
                add_result UNKNOWN "$ip" "$port" "postgres" "MSF probe inconclusive — manual verification required" "$evfile"
            fi
            return
        else
            add_result MANUAL "$ip" "$port" "postgres" \
                "Non-default PostgreSQL port (${port}); MSF postgres_login rejects RPORT in 6.4+ so cannot be used. Native psql also failed. Check manually: psql -h ${ip} -p ${port} -U postgres -c '\\l'" ""
            return
        fi
    fi

    add_result MANUAL "$ip" "$port" "postgres" "psql and msfconsole unavailable — probe not run" ""
}

# =============================================================================
# MRK:07_P_MONGO — PROBE: MONGODB NOAUTH | mongo,probe,mongodb,noauth,listdatabases | L752-811
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_mongodb() {
    local ip="$1" port="${2:-27017}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/mongodb_noauth_${SESSION_TS}.txt"
    log "  Probing MongoDB NOAUTH @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] mongosh ${ip}:${port}/admin --eval 'db.adminCommand({listDatabases:1})'"; return
    fi

    if [[ "${MSF_ONLY}" -eq 0 ]]; then
        local mongo_bin=""
        have mongosh && mongo_bin="mongosh"
        have mongo   && [[ -z "$mongo_bin" ]] && mongo_bin="mongo"

        if [[ -n "$mongo_bin" ]]; then
            local result
            result=$(timeout "${PROBE_TIMEOUT}" "$mongo_bin" \
                "${ip}:${port}/admin" \
                --eval "db.adminCommand({listDatabases:1})" \
                --quiet --norc 2>&1 || true)
            echo "# ${mongo_bin} NOAUTH @ ${ip}:${port} — $(_now)" > "$evfile"
            echo "$result" >> "$evfile"

            if echo "$result" | grep -qi "databases.*\[\|totalSize\|\"name\""; then
                enumerate_mongodb_vuln "$ip" "$port" "$evfile" "$mongo_bin"
                add_result VULN "$ip" "$port" "mongodb" "NOAUTH — unauthenticated listDatabases succeeded; collection enumeration in evidence." "$evfile"
                return
            elif echo "$result" | grep -qi "Unauthorized\|Authentication failed\|auth"; then
                add_result SAFE "$ip" "$port" "mongodb" "Authentication required" "$evfile"
                return
            fi
        fi
    fi

    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "27017" ]]; then
            local spool; spool=$(run_msf_module "mongo_${ip//./_}" \
                "auxiliary/scanner/mongodb/mongodb_login" \
                RHOSTS "$ip" RPORT "$port" \
                USERNAME "" PASSWORD "" BLANK_PASSWORDS true \
                STOP_ON_SUCCESS true THREADS 1)
            cp "$spool" "$evfile" 2>/dev/null || true
            if grep -qi "Login Successful\|Successful Login\|success" "$spool" 2>/dev/null; then
                add_result VULN "$ip" "$port" "mongodb" "NOAUTH — MSF mongodb_login confirmed unauthenticated access" "$evfile"
            elif grep -qi "Login Failed\|Unauthorized" "$spool" 2>/dev/null; then
                add_result SAFE "$ip" "$port" "mongodb" "MSF probe — authentication required" "$evfile"
            else
                add_result UNKNOWN "$ip" "$port" "mongodb" "MSF probe inconclusive — manual verification required" "$evfile"
            fi
            return
        else
            add_result MANUAL "$ip" "$port" "mongodb" \
                "Non-default MongoDB port (${port}); MSF mongodb_login rejects RPORT in 6.4+. Check manually: mongosh ${ip}:${port}/admin --eval 'db.adminCommand({listDatabases:1})'" ""
            return
        fi
    fi

    add_result MANUAL "$ip" "$port" "mongodb" "mongosh/mongo and msfconsole unavailable — probe not run" ""
}

# =============================================================================
# MRK:07_P_SSH — PROBE: SSH VERSION | ssh,probe,version,cve,regresshion | L812-913
# NAV-RULE: no-insert-before; read-toc-first
# Vulnerable range: OpenSSH 8.5p1 – 9.7p1 (fixed in 9.8p1)
# Also checks < 4.4p1 (historic — unlikely in 2026 but included)
# =============================================================================

probe_ssh_version() {
    local ip="$1" port="${2:-22}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/ssh_version_${SESSION_TS}.txt"
    log "  Probing SSH version @ ${ip}:${port} (CVE-2024-6387 range check)"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] nc -w3 ${ip} ${port}  # grab banner"; return
    fi

    local banner=""

    if [[ "${MSF_ONLY}" -eq 0 ]] && have nc; then
        banner=$(timeout "${PROBE_TIMEOUT}" nc -w3 "$ip" "$port" 2>/dev/null | head -1 || true)
        echo "# SSH banner @ ${ip}:${port} — $(_now)" > "$evfile"
        echo "$banner" >> "$evfile"
    fi

    if [[ -z "$banner" ]] && have ssh; then
        banner=$(timeout "${PROBE_TIMEOUT}" ssh -o BatchMode=yes \
            -o ConnectTimeout="${CONNECT_TIMEOUT}" \
            -o StrictHostKeyChecking=no \
            -vvv "$ip" -p "$port" 2>&1 | grep "Remote protocol version\|Server version\|SSH-" | head -2 || true)
        echo "$banner" >> "$evfile"
    fi

    if [[ -z "$banner" ]] && [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "22" ]]; then
            local spool; spool=$(run_msf_module "ssh_ver_${ip//./_}" \
                "auxiliary/scanner/ssh/ssh_version" \
                RHOSTS "$ip" RPORT "$port" THREADS 1)
            banner=$(grep -oP 'SSH-[0-9.-]+OpenSSH[_/][0-9p.]+[^,\s]*' "$spool" 2>/dev/null | head -1 || true)
            cp "$spool" "$evfile" 2>/dev/null || true
        else
            add_result MANUAL "$ip" "$port" "ssh" \
                "Non-default SSH port (${port}); MSF ssh_version rejects RPORT in 6.4+. Check manually: nc -w3 ${ip} ${port} | head -1" "$evfile"
            return
        fi
    fi

    if [[ -z "$banner" ]]; then
        if grep -qi "EHOSTUNREACH\|No route to host\|Connection refused\|refused" "$evfile" 2>/dev/null; then
            add_result SAFE "$ip" "$port" "ssh" "SSH unreachable at probe time — not assessed for CVE-2024-6387" "$evfile"
        else
            add_result UNKNOWN "$ip" "$port" "ssh" "Could not retrieve banner — port may be filtered" "$evfile"
        fi
        return
    fi

    # Extract OpenSSH version string e.g. OpenSSH_9.2p1
    local ver_str; ver_str=$(echo "$banner" | grep -oP 'OpenSSH[_/][0-9]+\.[0-9]+p?[0-9]*' | head -1)
    if [[ -z "$ver_str" ]]; then
        # Dropbear version check — versions < 2022.83 have known CVEs
        local dropbear_ver; dropbear_ver=$(echo "$banner" | grep -oP '(?i)dropbear[_/]([0-9]{4}\.[0-9]+)' | grep -oP '[0-9]{4}\.[0-9]+' | head -1)
        if [[ -n "$dropbear_ver" ]]; then
            local db_year db_minor
            db_year=$(echo "$dropbear_ver" | cut -d. -f1)
            db_minor=$(echo "$dropbear_ver" | cut -d. -f2)
            if [[ "$db_year" -lt 2022 ]] || [[ "$db_year" -eq 2022 && "$db_minor" -lt 83 ]]; then
                add_result VULN "$ip" "$port" "ssh" "Dropbear SSH ${dropbear_ver} — predates 2022.83; CVE-2020-15778 / CVE-2021-36369 candidates. Manual exploitation check required." "$evfile"
            else
                add_result SAFE "$ip" "$port" "ssh" "Dropbear SSH ${dropbear_ver} — patched (>= 2022.83)" "$evfile"
            fi
            return
        fi
        if echo "$banner" | grep -qi "zyxel\|ZyXEL"; then
            add_result MANUAL "$ip" "$port" "ssh" "Zyxel SSH server — vendor firmware; check version manually against Zyxel security advisories. Banner: ${banner}" "$evfile"
            return
        fi
        add_result UNKNOWN "$ip" "$port" "ssh" "Banner received but version not parseable: ${banner}" "$evfile"
        return
    fi

    # Extract major.minorp from OpenSSH_X.YpZ
    local major minor patch
    major=$(echo "$ver_str" | grep -oP '[0-9]+\.[0-9]+' | cut -d. -f1)
    minor=$(echo "$ver_str" | grep -oP '[0-9]+\.[0-9]+' | cut -d. -f2)
    patch=$(echo "$ver_str" | grep -oP 'p[0-9]+' | tr -d 'p' || echo "0")

    # CVE-2024-6387: vulnerable if 8.5p1 <= version <= 9.7p1
    local vuln=0
    if [[ "$major" -eq 8 && "$minor" -ge 5 ]] || \
       [[ "$major" -eq 9 && "$minor" -le 7 ]]; then
        vuln=1
    fi
    # Also catch 9.8+ which is patched
    [[ "$major" -eq 9 && "$minor" -ge 8 ]] && vuln=0
    [[ "$major" -gt 9 ]] && vuln=0
    # Ancient < 4.4p1 (theoretical)
    [[ "$major" -lt 4 ]] && vuln=1
    [[ "$major" -eq 4 && "$minor" -lt 4 ]] && vuln=1

    # CVE-2024-6409: Signal handler race in privsep child process (lower severity than 6387)
    # Affected: OpenSSH 8.7p1–9.7p1 on glibc-based Linux (similar race, different signal path)
    local vuln_6409=0
    if [[ "$major" -eq 8 && "$minor" -ge 7 ]] || [[ "$major" -eq 9 && "$minor" -le 7 ]]; then
        vuln_6409=1
    fi
    [[ "$major" -eq 9 && "$minor" -ge 8 ]] && vuln_6409=0
    [[ "$major" -gt 9 ]] && vuln_6409=0

    # CVE-2023-48795: Terrapin attack — SSH key exchange prefix truncation
    # Affected: OpenSSH < 9.6p1 when ETM MACs or chacha20-poly1305 are negotiated
    # Impact: MitM can downgrade security extensions (e.g. keystroke timing obfuscation)
    # Fixed: 9.6p1 disables vulnerable algorithms by default; strict key exchange mode added
    local vuln_terrapin=0
    if [[ "$major" -lt 9 ]] || [[ "$major" -eq 9 && "$minor" -lt 6 ]]; then
        vuln_terrapin=1
    fi

    local cve_notes=()
    [[ "$vuln" -eq 1 ]]         && cve_notes+=("CVE-2024-6387 regreSSHion (SIGALRM race RCE, 8.5p1–9.7p1)")
    [[ "$vuln_6409" -eq 1 ]]    && cve_notes+=("CVE-2024-6409 privsep-child race (8.7p1–9.7p1, lower severity)")
    [[ "$vuln_terrapin" -eq 1 ]] && cve_notes+=("CVE-2023-48795 Terrapin prefix-truncation MitM (< 9.6p1)")

    echo "Parsed: major=${major} minor=${minor} patch=${patch} vuln_6387=${vuln} vuln_6409=${vuln_6409} vuln_terrapin=${vuln_terrapin}" >> "$evfile"

    if [[ ${#cve_notes[@]} -gt 0 ]]; then
        add_result VULN "$ip" "$port" "ssh" "${ver_str} — CVE candidates: $(IFS='; '; echo "${cve_notes[*]}")" "$evfile"
    else
        add_result SAFE "$ip" "$port" "ssh" "${ver_str} — outside CVE-2024-6387/6409/2023-48795 vulnerable ranges" "$evfile"
    fi
}

# =============================================================================
# MRK:07_P_FTP — PROBE: FTP ANONYMOUS LOGIN | ftp,probe,anonymous,login | L914-979
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_ftp_anon() {
    local ip="$1" port="${2:-21}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/ftp_anon_${SESSION_TS}.txt"
    log "  Probing FTP anonymous @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] curl ftp://${ip}:${port}/ --user anonymous:test@test.com -l"; return
    fi

    if [[ "${MSF_ONLY}" -eq 0 ]] && have curl; then
        local result
        result=$(timeout "${PROBE_TIMEOUT}" curl -s \
            --connect-timeout "${CONNECT_TIMEOUT}" \
            --max-time "${PROBE_TIMEOUT}" \
            "ftp://${ip}:${port}/" \
            --user "anonymous:anon@test.com" \
            -l 2>&1 || true)
        echo "# FTP anonymous @ ${ip}:${port} — $(_now)" > "$evfile"
        echo "$result" >> "$evfile"

        # VULN: non-empty result with no curl error prefix → directory listing
        if echo "$result" | grep -qvE "^curl:|^$" && \
           echo "$result" | grep -qvE "Login failed|530|refused|timed out|denied"; then
            if echo "$result" | grep -qE "."; then
                add_result VULN "$ip" "$port" "ftp" "Anonymous login succeeded — directory listing returned" "$evfile"
                return
            fi
        fi
        # VULN: explicit 230 banner captured
        if echo "$result" | grep -qi "230 Login\|230-\|anonymous.*login"; then
            add_result VULN "$ip" "$port" "ftp" "Anonymous login accepted (230 response)" "$evfile"
            return
        fi
        # SAFE: curl exit 67 (Login denied), 530, or explicit rejection strings
        if echo "$result" | grep -qi "curl: (67)\|530\|Login incorrect\|Login denied\|anonymous.*not allowed\|access denied"; then
            add_result SAFE "$ip" "$port" "ftp" "Anonymous login rejected" "$evfile"
            return
        fi
    fi

    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "21" ]]; then
            local spool; spool=$(run_msf_module "ftp_${ip//./_}" \
                "auxiliary/scanner/ftp/anonymous" \
                RHOSTS "$ip" RPORT "$port" THREADS 1)
            cp "$spool" "$evfile" 2>/dev/null || true
            # MSF success patterns: [+] line with "Allowed" or "Anonymous" or 230
            if grep -qi "Anonymous.*Login Allowed\|Anonymous.*login\|\[+\].*ftp.*anon\|230.*anon\|successful" "$spool" 2>/dev/null; then
                add_result VULN "$ip" "$port" "ftp" "MSF ftp/anonymous — anonymous login confirmed" "$evfile"
            # MSF reject patterns: denied, no anonymous, 530, login failed
            elif grep -qi "access denied\|No anonymous\|denied\|530\|Login failed\|rejected\|% complete\|Auxiliary module execution completed" "$spool" 2>/dev/null; then
                add_result SAFE "$ip" "$port" "ftp" "MSF probe — anonymous login not permitted" "$evfile"
            else
                add_result UNKNOWN "$ip" "$port" "ftp" "MSF probe inconclusive — check evidence" "$evfile"
            fi
            return
        else
            add_result MANUAL "$ip" "$port" "ftp" \
                "Non-default FTP port (${port}); MSF ftp/anonymous rejects RPORT in 6.4+. Check manually: curl ftp://${ip}:${port}/ --user anonymous:anon@test.com -l" ""
            return
        fi
    fi

    add_result UNKNOWN "$ip" "$port" "ftp" "curl and msfconsole unavailable — not probed" ""
}

# =============================================================================
# MRK:07_P_SMB — PROBE: SMB NULL SESSION (PTI) | smb,probe,null,session,pti | L980-1031
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_smb_null() {
    local ip="$1" port="${2:-445}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/smb_null_${SESSION_TS}.txt"
    log "  Probing SMB null session @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] smbclient -L //${ip} -N -p ${port}"; return
    fi

    if [[ "${MSF_ONLY}" -eq 0 ]] && have smbclient; then
        local result
        result=$(timeout "${PROBE_TIMEOUT}" smbclient \
            -L "//${ip}" -N -p "$port" 2>&1 || true)
        echo "# SMB null session @ ${ip}:${port} — $(_now)" > "$evfile"
        echo "$result" >> "$evfile"

        if echo "$result" | grep -qi "Sharename\|IPC\$\|ADMIN\$"; then
            add_result VULN "$ip" "$port" "smb" "Null session — share enumeration succeeded without credentials" "$evfile"
            return
        elif echo "$result" | grep -qi "NT_STATUS_"; then
            add_result SAFE "$ip" "$port" "smb" "Null session rejected ($(echo "$result" | grep -oi 'NT_STATUS_[A-Z_]*' | head -1))" "$evfile"
            return
        fi
    fi

    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        # RPORT is not a valid option for smb_enumshares in MSF 6.4+ — module always probes 445
        local spool; spool=$(run_msf_module "smb_${ip//./_}" \
            "auxiliary/scanner/smb/smb_enumshares" \
            RHOSTS "$ip" \
            SMBUser "" SMBPass "" THREADS 1)
        cp "$spool" "$evfile" 2>/dev/null || true
        if grep -qi "DISK\|IPC\|ADMIN\|PRINT\|Sharename" "$spool" 2>/dev/null; then
            add_result VULN "$ip" "$port" "smb" "MSF smb_enumshares — null session share enumeration succeeded" "$evfile"
        elif grep -qi "ACCESS_DENIED\|authentication\|NT_STATUS\|% complete" "$spool" 2>/dev/null; then
            # "% complete" with no shares = module ran cleanly, null session not permitted
            add_result SAFE "$ip" "$port" "smb" "MSF probe — null session not permitted" "$evfile"
        else
            add_result UNKNOWN "$ip" "$port" "smb" "MSF probe inconclusive" "$evfile"
        fi
        return
    fi

    # CVE-2017-0144 (MS17-010 EternalBlue) — still found on unpatched Windows hosts
    # Also checks CVE-2020-0796 (SMBGhost, Windows 10/2019 SMBv3.1.1 compression)
    if have nmap; then
        local eb_out="${vdir}/smb_eternalblue_${SESSION_TS}.txt"
        log "    [SMB] Checking MS17-010 (EternalBlue) via nmap NSE..."
        local eb_result
        eb_result=$(timeout 30 nmap -Pn -p "$port" \
            --script "smb-vuln-ms17-010,smb-security-mode,smb2-security-mode" \
            --script-timeout 25s "$ip" 2>&1 || true)
        echo "# MS17-010 EternalBlue check @ ${ip}:${port} — $(_now)" > "$eb_out"
        echo "$eb_result" >> "$eb_out"
        if echo "$eb_result" | grep -qiE "VULNERABLE|State: VULNERABLE|ms17-010.*vulnerable"; then
            add_result VULN "$ip" "$port" "smb" \
                "CVE-2017-0144 (MS17-010 EternalBlue) CANDIDATE — nmap smb-vuln-ms17-010 flagged vulnerable; manual exploitation verification required" "$eb_out"
            return
        fi
        echo "$eb_result" | grep -qiE "SMB signing.*disabled|message signing.*disabled" && \
            log_warn "    SMB signing disabled on ${ip}:${port} — relay attack vector present"
    fi

    add_result UNKNOWN "$ip" "$port" "smb" "smbclient and msfconsole unavailable — not probed" ""
}

# =============================================================================
# MRK:07_P_SNMP — PROBE: SNMP DEFAULT COMMUNITY | snmp,probe,default,community,v1 | L1032-1087
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_snmp() {
    local ip="$1" port="${2:-161}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/snmp_default_${SESSION_TS}.txt"
    log "  Probing SNMP default community @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] snmpwalk -v2c -c public -t${CONNECT_TIMEOUT} ${ip} sysDescr"; return
    fi

    if [[ "${MSF_ONLY}" -eq 0 ]] && have snmpwalk; then
        local result
        # -p required: snmpwalk defaults to 161 but explicit is safer; UDP implicit
        result=$(timeout "${PROBE_TIMEOUT}" snmpwalk \
            -v2c -c public -t "${CONNECT_TIMEOUT}" -r 1 \
            -p "$port" "$ip" sysDescr 2>&1 || true)
        echo "# snmpwalk -v2c -c public @ ${ip}:${port} — $(_now)" > "$evfile"
        echo "$result" >> "$evfile"

        if echo "$result" | grep -qi "SNMPv2-MIB::sysDescr\|STRING:"; then
            local descr; descr=$(echo "$result" | grep -i "STRING:" | head -1 | sed 's/.*STRING: //')
            add_result VULN "$ip" "$port" "snmp" "Default community 'public' accepted — sysDescr: ${descr}" "$evfile"
            return
        elif echo "$result" | grep -qi "Timeout\|No response\|No Such\|refused"; then
            add_result SAFE "$ip" "$port" "snmp" "No SNMP response to community 'public' — filtered or not running" "$evfile"
            return
        fi
        # snmpwalk returned something but no sysDescr — fall through to MSF for clarity
    fi

    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "161" ]]; then
            local spool; spool=$(run_msf_module "snmp_${ip//./_}" \
                "auxiliary/scanner/snmp/snmp_login" \
                RHOSTS "$ip" RPORT "$port" \
                COMMUNITY "public" VERSION "2c" THREADS 1)
            cp "$spool" "$evfile" 2>/dev/null || true
            # MSF snmp_login success line: "[+] ip:port - SNMP Community: public (Access: read-only)"
            if grep -qi "SNMP Community\|\[+\].*snmp\|read-only\|read-write\|Access:.*public" "$spool" 2>/dev/null; then
                local access; access=$(grep -oi "Access: [^)]*" "$spool" | head -1 || echo "read-only")
                add_result VULN "$ip" "$port" "snmp" "MSF snmp_login — community 'public' accepted (${access})" "$evfile"
            elif grep -qi "No.*community\|login.*fail\|denied\|\[-\]" "$spool" 2>/dev/null; then
                add_result SAFE "$ip" "$port" "snmp" "MSF snmp_login — community 'public' rejected" "$evfile"
            else
                add_result UNKNOWN "$ip" "$port" "snmp" "MSF SNMP probe inconclusive — check evidence" "$evfile"
            fi
            return
        else
            add_result MANUAL "$ip" "$port" "snmp" \
                "Non-default SNMP port (${port}); MSF snmp_login rejects RPORT in 6.4+. Check manually: snmpwalk -v2c -c public -p ${port} ${ip} sysDescr" ""
            return
        fi
    fi

    add_result UNKNOWN "$ip" "$port" "snmp" "snmpwalk and msfconsole unavailable — not probed" ""
}

# =============================================================================
# MRK:07_P_SMTP — PROBE: SMTP OPEN RELAY | smtp,probe,open,relay,swaks | L1088-1148
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_smtp_relay() {
    local ip="$1" port="${2:-25}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/smtp_relay_${SESSION_TS}.txt"
    log "  Probing SMTP open relay @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] swaks --to probe@era-test.invalid --from relay-check@target.invalid --server ${ip} --port ${port}"; return
    fi

    if [[ "${MSF_ONLY}" -eq 0 ]] && have swaks; then
        local result
        result=$(timeout "${PROBE_TIMEOUT}" swaks \
            --to "probe@era-relay-check.invalid" \
            --from "relay-check@era-relay-check.invalid" \
            --server "$ip" --port "$port" \
            --timeout "${PROBE_TIMEOUT}" \
            --quit-after RCPT 2>&1 || true)
        echo "# swaks SMTP relay @ ${ip}:${port} — $(_now)" > "$evfile"
        echo "$result" >> "$evfile"

        # swaks response lines: "<-  NNN text" — check last server response (= RCPT TO result)
        local last_srv; last_srv=$(echo "$result" | grep "^<-" | tail -1)
        if [[ -z "$last_srv" ]]; then
            # No server response at all — connection refused or timeout
            add_result SAFE "$ip" "$port" "smtp" "SMTP unreachable — no server response at probe time" "$evfile"
            return
        elif echo "$last_srv" | grep -qE "^<-\s+2[0-9][0-9]"; then
            add_result VULN "$ip" "$port" "smtp" "OPEN RELAY — RCPT TO for external domain accepted (2xx response)" "$evfile"
            return
        elif echo "$last_srv" | grep -qE "^<-\s+[45][0-9][0-9]"; then
            add_result SAFE "$ip" "$port" "smtp" "Relay rejected ($(echo "$last_srv" | grep -oE '[45][0-9][0-9]' | head -1) response)" "$evfile"
            return
        fi
    fi

    # MSF fallback
    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "25" ]]; then
            local spool; spool=$(run_msf_module "smtp_relay_${ip//./_}" \
                "auxiliary/scanner/smtp/smtp_relay" \
                RHOSTS "$ip" RPORT "$port" MAILFROM "test@era-test.invalid" \
                MAILTO "relay@era-external.invalid" THREADS 1)
            cp "$spool" "$evfile" 2>/dev/null || true
            if grep -qi "relay.*allowed\|250.*OK\|open relay" "$spool" 2>/dev/null; then
                add_result VULN "$ip" "$port" "smtp" "MSF smtp_relay — open relay confirmed" "$evfile"
            elif grep -qi "relay.*denied\|not permitted\|550\|% complete\|Auxiliary module execution completed" "$spool" 2>/dev/null; then
                add_result SAFE "$ip" "$port" "smtp" "MSF smtp_relay — relay not permitted" "$evfile"
            else
                add_result UNKNOWN "$ip" "$port" "smtp" "MSF probe inconclusive — manual relay test recommended" "$evfile"
            fi
            return
        else
            add_result MANUAL "$ip" "$port" "smtp" \
                "Non-default SMTP port (${port}); MSF smtp_relay rejects RPORT in 6.4+. Check manually: swaks --to probe@era-relay-check.invalid --from relay-check@era-relay-check.invalid --server ${ip} --port ${port} --quit-after RCPT" ""
            return
        fi
    fi

    add_result UNKNOWN "$ip" "$port" "smtp" "swaks and msfconsole unavailable — manual relay test required" ""
}

# =============================================================================
# MRK:07_P_SSRF — PROBE: SSRF → IMDS (PTE) | ssrf,probe,imds,pte,aws | L1149-1223
# NAV-RULE: no-insert-before; read-toc-first
# Tests whether server-side request forgery can reach cloud IMDS at
# 169.254.169.254. Sweeps common SSRF parameter names at root path.
# A positive match requires the response to contain metadata fingerprints.
# UNKNOWN is the expected result — this flags targets for manual follow-up.
# =============================================================================

probe_ssrf_imds() {
    local ip="$1" port="${2:-80}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/ssrf_imds_${SESSION_TS}.txt"
    log "  Probing SSRF→IMDS @ ${ip}:${port} (parameter sweep)"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] curl -sk 'http://${ip}:${port}/?url=http://169.254.169.254/...' (parameter sweep)"; return
    fi

    local proto="http"
    [[ "$port" == "443" || "$port" == "8443" || "$port" == "10443" ]] && proto="https"

    # Try both http and https when the queued port is 80 (common dual-stack host)
    local bases=("${proto}://${ip}:${port}")
    [[ "$proto" == "http" ]] && bases+=("https://${ip}:443")

    local imds_url="http://169.254.169.254/latest/meta-data/"
    # Top-8 most common SSRF parameters — full sweep is a manual/Burp task
    local ssrf_params=("url" "uri" "redirect" "target" "proxy" "callback" "src" "fetch")

    echo "# SSRF→IMDS parameter sweep @ ${ip}:${port} — $(_now)" > "$evfile"
    local vuln_param=""

    for base in "${bases[@]}"; do
    for param in "${ssrf_params[@]}"; do
        local response
        response=$(timeout 3 curl -sk -k --max-time 3 --connect-timeout 3 \
            "${base}/?${param}=${imds_url}" 2>&1 || true)
        # AWS IMDS fingerprints
        if echo "$response" | grep -qiE "ami-id|instance-id|local-ipv4|public-ipv4|iam/security-credentials|placement/"; then
            echo "[HIT] param=${param} → AWS IMDS metadata in response" >> "$evfile"
            echo "$response" >> "$evfile"
            vuln_param="?${param}= (AWS metadata returned)"
            break
        fi
        # GCP metadata fingerprints
        if echo "$response" | grep -qiE "computeMetadata|project-id|instance-id.*gce|gce-project"; then
            echo "[HIT] param=${param} → GCP metadata in response" >> "$evfile"
            echo "$response" >> "$evfile"
            vuln_param="?${param}= (GCP metadata returned)"
            break
        fi
        # Azure IMDS fingerprints
        if echo "$response" | grep -qiE "azEnvironment|subscriptionId.*azure|vmId.*azure"; then
            echo "[HIT] param=${param} → Azure metadata in response" >> "$evfile"
            echo "$response" >> "$evfile"
            vuln_param="?${param}= (Azure metadata returned)"
            break
        fi
        # 169.254 IP appearing in response body (indirect confirmation)
        if echo "$response" | grep -qP '169\.254\.169\.254'; then
            echo "[PARTIAL] param=${param} → 169.254.169.254 reflected in response" >> "$evfile"
        fi
    done   # param loop
    [[ -n "$vuln_param" ]] && break
    done   # base loop

    if [[ -n "$vuln_param" ]]; then
        add_result VULN "$ip" "$port" "ssrf" "SSRF→IMDS confirmed via ${vuln_param}" "$evfile"
    else
        echo "[no IMDS fingerprint returned by parameter sweep]" >> "$evfile"
        add_result MANUAL "$ip" "$port" "ssrf" "Quick SSRF sweep (8 params) — no IMDS hit. Full test requires Burp with app context (authenticated, POST params, headers)." "$evfile"
    fi
}

# =============================================================================
# MRK:07_P_TLS — PROBE: TLS CERT VALIDITY | tls,probe,cert,validity,expiry | L1224-1289
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_tls_cert() {
    local ip="$1" port="${2:-443}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/tls_cert_${port}_${SESSION_TS}.txt"
    log "  Probing TLS cert @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] openssl s_client -connect ${ip}:${port}"; return
    fi

    have openssl || { add_result MANUAL "$ip" "$port" "tls" "openssl not available — manual cert check required" ""; return; }

    local cert_text
    cert_text=$(echo | timeout "${PROBE_TIMEOUT}" openssl s_client \
        -connect "${ip}:${port}" -servername "$ip" \
        -no_tls1 -no_ssl3 2>/dev/null | \
        openssl x509 -noout -text -dates -subject -issuer 2>/dev/null || true)

    echo "# TLS cert @ ${ip}:${port} — $(_now)" > "$evfile"
    echo "$cert_text" >> "$evfile"

    if [[ -z "$cert_text" ]]; then
        add_result UNKNOWN "$ip" "$port" "tls" "No TLS cert returned — port may not be TLS or host unreachable" "$evfile"
        return
    fi

    # Self-signed check: issuer == subject
    local subj issuer
    subj=$(echo "$cert_text" | grep -m1 'Subject:' | sed 's/.*Subject://')
    issuer=$(echo "$cert_text" | grep -m1 'Issuer:'  | sed 's/.*Issuer://')

    local issues=()
    [[ "$subj" == "$issuer" ]] && issues+=("self-signed certificate")

    # Expiry
    local not_after
    not_after=$(echo | timeout "${PROBE_TIMEOUT}" openssl s_client \
        -connect "${ip}:${port}" 2>/dev/null | \
        openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || true)
    if [[ -n "$not_after" ]]; then
        local exp_epoch; exp_epoch=$(date -d "$not_after" +%s 2>/dev/null || true)
        local now_epoch; now_epoch=$(date +%s)
        if [[ -n "$exp_epoch" ]] && [[ "$exp_epoch" -lt "$now_epoch" ]]; then
            issues+=("expired (${not_after})")
        elif [[ -n "$exp_epoch" ]]; then
            local days_left=$(( (exp_epoch - now_epoch) / 86400 ))
            [[ "$days_left" -lt 30 ]] && issues+=("expiring in ${days_left} days (${not_after})")
        fi
    fi

    # Weak signature algorithm
    echo "$cert_text" | grep -qi "sha1WithRSA\|md5WithRSA\|sha1With" && \
        issues+=("weak signature algorithm (SHA1/MD5)")

    if [[ "${#issues[@]}" -gt 0 ]]; then
        add_result VULN "$ip" "$port" "tls" "TLS cert issue(s): $(IFS=', '; echo "${issues[*]}")" "$evfile"
    else
        add_result SAFE "$ip" "$port" "tls" "Certificate valid, not self-signed, not expired" "$evfile"
    fi
}

# =============================================================================
# MRK:07_P_WEBH — PROBE: HTTP SECURITY HEADERS | webh,probe,http,security,headers | L1290-1337
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

probe_web_headers() {
    local ip="$1" port="${2:-80}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/web_headers_${port}_${SESSION_TS}.txt"
    log "  Probing HTTP security headers @ ${ip}:${port}"

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log "  [DRY RUN] curl -Isk http://${ip}:${port}/"; return
    fi

    have curl || { add_result MANUAL "$ip" "$port" "http-headers" "curl not available" ""; return; }

    local proto="http"
    [[ "$port" == "443" || "$port" == "8443" ]] && proto="https"

    local headers
    headers=$(timeout "${PROBE_TIMEOUT}" curl -Isk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" \
        "${proto}://${ip}:${port}/" 2>&1 || true)

    echo "# HTTP headers @ ${ip}:${port} — $(_now)" > "$evfile"
    echo "$headers" >> "$evfile"

    if [[ -z "$headers" ]]; then
        add_result UNKNOWN "$ip" "$port" "http-headers" "No HTTP response — port may not serve HTTP" "$evfile"
        return
    fi

    local missing=()
    echo "$headers" | grep -qi "Strict-Transport-Security" || missing+=("HSTS")
    echo "$headers" | grep -qi "X-Frame-Options\|Content-Security-Policy.*frame" || missing+=("X-Frame-Options")
    echo "$headers" | grep -qi "Content-Security-Policy" || missing+=("CSP")
    echo "$headers" | grep -qi "X-Content-Type-Options" || missing+=("X-Content-Type-Options")
    echo "$headers" | grep -qi "Referrer-Policy" || missing+=("Referrer-Policy")

    if [[ "${#missing[@]}" -gt 0 ]]; then
        add_result VULN "$ip" "$port" "http-headers" \
            "Missing security headers: $(IFS=', '; echo "${missing[*]}")" "$evfile"
    else
        add_result SAFE "$ip" "$port" "http-headers" "All checked security headers present" "$evfile"
    fi
}

# =============================================================================
# MRK:07_ENUM — POST-VULN ENUMERATION | enum,post,vuln,enumeration,redis | L1338-1509
# NAV-RULE: no-insert-before; read-toc-first
# Called after NOAUTH is confirmed; appends to evfile.
# =============================================================================

enumerate_redis_vuln() {
    local ip="$1" port="$2" evfile="$3"
    [[ "${MSF_ONLY}" -eq 1 ]] && return
    have redis-cli || return
    log "    [enum] Redis — collecting INFO / CONFIG / KEYS"
    {
        echo ""
        echo "# === Post-VULN Redis enumeration @ ${ip}:${port} ==="
        echo "# INFO server"
        timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" --no-auth-warning \
            INFO server 2>&1 || true
        echo ""
        echo "# INFO keyspace"
        timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" --no-auth-warning \
            INFO keyspace 2>&1 || true
        echo ""
        echo "# DBSIZE"
        timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" --no-auth-warning \
            DBSIZE 2>&1 || true
        echo ""
        echo "# CONFIG GET * (first 60 lines)"
        timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" --no-auth-warning \
            CONFIG GET '*' 2>&1 | head -60 || true
        echo ""
        echo "# KEYS * (first 20)"
        timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" --no-auth-warning \
            KEYS '*' 2>&1 | head -20 || true
        echo ""
        echo "# CLIENT LIST (first 10)"
        timeout "${PROBE_TIMEOUT}" redis-cli -h "$ip" -p "$port" --no-auth-warning \
            CLIENT LIST 2>&1 | head -10 || true
    } >> "$evfile"
}

enumerate_mysql_vuln() {
    local ip="$1" port="$2" evfile="$3"
    [[ "${MSF_ONLY}" -eq 1 ]] && return
    have mysql || return
    log "    [enum] MySQL — collecting databases / users / schema stats"
    local mc=(mysql -h "$ip" -P "$port" -u '' \
        --connect-timeout="${CONNECT_TIMEOUT}" --skip-ssl -N -s)

    # ── version / server info ──────────────────────────────────────────────────
    local ver_out
    ver_out=$(timeout "${PROBE_TIMEOUT}" "${mc[@]}" \
        -e "SELECT CONCAT(@@version,' / ',@@hostname,' / datadir=',@@datadir);" 2>&1 || true)
    {
        echo ""
        echo "# === Post-VULN MySQL enumeration @ ${ip}:${port} — $(_now) ==="
        echo "# Version / hostname / datadir"
        echo "$ver_out"
    } >> "$evfile"
    [[ -n "$ver_out" ]] && log "    [enum]   version: ${ver_out}"

    # ── databases ──────────────────────────────────────────────────────────────
    local dbs_out
    dbs_out=$(timeout "${PROBE_TIMEOUT}" "${mc[@]}" -e "SHOW DATABASES;" 2>&1 || true)
    { echo ""; echo "# SHOW DATABASES"; echo "$dbs_out"; } >> "$evfile"
    local db_list; db_list=$(echo "$dbs_out" | grep -v "^$" | tr '\n' ' ' | sed 's/ $//')
    [[ -n "$db_list" ]] && log "    [enum]   databases: ${db_list}"

    # ── user accounts ──────────────────────────────────────────────────────────
    local users_out
    users_out=$(timeout "${PROBE_TIMEOUT}" "${mc[@]}" \
        -e "SELECT CONCAT(user,'@',host,' plugin=',plugin,
            ' pwd=',IF(authentication_string!='','yes','no'))
            FROM mysql.user ORDER BY user;" 2>&1 || true)
    { echo ""; echo "# User accounts"; echo "$users_out"; } >> "$evfile"
    if [[ -n "$users_out" ]] && ! echo "$users_out" | grep -qi "access denied\|error"; then
        local u_count; u_count=$(echo "$users_out" | grep -c . || true)
        log "    [enum]   users (${u_count} rows): $(echo "$users_out" | head -5 | tr '\n' ' ')"
    fi

    # ── grants ─────────────────────────────────────────────────────────────────
    local grants_out
    grants_out=$(timeout "${PROBE_TIMEOUT}" "${mc[@]}" -e "SHOW GRANTS;" 2>&1 || true)
    { echo ""; echo "# SHOW GRANTS"; echo "$grants_out"; } >> "$evfile"
    [[ -n "$grants_out" ]] && log "    [enum]   grants: $(echo "$grants_out" | head -3 | tr '\n' ' ')"

    # ── table counts per schema ────────────────────────────────────────────────
    local tables_out
    tables_out=$(timeout "${PROBE_TIMEOUT}" "${mc[@]}" \
        -e "SELECT CONCAT(table_schema,': ',COUNT(*),' tables')
            FROM information_schema.tables
            WHERE table_schema NOT IN
                ('information_schema','performance_schema','sys')
            GROUP BY table_schema ORDER BY COUNT(*) DESC;" 2>&1 || true)
    { echo ""; echo "# Table counts per schema"; echo "$tables_out"; } >> "$evfile"
    [[ -n "$tables_out" ]] && log "    [enum]   schema/tables: $(echo "$tables_out" | tr '\n' ' ')"

    # ── MSF cross-check ────────────────────────────────────────────────────────
    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole && [[ "$port" == "3306" ]]; then
        log "    [enum] MySQL — MSF mysql_sql cross-check"
        run_msf_module "mysql_sql_${ip//./_}" \
            "auxiliary/scanner/mysql/mysql_sql" \
            RHOSTS "$ip" RPORT "$port" \
            USERNAME "" PASSWORD "" SQL "show databases" THREADS 1 >/dev/null || true
    fi
}

enumerate_postgres_vuln() {
    local ip="$1" port="$2" evfile="$3"
    [[ "${MSF_ONLY}" -eq 1 ]] && return
    have psql || return
    log "    [enum] PostgreSQL — collecting databases / roles / tables"
    local pc=(psql -h "$ip" -p "$port" -U postgres)
    local pe=(env PGPASSWORD="" PGCONNECT_TIMEOUT="${CONNECT_TIMEOUT}")
    {
        echo ""
        echo "# === Post-VULN PostgreSQL enumeration @ ${ip}:${port} ==="
        echo "# Version / server address"
        "${pe[@]}" timeout "${PROBE_TIMEOUT}" "${pc[@]}" \
            -c "SELECT version(), inet_server_addr();" 2>&1 || true
        echo ""
        echo "# Database list"
        "${pe[@]}" timeout "${PROBE_TIMEOUT}" "${pc[@]}" -c "\l" 2>&1 || true
        echo ""
        echo "# Roles (superuser first)"
        "${pe[@]}" timeout "${PROBE_TIMEOUT}" "${pc[@]}" \
            -c "SELECT rolname, rolsuper, rolcanlogin, rolcreaterole \
                FROM pg_roles ORDER BY rolsuper DESC, rolcanlogin DESC;" 2>&1 || true
        echo ""
        echo "# Tables in public schema"
        "${pe[@]}" timeout "${PROBE_TIMEOUT}" "${pc[@]}" -c "\dt public.*" 2>&1 || true
        echo ""
        echo "# Config paths"
        "${pe[@]}" timeout "${PROBE_TIMEOUT}" "${pc[@]}" \
            -c "SHOW hba_file; SHOW data_directory; SHOW config_file;" 2>&1 || true
    } >> "$evfile"
}

enumerate_mongodb_vuln() {
    local ip="$1" port="$2" evfile="$3" mongo_bin="$4"
    log "    [enum] MongoDB — collecting databases / collections / server info"
    {
        echo ""
        echo "# === Post-VULN MongoDB enumeration @ ${ip}:${port} ==="
        echo "# listDatabases"
        timeout "${PROBE_TIMEOUT}" "$mongo_bin" "${ip}:${port}/admin" \
            --eval "printjson(db.adminCommand({listDatabases:1}))" \
            --quiet --norc 2>&1 | head -60 || true
        echo ""
        echo "# buildInfo (version)"
        timeout "${PROBE_TIMEOUT}" "$mongo_bin" "${ip}:${port}/admin" \
            --eval "printjson(db.adminCommand({buildInfo:1}))" \
            --quiet --norc 2>&1 | grep -E '"version"|sysInfo' || true
        echo ""
        echo "# Collections per database"
        timeout "${PROBE_TIMEOUT}" "$mongo_bin" "${ip}:${port}/admin" \
            --eval 'db.adminCommand({listDatabases:1}).databases.forEach(
                function(d){
                    print("DB: "+d.name);
                    var c=db.getSiblingDB(d.name);
                    c.getCollectionNames().forEach(function(n){print("  "+n);});
                })' \
            --quiet --norc 2>&1 | head -60 || true
    } >> "$evfile"
    # MSF cross-check
    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole && [[ "$port" == "27017" ]]; then
        log "    [enum] MongoDB — MSF mongodb_login cross-check"
        run_msf_module "mongo_enum_${ip//./_}" \
            "auxiliary/scanner/mongodb/mongodb_login" \
            RHOSTS "$ip" RPORT "$port" THREADS 1 >/dev/null || true
    fi
}

# =============================================================================
# MRK:07_P_MSSQL — PROBE: MSSQL | mssql,probe,unauthenticated,sa,empty | L1510-1556
# NAV-RULE: no-insert-before; read-toc-first
# NOTE: MSF mssql_ping + mssql_login RPORT confirmed bad (MSF 6.4+) — action-plan.
# =============================================================================
probe_mssql() {
    local ip="$1" port="${2:-1433}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/mssql_${port}_${SESSION_TS}.txt"
    log "  Probing MSSQL @ ${ip}:${port}"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] mssqlclient / MSF mssql_ping + mssql_login"; return; }
    echo "# MSSQL probe @ ${ip}:${port} — $(_now)" > "$evfile"
    # FIX 2026-04-20: mssql_ping + mssql_login reject RPORT in MSF 6.4+ — silently probe default 1433.
    # Only call MSF when probe port IS 1433 (then module default matches). For any other port,
    # fall through to MANUAL — there is no reliable alternative without mssqlclient installed.
    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole && [[ "$port" == "1433" ]]; then
        local spool; spool=$(run_msf_module "mssql_${ip//./_}" \
            "auxiliary/scanner/mssql/mssql_ping" RHOSTS "$ip" THREADS 1)
        cat "$spool" >> "$evfile" 2>/dev/null || true
        if grep -qi "SQL Server\|mssql\|ServerName" "$spool" 2>/dev/null; then
            # Try login
            local spool2; spool2=$(run_msf_module "mssql_login_${ip//./_}" \
                "auxiliary/scanner/mssql/mssql_login" \
                RHOSTS "$ip" \
                USERNAME "sa" PASSWORD "" BLANK_PASSWORDS true \
                STOP_ON_SUCCESS true THREADS 1)
            cat "$spool2" >> "$evfile" 2>/dev/null || true
            if grep -qi "Login Successful\|logged in\|success" "$spool2" 2>/dev/null; then
                add_result VULN "$ip" "$port" "mssql" \
                    "NOAUTH — SA empty password accepted; unauthenticated MSSQL access" "$evfile"
                return
            else
                add_result SAFE "$ip" "$port" "mssql" \
                    "MSSQL detected — SA login rejected" "$evfile"
                return
            fi
        fi
        add_result UNKNOWN "$ip" "$port" "mssql" "MSF ping inconclusive — manual check required" "$evfile"
        return
    elif [[ "${NO_MSF}" -eq 0 ]] && have msfconsole && [[ "$port" != "1433" ]]; then
        add_result MANUAL "$ip" "$port" "mssql" \
            "Non-default MSSQL port (${port}); MSF mssql_ping/mssql_login reject RPORT in 6.4+ so cannot target ${port}. Check manually with mssqlclient.py or impacket-mssqlclient -port ${port}." ""
        return
    fi
    add_result MANUAL "$ip" "$port" "mssql" "msfconsole unavailable — install and run auxiliary/scanner/mssql/mssql_login (default port 1433)" ""
}

# =============================================================================
# MRK:07_P_NFS — PROBE: NFS | nfs,probe,showmount,world,accessible | L1557-1595
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
probe_nfs() {
    local ip="$1" port="${2:-2049}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/nfs_${SESSION_TS}.txt"
    log "  Probing NFS exports @ ${ip}"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] showmount -e ${ip}"; return; }
    echo "# NFS showmount @ ${ip} — $(_now)" > "$evfile"
    if have showmount; then
        local exports; exports=$(timeout "${PROBE_TIMEOUT}" showmount -e "$ip" 2>&1 || true)
        echo "$exports" >> "$evfile"
        if echo "$exports" | grep -qE "Export list|/[^ ]"; then
            # Check for world-accessible exports (everyone / * / 0.0.0.0)
            if echo "$exports" | grep -qE "\*|everyone|0\.0\.0\.0"; then
                add_result VULN "$ip" "$port" "nfs" \
                    "World-accessible NFS export detected — see evidence for export list" "$evfile"
            else
                add_result VULN "$ip" "$port" "nfs" \
                    "NFS exports visible — review access controls; world-accessible check inconclusive" "$evfile"
            fi
            return
        elif echo "$exports" | grep -qi "refused\|timeout\|not respond"; then
            add_result UNKNOWN "$ip" "$port" "nfs" "NFS port open but showmount rejected — rpcbind filtered?" "$evfile"
            return
        fi
    fi
    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        local spool; spool=$(run_msf_module "nfs_${ip//./_}" \
            "auxiliary/scanner/nfs/nfsmount" RHOSTS "$ip" THREADS 1)
        cat "$spool" >> "$evfile" 2>/dev/null || true
        grep -qi "NFS export\|mount\|/" "$spool" 2>/dev/null && \
            add_result VULN "$ip" "$port" "nfs" "MSF nfsmount — exports found" "$evfile" && return
    fi
    add_result MANUAL "$ip" "$port" "nfs" "showmount and msfconsole unavailable" ""
}

# =============================================================================
# MRK:07_P_TELNET — PROBE: Telnet | telnet,probe,banner,grab,cleartext | L1596-1626
# NAV-RULE: no-insert-before
# =============================================================================
probe_telnet() {
    local ip="$1" port="${2:-23}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/telnet_${port}_${SESSION_TS}.txt"
    log "  Probing Telnet @ ${ip}:${port}"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] nc -w5 ${ip} ${port}"; return; }
    echo "# Telnet banner @ ${ip}:${port} — $(_now)" > "$evfile"
    local banner=""
    have nc && banner=$(timeout 5 nc -w5 "$ip" "$port" 2>/dev/null | head -5 | strings || true)
    echo "$banner" >> "$evfile"
    if [[ -n "$banner" ]]; then
        add_result VULN "$ip" "$port" "telnet" \
            "Telnet service responding — cleartext protocol; banner: $(echo "$banner" | head -1 | tr -d '\r')" "$evfile"
    else
        # MSF fallback
        if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
            if [[ "$port" == "23" ]]; then
                local spool; spool=$(run_msf_module "telnet_${ip//./_}" \
                    "auxiliary/scanner/telnet/telnet_version" \
                    RHOSTS "$ip" RPORT "$port" THREADS 1)
                cat "$spool" >> "$evfile" 2>/dev/null || true
                grep -qi "Telnet\|login\|banner" "$spool" 2>/dev/null && \
                    add_result VULN "$ip" "$port" "telnet" "MSF telnet_version — service confirmed" "$evfile" && return
            else
                add_result MANUAL "$ip" "$port" "telnet" \
                    "Non-default Telnet port (${port}); MSF telnet_version rejects RPORT in 6.4+. Check manually: nc -w5 ${ip} ${port}" "$evfile"
                return
            fi
        fi
        add_result UNKNOWN "$ip" "$port" "telnet" "No banner received — port filtered or not Telnet" "$evfile"
    fi
}

# =============================================================================
# MRK:07_P_IPMI — PROBE: IPMI | ipmi,probe,version,cipher,zero | L1627-1675
# NAV-RULE: no-insert-before; read-toc-first
# Cipher-zero allows authentication bypass on most IPMI 2.0 implementations.
# =============================================================================
probe_ipmi() {
    local ip="$1" port="${2:-623}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/ipmi_${SESSION_TS}.txt"
    log "  Probing IPMI @ ${ip}:${port} (cipher-zero + default creds)"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] MSF ipmi_version + ipmi_cipher_zero"; return; }
    echo "# IPMI probe @ ${ip}:${port} — $(_now)" > "$evfile"
    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "623" ]]; then
            # Version detection
            local spool_ver; spool_ver=$(run_msf_module "ipmi_ver_${ip//./_}" \
                "auxiliary/scanner/ipmi/ipmi_version" \
                RHOSTS "$ip" RPORT "$port" THREADS 1)
            cat "$spool_ver" >> "$evfile" 2>/dev/null || true
            # Cipher-zero (auth bypass — highest priority IPMI finding)
            local spool_cz; spool_cz=$(run_msf_module "ipmi_cz_${ip//./_}" \
                "auxiliary/scanner/ipmi/ipmi_cipher_zero" \
                RHOSTS "$ip" RPORT "$port" THREADS 1)
            cat "$spool_cz" >> "$evfile" 2>/dev/null || true
            if grep -qi "cipher zero\|Authentication Bypass\|VULNERABLE\|authentication type.*none" \
                    "$spool_cz" 2>/dev/null; then
                add_result VULN "$ip" "$port" "ipmi" \
                    "IPMI Cipher-Zero auth bypass confirmed — unauthenticated access possible" "$evfile"
                return
            fi
            # Hash dump (RAKP — offline crack target)
            local spool_hash; spool_hash=$(run_msf_module "ipmi_hash_${ip//./_}" \
                "auxiliary/scanner/ipmi/ipmi_dumphashes" \
                RHOSTS "$ip" RPORT "$port" \
                OUTPUT_HASHCAT_FILE "${evfile}.hashes" THREADS 1)
            cat "$spool_hash" >> "$evfile" 2>/dev/null || true
            if grep -qi "hash\|HMAC-MD5\|HMAC-SHA1" "$spool_hash" 2>/dev/null; then
                add_result VULN "$ip" "$port" "ipmi" \
                    "IPMI RAKP hash captured — offline crackable; see evidence for hash file" "$evfile"
                return
            fi
            if grep -qi "IPMI\|version\|BMC" "$spool_ver" 2>/dev/null; then
                add_result UNKNOWN "$ip" "$port" "ipmi" \
                    "IPMI service detected — cipher-zero not confirmed; manual verification recommended" "$evfile"
                return
            fi
        else
            add_result MANUAL "$ip" "$port" "ipmi" \
                "Non-default IPMI port (${port}); MSF IPMI modules reject RPORT in 6.4+. Check manually with ipmitool -H ${ip} -p ${port} -I lanplus" ""
            return
        fi
    fi
    add_result MANUAL "$ip" "$port" "ipmi" "msfconsole unavailable — install MSF for IPMI cipher-zero check" ""
}

# =============================================================================
# MRK:07_P_RDP — PROBE: RDP | rdp,probe,nla,check,encryption | L1676-1713
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
probe_rdp() {
    local ip="$1" port="${2:-3389}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/rdp_${port}_${SESSION_TS}.txt"
    log "  Probing RDP @ ${ip}:${port} (NLA + encryption)"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] MSF rdp_scanner + nmap rdp-enum-encryption"; return; }
    echo "# RDP probe @ ${ip}:${port} — $(_now)" > "$evfile"
    # nmap rdp script (fast, no auth)
    if have nmap; then
        local nmap_out; nmap_out=$(timeout "${PROBE_TIMEOUT}" nmap -sV -p "$port" \
            --script rdp-enum-encryption --open -Pn "$ip" 2>&1 || true)
        echo "$nmap_out" >> "$evfile"
        if echo "$nmap_out" | grep -qi "CredSSP.*NLA\|NLA.*enabled\|Security.*NLA"; then
            add_result SAFE "$ip" "$port" "rdp" \
                "RDP NLA enforced — pre-auth credential required" "$evfile"
            return
        elif echo "$nmap_out" | grep -qi "Classic RDP\|Encryption.*40\|Encryption.*56\|RC4"; then
            add_result VULN "$ip" "$port" "rdp" \
                "RDP weak encryption / NLA not enforced — classic RDP mode detected" "$evfile"
            return
        fi
    fi
    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "3389" ]]; then
            local spool; spool=$(run_msf_module "rdp_${ip//./_}" \
                "auxiliary/scanner/rdp/rdp_scanner" \
                RHOSTS "$ip" RPORT "$port" THREADS 1)
            cat "$spool" >> "$evfile" 2>/dev/null || true
            grep -qi "RDP\|Remote Desktop\|3389\|% complete" "$spool" 2>/dev/null && \
                add_result MANUAL "$ip" "$port" "rdp" \
                    "RDP service confirmed — NLA status requires manual check; verify with xfreerdp or Nessus rdp plugin" "$evfile" && return
        else
            add_result MANUAL "$ip" "$port" "rdp" \
                "Non-default RDP port (${port}); MSF rdp_scanner rejects RPORT in 6.4+. Check manually: nmap -sV -p ${port} --script rdp-enum-encryption -Pn ${ip}" "$evfile"
            return
        fi
    fi
    add_result MANUAL "$ip" "$port" "rdp" "RDP port open — NLA status inconclusive; manual check required" "$evfile"
}

# =============================================================================
# MRK:07_P_WINRM — PROBE: WinRM | winrm,probe,auth,exposure,check | L1714-1758
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
probe_winrm() {
    local ip="$1" port="${2:-5985}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/winrm_${port}_${SESSION_TS}.txt"
    log "  Probing WinRM @ ${ip}:${port}"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] curl http://${ip}:${port}/wsman"; return; }
    echo "# WinRM probe @ ${ip}:${port} — $(_now)" > "$evfile"
    local proto="http"; [[ "$port" == "5986" ]] && proto="https"
    if have curl; then
        local resp; resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
            --connect-timeout "${CONNECT_TIMEOUT}" \
            "${proto}://${ip}:${port}/wsman" 2>&1 || true)
        echo "$resp" >> "$evfile"
        if echo "$resp" | grep -qi "WSManFault\|wsman\|SOAP"; then
            add_result VULN "$ip" "$port" "winrm" \
                "WinRM endpoint responding — accessible without credentials; test with evil-winrm if creds available" "$evfile"
            return
        elif echo "$resp" | grep -qi "Unauthorized\|401"; then
            add_result SAFE "$ip" "$port" "winrm" "WinRM requires authentication (401)" "$evfile"
            return
        fi
    fi
    if [[ "${NO_MSF}" -eq 0 ]] && have msfconsole; then
        if [[ "$port" == "5985" || "$port" == "5986" ]]; then
            local spool; spool=$(run_msf_module "winrm_${ip//./_}" \
                "auxiliary/scanner/winrm/winrm_auth_methods" \
                RHOSTS "$ip" RPORT "$port" THREADS 1)
            cat "$spool" >> "$evfile" 2>/dev/null || true
            if grep -qi "None\|Auth Methods:.*None" "$spool" 2>/dev/null; then
                add_result VULN "$ip" "$port" "winrm" "MSF winrm_auth_methods — None auth advertised; no credentials required" "$evfile"
            elif grep -qi "Negotiate\|Kerberos\|Basic\|CredSSP\|Auth Methods" "$spool" 2>/dev/null; then
                add_result SAFE "$ip" "$port" "winrm" "WinRM requires authentication" "$evfile"
            elif grep -qi "% complete" "$spool" 2>/dev/null; then
                add_result SAFE "$ip" "$port" "winrm" "WinRM probe complete — no auth methods returned (likely filtered)" "$evfile"
            else
                add_result UNKNOWN "$ip" "$port" "winrm" "WinRM port open — response inconclusive" "$evfile"
            fi
            return
        else
            add_result MANUAL "$ip" "$port" "winrm" \
                "Non-default WinRM port (${port}); MSF winrm_auth_methods rejects RPORT in 6.4+. Check manually: curl -sk http://${ip}:${port}/wsman" "$evfile"
            return
        fi
    fi
    add_result UNKNOWN "$ip" "$port" "winrm" "WinRM port open — curl inconclusive, msfconsole unavailable" "$evfile"
}

# =============================================================================
# MRK:07_P_WEBGEN — PROBE: Web generic | webgen,probe,web,generic,banner | L1759-1842
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
probe_web_generic() {
    local ip="$1" port="${2:-80}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/web_generic_${port}_${SESSION_TS}.txt"
    log "  Probing web generic @ ${ip}:${port} (headers/banner/default)"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] curl -Isk http://${ip}:${port}/"; return; }
    have curl || { add_result MANUAL "$ip" "$port" "web" "curl not available" ""; return; }

    local proto="http"; [[ "$port" == "443" || "$port" == "8443" || "$port" == "4443" || "$port" == "10443" ]] && proto="https"
    local base="${proto}://${ip}:${port}"

    echo "# Web generic probe @ ${ip}:${port} — $(_now)" > "$evfile"

    local headers; headers=$(timeout "${PROBE_TIMEOUT}" curl -Isk -k --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "${base}/" 2>&1 || true)
    # For port 8080 try https if http got nothing (some services run TLS on 8080)
    if [[ -z "$headers" && "$proto" == "http" && "$port" == "8080" ]]; then
        headers=$(timeout "${PROBE_TIMEOUT}" curl -Isk -k --max-time "${PROBE_TIMEOUT}" \
            --connect-timeout "${CONNECT_TIMEOUT}" "https://${ip}:${port}/" 2>&1 || true)
        [[ -n "$headers" ]] && base="https://${ip}:${port}" && proto="https"
    fi
    echo "=== HEAD ===" >> "$evfile"; echo "$headers" >> "$evfile"

    if [[ -z "$headers" ]]; then
        add_result SAFE "$ip" "$port" "web" "No HTTP response — port closed or filtered at time of probe" "$evfile"
        return
    fi

    local issues=() info=()

    # Version disclosure in Server / X-Powered-By
    local server; server=$(echo "$headers" | grep -i "^Server:" | head -1)
    local xpb; xpb=$(echo "$headers" | grep -i "^X-Powered-By:" | head -1)
    echo "$server" | grep -qiP 'Apache/[0-9]|nginx/[0-9]|IIS/[0-9]|OpenSSL/[0-9]|PHP/[0-9]' && \
        issues+=("Server version disclosed: ${server}")
    [[ -n "$xpb" ]] && issues+=("X-Powered-By disclosed: ${xpb}")

    # Missing security headers
    local missing_h=()
    echo "$headers" | grep -qi "Strict-Transport-Security" || { [[ "$proto" == "https" ]] && missing_h+=("HSTS"); }
    echo "$headers" | grep -qi "X-Frame-Options\|Content-Security-Policy.*frame" || missing_h+=("X-Frame-Options")
    echo "$headers" | grep -qi "X-Content-Type-Options" || missing_h+=("X-Content-Type-Options")
    echo "$headers" | grep -qi "Content-Security-Policy" || missing_h+=("CSP")
    [[ "${#missing_h[@]}" -gt 0 ]] && issues+=("Missing headers: $(IFS=', '; echo "${missing_h[*]}")")

    # HTTP→HTTPS redirect (only on port 80)
    if [[ "$proto" == "http" && "$port" == "80" ]]; then
        echo "$headers" | grep -qi "Location:.*https://" || issues+=("No HTTP→HTTPS redirect on port 80")
    fi

    # Default/error pages (grab body for fingerprint)
    local body; body=$(timeout "${PROBE_TIMEOUT}" curl -sk -k --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "${base}/" 2>&1 | head -60 || true)
    echo "=== BODY (first 60 lines) ===" >> "$evfile"; echo "$body" >> "$evfile"
    echo "$body" | grep -qi "Welcome to nginx\|Apache.*Test Page\|IIS Windows Server\|It works!" && \
        issues+=("Default web server page exposed — no application configured")

    # CORS misconfiguration
    local cors; cors=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time 5 -I \
        -H "Origin: https://evil-era-test.invalid" "${base}/" 2>&1 || true)
    echo "=== CORS check ===" >> "$evfile"; echo "$cors" >> "$evfile"
    echo "$cors" | grep -qi "Access-Control-Allow-Origin: \*\|Access-Control-Allow-Origin: https://evil" && \
        issues+=("CORS misconfigured — wildcard or reflected origin")

    # robots.txt / sitemap
    local robots; robots=$(timeout 5 curl -sk --max-time 5 "${base}/robots.txt" 2>&1 || true)
    [[ -n "$robots" ]] && ! echo "$robots" | grep -qi "404\|not found" && {
        info+=("robots.txt present")
        echo "=== robots.txt ===" >> "$evfile"; echo "$robots" >> "$evfile"
    }

    # Sensitive file exposure check (CWE-538 / CWE-312)
    # These files can leak credentials, source code, database dumps, or internal paths
    local sens_paths=(".env" ".git/HEAD" ".gitignore" "phpinfo.php" "info.php"
                      "backup.sql" "db.sql" "database.sql" "config.php.bak"
                      "wp-config.php.bak" ".htpasswd" "web.config.bak" ".DS_Store"
                      "composer.json" "package.json" "Dockerfile" ".dockerenv")
    local sens_found=()
    echo "=== Sensitive file probes ===" >> "$evfile"
    for sf in "${sens_paths[@]}"; do
        local sf_code
        sf_code=$(timeout 4 curl -sk --max-time 4 --connect-timeout 3 -o /dev/null \
            -w "%{http_code}" "${base}/${sf}" 2>/dev/null || echo "000")
        if [[ "$sf_code" == "200" || "$sf_code" == "301" || "$sf_code" == "302" ]]; then
            sens_found+=("/${sf}(${sf_code})")
            echo "  [HIT ${sf_code}] ${sf}" >> "$evfile"
            log_warn "    SENSITIVE FILE: ${base}/${sf} returned HTTP ${sf_code}"
        fi
    done
    [[ ${#sens_found[@]} -gt 0 ]] && issues+=("Sensitive files exposed: $(IFS=', '; echo "${sens_found[*]}")")

    # CVE-2024-4577: PHP CGI argument injection on Windows IIS+PHP-CGI configurations
    # Check presence of PHP-CGI paths; exploitation requires manual confirmation (Windows only)
    local php_cgi_paths=("/cgi-bin/php" "/cgi-bin/php.cgi" "/cgi-bin/php-cgi.exe" "/php-cgi/php")
    echo "=== PHP CGI path check (CVE-2024-4577) ===" >> "$evfile"
    for phppath in "${php_cgi_paths[@]}"; do
        local php_code
        php_code=$(timeout 4 curl -sk --max-time 4 --connect-timeout 3 -o /dev/null \
            -w "%{http_code}" "${base}${phppath}" 2>/dev/null || echo "000")
        if [[ "$php_code" != "404" && "$php_code" != "000" && "$php_code" != "403" ]]; then
            echo "  [HIT ${php_code}] ${phppath}" >> "$evfile"
            issues+=("CVE-2024-4577 candidate — PHP CGI path ${phppath} accessible (HTTP ${php_code}); Windows PHP-CGI argument injection — manual verification required")
            log_warn "    CVE-2024-4577 candidate: ${base}${phppath} returned ${php_code}"
            break
        fi
    done

    if [[ "${#issues[@]}" -gt 0 ]]; then
        add_result VULN "$ip" "$port" "web" \
            "Web issues: $(IFS=' | '; echo "${issues[*]}")" "$evfile"
    else
        add_result SAFE "$ip" "$port" "web" \
            "No major web misconfigs detected${info[*]:+ — info: $(IFS=', '; echo "${info[*]}")}" "$evfile"
    fi
}

# =============================================================================
# VAPT-ADDED: PROBE: ELASTICSEARCH/OPENSEARCH NO-AUTH | elasticsearch,9200,noauth,cwe306
# CVE: Unauthenticated Elasticsearch/OpenSearch access — CWE-306 Missing Authentication
# Description: ES/OS without X-Pack Security allows unauthenticated read/write to all
# indices. Pre-ES 6.8/7.1 had no security by default. Exposes PII, credentials, app data.
# Remediation: Enable X-Pack Security or OpenSearch Security plugin; restrict 9200/9300.
# =============================================================================
probe_elasticsearch() {
    local ip="$1" port="${2:-9200}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/elasticsearch_noauth_${SESSION_TS}.txt"
    log "  Probing Elasticsearch/OpenSearch NOAUTH @ ${ip}:${port}"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] curl http://${ip}:${port}/_cat/indices"; return; }
    have curl || { add_result MANUAL "$ip" "$port" "elasticsearch" "curl not available" ""; return; }

    echo "# Elasticsearch/OpenSearch NOAUTH @ ${ip}:${port} — $(_now)" > "$evfile"
    echo "# CVE: CWE-306 — Missing Authentication for Critical Function" >> "$evfile"
    echo "" >> "$evfile"

    local root_resp
    root_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "http://${ip}:${port}/" 2>&1 || true)
    echo "=== GET / ===" >> "$evfile"; echo "$root_resp" >> "$evfile"; echo "" >> "$evfile"

    if ! echo "$root_resp" | grep -qiE '"version".*"number"|elasticsearch|opensearch'; then
        add_result UNKNOWN "$ip" "$port" "elasticsearch" "Port ${port} open — no Elasticsearch/OpenSearch fingerprint" "$evfile"
        return
    fi

    local es_ver; es_ver=$(echo "$root_resp" | grep -oP '"number"\s*:\s*"\K[^"]+' | head -1 || echo "unknown")

    local health_resp
    health_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "http://${ip}:${port}/_cluster/health" 2>&1 || true)
    echo "=== GET /_cluster/health ===" >> "$evfile"; echo "$health_resp" >> "$evfile"; echo "" >> "$evfile"

    if echo "$health_resp" | grep -qiE '"status".*"(green|yellow|red)"'; then
        local indices_resp
        indices_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
            --connect-timeout "${CONNECT_TIMEOUT}" \
            "http://${ip}:${port}/_cat/indices?v&h=index,docs.count,store.size" 2>&1 | head -30 || true)
        echo "=== GET /_cat/indices ===" >> "$evfile"; echo "$indices_resp" >> "$evfile"
        local sens_idx=()
        for pat in logstash filebeat password credential user customer pii secret token auth; do
            echo "$indices_resp" | grep -qi "$pat" && sens_idx+=("$pat")
        done
        local sens_note=""
        [[ ${#sens_idx[@]} -gt 0 ]] && sens_note=" | Sensitive index patterns: ${sens_idx[*]}"
        add_result VULN "$ip" "$port" "elasticsearch" \
            "NOAUTH — Elasticsearch/OpenSearch ${es_ver} cluster accessible without credentials; /_cat/indices enumerable.${sens_note}" "$evfile"
        return
    elif echo "$health_resp" | grep -qi "security_exception\|Unauthorized\|401\|authentication"; then
        add_result SAFE "$ip" "$port" "elasticsearch" "Elasticsearch ${es_ver} — authentication required (X-Pack Security active)" "$evfile"
        return
    fi
    add_result UNKNOWN "$ip" "$port" "elasticsearch" "Elasticsearch ${es_ver} port open — cluster health inconclusive; manual: curl http://${ip}:${port}/_cluster/health" "$evfile"
}

# =============================================================================
# VAPT-ADDED: PROBE: KIBANA NO-AUTH | kibana,5601,noauth,dashboard
# Description: Kibana without authentication exposes full Elasticsearch data via
# dashboard, Lens, Discover views. Credentials not required to read all indices.
# Remediation: Enable Kibana authentication (xpack.security.enabled) or restrict port.
# =============================================================================
probe_kibana() {
    local ip="$1" port="${2:-5601}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/kibana_noauth_${SESSION_TS}.txt"
    log "  Probing Kibana NOAUTH @ ${ip}:${port}"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] curl http://${ip}:${port}/api/status"; return; }
    have curl || { add_result MANUAL "$ip" "$port" "kibana" "curl not available" ""; return; }

    echo "# Kibana NOAUTH @ ${ip}:${port} — $(_now)" > "$evfile"

    local status_resp
    status_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "http://${ip}:${port}/api/status" 2>&1 || true)
    echo "=== GET /api/status ===" >> "$evfile"; echo "$status_resp" >> "$evfile"; echo "" >> "$evfile"

    if ! echo "$status_resp" | grep -qiE '"overall".*"state"|"version".*"number"|kibana'; then
        add_result SAFE "$ip" "$port" "kibana" "Kibana not detected on port ${port}" "$evfile"
        return
    fi

    local kib_ver; kib_ver=$(echo "$status_resp" | grep -oP '"number"\s*:\s*"\K[^"]+' | head -1 || echo "unknown")
    local home_code
    home_code=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" -o /dev/null -w "%{http_code}" \
        "http://${ip}:${port}/" 2>&1 || echo "000")
    echo "=== GET / HTTP code: ${home_code} ===" >> "$evfile"

    if [[ "$home_code" == "200" ]]; then
        add_result VULN "$ip" "$port" "kibana" \
            "NOAUTH — Kibana ${kib_ver} accessible without authentication; full Elasticsearch data exposed via dashboard" "$evfile"
    elif echo "$status_resp" | grep -qi "Unauthorized\|401"; then
        add_result SAFE "$ip" "$port" "kibana" "Kibana ${kib_ver} — authentication required" "$evfile"
    else
        add_result UNKNOWN "$ip" "$port" "kibana" \
            "Kibana ${kib_ver} detected — home redirects (HTTP ${home_code}); manual login test required" "$evfile"
    fi
}

# =============================================================================
# VAPT-ADDED: PROBE: ETCD NO-AUTH | etcd,2379,noauth,kubernetes,secrets
# Description: etcd without authentication exposes Kubernetes secrets, service account
# tokens, TLS certificates, and full cluster configuration. Direct path to cluster
# compromise — extract tokens → kubectl access → container escape.
# CVSS: 10.0 CRITICAL (unauthenticated access to Kubernetes credential store)
# Remediation: Enable etcd client TLS cert auth; never expose 2379/2380 externally.
# =============================================================================
probe_etcd() {
    local ip="$1" port="${2:-2379}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/etcd_noauth_${SESSION_TS}.txt"
    log "  Probing etcd NOAUTH @ ${ip}:${port} (Kubernetes secret exposure)"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] curl http://${ip}:${port}/v2/keys/"; return; }
    have curl || { add_result MANUAL "$ip" "$port" "etcd" "curl not available" ""; return; }

    echo "# etcd NOAUTH @ ${ip}:${port} — $(_now)" > "$evfile"
    echo "# Kubernetes credential store — stores secrets, service-account tokens, TLS certs" >> "$evfile"
    echo "" >> "$evfile"

    local v2_resp
    v2_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "http://${ip}:${port}/v2/keys/" 2>&1 || true)
    echo "=== GET /v2/keys/ ===" >> "$evfile"; echo "$v2_resp" >> "$evfile"; echo "" >> "$evfile"

    local v3_resp
    v3_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" \
        -X POST "http://${ip}:${port}/v3/kv/range" \
        -H "Content-Type: application/json" \
        -d '{"key":"Cg=="}' 2>&1 || true)
    echo "=== POST /v3/kv/range (list all keys) ===" >> "$evfile"; echo "$v3_resp" >> "$evfile"; echo "" >> "$evfile"

    if echo "$v2_resp" | grep -qiE '"action"|"node"|"key".*"value"'; then
        add_result VULN "$ip" "$port" "etcd" \
            "CRITICAL: etcd v2 API NOAUTH — full key-value store accessible without credentials; Kubernetes secrets/tokens exposed" "$evfile"
        return
    fi
    if echo "$v3_resp" | grep -qiE '"kvs"|"count"|"header".*"cluster_id"'; then
        add_result VULN "$ip" "$port" "etcd" \
            "CRITICAL: etcd v3 API NOAUTH — /v3/kv/range accessible without credentials; Kubernetes secrets/tokens/TLS certs exposed" "$evfile"
        return
    fi
    if echo "$v2_resp$v3_resp" | grep -qi "Unauthorized\|401\|certificate required\|tls"; then
        add_result SAFE "$ip" "$port" "etcd" "etcd requires TLS client certificate or authentication" "$evfile"
        return
    fi
    add_result UNKNOWN "$ip" "$port" "etcd" "etcd port ${port} open — API inconclusive; manual: curl http://${ip}:${port}/v2/keys/" "$evfile"
}

# =============================================================================
# VAPT-ADDED: PROBE: SPRING BOOT ACTUATOR | spring,actuator,env,credentials,cwe200
# Description: Spring Boot Actuator management endpoints (/actuator/env, /actuator/heapdump)
# expose application credentials, DB passwords, API keys, and in-memory secrets when
# not secured. /heapdump allows downloading the full Java heap — extract passwords
# from heap dump with strings/grep. CWE-200: Information Exposure.
# Remediation: Secure actuator endpoints with Spring Security; disable /heapdump in prod.
# =============================================================================
probe_spring_actuator() {
    local ip="$1" port="${2:-8080}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/spring_actuator_${port}_${SESSION_TS}.txt"
    log "  Probing Spring Boot Actuator @ ${ip}:${port} (credential leak check)"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] curl http://${ip}:${port}/actuator/env"; return; }
    have curl || { add_result MANUAL "$ip" "$port" "spring-actuator" "curl not available" ""; return; }

    local proto="http"; [[ "$port" == "443" || "$port" == "8443" ]] && proto="https"
    local base="${proto}://${ip}:${port}"

    echo "# Spring Boot Actuator probe @ ${ip}:${port} — $(_now)" > "$evfile"
    echo "# CWE-200: Information Exposure via unsecured management endpoints" >> "$evfile"
    echo "" >> "$evfile"

    local act_resp
    act_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "${base}/actuator" 2>&1 || true)
    echo "=== GET /actuator ===" >> "$evfile"; echo "$act_resp" >> "$evfile"; echo "" >> "$evfile"

    if ! echo "$act_resp" | grep -qiE '"_links"|"health"|actuator'; then
        add_result SAFE "$ip" "$port" "spring-actuator" "No Spring Boot Actuator detected at ${base}/actuator" "$evfile"
        return
    fi

    local findings=("Actuator root accessible at ${base}/actuator")
    log_warn "    Spring Boot Actuator detected at ${base}"

    local env_resp
    env_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "${base}/actuator/env" 2>&1 || true)
    echo "=== GET /actuator/env ===" >> "$evfile"; echo "$env_resp" | head -100 >> "$evfile"; echo "" >> "$evfile"

    if echo "$env_resp" | grep -qiE '"propertySources"|"activeProfiles"|"systemProperties"'; then
        findings+=("/actuator/env exposed — environment properties readable")
        if echo "$env_resp" | grep -qiP '"(password|secret|key|token|credential|passwd|apikey|api_key)"'; then
            findings+=("CREDENTIAL PROPERTIES DETECTED in /actuator/env — passwords/keys may be in cleartext")
            log_warn "    CREDENTIAL PATTERNS found in actuator/env on ${base}"
        fi
    fi

    local heap_code
    heap_code=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" -o /dev/null -w "%{http_code}" \
        "${base}/actuator/heapdump" 2>&1 || echo "000")
    echo "=== GET /actuator/heapdump HTTP: ${heap_code} ===" >> "$evfile"
    if [[ "$heap_code" == "200" ]]; then
        findings+=("/actuator/heapdump accessible (HTTP 200) — Java heap downloadable; in-memory credential extraction possible via strings/jhat")
        log_warn "    HEAP DUMP downloadable at ${base}/actuator/heapdump"
    fi

    for ep in mappings beans loggers metrics; do
        local ec; ec=$(timeout 5 curl -sk --max-time 5 --connect-timeout 3 -o /dev/null \
            -w "%{http_code}" "${base}/actuator/${ep}" 2>/dev/null || echo "000")
        [[ "$ec" == "200" ]] && findings+=("/actuator/${ep} exposed (HTTP 200)")
    done

    if [[ ${#findings[@]} -gt 1 ]]; then
        add_result VULN "$ip" "$port" "spring-actuator" \
            "Spring Boot Actuator exposed: $(IFS=' | '; echo "${findings[*]}")" "$evfile"
    else
        add_result UNKNOWN "$ip" "$port" "spring-actuator" \
            "Spring Boot Actuator root accessible but sensitive endpoints protected — partial exposure" "$evfile"
    fi
}

# =============================================================================
# VAPT-ADDED: PROBE: JENKINS ANON + CVE-2024-23897 | jenkins,cve,2024,23897,fileread
# CVE-2024-23897: Jenkins arbitrary file read via CLI args4j @-file processing
# Affected: Jenkins < 2.442, LTS < 2.426.3 (unauthenticated when anon read enabled)
# CVSS 3.1: 9.8 CRITICAL — unauthenticated RCE via file read + groovy script console
# Exploit path: download jenkins-cli.jar → read /etc/passwd or SSH keys → escalate
# Remediation: Upgrade Jenkins; disable anonymous access; restrict CLI.
# =============================================================================
probe_jenkins() {
    local ip="$1" port="${2:-8080}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/jenkins_${port}_${SESSION_TS}.txt"
    log "  Probing Jenkins @ ${ip}:${port} (anon access + CVE-2024-23897)"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] curl http://${ip}:${port}/login (Jenkins detection)"; return; }
    have curl || { add_result MANUAL "$ip" "$port" "jenkins" "curl not available" ""; return; }

    local proto="http"; [[ "$port" == "443" || "$port" == "8443" ]] && proto="https"
    local base="${proto}://${ip}:${port}"

    echo "# Jenkins probe @ ${ip}:${port} — $(_now)" > "$evfile"
    echo "# CVE-2024-23897: Arbitrary file read via Jenkins CLI (Jenkins < 2.442 / LTS < 2.426.3)" >> "$evfile"
    echo "" >> "$evfile"

    local login_resp
    login_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" -I "${base}/login" 2>&1 || true)
    echo "=== HEAD /login ===" >> "$evfile"; echo "$login_resp" >> "$evfile"; echo "" >> "$evfile"

    local is_jenkins=0
    echo "$login_resp" | grep -qiE "X-Jenkins:|X-Hudson:" && is_jenkins=1
    if [[ "$is_jenkins" -eq 0 ]]; then
        local api_resp
        api_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
            --connect-timeout "${CONNECT_TIMEOUT}" "${base}/api/json?pretty=true" 2>&1 | head -20 || true)
        echo "=== GET /api/json ===" >> "$evfile"; echo "$api_resp" >> "$evfile"
        echo "$api_resp" | grep -qiE '"jobs"|"mode"|"nodeDescription"' && is_jenkins=1
    fi

    if [[ "$is_jenkins" -eq 0 ]]; then
        add_result SAFE "$ip" "$port" "jenkins" "Jenkins not detected on port ${port}" "$evfile"
        return
    fi

    local jenkins_ver; jenkins_ver=$(echo "$login_resp" | grep -i "X-Jenkins:" | awk '{print $2}' | tr -d '\r' || echo "unknown")
    log_info "    Jenkins ${jenkins_ver} detected at ${base}"

    local findings=()
    local dash_code
    dash_code=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" -o /dev/null -w "%{http_code}" "${base}/" 2>&1 || echo "000")
    echo "=== GET / HTTP: ${dash_code} ===" >> "$evfile"
    [[ "$dash_code" == "200" ]] && findings+=("Anonymous dashboard access (HTTP 200)")

    local api_code
    api_code=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" -o /dev/null -w "%{http_code}" "${base}/api/json" 2>&1 || echo "000")
    [[ "$api_code" == "200" ]] && findings+=("Anonymous API access /api/json (HTTP 200) — job enumeration possible")

    # CVE-2024-23897: CLI jar availability = exploitation vector exists
    local cli_code
    cli_code=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" -o /dev/null -w "%{http_code}" \
        "${base}/jnlpJars/jenkins-cli.jar" 2>&1 || echo "000")
    echo "=== GET /jnlpJars/jenkins-cli.jar HTTP: ${cli_code} ===" >> "$evfile"
    if [[ "$cli_code" == "200" ]]; then
        findings+=("Jenkins CLI jar downloadable (CVE-2024-23897 vector present)")
        if [[ -n "$jenkins_ver" && "$jenkins_ver" != "unknown" ]]; then
            local jver_maj jver_min
            jver_maj=$(echo "$jenkins_ver" | cut -d. -f1)
            jver_min=$(echo "$jenkins_ver" | cut -d. -f2)
            if [[ -n "$jver_min" ]] && [[ "$jver_maj" -le 2 && "$jver_min" -lt 442 ]]; then
                findings+=("CVE-2024-23897 CONFIRMED CANDIDATE — Jenkins ${jenkins_ver} < 2.442 (arbitrary file read via CLI @-file; escalate to RCE via script console if anon access enabled)")
                log_warn "    CVE-2024-23897: Jenkins ${jenkins_ver} in vulnerable range (< 2.442)"
            else
                findings+=("Jenkins ${jenkins_ver} >= 2.442 — CVE-2024-23897 likely patched; verify CLI access controls")
            fi
        else
            findings+=("CVE-2024-23897 CANDIDATE — Jenkins version unknown; manual version verification required")
        fi
    fi

    # Script console — if accessible anonymously = direct RCE
    local sc_code
    sc_code=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" -o /dev/null -w "%{http_code}" \
        "${base}/script" 2>&1 || echo "000")
    [[ "$sc_code" == "200" ]] && {
        findings+=("CRITICAL: Script console (/script) anonymously accessible — direct Groovy RCE")
        log_warn "    CRITICAL: Jenkins script console accessible at ${base}/script"
    }

    if [[ ${#findings[@]} -gt 0 ]]; then
        add_result VULN "$ip" "$port" "jenkins" \
            "Jenkins ${jenkins_ver}: $(IFS=' | '; echo "${findings[*]}")" "$evfile"
    else
        add_result SAFE "$ip" "$port" "jenkins" \
            "Jenkins ${jenkins_ver} — authentication required; anonymous access blocked" "$evfile"
    fi
}

# =============================================================================
# VAPT-ADDED: PROBE: CUPS IPP EXPOSURE | cups,631,ipp,cve,2024,47076,rce
# CVE-2024-47076: libcupsfilters — IPP attributes unsanitized → crafted PPD injection
# CVE-2024-47175: libppd — crafted IPP attributes injected into PPD file
# CVE-2024-47176: cups-browsed — binds UDP 0.0.0.0:631, accepts any IPP Get-Printer-Attributes
# CVE-2024-47177: cups-filters — FoomaticRIPCommandLine arbitrary command execution
# Full RCE chain: attacker → UDP 631 crafted packet → cups-browsed fetches attacker IPP
# → installs malicious printer → user prints → command injection → RCE as lp/root
# Affected: cups-browsed <= 2.0.1, libcupsfilters <= 2.1b1, libppd <= 2.1b1
# Remediation: Disable cups-browsed; firewall UDP 631; update CUPS packages.
# =============================================================================
probe_cups_ipp() {
    local ip="$1" port="${2:-631}"
    local vdir; vdir="$(verify_dir_for "$ip")"
    local evfile="${vdir}/cups_ipp_${SESSION_TS}.txt"
    log "  Probing CUPS/IPP @ ${ip}:${port} (CVE-2024-47076/47175/47176/47177 exposure)"
    [[ "${DRY_RUN}" -eq 1 ]] && { log "  [DRY RUN] curl http://${ip}:${port}/ (CUPS web interface)"; return; }
    have curl || { add_result MANUAL "$ip" "$port" "cups" "curl not available" ""; return; }

    echo "# CUPS/IPP probe @ ${ip}:${port} — $(_now)" > "$evfile"
    echo "# CVE-2024-47076/47175/47176/47177: CUPS RCE chain via crafted IPP attributes" >> "$evfile"
    echo "# Full chain: UDP 631 packet → malicious printer install → print job → RCE" >> "$evfile"
    echo "" >> "$evfile"

    local web_resp
    web_resp=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
        --connect-timeout "${CONNECT_TIMEOUT}" "http://${ip}:${port}/" 2>&1 || true)
    echo "=== GET http://${ip}:${port}/ ===" >> "$evfile"
    echo "$web_resp" | head -30 >> "$evfile"; echo "" >> "$evfile"

    local findings=()

    if echo "$web_resp" | grep -qiE "CUPS|cups.*printing|Common UNIX Printing System"; then
        local cups_ver; cups_ver=$(echo "$web_resp" | grep -oiP 'CUPS/[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")
        findings+=("CUPS web interface accessible at http://${ip}:${port}/ (version: ${cups_ver})")
        log_warn "    CUPS detected at http://${ip}:${port}/ — CVE-2024-47076/47176 exposure"

        local admin_code
        admin_code=$(timeout "${PROBE_TIMEOUT}" curl -sk --max-time "${PROBE_TIMEOUT}" \
            --connect-timeout "${CONNECT_TIMEOUT}" -o /dev/null -w "%{http_code}" \
            "http://${ip}:${port}/admin/" 2>&1 || echo "000")
        [[ "$admin_code" == "200" ]] && {
            findings+=("CUPS admin interface unauthenticated (HTTP 200) — printer management accessible")
            log_warn "    CUPS admin panel accessible without auth at http://${ip}:${port}/admin/"
        }

        local printers_resp
        printers_resp=$(timeout 5 curl -sk --max-time 5 --connect-timeout 3 \
            "http://${ip}:${port}/printers/" 2>&1 || true)
        echo "=== GET /printers/ ===" >> "$evfile"; echo "$printers_resp" | head -20 >> "$evfile"
        echo "$printers_resp" | grep -qiE "printer|queue|IPP" && \
            findings+=("IPP printer queue exposed at /printers/ — enumerate installed printers")

        findings+=("CVE-2024-47076/47175/47176 EXPOSURE — CUPS externally accessible; if cups-browsed <= 2.0.1 running, attacker can install malicious printer via crafted UDP packet to port 631 → RCE on print job")
    fi

    # Check if port is open at all (in case web interface shows nothing)
    if [[ ${#findings[@]} -eq 0 ]]; then
        if echo "$web_resp" | grep -q .; then
            add_result UNKNOWN "$ip" "$port" "cups" "Port ${port} responding but CUPS not identified — manual verification required" "$evfile"
        else
            add_result SAFE "$ip" "$port" "cups" "CUPS/IPP not responding on port ${port}" "$evfile"
        fi
        return
    fi

    add_result VULN "$ip" "$port" "cups" \
        "CUPS/IPP exposed: $(IFS=' | '; echo "${findings[*]}")" "$evfile"
}

# =============================================================================
# MRK:07_INGEST — PHASE 0 INGEST STUBS | ingest,phase,stubs,parse,prior | L1843-1923
# NAV-RULE: insert-here
# STATUS: STUB — pattern lists defined but no add_result calls yet.
# Action-plan MRK:SUITE tracks implementation. Until then Phase 0 is a no-op.
# =============================================================================

# Extract IP from a line that may contain "ip:port", "ip port", or bare "ip"
_ingest_ip()  { echo "$1" | grep -oP '\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b' | head -1; }
_ingest_port(){ echo "$1" | grep -oP ':\K[0-9]{2,5}' | head -1; }

ingest_tls_summary() {
    local f="$1" count=0
    log "  [ingest] tls_summary — scanning for confirmed TLS findings"
    # TODO next session: implement per-finding grep + add_result calls
    # Patterns to match (grep -iE on each line, extract IP:port from same line or context):
    #   expired cert      → VULN  "tls" "Certificate expired: <subject>"
    #   self-signed       → VULN  "tls" "Self-signed certificate"
    #   TLS 1.0 / 1.1    → VULN  "tls" "Deprecated protocol: TLS 1.x accepted"
    #   RC4 / DES / NULL  → VULN  "tls" "Weak cipher: <cipher>"
    #   expiry < 30d      → VULN  "tls" "Certificate expiring soon: N days"
    #   missing HSTS      → INFO  "tls" "HSTS not present"
    log "  [ingest] tls_summary — STUB (implement patterns in next session); found ${count} findings"
}

ingest_web_summary() {
    local f="$1" count=0
    log "  [ingest] web_summary — scanning for confirmed web findings"
    # TODO next session: implement per-finding grep + add_result calls
    # Patterns:
    #   "Directory listing"          → VULN  "web" "Directory listing enabled at <path>"
    #   "\.git|\.env|\.htpasswd"     → VULN  "web" "Sensitive file exposed: <path>"
    #   "nikto.*OSVDB|nikto.*CVE"    → VULN  "web" "Nikto: <finding>"
    #   "Missing.*X-Frame"           → INFO  "web" "Missing X-Frame-Options header"
    #   "Missing.*Content-Security"  → INFO  "web" "Missing Content-Security-Policy header"
    #   "Missing.*HSTS"              → INFO  "web" "Missing Strict-Transport-Security header"
    #   "Server:.*Apache|nginx|IIS"  → INFO  "web" "Version disclosure: <banner>"
    log "  [ingest] web_summary — STUB (implement patterns in next session); found ${count} findings"
}

ingest_wpscan_report() {
    local f="$1" count=0
    log "  [ingest] wpscan_report — scanning for vulnerable WP plugins/themes"
    # TODO next session: implement per-finding grep + add_result calls
    # Patterns:
    #   "VULNERABLE"                → VULN  "wordpress" "Vulnerable plugin/theme: <name> <version>"
    #   "CVE-"                      → VULN  "wordpress" "CVE: <id> — <desc>"
    #   "xmlrpc.php.*enabled"       → INFO  "wordpress" "XML-RPC enabled (brute-force vector)"
    #   "User Found|user found"     → INFO  "wordpress" "WP user enumerated: <user>"
    #   "WordPress.*version"        → INFO  "wordpress" "WP version: <ver>"
    log "  [ingest] wpscan_report — STUB (implement patterns in next session); found ${count} findings"
}

ingest_dns_summary() {
    local f="$1" count=0
    log "  [ingest] dns_summary — scanning for DNS misconfigurations"
    # TODO next session: implement per-finding grep + add_result calls
    # Patterns:
    #   "Zone transfer|AXFR success" → VULN  "dns" "Zone transfer succeeded from <ns>"
    #   "wildcard"                   → INFO  "dns" "Wildcard DNS record detected"
    #   "dangling|NXDOMAIN"          → INFO  "dns" "Dangling subdomain: <host>"
    log "  [ingest] dns_summary — STUB (implement patterns in next session); found ${count} findings"
}

ingest_prior_summaries() {
    local any=0
    if [[ -f "${TLS_SUMMARY_FILE:-}" ]]; then
        ingest_tls_summary "$TLS_SUMMARY_FILE"; any=1
    fi
    if [[ -f "${WEB_SUMMARY_FILE:-}" ]]; then
        ingest_web_summary "$WEB_SUMMARY_FILE"; any=1
    fi
    if [[ -f "${WP_REPORT_FILE:-}" ]]; then
        ingest_wpscan_report "$WP_REPORT_FILE"; any=1
    fi
    if [[ -f "${DNS_SUMMARY_FILE:-}" ]]; then
        ingest_dns_summary "$DNS_SUMMARY_FILE"; any=1
    fi
    [[ "$any" -eq 0 ]] && log "  [ingest] no prior summary MDs found — skipping"
}

# =============================================================================
# MRK:07_DISPATCH — PROBE DISPATCHER | dispatch,probe,dispatcher,svc,function | L1924-2016
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

dispatch_probe() {
    local ip="$1" port="$2" svc="$3"

    [[ "$PROBE_FILTER" != "all" ]] && {
        case "$svc" in
            redis|mysql|postgres|mongodb|mssql|elasticsearch|opensearch|es|etcd|kibana)
                                                  [[ "$PROBE_FILTER" != "db"      ]] && return ;;
            ssh)                                  [[ "$PROBE_FILTER" != "ssh"     ]] && return ;;
            ftp)                                  [[ "$PROBE_FILTER" != "ftp"     ]] && return ;;
            smb|cifs)                             [[ "$PROBE_FILTER" != "smb"     ]] && return ;;
            snmp)                                 [[ "$PROBE_FILTER" != "snmp"    ]] && return ;;
            smtp)                                 [[ "$PROBE_FILTER" != "smtp"    ]] && return ;;
            ssrf)                                 [[ "$PROBE_FILTER" != "ssrf"    ]] && return ;;
            telnet)                               [[ "$PROBE_FILTER" != "telnet"  ]] && return ;;
            rdp)                                  [[ "$PROBE_FILTER" != "rdp"     ]] && return ;;
            ipmi)                                 [[ "$PROBE_FILTER" != "ipmi"    ]] && return ;;
            nfs)                                  [[ "$PROBE_FILTER" != "nfs"     ]] && return ;;
            winrm)                                [[ "$PROBE_FILTER" != "winrm"   ]] && return ;;
            jenkins|spring-actuator|actuator|cups)[[ "$PROBE_FILTER" != "web"     ]] && return ;;
            web|http-headers)                     [[ "$PROBE_FILTER" != "web"     ]] && return ;;
        esac
    }

    case "$svc" in
        redis)                              probe_redis             "$ip" "$port" ;;
        mysql)                              probe_mysql             "$ip" "$port" ;;
        postgres|postgresql|pg)             probe_postgres          "$ip" "$port" ;;
        mongo|mongodb)                      probe_mongodb           "$ip" "$port" ;;
        mssql|sqlserver)                    probe_mssql             "$ip" "$port" ;;
        ssh)                                probe_ssh_version       "$ip" "$port" ;;
        ftp)                                probe_ftp_anon          "$ip" "$port" ;;
        smb|cifs)                           probe_smb_null          "$ip" "$port" ;;
        snmp)                               probe_snmp              "$ip" "$port" ;;
        smtp)                               probe_smtp_relay        "$ip" "$port" ;;
        ssrf)                               probe_ssrf_imds         "$ip" "$port" ;;
        tls)                                probe_tls_cert          "$ip" "$port" ;;
        http-headers)                       probe_web_headers       "$ip" "$port" ;;
        telnet)                             probe_telnet            "$ip" "$port" ;;
        ipmi)                               probe_ipmi              "$ip" "$port" ;;
        rdp)                                probe_rdp               "$ip" "$port" ;;
        winrm)                              probe_winrm             "$ip" "$port" ;;
        nfs)                                probe_nfs               "$ip" "$port" ;;
        web)                                probe_web_generic       "$ip" "$port" ;;
        # VAPT-ADDED: 2024-2025 CVE probes
        elasticsearch|opensearch|es)        probe_elasticsearch     "$ip" "$port" ;;
        kibana)                             probe_kibana            "$ip" "$port" ;;
        etcd)                               probe_etcd              "$ip" "$port" ;;
        spring-actuator|actuator|spring)    probe_spring_actuator   "$ip" "$port" ;;
        jenkins)                            probe_jenkins           "$ip" "$port" ;;
        cups|ipp)                           probe_cups_ipp          "$ip" "$port" ;;
        consul|vault)                       probe_web_generic       "$ip" "$port" ;;
        *) log_warn "  No probe defined for service '${svc}' @ ${ip}:${port} — skipped" ;;
    esac
}

run_all_probes() {
    local followup="$1"
    local queue_raw; queue_raw=$(build_probe_queue "$followup")
    local total=0 processed=0

    total=$(echo "$queue_raw" | grep -c . || true)
    log "Built probe queue: ${total} entries"

    # --debug-queue: print queue and stop — no probes run
    if [[ "${DEBUG_QUEUE}" -eq 1 ]]; then
        echo ""
        echo "=== DEBUG QUEUE (${total} entries) ==="
        echo "$queue_raw" | nl -ba
        echo "=== END DEBUG QUEUE ==="
        echo ""
        log "DEBUG_QUEUE mode — no probes dispatched. Re-run without --debug-queue to execute."
        return
    fi

    # Process in order (priority already encoded in queue build order)
    # FD 3 isolates the queue from stdin so subprocesses (nc, ssh, msfconsole)
    # cannot steal remaining entries by reading from FD 0.
    while IFS= read -r entry <&3; do
        [[ -z "$entry" ]] && continue
        local category; category=$(echo "$entry" | cut -d: -f1)
        local target; target=$(echo "$entry" | cut -d: -f2-)
        local ip port svc
        ip=$(echo "$target"   | awk '{print $1}')
        port=$(echo "$target" | awk '{print $2}')
        svc=$(echo "$target"  | awk '{print $3}' | tr '[:upper:]' '[:lower:]')

        [[ -z "$ip" || -z "$port" || -z "$svc" ]] && continue

        log "Probe [$(( processed + 1 ))/${total}] ${category}: ${svc}:${port} @ ${ip}"
        dispatch_probe "$ip" "$port" "$svc"
        (( processed++ )) || true

    done 3<<< "$queue_raw"

    log "Probes complete: ${processed}/${total}"
}

# =============================================================================
# MRK:07_REPORT — REPORT WRITER | report,writer,working,verify,summary | L2017-2124
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

write_verify_summary() {
    local report_file="working/verify_summary_${SESSION_TS}.md"
    local vuln_rows=() safe_rows=() unknown_rows=() manual_rows=()

    for r in "${RESULTS[@]+"${RESULTS[@]}"}"; do
        IFS='|' read -r status ip port svc detail evfile <<< "$r"
        local ev_rel="${evfile/#$(pwd)\//}"
        case "$status" in
            VULN)    vuln_rows+=(   "| ${ip} | ${port} | ${svc} | ${detail} | \`${ev_rel}\` |") ;;
            SAFE)    safe_rows+=(   "| ${ip} | ${port} | ${svc} | ${detail} | \`${ev_rel}\` |") ;;
            UNKNOWN) unknown_rows+=("| ${ip} | ${port} | ${svc} | ${detail} | \`${ev_rel}\` |") ;;
            MANUAL)  manual_rows+=( "| ${ip} | ${port} | ${svc} | ${detail} | — |") ;;
        esac
    done

    local n_vuln=${#vuln_rows[@]}
    local n_safe=${#safe_rows[@]}
    local n_unk=${#unknown_rows[@]}
    local n_man=${#manual_rows[@]}

    {
        echo "# Verify Summary — ${PROJECT_NAME:-unknown}"
        echo "**Generated:** $(_now) | 07_service_verify.sh"
        echo "**Mode:** ${MODE} | **Tier:** ${TIER}"
        echo ""
        echo "---"
        echo ""
        echo "## Summary"
        echo ""
        echo "| Status | Count |"
        echo "|--------|-------|"
        echo "| VULN (confirmed) | ${n_vuln} |"
        echo "| UNKNOWN (manual follow-up) | ${n_unk} |"
        echo "| SAFE | ${n_safe} |"
        echo "| MANUAL (tool unavailable) | ${n_man} |"
        echo "| **Total probes** | **$(( n_vuln + n_safe + n_unk + n_man ))** |"
        echo ""
        echo "---"
        echo ""
        echo "## VULN — Confirmed (action required)"
        echo ""
        if [[ ${#vuln_rows[@]} -eq 0 ]]; then
            echo "*No confirmed vulnerabilities from automated probes.*"
        else
            echo "| Host | Port | Service | Finding | Evidence |"
            echo "|------|------|---------|---------|----------|"
            printf '%s\n' "${vuln_rows[@]}"
        fi
        echo ""
        echo "---"
        echo ""
        echo "## UNKNOWN — Manual follow-up required"
        echo ""
        if [[ ${#unknown_rows[@]} -eq 0 ]]; then
            echo "*No inconclusive probes.*"
        else
            echo "| Host | Port | Service | Reason | Evidence |"
            echo "|------|------|---------|--------|----------|"
            printf '%s\n' "${unknown_rows[@]}"
        fi
        echo ""
        echo "---"
        echo ""
        echo "## SAFE — No vulnerability found"
        echo ""
        if [[ ${#safe_rows[@]} -eq 0 ]]; then
            echo "*No probes returned safe.*"
        else
            echo "| Host | Port | Service | Result | Evidence |"
            echo "|------|------|---------|--------|----------|"
            printf '%s\n' "${safe_rows[@]}"
        fi
        echo ""
        echo "---"
        echo ""
        echo "## MANUAL — Tool not available"
        echo ""
        if [[ ${#manual_rows[@]} -eq 0 ]]; then
            echo "*All probes had required tools available.*"
        else
            echo "| Host | Port | Service | Action needed |"
            echo "|------|------|---------|---------------|"
            printf '%s\n' "${manual_rows[@]}"
        fi
        echo ""
        echo "---"
        echo ""
        echo "## Evidence Files"
        echo ""
        echo "\`\`\`"
        echo "evidence/_verify/"
        find "${EVIDENCE_BASE}/_verify" -name "*.txt" 2>/dev/null \
            | sort | sed "s|${EVIDENCE_BASE}/_verify/|  |"
        echo "\`\`\`"
        echo ""
        echo "---"
        echo "*${PROJECT_NAME:-engagement} | 07_service_verify.sh | TechGuard.*"
    } > "$report_file"

    log_ok "Verify summary: ${report_file}"
    echo "$report_file"
}

# =============================================================================
# MRK:07_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L2125-2152
# NAV-RULE: no-insert-before; propose-before-edit
# =============================================================================

scope_confirm() {
    [[ "${AUTO_YES}" -eq 1 ]] && return 0
    echo ""
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    echo -e "\033[1m  SCOPE CONFIRMATION — 07_service_verify.sh\033[0m"
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    printf "  %-22s %s\n" "Project:"     "${PROJECT_NAME:-[not set]}"
    printf "  %-22s %s\n" "Mode:"        "${MODE}"
    printf "  %-22s %s\n" "Tier:"        "${TIER}"
    printf "  %-22s %s\n" "Probe filter:" "${PROBE_FILTER}"
    printf "  %-22s %s\n" "Severity:"    "${SEVERITY_FILTER}"
    printf "  %-22s %s\n" "Followup:"    "${FOLLOWUP_FILE:-[auto-discover]}"
    printf "  %-22s %s\n" "Dry run:"     "$([ "${DRY_RUN}" -eq 1 ] && echo 'YES' || echo 'no')"
    printf "  %-22s %s\n" "MSF modules:" "$([ "${NO_MSF}" -eq 1 ] && echo 'disabled' || echo 'enabled')"
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    echo ""
    echo -e "\033[1mConfirm authorisation is in place and scope is correct.\033[0m"
    echo -n "  Type YES to continue: "
    read -r answer
    [[ "$answer" != "YES" ]] && { echo "Aborted."; exit 0; }
    echo ""
}

# =============================================================================
# MRK:07_MAIN — MAIN entry point | main,entry,point | L2153-2215
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    log "=== 07_service_verify.sh | ${MODE} | tier=${TIER} | severity=${SEVERITY_FILTER} ==="

    parse_db_conf

    # Trail: phase start (basic event emission; per-probe emissions TBD)
    local _07_t_start; _07_t_start=$(date +%s)
    trail_phase_start phase "verify" project "${PROJECT_NAME:-}" mode "${MODE:-}" session "${SESSION_TS:-$(_ts)}" tier "${TIER:-}" severity "${SEVERITY_FILTER:-}" ts "$(date -u +%FT%TZ)" 2>/dev/null || true

    check_tools

    # Locate input files
    [[ -z "$FOLLOWUP_FILE" ]]     && FOLLOWUP_FILE="$(latest_working "manual_followup_*.md")"
    [[ -z "$SUMMARY_FILE" ]]      && SUMMARY_FILE="$(latest_working "scan_summary_*.md")"
    [[ -z "$TLS_SUMMARY_FILE" ]]  && TLS_SUMMARY_FILE="$(latest_working "tls_summary_*.md")"
    [[ -z "$WEB_SUMMARY_FILE" ]]  && WEB_SUMMARY_FILE="$(latest_working "web_summary_*.md")"
    [[ -z "$WP_REPORT_FILE" ]]    && WP_REPORT_FILE="$(latest_working "wpscan_report_*.md")"
    [[ -z "$DNS_SUMMARY_FILE" ]]  && DNS_SUMMARY_FILE="$(latest_working "dns_summary_*.md")"

    if [[ -z "$FOLLOWUP_FILE" || ! -f "$FOLLOWUP_FILE" ]]; then
        log_warn "No manual_followup MD found in working/ — probe queue will rely on --host args and DB"
        FOLLOWUP_FILE="/dev/null"
    else
        log_ok "Using followup:    ${FOLLOWUP_FILE}"
    fi
    [[ -f "$SUMMARY_FILE" ]]      && log_ok "Using scan_summary: ${SUMMARY_FILE}"
    [[ -f "$TLS_SUMMARY_FILE" ]]  && log_ok "Using tls_summary:  ${TLS_SUMMARY_FILE}"
    [[ -f "$WEB_SUMMARY_FILE" ]]  && log_ok "Using web_summary:  ${WEB_SUMMARY_FILE}"
    [[ -f "$WP_REPORT_FILE" ]]    && log_ok "Using wpscan_report:${WP_REPORT_FILE}"
    [[ -f "$DNS_SUMMARY_FILE" ]]  && log_ok "Using dns_summary:  ${DNS_SUMMARY_FILE}"

    scope_confirm

    log "=== PHASE 0: INGESTING PRIOR SCAN FINDINGS ==="
    ingest_prior_summaries

    log "=== PHASE 1: BUILDING PROBE QUEUE ==="
    run_all_probes "$FOLLOWUP_FILE"

    log "=== PHASE 2: WRITING VERIFY SUMMARY ==="
    local report; report=$(write_verify_summary)

    log ""
    log_ok "=== 07_service_verify complete ==="
    log_ok "  Report:   ${report}"
    log_ok "  Evidence: ${EVIDENCE_BASE}/_verify/"
    log_ok "  Log:      ${LOG_FILE}"
    echo ""
    echo -e "${GREEN}Verify summary: ${report}${NC}" >&2

    # Trail: phase end
    local _07_t_end; _07_t_end=$(date +%s)
    trail_phase_end phase "verify" project "${PROJECT_NAME:-}" session "${SESSION_TS:-}" duration_sec "$((_07_t_end - _07_t_start))" ts "$(date -u +%FT%TZ)" 2>/dev/null || true
}

main "$@"

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
