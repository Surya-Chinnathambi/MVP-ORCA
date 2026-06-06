#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:03_NAV_TOC — Section index | nav,toc,index | L5-64
# - MRK:03_ROOT — ROOT CHECK | root,check,db,nmap,requires | L65-74 | ⚠ no-insert-before
# - MRK:03_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L75-161 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:03_TIER — STEALTH TIER PARAMETERS | tier,stealth,parameters | L162-311 | ⚠ no-insert-before; read-toc-first
# - MRK:03_LOG — COLOURS AND LOGGING | log,colours,logging | L312-336 | ⚠ no-insert-before
# - MRK:03_ARGS — ARGUMENT PARSING | args,argument,parsing | L337-378 | ⚠ no-insert-before; read-toc-first
# - MRK:03_DIRS — DIRECTORY STRUCTURE SETUP | dirs,directory,structure,setup | L379-402 | ⚠ no-insert-before
# - MRK:03_DB — MSF / POSTGRES DB HELPERS | db,msf,postgres,helpers | L403-462 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:03_SCAN — SCAN EXECUTION MODEL | scan,execution,model,rc,spool | L463-704 | ⚠ no-insert-before; read-toc-first
# - MRK:03_CSV — CSV FALLBACK HELPERS | csv,fallback,helpers | L705-761 | ⚠ no-insert-before; read-toc-first
# - MRK:03_GNMAP — GNMAP FALLBACK | gnmap,fallback,parse,tcp,sweep | L762-837 | ⚠ no-insert-before; read-toc-first
# - MRK:03_SCOPE — TIER RESOLUTION | scope,tier,resolution | L838-933 | ⚠ no-insert-before; read-toc-first
# - MRK:03_SRCIP — SOURCE IP VERIFICATION (PTE) | srcip,source,ip,verification,pte | L934-955 | ⚠ no-insert-before
# - MRK:03_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L956-989 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:03_RATE — RATE SELF-TEST (PTE / evasion mode) | rate,self,test,pte,evasion | L990-1023 | ⚠ no-insert-before; read-toc-first
# - MRK:03_WS — MSF WORKSPACE SETUP | ws,msf,workspace,setup | L1024-1111 | ⚠ no-insert-before; read-toc-first
# - MRK:03_EXCL — TESTER EXCLUSION | excl,tester,exclusion | L1112-1415 | ⚠ no-insert-before; read-toc-first
# - MRK:03_P1 — PHASE 1: DISCOVERY | p1,phase,discovery | L1416-1449 | ⚠ no-insert-before; read-toc-first
# - MRK:03_P2 — PHASE 2: TCP FULL SCAN | p2,phase,tcp,full,scan | L1450-1796 | ⚠ no-insert-before; read-toc-first
# - MRK:03_NSE — PHASE 2b: COMMON-PORT NSE SWEEP | nse,phase,2b,common,port | L1797-1890 | ⚠ no-insert-before; read-toc-first
# - MRK:03_OS — PHASE 2c: OS FINGERPRINTING | os,phase,2c,fingerprinting | L1891-2024 | ⚠ no-insert-before; read-toc-first
# - MRK:03_P3 — PHASE 3: UDP CORRELATION SCAN | p3,phase,udp,correlation,scan | L2025-2120 | ⚠ no-insert-before; read-toc-first
# - MRK:03_P4 — PHASE 4: SERVICE ENUMERATION | p4,phase,service,enumeration | L2121-2126 | ⚠ no-insert-before; read-toc-first
# - MRK:03_PROBES — Active service probes | probes,active,service,mongodb,vuln | L2127-2461 | ⚠ insert-here
# - MRK:03_P4B — PHASE 4b: PTE SERVICE ENUMERATION | p4b,phase,4b,pte,service | L2462-2627 | ⚠ no-insert-before; read-toc-first
# - MRK:03_P5 — PHASE 5: REPORT / SUMMARY | p5,phase,report,summary | L2628-2698 | ⚠ no-insert-before; read-toc-first
# - MRK:03_MAIN — MAIN | main,03 | L2699-2801 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 26 entries | Integrity-hash: 7b3647616cebf458 | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# 03_comp_scan.sh — Phase-aware, DB-driven, stealth-tiered network scanner. PTI + PTE.
# TechGuard. | Version: 0.8 [VAPT-enhanced]
# VAPT additions: phase_sweep_nse_vapt_cve() — dedicated CVE NSE pass running
#   after the standard NSE sweep. Scripts: smb-vuln-ms17-010 (EternalBlue),
#   http-shellshock (CVE-2014-6271), ssl-heartbleed, ssl-poodle, ssl-drown,
#   ssl-ccs-injection, rdp-vuln-ms12-020, http-slowloris-check (loud tier only),
#   ftp-anon, ms-sql-info, mysql-empty-password, mysql-vuln-cve2012-2122.
#   Port-gated: each script group fires only when relevant ports are in scope.
# =============================================================================
# USAGE:
#   sudo ./03_comp_scan.sh [OPTIONS]
#
# OPTIONS:
#   --mode <pti|pte>      Engagement mode (default: from config)
#   --phase <n>           discovery|tcp|udp|enum|report|all (default: all)
#                         discovery optional (ARP)  use --phase discovery explicitly
#   --continue            After --phase, continue subsequent phases
#   --reuse-workspace     Reuse existing MSF workspace (no rename-to-archive);
#                         keeps prior hosts/services/ports for narrowing + resume.
#   --tier <t>            ghost|normal|loud|evasion (default: from config)
#                         evasion: T1, rate 5, fragmented, source-port 443, randomised
#   --yes                 Skip scope confirmation prompt
#   --dry-run             Print commands without sending packets (safe rehearsal)
#   --masscan-only        TCP phase only: run Pass 1 fast scan/import and skip all
#                         following nmap passes (legacy flag name kept for compatibility)
#   --decoys              Add -D RND:5 decoys (PTE  requires RoE sign-off)
#   --idle-scan <zombie>  TCP idle/zombie scan via <zombie IP> (TCP phases only;
#                         PTE  requires explicit RoE sign-off before use)
#
#  EDIT ENGAGEMENT CONFIGURATION BELOW BEFORE RUNNING WITHOUT ARGUMENTS 
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:03_ROOT — ROOT CHECK | root,check,db,nmap,requires | L65-74
# NAV-RULE: no-insert-before
# =============================================================================
if [[ "$EUID" -ne 0 ]] && [[ "${PTORC_ALLOW_NON_ROOT:-0}" != "1" ]]; then
    echo "[ERROR] This script must be run as root (required for db_nmap SYN/UDP scans)."
    echo "        Run: sudo $0 $*"
    exit 1
fi

# =============================================================================
# MRK:03_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L75-161
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

# Load shared engagement config (PROJECT_NAME, MODE, TARGET_SUBNETS, TARGET_IPS,
# TESTER_IP, TESTER_EXCLUDE_IPS, PTE_TARGETS_FILE, SUBNET_TIER_MAP, GLOBAL_TIER,
# MASSCAN_RATE_*, MAX_PARALLEL_SCANS, MASSCAN_INTERFACE, )
# shellcheck source=pt-orc.conf
[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found in ${SCRIPT_DIR}  set variables in pt-orc.conf"

# Script-local defaults  override in pt-orc.conf if needed
EVIDENCE_BASE="evidence"

# =============================================================================
# PTE MODE REMINDER (set in pt-orc.conf)
# =============================================================================
# MODE="pte"   TARGET_SUBNETS must be ""  targets come from PTE_TARGETS_FILE
# MODE="pti"   set TARGET_SUBNETS and/or TARGET_IPS in pt-orc.conf
# TESTER_IP    set in pt-orc.conf; script aborts if actual egress differs
# GLOBAL_TIER  "normal" for both PTI and PTE; downgrade reactively if needed
# --decoys and --idle-scan require explicit RoE sign-off before use
# =============================================================================

# =============================================================================
# PASS 1  FAST TCP DISCOVERY NOTES
# =============================================================================
# FAST_TCP_SCANNER selects the Pass 1 backend (masscan|naabu|db_nmap).
# The fast scanner replaces nmap -p- for the full-port sweep (Pass 1).
# Pass 2 (version/OS on open ports) still uses db_nmap via msfconsole.
# Evasion tier always falls back to nmap  masscan cannot do -f / --source-port.
# Rates and interface are set in pt-orc.conf (MASSCAN_RATE_*, MASSCAN_INTERFACE).
# =============================================================================

# BASELINE_PORTS  always included in TCP Pass 2 (deep scan) regardless of what
# masscan found. Provides a guaranteed floor of coverage if masscan under-delivers
# (wrong interface, rate-limited switch, hosts that drop SYN without prior ARP, etc.).
# Merged with masscan results; duplicates removed automatically.
BASELINE_PORTS="21,22,23,25,53,80,110,111,135,139,143,389,443,445,465,587,636,993,995,1433,1521,2049,3306,3389,5432,5900,5985,5986,8080,8443,8888,9200,10443,27017,6379,11211,2181"

# Pass 1 backend selection and fast-scan tuning.
FAST_TCP_SCANNER="${FAST_TCP_SCANNER:-masscan}"   # masscan | naabu | db_nmap
NAABU_THREADS="${NAABU_THREADS:-25}"
NAABU_TIMEOUT="${NAABU_TIMEOUT:-1500}"
NAABU_RETRIES="${NAABU_RETRIES:-1}"
DB_NMAP_FAST_MIN_RATE_GHOST="${DB_NMAP_FAST_MIN_RATE_GHOST:-2000}"
DB_NMAP_FAST_MIN_RATE_NORMAL="${DB_NMAP_FAST_MIN_RATE_NORMAL:-8000}"
DB_NMAP_FAST_MIN_RATE_LOUD="${DB_NMAP_FAST_MIN_RATE_LOUD:-20000}"
DB_NMAP_FAST_MAX_RATE_GHOST="${DB_NMAP_FAST_MAX_RATE_GHOST:-15000}"
DB_NMAP_FAST_MAX_RATE_NORMAL="${DB_NMAP_FAST_MAX_RATE_NORMAL:-50000}"
DB_NMAP_FAST_MAX_RATE_LOUD="${DB_NMAP_FAST_MAX_RATE_LOUD:-120000}"
DB_NMAP_FAST_MIN_HOSTGROUP_GHOST="${DB_NMAP_FAST_MIN_HOSTGROUP_GHOST:-16}"
DB_NMAP_FAST_MIN_HOSTGROUP_NORMAL="${DB_NMAP_FAST_MIN_HOSTGROUP_NORMAL:-32}"
DB_NMAP_FAST_MIN_HOSTGROUP_LOUD="${DB_NMAP_FAST_MIN_HOSTGROUP_LOUD:-64}"
DB_NMAP_FAST_MAX_HOSTGROUP_GHOST="${DB_NMAP_FAST_MAX_HOSTGROUP_GHOST:-64}"
DB_NMAP_FAST_MAX_HOSTGROUP_NORMAL="${DB_NMAP_FAST_MAX_HOSTGROUP_NORMAL:-128}"
DB_NMAP_FAST_MAX_HOSTGROUP_LOUD="${DB_NMAP_FAST_MAX_HOSTGROUP_LOUD:-256}"
DB_NMAP_FAST_MAX_RETRIES_GHOST="${DB_NMAP_FAST_MAX_RETRIES_GHOST:-2}"
DB_NMAP_FAST_MAX_RETRIES_NORMAL="${DB_NMAP_FAST_MAX_RETRIES_NORMAL:-2}"
DB_NMAP_FAST_MAX_RETRIES_LOUD="${DB_NMAP_FAST_MAX_RETRIES_LOUD:-1}"
DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_GHOST="${DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_GHOST:-150ms}"
DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_NORMAL="${DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_NORMAL:-100ms}"
DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_LOUD="${DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_LOUD:-50ms}"
DB_NMAP_FAST_MAX_RTT_TIMEOUT_GHOST="${DB_NMAP_FAST_MAX_RTT_TIMEOUT_GHOST:-500ms}"
DB_NMAP_FAST_MAX_RTT_TIMEOUT_NORMAL="${DB_NMAP_FAST_MAX_RTT_TIMEOUT_NORMAL:-350ms}"
DB_NMAP_FAST_MAX_RTT_TIMEOUT_LOUD="${DB_NMAP_FAST_MAX_RTT_TIMEOUT_LOUD:-200ms}"
DB_NMAP_FAST_HOST_TIMEOUT_GHOST="${DB_NMAP_FAST_HOST_TIMEOUT_GHOST:-2m}"
DB_NMAP_FAST_HOST_TIMEOUT_NORMAL="${DB_NMAP_FAST_HOST_TIMEOUT_NORMAL:-1m}"
DB_NMAP_FAST_HOST_TIMEOUT_LOUD="${DB_NMAP_FAST_HOST_TIMEOUT_LOUD:-30s}"
DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_GHOST="${DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_GHOST:-1}"
DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_NORMAL="${DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_NORMAL:-1}"
DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_LOUD="${DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_LOUD:-1}"

# Discovery + target-list narrowing (see phase_discovery, phase_tcp)
RUN_DISCOVERY="${RUN_DISCOVERY:-1}"
USE_DISCOVERY_FOR_TCP="${USE_DISCOVERY_FOR_TCP:-1}"

# Timeouts
CONNECT_TIMEOUT=5
MQTT_LISTEN_TIMEOUT=30
E4L_TIMEOUT=120

# =============================================================================
#  END ENGAGEMENT CONFIGURATION 
# =============================================================================

# =============================================================================
# MRK:03_TIER — STEALTH TIER PARAMETERS | tier,stealth,parameters | L162-311
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# ghost    T2, max-rate 100, min-hostgroup 4.  PTI default. OT/fragile-device safe.
# normal   T3, max-rate 2000, min-rate 500.    Standard corporate LAN.
# loud     T4, max-rate 5000, min-rate 3000.   Lab / time-critical.
# evasion  T1, max-rate 5, fragmented, source-port 443, randomised order, no DNS.
#            NOTE: decoys (-D) and idle scan (-sI) require explicit RoE sign-off.

tier_nmap_timing()      { case "$1" in ghost) echo "-T2";; normal) echo "-T3";; loud) echo "-T4";; evasion) echo "-T1";; esac; }
tier_min_rate()         { case "$1" in ghost) echo "";; normal) echo "--min-rate 500";; loud) echo "--min-rate 3000";; evasion) echo "";; esac; }
tier_max_rate()         { case "$1" in ghost) echo "--max-rate 100";; normal) echo "--max-rate 2000";; loud) echo "--max-rate 5000";; evasion) echo "--max-rate 5";; esac; }
tier_min_hostgroup()    { case "$1" in ghost) echo "--min-hostgroup 8";; normal) echo "--min-hostgroup 16";; loud) echo "--min-hostgroup 32";; evasion) echo "--min-hostgroup 1";; esac; }
tier_version_intensity(){ case "$1" in ghost) echo "--version-intensity 3";; normal) echo "--version-intensity 5";; loud) echo "--version-intensity 7";; evasion) echo "--version-intensity 1";; esac; }
tier_max_retries()      { case "$1" in ghost) echo "--max-retries 2";; normal) echo "--max-retries 4";; loud) echo "--max-retries 3";; evasion) echo "--max-retries 1";; esac; }
tier_host_timeout()     { case "$1" in ghost) echo "--host-timeout 10m";; normal) echo "--host-timeout 5m";; loud) echo "--host-timeout 2m";; evasion) echo "--host-timeout 30m";; esac; }
tier_script_timeout()   { case "$1" in ghost) echo "--script-timeout 3m";; normal) echo "--script-timeout 2m";; loud) echo "--script-timeout 1m";; evasion) echo "--script-timeout 5m";; esac; }

# Evasion-specific extra flags
tier_evasion_flags() {
    [[ "$1" == "evasion" ]] && echo "-f --source-port 443 --scan-delay 2s --randomize-hosts --data-length 25 -n"
}

# Default NSE scripts for Pass 2 deep scan.
# Evasion omits -sC  default scripts are too noisy for WAF/IDS environments.
tier_scripts() { case "$1" in ghost|normal|loud) echo "-sC";; evasion) echo "";; esac; }

# masscan pps rate for a given tier (Pass 1 only; evasion uses nmap, not masscan)
masscan_rate_for_tier() {
    case "$1" in
        ghost)  echo "${MASSCAN_RATE_GHOST:-500}" ;;
        normal) echo "${MASSCAN_RATE_NORMAL:-5000}" ;;
        loud)   echo "${MASSCAN_RATE_LOUD:-10000}" ;;
        *)      echo "1000" ;;
    esac
}

# naabu worker threads for a given tier (Pass 1 only; evasion uses nmap, not naabu)
naabu_threads_for_tier() {
    case "$1" in
        ghost)  echo "${NAABU_THREADS_GHOST:-10}" ;;
        normal) echo "${NAABU_THREADS_NORMAL:-25}" ;;
        loud)   echo "${NAABU_THREADS_LOUD:-40}" ;;
        *)      echo "${NAABU_THREADS:-25}" ;;
    esac
}

# db_nmap fast full-port sweep tuning for Pass 1.
# These helpers keep the fast backend aligned with the ghost|normal|loud tier
# model while allowing each tier to tune speed and RTT behavior independently.
db_nmap_fast_min_rate_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_MIN_RATE_GHOST:-2000}" ;;
        normal) echo "${DB_NMAP_FAST_MIN_RATE_NORMAL:-8000}" ;;
        loud)   echo "${DB_NMAP_FAST_MIN_RATE_LOUD:-20000}" ;;
        *)      echo "${DB_NMAP_FAST_MIN_RATE_NORMAL:-8000}" ;;
    esac
}

db_nmap_fast_max_rate_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_MAX_RATE_GHOST:-15000}" ;;
        normal) echo "${DB_NMAP_FAST_MAX_RATE_NORMAL:-50000}" ;;
        loud)   echo "${DB_NMAP_FAST_MAX_RATE_LOUD:-120000}" ;;
        *)      echo "${DB_NMAP_FAST_MAX_RATE_NORMAL:-50000}" ;;
    esac
}

db_nmap_fast_min_hostgroup_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_MIN_HOSTGROUP_GHOST:-16}" ;;
        normal) echo "${DB_NMAP_FAST_MIN_HOSTGROUP_NORMAL:-32}" ;;
        loud)   echo "${DB_NMAP_FAST_MIN_HOSTGROUP_LOUD:-64}" ;;
        *)      echo "${DB_NMAP_FAST_MIN_HOSTGROUP_NORMAL:-32}" ;;
    esac
}

db_nmap_fast_max_hostgroup_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_MAX_HOSTGROUP_GHOST:-64}" ;;
        normal) echo "${DB_NMAP_FAST_MAX_HOSTGROUP_NORMAL:-128}" ;;
        loud)   echo "${DB_NMAP_FAST_MAX_HOSTGROUP_LOUD:-256}" ;;
        *)      echo "${DB_NMAP_FAST_MAX_HOSTGROUP_NORMAL:-128}" ;;
    esac
}

db_nmap_fast_max_retries_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_MAX_RETRIES_GHOST:-2}" ;;
        normal) echo "${DB_NMAP_FAST_MAX_RETRIES_NORMAL:-2}" ;;
        loud)   echo "${DB_NMAP_FAST_MAX_RETRIES_LOUD:-1}" ;;
        *)      echo "${DB_NMAP_FAST_MAX_RETRIES_NORMAL:-2}" ;;
    esac
}

db_nmap_fast_initial_rtt_timeout_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_GHOST:-150ms}" ;;
        normal) echo "${DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_NORMAL:-100ms}" ;;
        loud)   echo "${DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_LOUD:-50ms}" ;;
        *)      echo "${DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_NORMAL:-100ms}" ;;
    esac
}

db_nmap_fast_max_rtt_timeout_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_MAX_RTT_TIMEOUT_GHOST:-500ms}" ;;
        normal) echo "${DB_NMAP_FAST_MAX_RTT_TIMEOUT_NORMAL:-350ms}" ;;
        loud)   echo "${DB_NMAP_FAST_MAX_RTT_TIMEOUT_LOUD:-200ms}" ;;
        *)      echo "${DB_NMAP_FAST_MAX_RTT_TIMEOUT_NORMAL:-350ms}" ;;
    esac
}

db_nmap_fast_host_timeout_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_HOST_TIMEOUT_GHOST:-2m}" ;;
        normal) echo "${DB_NMAP_FAST_HOST_TIMEOUT_NORMAL:-1m}" ;;
        loud)   echo "${DB_NMAP_FAST_HOST_TIMEOUT_LOUD:-30s}" ;;
        *)      echo "${DB_NMAP_FAST_HOST_TIMEOUT_NORMAL:-1m}" ;;
    esac
}

db_nmap_fast_defeat_rst_ratelimit_for_tier() {
    case "$1" in
        ghost)  echo "${DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_GHOST:-1}" ;;
        normal) echo "${DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_NORMAL:-1}" ;;
        loud)   echo "${DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_LOUD:-1}" ;;
        *)      echo "${DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_NORMAL:-1}" ;;
    esac
}

db_nmap_fast_flags() {
    local tier="$1"
    local min_rate max_rate min_hostgroup max_hostgroup max_retries
    local initial_rtt max_rtt host_timeout defeat_rst
    min_rate="$(db_nmap_fast_min_rate_for_tier "$tier")"
    max_rate="$(db_nmap_fast_max_rate_for_tier "$tier")"
    min_hostgroup="$(db_nmap_fast_min_hostgroup_for_tier "$tier")"
    max_hostgroup="$(db_nmap_fast_max_hostgroup_for_tier "$tier")"
    max_retries="$(db_nmap_fast_max_retries_for_tier "$tier")"
    initial_rtt="$(db_nmap_fast_initial_rtt_timeout_for_tier "$tier")"
    max_rtt="$(db_nmap_fast_max_rtt_timeout_for_tier "$tier")"
    host_timeout="$(db_nmap_fast_host_timeout_for_tier "$tier")"
    defeat_rst="$(db_nmap_fast_defeat_rst_ratelimit_for_tier "$tier")"

    printf '%s' "--min-rate ${min_rate} --max-rate ${max_rate} --min-hostgroup ${min_hostgroup} --max-hostgroup ${max_hostgroup} --max-retries ${max_retries} --initial-rtt-timeout ${initial_rtt} --max-rtt-timeout ${max_rtt} --host-timeout ${host_timeout}"
    [[ "$defeat_rst" == "1" ]] && printf ' %s' "--defeat-rst-ratelimit"
}

# =============================================================================
# MRK:03_LOG — COLOURS AND LOGGING | log,colours,logging | L312-336
# NAV-RULE: no-insert-before
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

_ts()  { date +'%Y%m%d_%H%M%S'; }
_now() { date +'%Y-%m-%d %H:%M:%S'; }

# Resolve EVIDENCE_BASE to absolute path now, before LOG_FILE is set.
# db_nmap inside msfconsole uses the rc file's paths verbatim  if msfconsole
# inherits a different CWD, relative paths would point to the wrong location.
[[ "$EVIDENCE_BASE" != /* ]] && EVIDENCE_BASE="$(pwd)/${EVIDENCE_BASE}"

SESSION_TS="$(_ts)"
LOG_FILE="${EVIDENCE_BASE}/_sweep/scan_${SESSION_TS}.log"

log()     { local m="[$(_now)] $1";    echo -e "${BLUE}${m}${NC}"   >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_ok()  { local m="[$(_now)] [OK] $1"; echo -e "${GREEN}${m}${NC}"  >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_warn(){ local m="[$(_now)] [WARN] $1"; echo -e "${YELLOW}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_err() { local m="[$(_now)] [ERR] $1"; echo -e "${RED}${m}${NC}"    >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_info(){ local m="[$(_now)]   $1"; echo -e "${CYAN}${m}${NC}"   >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }

# =============================================================================
# MRK:03_ARGS — ARGUMENT PARSING | args,argument,parsing | L337-378
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

PHASE="all"
CONTINUE_MODE=0 # tbd?
AUTO_YES=0      # default: always prompt for scope confirmation (use --yes to skip)
DRY_RUN=0
MASSCAN_ONLY=0
REUSE_WORKSPACE=0   # default: rename existing workspace to archive and create fresh
USE_DECOYS=0
IDLE_SCAN_ZOMBIE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)         MODE="$2"; shift 2 ;;
        --phase)        PHASE="$2"; shift 2 ;;
        --continue)     CONTINUE_MODE=1; shift ;;
        --tier)         GLOBAL_TIER="$2"; shift 2 ;;
        --yes)          AUTO_YES=1; shift ;;
        --dry-run)      DRY_RUN=1; shift ;;
        --masscan-only) MASSCAN_ONLY=1; shift ;;
        --reuse-workspace) REUSE_WORKSPACE=1; shift ;;
        --decoys)       USE_DECOYS=1; shift ;;
        --idle-scan)    IDLE_SCAN_ZOMBIE="$2"; shift 2 ;;
        *) log_err "Unknown argument: $1"; exit 1 ;;
    esac
done

# PTE: always load from targets.txt (produced by 01_dns_recon.sh).
# This is the canonical target list  includes DNS-resolved IPs, provided IPs,
# and live-verified hosts. TARGET_IPS in pt-orc.conf feeds 01_dns_recon only.
if [[ "$MODE" == "pte" ]]; then
    if [[ -f "$PTE_TARGETS_FILE" ]]; then
        TARGET_IPS=$(grep -v '^\s*#' "$PTE_TARGETS_FILE" | grep -v '^\s*$' | tr '\n' ' ' | xargs)
        log_ok "PTE: loaded $(echo "$TARGET_IPS" | wc -w) targets from ${PTE_TARGETS_FILE}"
    else
        log_warn "PTE: ${PTE_TARGETS_FILE} not found  run 01_dns_recon.sh first"
    fi
fi

# =============================================================================
# MRK:03_DIRS — DIRECTORY STRUCTURE SETUP | dirs,directory,structure,setup | L379-402
# NAV-RULE: no-insert-before
# =============================================================================
# evidence/
#   _sweep/           host discovery, full subnet scans, MSF exports
#   _msf/             MSF spool logs
#   _exports/         MSF DB CSV exports
#   <IP>/             per-host targeted enum output


setup_dirs() {
    mkdir -p "${EVIDENCE_BASE}/_sweep" \
             "${EVIDENCE_BASE}/_msf" \
             "${EVIDENCE_BASE}/_exports" \
             "${EVIDENCE_BASE}/_captures" \
             "${EVIDENCE_BASE}/_dns" \
             working
    # Per-IP dirs created lazily via ip_dir() as hosts are processed
}

ip_dir() { local ip="$1"; mkdir -p "${EVIDENCE_BASE}/${ip}"; echo "${EVIDENCE_BASE}/${ip}"; }


# =============================================================================
# MRK:03_DB — MSF / POSTGRES DB HELPERS | db,msf,postgres,helpers | L403-462
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

# Read MSF DB credentials from database.yml
MSF_DB_CONF="/usr/share/metasploit-framework/config/database.yml"
# Always TCP to 127.0.0.1  Unix socket requires peer auth (OS user must be 'msf'),
# which fails when running as root or any other user. TCP uses password auth (md5/scram).
MSF_DB_USER="msf"; MSF_DB_NAME="msf"; MSF_DB_HOST="127.0.0.1"; MSF_DB_PORT="5432"
# 0 = psql cannot reach the DB at all; phases use gnmap/CSV fallbacks instead
DB_DIRECT_AVAILABLE=1

parse_db_conf() {
    if [[ -f "$MSF_DB_CONF" ]]; then
        MSF_DB_USER=$(grep -m1 'username:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "msf")
        MSF_DB_NAME=$(grep -m1 'database:'  "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "msf")
        MSF_DB_PORT=$(grep -m1 'port:'      "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" || echo "5432")
        # Note: we intentionally ignore the 'host:' field from database.yml and always
        # use 127.0.0.1  the yaml may say 'localhost' which resolves to the Unix socket
        # on some Kali builds, triggering peer auth failure.
        MSF_DB_HOST="127.0.0.1"
        if [[ -z "${MSF_DB_PASS:-}" ]]; then
            MSF_DB_PASS=$(grep -m1 'password:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"" 2>/dev/null || true)
        fi
        export MSF_DB_PASS
    fi

    #  Connection test (TCP only) 
    local _test
    _test=$(PGPASSWORD="${MSF_DB_PASS:-}" psql \
        -h "$MSF_DB_HOST" -p "$MSF_DB_PORT" \
        -U "$MSF_DB_USER" -d "$MSF_DB_NAME" \
        -t -A -c "SELECT 1;" 2>&1)
    if [[ "$_test" == *"1"* && "$_test" != *"error"* && "$_test" != *"FATAL"* ]]; then
        log_ok "DB direct: TCP OK (${MSF_DB_HOST}:${MSF_DB_PORT}, user=${MSF_DB_USER}, db=${MSF_DB_NAME})"
        DB_DIRECT_AVAILABLE=1
    else
        log_warn "DB direct: TCP connection failed  psql error: $(echo "$_test" | head -1)"
        log_warn "  Phases will fall back to gnmap sweep files then configured scope"
        log_warn "  Fix: ensure postgresql is running and credentials match ${MSF_DB_CONF}"
        DB_DIRECT_AVAILABLE=0
    fi
}

# Execute a postgres query via TCP, return results (one value per line, no headers).
# Errors are logged to LOG_FILE only  callers receive empty string and trigger fallback.
db_query() {
    local _out
    _out=$(PGPASSWORD="${MSF_DB_PASS:-}" psql \
        -h "$MSF_DB_HOST" -p "$MSF_DB_PORT" \
        -U "$MSF_DB_USER" -d "$MSF_DB_NAME" -t -A -c "$1" 2>&1) || true
    # Log psql errors without breaking callers (empty return = fallback triggers normally)
    if echo "$_out" | grep -qiE 'error|fatal|could not connect|FATAL|password'; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [db_query] psql error: $(echo "$_out" | head -1)" >> "${LOG_FILE:-/dev/null}"
        return 0
    fi
    echo "$_out"
}

# =============================================================================
# MRK:03_SCAN — SCAN EXECUTION MODEL | scan,execution,model,rc,spool | L463-704
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# All db_nmap calls use msfconsole resource scripts (.rc files):
#   - msfconsole stays open for the full scan duration (no timeout wrapping nmap)
#   - spool captures full console session to evidence/_msf/<label>_<ts>.log
#   - db_nmap populates hosts/services in real time; NSE output  notes table
#   - rc file retained in evidence/_msf/ (reproducible, auditable)
#
# Usage: run_rc_scan <label> <nmap_args...>
#   label      short identifier for rc/spool filenames (e.g. tcp_ghost, smb_10.0.0.1)
#   nmap_args  passed verbatim to db_nmap; must include -oA <base>
#
# To follow progress live: tail -f evidence/_msf/<label>_<ts>.log
# =============================================================================

RC_DIR="${EVIDENCE_BASE}/_msf"

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

    # Write rc file  use printf to avoid heredoc variable expansion issues
    # workspace -a: create if missing then switch (idempotent  safe to repeat)
    {
        printf 'spool %s\n'          "$spool_file"
        printf 'workspace -a %s\n'   "$PROJECT_NAME"
        printf 'db_nmap %s\n'        "$*"
        printf 'spool off\n'
        printf 'exit\n'
    } > "$rc_file"

    log "  rc_scan [${label}]  ${rc_file}"
    log "  spool  [${label}]  ${spool_file}  (tail -f to follow)"

    # </dev/null: prevents msfconsole reading pipeline stdout as commands if rc file is missing
    PGPASSWORD="${MSF_DB_PASS:-}" msfconsole -q -r "$rc_file" </dev/null
    local rc=$?

    if [[ $rc -ne 0 ]]; then
        log_warn "  msfconsole rc=${rc} [${label}]  check: ${spool_file}"
    else
        log_ok "  rc_scan done [${label}]"
    fi
    return $rc
}

# Import one or more scan XML files into the MSF workspace in a single msfconsole
# session.  Used after parallel masscan jobs complete  avoids DB lock contention
# from simultaneous db_nmap processes.
#
# Usage: run_db_import [--db-nmap] <label> <xml_file> [<xml_file> ...]
#   --db-nmap   caller used db_nmap: data is already in workspace; missing XML is
#                expected (db_nmap uses an internal temp file, not the -oX path).
#                Downgrades missing-file messages from warn  info.
#   label      short identifier for rc/spool filenames
#   xml_files  masscan or nmap XML files to import
run_db_import() {
    local _db_nmap_mode=0
    [[ "${1:-}" == "--db-nmap" ]] && { _db_nmap_mode=1; shift; }

    local label="${1//\//_}"; shift   # sanitize label  same reason as run_rc_scan
    local -a xml_files=("$@")

    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        for f in "${xml_files[@]}"; do
            log "  [DRY RUN] would db_import: ${f}"
        done
        return 0
    fi

    # Filter to files that exist and have content (masscan writes even on empty result)
    local -a existing=()
    for f in "${xml_files[@]}"; do
        if [[ -f "$f" && -s "$f" ]]; then
            existing+=("$f")
        else
            if [[ "$_db_nmap_mode" -eq 1 ]]; then
                log_info "  db_import: XML not written by db_nmap (data already in workspace)  $(basename "$f")"
            else
                log_warn "  db_import: skipping missing/empty: $(basename "$f")"
            fi
        fi
    done
    if [[ ${#existing[@]} -eq 0 ]]; then
        if [[ "$_db_nmap_mode" -eq 1 ]]; then
            log_info "  db_import [${label}]: db_nmap imported directly  no XML reimport needed"
        else
            log_warn "  db_import [${label}]: no valid XML files  nothing to import"
        fi
        return 0
    fi

    local ts; ts="$(_ts)"
    local rc_file="${RC_DIR}/import_${label}_${ts}.rc"
    local spool_file="${RC_DIR}/import_${label}_${ts}.log"

    mkdir -p "$RC_DIR"
    {
        printf 'spool %s\n'          "$spool_file"
        printf 'workspace -a %s\n'   "$PROJECT_NAME"
        for f in "${existing[@]}"; do
            printf 'db_import %s\n' "$f"
        done
        printf 'spool off\n'
        printf 'exit\n'
    } > "$rc_file"

    log "  db_import [${label}] ${#existing[@]} file(s)  ${spool_file}"
    log "  tail -f ${spool_file}  to follow"

    PGPASSWORD="${MSF_DB_PASS:-}" msfconsole -q -r "$rc_file" </dev/null
    local rc=$?
    [[ $rc -ne 0 ]] \
        && log_warn "  db_import rc=${rc} [${label}]  check: ${spool_file}" \
        || log_ok   "  db_import done [${label}]: ${#existing[@]} file(s)"
    return $rc
}

# Get workspace ID
workspace_id() {
    db_query "SELECT id FROM workspaces WHERE name='${PROJECT_NAME}' LIMIT 1;"
}

# Get all live host IPs in workspace.
# host(address) extracts the IP string from the inet column (works for plain IPs and CIDR-
# suffixed values like 10.0.0.1/32 that masscan db_import stores). split_part(address,'/',1)
# does NOT work on inet  address is inet type, not text.
get_live_hosts() {
    # Primary: live psql query against workspace
    if [[ "${DB_DIRECT_AVAILABLE:-1}" -eq 1 ]]; then
        local wid; wid="$(workspace_id)"
        if [[ -n "$wid" ]]; then
            local hosts
            hosts=$(db_query "SELECT DISTINCT host(address) FROM hosts \
                      WHERE workspace_id=${wid} ORDER BY host(address);")
            if [[ -n "$hosts" ]]; then
                echo "$hosts"
                return
            fi
            log_info "get_live_hosts: workspace '${PROJECT_NAME}' is empty in DB  trying CSV fallback"
        else
            log_info "get_live_hosts: workspace '${PROJECT_NAME}' not found in DB  trying CSV fallback"
        fi
    fi
    # Fallback 1: read from the most recently exported hosts CSV.
    # CSV is written by export_db at end of phase_tcp  always present for later phases.
    local csv_result; csv_result="$(get_live_hosts_csv)"
    if [[ -n "$csv_result" ]]; then
        echo "$csv_result"
        return
    fi
    # Fallback 2: parse gnmap sweep files from TCP phase  written by nmap directly,
    # independent of MSF DB. Critical on fresh runs where DB was unavailable from the start.
    local gnmap_result; gnmap_result="$(get_live_hosts_gnmap)"
    if [[ -n "$gnmap_result" ]]; then
        log_info "get_live_hosts: DB and CSV empty  using gnmap sweep files ($(echo "$gnmap_result" | wc -l | tr -d ' ') host(s))"
        echo "$gnmap_result"
        return
    fi
    log_warn "get_live_hosts: no host data in DB, CSV, or gnmap sweep files"
}

# Get open TCP ports for a host.
# Matches both plain (10.0.0.1) and CIDR-suffixed (10.0.0.1/32) rows in the DB.
get_open_tcp() {
    local ip="$1"
    # Primary: live DB query
    if [[ "${DB_DIRECT_AVAILABLE:-1}" -eq 1 ]]; then
        local wid; wid="$(workspace_id)"
        if [[ -n "$wid" ]]; then
            local ports
            ports=$(db_query "SELECT port FROM services \
                      WHERE host_id=(SELECT id FROM hosts \
                                     WHERE host(address)='${ip}' \
                                     AND workspace_id=${wid} LIMIT 1) \
                      AND proto='tcp' AND state='open' ORDER BY port;")
            if [[ -n "$ports" ]]; then
                echo "$ports"
                return
            fi
            # Empty: workspace exists but no data for this host  fall to CSV
        fi
    fi
    # Fallback 1: read from the most recently exported services CSV
    local csv_result; csv_result="$(get_open_tcp_csv "$ip")"
    if [[ -n "$csv_result" ]]; then
        echo "$csv_result"
        return
    fi
    # Fallback 2: parse gnmap sweep files
    get_open_tcp_gnmap "$ip"
}

# Check if port is open on host.
# Matches both plain and CIDR-suffixed address rows.
port_open() {
    local ip="$1" port="$2" proto="${3:-tcp}"
    # Primary: live DB query
    if [[ "${DB_DIRECT_AVAILABLE:-1}" -eq 1 ]]; then
        local wid; wid="$(workspace_id)"
        if [[ -n "$wid" ]]; then
            local result
            result=$(db_query "SELECT COUNT(*) FROM services \
                      WHERE host_id=(SELECT id FROM hosts \
                                     WHERE host(address)='${ip}' \
                                     AND workspace_id=${wid} LIMIT 1) \
                      AND port=${port} AND proto='${proto}' AND state='open';")
            # Non-empty result = query executed: trust it (0=closed, >0=open)
            if [[ -n "${result// /}" ]]; then
                [[ "${result:-0}" -gt 0 ]]
                return
            fi
            # Empty = query failed (workspace has no data for this host)  fall to CSV
        fi
    fi
    # Fallback 1: check exported services CSV
    port_open_csv "$ip" "$port" "$proto" && return 0
    # Fallback 2: check gnmap sweep files
    port_open_gnmap "$ip" "$port" "$proto"
}

# Any port from list open on host
any_port_open() {
    local ip="$1"; shift
    for port in "$@"; do
        port_open "$ip" "$port" "tcp" 2>/dev/null && return 0
    done
    return 1
}

# =============================================================================
# MRK:03_CSV — CSV FALLBACK HELPERS | csv,fallback,helpers | L705-761
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# Used when DB_DIRECT_AVAILABLE=0 or workspace_id() returns empty.
# Reads from the services_tcp_*.csv exported by export_db "tcp" at end of
# phase_tcp  so data is always present by the time enum phases run.
# CSV column layout (MSF export): host,port,proto,name,state,info  (all double-quoted)

# Path to the most recently exported TCP services CSV
_latest_services_csv() {
    find "${EVIDENCE_BASE}/_exports" -name 'services_tcp_*.csv' 2>/dev/null \
        | sort | tail -1
}

# Path to the most recently exported hosts CSV
_latest_hosts_csv() {
    find "${EVIDENCE_BASE}/_exports" -name 'hosts_tcp_*.csv' 2>/dev/null \
        | sort | tail -1
}

# Return unique host IPs from the hosts CSV (one per line).
# MSF hosts CSV: address,mac,name,os_name,  addresses are double-quoted.
get_live_hosts_csv() {
    local csv; csv="$(_latest_hosts_csv)"
    [[ -z "$csv" ]] && return
    awk -F',' 'NR>1 {gsub(/"/, "", $1); if ($1~/^[0-9]/) print $1}' "$csv" \
        2>/dev/null | sort -u -t. -k1,1n -k2,2n -k3,3n -k4,4n
}

# Return open TCP ports for an IP from the services CSV (one port per line).
# Columns: host($1),port($2),proto($3),name($4),state($5),info($6)  all double-quoted.
get_open_tcp_csv() {
    local ip="$1"
    local csv; csv="$(_latest_services_csv)"
    [[ -z "$csv" ]] && return
    awk -F',' -v ip="$ip" 'NR>1 {
        gsub(/"/, "", $1); gsub(/"/, "", $2); gsub(/"/, "", $3); gsub(/"/, "", $5)
        if ($1==ip && $3=="tcp" && $5=="open") print $2
    }' "$csv" 2>/dev/null
}

# Return true (0) if port/proto is open in the services CSV.
# Columns: host($1),port($2),proto($3),name($4),state($5),info($6)  all double-quoted.
port_open_csv() {
    local ip="$1" port="$2" proto="${3:-tcp}"
    local csv; csv="$(_latest_services_csv)"
    [[ -z "$csv" ]] && return 1
    awk -F',' -v ip="$ip" -v p="$port" -v pr="$proto" '
        BEGIN{found=0}
        NR>1 {
            gsub(/"/, "", $1); gsub(/"/, "", $2); gsub(/"/, "", $3); gsub(/"/, "", $5)
            if ($1==ip && $2==p && $3==pr && $5=="open") found=1
        }
        END{exit !found}' "$csv" 2>/dev/null
}

# =============================================================================
# MRK:03_GNMAP — GNMAP FALLBACK | gnmap,fallback,parse,tcp,sweep | L762-837
# NAV-RULE: no-insert-before; read-toc-first
# both empty (e.g. fresh run where MSF DB connection was unavailable).
# Uses tcp_deep_*.gnmap and nse_common_*.gnmap  richest port/service data.
# gnmap line format: Host: IP (hostname)\tPorts: port/state/proto//svc///,...
# =============================================================================

# List all tcp_deep + nse_common gnmap files (all timestamps  merge for best coverage)
_sweep_gnmaps() {
    find "${EVIDENCE_BASE}/_sweep" \
        \( -name 'tcp_deep_*.gnmap' -o -name 'nse_common_*.gnmap' \) \
        2>/dev/null | sort
}

# Return unique host IPs that have at least one open port in any sweep gnmap file.
get_live_hosts_gnmap() {
    local f; f="$(_sweep_gnmaps)"
    [[ -z "$f" ]] && return
    # gnmap lines with open ports contain "/open/"; extract the IP (field 2 after "Host: ")
    grep -h "^Host: " $f 2>/dev/null \
        | grep "/open/" \
        | grep -oP "^Host: \K[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" \
        | sort -u -t. -k1,1n -k2,2n -k3,3n -k4,4n
}

# Return open TCP ports for an IP from sweep gnmap files (one port per line).
get_open_tcp_gnmap() {
    local ip="$1"
    local f; f="$(_sweep_gnmaps)"
    [[ -z "$f" ]] && return
    grep -h "^Host: ${ip} \|^Host: ${ip}\t" $f 2>/dev/null \
        | grep -oP "[0-9]+/open/tcp" \
        | cut -d/ -f1 \
        | sort -un
}

# Return true (0) if port/proto is open in any sweep gnmap file.
port_open_gnmap() {
    local ip="$1" port="$2" proto="${3:-tcp}"
    local f; f="$(_sweep_gnmaps)"
    [[ -z "$f" ]] && return 1
    grep -h "^Host: ${ip} \|^Host: ${ip}\t" $f 2>/dev/null \
        | grep -qP "${port}/open/${proto}"
}

# Export MSF DB  hosts, services, AND notes  per phase via rc file.
# Notes contain all NSE script output from db_nmap --script runs. Critical.
# Usage: export_db <phase_label>
export_db() {
    local phase="${1:-unknown}"
    local ts; ts="$(_ts)"
    local label="${phase}_${ts}"
    local rc_file="${RC_DIR}/export_${label}.rc"
    local spool_file="${RC_DIR}/export_${label}.log"

    mkdir -p "$RC_DIR" "${EVIDENCE_BASE}/_exports"

    {
        printf 'spool %s\n'          "$spool_file"
        printf 'workspace -a %s\n'   "$PROJECT_NAME"
        printf 'hosts    -o %s/_exports/hosts_%s.csv\n'    "$EVIDENCE_BASE" "$label"
        printf 'services -o %s/_exports/services_%s.csv\n' "$EVIDENCE_BASE" "$label"
        printf 'notes    -o %s/_exports/notes_%s.csv\n'    "$EVIDENCE_BASE" "$label"
        printf 'spool off\n'
        printf 'exit\n'
    } > "$rc_file"

    log "Exporting MSF DB (${phase})..."
    PGPASSWORD="${MSF_DB_PASS:-}" msfconsole -q -r "$rc_file" </dev/null >/dev/null 2>&1 \
        && log_ok "Exported: hosts_${label}.csv | services_${label}.csv | notes_${label}.csv" \
        || log_warn "MSF export may have partial results (${phase})  check ${spool_file}"
}



# =============================================================================
# MRK:03_SCOPE — TIER RESOLUTION | scope,tier,resolution | L838-933
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# Two levels  highest priority first:
#   1. SUBNET_TIER_MAP entry whose CIDR contains the target IP
#   2. GLOBAL_TIER  fallback when no map entry matches
#
# No per-IP overrides. No Python dependency  pure bash arithmetic CIDR check.

# Returns 0 (true) if IP is within CIDR, 1 otherwise.
ip_in_cidr() {
    local ip="$1" cidr="$2"
    local net="${cidr%/*}" prefix="${cidr#*/}"
    local a b c d
    IFS='.' read -r a b c d <<< "$ip";  local ip_int=$(( (a<<24)+(b<<16)+(c<<8)+d ))
    IFS='.' read -r a b c d <<< "$net"; local net_int=$(( (a<<24)+(b<<16)+(c<<8)+d ))
    local mask=$(( prefix > 0 ? (0xFFFFFFFF << (32-prefix)) & 0xFFFFFFFF : 0 ))
    [[ $(( ip_int & mask )) -eq $(( net_int & mask )) ]]
}

# Resolve tier for a host IP  checks SUBNET_TIER_MAP, falls back to GLOBAL_TIER.
resolve_tier() {
    local target="$1"
    for entry in "${SUBNET_TIER_MAP[@]}"; do
        [[ "$entry" == \#* ]] && continue
        local cidr="${entry%%:*}" stier="${entry##*:}"
        ip_in_cidr "$target" "$cidr" && { echo "$stier"; return; }
    done
    echo "$GLOBAL_TIER"
}

# Resolve tier for a subnet CIDR  exact map lookup, falls back to GLOBAL_TIER.
# Used in phase_tcp where we group whole subnets, not individual IPs.
resolve_subnet_tier() {
    local subnet="$1"
    for entry in "${SUBNET_TIER_MAP[@]}"; do
        [[ "$entry" == \#* ]] && continue
        local cidr="${entry%%:*}" stier="${entry##*:}"
        [[ "$subnet" == "$cidr" ]] && { echo "$stier"; return; }
    done
    echo "$GLOBAL_TIER"
}

# Human-readable tier model summary for banners and logs.
effective_tier_label() {
    local subnet_count=0
    for entry in "${SUBNET_TIER_MAP[@]}"; do
        [[ "$entry" == \#* ]] && continue
        (( subnet_count++ ))
    done
    local parts=()
    [[ $subnet_count -gt 0 ]] && parts+=("${subnet_count} subnet(s)")
    parts+=("global=${GLOBAL_TIER}")
    local IFS=' | '
    echo "${parts[*]}"
}

# Build combined target list from TARGET_SUBNETS + TARGET_IPS (both may be empty)
build_target_list() {
    local targets=()
    for s in $TARGET_SUBNETS; do targets+=("$s"); done
    for ip in $TARGET_IPS;    do targets+=("$ip"); done
    if [[ ${#targets[@]} -eq 0 ]]; then
        log_err "No targets defined. Set TARGET_SUBNETS and/or TARGET_IPS in the script."
        exit 1
    fi
    printf '%s\n' "${targets[@]}"
}

# Space-separated combined target string for nmap invocation
all_targets() { build_target_list | tr '\n' ' '; }

# Build complete nmap flags for a tier.
# version-intensity is included here  callers must NOT append it separately.
# skip_idle=1 suppresses -sI injection; pass 1 for UDP/enum phases where idle
# scan does not apply (it is TCP-only). phase_tcp handles -sI via scan_type.
nmap_tier_flags() {
    local tier="$1"
    local skip_idle="${2:-0}"   # 1 = do not inject -sI (UDP, enum, discovery)
    local flags
    flags="$(tier_nmap_timing "$tier") \
           $(tier_min_rate "$tier") \
           $(tier_max_rate "$tier") \
           $(tier_min_hostgroup "$tier") \
           $(tier_max_retries "$tier") \
           $(tier_host_timeout "$tier") \
           $(tier_script_timeout "$tier") \
           $(tier_version_intensity "$tier") \
           $(tier_evasion_flags "$tier")"
    [[ "${USE_DECOYS:-0}" -eq 1 ]] && flags+=" -D RND:5"
    [[ -n "${IDLE_SCAN_ZOMBIE:-}" && "$skip_idle" -eq 0 ]] && flags+=" -sI ${IDLE_SCAN_ZOMBIE}"
    # Collapse multiple spaces left by empty substitutions
    echo "$flags" | tr -s ' '
}

# =============================================================================
# MRK:03_SRCIP — SOURCE IP VERIFICATION (PTE) | srcip,source,ip,verification,pte | L934-955
# NAV-RULE: no-insert-before
# =============================================================================

verify_source_ip() {
    [[ "$MODE" != "pte" ]] && return 0
    [[ -z "${TESTER_IP:-}" ]] && { log_warn "TESTER_IP not set  skipping source IP verification"; return 0; }
    log "Verifying outbound source IP..."
    local actual_ip
    actual_ip=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || \
                dig +short myip.opendns.com @resolver1.opendns.com 2>/dev/null || \
                echo "unknown")
    if [[ "$actual_ip" == "$TESTER_IP" ]]; then
        log_ok "Source IP verified: ${actual_ip}"
    else
        log_err "SOURCE IP MISMATCH  actual: ${actual_ip} | expected: ${TESTER_IP}"
        log_err "Check VPN / interface before proceeding. Aborting."
        exit 1
    fi
}

# =============================================================================
# MRK:03_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L956-989
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

scope_confirm() {
    [[ "${AUTO_YES:-0}" -eq 1 ]] && return 0
    local all_targets; all_targets="$(all_targets 2>/dev/null || echo "[none]")"
    local target_count; target_count=$(echo "$all_targets" | wc -w | tr -d ' ')
    echo ""
    echo -e "\033[1m\033[1;33m\033[0m"
    echo -e "\033[1m  SCOPE CONFIRMATION  03_comp_scan.sh v0.8\033[0m"
    echo -e "\033[1m\033[1;33m\033[0m"
    printf "  %-20s %s\n" "Project:"     "$PROJECT_NAME"
    printf "  %-20s %s\n" "Mode:"        "$MODE"
    printf "  %-20s %s\n" "Tier:"        "$(effective_tier_label)$([ "${USE_DECOYS:-0}" -eq 1 ] && echo " +decoys")"
    printf "  %-20s %s\n" "Phase:"       "$PHASE"
    printf "  %-20s %s\n" "Subnets:"     "${TARGET_SUBNETS:-[none]}"
    printf "  %-20s %s\n" "IPs:"         "${TARGET_IPS:-[none]}"
    printf "  %-20s %s\n" "Target count:" "$target_count"
    printf "  %-20s %s\n" "Tester IP:"   "${TESTER_IP:-[not verified]}"
    printf "  %-20s %s\n" "Excluded IPs:" "${EXCLUDE_IPS[*]:-[none detected yet]}"
    printf "  %-20s %s\n" "Dry run:"     "$([ "$DRY_RUN" -eq 1 ] && echo "YES" || echo "no")"
    [[ -n "${IDLE_SCAN_ZOMBIE:-}" ]] && printf "  %-20s %s\n" "Idle scan via:" "$IDLE_SCAN_ZOMBIE"
    echo -e "\033[1m\033[1;33m\033[0m"
    echo ""
    echo -e "\033[1mConfirm authorisation is in place and scope is correct.\033[0m"
    echo -n "  Type YES to continue: "
    read -r answer
    [[ "$answer" != "YES" ]] && { echo "Aborted."; exit 0; }
    echo ""
}


# =============================================================================
# MRK:03_RATE — RATE SELF-TEST (PTE / evasion mode) | rate,self,test,pte,evasion | L990-1023
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
rate_self_test() {
    [[ "$MODE" != "pte" ]] && return 0
    local first_target
    first_target=$(all_targets 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]' | head -1)
    [[ -z "$first_target" ]] && return 0

    #  Rate self-test sends REAL SYN probes to the first target 
    # This is an intentional network touch to validate tier/rate settings before
    # the full scan. The target is a live production host  ensure RoE covers this.
    log_warn "Rate self-test: about to send 10 SYN probes to live target: ${first_target}"
    log_warn "  Tier: ${GLOBAL_TIER} | Purpose: validate connectivity and response rate"
    log_warn "  This is a real network probe to a production host  confirm RoE covers this."
    if [[ "${AUTO_YES:-0}" -ne 1 ]]; then
        echo -n "  Press ENTER to send probes, or Ctrl-C to abort: "
        read -r _dummy
    fi

    log "Rate self-test: 10 probes to ${first_target} [${GLOBAL_TIER} tier]..."
    local flags; flags="$(nmap_tier_flags "$GLOBAL_TIER" 1)"
    local result
    result=$(nmap -Pn -sS --top-ports 10 $flags "$first_target" \
             2>/dev/null | grep -cE "open|closed|filtered" || echo 0)
    if [[ "$result" -eq 0 ]]; then
        log_warn "Rate self-test: no responses  target may be rate-limiting or blocked"
        [[ "$GLOBAL_TIER" != "evasion" ]] && log_warn "Consider re-running with --tier evasion"
    else
        log_ok "Rate self-test: ${result} port responses  tier ${GLOBAL_TIER} OK"
    fi
}

# =============================================================================
# MRK:03_WS — MSF WORKSPACE SETUP | ws,msf,workspace,setup | L1024-1111
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

# List all MSF workspaces as bare names (one per line).
# Strips ANSI codes, leading "* " active-marker, surrounding whitespace, and
# blank/header lines.  Safe to call multiple times  each call starts msfconsole
# fresh (60s timeout).
_msf_list_workspaces() {
    PGPASSWORD="${MSF_DB_PASS:-}" timeout 60s \
        msfconsole -q -x "workspace -l; exit" </dev/null 2>/dev/null \
    | sed 's/\x1b\[[0-9;]*[mGKHF]//g' \
    | sed 's/^[[:space:]]*\*[[:space:]]*//' \
    | sed 's/^[[:space:]]*//' \
    | sed 's/[[:space:]]*$//' \
    | grep -v '^$' \
    | grep -v '^msf' \
    | grep -v '^\[' || true
}

# Return 1 if NAME exists in the workspace list (exact full-line match).
_msf_workspace_exists() {
    local name="$1"
    _msf_list_workspaces | grep -Fxq "$name"
}

ensure_workspace() {
    log "Verifying MSF workspace: ${PROJECT_NAME}"
    if ! command -v msfconsole >/dev/null 2>&1; then
        log_err "msfconsole not found"; exit 1
    fi

    #  Collision check: workspace already exists from a prior run
    # Default behaviour: rename it to PROJECT_NAME_HHMM (archive prior run data)
    # and create a fresh workspace for this run.
    # --reuse-workspace: skip rename, reuse in-place so prior hosts/services/ports
    # remain available (e.g. ARP-discovered hosts feeding phase_tcp narrowing on
    # a restart after the fast-scan backend was changed).
    if _msf_workspace_exists "$PROJECT_NAME"; then
        if [[ "${REUSE_WORKSPACE:-0}" -eq 1 ]]; then
            log_ok "Reusing existing workspace: ${PROJECT_NAME} (--reuse-workspace)"
            # Verify we can select it, then return  skip the "create fresh" block below.
            PGPASSWORD="${MSF_DB_PASS:-}" timeout 60s \
                msfconsole -q -x "workspace ${PROJECT_NAME}; exit" \
                </dev/null 2>&1 \
                | sed 's/\x1b\[[0-9;]*[mGKHF]//g' >> "$LOG_FILE" || true
            log_ok "Workspace ready: ${PROJECT_NAME}"
            return 0
        fi
        local stamp; stamp=$(date +%H%M)
        local archived="${PROJECT_NAME}_${stamp}"
        log_warn "Workspace '${PROJECT_NAME}' already exists (prior run detected)"
        log_warn "  Renaming  '${archived}' to preserve earlier run data"
        PGPASSWORD="${MSF_DB_PASS:-}" timeout 60s \
            msfconsole -q -x "workspace -r ${PROJECT_NAME} ${archived}; exit" \
            </dev/null 2>&1 \
            | sed 's/\x1b\[[0-9;]*[mGKHF]//g' >> "$LOG_FILE" || true
        # Confirm rename landed
        if _msf_workspace_exists "$archived"; then
            log_ok "Prior workspace archived as: ${archived}"
        else
            log_warn "  Could not confirm rename  prior data may still be in '${PROJECT_NAME}'"
        fi
    fi

    #  Create fresh workspace 
    # workspace -a: create-and-switch, idempotent  same command used in all RC files.
    log "Creating workspace: ${PROJECT_NAME}"
    PGPASSWORD="${MSF_DB_PASS:-}" timeout 60s \
        msfconsole -q -x "workspace -a ${PROJECT_NAME}; exit" \
        </dev/null 2>&1 \
        | sed 's/\x1b\[[0-9;]*[mGKHF]//g' >> "$LOG_FILE" || true

    #  Verify 
    if _msf_workspace_exists "$PROJECT_NAME"; then
        log_ok "Workspace ready: ${PROJECT_NAME}"
    else
        log_warn "ensure_workspace: could not verify '${PROJECT_NAME}' after creation"
        log_warn "  RC files use 'workspace -a'  workspace will be created on first scan."
        log_warn "  Create manually: msfconsole -q -x \"workspace -a ${PROJECT_NAME}; exit\""
        # Do NOT abort  workspace -a in every RC file handles it.
    fi

    local spool="${EVIDENCE_BASE}/_msf/${SESSION_TS}_console.log"
    echo "MSF spool path: ${spool}" >> "$LOG_FILE"
}

# =============================================================================
# MRK:03_EXCL — TESTER EXCLUSION | excl,tester,exclusion | L1112-1415
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# All local IPv4 addresses are auto-detected at startup (covers multiple NICs
# and VPN tunnels simultaneously). TESTER_EXCLUDE_IPS adds manual entries on
# top, e.g. a jump box or a secondary test host not reachable from this machine.
#
# nmap_exclude_args()  produces --exclude <csv> for every scan that takes a
#                       range/subnet (discovery, tcp passes).
# get_scan_hosts()     wraps get_live_hosts() filtering tester IPs so they
#                       never enter udp/enum phase processing.

EXCLUDE_IPS=()   # populated by init_exclude_list  do not edit directly

init_exclude_list() {
    local detected=()

    # Auto-detect all local IPv4 addresses; skip loopback
    while IFS= read -r ip; do
        [[ -n "$ip" ]] && detected+=("$ip")
    done < <(
        ip -4 addr show 2>/dev/null \
            | grep -oP '(?<=inet\s)\d+(\.\d+){3}' \
            | grep -v '^127\.' \
        || hostname -I 2>/dev/null \
            | tr ' ' '\n' \
            | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' \
            | grep -v '^127\.'
    )

    # Merge with manual TESTER_EXCLUDE_IPS
    local combined=("${detected[@]}")
    for ip in $TESTER_EXCLUDE_IPS; do combined+=("$ip"); done

    # Deduplicate into global EXCLUDE_IPS
    while IFS= read -r ip; do
        [[ -n "$ip" ]] && EXCLUDE_IPS+=("$ip")
    done < <(printf '%s\n' "${combined[@]}" | sort -u)

    if [[ ${#EXCLUDE_IPS[@]} -gt 0 ]]; then
        log_ok "Tester exclusions (${#EXCLUDE_IPS[@]}): ${EXCLUDE_IPS[*]}"
    else
        log_warn "Tester exclusion: no local IPs detected  auto-exclusion disabled"
    fi
}

# Returns --exclude <ip,...> for nmap if EXCLUDE_IPS is non-empty, else empty string.
nmap_exclude_args() {
    [[ ${#EXCLUDE_IPS[@]} -eq 0 ]] && return
    local csv; csv=$(printf '%s,' "${EXCLUDE_IPS[@]}" | sed 's/,$//')
    echo "--exclude ${csv}"
}

# Returns --excludefile <path> for masscan if EXCLUDE_IPS is non-empty.
# masscan reads one IP/CIDR per line from the exclude file.
masscan_exclude_args() {
    [[ ${#EXCLUDE_IPS[@]} -eq 0 ]] && return
    local excl_file="${EVIDENCE_BASE}/_sweep/masscan_excludes.txt"
    printf '%s\n' "${EXCLUDE_IPS[@]}" > "$excl_file"
    echo "--excludefile ${excl_file}"
}

naabu_exclude_args() {
    [[ ${#EXCLUDE_IPS[@]} -eq 0 ]] && return
    local excl_file="${EVIDENCE_BASE}/_sweep/naabu_excludes.txt"
    printf '%s\n' "${EXCLUDE_IPS[@]}" > "$excl_file"
    echo "-exclude-file ${excl_file}"
}

# Convert dotted IPv4 to integer for simple CIDR host selection.
ipv4_to_int() {
    local a b c d
    IFS=. read -r a b c d <<< "$1"
    echo $(( (a << 24) | (b << 16) | (c << 8) | d ))
}

# Convert integer back to dotted IPv4.
int_to_ipv4() {
    local ip_int="$1"
    printf '%d.%d.%d.%d\n' \
        $(( (ip_int >> 24) & 255 )) \
        $(( (ip_int >> 16) & 255 )) \
        $(( (ip_int >> 8) & 255 )) \
        $(( ip_int & 255 ))
}

# Choose one routable IPv4 from a target token so ip route can resolve the egress path.
route_probe_ip_for_target() {
    local target="$1"

    if [[ "$target" != */* ]]; then
        echo "$target"
        return 0
    fi

    local network="${target%/*}"
    local prefix="${target#*/}"

    [[ "$prefix" =~ ^[0-9]+$ ]] || return 1
    (( prefix >= 0 && prefix <= 32 )) || return 1

    if (( prefix >= 31 )); then
        echo "$network"
        return 0
    fi

    local network_int probe_int
    network_int=$(ipv4_to_int "$network") || return 1
    probe_int=$(( network_int + 1 ))
    int_to_ipv4 "$probe_int"
}

# If a target belongs to a directly attached subnet, use that interface and
# source IP only. On-link scans should not invent a gateway/router hint such as
# "network+1" because that can steer masscan to a non-existent next hop.
masscan_local_link_args_for_target() {
    local target="$1"
    local probe_ip line dev cidr src
    probe_ip="$(route_probe_ip_for_target "$target")" || return 1

    while IFS= read -r line; do
        dev="$(awk '{print $2}' <<< "$line")"
        cidr="$(awk '{for (i=1; i<=NF; i++) if ($i=="inet") { print $(i+1); exit }}' <<< "$line")"
        src="${cidr%/*}"
        [[ -n "$dev" && -n "$cidr" && -n "$src" ]] || continue
        if ip_in_cidr "$probe_ip" "$cidr"; then
            printf '%s|%s|\n' "$dev" "$src"
            return 0
        fi
    done < <(ip -o -4 addr show up scope global 2>/dev/null)

    return 1
}

# Resolve per-target masscan routing args so multi-homed testers hit the correct path.
masscan_route_args_for_target() {
    local target="$1"
    local probe_ip route_line dev src via
    local local_link

    if local_link="$(masscan_local_link_args_for_target "$target")"; then
        printf '%s\n' "$local_link"
        return 0
    fi

    probe_ip="$(route_probe_ip_for_target "$target")" || return 1
    route_line="$(ip -o -4 route get "$probe_ip" 2>/dev/null | head -n1)" || return 1
    [[ -n "$route_line" ]] || return 1

    dev="$(awk '{for (i=1; i<=NF; i++) if ($i=="dev") { print $(i+1); exit }}' <<< "$route_line")"
    src="$(awk '{for (i=1; i<=NF; i++) if ($i=="src") { print $(i+1); exit }}' <<< "$route_line")"
    via="$(awk '{for (i=1; i<=NF; i++) if ($i=="via") { print $(i+1); exit }}' <<< "$route_line")"

    [[ -n "$dev" ]] || return 1
    [[ -n "$src" ]] || return 1

    printf '%s|%s|%s\n' "$dev" "$src" "$via"
}

# masscan needs a single destination MAC. For directly attached CIDR sweeps on an
# interface that has no gateway, that model breaks down: there is no router MAC to
# use, and forcing one host's MAC would misdirect the rest of the subnet. Those
# targets should use the nmap full-scan path instead.
masscan_supported_for_target() {
    local target="$1"
    local route_info route_dev route_src route_via

    [[ "$target" != */* ]] && return 0

    route_info="$(masscan_route_args_for_target "$target" 2>/dev/null)" || return 0
    IFS='|' read -r route_dev route_src route_via <<< "$route_info"
    [[ -n "$route_via" ]]
}

fast_xml_find_expr() {
    printf "%s\n" "-name 'masscan_fast_*.xml' -o -name 'naabu_fast_*.xml'"
}

naabu_json_to_nmap_xml() {
    local jsonl="$1" out_xml="$2"
    local epoch now host_count=0 tmp_pairs
    epoch="$(date +%s)"
    now="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    tmp_pairs="$(mktemp)"

    awk '
        match($0, /"ip":"([^"]+)"/, a) && match($0, /"port":([0-9]+)/, b) {
            print a[1], b[1]
        }
    ' "$jsonl" 2>/dev/null | sort -u -k1,1 -k2,2n > "$tmp_pairs"

    {
        printf '<?xml version="1.0"?>\n'
        printf '<!DOCTYPE nmaprun>\n'
        printf '<nmaprun scanner="naabu" start="%s" startstr="%s" version="fast-import" xmloutputversion="1.05">\n' "$epoch" "$now"
        local current_ip="" ip port
        while read -r ip port; do
            [[ -n "$ip" && -n "$port" ]] || continue
            if [[ "$ip" != "$current_ip" ]]; then
                if [[ -n "$current_ip" ]]; then
                    printf '    </ports>\n'
                    printf '  </host>\n'
                fi
                current_ip="$ip"
                (( host_count++ )) || true
                printf '  <host starttime="%s" endtime="%s">\n' "$epoch" "$epoch"
                printf '    <status state="up" reason="syn-ack"/>\n'
                printf '    <address addr="%s" addrtype="ipv4"/>\n' "$current_ip"
                printf '    <ports>\n'
            fi
            printf '      <port protocol="tcp" portid="%s"><state state="open" reason="syn-ack"/></port>\n' "$port"
        done < "$tmp_pairs"
        if [[ -n "$current_ip" ]]; then
            printf '    </ports>\n'
            printf '  </host>\n'
        fi

        printf '  <runstats><finished time="%s" timestr="%s"/><hosts up="%s" down="0" total="%s"/></runstats>\n' "$epoch" "$now" "$host_count" "$host_count"
        printf '</nmaprun>\n'
    } > "$out_xml"
    rm -f "$tmp_pairs"
}

# get_live_hosts() with tester IPs removed  used by udp/enum phases.
get_scan_hosts() {
    if [[ ${#EXCLUDE_IPS[@]} -eq 0 ]]; then
        get_live_hosts
        return
    fi
    get_live_hosts | grep -vxF -f <(printf '%s\n' "${EXCLUDE_IPS[@]}")
}

# Returns 0 if <cidr|ip> is on-link (L2-adjacent, no gateway), 1 if routed via a
# gateway or the route lookup fails. Used by phase_tcp narrowing to decide whether
# ARP-discovered hosts can be trusted as a complete view of the subnet.
# Probes with a representative address within the range: for CIDRs uses .1 of the
# network; for bare IPs uses the IP itself.
is_subnet_onlink() {
    local cidr="$1"
    local net="${cidr%/*}"
    local probe
    if [[ "$cidr" == */32 || "$cidr" != */* ]]; then
        probe="$net"
    else
        probe="${net%.*}.1"
    fi
    local rt; rt="$(ip route get "$probe" 2>/dev/null | head -1)"
    [[ -z "$rt" ]] && return 1
    [[ "$rt" != *" via "* ]]
}

# Filters an incoming newline-separated list of IPs (stdin) to those inside <cidr>.
# Uses python3 (guaranteed on Kali) for correct CIDR arithmetic across any prefix.
# If python3 is unavailable, falls back to crude string-prefix match for /24 only
# (any non-/24 input is passed through unfiltered  safer than silently dropping).
_filter_hosts_in_cidr() {
    local cidr="$1"
    if command -v python3 &>/dev/null; then
        python3 -c '
import sys, ipaddress
try:
    net = ipaddress.ip_network(sys.argv[1], strict=False)
except ValueError:
    sys.exit(0)
for line in sys.stdin:
    ip = line.strip()
    if not ip:
        continue
    try:
        if ipaddress.ip_address(ip) in net:
            print(ip)
    except ValueError:
        pass
' "$cidr"
    else
        # Fallback without python3: only /24 can be filtered safely with pure bash.
        # For any other prefix length return empty  phase_tcp will see "no live
        # hosts" and fall back to full-CIDR scan (correct, just un-narrowed).
        if [[ "$cidr" == */24 ]]; then
            local prefix="${cidr%.*/24}"
            grep -E "^${prefix//./\\.}\.[0-9]{1,3}$" || true
        else
            cat >/dev/null
            log_warn "python3 not available and CIDR ${cidr} is not /24  narrowing disabled for this subnet" >&2
        fi
    fi
}

# ARP-discovered (and prior-session) live hosts within <cidr>, from MSF workspace.
# Space-separated output (consumable by tier_targets accumulator).
live_hosts_in_subnet() {
    local cidr="$1"
    get_scan_hosts 2>/dev/null | _filter_hosts_in_cidr "$cidr" | tr '\n' ' '
}

# Explicit TARGET_IPS (operator-listed) that fall within <cidr>. Used to union
# with ARP results so operator-listed IPs never drop out if ARP missed them.
list_target_ips_in_subnet() {
    local cidr="$1"
    [[ -z "${TARGET_IPS// }" ]] && return
    printf '%s\n' $TARGET_IPS | _filter_hosts_in_cidr "$cidr" | tr '\n' ' '
}

# =============================================================================
# MRK:03_P1 — PHASE 1: DISCOVERY | p1,phase,discovery | L1416-1449
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

# OPTIONAL  disabled by default. Use --phase discovery to run explicitly.
# Uses ARP-only sweep (-PR)  the only reliable passive discovery on local segments.
# TCP SYN scan (phase_tcp) is the primary host discovery method for this engagement.
phase_discovery() {
    log "=== PHASE 1: HOST DISCOVERY (optional ARP sweep) ==="
    local ts; ts="$(_ts)"
    local out="${EVIDENCE_BASE}/_sweep/sweep_arp_${ts}"
    local targets; targets="$(all_targets)"

    if [[ -z "$targets" ]]; then
        log_err "No targets defined for discovery"
        return 1
    fi

    # ARP-only: reliable on local segments, no ICMP/TCP probes that cause hangs
    # -Pn not used here  ARP is the probe. -sn means no port scan, host discovery only.
    # -PR forces ARP (default on local segment anyway, explicit for clarity)
    local flags; flags="$(nmap_tier_flags "ghost" 1)"
    local excl; excl="$(nmap_exclude_args)"
    log "ARP sweep: ${targets} [ghost tier, ARP-only -PR -sn]"
    run_rc_scan "arp_discovery" -PR -sn $flags $excl -oA "${out}" $targets
    log_ok "Discovery output: ${out}.{nmap,xml,gnmap}"
    export_db "discovery"

    local host_count; host_count=$(get_scan_hosts | wc -l | tr -d ' ')
    log_ok "ARP discovery complete. Live hosts (excl. tester): ${host_count}"
    echo "$host_count" > "${EVIDENCE_BASE}/_sweep/host_count.txt"
}

# =============================================================================
# MRK:03_P2 — PHASE 2: TCP FULL SCAN | p2,phase,tcp,full,scan | L1450-1796
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# Two-pass approach:
#   Pass 1  fast full-range discovery (-p-) with tier timing, no version detection.
#             Finds all open ports quickly before committing to slow version probes.
#   Pass 2  version + OS detection (-sV -O) on confirmed open ports only.
#             Version probes sent only where ports are actually open  far faster
#             than running -sV across all 65535 ports.
#
# -Pn skips ping in both passes  SYN probe IS the discovery mechanism.
# Hosts with no open TCP ports will not appear in DB  intentional.

# Extract comma-separated list of unique open TCP ports from a .gnmap file.
extract_open_ports() {
    grep "/open/" "$1" 2>/dev/null \
        | grep -oP '\d+(?=/open)' \
        | sort -un \
        | tr '\n' ',' \
        | sed 's/,$//'
}

# Extract unique open port numbers from masscan (or nmap) XML files.
# masscan XML: every <port> element is open (masscan only records open ports).
# Multiple files supported  returns the union across all inputs.
extract_open_ports_xml() {
    grep -hoP 'portid="\K\d+' "$@" 2>/dev/null \
        | sort -un \
        | tr '\n' ',' \
        | sed 's/,$//'
}

phase_tcp() {
    log "=== PHASE 2: TCP SCAN ==="
    log "Pass 1: ${FAST_TCP_SCANNER} for ghost/normal/loud; nmap for evasion"
    log "Pass 2: db_nmap version/OS scan on open ports only (per tier)"
    [[ "${MASSCAN_ONLY:-0}" -eq 1 ]] && log_warn "TCP --masscan-only mode enabled: skipping all post-fast-scan nmap phases"

    #  Build tier  target lists
    # Per-subnet decision:
    #   - on-link subnet + ARP live hosts present  narrow CIDR to live-host list
    #     (union with any TARGET_IPS falling inside subnet  operator-listed IPs
    #     are never dropped even if they missed the ARP sweep).
    #   - on-link subnet + 0 ARP hosts                full CIDR fallback (conservative).
    #   - routed subnet (via gateway)                 full CIDR (ARP can't cross L3).
    #   - USE_DISCOVERY_FOR_TCP=0                     full CIDR (escape hatch).
    # Logged per-subnet before scan starts so scope is auditable.
    declare -A tier_targets
    tier_targets["ghost"]=""
    tier_targets["normal"]=""
    tier_targets["loud"]=""
    tier_targets["evasion"]=""

    local _narrow="${USE_DISCOVERY_FOR_TCP:-1}"
    declare -A _narrowed_subnet_of_ip  # track IPs already folded into a narrowed subnet
    for subnet in $TARGET_SUBNETS; do
        local tier; tier="$(resolve_subnet_tier "$subnet")"
        if [[ "${FAST_TCP_SCANNER}" == "masscan" ]] && ! masscan_supported_for_target "$subnet"; then
            log_warn "Tier ${tier}: ${subnet} is directly attached with no gateway; using nmap Pass 1 instead of fast scanner"
            tier="evasion"
        fi

        local _scope="" _source=""
        if [[ "$_narrow" -eq 1 ]] && is_subnet_onlink "$subnet"; then
            local _live _listed
            _live="$(live_hosts_in_subnet "$subnet")"
            _listed="$(list_target_ips_in_subnet "$subnet")"
            if [[ -n "${_live// }" ]]; then
                # Union ARP-live + operator-listed IPs within subnet, deduped.
                local _union
                _union="$(printf '%s\n' $_live $_listed | awk 'NF && !seen[$0]++' | tr '\n' ' ')"
                local _live_count _listed_count
                _live_count=$(printf '%s\n' $_live   | awk 'NF' | wc -l | tr -d ' ')
                _listed_count=$(printf '%s\n' $_listed | awk 'NF' | wc -l | tr -d ' ')
                _scope="$_union"
                if [[ "$_listed_count" -gt 0 ]]; then
                    _source="on-link, ${_live_count} live (ARP) + ${_listed_count} listed"
                else
                    _source="on-link, ${_live_count} live (ARP)"
                fi
                # Mark each IP so it's not re-added by the TARGET_IPS loop below
                local _ip
                for _ip in $_union; do _narrowed_subnet_of_ip["$_ip"]="$subnet"; done
            else
                _scope="$subnet"
                _source="on-link, 0 live -- fallback to full CIDR"
            fi
        elif [[ "$_narrow" -eq 1 ]]; then
            _scope="$subnet"
            _source="routed, full CIDR"
        else
            _scope="$subnet"
            _source="narrow-disabled (USE_DISCOVERY_FOR_TCP=0)"
        fi

        log_info "TCP scope [${tier}]  ${subnet}  -> ${_source}"
        tier_targets["$tier"]+="${_scope} "
    done
    for ip in $TARGET_IPS; do
        # Skip IPs already folded into a narrowed subnet's host list (dedup).
        [[ -n "${_narrowed_subnet_of_ip[$ip]:-}" ]] && continue
        tier_targets["${GLOBAL_TIER}"]+="${ip} "
    done

    local any=0
    for tier in ghost normal loud evasion; do
        [[ -n "${tier_targets[$tier]// }" ]] || continue
        any=1
        log_info "Tier ${tier}: ${tier_targets[$tier]}"
    done
    [[ "$any" -eq 0 ]] && {
        log_err "No targets defined. Set TARGET_SUBNETS and/or TARGET_IPS."
        return 1
    }

    mkdir -p "${EVIDENCE_BASE}/_sweep"

    # Check fast scanner is available (needed for ghost/normal/loud tiers)
    local has_fast_scanner=0
    case "${FAST_TCP_SCANNER}" in
        masscan) command -v masscan &>/dev/null && has_fast_scanner=1 ;;
        naabu)   command -v naabu   &>/dev/null && has_fast_scanner=1 ;;
        db_nmap) command -v msfconsole &>/dev/null && has_fast_scanner=1 ;;
        *)       log_err "Unsupported FAST_TCP_SCANNER: ${FAST_TCP_SCANNER}"; return 1 ;;
    esac

    local session_ts; session_ts="$(_ts)"

    #  Pass 1: masscan (all ghost/normal/loud targets in parallel) 
    # Each target (CIDR or IP) from each tier gets its own masscan job.
    # Jobs run in parallel up to MAX_PARALLEL_SCANS.
    # Results imported to MSF DB in a single msfconsole db_import call after all
    # jobs finish  avoids DB lock contention from concurrent db_nmap processes.
    declare -A tier_xml_lists   # tier -> space-separated list of XML file paths
    local -a all_fast_xml=()    # global union for db_import
    local -a scan_pids=()
    local running=0

    for tier in ghost normal loud; do
        local hosts="${tier_targets[$tier]}"
        [[ -z "${hosts// }" ]] && continue
        tier_xml_lists["$tier"]=""

        if [[ "$has_fast_scanner" -eq 0 ]]; then
            log_err "${FAST_TCP_SCANNER} not found - cannot run Pass 1 for tier [${tier}]"
            continue
        fi

        local rate; rate="$(masscan_rate_for_tier "$tier")"
        local naabu_threads; naabu_threads="$(naabu_threads_for_tier "$tier")"
        local db_nmap_fast; db_nmap_fast="$(db_nmap_fast_flags "$tier")"
        local excl_args=""
        [[ "${FAST_TCP_SCANNER}" == "masscan" ]] && excl_args="$(masscan_exclude_args)"
        [[ "${FAST_TCP_SCANNER}" == "naabu"   ]] && excl_args="$(naabu_exclude_args)"
        local tier_list="${EVIDENCE_BASE}/_sweep/targets_${tier}.txt"
        echo "$hosts" | tr ' ' '\n' | grep -v '^$' > "$tier_list"
        local count; count=$(wc -l < "$tier_list" | tr -d ' ')
        if [[ "${FAST_TCP_SCANNER}" == "db_nmap" ]]; then
            log "TCP [${tier}] Pass 1 - ${count} target(s) via db_nmap fast flags: ${db_nmap_fast}"
        else
            log "TCP [${tier}] Pass 1 - ${count} target(s) @ ${rate} pps (${FAST_TCP_SCANNER})"
        fi

        if [[ "${FAST_TCP_SCANNER}" == "db_nmap" ]]; then
            local out_fast="${EVIDENCE_BASE}/_sweep/db_nmap_fast_${tier}_${session_ts}"
            local out_xml="${out_fast}.xml"
            tier_xml_lists["$tier"]+="${out_xml} "
            all_fast_xml+=("$out_xml")
            log "  db_nmap [${tier}] full-port discovery -> $(basename "$out_fast")"
            run_rc_scan "tcp_fast_db_nmap_${tier}" -sS -p- --open -Pn \
                ${db_nmap_fast} ${excl_args} -iL "$tier_list" -oA "${out_fast}"
            log_ok "TCP fast [${tier}]: ${out_fast}.{nmap,xml,gnmap}"
            continue
        fi

        while IFS= read -r target; do
            [[ -z "$target" ]] && continue

            # Throttle: block until a worker slot opens
            while [[ "$running" -ge "${MAX_PARALLEL_SCANS}" ]]; do
                wait -n 2>/dev/null || true
                (( running-- )) || true
            done

            local safe="${target//\//_}"
            local out_xml="${EVIDENCE_BASE}/_sweep/${FAST_TCP_SCANNER}_fast_${tier}_${safe}_${session_ts}.xml"
            local out_log="${EVIDENCE_BASE}/_sweep/${FAST_TCP_SCANNER}_fast_${tier}_${safe}_${session_ts}.log"
            local out_json=""
            local -a masscan_route_args=()
            tier_xml_lists["$tier"]+="${out_xml} "
            all_fast_xml+=("$out_xml")

            local route_info route_dev route_src route_via
            if [[ -n "${MASSCAN_INTERFACE:-}" ]]; then
                route_dev="${MASSCAN_INTERFACE}"
                route_src=""
                route_via=""
            else
                if route_info="$(masscan_route_args_for_target "$target")"; then
                    IFS='|' read -r route_dev route_src route_via <<< "$route_info"
                    log "  fast route [${target}] dev=${route_dev} src=${route_src:-auto} via=${route_via:-on-link}"
                else
                    route_dev=""
                    route_src=""
                    route_via=""
                    log_warn "  fast route auto-detect failed for ${target}; using tool defaults"
                fi
            fi

            if [[ "${FAST_TCP_SCANNER}" == "masscan" ]]; then
                [[ -n "$route_dev" ]] && masscan_route_args+=(--interface "$route_dev")
                [[ -n "$route_src" ]] && masscan_route_args+=(--source-ip "$route_src")
                [[ -n "$route_via" ]] && masscan_route_args+=(--router-ip "$route_via")

                if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
                    log "  [DRY RUN] masscan ${target} -p 0-65535 --rate ${rate} ${masscan_route_args[*]} -oX ${out_xml}"
                else
                    log "  masscan [${tier}] ${target} -> $(basename "$out_xml")"
                    masscan "${target}" -p 0-65535 --rate "${rate}" \
                        ${excl_args} "${masscan_route_args[@]}" \
                        -oX "${out_xml}" --wait 10 \
                        > "${out_log}" 2>&1 &
                    scan_pids+=($!)
                    (( running++ )) || true
                fi
            else
                local -a naabu_args=()
                out_json="${EVIDENCE_BASE}/_sweep/naabu_fast_${tier}_${safe}_${session_ts}.jsonl"
                [[ -n "$route_dev" ]] && naabu_args+=(-interface "$route_dev")

                if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
                    log "  [DRY RUN] naabu -host ${target} -p - -json -o ${out_json} -silent -Pn -s s -rate ${rate} -c ${naabu_threads} -timeout ${NAABU_TIMEOUT} -retries ${NAABU_RETRIES} ${naabu_args[*]}"
                    log "  [DRY RUN] naabu_json_to_nmap_xml ${out_json} ${out_xml}"
                else
                    log "  naabu [${tier}] ${target} -> $(basename "$out_json") / $(basename "$out_xml")"
                    (
                        naabu -host "${target}" -p - -json -o "${out_json}" -silent -Pn -s s \
                            -rate "${rate}" -c "${naabu_threads}" \
                            -timeout "${NAABU_TIMEOUT}" -retries "${NAABU_RETRIES}" \
                            ${excl_args} "${naabu_args[@]}" \
                            > "${out_log}" 2>&1
                        rc=$?
                        naabu_json_to_nmap_xml "${out_json}" "${out_xml}"
                        exit $rc
                    ) &
                    scan_pids+=($!)
                    (( running++ )) || true
                fi
            fi
        done < "$tier_list"
    done

    # Wait for all fast-scan jobs to finish
    if [[ ${#scan_pids[@]} -gt 0 ]]; then
        log "Waiting for ${#scan_pids[@]} ${FAST_TCP_SCANNER} job(s) to complete..."
        wait "${scan_pids[@]}" || true
        log_ok "All ${FAST_TCP_SCANNER} jobs finished"
    fi

    # Import all fast-scan XML files into MSF DB (single msfconsole session)
    if [[ "${FAST_TCP_SCANNER}" != "db_nmap" && ${#all_fast_xml[@]} -gt 0 ]]; then
        run_db_import "tcp_fast_${FAST_TCP_SCANNER}_${session_ts}" "${all_fast_xml[@]}"
    fi

    #  Pass 2: db_nmap version/OS scan on open ports (per tier) 
    # Evasion Pass 1 also runs here (nmap, sequential  stealth flags preserved).
    if [[ "${MASSCAN_ONLY:-0}" -eq 1 ]]; then
        if [[ -n "${tier_targets[evasion]// }" ]]; then
            log_warn "TCP [evasion] targets present, but --masscan-only skips their nmap-only handling"
        fi
        export_db "tcp_fast"
        log_ok "TCP fast-scan-only phase complete"
        return 0
    fi

    # BUG-ACTIVE-1 fix extended to phase_tcp (Nimbus-84 2026-05-15): array prevents injection via IDLE_SCAN_ZOMBIE
    local -a scan_type_args=("-sS")
    [[ -n "${IDLE_SCAN_ZOMBIE:-}" ]] && scan_type_args=("-sI" "${IDLE_SCAN_ZOMBIE}")

    for tier in ghost normal loud evasion; do
        local hosts="${tier_targets[$tier]}"
        [[ -z "${hosts// }" ]] && continue

        local tier_ts; tier_ts="$(_ts)"
        local flags; flags="$(nmap_tier_flags "$tier" 1)"
        local excl; excl="$(nmap_exclude_args)"
        local tier_list="${EVIDENCE_BASE}/_sweep/targets_${tier}.txt"
        echo "$hosts" | tr ' ' '\n' | grep -v '^$' > "$tier_list"
        local count; count=$(wc -l < "$tier_list" | tr -d ' ')

        local open_ports=""

        if [[ "$tier" == "evasion" ]]; then
            # Evasion: nmap Pass 1  masscan cannot do fragmentation/source-port tricks
            # Remove host-timeout for full -p- scan; retries kept low for stealth
            local evasion_flags; evasion_flags="$(nmap_tier_flags "evasion" 1 | sed 's/--host-timeout [^ ]*//')"
            local out_fast="${EVIDENCE_BASE}/_sweep/tcp_fast_evasion_${tier_ts}"
            log "TCP [evasion] Pass 1  nmap full scan (stealth): ${count} target(s)"
            run_rc_scan "tcp_fast_evasion" "${scan_type_args[@]}" -p- --open -Pn \
                ${evasion_flags} ${excl} -iL "$tier_list" -oA "${out_fast}"
            log_ok "TCP fast [evasion]: ${out_fast}.{nmap,xml,gnmap}"
            open_ports="$(extract_open_ports "${out_fast}.gnmap")"
        else
            # Extract open ports from this tier's Pass 1 XML files
            local tier_xmls="${tier_xml_lists[$tier]:-}"
            if [[ -n "$tier_xmls" ]]; then
                local -a xml_arr
                read -ra xml_arr <<< "$tier_xmls"
                open_ports="$(extract_open_ports_xml "${xml_arr[@]}")"
            fi
            if [[ -z "$open_ports" ]]; then
                log_warn "TCP [${tier}] ${FAST_TCP_SCANNER} found 0 open ports  check interface/rate; BASELINE_PORTS will cover minimum set"
            fi
        fi

        # Merge BASELINE_PORTS into open_ports  guarantees minimum coverage even if
        # masscan found nothing. Deduplicates the combined list before scanning.
        if [[ -n "${BASELINE_PORTS:-}" ]]; then
            local merged="${open_ports:+${open_ports},}${BASELINE_PORTS}"
            open_ports=$(echo "$merged" | tr ',' '\n' | sort -un | tr '\n' ',' | sed 's/,$//')
        fi

        if [[ -z "$open_ports" ]]; then
            log_warn "TCP [${tier}] Pass 2: no ports to scan  skipping"
            continue
        fi

        local open_count; open_count=$(echo "$open_ports" | tr ',' '\n' | wc -l | tr -d ' ')
        log "TCP [${tier}] Pass 2  version/OS/scripts: ${open_count} port(s) across ${count} target(s)"

        local scripts; scripts="$(tier_scripts "$tier")"
        local out_deep="${EVIDENCE_BASE}/_sweep/tcp_deep_${tier}_${tier_ts}"
        run_rc_scan "tcp_deep_${tier}" "${scan_type_args[@]}" -sV -O ${scripts} --open -Pn $flags $excl \
            -p "$open_ports" -iL "$tier_list" -oA "${out_deep}"
        log_ok "TCP deep [${tier}]: ${out_deep}.{nmap,xml,gnmap}"
    done

    # Phase 2b: common-ports NSE sweep  runs unconditionally after all tier scans
    phase_sweep_nse

    # Phase 2c: OS fingerprinting on confirmed live hosts
    phase_os_detect

    export_db "tcp"
    log_ok "TCP scan complete"
}

# =============================================================================
# MRK:03_NSE — PHASE 2b: COMMON-PORT NSE SWEEP | nse,phase,2b,common,port | L1797-1890
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# Target set: confirmed live hosts from DB/CSV/gnmap; falls back to full scope
# only if no evidence exists (e.g. phase_tcp not yet run).
# Port set: DB query for all open TCP ports in workspace -> Pass 1 XMLs ->
# BASELINE_PORTS fallback only when both DB and XMLs return nothing.
#
# Differs from phase_tcp Pass 2 in that it:
#  - Is DB-gated: only scans confirmed live hosts (no broad scope noise)
#  - Scans only confirmed-open ports (no unconditional BASELINE_PORTS inflation)
#  - Saves to a dedicated evidence path for easy review
#  - Runs at GLOBAL_TIER speed

phase_sweep_nse() {
    log "=== PHASE 2b: COMMON-PORT NSE SWEEP (DB-gated) ==="

    local targets_file="${EVIDENCE_BASE}/_sweep/targets_nse_sweep.txt"

    # Target set: confirmed live hosts (DB -> CSV -> gnmap).
    # Falls back to full configured scope only if no evidence exists yet
    # (e.g. phase_tcp not run, or DB/CSV/gnmap all empty on a fresh engagement).
    get_live_hosts > "$targets_file"
    if [[ ! -s "$targets_file" ]]; then
        log_warn "phase_sweep_nse: no live hosts in DB/CSV/gnmap  falling back to full scope"
        build_target_list > "$targets_file"
    fi

    local count; count=$(wc -l < "$targets_file" | tr -d ' ')
    if [[ "$count" -eq 0 ]]; then
        log_warn "phase_sweep_nse: no targets  skipping"
        return 0
    fi

    local flags; flags="$(nmap_tier_flags "${GLOBAL_TIER}" 1)"
    local excl;  excl="$(nmap_exclude_args)"
    local ts;    ts="$(_ts)"
    local out="${EVIDENCE_BASE}/_sweep/nse_common_${ts}"

    # Port set: DB-discovered ports -> Pass 1 XMLs -> BASELINE_PORTS last resort.
    # Do NOT inflate unconditionally with BASELINE_PORTS: scan what was actually
    # found open, not a fixed wishlist. Fallback chain ensures coverage on fresh runs.
    local sweep_ports=""

    # Primary: single DB query for all open TCP ports across the workspace
    if [[ "${DB_DIRECT_AVAILABLE:-1}" -eq 1 ]]; then
        local wid; wid="$(workspace_id)"
        if [[ -n "$wid" ]]; then
            local db_ports
            db_ports=$(db_query "SELECT DISTINCT port FROM services \
                WHERE workspace_id=${wid} AND proto='tcp' AND state='open' ORDER BY port;")
            if [[ -n "$db_ports" ]]; then
                sweep_ports="$(echo "$db_ports" | tr '\n' ',' | sed 's/,$//')"
            fi
        fi
    fi

    # Fallback 1: parse Pass 1 XML files (masscan/naabu) from disk
    if [[ -z "$sweep_ports" ]]; then
        local extra_xml
        set +u
        extra_xml="$(find "${EVIDENCE_BASE}/_sweep" \( -name 'masscan_fast_*.xml' -o -name 'naabu_fast_*.xml' \) 2>/dev/null | tr '\n' ' ')"
        set -u
        if [[ -n "$extra_xml" ]]; then
            # BUG-ACTIVE-1 fix (Nimbus-84 2026-05-15): quote array expansion to prevent
            # word-splitting on paths with spaces or shell metacharacters
            read -r -a extra_xml_files <<< "$extra_xml"
            sweep_ports="$(extract_open_ports_xml "${extra_xml_files[@]}" 2>/dev/null || true)"
        fi
    fi

    # Fallback 2: BASELINE_PORTS (last resort  nothing in DB or Pass 1 XMLs)
    if [[ -z "$sweep_ports" ]]; then
        log_warn "phase_sweep_nse: no discovered ports in DB or XMLs  using BASELINE_PORTS"
        sweep_ports="${BASELINE_PORTS:-21,22,23,25,53,80,110,111,135,139,143,389,443,445,465,587,636,993,995,1433,1521,2049,3306,3389,5432,5900,5985,5986,8080,8443,8888,9200,10443}"
    fi

    # BUG-ACTIVE-1 fix: use array for scan_type to prevent injection via IDLE_SCAN_ZOMBIE
    local -a scan_type_args=("-sS")
    [[ -n "${IDLE_SCAN_ZOMBIE:-}" ]] && scan_type_args=("-sI" "${IDLE_SCAN_ZOMBIE}")

    local port_count; port_count=$(echo "$sweep_ports" | tr ',' '\n' | wc -l | tr -d ' ')
    log "NSE sweep [${GLOBAL_TIER}]  ${count} target(s), ${port_count} port(s)"

    run_rc_scan "nse_common_${ts}" "${scan_type_args[@]}" -sV -O -sC --open -Pn \
        $flags $excl \
        -p "$sweep_ports" \
        -iL "$targets_file" \
        -oA "${out}"

    log_ok "NSE sweep: ${out}.{nmap,xml,gnmap}"

    # db_nmap already committed results to the workspace directly.
    # This reimport is belt-and-suspenders only  missing XML is expected and not an error.
    run_db_import --db-nmap "nse_common_${ts}" "${out}.xml"

    # VAPT: CVE-specific NSE scan — separate pass targeting known-vuln scripts
    phase_sweep_nse_vapt_cve "$targets_file" "$sweep_ports"
}

# VAPT-ADDED: CVE-focused NSE scan using vulnerability-specific scripts.
# Runs after the standard NSE sweep to avoid polluting the main scan results.
# Scripts used: EternalBlue, Shellshock, Heartbleed, POODLE, RDP-DoS, SlowLoris,
#   SMB signing, anonymous FTP, MS-SQL info, SSH auth methods.
phase_sweep_nse_vapt_cve() {
    local targets_file="$1"
    local sweep_ports="$2"

    log "=== PHASE 2b-VAPT: CVE-SPECIFIC NSE VULNERABILITY SCAN ==="

    local ts; ts="$(_ts)"
    local flags; flags="$(nmap_tier_flags "${GLOBAL_TIER}" 1)"
    local excl;  excl="$(nmap_exclude_args)"

    # SMB vulnerability scripts (EternalBlue CVE-2017-0144, signing check)
    local smb_ports="445,139"
    local smb_out="${EVIDENCE_BASE}/_sweep/nse_vapt_smb_${ts}"
    log "  VAPT NSE: SMB vulnerabilities (MS17-010 EternalBlue, signing)"
    run_rc_scan "nse_vapt_smb_${ts}" \
        "${scan_type_args[@]:-"-sS"}" -Pn --open \
        $flags $excl \
        -p "$smb_ports" \
        --script "smb-vuln-ms17-010,smb-security-mode,smb2-security-mode,smb-vuln-cve-2017-7494" \
        --script-timeout 30s \
        -iL "$targets_file" \
        -oA "$smb_out" 2>/dev/null || true
    log_ok "  SMB VAPT NSE: ${smb_out}.nmap"
    run_db_import --db-nmap "nse_vapt_smb_${ts}" "${smb_out}.xml"

    # HTTP Shellshock (CVE-2014-6271) — still found on embedded/IoT devices
    local http_ports; http_ports=$(echo "$sweep_ports" | tr ',' '\n' | grep -E "^(80|443|8080|8443|8888|8000|8008)$" | tr '\n' ',' | sed 's/,$//' || true)
    if [[ -n "$http_ports" ]]; then
        local shellshock_out="${EVIDENCE_BASE}/_sweep/nse_vapt_shellshock_${ts}"
        log "  VAPT NSE: Shellshock (CVE-2014-6271) on HTTP ports"
        run_rc_scan "nse_vapt_shellshock_${ts}" \
            -sS -Pn --open \
            $flags $excl \
            -p "$http_ports" \
            --script "http-shellshock" \
            --script-args "http-shellshock.uri=/cgi-bin/status,http-shellshock.header=User-Agent" \
            --script-timeout 20s \
            -iL "$targets_file" \
            -oA "$shellshock_out" 2>/dev/null || true
        log_ok "  Shellshock NSE: ${shellshock_out}.nmap"
        run_db_import --db-nmap "nse_vapt_shellshock_${ts}" "${shellshock_out}.xml"
    fi

    # SSL/TLS vulnerability scripts (Heartbleed, POODLE, DROWN)
    local tls_ports; tls_ports=$(echo "$sweep_ports" | tr ',' '\n' | grep -E "^(443|8443|465|993|995|636|3269|8080|8000)$" | tr '\n' ',' | sed 's/,$//' || true)
    if [[ -n "$tls_ports" ]]; then
        local ssl_vuln_out="${EVIDENCE_BASE}/_sweep/nse_vapt_ssl_${ts}"
        log "  VAPT NSE: SSL/TLS vulnerabilities (Heartbleed, POODLE, DROWN, CCS)"
        run_rc_scan "nse_vapt_ssl_${ts}" \
            -sS -Pn --open \
            $flags $excl \
            -p "$tls_ports" \
            --script "ssl-heartbleed,ssl-poodle,ssl-drown,ssl-ccs-injection,ssl-known-key" \
            --script-timeout 30s \
            -iL "$targets_file" \
            -oA "$ssl_vuln_out" 2>/dev/null || true
        log_ok "  SSL VAPT NSE: ${ssl_vuln_out}.nmap"
        run_db_import --db-nmap "nse_vapt_ssl_${ts}" "${ssl_vuln_out}.xml"
    fi

    # RDP vulnerability (CVE-2019-0708 BlueKeep, MS12-020 DoS)
    local rdp_ports; rdp_ports=$(echo "$sweep_ports" | tr ',' '\n' | grep -E "^(3389|3388)$" | tr '\n' ',' | sed 's/,$//' || true)
    if [[ -n "$rdp_ports" ]]; then
        local rdp_out="${EVIDENCE_BASE}/_sweep/nse_vapt_rdp_${ts}"
        log "  VAPT NSE: RDP vulnerabilities (BlueKeep CVE-2019-0708, MS12-020)"
        run_rc_scan "nse_vapt_rdp_${ts}" \
            -sS -Pn --open \
            $flags $excl \
            -p "$rdp_ports" \
            --script "rdp-vuln-ms12-020,rdp-enum-encryption" \
            --script-timeout 20s \
            -iL "$targets_file" \
            -oA "$rdp_out" 2>/dev/null || true
        log_ok "  RDP VAPT NSE: ${rdp_out}.nmap"
        run_db_import --db-nmap "nse_vapt_rdp_${ts}" "${rdp_out}.xml"
    fi

    # HTTP slow-loris DoS check (informational — verify RoE before testing)
    if [[ -n "$http_ports" ]] && [[ "${GLOBAL_TIER:-normal}" == "loud" ]]; then
        local slowloris_out="${EVIDENCE_BASE}/_sweep/nse_vapt_slowloris_${ts}"
        log "  VAPT NSE: SlowLoris DoS check (tier=loud, informational)"
        run_rc_scan "nse_vapt_slowloris_${ts}" \
            -sS -Pn --open \
            $flags $excl \
            -p "$http_ports" \
            --script "http-slowloris-check" \
            --script-timeout 30s \
            -iL "$targets_file" \
            -oA "$slowloris_out" 2>/dev/null || true
        log_ok "  SlowLoris NSE: ${slowloris_out}.nmap"
    fi

    # FTP anonymous login check
    local ftp_ports; ftp_ports=$(echo "$sweep_ports" | tr ',' '\n' | grep -E "^(21|990|2121)$" | tr '\n' ',' | sed 's/,$//' || true)
    if [[ -n "$ftp_ports" ]]; then
        local ftp_out="${EVIDENCE_BASE}/_sweep/nse_vapt_ftp_${ts}"
        log "  VAPT NSE: FTP anonymous login + banner"
        run_rc_scan "nse_vapt_ftp_${ts}" \
            -sS -Pn --open \
            $flags $excl \
            -p "$ftp_ports" \
            --script "ftp-anon,ftp-bounce,ftp-syst" \
            --script-timeout 15s \
            -iL "$targets_file" \
            -oA "$ftp_out" 2>/dev/null || true
        log_ok "  FTP VAPT NSE: ${ftp_out}.nmap"
        run_db_import --db-nmap "nse_vapt_ftp_${ts}" "${ftp_out}.xml"
    fi

    # MS-SQL / MySQL enumeration
    local db_ports; db_ports=$(echo "$sweep_ports" | tr ',' '\n' | grep -E "^(1433|1434|3306|5432|27017)$" | tr '\n' ',' | sed 's/,$//' || true)
    if [[ -n "$db_ports" ]]; then
        local db_out="${EVIDENCE_BASE}/_sweep/nse_vapt_db_${ts}"
        log "  VAPT NSE: Database service fingerprinting"
        run_rc_scan "nse_vapt_db_${ts}" \
            -sS -Pn --open \
            $flags $excl \
            -p "$db_ports" \
            --script "ms-sql-info,ms-sql-config,mysql-info,mysql-empty-password,mysql-vuln-cve2012-2122,pgsql-brute" \
            --script-timeout 20s \
            -iL "$targets_file" \
            -oA "$db_out" 2>/dev/null || true
        log_ok "  DB VAPT NSE: ${db_out}.nmap"
        run_db_import --db-nmap "nse_vapt_db_${ts}" "${db_out}.xml"
    fi

    log_ok "VAPT CVE NSE sweep complete"
}

# =============================================================================
# MRK:03_OS — PHASE 2c: OS FINGERPRINTING | os,phase,2c,fingerprinting | L1891-2024
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# Runs against confirmed live hosts (DB-driven) after TCP Pass 2 and NSE sweep
# have populated the workspace.
#
# Design:
#  - Port list = BASELINE_PORTS  all masscan-discovered ports (maximises the
#    chance nmap finds both an open and a closed/filtered TCP port on each host,
#    which is the minimum requirement for OS detection to trigger).
#  - --osscan-guess    aggressively guess when no exact match found.
#  - --osscan-limit    skip hosts with no useful open/closed port pair; avoids
#    wasting time on fully-filtered hosts.
#  - Grouped by tier for correct timing/rate parameters.
#  - OS match lines are logged inline for immediate operator visibility.
#  - Output saved to evidence/_sweep/os_detect_<tier>_<ts>.{nmap,xml,gnmap}
#    and imported into MSF DB (CPE data lands in the hosts table).

phase_os_detect() {
    log "=== PHASE 2c: OS FINGERPRINTING ==="

    local live_hosts; live_hosts="$(get_scan_hosts)"
    local db_fallback=0

    if [[ -z "$live_hosts" ]]; then
        # Direct psql query returned nothing  DB connection may be unavailable or
        # workspace_id lookup failed (credentials mismatch, socket not ready, etc.).
        # Fall back to all_targets() so OS detection is not silently skipped when
        # the DB is populated but unreachable via direct psql (export_db still works
        # because it uses msfconsole's internal connection rather than raw psql).
        log_info "phase_os_detect: no hosts from DB/CSV/gnmap  using configured scope (all_targets)"
        live_hosts="$(build_target_list)"
        db_fallback=1
    fi

    if [[ -z "$live_hosts" ]]; then
        log_warn "phase_os_detect: no targets available  skipping"
        return 0
    fi

    local host_count; host_count=$(echo "$live_hosts" | wc -l | tr -d ' ')
    if [[ "$db_fallback" -eq 1 ]]; then
        log "OS fingerprinting: ${host_count} target(s) from target list (DB fallback)"
    else
        log "OS fingerprinting: ${host_count} confirmed live host(s)"
    fi

    mkdir -p "${EVIDENCE_BASE}/_sweep"

    #  Build OS scan port list 
    # Start with BASELINE_PORTS, then add any ports masscan found on disk.
    # The wider the port set, the higher the chance of finding both an open
    # and a closed port per host (required for nmap OS probing to fire).
    local os_ports="${BASELINE_PORTS}"
    local extra_xml
    set +u
    extra_xml="$(find "${EVIDENCE_BASE}/_sweep" \( -name 'masscan_fast_*.xml' -o -name 'naabu_fast_*.xml' \) 2>/dev/null | tr '\n' ' ')"
    set -u
    if [[ -n "$extra_xml" ]]; then
        local extra_ports; extra_ports="$(extract_open_ports_xml $extra_xml 2>/dev/null || true)"
        if [[ -n "$extra_ports" ]]; then
            os_ports="$(echo "${os_ports},${extra_ports}" | tr ',' '\n' | sort -un | tr '\n' ',' | sed 's/,$//')"
        fi
    fi
    local port_count; port_count=$(echo "$os_ports" | tr ',' '\n' | wc -l | tr -d ' ')
    log "OS port list: ${port_count} port(s)"

    # BUG-ACTIVE-1 fix extended to phase_os_detect (Nimbus-84 2026-05-15): array prevents injection via IDLE_SCAN_ZOMBIE
    local -a scan_type_args=("-sS")
    [[ -n "${IDLE_SCAN_ZOMBIE:-}" ]] && scan_type_args=("-sI" "${IDLE_SCAN_ZOMBIE}")

    #  Group live hosts by tier
    declare -A tier_os_hosts
    tier_os_hosts["ghost"]=""
    tier_os_hosts["normal"]=""
    tier_os_hosts["loud"]=""
    tier_os_hosts["evasion"]=""

    while IFS= read -r ip; do
        [[ -z "$ip" ]] && continue
        # Skip non-IP tokens (guards against comment/header garbage in fallback target lists)
        [[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}(/[0-9]{1,2})?$ ]] || continue
        local t; t="$(resolve_tier "$ip")"
        tier_os_hosts["$t"]+="${ip}"$'\n'
    done <<< "$live_hosts"

    #  One nmap OS scan per tier 
    set +u
    for tier in ghost normal loud evasion; do
        local hosts="${tier_os_hosts[$tier]:-}"
        [[ -z "${hosts// }" ]] && continue

        local tier_list="${EVIDENCE_BASE}/_sweep/targets_os_${tier}.txt"
        printf '%s' "$hosts" | grep -v '^$' > "$tier_list"
        local count; count=$(wc -l < "$tier_list" | tr -d ' ')

        local flags; flags="$(nmap_tier_flags "$tier" 1)"
        local excl; excl="$(nmap_exclude_args)"
        local ts; ts="$(_ts)"
        local out="${EVIDENCE_BASE}/_sweep/os_detect_${tier}_${ts}"

        log "OS detect [${tier}]: ${count} host(s)"

        run_rc_scan "os_detect_${tier}" \
            "${scan_type_args[@]}" \
            -O --osscan-guess --osscan-limit \
            -sV -Pn --open \
            $flags $excl \
            -p "$os_ports" \
            -iL "$tier_list" \
            -oA "${out}"

        log_ok "OS detect [${tier}]: ${out}.{nmap,xml,gnmap}"

        #  Inline OS result summary 
        if [[ -f "${out}.nmap" ]]; then
            local os_lines
            os_lines=$(grep -E \
                "^(OS details|Running:|Aggressive OS guesses|OS CPE|MAC Address):" \
                "${out}.nmap" 2>/dev/null || true)
            if [[ -n "$os_lines" ]]; then
                log_ok "  OS matches [${tier}]:"
                echo "$os_lines" | while IFS= read -r line; do
                    log_info "    ${line}"
                done
            else
                log_warn "  OS detect [${tier}]: no fingerprint matches  each host needs" \
                         "at least 1 open + 1 closed/filtered TCP port"
            fi
        fi
    done
    set -u
}

# =============================================================================
# MRK:03_P3 — PHASE 3: UDP CORRELATION SCAN | p3,phase,udp,correlation,scan | L2025-2120
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# Derives UDP targets per host from TCP findings in DB.
# Always probes baseline UDP (SNMP, NTP, DNS, IPMI, DHCP on GW-range).
# Adds correlated ports based on observed TCP services.
# Fallback: when DB has no live hosts (e.g. DB unavailable or phase_tcp
# skipped), runs baseline UDP against all configured targets at GLOBAL_TIER.

phase_udp() {
    log "=== PHASE 3: UDP CORRELATION SCAN ==="

    local live_hosts; live_hosts="$(get_scan_hosts)"

    #  Fallback: DB empty  scan all configured targets with baseline UDP 
    if [[ -z "$live_hosts" ]]; then
        log_info "phase_udp: no hosts from DB/CSV/gnmap  baseline UDP sweep of configured scope (all_targets)"

        local targets_file="${EVIDENCE_BASE}/_sweep/targets_udp_fallback.txt"
        build_target_list > "$targets_file"
        local count; count=$(wc -l < "$targets_file" | tr -d ' ')

        if [[ "$count" -eq 0 ]]; then
            log_warn "phase_udp: no targets defined  skipping"
            return 0
        fi

        local flags; flags="$(nmap_tier_flags "${GLOBAL_TIER}" 1)"
        local ts; ts="$(_ts)"
        local out="${EVIDENCE_BASE}/_sweep/udp_fallback_${ts}"
        # Baseline UDP ports: SNMP, NTP, DNS, NetBIOS, DHCP, TFTP, IPMI, RPC, NFS, IKE, L2TP
        local udp_ports="53,67,68,69,123,137,138,161,162,389,443,500,623,1194,1434,1701,2049,4500"

        log "UDP fallback sweep [${GLOBAL_TIER}]: ${count} target(s), ports ${udp_ports}"
        run_rc_scan "udp_fallback_${ts}" -Pn -sU -sV $flags -p "$udp_ports" \
            -iL "$targets_file" -oA "${out}"
        log_ok "UDP fallback: ${out}.{nmap,xml,gnmap}"

        export_db "udp"
        log_ok "UDP fallback sweep complete"
        return 0
    fi

    while IFS= read -r ip; do
        [[ -z "$ip" ]] && continue
        local tier; tier="$(resolve_tier "$ip")"
        local ts; ts="$(_ts)"
        local out="${EVIDENCE_BASE}/_sweep/udp_${ip}_${ts}"
        local flags; flags="$(nmap_tier_flags "$tier" 1)"

        # Baseline UDP  always probe these on every live host
        local udp_ports="161,162,123,53,67,68,69,623"

        # Derive correlated UDP from TCP findings
        # NOTE: must use while+herestring (not pipe) to avoid subshell  udp_ports
        # must remain mutable in the current shell scope.
        local tcp_ports; tcp_ports="$(get_open_tcp "$ip")"

        while read -r p; do
            [[ -z "$p" ]] && continue
            case "$p" in
                80|443|8080|8443|4443|9443|10443) udp_ports="${udp_ports},443" ;;  # QUIC/HTTP3
                139|445)  udp_ports="${udp_ports},137,138" ;;                       # NetBIOS
                111)      udp_ports="${udp_ports},111" ;;                            # RPCbind
                2049)     udp_ports="${udp_ports},2049" ;;                           # NFS
                389|636)  udp_ports="${udp_ports},389" ;;                            # LDAP
                500)      udp_ports="${udp_ports},500,4500" ;;                       # IKE/IPSec
                1433)     udp_ports="${udp_ports},1434" ;;                           # MSSQL browser
                88)       udp_ports="${udp_ports},88" ;;                             # Kerberos
                464)      udp_ports="${udp_ports},464" ;;                            # kpasswd
                5060)     udp_ports="${udp_ports},5060" ;;                           # SIP
                1194)     udp_ports="${udp_ports},1194" ;;                           # OpenVPN
                1701)     udp_ports="${udp_ports},1701" ;;                           # L2TP
            esac
        done <<< "$tcp_ports"

        # Deduplicate port list
        udp_ports=$(echo "$udp_ports" | tr ',' '\n' | sort -un | tr '\n' ',' | sed 's/,$//')

        log "UDP [${tier}] ${ip}: ports ${udp_ports}"
        run_rc_scan "udp_${ip}" -Pn -sU -sV $flags -p "$udp_ports" "$ip" -oA "${out}"
        log_ok "UDP output: ${out}.{nmap,xml,gnmap}"
        # UDP caveat: MSF DB may record open|filtered as filtered  verify manually
        PGPASSWORD="${MSF_DB_PASS:-}" msfconsole -q -x \
            "workspace ${PROJECT_NAME}; \
             notes -a -h ${ip} -t db.caveat \
             -d 'UDP scan ${out}: open|filtered states require manual verification  nmap cannot distinguish from filtered'; \
             exit" </dev/null >/dev/null 2>&1 || true

    done <<< "$live_hosts"

    export_db "udp"
    log_ok "UDP correlation scan complete"
}

# =============================================================================
# MRK:03_P4 — PHASE 4: SERVICE ENUMERATION | p4,phase,service,enumeration | L2121-2126
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# Per-host, per-port. Runs only scripts relevant to confirmed open services.
# Reads from DB  no subnet-wide script runs.

# MRK:03_PROBES — Active service probes | probes,active,service,mongodb,vuln | L2127-2461
# NAV-RULE: insert-here
# ---------------------------------------------------------------------------
# probe_mongodb — active unauthenticated-access test for MongoDB (default :27017).
# Requires mongosh on tester host; gracefully skips if absent.
# Returns 0 (confirmed unauth access) or 1 (auth required / unreachable).
# ---------------------------------------------------------------------------
probe_mongodb() {
    local ip="$1" port="${2:-27017}" result dbs
    if ! command -v mongosh &>/dev/null; then
        log_info "  mongosh not found  skipping active MongoDB probe on ${ip}:${port}"
        return 1
    fi
    result=$(timeout 10 mongosh --host "$ip" --port "$port" --quiet \
        --eval "db.adminCommand({listDatabases:1})" 2>/dev/null)
    if echo "$result" | grep -qE '"ok"\s*:\s*1'; then
        dbs=$(echo "$result" | grep -oP '"name"\s*:\s*"\K[^"]+' | tr '\n' ',' | sed 's/,$//')
        log_warn "  [VULN] MongoDB:${port} NOAUTH on ${ip}  unauthenticated admin access confirmed. Databases: ${dbs}"
        add_followup "$ip" "MongoDB:${port} NOAUTH [CRITICAL]" \
            "Unauthenticated admin access confirmed. Databases: ${dbs}. Bind to localhost + enable --auth immediately."
        return 0
    fi
    log_info "  MongoDB:${port} on ${ip}  auth required or port not responding"
    return 1
}

# Manual follow-up tracker
FOLLOWUP_FILE="working/manual_followup_${SESSION_TS}.md"

add_followup() {
    local ip="$1" reason="$2" action="$3"
    echo "| ${ip} | ${reason} | ${action} |" >> "$FOLLOWUP_FILE"
}

init_followup() {
    cat > "$FOLLOWUP_FILE" << 'EOF'
# Manual Follow-up Required
# Generated by 03_comp_scan.sh
# Paste this section into chat for state snapshot integration

## Items Requiring Manual Investigation

| Host | Reason | Suggested Action |
|------|--------|-----------------|
EOF
}

phase_enum() {
    log "=== PHASE 4: SERVICE ENUMERATION ==="
    init_followup

    local live_hosts; live_hosts="$(get_scan_hosts)"
    if [[ -z "$live_hosts" ]]; then
        log_info "phase_enum: no hosts from DB/CSV/gnmap  using configured scope (all_targets)"
        live_hosts="$(build_target_list)"
    fi
    if [[ -z "$live_hosts" ]]; then
        log_warn "phase_enum: no targets available  skipping"
        return 0
    fi

    while IFS= read -r ip; do
        [[ -z "$ip" ]] && continue
        local tier; tier="$(resolve_tier "$ip")"
        local dir; dir="$(ip_dir "$ip")"
        local ts; ts="$(_ts)"
        local flags; flags="$(nmap_tier_flags "$tier" 1)"

        log "Enumerating ${ip} [${tier}] [${MODE}]"

        # PTE: skip internal-only services unlikely to be externally exposed
        local skip_internal=0
        [[ "$MODE" == "pte" ]] && skip_internal=1

        # ----- SMB (PTI only) -----
        if [[ "$skip_internal" -eq 0 ]] && any_port_open "$ip" 445 139; then
            log_info "  SMB detected on ${ip}"
            local out="${dir}/nmap_smb_${ts}"
            run_rc_scan "smb-os-discovery" -Pn -p 445,139 $flags --script "smb-os-discovery,smb-enum-shares,smb-enum-users,smb-protocols,smb2-security-mode,smb-vuln-ms17-010" "$ip" -oA "$out"
            # enum4linux-ng  auto when both 445+139 open
            if port_open "$ip" 445 "tcp" 2>/dev/null && port_open "$ip" 139 "tcp" 2>/dev/null; then
                log_info "  Running enum4linux-ng on ${ip}"
                local e4l_out="${dir}/enum4linux_${ts}.yml"
                timeout "$E4L_TIMEOUT" enum4linux-ng "$ip" -oY "$e4l_out" 2>&1 | \
                    tee "${dir}/enum4linux_${ts}.txt" || \
                    log_warn "  enum4linux-ng timed out or errored on ${ip}"
            fi
        fi

        # ----- NFS / RPC (PTI only) -----
        if [[ "$skip_internal" -eq 0 ]] && any_port_open "$ip" 111 2049; then
            log_info "  NFS/RPC detected on ${ip}"
            local out="${dir}/nmap_nfs_${ts}"
            run_rc_scan "nfs-showmount" -Pn -p 111,2049 $flags --script "nfs-showmount,nfs-ls,nfs-statfs,rpcinfo" "$ip" -oA "$out"
            add_followup "$ip" "NFS exports found" "Mount and verify write access; check world-accessible exports"
        fi

        # ----- FTP -----
        if port_open "$ip" 21 "tcp" 2>/dev/null; then
            log_info "  FTP detected on ${ip}"
            local out="${dir}/nmap_ftp_${ts}"
            run_rc_scan "ftp-anon" -Pn -p 21 $flags --script "ftp-anon,ftp-syst,ftp-bounce,banner" "$ip" -oA "$out"
            add_followup "$ip" "FTP open" "Test anonymous login + STOR write; confirm manually"
        fi

        # ----- SSH -----
        if port_open "$ip" 22 "tcp" 2>/dev/null; then
            log_info "  SSH detected on ${ip}"
            local out="${dir}/nmap_ssh_${ts}"
            run_rc_scan "ssh-auth-methods" -Pn -p 22 $flags --script "ssh-auth-methods,ssh-hostkey,ssh2-enum-algos" "$ip" -oA "$out"
            add_followup "$ip" "SSH version detected" "Check version against CVE-2024-6387 (regreSSHion); review accepted auth methods"
        fi

        # ----- Telnet -----
        if port_open "$ip" 23 "tcp" 2>/dev/null; then
            log_info "  Telnet detected on ${ip}  cleartext protocol"
            local out="${dir}/nmap_telnet_${ts}"
            run_rc_scan "telnet-encryption" -Pn -p 23 $flags --script "telnet-encryption,banner" "$ip" -oA "$out"
            add_followup "$ip" "Telnet open (cleartext)" "Capture banner; confirm device type; manual banner review"
        fi

        # ----- VNC -----
        for vnc_port in 5900 5901 5902 5903 5904 5905; do
            if port_open "$ip" "$vnc_port" "tcp" 2>/dev/null; then
                log_info "  VNC detected on ${ip}:${vnc_port}"
                local out="${dir}/nmap_vnc_${vnc_port}_${ts}"
                run_rc_scan "vnc-info" -Pn -p "$vnc_port" $flags --script "vnc-info,vnc-auth,realvnc-auth-bypass" "$ip" -oA "$out"
                add_followup "$ip" "VNC port ${vnc_port} open" "Check auth type  None auth = Critical; test manually"
            fi
        done

        # ----- HTTP / Web -----
        local web_ports=()
        for wp in 80 443 8080 8443 4443 8888 9443 9200 10443 8006; do
            port_open "$ip" "$wp" "tcp" 2>/dev/null && web_ports+=("$wp")
        done
        if [[ ${#web_ports[@]} -gt 0 ]]; then
            log_info "  Web ports on ${ip}: ${web_ports[*]}"
            local port_str; port_str=$(IFS=','; echo "${web_ports[*]}")
            local out="${dir}/nmap_http_${ts}"
            run_rc_scan "http-title" -Pn -p "$port_str" $flags --script "http-title,http-headers,http-auth-finder,http-methods,http-default-accounts,http-robots.txt" "$ip" -oA "$out"
            # Flag HTTPS hosts for TLS script
            for wp in "${web_ports[@]}"; do
                case "$wp" in 443|8443|4443|9443|10443)
                    echo "${ip}:${wp}" >> "working/tls_targets.txt"
                    ;;
                esac
            done
            add_followup "$ip" "Web service(s) on ${web_ports[*]}" "Run 04_tls_scan.sh; check security headers; run web enum script"
        fi

        # ----- SNMP -----
        if port_open "$ip" 161 "udp" 2>/dev/null; then
            log_info "  SNMP detected on ${ip}"
            local out="${dir}/nmap_snmp_${ts}"
            run_rc_scan "snmp-info" -Pn -sU -p 161 $flags --script "snmp-info,snmp-interfaces,snmp-processes,snmp-netstat" "$ip" -oA "$out"
            add_followup "$ip" "SNMP responding" "Run snmpwalk -v1/v2c -c public; confirm community string"
        fi

        # ----- LDAP -----
        if any_port_open "$ip" 389 636 3268 3269; then
            log_info "  LDAP detected on ${ip}"
            local out="${dir}/nmap_ldap_${ts}"
            run_rc_scan "ldap-rootdse" -Pn -p 389,636,3268,3269 $flags --script "ldap-rootdse" "$ip" -oA "$out"
            add_followup "$ip" "LDAP/AD detected" "Test anonymous bind; run ldapsearch; check for DC role"
        fi

        # ----- Kerberos (DC indicator) -----
        if any_port_open "$ip" 88 464; then
            log_info "  Kerberos on ${ip}  likely Domain Controller"
            add_followup "$ip" "Kerberos port open  DC suspected" "Confirm DC role; check for AS-REP roasting candidates"
        fi

        # ----- RDP -----
        if port_open "$ip" 3389 "tcp" 2>/dev/null; then
            log_info "  RDP detected on ${ip}"
            local out="${dir}/nmap_rdp_${ts}"
            run_rc_scan "rdp-enum-encryption" -Pn -p 3389 $flags --script "rdp-enum-encryption,rdp-vuln-ms12-020" "$ip" -oA "$out"
            add_followup "$ip" "RDP detected" "Check NLA requirement; verify encryption level; assess firewall exposure"
        fi

        # ----- WinRM -----
        if any_port_open "$ip" 5985 5986; then
            log_info "  WinRM detected on ${ip}"
            add_followup "$ip" "WinRM open (5985/5986)" "Test with evil-winrm if credentials available"
        fi

        # ----- MQTT (PTI only) -----
        if [[ "$skip_internal" -eq 0 ]] && port_open "$ip" 1883 "tcp" 2>/dev/null; then
            log_info "  MQTT detected on ${ip}  subscribing for ${MQTT_LISTEN_TIMEOUT}s"
            local mqtt_out="${dir}/mqtt_subscribe_${ts}.txt"
            {
                echo "# MQTT Subscribe  ${ip}:1883"
                echo "# Engagement: ${PROJECT_NAME}"
                echo "# Date/Time:  $(_now)"
                echo "---"
                timeout "$MQTT_LISTEN_TIMEOUT" mosquitto_sub \
                    -h "$ip" -p 1883 -t '#' -v --quiet 2>&1 || true
            } | tee "$mqtt_out"
            log_ok "  MQTT capture saved: ${mqtt_out}"
            add_followup "$ip" "MQTT broker  topics captured" "Review ${mqtt_out}; check for unauthenticated subscribe/publish"
        fi

        if [[ "$skip_internal" -eq 0 ]] && port_open "$ip" 8883 "tcp" 2>/dev/null; then
            log_info "  MQTT/TLS detected on ${ip}:8883"
            local mqtt_tls_out="${dir}/mqtt_tls_${ts}.txt"
            {
                echo "# MQTT/TLS Subscribe  ${ip}:8883"
                echo "# Engagement: ${PROJECT_NAME}"
                echo "# Date/Time:  $(_now)"
                echo "---"
                timeout "$MQTT_LISTEN_TIMEOUT" mosquitto_sub \
                    -h "$ip" -p 8883 -t '#' -v --insecure --quiet 2>&1 || true
            } | tee "$mqtt_tls_out"
            log_ok "  MQTT/TLS capture saved: ${mqtt_tls_out}"
        fi

        # ----- OOB Management (PTI only) -----
        if [[ "$skip_internal" -eq 0 ]] && port_open "$ip" 623 "udp" 2>/dev/null; then
            log_info "  IPMI detected on ${ip}"
            local out="${dir}/nmap_ipmi_${ts}"
            run_rc_scan "ipmi-version" -Pn -sU -p 623 $flags --script "ipmi-version,ipmi-cipher-zero" "$ip" -oA "$out"
            add_followup "$ip" "IPMI (port 623/udp)" "Check cipher-zero; test default credentials (ADMIN/ADMIN, root/calvin)"
        fi
        if any_port_open "$ip" 17988 17990; then
            log_info "  HP iLO detected on ${ip}"
            add_followup "$ip" "HP iLO suspected (port 17988/17990)" "Check iLO version; probe web interface; review OpenSSH version"
        fi

        # ----- TFTP -----
        if port_open "$ip" 69 "udp" 2>/dev/null; then
            log_info "  TFTP detected on ${ip}  cleartext file transfer"
            local out="${dir}/nmap_tftp_${ts}"
            run_rc_scan "tftp-enum" -Pn -sU -p 69 $flags --script "tftp-enum" "$ip" -oA "$out"
            add_followup "$ip" "TFTP open (cleartext)" "Attempt file listing; check for config file exposure"
        fi

        # ----- OT/ICS (PTI only) -----
        if [[ "$skip_internal" -eq 0 ]]; then  # OT/ICS: PTI only
        for ot_port in 102 502 44818 20000 4840; do
            if port_open "$ip" "$ot_port" "tcp" 2>/dev/null; then
                local proto_name
                case "$ot_port" in
                    102)   proto_name="S7comm (Siemens PLC)" ;;
                    502)   proto_name="Modbus" ;;
                    44818) proto_name="EtherNet/IP" ;;
                    20000) proto_name="DNP3" ;;
                    4840)  proto_name="OPC-UA" ;;
                esac
                log_warn "  OT/ICS port ${ot_port} open on ${ip}: ${proto_name}  connect-only confirmed, NO protocol probe"
                add_followup "$ip" "OT/ICS port ${ot_port} (${proto_name})" "MANUAL ONLY  assess risk before any further probe; consult client before testing"
            fi
        done
        if port_open "$ip" 47808 "udp" 2>/dev/null; then
            log_warn "  BACnet (47808/udp) on ${ip}  NO probe"
            add_followup "$ip" "BACnet 47808/udp" "MANUAL ONLY  building automation; consult client"
        fi
        fi  # end OT/ICS PTI-only block

        # ----- Database services -----
        for db_port in 1433 3306 5432 27017 6379 9200 5984 1521; do
            if port_open "$ip" "$db_port" "tcp" 2>/dev/null; then
                local db_name
                case "$db_port" in
                    1433) db_name="MSSQL" ;; 3306) db_name="MySQL" ;;
                    5432) db_name="PostgreSQL" ;; 27017) db_name="MongoDB" ;;
                    6379) db_name="Redis" ;; 9200) db_name="Elasticsearch" ;;
                    5984) db_name="CouchDB" ;; 1521) db_name="Oracle" ;;
                esac
                log_info "  Database port ${db_port} (${db_name}) on ${ip}"
                add_followup "$ip" "${db_name} port ${db_port} open" "Test unauthenticated access; check default credentials; run db-specific nmap scripts"
                # Active unauthenticated-access probes
                case "$db_port" in
                    27017) probe_mongodb "$ip" "$db_port" ;;
                esac
            fi
        done

        # ----- Cisco Smart Install (Critical if open) -----
        if port_open "$ip" 4786 "tcp" 2>/dev/null; then
            log_warn "  CRITICAL: Cisco Smart Install port 4786 open on ${ip}"
            add_followup "$ip" "Cisco Smart Install 4786  CRITICAL" "Immediate manual verification; unauthenticated config replacement possible"
        fi

        # ----- SIP / VoIP -----
        if any_port_open "$ip" 5060 5061; then
            log_info "  SIP detected on ${ip}"
            local out="${dir}/nmap_sip_${ts}"
            run_rc_scan "sip-methods" -Pn -p 5060,5061 $flags --script "sip-methods,sip-enum-users" "$ip" -oA "$out"
            add_followup "$ip" "SIP/VoIP detected" "Test INVITE enumeration; check for authentication bypass"
        fi

        # ----- Mail -----
        if any_port_open "$ip" 25 110 143 465 587 993 995; then
            log_info "  Mail services detected on ${ip}"
            local out="${dir}/nmap_mail_${ts}"
            run_rc_scan "smtp-commands" -Pn -p 25,110,143,465,587,993,995 $flags --script "smtp-commands,smtp-open-relay,smtp-enum-users,pop3-capabilities,imap-capabilities" "$ip" -oA "$out"
            add_followup "$ip" "Mail services detected" "Open relay check; cleartext auth check; VRFY/EXPN enumeration"
        fi

        # ----- RPCbind -----
        if port_open "$ip" 111 "tcp" 2>/dev/null; then
            log_info "  RPCbind on ${ip}"
            local out="${dir}/nmap_rpc_${ts}"
            run_rc_scan "rpcinfo" -Pn -p 111 $flags --script "rpcinfo" "$ip" -oA "$out"
            add_followup "$ip" "RPCbind open" "Review exposed RPC services; correlate with NFS/NIS findings"
        fi

    done <<< "$live_hosts"

    # Deduplicate tls_targets.txt  safe across multiple partial runs / re-runs
    if [[ -f "working/tls_targets.txt" ]]; then
        sort -u "working/tls_targets.txt" -o "working/tls_targets.txt"
        log_ok "TLS targets: $(wc -l < working/tls_targets.txt | tr -d ' ') unique entries  working/tls_targets.txt"
    fi

    # Finalise follow-up file
    echo "" >> "$FOLLOWUP_FILE"
    echo "## TLS Targets (for 04_tls_scan.sh)" >> "$FOLLOWUP_FILE"
    echo "File: \`working/tls_targets.txt\`" >> "$FOLLOWUP_FILE"
    if [[ -f "working/tls_targets.txt" ]]; then
        cat "working/tls_targets.txt" >> "$FOLLOWUP_FILE"
    fi

    echo "" >> "$FOLLOWUP_FILE"
    echo "---" >> "$FOLLOWUP_FILE"
    echo "*Generated: $(_now) | ${PROJECT_NAME} | Session: ${SESSION_TS}*" >> "$FOLLOWUP_FILE"

    export_db "enum"
    log_ok "Enumeration complete"
    log_ok "Manual follow-up list: ${FOLLOWUP_FILE}"
}


# =============================================================================
# MRK:03_P4B — PHASE 4b: PTE SERVICE ENUMERATION | p4b,phase,4b,pte,service | L2462-2627
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================
# PTE focus: web, TLS, auth, API, SSH, VPN, mail
# PTI-only services stripped: SMB, NFS, OT/ICS, MQTT, IPMI, RPC, Telnet (flagged only)

phase_enum_pte() {
    log "=== PHASE 4: SERVICE ENUMERATION [PTE MODE] ==="
    init_followup

    local live_hosts; live_hosts="$(get_scan_hosts)"
    if [[ -z "$live_hosts" ]]; then
        # No hosts from DB, CSV, or gnmap sweep files  fall back to configured scope.
        # port_open() and get_open_tcp() will try gnmap then all-open assumption for
        # service checks, so per-service enum still runs on the configured targets.
        log_info "phase_enum_pte: no hosts from DB/CSV/gnmap  using configured scope (all_targets)"
        live_hosts="$(build_target_list)"
    fi
    if [[ -z "$live_hosts" ]]; then
        log_warn "phase_enum_pte: no targets available  skipping"
        return 0
    fi

    while IFS= read -r ip; do
        [[ -z "$ip" ]] && continue
        local tier; tier="$(resolve_tier "$ip")"
        local dir; dir="$(ip_dir "$ip")"
        local ts; ts="$(_ts)"
        local flags; flags="$(nmap_tier_flags "$tier" 1)"

        log "PTE enum: ${ip} [${tier}]"

        #  SSH 
        if port_open "$ip" 22 "tcp" 2>/dev/null; then
            log_info "  SSH on ${ip}"
            local out="${dir}/nmap_ssh_${ts}"
            run_rc_scan "ssh-auth-methods" -Pn -p 22 $flags --script "ssh-auth-methods,ssh-hostkey,ssh2-enum-algos" "$ip" -oA "$out"
            add_followup "$ip" "SSH detected" "Version CVE check (regreSSHion); auth methods review"
        fi

        #  Web / HTTP 
        local web_ports=()
        for wp in 80 443 8080 8443 4443 8888 9443 9200 10443 8006; do
            port_open "$ip" "$wp" "tcp" 2>/dev/null && web_ports+=("$wp")
        done
        if [[ ${#web_ports[@]} -gt 0 ]]; then
            log_info "  Web ports on ${ip}: ${web_ports[*]}"
            local port_str; port_str=$(IFS=','; echo "${web_ports[*]}")
            local out="${dir}/nmap_http_${ts}"
            # http-waf-detect / http-waf-fingerprint: WAF detection  critical for PTE to
            # understand defensive controls before deeper testing. Adds minimal noise.
            run_rc_scan "http-title" -Pn -p "$port_str" $flags \
                --script "http-title,http-headers,http-auth-finder,http-methods,http-default-accounts,http-robots.txt,http-security-headers,http-waf-detect,http-waf-fingerprint" \
                "$ip" -oA "$out"
            for wp in "${web_ports[@]}"; do
                case "$wp" in 443|8443|4443|9443|10443)
                    echo "${ip}:${wp}" >> "working/tls_targets.txt"
                    ;;
                esac
            done
            add_followup "$ip" "Web service(s): ${web_ports[*]}" "Run 04_tls_scan.sh; run 05_web_enum.sh; test auth endpoints; check WAF detection output"
            # Cloud metadata SSRF  flag for manual test on every externally exposed web host
            add_followup "$ip" "Web  SSRF/cloud metadata test" "Manual: probe for SSRF to 169.254.169.254 (AWS/Azure/GCP IMDS); check IMDSv2 enforcement if applicable"
        fi

        #  SNMP 
        if port_open "$ip" 161 "udp" 2>/dev/null; then
            log_info "  SNMP on ${ip}"
            local out="${dir}/nmap_snmp_${ts}"
            run_rc_scan "snmp-info" -Pn -sU -p 161 $flags --script "snmp-info,snmp-interfaces" "$ip" -oA "$out"
            add_followup "$ip" "SNMP (publicly exposed)" "Test public community; v1/v2c = High"
        fi

        #  LDAP (exposed externally = critical finding candidate) 
        if any_port_open "$ip" 389 636 3268; then
            log_info "  LDAP externally exposed on ${ip}  High severity candidate"
            local out="${dir}/nmap_ldap_${ts}"
            run_rc_scan "ldap-rootdse" -Pn -p 389,636,3268 $flags --script "ldap-rootdse" "$ip" -oA "$out"
            add_followup "$ip" "LDAP externally exposed  HIGH" "Anonymous bind test; confirm exposure"
        fi

        #  RDP (externally exposed) 
        if port_open "$ip" 3389 "tcp" 2>/dev/null; then
            log_warn "  RDP externally exposed on ${ip}  High severity"
            local out="${dir}/nmap_rdp_${ts}"
            run_rc_scan "rdp-enum-encryption" -Pn -p 3389 $flags --script "rdp-enum-encryption" "$ip" -oA "$out"
            add_followup "$ip" "RDP externally exposed  HIGH" "NLA check; brute-force surface; firewall exposure"
        fi

        #  VPN / Firewall / Gateway 
        # Trigger on VPN-protocol ports only  500 (IKE/IPSec), 1194 (OpenVPN), 1723 (PPTP).
        # SSL-VPN web consoles (4443, 10443, 8443) are already covered by the HTTP section above.
        if any_port_open "$ip" 500 1194 1723; then
            log_info "  VPN/gateway ports on ${ip}"
            local out="${dir}/nmap_vpn_${ts}"
            run_rc_scan "ike-version" -Pn -sU -p 500,4500 $flags --script "ike-version" "$ip" -oA "$out"
            add_followup "$ip" "VPN/gateway detected (IKE/IPSec or OpenVPN)" "Zyxel CVE-2023-28771/CVE-2024-42057 check; IKE aggressive mode test; version identification"
        fi

        #  Mail 
        if any_port_open "$ip" 25 110 143 465 587 993 995; then
            log_info "  Mail services on ${ip}"
            local out="${dir}/nmap_mail_${ts}"
            run_rc_scan "smtp-commands" -Pn -p 25,110,143,465,587,993,995 $flags --script "smtp-commands,smtp-open-relay,smtp-enum-users,pop3-capabilities,imap-capabilities" "$ip" -oA "$out"
            add_followup "$ip" "Mail services" "Open relay check; cleartext protocol check; auth methods"
        fi

        #  Database (externally exposed = critical) 
        for db_port in 1433 3306 5432 27017 6379 9200; do
            if port_open "$ip" "$db_port" "tcp" 2>/dev/null; then
                local db_name
                case "$db_port" in
                    1433) db_name="MSSQL";; 3306) db_name="MySQL";;
                    5432) db_name="PostgreSQL";; 27017) db_name="MongoDB";;
                    6379) db_name="Redis";; 9200) db_name="Elasticsearch";;
                esac
                log_warn "  EXTERNALLY EXPOSED DB: ${db_name}:${db_port} on ${ip}  CRITICAL candidate"
                add_followup "$ip" "${db_name}:${db_port} EXTERNALLY EXPOSED  CRITICAL" "Immediate manual verification; unauthenticated access test"
            fi
        done

        #  FTP (externally exposed) 
        if port_open "$ip" 21 "tcp" 2>/dev/null; then
            log_warn "  FTP externally exposed on ${ip}"
            local out="${dir}/nmap_ftp_${ts}"
            run_rc_scan "ftp-anon" -Pn -p 21 $flags --script "ftp-anon,ftp-syst,banner" "$ip" -oA "$out"
            add_followup "$ip" "FTP externally exposed" "Anonymous login test; cleartext protocol"
        fi

        #  Telnet (flag only  extremely high severity externally) 
        if port_open "$ip" 23 "tcp" 2>/dev/null; then
            log_warn "  TELNET externally exposed on ${ip}  CRITICAL"
            add_followup "$ip" "Telnet externally exposed  CRITICAL" "Banner grab only; cleartext credential risk; immediate escalation"
        fi

        #  Cisco Smart Install 
        if port_open "$ip" 4786 "tcp" 2>/dev/null; then
            log_warn "  CRITICAL: Cisco Smart Install 4786 on ${ip}"
            add_followup "$ip" "Cisco Smart Install 4786  CRITICAL" "Unauthenticated config replacement  immediate manual verification"
        fi

    done <<< "$live_hosts"

    # Deduplicate tls_targets.txt  safe across multiple partial runs / re-runs
    if [[ -f "working/tls_targets.txt" ]]; then
        sort -u "working/tls_targets.txt" -o "working/tls_targets.txt"
        log_ok "TLS targets: $(wc -l < working/tls_targets.txt | tr -d ' ') unique entries  working/tls_targets.txt"
    fi

    # Finalise follow-up
    {
        echo ""
        echo "## TLS Targets (for 04_tls_scan.sh)"
        echo "File: \`working/tls_targets.txt\`"
        [[ -f "working/tls_targets.txt" ]] && cat "working/tls_targets.txt"
        echo ""
        echo "---"
        echo "*Generated: $(_now) | ${PROJECT_NAME} | Session: ${SESSION_TS}*"
    } >> "$FOLLOWUP_FILE"

    export_db "enum"
    log_ok "PTE enumeration complete"
    log_ok "Follow-up: ${FOLLOWUP_FILE}"
}

# =============================================================================
# MRK:03_P5 — PHASE 5: REPORT / SUMMARY | p5,phase,report,summary | L2628-2698
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

phase_report() {
    log "=== PHASE 5: SCAN SUMMARY ==="
    local ts; ts="$(_ts)"
    local report="working/scan_summary_${ts}.md"
    local host_count; host_count=$(get_scan_hosts | wc -l | tr -d ' ')

    cat > "$report" << EOF
# Scan Summary  ${PROJECT_NAME}
*Generated: $(_now) | Session: ${SESSION_TS}*

## Engagement
- **Project:** ${PROJECT_NAME}
- **Mode:** ${MODE}
- **Subnets:** ${TARGET_SUBNETS:-[none]}
- **IPs:** ${TARGET_IPS:-[none]}
- **Global tier:** ${GLOBAL_TIER}
- **Subnet map:** $(effective_tier_label)
- **Excluded IPs:** ${EXCLUDE_IPS[*]:-none}

## Host Inventory
- **Live hosts discovered:** ${host_count}

## Evidence Produced
### Sweep files (\`evidence/_sweep/\`)
$(ls -1 "${EVIDENCE_BASE}/_sweep/"*.{nmap,xml} 2>/dev/null | sed 's/^/- /' || echo "- none")

### Per-host enum files (\`evidence/<IP>/\`)
$(find "${EVIDENCE_BASE}" -maxdepth 2 -name "*.xml" ! -path "*/_sweep/*" 2>/dev/null | \
  sed 's/^/- /' | head -40 || echo "- none")

## MSF DB Exports (\`evidence/_exports/\`)
$(ls -1 "${EVIDENCE_BASE}/_exports/" 2>/dev/null | sed 's/^/- /' || echo "- none")

## TLS Targets (for 04_tls_scan.sh)
$(cat "working/tls_targets.txt" 2>/dev/null | sed 's/^/- /' || echo "- none identified")

## Manual Follow-up Required
See: \`${FOLLOWUP_FILE}\`

## Next Steps
1. Review per-host enum output in \`evidence/<IP>/\`
2. Run \`04_tls_scan.sh\` against \`working/tls_targets.txt\`
3. Run \`05_web_enum.sh\` against confirmed web hosts
4. Process findings via pt-evidence workflow
5. Generate state snapshot

---
*03_comp_scan.sh v0.8 | TechGuard.*
EOF

    log_ok "Summary report: ${report}"

    # Console summary of manual follow-up
    echo ""
    echo -e "${YELLOW}${NC}"
    echo -e "${YELLOW}  MANUAL FOLLOW-UP REQUIRED${NC}"
    echo -e "${YELLOW}${NC}"
    grep "^|" "$FOLLOWUP_FILE" | grep -v "^| Host" | grep -v "^|---" | while IFS='|' read -r _ host reason action _; do
        echo -e "${CYAN}  ${host}${NC}: ${reason}"
        echo -e "     ${action}"
    done
    echo -e "${YELLOW}${NC}"
    echo -e "  Full list: ${FOLLOWUP_FILE}"
    echo ""
}

# =============================================================================
# MRK:03_MAIN — MAIN | main,03 | L2699-2801
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    echo -e "${GREEN}"
    echo ""
    echo "  03_comp_scan.sh v0.8"
    echo "  TechGuard."
    echo "  Project: ${PROJECT_NAME}"
    echo "  Mode:    ${MODE} | Tier: $(effective_tier_label)"
    echo "  Phase:   ${PHASE}$([ "$DRY_RUN" -eq 1 ] && echo " [DRY RUN]")"
    echo ""
    echo -e "${NC}"

    setup_dirs          # directories first  log file path must exist
    parse_db_conf       # read DB credentials before any workspace ops
    init_exclude_list   # detect tester IPs before scope banner is shown

    # PTE safety check: TARGET_SUBNETS should be empty for external engagements.
    # If the operator forgot to clear the PTI example values, internal RFC-1918
    # subnets would be scanned alongside external PTE targets  almost certainly wrong.
    if [[ "$MODE" == "pte" && -n "${TARGET_SUBNETS:-}" ]]; then
        log_warn "PTE mode: TARGET_SUBNETS is non-empty: ${TARGET_SUBNETS}"
        log_warn "  External (PTE) engagements should use TARGET_IPS or PTE_TARGETS_FILE."
        log_warn "  If you intend to include these subnets, ignore this warning."
        if [[ "${AUTO_YES:-0}" -ne 1 ]]; then
            echo -n "  Press ENTER to continue anyway, or Ctrl-C to abort: "
            read -r _dummy
        fi
    fi

    scope_confirm       # human gate  abort before any network activity if not YES
    verify_source_ip    # PTE: confirm outbound IP matches expected (network touch)
    ensure_workspace    # create/verify MSF workspace (DB touch)
    rate_self_test      # send a few probe packets to validate tier settings

    # Session boundary log
    {
        echo "# Session Start"
        echo "# Time:      $(_now)"
        echo "# Project:   ${PROJECT_NAME}"
        echo "# Mode:      ${MODE}"
        echo "# Tier:      $(effective_tier_label)"
        echo "# Tester IP: ${TESTER_IP:-unverified}"
        echo "# Excluded:  ${EXCLUDE_IPS[*]:-none}"
        echo "# Decoys:    ${USE_DECOYS}"
        echo "# Idle scan: ${IDLE_SCAN_ZOMBIE:-no}"
        echo "# Masscan-only: ${MASSCAN_ONLY}"
        echo "# Dry run:   ${DRY_RUN}"
    } >> "$LOG_FILE"

    local all_phases=("tcp" "udp" "enum" "report")
    local all_phases_with_disc=("discovery" "tcp" "udp" "enum" "report")
    local run_phases=()

    if [[ "$PHASE" == "all" ]]; then
        if [[ "$MODE" == "pti" && "${RUN_DISCOVERY:-1}" -eq 1 ]]; then
            run_phases=("${all_phases_with_disc[@]}")
        else
            run_phases=("${all_phases[@]}")
            [[ "$MODE" == "pti" && "${RUN_DISCOVERY:-1}" -eq 0 ]] \
                && log_info "Discovery skipped (RUN_DISCOVERY=0 in pt-orc.conf)"
        fi
    else
        local found=0
        for p in "${all_phases_with_disc[@]}"; do
            if [[ "$p" == "$PHASE" ]]; then found=1; fi
            if [[ "$found" -eq 1 ]]; then
                run_phases+=("$p")
                [[ "$CONTINUE_MODE" -eq 0 ]] && break
            fi
        done
        if [[ "$found" -eq 0 ]]; then
            log_err "Unknown phase: ${PHASE}. Valid: ${all_phases_with_disc[*]}"
            exit 1
        fi
    fi

    for p in "${run_phases[@]}"; do
        case "$p" in
            discovery) phase_discovery ;;
            tcp)       phase_tcp ;;
            udp)       phase_udp ;;
            enum)      [[ "$MODE" == "pte" ]] && phase_enum_pte || phase_enum ;;
            report)    phase_report ;;
        esac
    done

    # Session end log
    {
        echo "# Session End"
        echo "# Time:    $(_now)"
        echo "# Project: ${PROJECT_NAME}"
        echo "# Phases:  ${run_phases[*]}"
    } >> "$LOG_FILE"
    log_ok "All phases complete. Session: ${SESSION_TS}"
}

main

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
