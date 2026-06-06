#!/usr/bin/env bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:02_NAV_TOC — Section index | nav,toc,index | L5-41
# - MRK:02_LOG — COLOURS AND LOGGING | log,colours,logging | L42-59 | ⚠ no-insert-before
# - MRK:02_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L60-84 | ⚠ no-insert-before; propose-before-edit
# - MRK:02_USAGE — USAGE | usage,02 | L85-109 | ⚠ no-insert-before
# - MRK:02_ARGS — ARGUMENT PARSING | args,argument,parsing | L110-128 | ⚠ no-insert-before
# - MRK:02_DEPS — DEPENDENCY CHECK | deps,dependency,check | L129-166 | ⚠ no-insert-before; read-toc-first
# - MRK:02_TARGETS — TARGET LOADING | targets,target,loading,pte,override | L167-219 | ⚠ no-insert-before; read-toc-first
# - MRK:02_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L220-250 | ⚠ no-insert-before; propose-before-edit
# - MRK:02_CMDWRAP — DRY-RUN COMMAND WRAPPER | cmdwrap,dry,run,command,wrapper | L251-267 | ⚠ no-insert-before
# - MRK:02_STATE — PER-IP ACCUMULATORS | state,ip,accumulators,populated,analyze | L268-281 | ⚠ no-insert-before
# - MRK:02_ANALYZE — PER-IP ANALYSIS | analyze,ip,analysis,whois,ptr | L282-598 | ⚠ no-insert-before; read-toc-first
# - MRK:02_REPORT — CONSOLIDATED REPORT | report,consolidated,working,ip,range | L599-768 | ⚠ no-insert-before; read-toc-first
# - MRK:02_MAIN — MAIN entry point | main,entry,point | L769-820 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 12 entries | Integrity-hash: ba320dcc145dd091 | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# 02_ip_analysis.sh — PTE IP Range & Ownership Analysis — TechGuard. [VAPT-enhanced]
# VAPT additions: AbuseIPDB threat intel (Step 8), VirusTotal IP report (Step 9),
#   cloud JSON range validation, expanded PTR cloud fingerprints, CDN bypass hints.
# =============================================================================
# Purpose:
#   Passive intelligence gathering on PTE scope IPs:
#     ASN / WHOIS ownership, reverse DNS (PTR), routing info (ipinfo.io),
#     geolocation (ip-api.com), cloud/CDN provider detection, traceroute
#     topology, and optional Shodan host summary.
#
#   Output feeds into scope confirmation, report Appendix A (Infrastructure
#   Ownership), and flags third-party/cloud-hosted IPs that require extra
#   RoE care before testing.
#
# Prerequisites: whois, dig, curl, traceroute; shodan CLI optional
# Evidence:      evidence/_ip_analysis/<ip>/ per-IP + consolidated report
# Run after:     01_dns_recon.sh (reads scripts/targets.txt by default)
# Run before:    03_comp_scan.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:02_LOG — COLOURS AND LOGGING | log,colours,logging | L42-59
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
# MRK:02_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L60-84
# NAV-RULE: no-insert-before; propose-before-edit
# =============================================================================

# Load shared engagement config (PROJECT_NAME, MODE, TARGET_IPS, SHODAN_API_KEY,
# PTE_TARGETS_FILE, …)
# shellcheck source=pt-orc.conf
[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found in ${SCRIPT_DIR} — set variables in pt-orc.conf"

EVIDENCE_BASE="evidence"
AUTO_YES=0   # 1 = skip interactive confirmations (not recommended for PTE)
DRY_RUN=0    # 1 = print commands, do not execute
CLI_TARGETS_OVERRIDE=0   # set to 1 by --targets flag; bypasses PTE_TARGETS_FILE

# API rate limits — free tiers are strict; do not reduce these
IPINFO_DELAY=1   # seconds between ipinfo.io calls (free tier: 50k req/month)
GEO_DELAY=1      # seconds between ip-api.com calls  (free tier: 45 req/min)
TRACEROUTE_MAX_HOPS=20
TRACEROUTE_TIMEOUT=3

# Cloud/CDN ASN signatures — extend as needed
CLOUD_ORGS_REGEX="amazon|aws|google|gcp|microsoft|azure|cloudflare|fastly|akamai|limelight|incapsula|imperva|sucuri|digitalocean|linode|vultr|ovh|hetzner|rackspace|softlayer|cloudfront|stackpath|edgecast|verizon|leaseweb|choopa|zenlayer|cogent|equinix"

# VAPT: optional threat intel API keys (set in pt-orc.conf)
ABUSEIPDB_API_KEY="${ABUSEIPDB_API_KEY:-}"
VIRUSTOTAL_API_KEY="${VIRUSTOTAL_API_KEY:-}"

# =============================================================================
# MRK:02_USAGE — USAGE | usage,02 | L85-109
# NAV-RULE: no-insert-before
# =============================================================================

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --yes               Skip scope confirmation prompt (AUTO_YES=1)
  --dry-run           Print commands without executing them
  --mode <pte|pti>    Set engagement mode (default: pte)
  --targets "ip ..."  Space-separated list of target IPs (overrides targets file)
  --shodan-key <key>  Shodan API key (overrides SHODAN_API_KEY in config)
  -h, --help          Show this help message and exit

Examples:
  $0 --targets "1.2.3.4 5.6.7.8"
  $0 --mode pte --yes
  $0 --dry-run
  $0 --shodan-key YOURKEY123
EOF
}

# =============================================================================
# MRK:02_ARGS — ARGUMENT PARSING | args,argument,parsing | L110-128
# NAV-RULE: no-insert-before
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --yes)           AUTO_YES=1 ; shift ;;
            --dry-run)       DRY_RUN=1  ; shift ;;
            --mode)          MODE="$2"  ; shift 2 ;;
            --targets)       TARGET_IPS="$2"; CLI_TARGETS_OVERRIDE=1 ; shift 2 ;;
            --shodan-key)    SHODAN_API_KEY="$2" ; shift 2 ;;
            -h|--help)       usage ; exit 0 ;;
            *) log_err "Unknown argument: $1"; usage; exit 1 ;;
        esac
    done
}

# =============================================================================
# MRK:02_DEPS — DEPENDENCY CHECK | deps,dependency,check | L129-166
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

check_deps() {
    log "Checking dependencies..."
    local missing=0

    for tool in whois dig curl; do
        if command -v "$tool" &>/dev/null; then
            log_ok "  ${tool}: found"
        else
            log_err "  ${tool}: NOT FOUND — required"
            (( missing++ )) || true
        fi
    done

    if command -v traceroute &>/dev/null; then
        log_ok "  traceroute: found"
    elif command -v tracepath &>/dev/null; then
        log_warn "  traceroute: not found — will fall back to tracepath"
    else
        log_warn "  traceroute/tracepath: not found — Step 6 will be skipped"
    fi

    if command -v shodan &>/dev/null; then
        log_ok "  shodan CLI: found"
    else
        log_warn "  shodan CLI: not found — Step 7 (Shodan) will be skipped"
    fi

    if [[ "$missing" -gt 0 ]]; then
        log_err "Missing ${missing} required tool(s). Install and re-run."
        exit 1
    fi
}

# =============================================================================
# MRK:02_TARGETS — TARGET LOADING | targets,target,loading,pte,override | L167-219
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

TARGETS=()

load_targets() {
    if [[ "$CLI_TARGETS_OVERRIDE" -eq 1 ]]; then
        # Explicit --targets flag overrides everything
        log "Loading targets from --targets flag..."
        for ip in $TARGET_IPS; do
            if [[ "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
                TARGETS+=("$ip")
            else
                log_warn "  Skipping non-IPv4 value: ${ip}"
            fi
        done
    elif [[ -f "$PTE_TARGETS_FILE" ]]; then
        # Standard PTE flow: always load from targets.txt (produced by 01_dns_recon.sh).
        # Contains DNS-resolved IPs, provided IPs, and live-verified hosts.
        log "Loading targets from ${PTE_TARGETS_FILE}..."
        while IFS= read -r line; do
            [[ -z "$line" || "$line" == \#* ]] && continue
            if [[ "$line" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
                TARGETS+=("$line")
            fi
        done < "$PTE_TARGETS_FILE"
    else
        # PTI note: 02 is primarily an external-intel script (whois/ASN/traceroute/
        # Shodan). Pure-internal PTIs have no external IPs to analyse; exit 0 so
        # the orchestrator moves on to 03.
        if [[ "${MODE:-}" == "pti" ]]; then
            log_ok "PTI mode + no TARGET_IPS/${PTE_TARGETS_FILE}  no external IPs to analyse, skipping IP analysis"
            exit 0
        fi
        log_err "No targets provided and ${PTE_TARGETS_FILE} not found."
        log_err "Run 01_dns_recon.sh first, or pass --targets <ip list> for a manual run."
        exit 1
    fi

    if [[ "${#TARGETS[@]}" -eq 0 ]]; then
        if [[ "${MODE:-}" == "pti" ]]; then
            log_ok "PTI mode + targets.txt has no valid IPv4  skipping IP analysis"
            exit 0
        fi
        log_err "No valid IPv4 addresses found in targets."
        exit 1
    fi

    log_ok "Loaded ${#TARGETS[@]} target IP(s)"
}

# =============================================================================
# MRK:02_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L220-250
# NAV-RULE: no-insert-before; propose-before-edit
# =============================================================================

scope_confirm() {
    [[ "$AUTO_YES" -eq 1 ]] && return 0

    echo ""
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  SCOPE CONFIRMATION — 02_ip_analysis.sh${NC}"
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════════${NC}"
    printf "  %-22s %s\n" "Project:"     "$PROJECT_NAME"
    printf "  %-22s %s\n" "Mode:"        "$MODE"
    printf "  %-22s %s\n" "IP count:"    "${#TARGETS[@]}"
    printf "  %-22s %s\n" "Shodan:"      "$([ -n "$SHODAN_API_KEY" ] && echo "enabled" || echo "no key")"
    printf "  %-22s %s\n" "Dry run:"     "$([ "$DRY_RUN" -eq 1 ] && echo "YES" || echo "no")"
    echo ""
    echo -e "${BOLD}  Target IPs:${NC}"
    for ip in "${TARGETS[@]}"; do
        printf "    %s\n" "$ip"
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
# MRK:02_CMDWRAP — DRY-RUN COMMAND WRAPPER | cmdwrap,dry,run,command,wrapper | L251-267
# NAV-RULE: no-insert-before
# =============================================================================

# Usage: run_cmd <label> <cmd> [args...]
# In dry-run mode: prints command, does not execute.
# Returns output via stdout in live mode; empty string in dry-run.
run_cmd() {
    local label="$1"; shift
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] ${label}: $*"
        return 0
    fi
    "$@" 2>/dev/null || true
}

# =============================================================================
# MRK:02_STATE — PER-IP ACCUMULATORS | state,ip,accumulators,populated,analyze | L268-281
# NAV-RULE: no-insert-before
# =============================================================================

declare -A IP_PTR         # ip -> PTR record or "[none]"
declare -A IP_ASN         # ip -> ASN number
declare -A IP_ORG         # ip -> org/AS name
declare -A IP_COUNTRY     # ip -> country
declare -A IP_PREFIX      # ip -> BGP prefix
declare -A IP_CLOUD       # ip -> cloud match string or ""
declare -A IP_HOPS        # ip -> traceroute hop count or "n/a"
declare -A IP_PORTS       # ip -> Shodan open ports summary or ""

# =============================================================================
# MRK:02_ANALYZE — PER-IP ANALYSIS | analyze,ip,analysis,whois,ptr | L282-598
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

analyze_ip() {
    local ip="$1"
    local safe="${ip//./_}"
    local ipdir="${EVIDENCE_BASE}/_ip_analysis/${safe}"

    if [[ "$DRY_RUN" -eq 0 ]]; then
        mkdir -p "$ipdir"
    else
        log_info "  [DRY-RUN] mkdir -p ${ipdir}"
    fi

    # Initialise accumulators for this IP
    IP_PTR["$ip"]="[none]"
    IP_ASN["$ip"]="[unknown]"
    IP_ORG["$ip"]="[unknown]"
    IP_COUNTRY["$ip"]="[unknown]"
    IP_PREFIX["$ip"]="[unknown]"
    IP_CLOUD["$ip"]=""
    IP_HOPS["$ip"]="n/a"
    IP_PORTS["$ip"]=""

    # ── Step 1: WHOIS / ASN ─────────────────────────────────────────────────
    log "  [${ip}] Step 1: WHOIS / ASN"
    local whois_file="${ipdir}/whois_${safe}.txt"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] timeout 10 whois ${ip} > ${whois_file}"
    else
        {
            echo "# WHOIS — ${ip}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "---"
            timeout 10 whois "$ip" 2>/dev/null || echo "[WARN] whois timed out or failed"
        } > "$whois_file" || true

        # Extract fields — try common WHOIS field variants
        local whois_org whois_asn whois_netname whois_country whois_cidr
        whois_org=$(grep -iE "^(OrgName|org-name|owner|netname):" "$whois_file" \
                    | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r' || true)
        whois_asn=$(grep -iE "^(aut-num|origin):" "$whois_file" \
                    | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r' || true)
        whois_netname=$(grep -iE "^netname:" "$whois_file" \
                        | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r' || true)
        whois_country=$(grep -iE "^country:" "$whois_file" \
                        | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r' || true)
        whois_cidr=$(grep -iE "^(CIDR|inetnum|NetRange):" "$whois_file" \
                     | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r' || true)

        [[ -n "$whois_org" ]]     && log_info "  WHOIS OrgName:  ${whois_org}"
        [[ -n "$whois_asn" ]]     && { log_info "  WHOIS ASN:      ${whois_asn}"; IP_ASN["$ip"]="$whois_asn"; }
        [[ -n "$whois_netname" ]] && log_info "  WHOIS netname:  ${whois_netname}"
        [[ -n "$whois_country" ]] && { log_info "  WHOIS country:  ${whois_country}"; IP_COUNTRY["$ip"]="$whois_country"; }
        [[ -n "$whois_cidr" ]]    && { log_info "  WHOIS CIDR:     ${whois_cidr}"; IP_PREFIX["$ip"]="$whois_cidr"; }
        [[ -n "$whois_org" ]]     && IP_ORG["$ip"]="$whois_org"

        log_ok "  WHOIS saved: ${whois_file}"
    fi

    # ── Step 2: Reverse DNS ─────────────────────────────────────────────────
    log "  [${ip}] Step 2: Reverse DNS (PTR)"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] dig +short -x ${ip}"
    else
        local ptr
        ptr=$(timeout 10 dig +short -x "$ip" 2>/dev/null | head -1 | sed 's/\.$//' || true)

        if [[ -n "$ptr" ]]; then
            IP_PTR["$ip"]="$ptr"
            log_info "  PTR: ${ptr}"
            # Flag well-known cloud PTR patterns (VAPT-expanded)
            if echo "$ptr" | grep -qiE \
                "compute\.internal|ec2\.internal|googleusercontent\.com|azure\.com|cloudfront\.net|\.amazonaws\.com|\.azure\.net|akamaitechnologies\.com|fastly\.net|cloudflare\.net|digitalocean\.com|linode\.com|vultr\.com|ovh\.net|hetzner\.com|rackspace\.com|softlayer\.com|stackpath\.com|edgecast\.net|choopa\.com|leaseweb\.com"; then
                log_warn "  Cloud PTR pattern detected: ${ptr}"
                IP_CLOUD["$ip"]="PTR:${ptr}"
            fi
        else
            log_info "  PTR: [none]"
        fi
    fi

    # ── Step 3: Routing info (ipinfo.io) ────────────────────────────────────
    # org field: "AS396982 Google LLC" — split into ASN + name
    # prefix: taken from WHOIS CIDR (step 1); ipinfo.io prefix is paid-tier only
    log "  [${ip}] Step 3: Routing info (ipinfo.io)"
    local ipinfo_file="${ipdir}/ipinfo_${safe}.json"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] curl -s --max-time 10 https://ipinfo.io/${ip}/json > ${ipinfo_file}"
        log_info "  [DRY-RUN] sleep ${IPINFO_DELAY}  # rate-limit delay"
    else
        local ipinfo_json
        ipinfo_json=$(curl -s --max-time 10 "https://ipinfo.io/${ip}/json" 2>/dev/null || true)

        if [[ -n "$ipinfo_json" ]]; then
            echo "$ipinfo_json" > "$ipinfo_file" || true

            local ipinfo_org ipinfo_asn ipinfo_asname
            ipinfo_org=$(echo "$ipinfo_json" | python3 -c \
                "import json,sys; d=json.load(sys.stdin); print(d.get('org',''))" 2>/dev/null || true)

            if [[ -n "$ipinfo_org" ]]; then
                # "AS12345 Org Name" → split on first space
                ipinfo_asn=$(echo "$ipinfo_org" | awk '{print $1}')
                ipinfo_asname=$(echo "$ipinfo_org" | cut -d' ' -f2-)
                [[ -n "$ipinfo_asn" ]]    && { log_info "  ipinfo ASN:  ${ipinfo_asn}";    IP_ASN["$ip"]="$ipinfo_asn"; }
                [[ -n "$ipinfo_asname" ]] && { log_info "  ipinfo Org:  ${ipinfo_asname}"; IP_ORG["$ip"]="$ipinfo_asname"; }
            fi
            log_ok "  ipinfo saved: ${ipinfo_file}"
        else
            log_warn "  ipinfo: no response from ipinfo.io"
            echo '{}' > "$ipinfo_file" || true
        fi

        sleep "$IPINFO_DELAY"
    fi

    # ── Step 4: Geolocation (ip-api.com) ────────────────────────────────────
    log "  [${ip}] Step 4: Geolocation (ip-api.com)"
    local geo_file="${ipdir}/geo_${safe}.json"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] curl -s --max-time 10 http://ip-api.com/json/${ip}?fields=... > ${geo_file}"
        log_info "  [DRY-RUN] sleep ${GEO_DELAY}  # rate-limit delay"
    else
        local geo_json
        geo_json=$(curl -s --max-time 10 \
            "http://ip-api.com/json/${ip}?fields=status,country,regionName,city,isp,org,as" \
            2>/dev/null || true)

        if [[ -n "$geo_json" ]]; then
            echo "$geo_json" > "$geo_file" || true

            local geo_country geo_city geo_isp geo_org geo_as
            geo_country=$(echo "$geo_json" | python3 -c \
                "import json,sys; d=json.load(sys.stdin); print(d.get('country',''))" 2>/dev/null || true)
            geo_city=$(echo "$geo_json" | python3 -c \
                "import json,sys; d=json.load(sys.stdin); print(d.get('city',''))" 2>/dev/null || true)
            geo_isp=$(echo "$geo_json" | python3 -c \
                "import json,sys; d=json.load(sys.stdin); print(d.get('isp',''))" 2>/dev/null || true)
            geo_org=$(echo "$geo_json" | python3 -c \
                "import json,sys; d=json.load(sys.stdin); print(d.get('org',''))" 2>/dev/null || true)
            geo_as=$(echo "$geo_json" | python3 -c \
                "import json,sys; d=json.load(sys.stdin); print(d.get('as',''))" 2>/dev/null || true)

            [[ -n "$geo_country" ]] && { log_info "  Geo country:  ${geo_country}"; IP_COUNTRY["$ip"]="$geo_country"; }
            [[ -n "$geo_city" ]]    && log_info "  Geo city:     ${geo_city}"
            [[ -n "$geo_isp" ]]     && log_info "  Geo ISP:      ${geo_isp}"
            [[ -n "$geo_org" ]]     && log_info "  Geo org:      ${geo_org}"
            [[ -n "$geo_as" ]]      && log_info "  Geo AS:       ${geo_as}"
            log_ok "  Geo saved: ${geo_file}"
        else
            log_warn "  Geo: no response from ip-api.com"
            echo '{}' > "$geo_file" || true
        fi

        sleep "$GEO_DELAY"
    fi

    # ── Step 5: Cloud/CDN detection ─────────────────────────────────────────
    log "  [${ip}] Step 5: Cloud/CDN detection"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        local combined_str
        combined_str="${IP_ORG[$ip]:-} ${IP_ASN[$ip]:-} ${IP_PTR[$ip]:-}"

        local cloud_match
        cloud_match=$(echo "$combined_str" | grep -ioE "$CLOUD_ORGS_REGEX" | head -1 || true)

        if [[ -n "$cloud_match" ]]; then
            # Preserve PTR-based flag if already set; append infra match
            if [[ -n "${IP_CLOUD[$ip]:-}" ]]; then
                IP_CLOUD["$ip"]="${IP_CLOUD[$ip]};org:${cloud_match}"
            else
                IP_CLOUD["$ip"]="org:${cloud_match}"
            fi
            log_warn "  CLOUD/CDN: ${ip} — ${cloud_match} — VERIFY RoE before testing"
        else
            log_info "  Cloud/CDN: no match detected"
        fi
    else
        log_info "  [DRY-RUN] cloud/CDN regex check against WHOIS/BGP/geo fields"
    fi

    # ── Step 6: Traceroute ──────────────────────────────────────────────────
    log "  [${ip}] Step 6: Traceroute"
    local tr_file="${ipdir}/traceroute_${safe}.txt"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] traceroute -m ${TRACEROUTE_MAX_HOPS} -w ${TRACEROUTE_TIMEOUT} ${ip} > ${tr_file}"
    else
        local tr_cmd=""
        if command -v traceroute &>/dev/null; then
            tr_cmd="traceroute"
        elif command -v tracepath &>/dev/null; then
            tr_cmd="tracepath"
            log_info "  Using tracepath fallback"
        fi

        if [[ -n "$tr_cmd" ]]; then
            {
                echo "# Traceroute — ${ip}"
                echo "# Engagement: ${PROJECT_NAME}"
                echo "# Date/Time:  $(_now)"
                echo "---"
                if [[ "$tr_cmd" == "traceroute" ]]; then
                    timeout $(( TRACEROUTE_MAX_HOPS * TRACEROUTE_TIMEOUT + 10 )) \
                        traceroute -m "$TRACEROUTE_MAX_HOPS" -w "$TRACEROUTE_TIMEOUT" "$ip" \
                        2>&1 || echo "[WARN] traceroute did not complete"
                else
                    timeout $(( TRACEROUTE_MAX_HOPS * TRACEROUTE_TIMEOUT + 10 )) \
                        tracepath "$ip" \
                        2>&1 || echo "[WARN] tracepath did not complete"
                fi
            } > "$tr_file" || true

            # Count hops: lines that start with a hop number
            local hop_count
            hop_count=$(grep -cE '^\s*[0-9]+\.' "$tr_file" 2>/dev/null || echo 0)
            IP_HOPS["$ip"]="$hop_count"

            # Warn if destination not reached (last hop is not the target IP)
            if ! grep -qE "${ip//./\\.}" "$tr_file" 2>/dev/null; then
                log_warn "  Traceroute: destination ${ip} may not have been reached"
            fi
            log_ok "  Traceroute: ${hop_count} hop(s) — ${tr_file}"
        else
            log_warn "  traceroute/tracepath not found — skipping"
        fi
    fi

    # ── Step 7: Shodan (optional) ───────────────────────────────────────────
    log "  [${ip}] Step 7: Shodan"
    if [[ -n "$SHODAN_API_KEY" ]]; then
        if command -v shodan &>/dev/null; then
            local shodan_file="${ipdir}/shodan_${safe}.txt"
            if [[ "$DRY_RUN" -eq 1 ]]; then
                log_info "  [DRY-RUN] shodan host ${ip} > ${shodan_file}"
            else
                {
                    echo "# Shodan Host — ${ip}"
                    echo "# Engagement: ${PROJECT_NAME}"
                    echo "# Date/Time:  $(_now)"
                    echo "---"
                    SHODAN_API_KEY="$SHODAN_API_KEY" shodan host "$ip" 2>&1 \
                        || echo "[WARN] shodan host lookup failed"
                } > "$shodan_file" || true

                # Extract open ports summary: lines matching "Port: NNNN/proto"
                local ports_summary
                ports_summary=$(grep -E "^[0-9]+/|Port:" "$shodan_file" \
                                | awk '{print $1}' | sort -u | tr '\n' ' ' | sed 's/ $//' || true)
                [[ -n "$ports_summary" ]] && IP_PORTS["$ip"]="$ports_summary"
                log_ok "  Shodan saved: ${shodan_file}"
            fi
        else
            log_warn "  Shodan key set but CLI not found — skipping"
        fi
    else
        log_info "  Shodan: no API key — skipping"
    fi

    # ── Step 8: AbuseIPDB threat intel ─────────────────────────────────────
    log "  [${ip}] Step 8: AbuseIPDB threat intel"
    if [[ -n "${ABUSEIPDB_API_KEY:-}" ]]; then
        if [[ "$DRY_RUN" -eq 1 ]]; then
            log_info "  [DRY-RUN] curl AbuseIPDB /check?ipAddress=${ip}"
        else
            local abuse_file="${ipdir}/abuseipdb_${safe}.json"
            local abuse_resp
            abuse_resp=$(curl -s --max-time 15 \
                "https://api.abuseipdb.com/api/v2/check?ipAddress=${ip}&maxAgeInDays=90&verbose" \
                -H "Key: ${ABUSEIPDB_API_KEY}" \
                -H "Accept: application/json" 2>/dev/null || true)
            if [[ -n "$abuse_resp" ]]; then
                echo "$abuse_resp" > "$abuse_file" || true
                local abuse_score abuse_reports abuse_country abuse_isp
                abuse_score=$(echo "$abuse_resp" | python3 -c \
                    "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('abuseConfidenceScore','?'))" 2>/dev/null || echo "?")
                abuse_reports=$(echo "$abuse_resp" | python3 -c \
                    "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('totalReports','?'))" 2>/dev/null || echo "?")
                log_info "  AbuseIPDB score: ${abuse_score}/100 | reports: ${abuse_reports}"
                [[ "$abuse_score" =~ ^[0-9]+$ ]] && [[ "$abuse_score" -ge 50 ]] && \
                    log_warn "  HIGH abuse score (${abuse_score}) — IP may be flagged/blocked mid-engagement"
                log_ok "  AbuseIPDB saved: ${abuse_file}"
            fi
            sleep 1  # rate limit: free tier 1000 req/day
        fi
    else
        log_info "  AbuseIPDB: no API key — skipping (set ABUSEIPDB_API_KEY in pt-orc.conf)"
    fi

    # ── Step 9: VirusTotal IP report ────────────────────────────────────────
    log "  [${ip}] Step 9: VirusTotal IP report"
    if [[ -n "${VIRUSTOTAL_API_KEY:-}" ]]; then
        if [[ "$DRY_RUN" -eq 1 ]]; then
            log_info "  [DRY-RUN] curl VirusTotal /ip_addresses/${ip}"
        else
            local vt_file="${ipdir}/virustotal_${safe}.json"
            local vt_resp
            vt_resp=$(curl -s --max-time 15 \
                "https://www.virustotal.com/api/v3/ip_addresses/${ip}" \
                -H "x-apikey: ${VIRUSTOTAL_API_KEY}" 2>/dev/null || true)
            if [[ -n "$vt_resp" ]]; then
                echo "$vt_resp" > "$vt_file" || true
                local vt_malicious vt_harmless vt_suspicious
                vt_malicious=$(echo "$vt_resp" | python3 -c \
                    "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('attributes',{}).get('last_analysis_stats',{}).get('malicious','?'))" 2>/dev/null || echo "?")
                vt_harmless=$(echo "$vt_resp" | python3 -c \
                    "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('attributes',{}).get('last_analysis_stats',{}).get('harmless','?'))" 2>/dev/null || echo "?")
                vt_suspicious=$(echo "$vt_resp" | python3 -c \
                    "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('attributes',{}).get('last_analysis_stats',{}).get('suspicious','?'))" 2>/dev/null || echo "?")
                log_info "  VirusTotal: malicious=${vt_malicious} suspicious=${vt_suspicious} harmless=${vt_harmless}"
                [[ "$vt_malicious" =~ ^[0-9]+$ ]] && [[ "$vt_malicious" -gt 0 ]] && \
                    log_warn "  ${vt_malicious} VT engines flagged ${ip} as malicious — investigate before scanning"
                log_ok "  VirusTotal saved: ${vt_file}"
            fi
            sleep 15  # free tier: 4 lookups/min
        fi
    else
        log_info "  VirusTotal: no API key — skipping (set VIRUSTOTAL_API_KEY in pt-orc.conf)"
    fi

    # ── Per-IP summary markdown ─────────────────────────────────────────────
    local summary_file="${ipdir}/summary_${safe}.md"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] write ${summary_file}"
    else
        {
            cat <<EOF
# IP Analysis Summary — ${ip}
*Engagement: ${PROJECT_NAME} | Date: $(_now) | Mode: ${MODE}*

## Identity
| Field    | Value |
|----------|-------|
| IP       | ${ip} |
| PTR      | ${IP_PTR[$ip]:-[none]} |
| ASN      | ${IP_ASN[$ip]:-[unknown]} |
| Org/Name | ${IP_ORG[$ip]:-[unknown]} |
| Country  | ${IP_COUNTRY[$ip]:-[unknown]} |
| Prefix   | ${IP_PREFIX[$ip]:-[unknown]} |

## Cloud/CDN Flag
$(if [[ -n "${IP_CLOUD[$ip]:-}" ]]; then
    echo "**CLOUD/CDN DETECTED: ${IP_CLOUD[$ip]}**"
    echo ""
    echo "> VERIFY RoE before active testing. This IP may be shared infrastructure."
else
    echo "No cloud/CDN indicators detected."
fi)

## Traceroute
- Hop count: ${IP_HOPS[$ip]:-n/a}
- Raw file: traceroute_${safe}.txt

## Shodan
$(if [[ -n "${IP_PORTS[$ip]:-}" ]]; then
    echo "Open ports: ${IP_PORTS[$ip]}"
else
    echo "No Shodan data (no key or lookup skipped)."
fi)

## Evidence Files
$(ls -1 "${ipdir}/" 2>/dev/null | sed "s/^/- evidence\/_ip_analysis\/${safe}\//" || true)

---
*02_ip_analysis.sh | TechGuard | ${PROJECT_NAME}*
EOF
        } > "$summary_file" || true
        log_ok "  Per-IP summary: ${summary_file}"
    fi
}

# =============================================================================
# MRK:02_REPORT — CONSOLIDATED REPORT | report,consolidated,working,ip,range | L599-768
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

write_report() {
    local report_file="working/ip_range_report_${SESSION_TS}.md"

    log "Writing consolidated report: ${report_file}"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_info "  [DRY-RUN] write ${report_file}"
        return 0
    fi

    # Build ASN grouping (asn -> space-sep list of IPs)
    declare -A asn_groups
    for ip in "${TARGETS[@]}"; do
        local asn="${IP_ASN[$ip]:-[unknown]}"
        asn_groups["$asn"]="${asn_groups[$asn]:-} ${ip}"
    done

    # Build prefix list
    declare -A prefix_set
    for ip in "${TARGETS[@]}"; do
        local pfx="${IP_PREFIX[$ip]:-}"
        [[ -n "$pfx" ]] && prefix_set["$pfx"]=1
    done

    {
        cat <<EOF
# IP Range & Ownership Report — ${PROJECT_NAME}
*Generated: $(_now) | Session: ${SESSION_TS}*

---

## Engagement Metadata
| Field        | Value |
|--------------|-------|
| Project      | ${PROJECT_NAME} |
| Date         | $(_now) |
| Mode         | ${MODE} |
| Script       | 02_ip_analysis.sh |
| IP count     | ${#TARGETS[@]} |
| Shodan       | $([ -n "$SHODAN_API_KEY" ] && echo "enabled" || echo "not configured") |

---

## Target IP Inventory
| IP | PTR | ASN | Org | Country | Cloud? |
|----|-----|-----|-----|---------|--------|
EOF

        for ip in "${TARGETS[@]}"; do
            local cloud_flag="no"
            [[ -n "${IP_CLOUD[$ip]:-}" ]] && cloud_flag="**YES — ${IP_CLOUD[$ip]}**"
            printf "| %s | %s | %s | %s | %s | %s |\n" \
                "$ip" \
                "${IP_PTR[$ip]:-[none]}" \
                "${IP_ASN[$ip]:-[unknown]}" \
                "${IP_ORG[$ip]:-[unknown]}" \
                "${IP_COUNTRY[$ip]:-[unknown]}" \
                "$cloud_flag"
        done

        echo ""
        echo "---"
        echo ""
        echo "## Cloud/CDN-Hosted IPs"
        echo ""
        local cloud_count=0
        for ip in "${TARGETS[@]}"; do
            if [[ -n "${IP_CLOUD[$ip]:-}" ]]; then
                echo "- **${ip}** — ${IP_CLOUD[$ip]}"
                echo "  > RoE Advisory: Confirm client owns or controls this IP before active scanning."
                echo "  > Cloud/CDN IPs may be shared infrastructure. Obtain written permission from"
                echo "  > the cloud provider or verify the IP is dedicated to this client."
                echo ""
                (( cloud_count++ )) || true
            fi
        done
        [[ "$cloud_count" -eq 0 ]] && echo "No cloud/CDN-hosted IPs detected."

        echo ""
        echo "---"
        echo ""
        echo "## ASN Grouping"
        echo ""
        set +u
        for asn in $(printf '%s\n' "${!asn_groups[@]}" | sort); do
            echo "### ${asn}"
            for ip in ${asn_groups[$asn]}; do
                printf "  - %s (%s)\n" "$ip" "${IP_ORG[$ip]:-[unknown]}"
            done
            echo ""
        done
        set -u

        echo "---"
        echo ""
        echo "## BGP Prefix Coverage"
        echo ""
        set +u
        if [[ "${#prefix_set[@]}" -gt 0 ]]; then
            echo "| Prefix | IPs in scope |"
            echo "|--------|-------------|"
            for pfx in $(printf '%s\n' "${!prefix_set[@]}" | sort); do
                local pfx_ips=""
                for ip in "${TARGETS[@]}"; do
                    [[ "${IP_PREFIX[$ip]:-}" == "$pfx" ]] && pfx_ips="${pfx_ips} ${ip}"
                done
                printf "| %s | %s |\n" "$pfx" "${pfx_ips# }"
            done
        else
            echo "No BGP prefix data collected."
        fi
        set -u

        echo ""
        echo "---"
        echo ""
        echo "## Traceroute Summary"
        echo ""
        echo "| IP | Hop Count |"
        echo "|----|-----------|"
        for ip in "${TARGETS[@]}"; do
            printf "| %s | %s |\n" "$ip" "${IP_HOPS[$ip]:-n/a}"
        done

        echo ""
        echo "---"
        echo ""
        echo "## Recommendations"
        echo ""
        cat <<'RECS'
- **Cloud/CDN IPs (if any flagged above):** Do not begin active testing until written
  authorisation is obtained confirming the client owns/controls the IP, or until the
  cloud provider's own penetration testing policy is satisfied (e.g. AWS Penetration
  Testing Policy, Azure Penetration Testing T&Cs).

- **Shared hosting / CDN bypass:** If a target resolves to a CDN edge IP, confirm
  the origin IP with the client and add it to scope explicitly. CDN bypass testing
  (direct origin IP, Host header manipulation) should be included in scope.

- **IPs with no PTR record:** May indicate dynamically assigned addresses or
  infrastructure maintained with minimal DNS hygiene. Flag for manual scope
  confirmation with client before active scanning.

- **Multi-ASN scope:** Where IPs span multiple ASNs/orgs (see ASN Grouping above),
  confirm each netblock with the client. Third-party-managed IPs require separate
  written authorisation.

- **Traceroute topology:** Review per-IP traceroute files for shared intermediate
  hops — these can reveal upstream infrastructure and help detect filtering or WAF
  choke points between tester and target.

- **Shodan enrichment:** If Shodan data is available, cross-reference open port
  listings against 03_comp_scan.sh results to confirm scan coverage and
  identify any ports that may be filtered from the tester's source IP.

- **Threat intel (AbuseIPDB/VirusTotal):** IPs with high abuse confidence scores
  or positive VT detections may be sinkholes, honeypots, or adversary-controlled.
  Cross-reference before active scanning — a high-score IP may already be
  actively monitored. Set ABUSEIPDB_API_KEY and VIRUSTOTAL_API_KEY in pt-orc.conf.

- **CDN bypass:** For CDN-fronted targets, request the client's origin IP(s)
  and add them to scope. Test direct origin access via: curl -H "Host: target.com"
  https://origin-ip/ — bypass may expose unpatched origin servers not behind WAF.
RECS

        echo ""
        echo "---"
        echo "*02_ip_analysis.sh | TechGuard | ${PROJECT_NAME}*"

    } > "$report_file" || true

    log_ok "Report written: ${report_file}"
}

# =============================================================================
# MRK:02_MAIN — MAIN entry point | main,entry,point | L769-820
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    parse_args "$@"

    echo -e "${GREEN}"
    echo "════════════════════════════════════════════════"
    echo "  02_ip_analysis.sh"
    echo "  TechGuard."
    echo "  Project: ${PROJECT_NAME}"
    echo "  Mode:    ${MODE}"
    echo "════════════════════════════════════════════════"
    echo -e "${NC}"

    check_deps
    load_targets
    scope_confirm

    mkdir -p "${EVIDENCE_BASE}/_ip_analysis"
    mkdir -p "working"

    local total="${#TARGETS[@]}"
    local i=0

    for ip in "${TARGETS[@]}"; do
        (( i++ )) || true
        log "Analysing ${ip} (${i}/${total})..."
        # analyze_ip uses || true throughout — call directly so array assignments
        # survive to write_report (subshell would discard all IP_* assignments)
        analyze_ip "$ip" || log_warn "  analyze_ip failed for ${ip} — continuing with remaining targets"
        echo ""
    done

    write_report

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  IP Range Analysis Complete — ${PROJECT_NAME}${NC}"
    echo -e "${GREEN}  IPs analysed:  ${total}${NC}"
    echo -e "${GREEN}  Evidence base: ${EVIDENCE_BASE}/_ip_analysis/${NC}"
    echo -e "${GREEN}  Report:        working/ip_range_report_${SESSION_TS}.md${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════${NC}"
    echo ""
    echo "Next step: sudo ./03_comp_scan.sh --mode pte"
}

main "$@"

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
