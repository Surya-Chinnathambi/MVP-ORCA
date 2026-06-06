#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:01_NAV_TOC — Section index | nav,toc,index | L5-46
# - MRK:01_ROOT — ROOT CHECK | root,check | L47-56 | ⚠ no-insert-before
# - MRK:01_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L57-101 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:01_LOG — COLOURS AND LOGGING | log,colours,logging | L102-128 | ⚠ no-insert-before
# - MRK:01_ARGS — ARGUMENT PARSING | args,argument,parsing | L129-148 | ⚠ no-insert-before
# - MRK:01_SRCIP — SOURCE IP VERIFICATION | srcip,source,ip,verification,abort | L149-169 | ⚠ no-insert-before
# - MRK:01_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L170-202 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:01_SCOPE — THIRD-PARTY / PRIVATE IP BOUNDARY CHECKS + add_ip accumulator | scope,third,party,private,ip | L203-240 | ⚠ no-insert-before; read-toc-first
# - MRK:01_TAKEOVER — SUBDOMAIN TAKEOVER DETECTION | takeover,subdomain,detection,curl,patterns | L241-262 | ⚠ no-insert-before
# - MRK:01_STATE — TARGET ACCUMULATORS | state,target,accumulators,discovered,ips | L263-288 | ⚠ no-insert-before
# - MRK:01_PASSIVE — PASSIVE RECON | passive,recon,crt,sh,subfinder | L289-419 | ⚠ no-insert-before; read-toc-first
# - MRK:01_ACTIVE — ACTIVE DNS | active,dns,axfr,attempts,subdomain | L420-472 | ⚠ no-insert-before; read-toc-first
# - MRK:01_RESOLVE — RESOLUTION AND LIVE CHECK | resolve,resolution,live,check,cname | L473-536 | ⚠ no-insert-before; read-toc-first
# - MRK:01_OUTPUT — TARGET LIST + SUMMARY | output,target,list,summary,write | L537-653 | ⚠ no-insert-before; read-toc-first
# - MRK:01_MAIN — MAIN entry point | main,entry,point | L654-811 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 14 entries | Integrity-hash: 42c33e21f72f302e | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# 01_dns_recon.sh — TechGuard. [VAPT-enhanced]
# PTE DNS/OSINT Reconnaissance
# VAPT additions: 40+ subdomain takeover fingerprints, dnsx fast resolution,
#   puredns DNS bruteforce, DNSSEC validation, cloud range verification,
#   DNS-over-HTTPS detection, expanded CDN CIDR ranges.
# =============================================================================
# USAGE:
#   sudo ./01_dns_recon.sh [OPTIONS]
#
# OPTIONS:
#   --yes             Skip scope confirmation prompt
#   --dry-run         Print what would run without executing
#   --skip-active     Skip active DNS probes (AXFR, brute) — passive only
#   --append          Append to existing scripts/targets.txt (default: overwrite)
#
# OUTPUT:
#   evidence/_dns/            — all raw tool output
#   scripts/targets.txt       — confirmed live IPs for 03_comp_scan.sh
#   working/dns_summary_<TS>.md  — analyst summary
#
# Engagement config lives in pt-orc.conf (sourced below). Edit once per engagement.
set -uo pipefail

# Location of this script — use to keep evidence inside the repo
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:01_ROOT — ROOT CHECK | root,check | L47-56
# NAV-RULE: no-insert-before
# =============================================================================
if [[ "$EUID" -ne 0 ]] && [[ "${PTORC_ALLOW_NON_ROOT:-0}" != "1" ]]; then
    echo "[ERROR] This script must be run as root."
    echo "        Run: sudo $0 $*"
    exit 1
fi

# =============================================================================
# MRK:01_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L57-101
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

# Load shared engagement config (PROJECT_NAME, MODE, TARGET_DOMAINS, TARGET_IPS,
# TESTER_IP, SHODAN_API_KEY, CENSYS_*, SECURITYTRAILS_*, AMASS_BRUTE, …)
# shellcheck source=pt-orc.conf
[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found in ${SCRIPT_DIR} — set variables in pt-orc.conf"

# Script-local paths and tool settings — not engagement-specific
EVIDENCE_BASE="${SCRIPT_DIR}/evidence"
ENABLE_HARVESTER=1    # 0 = skip theHarvester

# Known CDN/third-party CIDR ranges — IPs in these are flagged out-of-scope
THIRDPARTY_RANGES=(
    # Cloudflare
    "104.16.0.0/12"
    "172.64.0.0/13"
    "103.21.244.0/22"
    "103.22.200.0/22"
    "103.31.4.0/22"
    "141.101.64.0/18"
    "108.162.192.0/18"
    "190.93.240.0/20"
    "188.114.96.0/20"
    "197.234.240.0/22"
    "198.41.128.0/17"
    "162.158.0.0/15"
    "104.24.0.0/14"
    # Fastly
    "151.101.0.0/16"
    "199.27.72.0/21"
    "23.235.32.0/20"
    # AWS CloudFront
    "13.32.0.0/15"
    "52.84.0.0/15"
    "13.224.0.0/14"
    "54.182.0.0/16"
    "99.84.0.0/16"
    "205.251.192.0/19"
    # AWS general (commonly shared infra)
    "52.92.0.0/20"
    "52.216.0.0/14"
    # Akamai
    "23.0.0.0/12"
    "23.192.0.0/11"
    "2.16.0.0/13"
    "92.122.0.0/15"
    # Azure CDN / Front Door
    "104.40.0.0/13"
    "20.60.0.0/16"
    "13.107.246.0/24"
    "20.190.128.0/18"
    # Google (Cloud CDN / LB)
    "35.190.0.0/17"
    "35.191.0.0/16"
    "130.211.0.0/22"
    "34.64.0.0/10"
    # StackPath
    "151.139.0.0/17"
    # Incapsula/Imperva
    "199.83.128.0/21"
    "198.143.32.0/21"
    "149.126.72.0/21"
    "103.28.248.0/22"
)

# Subdomain takeover fingerprints (40+ services — VAPT-enhanced)
TAKEOVER_PATTERNS=(
    # GitHub / GitHub Pages
    "There isn't a GitHub Pages site here"
    "githubapp.com"
    # Heroku
    "herokucdn.com/error-pages/no-such-app"
    "No such app"
    # AWS S3
    "The specified bucket does not exist"
    "NoSuchBucket"
    "NoSuchKey"
    # Bitbucket
    "Repository not found"
    "RepositoryNotFound"
    # UserVoice
    "This UserVoice subdomain is currently available"
    # GitLab
    "project not found"
    "The page you're looking for could not be found"
    # JetBrains YouTrack
    "is not a registered InCloud YouTrack"
    # Domain parking
    "This page is parked free"
    "This domain has expired"
    # Help Scout / Beacon
    "No settings were found for this"
    # Ghost
    "You've Discovered a Ghost Blog"
    # Tumblr
    "There's nothing here"
    "Whatever you were looking for doesn't currently exist at this address"
    # WordPress.com
    "Do you want to register"
    "Domain mapping upgrade"
    # Zendesk
    "Help Center Closed"
    "Oops, this help center no longer exists"
    # Azure / Microsoft
    "404 Web Site not found"
    "The resource you are looking for has been removed"
    # Shopify
    "Sorry, this shop is currently unavailable"
    # Webflow
    "Sorry, we couldn't find"
    "Page Not Found — Try searching"
    # Surge
    "project not found"
    "If you are the website owner"
    # Unbounce
    "The page you are looking for could not be found"
    # Pantheon
    "The gods are wise, but do not know of the site which you seek"
    # Intercom
    "Uh oh. That page doesn't exist"
    "This user doesn't exist"
    # Helpjuice
    "We could not find what you're looking for"
    # Campaign Monitor
    "Double check the URL"
    # Mailgun
    "This domain is not configured for use with Mailgun"
    # Fastly
    "Fastly error: unknown domain"
    # Netlify
    "Not Found - Request ID"
    # Squarespace
    "No Site At This Address"
    # WP Engine
    "The site you were looking for couldn't be found"
    # ReadMe
    "project doesnt exist"
    # Cargo
    "If you're moving your domain away from Cargo"
    # Acquia
    "Web Site Not Found"
    # Kinsta
    "No Site For Domain"
    # Instapage
    "Looks Like You're Lost"
    # Leadpages
    "Your requested page is not available"
    # Desk.com (Salesforce)
    "Please check the URL and try again"
    # Apigee
    "No content returned from API"
    # Firebase
    "The specified Firebase project does not exist"
    # Digital Ocean Spaces
    "NoSuchBucket"
    # Agile CRM
    "Sorry, this page is no longer available"
    # Smart Jobboard
    "This job board website is either expired"
    # Feedpress
    "The feed has not been found"
    # LaunchRock
    "It looks like you may have taken a wrong turn somewhere"
    # Pingdom
    "This public report page has not been activated"
    # StatusPage.io
    "You are being redirected"
    # Canny
    "Company Not Found"
    # Tave
    "Tave Studio"
)

# Tool timeouts
TOOL_TIMEOUT=120
HTTPX_TIMEOUT=10
CURL_TIMEOUT=10

# =============================================================================
# MRK:01_LOG — COLOURS AND LOGGING | log,colours,logging | L102-128
# NAV-RULE: no-insert-before
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

_ts()  { date +'%Y%m%d_%H%M%S'; }
_now() { date +'%Y-%m-%d %H:%M:%S'; }

SESSION_TS="$(_ts)"

# Ensure directories are under the repo and owned by the invoking user where possible
mkdir -p "${EVIDENCE_BASE}/_dns" "${EVIDENCE_BASE}/_exports" working scripts
LOG_FILE="${EVIDENCE_BASE}/_dns/dns_recon_${SESSION_TS}.log"

# When run under sudo we want colored stderr output while still writing a plain log file
log()     { local m="[$(_now)] $1";            echo -e "${BLUE}${m}${NC}" >&2;        echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_ok()  { local m="[$(_now)] ✓ $1";          echo -e "${GREEN}${m}${NC}" >&2;       echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_warn(){ local m="[$(_now)] ⚠ $1";          echo -e "${YELLOW}${m}${NC}" >&2;      echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_err() { local m="[$(_now)] ✗ $1";          echo -e "${RED}${m}${NC}" >&2;         echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_info(){ local m="[$(_now)]   $1";          echo -e "${CYAN}${m}${NC}" >&2;        echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_find(){ local m="[$(_now)] ★ FINDING: $1"; echo -e "${BOLD}${RED}${m}${NC}" >&2;  echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }

# Ownership helper removed per operator preference; leave ownership as-is

# =============================================================================
# MRK:01_ARGS — ARGUMENT PARSING | args,argument,parsing | L129-148
# NAV-RULE: no-insert-before
# =============================================================================

AUTO_YES=0
DRY_RUN=0
SKIP_ACTIVE=0
APPEND_TARGETS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes)          AUTO_YES=1; shift ;;
        --dry-run)      DRY_RUN=1; shift ;;
        --skip-active)  SKIP_ACTIVE=1; shift ;;
        --append)       APPEND_TARGETS=1; shift ;;
        *) log_err "Unknown argument: $1"; exit 1 ;;
    esac
done

# =============================================================================
# MRK:01_SRCIP — SOURCE IP VERIFICATION | srcip,source,ip,verification,abort | L149-169
# NAV-RULE: no-insert-before
# =============================================================================

verify_source_ip() {
    [[ -z "${TESTER_IP:-}" ]] && { log_warn "TESTER_IP not set — skipping source IP verification"; return 0; }
    log "Verifying outbound source IP..."
    local actual_ip
    actual_ip=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || \
                dig +short myip.opendns.com @resolver1.opendns.com 2>/dev/null || \
                echo "unknown")
    if [[ "$actual_ip" == "$TESTER_IP" ]]; then
        log_ok "Source IP verified: ${actual_ip}"
    else
        log_err "SOURCE IP MISMATCH — actual: ${actual_ip} | expected: ${TESTER_IP}"
        log_err "Check VPN / interface. Aborting."
        exit 1
    fi
}

# =============================================================================
# MRK:01_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L170-202
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

scope_confirm() {
    [[ "$AUTO_YES" -eq 1 ]] && return 0
    local domain_count; domain_count=$(echo "$TARGET_DOMAINS" | wc -w | tr -d ' ')
    local ip_count;     ip_count=$(echo "$TARGET_IPS" | wc -w | tr -d ' ')
    echo ""
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  SCOPE CONFIRMATION — 01_dns_recon.sh${NC}"
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════════${NC}"
    printf "  %-22s %s\n" "Project:"        "$PROJECT_NAME"
    printf "  %-22s %s\n" "Domains:"        "${TARGET_DOMAINS:-[none]}"
    printf "  %-22s %s\n" "Seed IPs:"       "${TARGET_IPS:-[none]}"
    printf "  %-22s %s\n" "Domain count:"   "$domain_count"
    printf "  %-22s %s\n" "Seed IP count:"  "$ip_count"
    printf "  %-22s %s\n" "Tester IP:"      "${TESTER_IP:-[not verified]}"
    printf "  %-22s %s\n" "Shodan:"         "$([ -n "$SHODAN_API_KEY" ] && echo "enabled" || echo "no key")"
    printf "  %-22s %s\n" "Censys:"         "$([ -n "$CENSYS_API_ID" ] && echo "enabled" || echo "no key")"
    printf "  %-22s %s\n" "SecurityTrails:" "$([ -n "$SECURITYTRAILS_API_KEY" ] && echo "enabled" || echo "no key")"
    printf "  %-22s %s\n" "Active probes:"  "$([ "$SKIP_ACTIVE" -eq 1 ] && echo "SKIP (passive only)" || echo "enabled (AXFR, brute)")"
    printf "  %-22s %s\n" "Dry run:"        "$([ "$DRY_RUN" -eq 1 ] && echo "YES" || echo "no")"
    echo -e "${BOLD}${YELLOW}════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}Confirm authorisation is in place and scope is correct.${NC}"
    echo -n "  Type YES to continue: "
    read -r answer
    [[ "$answer" != "YES" ]] && { echo "Aborted."; exit 0; }
    echo ""
}

# =============================================================================
# MRK:01_SCOPE — THIRD-PARTY / PRIVATE IP BOUNDARY CHECKS + add_ip accumulator | scope,third,party,private,ip | L203-240
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

# Pure-bash CIDR containment check (no python3 dependency)
_ip_in_cidr() {
    local ip="$1" cidr="$2"
    local net="${cidr%/*}" prefix="${cidr#*/}"
    local a b c d
    IFS='.' read -r a b c d <<< "$ip";  local ip_int=$(( (a<<24)+(b<<16)+(c<<8)+d ))
    IFS='.' read -r a b c d <<< "$net"; local net_int=$(( (a<<24)+(b<<16)+(c<<8)+d ))
    local mask=$(( prefix > 0 ? (0xFFFFFFFF << (32-prefix)) & 0xFFFFFFFF : 0 ))
    [[ $(( ip_int & mask )) -eq $(( net_int & mask )) ]]
}

is_thirdparty() {
    local ip="$1"
    for cidr in "${THIRDPARTY_RANGES[@]}"; do
        _ip_in_cidr "$ip" "$cidr" && return 0
    done
    return 1
}

# Returns 0 (true) if IP is RFC1918 private, loopback, or link-local.
# PTE engagements target internet-facing infrastructure only — private IPs
# that slip in via split-horizon DNS or misconfigured records are not valid targets.
is_private_ip() {
    local ip="$1"
    [[ "$ip" =~ ^10\.                          ]] && return 0   # RFC1918 10/8
    [[ "$ip" =~ ^172\.(1[6-9]|2[0-9]|3[01])\. ]] && return 0   # RFC1918 172.16-31/12
    [[ "$ip" =~ ^192\.168\.                    ]] && return 0   # RFC1918 192.168/16
    [[ "$ip" =~ ^127\.                         ]] && return 0   # loopback
    [[ "$ip" =~ ^169\.254\.                    ]] && return 0   # link-local
    [[ "$ip" =~ ^0\.                           ]] && return 0   # this-network
    return 1
}

# =============================================================================
# MRK:01_TAKEOVER — SUBDOMAIN TAKEOVER DETECTION | takeover,subdomain,detection,curl,patterns | L241-262
# NAV-RULE: no-insert-before
# =============================================================================

check_takeover() {
    local subdomain="$1"
    local response
    response=$(curl -sk --max-time "$CURL_TIMEOUT" --connect-timeout 5 \
               "https://${subdomain}" 2>/dev/null || \
               curl -sk --max-time "$CURL_TIMEOUT" --connect-timeout 5 \
               "http://${subdomain}" 2>/dev/null || echo "")
    for pattern in "${TAKEOVER_PATTERNS[@]}"; do
        if echo "$response" | grep -qi "$pattern"; then
            log_find "SUBDOMAIN TAKEOVER CANDIDATE: ${subdomain} — '${pattern}'"
            echo "${subdomain}" >> "${EVIDENCE_BASE}/_dns/takeover_candidates_${SESSION_TS}.txt"
            return 0
        fi
    done
    return 1
}

# =============================================================================
# MRK:01_STATE — TARGET ACCUMULATORS | state,target,accumulators,discovered,ips | L263-288
# NAV-RULE: no-insert-before
# =============================================================================

declare -A DISCOVERED_IPS   # ip -> source
declare -A CONFIRMED_LIVE   # ip/host -> "confirmed"
declare -A CNAME_TARGETS    # subdomain -> cname
declare -A THIRDPARTY_IPS   # ip -> source

add_ip() {
    local ip="$1" source="$2"
    [[ "$ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] || return 0
    if [[ "${MODE:-pte}" == "pte" ]] && is_private_ip "$ip"; then
        log_warn "  Private IP skipped (not a valid PTE target): ${ip} [${source}]"
        return 0
    fi
    if is_thirdparty "$ip"; then
        THIRDPARTY_IPS["$ip"]="${source}"
        log_warn "  Third-party/CDN (flagged — verify RoE before scanning): ${ip} [${source}]"
    else
        DISCOVERED_IPS["$ip"]="${source}"
        log_info "  IP: ${ip} [${source}]"
    fi
}

# =============================================================================
# MRK:01_PASSIVE — PASSIVE RECON | passive,recon,crt,sh,subfinder | L289-419
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

recon_crt() {
    local domain="$1"
    log "crt.sh certificate transparency: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/crt_${domain}_${SESSION_TS}.txt"
    curl -s --max-time 30 "https://crt.sh/?q=%25.${domain}&output=json" 2>/dev/null | \
        python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    names=set()
    for e in data:
        for n in e.get('name_value','').split('\n'):
            n=n.strip().lstrip('*.')
            if n: names.add(n)
    print('\n'.join(sorted(names)))
except: pass
" 2>/dev/null | tee "$out"
    log_ok "crt.sh → ${out}"
}

recon_subfinder() {
    local domain="$1"
    command -v subfinder &>/dev/null || { log_warn "subfinder not found — skipping"; return; }
    log "subfinder: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/subfinder_${domain}_${SESSION_TS}.txt"
    timeout "$TOOL_TIMEOUT" subfinder -d "$domain" -silent -o "$out" 2>/dev/null || true
    log_ok "subfinder: $(wc -l < "$out" 2>/dev/null || echo 0) hits → ${out}"
    cat "$out" 2>/dev/null || true
}

recon_amass() {
    local domain="$1"
    command -v amass &>/dev/null || { log_warn "amass not found — skipping"; return; }
    log "amass (passive): ${domain}"
    local out="${EVIDENCE_BASE}/_dns/amass_${domain}_${SESSION_TS}.txt"
    timeout "$TOOL_TIMEOUT" amass enum -passive -d "$domain" -o "$out" 2>/dev/null || true
    log_ok "amass: $(wc -l < "$out" 2>/dev/null || echo 0) hits → ${out}"
    cat "$out" 2>/dev/null || true
}

recon_amass_brute() {
    local domain="$1"
    command -v amass &>/dev/null || { log_warn "amass not found — skipping brute"; return; }
    log "amass (brute): ${domain}"
    local out="${EVIDENCE_BASE}/_dns/amass_brute_${domain}_${SESSION_TS}.txt"
    timeout "$TOOL_TIMEOUT" amass enum -brute -d "$domain" -o "$out" 2>/dev/null || true
    log_ok "amass brute: $(wc -l < "$out" 2>/dev/null || echo 0) hits → ${out}"
    cat "$out" 2>/dev/null || true
}

recon_harvester() {
    local domain="$1"
    command -v theHarvester &>/dev/null || { log_warn "theHarvester not found — skipping"; return; }
    log "theHarvester: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/harvester_${domain}_${SESSION_TS}.txt"
    # Avoid "-b all" — many sources require API keys and produce timeout/auth errors in PTE.
    # These sources are reliable without keys. Add api-keyed sources if SHODAN/etc are configured.
    local harvester_sources="google,bing,baidu,crt,dnsdumpster,hackertarget,certspotter"
    timeout "$TOOL_TIMEOUT" theHarvester -d "$domain" -b "$harvester_sources" -f "$out" 2>/dev/null || true
    log_ok "theHarvester: $(wc -l < "$out" 2>/dev/null || echo 0) lines → ${out}"
    # Extract discovered hosts (best-effort)
    grep -Eo "[A-Za-z0-9_.-]+\.${domain}" "$out" 2>/dev/null | sed 's/^\.*//' | sort -u || true
}

recon_securitytrails() {
    local domain="$1"
    [[ -z "$SECURITYTRAILS_API_KEY" ]] && return
    log "SecurityTrails: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/securitytrails_${domain}_${SESSION_TS}.json"
    curl -s --max-time 30 \
        "https://api.securitytrails.com/v1/domain/${domain}/subdomains" \
        -H "APIKEY: ${SECURITYTRAILS_API_KEY}" | tee "$out" | \
    python3 -c "
import json,sys,os
domain=os.environ.get('DOMAIN','')
try:
    d=json.load(sys.stdin)
    for s in d.get('subdomains',[]):
        print(f'{s}.{domain}')
except: pass
" DOMAIN="$domain" 2>/dev/null || true
}

recon_censys() {
    local domain="$1"
    [[ -z "$CENSYS_API_ID" || -z "$CENSYS_API_SECRET" ]] && return
    log "Censys: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/censys_${domain}_${SESSION_TS}.json"
    curl -s --max-time 30 \
        "https://search.censys.io/api/v2/certificates/search" \
        -u "${CENSYS_API_ID}:${CENSYS_API_SECRET}" \
        -G --data-urlencode "q=parsed.names: ${domain}" \
        --data-urlencode "fields=parsed.names" | tee "$out" | \
    python3 -c "
import json,sys,os
domain=os.environ.get('DOMAIN','')
try:
    d=json.load(sys.stdin)
    names=set()
    for r in d.get('result',{}).get('hits',[]):
        for n in r.get('parsed.names',[]):
            if domain in n:
                names.add(n.lstrip('*.'))
    print('\n'.join(sorted(names)))
except: pass
" DOMAIN="$domain" 2>/dev/null || true
}

recon_shodan_domain() {
    local domain="$1"
    [[ -z "$SHODAN_API_KEY" ]] && return
    command -v shodan &>/dev/null || { log_warn "shodan CLI not found — skipping"; return; }
    log "Shodan domain: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/shodan_domain_${domain}_${SESSION_TS}.txt"
    shodan domain "$domain" 2>/dev/null | tee "$out" || true
}

recon_shodan_ip() {
    local ip="$1"
    [[ -z "$SHODAN_API_KEY" ]] && return
    command -v shodan &>/dev/null || return
    log "Shodan host: ${ip}"
    local out="${EVIDENCE_BASE}/_dns/shodan_host_${ip}_${SESSION_TS}.txt"
    shodan host "$ip" 2>/dev/null | tee "$out" || true
}

recon_dnsx() {
    local domain="$1"
    command -v dnsx &>/dev/null || { log_warn "dnsx not found — skipping fast resolution validation"; return; }
    log "dnsx fast resolution: ${domain}"
    local input="${EVIDENCE_BASE}/_dns/all_subdomains_${domain}_${SESSION_TS}.txt"
    [[ -f "$input" ]] || { log_warn "  dnsx: no subdomain list yet for ${domain}"; return; }
    local out="${EVIDENCE_BASE}/_dns/dnsx_${domain}_${SESSION_TS}.txt"
    # -a: resolve A records, -aaaa: AAAA, -cname: CNAME, -resp: show response
    timeout "$TOOL_TIMEOUT" dnsx \
        -l "$input" -silent -a -cname -resp \
        -o "$out" 2>/dev/null || true
    local cnt; cnt=$(wc -l < "$out" 2>/dev/null || echo 0)
    log_ok "dnsx: ${cnt} resolved → ${out}"
    # Feed any new IPs back into the accumulator
    while IFS= read -r line; do
        local ip_from_dnsx
        ip_from_dnsx=$(echo "$line" | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | head -1 || true)
        [[ -n "$ip_from_dnsx" ]] && add_ip "$ip_from_dnsx" "dnsx:${domain}"
    done < "$out" || true
}

recon_puredns() {
    local domain="$1"
    command -v puredns &>/dev/null || { log_warn "puredns not found — skipping bruteforce"; return; }
    [[ "$SKIP_ACTIVE" -eq 1 ]] && return
    local wordlist=""
    for wl in \
        "/usr/share/seclists/Discovery/DNS/subdomains-top1million-20000.txt" \
        "/usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt" \
        "/usr/share/wordlists/dnsmap.txt"; do
        [[ -f "$wl" ]] && { wordlist="$wl"; break; }
    done
    [[ -z "$wordlist" ]] && { log_warn "puredns: no wordlist found — skipping"; return; }
    log "puredns bruteforce: ${domain} (${wordlist})"
    local out="${EVIDENCE_BASE}/_dns/puredns_${domain}_${SESSION_TS}.txt"
    timeout "$TOOL_TIMEOUT" puredns bruteforce "$wordlist" "$domain" \
        --write "$out" 2>/dev/null || true
    local cnt; cnt=$(wc -l < "$out" 2>/dev/null || echo 0)
    log_ok "puredns: ${cnt} found → ${out}"
    cat "$out" 2>/dev/null || true
}

check_dnssec() {
    local domain="$1"
    log "DNSSEC check: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/dnssec_${domain}_${SESSION_TS}.txt"
    {
        echo "# DNSSEC Validation — ${domain} — $(_now)"
        echo "---"
        local ds_rec; ds_rec=$(dig ds "$domain" +short 2>/dev/null)
        local dnskey_rec; dnskey_rec=$(dig dnskey "$domain" +short 2>/dev/null)
        if [[ -n "$ds_rec" ]]; then
            echo "[DNSSEC] DS record found — DNSSEC likely enabled"
            echo "DS: ${ds_rec}"
            [[ -n "$dnskey_rec" ]] && echo "DNSKEY: ${dnskey_rec}"
            # Validate chain using +dnssec flag
            local ad_flag
            ad_flag=$(dig "$domain" A +dnssec +short 2>/dev/null | grep -c "AD" || echo 0)
            [[ "$ad_flag" -gt 0 ]] && echo "[DNSSEC] Authenticated Data (AD) bit set — validation successful" \
                                    || echo "[DNSSEC] AD bit NOT set — validation may have failed or not enforced"
        else
            echo "[DNSSEC] No DS record — DNSSEC NOT configured for ${domain}"
            log_warn "  DNSSEC not configured for ${domain} — DNS hijacking risk"
        fi
    } | tee "$out"
    log_ok "DNSSEC: ${out}"
}

check_doh() {
    local domain="$1"
    log "DNS-over-HTTPS probe: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/doh_${domain}_${SESSION_TS}.txt"
    {
        echo "# DNS-over-HTTPS probe — ${domain} — $(_now)"
        echo "---"
        # Probe Google DoH and Cloudflare DoH for the domain
        for doh_url in \
            "https://dns.google/resolve?name=${domain}&type=A" \
            "https://cloudflare-dns.com/dns-query?name=${domain}&type=A"; do
            local doh_resp
            doh_resp=$(curl -s --max-time 8 -H "Accept: application/dns-json" \
                           "$doh_url" 2>/dev/null || true)
            if [[ -n "$doh_resp" ]]; then
                local doh_status; doh_status=$(echo "$doh_resp" | python3 -c \
                    "import json,sys; d=json.load(sys.stdin); print(d.get('Status','?'))" 2>/dev/null || echo "?")
                echo "DoH [${doh_url%%?*}] Status=${doh_status}"
                echo "$doh_resp" | python3 -c \
                    "import json,sys; d=json.load(sys.stdin)
[print('  A: '+r.get('data','')) for r in d.get('Answer',[]) if r.get('type')==1]" 2>/dev/null || true
            fi
        done
    } | tee "$out"
    log_ok "DoH probe: ${out}"
}

# =============================================================================
# MRK:01_ACTIVE — ACTIVE DNS | active,dns,axfr,attempts,subdomain | L420-472
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

axfr_attempt() {
    local domain="$1"
    [[ "$SKIP_ACTIVE" -eq 1 ]] && return
    log "AXFR attempts: ${domain}"
    local out="${EVIDENCE_BASE}/_dns/axfr_${domain}_${SESSION_TS}.txt"
    {
        echo "# AXFR Attempts — ${domain} — $(_now)"
        echo "---"
        local ns_list
        ns_list=$(dig ns "$domain" +short 2>/dev/null | sed 's/\.$//')
        [[ -z "$ns_list" ]] && { echo "No NS records found"; return; }
        echo "Nameservers: $(echo "$ns_list" | tr '\n' ' ')"
        echo ""
        while IFS= read -r ns; do
            [[ -z "$ns" ]] && continue
            echo "--- AXFR @${ns} ---"
            local result
            result=$(timeout 15 dig axfr "$domain" "@${ns}" 2>/dev/null || echo "FAILED/REFUSED")
            echo "$result"
            if echo "$result" | grep -q "XFR size"; then
                log_find "ZONE TRANSFER SUCCESS: ${domain} @${ns}"
            fi
        done <<< "$ns_list"
    } | tee "$out"
    log_ok "AXFR: ${out}"
}

brute_subdomains() {
    local domain="$1"
    [[ "$SKIP_ACTIVE" -eq 1 ]] && return
    command -v gobuster &>/dev/null || { log_warn "gobuster not found — skipping DNS brute"; return; }
    local wordlist=""
    for wl in \
        "/usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt" \
        "/usr/share/seclists/Discovery/DNS/bitquark-subdomains-top100000.txt" \
        "/usr/share/wordlists/dnsmap.txt"; do
        [[ -f "$wl" ]] && { wordlist="$wl"; break; }
    done
    [[ -z "$wordlist" ]] && { log_warn "No DNS wordlist found — skipping brute"; return; }
    log "DNS brute: ${domain} (${wordlist})"
    local out="${EVIDENCE_BASE}/_dns/brute_${domain}_${SESSION_TS}.txt"
    timeout "$TOOL_TIMEOUT" gobuster dns \
        --domain "$domain" -w "$wordlist" -q --timeout 3s \
        2>/dev/null | tee "$out" || true
    log_ok "DNS brute: $(wc -l < "$out" 2>/dev/null || echo 0) hits → ${out}"
    grep "Found:" "$out" 2>/dev/null | awk '{print $2}' || true
}

# =============================================================================
# MRK:01_RESOLVE — RESOLUTION AND LIVE CHECK | resolve,resolution,live,check,cname | L473-536
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

resolve_subdomain() {
    local subdomain="$1"
    # CNAME check first
    local cname
    cname=$(dig cname "$subdomain" +short 2>/dev/null | head -1 | sed 's/\.$//')
    if [[ -n "$cname" ]]; then
        CNAME_TARGETS["$subdomain"]="$cname"
        log_info "  CNAME: ${subdomain} → ${cname}"
        local ip
        ip=$(dig a "$subdomain" +short 2>/dev/null | grep -E '^[0-9]' | head -1)
        [[ -n "$ip" ]] && add_ip "$ip" "cname:${subdomain}"
        return
    fi
    # A record
    local ip
    ip=$(dig a "$subdomain" +short 2>/dev/null | grep -E '^[0-9]' | head -1)
    [[ -n "$ip" ]] && add_ip "$ip" "a:${subdomain}"
}

httpx_verify() {
    log "Live HTTP/S verification..."
    local input_file="${EVIDENCE_BASE}/_dns/all_targets_${SESSION_TS}.txt"
    local out="${EVIDENCE_BASE}/_dns/httpx_${SESSION_TS}.txt"
    {
        set +u
        for ip in "${!DISCOVERED_IPS[@]}"; do echo "$ip"; done
        for sub in "${!CNAME_TARGETS[@]}"; do echo "$sub"; done
        set -u
    } | sort -u > "$input_file"

    > "$out"  # ensure file exists even if tool produces no output
    if command -v httpx &>/dev/null; then
        timeout "$TOOL_TIMEOUT" httpx \
            -l "$input_file" -silent -status-code -title -tech-detect \
            -timeout "$HTTPX_TIMEOUT" -o "$out" 2>/dev/null || true
        log_ok "httpx: $(wc -l < "$out") live → ${out}"
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local host
            host=$(echo "$line" | grep -oE 'https?://[^/ ]+' | sed 's|https\?://||' | head -1)
            [[ -n "$host" ]] && CONFIRMED_LIVE["$host"]="confirmed"
        done < "$out"
    else
        log_warn "httpx not found — curl fallback"
        while IFS= read -r target; do
            [[ -z "$target" ]] && continue
            local code
            code=$(curl -sk --max-time "$HTTPX_TIMEOUT" --connect-timeout 3 \
                       -o /dev/null -w "%{http_code}" "https://${target}" 2>/dev/null || echo "000")
            if [[ "$code" != "000" && "$code" != "400" ]]; then
                echo "${target} [HTTPS ${code}]" >> "$out"
                CONFIRMED_LIVE["$target"]="confirmed"
                log_info "  Live: ${target} [${code}]"
            fi
        done < "$input_file"
        log_ok "curl verify: $(wc -l < "$out") live → ${out}"
    fi
}

# =============================================================================
# MRK:01_OUTPUT — TARGET LIST + SUMMARY | output,target,list,summary,write | L537-653
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

write_targets() {
    # Use SCRIPT_DIR-anchored path so the file lands alongside the scripts
    # regardless of which directory the caller cd'd into.
    local targets_file="${SCRIPT_DIR}/targets.txt"
    [[ "$APPEND_TARGETS" -eq 0 ]] && > "$targets_file"
    {
        echo "# targets.txt — 01_dns_recon.sh | ${PROJECT_NAME} | $(_now)"
        echo "# ─────────────────────────────────────────────"
        echo "# Seed IPs (explicitly provided in scope — written unconditionally)"
        for ip in $TARGET_IPS; do echo "$ip"; done
        echo ""
        echo "# Discovered IPs (DNS resolution + OSINT — private IPs filtered in pte mode)"
        for ip in "${!DISCOVERED_IPS[@]}"; do echo "$ip"; done
    } | grep -v "^#" | grep -E '^[0-9]' \
      | sort -u -t. -k1,1n -k2,2n -k3,3n -k4,4n \
      >> "$targets_file"

    # Re-add headers cleanly
    local tmp
    tmp=$(grep -v "^#" "$targets_file" | grep -E '^[0-9]' | sort -u -t. -k1,1n -k2,2n -k3,3n -k4,4n)
    {
        echo "# targets.txt — 01_dns_recon.sh | ${PROJECT_NAME} | $(_now)"
        echo "$tmp"
    } > "$targets_file"

    local total; total=$(grep -cE '^[0-9]' "$targets_file" 2>/dev/null || echo 0)
    log_ok "targets.txt: ${total} IPs → ${targets_file}"
}

write_summary() {
    local summary="working/dns_summary_${SESSION_TS}.md"
    local takeover_file="${EVIDENCE_BASE}/_dns/takeover_candidates_${SESSION_TS}.txt"
    local takeover_count=0
    [[ -f "$takeover_file" ]] && takeover_count=$(wc -l < "$takeover_file")
    local targets_count; targets_count=$(grep -cE '^[0-9]' "${SCRIPT_DIR}/targets.txt" 2>/dev/null || echo 0)

    set +u
    local cnt_discovered="${#DISCOVERED_IPS[@]}"
    local cnt_live="${#CONFIRMED_LIVE[@]}"
    local cnt_thirdparty="${#THIRDPARTY_IPS[@]}"
    set -u

    {
    cat << EOF
# DNS Recon Summary — ${PROJECT_NAME}
*Generated: $(_now) | Session: ${SESSION_TS}*

## Scope
- **Domains:** ${TARGET_DOMAINS:-[none]}
- **Seed IPs:** ${TARGET_IPS:-[none]}
- **Tester IP:** ${TESTER_IP:-[not verified]}

## Results
| Metric | Count |
|--------|-------|
| Unique in-scope IPs | ${cnt_discovered} |
| Live HTTP/S hosts | ${cnt_live} |
| Third-party/CDN IPs (flagged) | ${cnt_thirdparty} |
| Takeover candidates | ${takeover_count} |
| Total targets.txt | ${targets_count} |

## In-Scope IPs Discovered
| IP | Source |
|----|--------|
EOF
    set +u
    for ip in "${!DISCOVERED_IPS[@]}"; do
        echo "| ${ip} | ${DISCOVERED_IPS[$ip]} |"
    done | sort

    echo ""
    echo "## Third-Party / CDN IPs (flagged — verify RoE before scanning)"
    echo "| IP | Source |"
    echo "|----|--------|"
    for ip in "${!THIRDPARTY_IPS[@]}"; do
        echo "| ${ip} | ${THIRDPARTY_IPS[$ip]} |"
    done | sort

    echo ""
    echo "## CNAME Records"
    echo "| Subdomain | CNAME |"
    echo "|-----------|-------|"
    for sub in "${!CNAME_TARGETS[@]}"; do
        echo "| ${sub} | ${CNAME_TARGETS[$sub]} |"
    done | sort
    set -u

    if [[ "$takeover_count" -gt 0 ]]; then
        echo ""
        echo "## ★ SUBDOMAIN TAKEOVER CANDIDATES"
        echo '```'
        cat "$takeover_file"
        echo '```'
    fi

    cat << EOF

## Evidence Files
$(ls -1 "${EVIDENCE_BASE}/_dns/" 2>/dev/null | sed 's/^/- evidence\/_dns\//')

## Next Steps
1. Review takeover candidates manually (if any)
2. Review third-party IPs — confirm any in scope and add manually to \`scripts/targets.txt\`
3. Validate \`scripts/targets.txt\` — confirm all IPs are client-owned
4. Run: \`sudo ./03_comp_scan.sh --mode pte\`

---
*01_dns_recon.sh | TechGuard.*
EOF
    } > "$summary"
    log_ok "DNS summary: ${summary}"
}

# =============================================================================
# MRK:01_MAIN — MAIN entry point | main,entry,point | L654-811
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    echo -e "${GREEN}"
    echo "════════════════════════════════════════════════"
    echo "  01_dns_recon.sh"
    echo "  TechGuard."
    echo "  Project: ${PROJECT_NAME}"
    echo "  Domains: ${TARGET_DOMAINS:-[none]}"
    echo "  Seed IPs: ${TARGET_IPS:-[none]}"
    echo "════════════════════════════════════════════════"
    echo -e "${NC}"

    verify_source_ip
    scope_confirm

    {
        echo "# Session Start — 01_dns_recon.sh"
        echo "# Time:      $(_now)"
        echo "# Project:   ${PROJECT_NAME}"
        echo "# Domains:   ${TARGET_DOMAINS:-[none]}"
        echo "# Seed IPs:  ${TARGET_IPS:-[none]}"
        echo "# Tester IP: ${TESTER_IP:-unverified}"
        echo "# Dry run:   ${DRY_RUN}"
    } >> "$LOG_FILE"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo -e "${CYAN}[DRY-RUN] Would enumerate domains: ${TARGET_DOMAINS:-[none]}${NC}"
        echo -e "${CYAN}[DRY-RUN] Would add seed IPs: ${TARGET_IPS:-[none]}${NC}"
        exit 0
    fi

    # Validate that there is something to enumerate.
    # PTI note: in internal engagements, targets come from TARGET_SUBNETS (consumed
    # by 03), not from DNS. Empty domains + empty IPs is legitimate in PTI  the
    # script has nothing to do and exits 0 (not 1) so the orchestrator moves on.
    if [[ -z "${TARGET_DOMAINS:-}" && -z "${TARGET_IPS:-}" ]]; then
        if [[ "${MODE:-}" == "pti" ]]; then
            log_ok "PTI mode + no TARGET_DOMAINS/TARGET_IPS  nothing to enumerate, skipping DNS recon"
            exit 0
        fi
        log_err "Nothing to enumerate — set TARGET_DOMAINS and/or TARGET_IPS in the config block."
        exit 1
    fi

    # Add seed IPs immediately — always in scope
    for ip in $TARGET_IPS; do
        add_ip "$ip" "scope-provided"
    done

    # Per-domain enumeration
    for domain in $TARGET_DOMAINS; do
        log "════ Domain: ${domain} ════"
        local all_subdomains=()

        # Always resolve the root domain itself first — passive recon only discovers
        # subdomains, so a leaf domain like testphp.vulnweb.com would never get its
        # own A record added without this step.
        local root_ip
        root_ip=$(dig a "$domain" +short 2>/dev/null | grep -E '^[0-9]' | head -1 || true)
        [[ -n "$root_ip" ]] && add_ip "$root_ip" "root-domain:${domain}"
        # Also seed the domain itself into the subdomain list so resolve_subdomain
        # captures its CNAME chain if one exists.
        all_subdomains+=("$domain")

        # Passive sources — collect all subdomains
        while IFS= read -r sub; do [[ -n "$sub" ]] && all_subdomains+=("$sub"); done < <(recon_crt "$domain")
        while IFS= read -r sub; do [[ -n "$sub" ]] && all_subdomains+=("$sub"); done < <(recon_subfinder "$domain")
        while IFS= read -r sub; do [[ -n "$sub" ]] && all_subdomains+=("$sub"); done < <(recon_amass "$domain")
        while IFS= read -r sub; do [[ -n "$sub" ]] && all_subdomains+=("$sub"); done < <(recon_securitytrails "$domain")
        while IFS= read -r sub; do [[ -n "$sub" ]] && all_subdomains+=("$sub"); done < <(recon_censys "$domain")
        recon_shodan_domain "$domain"

        # Active DNS
        axfr_attempt "$domain"
        check_dnssec "$domain"
        check_doh "$domain"
        while IFS= read -r sub; do [[ -n "$sub" ]] && all_subdomains+=("$sub"); done < <(brute_subdomains "$domain")
        while IFS= read -r sub; do [[ -n "$sub" ]] && all_subdomains+=("$sub"); done < <(recon_puredns "$domain")
        [[ "${AMASS_BRUTE:-0}" -eq 1 ]] && \
            while IFS= read -r sub; do [[ -n "$sub" ]] && all_subdomains+=("$sub"); done < <(recon_amass_brute "$domain")

        # Deduplicate
        local unique_subs=""
        set +u
        [[ "${#all_subdomains[@]}" -gt 0 ]] && \
            unique_subs=$(printf '%s\n' "${all_subdomains[@]}" | sort -u | grep -v '^$' || true)
        set -u
        local sub_count; sub_count=$(echo "$unique_subs" | grep -c '.' 2>/dev/null || echo 0)
        log_ok "Domain ${domain}: ${sub_count} unique subdomains"
        echo "$unique_subs" > "${EVIDENCE_BASE}/_dns/all_subdomains_${domain}_${SESSION_TS}.txt"

        # Resolve subdomains sequentially; run takeover checks in background with
        # a concurrency cap (MAX_TAKEOVER_JOBS) to avoid spawning thousands of
        # curl processes simultaneously on large subdomain sets.
        local MAX_TAKEOVER_JOBS=20
        local takeover_running=0
        local -a takeover_pids=()

        while IFS= read -r sub; do
            [[ -z "$sub" ]] && continue
            resolve_subdomain "$sub"

            # Throttle: reap finished jobs before spawning a new one
            while [[ "$takeover_running" -ge "$MAX_TAKEOVER_JOBS" ]]; do
                wait -n 2>/dev/null || true
                (( takeover_running-- )) || true
            done

            check_takeover "$sub" &
            takeover_pids+=($!)
            (( takeover_running++ )) || true
        done <<< "$unique_subs"

        # Wait for all remaining takeover jobs
        if [[ ${#takeover_pids[@]} -gt 0 ]]; then
            wait "${takeover_pids[@]}" 2>/dev/null || true
        fi

        # Fast resolution validation with dnsx (run after subdomain list is written)
        recon_dnsx "$domain"

        log_ok "Resolution complete: ${domain}"
    done

    # Live verification
    httpx_verify

    # Shodan enrichment per IP
    if [[ -n "$SHODAN_API_KEY" ]]; then
        log "Shodan enrichment..."
        set +u
        for ip in "${!DISCOVERED_IPS[@]}"; do
            recon_shodan_ip "$ip"
        done
        set -u
    fi

    # Outputs
    write_targets
    write_summary

    set +u
    local final_discovered="${#DISCOVERED_IPS[@]}"
    local final_thirdparty="${#THIRDPARTY_IPS[@]}"
    local final_live="${#CONFIRMED_LIVE[@]}"
    set -u

    {
        echo "# Session End — 01_dns_recon.sh"
        echo "# Time:            $(_now)"
        echo "# IPs discovered:  ${final_discovered}"
        echo "# Third-party:     ${final_thirdparty}"
        echo "# Live hosts:      ${final_live}"
    } >> "$LOG_FILE"

    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  DNS Recon Complete — ${PROJECT_NAME}${NC}"
    echo -e "${GREEN}  IPs in scope:    ${final_discovered}${NC}"
    echo -e "${GREEN}  Third-party:     ${final_thirdparty} (flagged — verify RoE)${NC}"
    echo -e "${GREEN}  Live HTTP/S:     ${final_live}${NC}"
    echo -e "${GREEN}  Targets file:    scripts/targets.txt${NC}"
    echo -e "${GREEN}  Summary:         working/dns_summary_${SESSION_TS}.md${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════${NC}"
    echo ""
}

main

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
