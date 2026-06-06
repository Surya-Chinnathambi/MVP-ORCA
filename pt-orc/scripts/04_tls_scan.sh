#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:04_NAV_TOC — Section index | nav,toc,index | L5-45
# - MRK:04_ROOT — ROOT CHECK | root,check,db,nmap,requires | L46-55 | ⚠ no-insert-before
# - MRK:04_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L56-83 | ⚠ no-insert-before; propose-before-edit
# - MRK:04_LOG — COLOURS AND LOGGING | log,colours,logging | L84-109 | ⚠ no-insert-before
# - MRK:04_DB — MSF DB CREDENTIALS | db,msf,credentials,tcp,peer | L110-131 | ⚠ no-insert-before; propose-before-edit
# - MRK:04_ARGS — ARGUMENT PARSING | args,argument,parsing | L132-150 | ⚠ no-insert-before
# - MRK:04_SCAN — SCAN EXECUTION MODEL | scan,execution,model,rc,spool | L151-219 | ⚠ no-insert-before; read-toc-first
# - MRK:04_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L220-245 | ⚠ no-insert-before; propose-before-edit
# - MRK:04_TARGETS — TARGET LIST ASSEMBLY | targets,target,list,assembly,host | L246-278 | ⚠ no-insert-before; read-toc-first
# - MRK:04_ASSESS — PER-HOST TLS ASSESSMENT | assess,host,tls,assessment,cert | L279-479 | ⚠ no-insert-before; read-toc-first
# - MRK:04_SCREENS — SCREENSHOT CAPTURE | screens,screenshot,capture,external,grabscores | L480-499 | ⚠ no-insert-before
# - MRK:04_MAIN — MAIN entry point | main,entry,point | L500-568 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 11 entries | Integrity-hash: 63cb04ee9b3ec4b7 | Last-indexed: 2026-04-24T20:37:14Z

# =============================================================================
# 04_tls_scan.sh — TechGuard. [VAPT-enhanced]
# TLS/Certificate assessment — separate from main scan
# VAPT additions: CT log lookup (crt.sh), certificate key size & SAN check,
#   ALPACA attack hint, ROBOT attack check (RSA key exchange), HSTS preload
#   validation, expanded security header list, Lucky13/BEAST/POODLE explicit
#   identification, post-quantum TLS awareness note.
# Consumes: working/tls_targets.txt (produced by 03_comp_scan.sh)
# Or:       --targets <file>  or  --host <IP:PORT>
# =============================================================================
# USAGE:
#   ./04_tls_scan.sh [OPTIONS]
#
# OPTIONS:
#   --targets <file>    File with host:port entries (default: working/tls_targets.txt)
#   --host <IP:PORT>    Single target (can repeat)
#   --fast              Skip testssl; openssl + nmap ssl-enum-ciphers only
#   --output-dir <dir>  Screenshots output dir (default: screens/)
#   --grab-screens      Run GrabScores-v2.5.py after testssl (external helper; requires Playwright)
#   --dry-run           Print what would run without executing db_nmap
#
# ENVIRONMENT VARS:
#   PROJECT_NAME        MSF workspace name
#   EVIDENCE_BASE       Base evidence directory (default: evidence)
#   TESTSSL_TIMEOUT     Seconds per host for testssl (default: 300)
set -uo pipefail

# Location of this script — keep evidence inside this PT-Orc directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:04_ROOT — ROOT CHECK | root,check,db,nmap,requires | L46-55
# NAV-RULE: no-insert-before
# =============================================================================
if [[ "$EUID" -ne 0 ]] && [[ "${PTORC_ALLOW_NON_ROOT:-0}" != "1" ]]; then
    echo "[ERROR] This script must be run as root (required for db_nmap)."
    echo "        Run: sudo $0 $*"
    exit 1
fi

# =============================================================================
# MRK:04_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L56-83
# NAV-RULE: no-insert-before; propose-before-edit
# =============================================================================

# Load shared engagement config (PROJECT_NAME, MODE, …)
# shellcheck source=pt-orc.conf
[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found in ${SCRIPT_DIR} — set variables in pt-orc.conf"

# Shared helpers (logging, DB access, trail/notes writer). Source AFTER pt-orc.conf
# so PROJECT_NAME / MSF_DB_* are already in env when parse_db_conf runs.
# shellcheck source=orc-common-lib.sh
[[ -f "${SCRIPT_DIR}/orc-common-lib.sh" ]] && source "${SCRIPT_DIR}/orc-common-lib.sh" \
    || echo "[WARN] orc-common-lib.sh not found — trail/notes writes will be disabled"

# Keep evidence inside the PT-Orc directory
EVIDENCE_BASE="${SCRIPT_DIR}/evidence"
TESTSSL_TIMEOUT="${TESTSSL_TIMEOUT:-300}"
SCREENS_DIR="${SCREENS_DIR:-screens}"
FAST_MODE=0
GRAB_SCREENS=0
DRY_RUN=0

TARGETS_FILE="working/tls_targets.txt"
EXTRA_HOSTS=()
AUTO_YES=0

# =============================================================================
# MRK:04_LOG — COLOURS AND LOGGING | log,colours,logging | L84-109
# NAV-RULE: no-insert-before
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

_ts()  { date +'%Y%m%d_%H%M%S'; }
_now() { date +'%Y-%m-%d %H:%M:%S'; }

SESSION_TS="$(_ts)"
[[ "$EVIDENCE_BASE" != /* ]] && EVIDENCE_BASE="$(pwd)/${EVIDENCE_BASE}"
# Ensure evidence dirs exist under repo
mkdir -p "${EVIDENCE_BASE}/_sweep" working
LOG_FILE="${EVIDENCE_BASE}/_sweep/tls_scan_${SESSION_TS}.log"

# Colored output to stderr, plain log to file
log()     { local m="[$(_now)] $1"; echo -e "${BLUE}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_ok()  { local m="[$(_now)] ✓ $1"; echo -e "${GREEN}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_warn(){ local m="[$(_now)] ⚠ $1"; echo -e "${YELLOW}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_err() { local m="[$(_now)] ✗ $1"; echo -e "${RED}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_info(){ local m="[$(_now)]   $1"; echo -e "${CYAN}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }

# Ownership helper removed per operator preference; leave ownership as-is

# =============================================================================
# MRK:04_DB — MSF DB CREDENTIALS | db,msf,credentials,tcp,peer | L110-131
# NAV-RULE: no-insert-before; propose-before-edit
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

# =============================================================================
# MRK:04_ARGS — ARGUMENT PARSING | args,argument,parsing | L132-150
# NAV-RULE: no-insert-before
# =============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --targets)      TARGETS_FILE="$2"; shift 2 ;;
        --host)         EXTRA_HOSTS+=("$2"); shift 2 ;;
        --fast)         FAST_MODE=1; shift ;;
        --output-dir)   SCREENS_DIR="$2"; shift 2 ;;
        --grab-screens) GRAB_SCREENS=1; shift ;;
        --yes)          AUTO_YES=1; shift ;;
        --dry-run)      DRY_RUN=1; shift ;;
        *) log_err "Unknown argument: $1"; exit 1 ;;
    esac
done


# =============================================================================
# MRK:04_SCAN — SCAN EXECUTION MODEL | scan,execution,model,rc,spool | L151-219
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
        printf 'workspace -a %s\n'    "$PROJECT_NAME"
        printf 'db_nmap %s\n'      "$*"
        printf 'spool off\n'
        printf 'exit\n'
    } > "$rc_file"

    log "  rc_scan [${label}] → ${rc_file}"
    log "  spool  [${label}] → ${spool_file}  (tail -f to follow)"

    # </dev/null: prevents msfconsole from reading stdout as commands if rc file is missing
    PGPASSWORD="${MSF_DB_PASS:-}" msfconsole -q -r "$rc_file" </dev/null
    local rc=$?
    [[ $rc -ne 0 ]] \
        && log_warn "  msfconsole rc=${rc} [${label}] — check: ${spool_file}" \
        || log_ok   "  rc_scan done [${label}]"
    return $rc
}

# Export MSF DB via rc file.
# Usage: export_db <phase_label>
export_db() {
    local phase="${1:-tls}"
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
# MRK:04_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L220-245
# NAV-RULE: no-insert-before; propose-before-edit
# =============================================================================

scope_confirm() {
    local target_count="${1:-0}"
    [[ "${AUTO_YES:-0}" -eq 1 ]] && return 0
    echo ""
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    echo -e "\033[1m  SCOPE CONFIRMATION — 04_tls_scan.sh\033[0m"
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    printf "  %-22s %s\n" "Project:"    "${PROJECT_NAME}"
    printf "  %-22s %s\n" "Targets:"    "${target_count}"
    printf "  %-22s %s\n" "Mode:"       "$([ "$FAST_MODE" -eq 1 ] && echo "fast (nmap ssl-ciphers)" || echo "full (testssl)")"
    printf "  %-22s %s\n" "Targets file:" "${TARGETS_FILE}"
    printf "  %-22s %s\n" "Dry run:"    "$([ "${DRY_RUN:-0}" -eq 1 ] && echo "YES" || echo "no")"
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    echo ""
    echo -e "\033[1mConfirm authorisation is in place and scope is correct.\033[0m"
    echo -n "  Type YES to continue: "
    read -r answer
    [[ "$answer" != "YES" ]] && { echo "Aborted."; exit 0; }
    echo ""
}

# =============================================================================
# MRK:04_TARGETS — TARGET LIST ASSEMBLY | targets,target,list,assembly,host | L246-278
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

assemble_targets() {
    local targets=()

    # From file
    if [[ -f "$TARGETS_FILE" ]]; then
        while IFS= read -r line; do
            [[ -z "$line" || "$line" == \#* ]] && continue
            targets+=("$line")
        done < "$TARGETS_FILE"
    else
        log_warn "Targets file not found: ${TARGETS_FILE}"
    fi

    # From --host args
    set +u
    for h in "${EXTRA_HOSTS[@]}"; do
        targets+=("$h")
    done
    set -u

    # Deduplicate
    set +u
    if [[ ${#targets[@]} -gt 0 ]]; then
        printf '%s\n' "${targets[@]}" | sort -u
    fi
    set -u
}

# =============================================================================
# MRK:04_ASSESS — PER-HOST TLS ASSESSMENT | assess,host,tls,assessment,cert | L279-479
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

assess_host() {
    local target="$1"   # IP:PORT
    local ip="${target%%:*}"
    ip="${ip%%/*}"      # strip CIDR suffix if present (e.g. 10.0.0.1/32 → 10.0.0.1)
    local port="${target##*:}"
    local dir="${EVIDENCE_BASE}/${ip}"
    local ts; ts="$(_ts)"

    mkdir -p "$dir"
    log "Assessing TLS: ${target}"

    # ── 1. Certificate info (openssl) ──────────────────────────────────────
    local cert_out="${dir}/cert_${port}_${ts}.txt"
    {
        echo "# TLS Certificate — ${target}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        timeout 15 bash -c \
            "echo | openssl s_client -connect '${ip}:${port}' \
             -servername '${ip}' -showcerts 2>/dev/null \
             | openssl x509 -noout -text 2>/dev/null" || \
            echo "[WARN] openssl handshake failed or timed out"
    } | tee "$cert_out"
    log_ok "  Certificate: ${cert_out}"

    # Quick cert facts for follow-up
    local expiry; expiry=$(grep -m1 "Not After" "$cert_out" 2>/dev/null || echo "unknown")
    local subject; subject=$(grep -m1 "Subject:" "$cert_out" 2>/dev/null || echo "unknown")
    log_info "  Subject: ${subject}"
    log_info "  Expiry:  ${expiry}"

    # ── 2. Legacy protocol checks (openssl) ────────────────────────────────
    # OpenSSL 3.x dropped SSLv2/SSLv3 entirely — test only what the local binary
    # supports. TLS 1.0/1.1 "unexpected eof" means the server refused that version,
    # which is the expected (correct) result for a hardened server.
    local legacy_out="${dir}/tls_legacy_${port}_${ts}.txt"
    {
        echo "# Legacy Protocol Check — ${target}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local openssl_help; openssl_help=$(openssl s_client -help 2>&1 || true)
        for proto in ssl2 ssl3 tls1 tls1_1; do
            if ! echo "$openssl_help" | grep -q -- "-${proto}"; then
                echo "[${proto}] NOT TESTED — local OpenSSL does not support -${proto} (removed in OpenSSL 3.x)"
                continue
            fi
            local result
            result=$(timeout 8 bash -c \
                "echo | openssl s_client -connect '${ip}:${port}' \
                 -${proto} 2>&1 | grep -E 'CONNECTED|Protocol|refused|eof|alert|handshake|error' | head -3" \
                2>/dev/null || echo "timeout/connection error")
            # "unexpected eof" = server actively rejected the protocol (good)
            if echo "$result" | grep -q "unexpected eof\|alert\|refused"; then
                echo "[${proto}] REJECTED by server (expected for hardened config)"
            elif echo "$result" | grep -q "CONNECTED"; then
                echo "[${proto}] ACCEPTED — server supports this legacy protocol (FINDING)"
            else
                echo "[${proto}] ${result:-no response}"
            fi
        done
    } | tee "$legacy_out"
    log_ok "  Legacy check: ${legacy_out}"

    if [[ "$FAST_MODE" -eq 1 ]]; then
        # ── FAST: nmap ssl-enum-ciphers only ───────────────────────────────
        local cipher_out="${dir}/nmap_tls_${port}_${ts}"
        run_rc_scan "ssl-ciphers_${ip}_${port}" \
             -Pn -p "$port" \
             --script "ssl-enum-ciphers,ssl-cert" \
             --script-timeout 2m \
             -T3 \
             "$ip" \
             -oA "$cipher_out"
        log_ok "  Cipher enum: ${cipher_out}.nmap"
    else
        # ── FULL: testssl (non-interactive, batch mode) ─────────────────────
        if command -v testssl &>/dev/null; then
            local testssl_base="${dir}/testssl_${port}_${ts}"
            log "  Running testssl on ${target} (timeout: ${TESTSSL_TIMEOUT}s)..."
            timeout "$TESTSSL_TIMEOUT" testssl \
                --htmlfile "${testssl_base}.html" \
                --jsonfile  "${testssl_base}.json" \
                --logfile   "${testssl_base}.log" \
                --severity  LOW \
                --color 0 \
                --warnings  batch \
                "${ip}:${port}" 2>&1 | tee "${testssl_base}.console.txt"
            local _tssl_rc=${PIPESTATUS[0]}
            if [[ $_tssl_rc -eq 124 ]]; then
                log_warn "  testssl timed out on ${target} (>${TESTSSL_TIMEOUT}s)"
            elif [[ $_tssl_rc -ne 0 ]] && [[ ! -s "${testssl_base}.json" ]]; then
                log_warn "  testssl failed on ${target} (rc=${_tssl_rc}) — no output produced"
            else
                log_ok "  testssl: ${testssl_base}.{html,json,log}"
            fi

            # Parse quick severity summary from JSON
            if [[ -f "${testssl_base}.json" ]] && command -v jq &>/dev/null; then
                log_info "  Severity summary:"
                jq -r '.[] | select(.severity != null) | "\(.severity): \(.id) — \(.finding)"' \
                    "${testssl_base}.json" 2>/dev/null | \
                    grep -E "CRITICAL|HIGH|MEDIUM" | head -15 | \
                    while IFS= read -r line; do log_info "    ${line}"; done
            fi
        else
            log_warn "  testssl not found — falling back to nmap ssl-enum-ciphers"
            local cipher_out="${dir}/nmap_tls_${port}_${ts}"
            run_rc_scan "ssl-ciphers_${ip}_${port}" \
                 -Pn -p "$port" \
                 --script "ssl-enum-ciphers,ssl-cert" \
                 --script-timeout 2m \
                 -T3 \
                 "$ip" \
                 -oA "$cipher_out"
            log_ok "  Cipher enum: ${cipher_out}.nmap"
        fi
    fi

    # ── 2b. VAPT: Extended certificate analysis ────────────────────────────
    if [[ "$DRY_RUN" -eq 0 ]]; then
        local cert_ext_out="${dir}/cert_ext_${port}_${ts}.txt"
        {
            echo "# Extended Certificate Analysis — ${target}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "---"

            # Key size and algorithm
            local key_info
            key_info=$(timeout 15 bash -c \
                "echo | openssl s_client -connect '${ip}:${port}' -servername '${ip}' 2>/dev/null \
                 | openssl x509 -noout -text 2>/dev/null \
                 | grep -E 'Public Key Algorithm|RSA Public-Key|Public-Key|Signature Algorithm'" 2>/dev/null || true)
            echo "=== Key / Algorithm ==="
            echo "${key_info:-[could not parse]}"
            # Flag weak key sizes
            if echo "$key_info" | grep -qiE "RSA Public-Key: \(102[0-4]|512|768\) bit|Public-Key: \(102[0-4]|512|768\)"; then
                echo "[FINDING] Weak RSA key size detected — below 2048 bits"
            fi

            # Subject Alternative Names
            echo ""
            echo "=== Subject Alternative Names ==="
            local sans
            sans=$(timeout 15 bash -c \
                "echo | openssl s_client -connect '${ip}:${port}' -servername '${ip}' 2>/dev/null \
                 | openssl x509 -noout -text 2>/dev/null \
                 | grep -A1 'Subject Alternative Name'" 2>/dev/null || true)
            echo "${sans:-[none found]}"

            # CT SCT presence (Certificate Transparency)
            echo ""
            echo "=== Certificate Transparency (SCT) ==="
            local sct_info
            sct_info=$(timeout 15 bash -c \
                "echo | openssl s_client -connect '${ip}:${port}' -servername '${ip}' 2>/dev/null \
                 | openssl x509 -noout -text 2>/dev/null \
                 | grep -A5 'CT Precertificate SCTs\|Signed Certificate Timestamp'" 2>/dev/null || true)
            if [[ -n "$sct_info" ]]; then
                echo "[CT] SCTs present — certificate logged in public CT logs"
                echo "$sct_info"
            else
                echo "[CT] No SCTs found in certificate — may not be in CT logs"
                echo "     Note: check crt.sh for this domain's certificates"
            fi

            # ALPACA attack hint (cross-protocol redirect check)
            echo ""
            echo "=== ALPACA Attack Assessment ==="
            echo "ALPACA (Application Layer Protocol Confusion):"
            echo "  Vulnerable if TLS cert covers multiple services (e.g. SMTP+HTTPS on same cert)"
            local cert_domain
            cert_domain=$(grep -oE "CN = [^,]+" "$cert_out" 2>/dev/null | head -1 | sed 's/CN = //' || true)
            echo "  Certificate CN: ${cert_domain:-[unknown]}"
            echo "  Manual check: confirm port ${port} does not share cert with SMTP(25/587/465) or FTP(21) services"

            # ROBOT attack hint (RSA key exchange)
            echo ""
            echo "=== ROBOT Attack Awareness ==="
            local kex_algo
            kex_algo=$(timeout 8 bash -c \
                "echo | openssl s_client -connect '${ip}:${port}' -servername '${ip}' 2>/dev/null \
                 | grep 'New, '" 2>/dev/null || true)
            if echo "$kex_algo" | grep -qiE "RSA\b"; then
                echo "[ROBOT RISK] RSA key exchange in use — server may be vulnerable to Bleichenbacher/ROBOT"
                echo "  CVE-2017-13099 / ROBOT: test with robot-detect tool for confirmation"
            else
                echo "[RSA KEX] Not detected in cipher suite — lower ROBOT risk (ECDHE/DHE preferred)"
            fi

            # Post-quantum TLS note
            echo ""
            echo "=== Post-Quantum TLS ==="
            local pq_ciphers
            pq_ciphers=$(timeout 8 bash -c \
                "echo | openssl s_client -connect '${ip}:${port}' -servername '${ip}' 2>/dev/null \
                 | grep 'Cipher    :'" 2>/dev/null || true)
            echo "Active cipher: ${pq_ciphers:-[could not determine]}"
            echo "PQ-awareness: TLS 1.3 with X25519/P-256 key exchange is quantum-safe *for confidentiality*"
            echo "  but authentication (RSA/ECDSA signatures) is still quantum-vulnerable."
            echo "  NIST PQC winners (ML-KEM/ML-DSA) not yet widely deployed. Monitor RFC 9180+ adoption."
        } | tee "$cert_ext_out"
        log_ok "  Extended cert analysis: ${cert_ext_out}"

        # CT log lookup via crt.sh (passive — no active connection to target)
        local cn_for_ct; cn_for_ct=$(grep -oE "CN = [^,]+" "$cert_out" 2>/dev/null | head -1 | sed 's/CN = //' || true)
        if [[ -n "$cn_for_ct" && "$cn_for_ct" != "[unknown]" ]]; then
            local ct_out="${dir}/ct_log_${port}_${ts}.json"
            log "  CT log lookup (crt.sh): ${cn_for_ct}"
            local ct_resp
            ct_resp=$(curl -s --max-time 20 \
                "https://crt.sh/?q=${cn_for_ct}&output=json" 2>/dev/null || true)
            if [[ -n "$ct_resp" ]]; then
                echo "$ct_resp" > "$ct_out" || true
                local ct_count
                ct_count=$(echo "$ct_resp" | python3 -c \
                    "import json,sys; d=json.load(sys.stdin); print(len(d))" 2>/dev/null || echo "0")
                log_info "  CT log: ${ct_count} certificate(s) found for ${cn_for_ct}"
                # Extract unique sans from CT for subdomain discovery
                local ct_sans
                ct_sans=$(echo "$ct_resp" | python3 -c \
                    "import json,sys
d=json.load(sys.stdin)
names=set()
for e in d:
    for n in e.get('name_value','').split('\n'):
        n=n.strip().lstrip('*.')
        if n: names.add(n)
print('\n'.join(sorted(names)))" 2>/dev/null || true)
                if [[ -n "$ct_sans" ]]; then
                    local ct_sans_file="${dir}/ct_sans_${port}_${ts}.txt"
                    echo "$ct_sans" > "$ct_sans_file"
                    log_info "  CT SANs discovered ($(echo "$ct_sans" | wc -l)): see ${ct_sans_file}"
                fi
            fi
        fi
    fi

    # ── 3. Security headers (curl) ─────────────────────────────────────────
    # Skip for known non-HTTP TLS services (mail, DB, LDAP, etc.)
    local _is_http=1
    case "$port" in
        25|110|143|465|587|993|995|636|389|3268|3269|5432|3306|27017|6379|1433)
            _is_http=0 ;;
    esac

    local headers_out="${dir}/headers_${port}_${ts}.txt"
    if [[ $_is_http -eq 0 ]]; then
        { echo "# HTTP Security Headers — ${target}"
          echo "# Engagement: ${PROJECT_NAME}"
          echo "# Date/Time:  $(_now)"
          echo "---"
          echo "[SKIP] Port ${port} is not an HTTP service — header check not applicable"
        } > "$headers_out"
        log_info "  Skipping HTTP header check — port ${port} is not an HTTP service"
    else
        {
            echo "# HTTP Security Headers — ${target}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "---"
            curl --max-time 15 --connect-timeout 5 \
                 -sk -I "https://${ip}:${port}" 2>/dev/null || \
                curl --max-time 15 --connect-timeout 5 \
                     -I "http://${ip}:${port}" 2>/dev/null || \
                echo "[WARN] curl failed"
        } | tee "$headers_out"
    fi

    # Analyse security headers — only meaningful for HTTP services
    local sec_headers_out="${dir}/sec_headers_${port}_${ts}.txt"
    if [[ $_is_http -eq 0 ]]; then
        echo "[SKIP] Port ${port} is not an HTTP service — header analysis not applicable" > "$sec_headers_out"
    else
        {
            echo "# Security Headers Analysis — ${target}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "---"
            local raw; raw=$(cat "$headers_out")
            local headers_to_check=(
                "Strict-Transport-Security"
                "Content-Security-Policy"
                "X-Frame-Options"
                "X-Content-Type-Options"
                "X-XSS-Protection"
                "Referrer-Policy"
                "Permissions-Policy"
                "Cross-Origin-Opener-Policy"
                "Cross-Origin-Resource-Policy"
                "Cross-Origin-Embedder-Policy"
                "Cache-Control"
                "Clear-Site-Data"
                "NEL"
            )
            local missing=()
            for h in "${headers_to_check[@]}"; do
                local val; val=$(echo "$raw" | grep -i "^${h}:" | head -1 || true)
                if [[ -n "$val" ]]; then
                    echo "  PRESENT: ${val}"
                else
                    echo "  MISSING: ${h}"
                    missing+=("$h")
                fi
            done
            echo ""
            echo "Missing headers (${#missing[@]}): ${missing[*]:-none}"

            # HSTS preload check
            local hsts_val; hsts_val=$(echo "$raw" | grep -i "^Strict-Transport-Security:" | head -1 || true)
            if [[ -n "$hsts_val" ]]; then
                echo ""
                echo "=== HSTS Analysis ==="
                echo "  Value: ${hsts_val}"
                echo "$hsts_val" | grep -qi "includeSubDomains" \
                    && echo "  [OK] includeSubDomains present" \
                    || echo "  [WARN] includeSubDomains MISSING — subdomains not covered by HSTS"
                echo "$hsts_val" | grep -qi "preload" \
                    && echo "  [OK] preload directive present" \
                    || echo "  [INFO] preload not set — not eligible for browser HSTS preload list"
                local max_age
                max_age=$(echo "$hsts_val" | grep -oE "max-age=[0-9]+" | grep -oE "[0-9]+" || echo "0")
                [[ "$max_age" -lt 31536000 ]] && \
                    echo "  [WARN] max-age=${max_age}s < 1 year (31536000s) — HSTS preload requires ≥1 year" || \
                    echo "  [OK] max-age=${max_age}s (≥1 year)"
            fi

            # Lucky13 / BEAST / POODLE indicator from legacy check output
            echo ""
            echo "=== Known TLS Attack Indicators ==="
            if [[ -f "$legacy_out" ]]; then
                echo "From legacy protocol check:"
                grep -E "ACCEPTED|REJECTED|NOT TESTED|FINDING" "$legacy_out" 2>/dev/null | sed 's/^/  /' || true
                grep -qi "tls1.*ACCEPTED\|tls1_1.*ACCEPTED" "$legacy_out" 2>/dev/null \
                    && echo "  [BEAST/LUCKY13 RISK] TLS 1.0/1.1 accepted — CBC cipher modes vulnerable to BEAST and Lucky13 timing attacks" || true
            fi
        } | tee "$sec_headers_out"
    fi

    log_ok "  Headers: ${sec_headers_out}"

    # ── 4. Append to TLS summary ───────────────────────────────────────────
    echo "| ${ip} | ${port} | ${expiry} | ${subject} | ${dir} |" \
        >> "working/tls_summary_${SESSION_TS}.md"
}

# =============================================================================
# MRK:04_SCREENS — SCREENSHOT CAPTURE | screens,screenshot,capture,external,grabscores | L480-499
# NAV-RULE: no-insert-before
# =============================================================================

run_grab_scores() {
    if [[ "$GRAB_SCREENS" -eq 0 ]]; then return; fi
    local script_path="${SCRIPT_DIR}/GrabScores-v2.5.py"
    if [[ ! -f "$script_path" ]]; then
        log_warn "GrabScores-v2.5.py not found at ${script_path} — skipping screenshots"
        return
    fi
    mkdir -p "$SCREENS_DIR"
    log "Running GrabScores-v2.5.py..."
    python3 "$script_path" \
        --targets "$TARGETS_FILE" \
        --output-dir "$SCREENS_DIR" 2>&1 | tee "working/grab_scores_${SESSION_TS}.log"
    log_ok "Screenshots: ${SCREENS_DIR}"
}

# =============================================================================
# MRK:04_MAIN — MAIN entry point | main,entry,point | L500-568
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    echo -e "${GREEN}"
    echo "════════════════════════════════════════════════"
    echo "  04_tls_scan.sh"
    echo "  TechGuard."
    echo "  Project: ${PROJECT_NAME}"
    echo "  Mode:    $([ "$FAST_MODE" -eq 1 ] && echo "fast" || echo "full (testssl)")"
    echo "════════════════════════════════════════════════"
    echo -e "${NC}"

    parse_db_conf

    # Trail: phase start
    local _04_t_start; _04_t_start=$(date +%s)
    trail_phase_start phase "tls" project "${PROJECT_NAME:-}" mode "${MODE:-}" session "${SESSION_TS:-$(_ts)}" ts "$(date -u +%FT%TZ)" fast_mode "${FAST_MODE:-0}" 2>/dev/null || true

    # TLS summary header
    mkdir -p "${EVIDENCE_BASE}/_sweep" "${EVIDENCE_BASE}/_exports" working
    cat > "working/tls_summary_${SESSION_TS}.md" << EOF
# TLS Assessment Summary — ${PROJECT_NAME}
*Generated: $(_now) | Session: ${SESSION_TS}*

| IP | Port | Cert Expiry | Subject | Evidence Dir |
|----|------|-------------|---------|--------------|
EOF

    # Assemble and process targets
    local targets; targets="$(assemble_targets)"
    if [[ -z "$targets" ]]; then
        log_err "No targets found. Provide --targets <file> or --host <IP:PORT>"
        exit 1
    fi

    local count; count=$(echo "$targets" | wc -l | tr -d ' ')
    log "TLS targets: ${count}"
    scope_confirm "$count"

    while IFS= read -r target; do
        [[ -z "$target" ]] && continue
        assess_host "$target"
    done <<< "$targets"

    # Screenshots
    run_grab_scores

    # Finalise summary
    echo "" >> "working/tls_summary_${SESSION_TS}.md"
    echo "---" >> "working/tls_summary_${SESSION_TS}.md"
    echo "*04_tls_scan.sh | TechGuard.*" \
        >> "working/tls_summary_${SESSION_TS}.md"

    export_db "tls"

    # Trail: phase end
    local _04_t_end; _04_t_end=$(date +%s)
    trail_phase_end phase "tls" project "${PROJECT_NAME:-}" session "${SESSION_TS:-}" duration_sec "$((_04_t_end - _04_t_start))" targets "$count" ts "$(date -u +%FT%TZ)" 2>/dev/null || true

    log_ok "TLS scan complete. Summary: working/tls_summary_${SESSION_TS}.md"
    log_ok "Evidence per host: ${EVIDENCE_BASE}/<IP>/testssl_<port>_<TS>.{html,json,log}"
}

main

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
