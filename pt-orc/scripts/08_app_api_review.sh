#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:08_NAV_TOC — Section index | nav,toc,index | L5-54
# - MRK:08_ROOT    — ROOT CHECK                  | root,check,euid              | L55-64   | ⚠ no-insert-before
# - MRK:08_CONF    — ENGAGEMENT CONFIGURATION    | conf,engagement,config,curl  | L65-111  | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:08_LOG     — COLOURS AND LOGGING         | log,colours,logging          | L112-136 | ⚠ no-insert-before
# - MRK:08_ARGS    — ARGUMENT PARSING            | args,argument,parsing        | L137-163 | ⚠ no-insert-before
# - MRK:08_DB      — MSF DB HELPERS              | db,msf,helpers,web,ports     | L164-233 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:08_CONFIRM — SCOPE CONFIRMATION          | confirm,scope,confirmation   | L234-261 | ⚠ no-insert-before; propose-before-edit
# - MRK:08_TARGETS — TARGET ASSEMBLY             | targets,target,assembly      | L262-301 | ⚠ no-insert-before; read-toc-first
# - MRK:08_FIND    — FINDING WRITER              | find,finding,jsonl,jq        | L302-327 | ⚠ no-insert-before; read-toc-first
# - MRK:08_TEST    — PER-TARGET API TESTS        | test,target,api,methods      | L328-616 | ⚠ no-insert-before; read-toc-first
# - MRK:08_MAIN    — MAIN entry point            | main,entry,point             | L617-720 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 10 entries | Integrity-hash: b84c2a9f1e07d563 | Last-indexed: 2026-06-06T00:00:00Z

# =============================================================================
# 08_app_api_review.sh — TechGuard. [VAPT-Enhanced v1.0 — 2026-06-06]
# Application / API security review — curl-based, auth-aware, stealth-tier aware
# Tests: HTTP method enum, schema discovery, auth bypass, rate limiting,
#        CORS misconfiguration, mass assignment, IDOR/BOLA, security headers
# Consumes: MSF DB (web hosts from 03_comp_scan.sh / 05_web_enum.sh)
# Or:       --targets <file>  or  --host <IP:PORT>
# Produces: per-host evidence files + JSONL findings + markdown summary
# =============================================================================
# USAGE:
#   ./08_app_api_review.sh [OPTIONS]
#
# OPTIONS:
#   --targets <file>    File with host:port entries (one per line)
#   --host <IP:PORT>    Single target (can repeat)
#   --from-db           Pull web hosts from MSF DB (default if no targets given)
#   --tier <n>          ghost|normal|loud — controls request rate and delays
#   --creds <user:pass> HTTP Basic / login credentials for auth testing
#   --token <bearer>    Bearer token for JWT/auth tests
#   --fast              Headers + schema discovery only; skip brute-force tests
#   --yes               Skip interactive scope confirmation
#   --dry-run           Print commands without executing
#
# ENVIRONMENT VARS:
#   PROJECT_NAME        MSF workspace name
#   EVIDENCE_BASE       Base evidence directory (default: evidence)
#   CURL_TIMEOUT        Seconds per curl request (default: 10)
set -uo pipefail

# Location of this script — keep evidence inside this PT-Orc directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:08_ROOT — ROOT CHECK | root,check,euid | L55-64
# NAV-RULE: no-insert-before
# =============================================================================
if [[ "$EUID" -ne 0 ]] && [[ "${PTORC_ALLOW_NON_ROOT:-0}" != "1" ]]; then
    echo "[ERROR] This script must be run as root (required for db_nmap)."
    echo "        Run: sudo $0 $*"
    exit 1
fi

# =============================================================================
# MRK:08_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,config,curl | L65-111
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

# Keep evidence inside the PT-Orc directory
EVIDENCE_BASE="${SCAN_EVIDENCE_DIR:-${SCRIPT_DIR}/evidence}"

CURL_TIMEOUT="${CURL_TIMEOUT:-10}"
CURL_CONNECT=5

TIER="normal"
FROM_DB=1
FAST_MODE=0
AUTO_YES=0
DRY_RUN=0

# Auth options
CREDS=""          # user:pass for HTTP Basic / login
BEARER_TOKEN=""   # Bearer token for JWT tests

EXTRA_HOSTS=()
TARGETS_FILE=""

# Tier → inter-request delay (seconds) for ghost/evasion to avoid rate-limit triggers
tier_delay() { case "$1" in ghost) echo 2;; evasion) echo 3;; normal) echo 0;; loud) echo 0;; *) echo 0;; esac; }

# Known TLS ports (same fast-path as 05)
TLS_PORTS="443 8443 4443 9443 10443"

# =============================================================================
# MRK:08_LOG — COLOURS AND LOGGING | log,colours,logging | L112-136
# NAV-RULE: no-insert-before
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

_ts()  { date +'%Y%m%d_%H%M%S'; }
_now() { date +'%Y-%m-%d %H:%M:%S'; }

SESSION_TS="$(_ts)"
[[ "$EVIDENCE_BASE" != /* ]] && EVIDENCE_BASE="$(pwd)/${EVIDENCE_BASE}"
mkdir -p "${EVIDENCE_BASE}/_sweep" working
LOG_FILE="${EVIDENCE_BASE}/_sweep/app_api_review_${SESSION_TS}.log"

# Colored to stderr, plain to logfile
log()     { local m="[$(_now)] $1";   echo -e "${BLUE}${m}${NC}" >&2;   echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_ok()  { local m="[$(_now)] ✓ $1"; echo -e "${GREEN}${m}${NC}" >&2;  echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_warn(){ local m="[$(_now)] ⚠ $1"; echo -e "${YELLOW}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_err() { local m="[$(_now)] ✗ $1"; echo -e "${RED}${m}${NC}" >&2;    echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_info(){ local m="[$(_now)]   $1"; echo -e "${CYAN}${m}${NC}" >&2;   echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }

# Ownership helper removed per operator preference; leave ownership as-is

# =============================================================================
# MRK:08_ARGS — ARGUMENT PARSING | args,argument,parsing | L137-163
# NAV-RULE: no-insert-before
# =============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --targets)  TARGETS_FILE="$2"; FROM_DB=0; shift 2 ;;
        --host)     EXTRA_HOSTS+=("$2"); FROM_DB=0; shift 2 ;;
        --from-db)  FROM_DB=1; shift ;;
        --tier)     TIER="$2"; shift 2 ;;
        --creds)    CREDS="$2"; shift 2 ;;
        --token)    BEARER_TOKEN="$2"; shift 2 ;;
        --fast)     FAST_MODE=1; shift ;;
        --yes)      AUTO_YES=1; shift ;;
        --dry-run)  DRY_RUN=1; shift ;;
        *) log_err "Unknown argument: $1"; exit 1 ;;
    esac
done

# =============================================================================
# MRK:08_DB — MSF DB HELPERS | db,msf,helpers,web,ports | L164-233
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

_get_web_hosts_csv() {
    local csv
    csv=$(find "${EVIDENCE_BASE}/_exports" -name 'services_tcp_*.csv' 2>/dev/null | sort | tail -1)
    [[ -z "$csv" ]] && return
    awk -F',' 'NR>1 {
        gsub(/"/, "", $1); gsub(/"/, "", $2); gsub(/"/, "", $3); gsub(/"/, "", $5)
        if ($3=="tcp" && $5=="open" && \
            ($2=="80"||$2=="443"||$2=="8080"||$2=="8443"||$2=="4443"|| \
             $2=="8888"||$2=="9443"||$2=="9200"||$2=="10443"||$2=="8006"))
            print $1":"$2
    }' "$csv" 2>/dev/null | sort -u
}

# =============================================================================
# MRK:08_CONFIRM — SCOPE CONFIRMATION | confirm,scope,confirmation | L234-261
# NAV-RULE: no-insert-before; propose-before-edit
# =============================================================================

scope_confirm() {
    local target_count="${1:-0}"
    [[ "${AUTO_YES:-0}" -eq 1 ]] && return 0
    echo ""
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    echo -e "\033[1m  SCOPE CONFIRMATION — 08_app_api_review.sh\033[0m"
    echo -e "\033[1m\033[1;33m════════════════════════════════════════════════\033[0m"
    printf "  %-22s %s\n" "Project:"     "${PROJECT_NAME}"
    printf "  %-22s %s\n" "Tier:"        "${TIER}"
    printf "  %-22s %s\n" "Targets:"     "${target_count}"
    printf "  %-22s %s\n" "Creds:"       "$([ -n "$CREDS" ] && echo "provided" || echo "none")"
    printf "  %-22s %s\n" "Bearer token:" "$([ -n "$BEARER_TOKEN" ] && echo "provided" || echo "none")"
    printf "  %-22s %s\n" "Fast mode:"   "$([ "$FAST_MODE" -eq 1 ] && echo "YES (headers+schema only)" || echo "no")"
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
# MRK:08_TARGETS — TARGET ASSEMBLY | targets,target,assembly | L262-301
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
# MRK:08_FIND — FINDING WRITER | find,finding,jsonl,jq | L302-327
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

# Global finding counter — reset per target via host_safe variable in test_target
declare -g _FIND_CTR=0

# emit_finding <host_safe> <title> <severity> <description> <recommendation> <evidence_ids_csv>
# Appends one JSON line to working/08_app_api_findings_${SESSION_TS}.jsonl
emit_finding() {
    local host_safe="$1" title="$2" severity="$3" description="$4" recommendation="$5"
    local ev_ids_csv="${6:-}"
    (( _FIND_CTR++ )) || true
    local n; printf -v n '%03d' "$_FIND_CTR"
    local fid="f-08-${host_safe}-${n}"
    local ev_arr="[]"
    if [[ -n "$ev_ids_csv" ]]; then
        # Build a JSON array from comma-separated evidence IDs
        ev_arr=$(echo "$ev_ids_csv" | tr ',' '\n' | \
            jq -Rn '[inputs | select(length>0)]' 2>/dev/null || echo '[]')
    fi
    jq -nc \
        --arg id          "$fid" \
        --arg title       "$title" \
        --arg severity    "$severity" \
        --arg description "$description" \
        --arg recommendation "$recommendation" \
        --argjson ev_arr  "$ev_arr" \
        '{id:$id,title:$title,severity:$severity,phase:"08_app_api",evidence_ids:$ev_arr,description:$description,recommendation:$recommendation,retest_status:"n/a",residual_risk:""}' \
        >> "working/08_app_api_findings_${SESSION_TS}.jsonl" 2>/dev/null || true
    log_warn "  FINDING [${severity}]: ${title}"
}

# =============================================================================
# MRK:08_TEST — PER-TARGET API TESTS | test,target,api,methods | L328-616
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

detect_tls() {
    local ip="$1" port="$2"
    for p in $TLS_PORTS; do
        [[ "$port" == "$p" ]] && return 0
    done
    timeout 6 bash -c \
        "echo | openssl s_client -connect '${ip}:${port}' \
         -servername '${ip}' 2>/dev/null | grep -q 'SSL-Session'" \
        >/dev/null 2>&1
}

# _curl <extra_args...> — honours DRY_RUN; always silent+TLS-skip
_curl() {
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        log_info "  [DRY-RUN] curl -sk --max-time ${CURL_TIMEOUT} --connect-timeout ${CURL_CONNECT} $*"
        return 0
    fi
    curl -sk --max-time "$CURL_TIMEOUT" --connect-timeout "$CURL_CONNECT" "$@" 2>/dev/null || true
}

# _tier_pause — insert delay between requests when running ghost/evasion tier
_tier_pause() {
    local d; d="$(tier_delay "$TIER")"
    [[ "$d" -gt 0 ]] && rate_limit_wait "$d"
}

# test_target <host> <port>
# Runs all eight API security tests against a single target, writes evidence,
# and emits findings to the JSONL file.
test_target() {
    local ip="$1" port="$2"
    local dir="${EVIDENCE_BASE}/${ip}"
    local ts; ts="$(_ts)"
    local host_safe="${ip//./_}"

    mkdir -p "$dir"

    # Determine protocol
    local proto="http"
    detect_tls "$ip" "$port" && proto="https"
    local base="${proto}://${ip}:${port}"

    # Per-target finding counter reset
    _FIND_CTR=0

    # New-test result accumulators (used in SUMMARY_ROW)
    local cookie_issues=0
    local sensitive_found=0
    local verbose_errors=0
    local authz_issues=0

    log "API review: ${base} [tier=${TIER}]"

    # ── 1. HTTP Method Enumeration ─────────────────────────────────────────
    local methods_out="${dir}/app_methods_${port}_${ts}.txt"
    {
        echo "# HTTP Method Enumeration — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local opts_resp
        opts_resp=$(_curl -X OPTIONS -i "${base}/")
        echo "$opts_resp"
        echo ""
        local allow_hdr; allow_hdr=$(echo "$opts_resp" | grep -i "^Allow:" | head -1 | tr -d '\r' || true)
        echo "Allow header: ${allow_hdr:-[not returned]}"

        # Flag TRACE
        if echo "$opts_resp" | grep -i "^Allow:" | grep -qi "TRACE"; then
            echo "TRACE_ENABLED: YES"
            log_warn "  Method: TRACE enabled on ${base}"
        fi

        # Active TRACE probe to confirm
        local trace_code
        trace_code=$(_curl -X TRACE -o /dev/null -w "%{http_code}" "${base}/")
        echo "TRACE probe HTTP status: ${trace_code:-000}"
        if [[ "$trace_code" == "200" ]]; then
            echo "TRACE_CONFIRMED: YES (active probe returned 200)"
        fi

        # PUT/DELETE without auth — check for permissive 200/201/204
        for method in PUT DELETE; do
            local mc
            mc=$(_curl -X "$method" -o /dev/null -w "%{http_code}" "${base}/api/test_method_probe")
            echo "${method} probe (no auth): HTTP ${mc:-000}"
            if [[ "$mc" == "200" || "$mc" == "201" || "$mc" == "204" ]] && [[ -z "$BEARER_TOKEN" ]]; then
                echo "DANGEROUS_METHOD_NO_AUTH: ${method} returned ${mc} without credentials"
            fi
            _tier_pause
        done
    } | tee "$methods_out"
    log_ok "  Methods: ${methods_out}"

    # Emit findings for method issues
    if grep -q "TRACE_ENABLED: YES\|TRACE_CONFIRMED: YES" "$methods_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "HTTP TRACE Method Enabled" \
            "high" \
            "The server at ${base} has the TRACE HTTP method enabled. TRACE can be used in Cross-Site Tracing (XST) attacks to steal cookies and auth headers even when HttpOnly is set." \
            "Disable the TRACE method in the web server / application configuration. In Apache: TraceEnable off. In Nginx: limit_except GET POST { deny all; }." \
            "ev-08-${host_safe}-001"
    fi
    if grep -q "DANGEROUS_METHOD_NO_AUTH:" "$methods_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "Dangerous HTTP Methods Without Authentication (PUT/DELETE)" \
            "high" \
            "The server at ${base} accepts PUT or DELETE requests on API paths without requiring authentication credentials. This may allow unauthenticated data manipulation or deletion." \
            "Require authentication for all state-mutating HTTP methods. Confirm via WAF rules or application-layer ACLs. Audit all routes accepting PUT/PATCH/DELETE." \
            "ev-08-${host_safe}-002"
    fi
    _tier_pause

    # ── 2. API Schema Discovery ────────────────────────────────────────────
    local schema_out="${dir}/app_schema_${port}_${ts}.txt"
    local schema_exposed=0
    {
        echo "# API Schema Discovery — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local schema_paths=(
            "/openapi.json" "/openapi.yaml"
            "/swagger.json" "/swagger-ui.html"
            "/api-docs" "/api/docs"
            "/v1/api-docs" "/v2/api-docs"
            "/api/swagger.json"
            "/graphql"
            "/api/schema/"
        )
        for path in "${schema_paths[@]}"; do
            local sc ct
            # Capture both status code and content-type in one request
            sc=$(_curl -o /dev/null -w "%{http_code}" "${base}${path}")
            ct=$(_curl -I -o /dev/null -w "%{content_type}" "${base}${path}")
            sc="${sc:-000}"
            echo "  [${sc}] ${path}  Content-Type: ${ct:-unknown}"
            if [[ "$sc" != "404" && "$sc" != "000" && "$sc" != "410" && "$sc" != "403" ]]; then
                log_info "    Schema candidate [${sc}]: ${path}"
                schema_exposed=1
                echo "  SCHEMA_EXPOSED: ${path} (HTTP ${sc})"
            fi
            _tier_pause
        done
    } | tee "$schema_out"
    log_ok "  Schema discovery: ${schema_out}"

    if [[ "$schema_exposed" -eq 1 ]]; then
        emit_finding "$host_safe" \
            "API Schema/Documentation Publicly Exposed" \
            "info" \
            "One or more API schema or documentation endpoints (OpenAPI/Swagger/GraphQL) are accessible at ${base} without authentication. This exposes the full API structure, endpoint names, parameter types, and security requirements to potential attackers." \
            "Restrict access to API documentation and schema endpoints. If external consumers require access, protect with authentication. Remove from production if not needed." \
            "ev-08-${host_safe}-003"
    fi
    _tier_pause

    # ── 3. Authentication Testing ──────────────────────────────────────────
    local auth_out="${dir}/app_auth_${port}_${ts}.txt"
    local auth_bypass_found=0
    {
        echo "# Authentication Testing — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local api_paths=(
            "/api/users" "/api/admin" "/api/v1/users" "/api/v1/admin"
            "/api/profile" "/api/config" "/v1/users"
        )

        echo "=== Unauthenticated probe ==="
        for path in "${api_paths[@]}"; do
            local sc
            sc=$(_curl -o /dev/null -w "%{http_code}" "${base}${path}")
            sc="${sc:-000}"
            echo "  [${sc}] ${path}"
            if [[ "$sc" == "200" ]] && [[ -z "$BEARER_TOKEN" ]]; then
                echo "  AUTH_BYPASS_CANDIDATE: ${path}"
                auth_bypass_found=1
                log_warn "    Unauthenticated 200 on ${path}"
            fi
            _tier_pause
        done

        # JWT none-algorithm test (only if token provided)
        if [[ -n "$BEARER_TOKEN" ]]; then
            echo ""
            echo "=== JWT none-algorithm test ==="
            # Decode the header and payload; replace alg with none; strip signature
            local header_b64 payload_b64 none_token
            header_b64=$(echo "$BEARER_TOKEN" | cut -d. -f1 2>/dev/null || true)
            payload_b64=$(echo "$BEARER_TOKEN" | cut -d. -f2 2>/dev/null || true)
            if [[ -n "$header_b64" && -n "$payload_b64" ]]; then
                # Rebuild header with alg=none (base64url-encoded)
                local none_hdr
                none_hdr=$(printf '{"alg":"none","typ":"JWT"}' | \
                    python3 -c "import base64,sys; d=sys.stdin.read(); print(base64.urlsafe_b64encode(d.encode()).rstrip(b'=').decode())" 2>/dev/null || \
                    echo "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0")
                none_token="${none_hdr}.${payload_b64}."
                echo "  None-alg token (header replaced): ${none_token:0:60}..."
                local jwt_sc
                jwt_sc=$(_curl -H "Authorization: Bearer ${none_token}" \
                    -o /dev/null -w "%{http_code}" "${base}/api/users")
                echo "  JWT none-alg probe /api/users: HTTP ${jwt_sc:-000}"
                if [[ "$jwt_sc" == "200" ]]; then
                    echo "  JWT_NONE_BYPASS: /api/users returned 200 with none-algorithm token"
                    log_warn "    JWT none-algorithm accepted at ${base}/api/users"
                fi
            else
                echo "  [SKIP] Could not split Bearer token for none-alg test"
            fi
        fi
    } | tee "$auth_out"
    log_ok "  Auth testing: ${auth_out}"

    if [[ "$auth_bypass_found" -eq 1 ]]; then
        emit_finding "$host_safe" \
            "Unauthenticated Access to API Endpoint" \
            "high" \
            "One or more API endpoints at ${base} returned HTTP 200 without any credentials. Endpoints such as /api/users, /api/admin, or /api/profile may expose sensitive user or configuration data to unauthenticated requests." \
            "Enforce authentication on all API endpoints. Use a centralised authentication middleware. Audit each endpoint's access control decorators/attributes. Apply principle of least privilege." \
            "ev-08-${host_safe}-004"
    fi
    if grep -q "JWT_NONE_BYPASS:" "$auth_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "JWT None-Algorithm Signature Bypass" \
            "high" \
            "The API at ${base} accepted a JWT token with the algorithm set to 'none', bypassing signature verification. This allows any attacker with a valid payload to forge tokens without knowing the signing secret." \
            "Reject JWTs with alg=none in all authentication middleware. Maintain an explicit allowlist of accepted algorithm(s). Use a hardened JWT library (e.g. python-jose with algorithms=['RS256']). Never trust the alg field from the token header." \
            "ev-08-${host_safe}-005"
    fi
    _tier_pause

    # ── 4. Rate Limiting Test ──────────────────────────────────────────────
    local rate_out="${dir}/app_rate_limit_${port}_${ts}.txt"
    if [[ "$FAST_MODE" -eq 0 ]]; then
        {
            echo "# Rate Limiting Test — ${base}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "---"
            # Determine target path: first of /api/login or /login that responds
            local login_path=""
            for candidate in "/api/login" "/login"; do
                local probe_sc
                probe_sc=$(_curl -o /dev/null -w "%{http_code}" "${base}${candidate}")
                if [[ "${probe_sc:-000}" != "000" ]]; then
                    login_path="$candidate"
                    echo "Login path detected: ${login_path} (HTTP ${probe_sc})"
                    break
                fi
            done
            [[ -z "$login_path" ]] && login_path="/api/login" && echo "No login path detected — defaulting to /api/login"

            echo ""
            echo "Sending 20 rapid requests to ${login_path} ..."
            local saw_429=0
            for i in $(seq 1 20); do
                local rsc
                rsc=$(_curl -X POST \
                    -H "Content-Type: application/json" \
                    -d '{"username":"ratelimit_probe","password":"probe_password"}' \
                    -o /dev/null -w "%{http_code}" \
                    "${base}${login_path}")
                echo "  Request ${i}: HTTP ${rsc:-000}"
                [[ "${rsc:-000}" == "429" ]] && { saw_429=1; echo "  [429 SEEN at request ${i} — rate limiting active]"; break; }
            done
            if [[ "$saw_429" -eq 0 ]]; then
                echo ""
                echo "RATE_LIMIT: MISSING — no HTTP 429 observed after 20 rapid requests"
                log_warn "  Rate limiting absent on ${base}${login_path}"
            else
                echo ""
                echo "RATE_LIMIT: PRESENT — HTTP 429 returned"
                log_ok "  Rate limiting confirmed on ${base}${login_path}"
            fi
        } | tee "$rate_out"
        log_ok "  Rate limit test: ${rate_out}"

        if grep -q "RATE_LIMIT: MISSING" "$rate_out" 2>/dev/null; then
            emit_finding "$host_safe" \
                "Missing Rate Limiting on Login Endpoint" \
                "medium" \
                "The login endpoint at ${base} does not enforce rate limiting. Sending 20 rapid successive requests produced no HTTP 429 response, indicating the application is susceptible to brute-force and credential-stuffing attacks." \
                "Implement rate limiting on all authentication endpoints (e.g. 5 attempts per minute per IP). Add account lockout or CAPTCHA after repeated failures. Consider tools like fail2ban, nginx limit_req_zone, or application-layer libraries (e.g. flask-limiter, express-rate-limit)." \
                "ev-08-${host_safe}-006"
        fi
        _tier_pause
    else
        log_info "  Rate limit test: SKIPPED (fast mode)"
    fi

    # ── 5. CORS Misconfiguration ───────────────────────────────────────────
    local cors_out="${dir}/app_cors_${port}_${ts}.txt"
    {
        echo "# CORS Misconfiguration — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local cors_paths=("/" "/api/" "/api/v1/")
        local attacker_origin="https://evil.attacker.com"

        for cpath in "${cors_paths[@]}"; do
            local cors_resp acao acac
            cors_resp=$(_curl -I -H "Origin: ${attacker_origin}" "${base}${cpath}")
            acao=$(echo "$cors_resp" | grep -i "^access-control-allow-origin:" | head -1 | tr -d '\r' || true)
            acac=$(echo "$cors_resp" | grep -i "^access-control-allow-credentials:" | head -1 | tr -d '\r' || true)
            echo "  Path: ${cpath}"
            echo "  ACAO: ${acao:-[not set]}"
            echo "  ACAC: ${acac:-[not set]}"

            if echo "$acao" | grep -qiF "${attacker_origin}"; then
                echo "  CORS_MISCONFIG_HIGH: attacker origin reflected with credentials=${acac}"
            elif echo "$acao" | grep -q '\*' && echo "$acac" | grep -qi "true"; then
                echo "  CORS_MISCONFIG_HIGH: wildcard ACAO with credentials=true"
            elif echo "$acao" | grep -q '\*'; then
                echo "  CORS_MISCONFIG_LOW: ACAO=* (no credentials)"
            fi
            echo ""
            _tier_pause
        done
    } | tee "$cors_out"
    log_ok "  CORS test: ${cors_out}"

    if grep -q "CORS_MISCONFIG_HIGH:" "$cors_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "CORS Misconfiguration — Attacker Origin Reflected or Wildcard with Credentials" \
            "high" \
            "The API at ${base} reflects an attacker-controlled origin in Access-Control-Allow-Origin, or sets ACAO=* combined with Access-Control-Allow-Credentials: true. This enables cross-origin requests from attacker sites that can read authenticated responses." \
            "Never reflect arbitrary request origins in ACAO. Maintain a strict allowlist of trusted origins. Never combine ACAO=* with ACAC=true (this is disallowed by the browser specification but some servers permit it). Validate the Origin header server-side before echoing it back." \
            "ev-08-${host_safe}-007"
    elif grep -q "CORS_MISCONFIG_LOW:" "$cors_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "CORS Misconfiguration — Wildcard Access-Control-Allow-Origin" \
            "low" \
            "The API at ${base} returns Access-Control-Allow-Origin: * on one or more paths. While credentials are not enabled, this allows any web origin to read API responses, which may leak sensitive data to third-party sites." \
            "Replace the wildcard ACAO with an explicit origin allowlist. Avoid ACAO=* on endpoints that return any application-specific data. Apply the strictest CORS policy that satisfies your legitimate cross-origin consumers." \
            "ev-08-${host_safe}-008"
    fi
    _tier_pause

    # ── 6. Mass Assignment Test ────────────────────────────────────────────
    local massassign_out="${dir}/app_mass_assign_${port}_${ts}.txt"
    if [[ "$FAST_MODE" -eq 0 ]]; then
        {
            echo "# Mass Assignment Test — ${base}"
            echo "# Engagement: ${PROJECT_NAME}"
            echo "# Date/Time:  $(_now)"
            echo "---"
            local ma_ts; ma_ts=$(date +%s)
            local ma_payload
            ma_payload=$(printf '{"username":"test_ma_%s","role":"admin","is_admin":true,"admin":true}' "$ma_ts")
            local ma_paths=("/api/users" "/api/register" "/api/profile")

            for mpath in "${ma_paths[@]}"; do
                local -a curl_auth_args=()
                [[ -n "$CREDS" ]] && curl_auth_args=(-u "$CREDS")
                [[ -n "$BEARER_TOKEN" ]] && curl_auth_args=(-H "Authorization: Bearer $BEARER_TOKEN")

                local ma_resp ma_sc
                set +u
                ma_resp=$(_curl -X POST \
                    -H "Content-Type: application/json" \
                    -d "$ma_payload" \
                    -w "\n__STATUS__%{http_code}" \
                    "${curl_auth_args[@]}" \
                    "${base}${mpath}")
                set -u
                ma_sc=$(echo "$ma_resp" | grep "__STATUS__" | sed 's/__STATUS__//' | tr -d '\n' || echo "000")
                local ma_body; ma_body=$(echo "$ma_resp" | grep -v "__STATUS__" || true)

                echo "  Path: ${mpath}  HTTP: ${ma_sc}"
                echo "  Response (first 10 lines):"
                echo "$ma_body" | head -10
                echo ""

                # Check if admin/role fields are reflected in response
                if echo "$ma_body" | grep -qiE '"role"\s*:\s*"admin"|"is_admin"\s*:\s*true|"admin"\s*:\s*true'; then
                    echo "  MASS_ASSIGN_CANDIDATE: admin/role fields reflected in response from ${mpath}"
                    log_warn "    Mass assignment candidate at ${base}${mpath}"
                fi
                _tier_pause
            done
        } | tee "$massassign_out"
        log_ok "  Mass assignment: ${massassign_out}"

        if grep -q "MASS_ASSIGN_CANDIDATE:" "$massassign_out" 2>/dev/null; then
            emit_finding "$host_safe" \
                "Potential Mass Assignment Vulnerability" \
                "medium" \
                "The API at ${base} appears to reflect privilege fields (role, is_admin, admin) supplied in a POST body back in the response. This suggests the application may bind request parameters directly to model attributes without filtering sensitive fields." \
                "Use an explicit allowlist (include-only) of bindable attributes for each model/DTO. Never expose internal fields such as role or admin status to user-supplied input. Apply input validation and use separate request/response DTO objects. Review ORM/framework mass-assignment protection settings." \
                "ev-08-${host_safe}-009"
        fi
        _tier_pause
    else
        log_info "  Mass assignment: SKIPPED (fast mode)"
    fi

    # ── 7. IDOR / BOLA Test ───────────────────────────────────────────────
    local idor_out="${dir}/app_idor_${port}_${ts}.txt"
    {
        echo "# IDOR / BOLA Test — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local idor_paths=("/api/users/1" "/api/users/2" "/api/orders/1" "/api/items/1")

        echo "=== Unauthenticated object access probe ==="
        for ipath in "${idor_paths[@]}"; do
            local isc
            isc=$(_curl -o /dev/null -w "%{http_code}" "${base}${ipath}")
            isc="${isc:-000}"
            echo "  [${isc}] ${ipath}"
            if [[ "$isc" == "200" ]]; then
                echo "  IDOR_CANDIDATE: ${ipath} returned 200 without credentials"
                log_warn "    IDOR candidate (no auth) at ${base}${ipath}"
            fi
            _tier_pause
        done

        # If token provided: simulate cross-user access pattern (token for user2 accessing user1)
        if [[ -n "$BEARER_TOKEN" ]]; then
            echo ""
            echo "=== Cross-user token probe (token user accessing /api/users/1) ==="
            local xsc
            xsc=$(_curl -H "Authorization: Bearer ${BEARER_TOKEN}" \
                -o /dev/null -w "%{http_code}" "${base}/api/users/1")
            echo "  [${xsc:-000}] /api/users/1 with supplied token"
            if [[ "${xsc:-000}" == "200" ]]; then
                echo "  IDOR_CANDIDATE_WITH_TOKEN: /api/users/1 returned 200 — verify this belongs to a different user than the token"
                log_warn "    Cross-user IDOR candidate at ${base}/api/users/1"
            fi
        fi
    } | tee "$idor_out"
    log_ok "  IDOR/BOLA: ${idor_out}"

    if grep -q "IDOR_CANDIDATE:" "$idor_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "Insecure Direct Object Reference (IDOR/BOLA) — Unauthenticated Access" \
            "high" \
            "One or more object-level API endpoints at ${base} (e.g. /api/users/1, /api/orders/1) returned HTTP 200 without any authentication. Attackers can enumerate and access arbitrary resources by incrementing or manipulating the object identifier." \
            "Enforce authentication on all resource endpoints. Implement object-level authorisation checks (BOLA controls) that verify the requesting user owns or has permission to access the specific resource. Never rely on sequential IDs — use opaque UUIDs or signed references." \
            "ev-08-${host_safe}-010"
    fi
    _tier_pause

    # ── 8. Security Headers on API ─────────────────────────────────────────
    local api_headers_out="${dir}/app_api_headers_${port}_${ts}.txt"
    {
        echo "# API Security Headers — ${base}/api/"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local raw_headers
        raw_headers=$(_curl -I "${base}/api/")
        echo "$raw_headers"
        echo ""
        echo "=== Security Header Analysis ==="
        local missing_hdrs=()
        for hdr in \
            "X-Content-Type-Options" \
            "X-Frame-Options" \
            "Content-Security-Policy" \
            "Strict-Transport-Security"; do
            local hval
            hval=$(echo "$raw_headers" | grep -i "^${hdr}:" | head -1 || true)
            if [[ -n "$hval" ]]; then
                echo "  PRESENT: ${hval}"
            else
                echo "  MISSING: ${hdr}"
                missing_hdrs+=("$hdr")
            fi
        done
        echo ""
        set +u
        echo "Missing: ${#missing_hdrs[@]} / 4 checked"
        if [[ ${#missing_hdrs[@]} -ge 2 ]]; then
            echo "HEADERS_FINDING: 2 or more security headers absent: ${missing_hdrs[*]}"
        fi
        set -u
    } | tee "$api_headers_out"
    log_ok "  API headers: ${api_headers_out}"

    if grep -q "HEADERS_FINDING:" "$api_headers_out" 2>/dev/null; then
        local missing_list
        missing_list=$(grep "MISSING:" "$api_headers_out" | awk '{print $2}' | paste -sd ',' || true)
        emit_finding "$host_safe" \
            "Missing Security Headers on API Endpoint" \
            "low" \
            "The API at ${base}/api/ is missing two or more recommended security response headers: ${missing_list}. Absent headers increase exposure to MIME-sniffing, clickjacking, and cross-site scripting attack vectors." \
            "Add the missing HTTP security headers to all API responses. Configure X-Content-Type-Options: nosniff, X-Frame-Options: DENY, and a restrictive Content-Security-Policy. Enable Strict-Transport-Security with includeSubDomains for HTTPS endpoints." \
            "ev-08-${host_safe}-011"
    fi
    _tier_pause

    # ── 9. Cookie Security Analysis ───────────────────────────────────────────
    local cookie_out="${dir}/app_cookies_${port}_${ts}.txt"
    {
        echo "# Cookie Security Analysis — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local cookie_paths=("/" "/login" "/api/login" "/api/auth" "/auth")
        for cpath in "${cookie_paths[@]}"; do
            local resp
            resp=$(_curl -c /dev/null -I "${base}${cpath}")
            local cookies; cookies=$(echo "$resp" | grep -i "^Set-Cookie:" || true)
            [[ -z "$cookies" ]] && continue
            echo "  Path: ${cpath}"
            echo "$cookies"
            echo ""
            while IFS= read -r cookie_line; do
                [[ -z "$cookie_line" ]] && continue
                local cname; cname=$(echo "$cookie_line" | sed 's/Set-Cookie: //i' | cut -d= -f1 | tr -d ' \r')
                echo "  Cookie: ${cname}"
                if ! echo "$cookie_line" | grep -qi "HttpOnly"; then
                    echo "  MISSING_HTTPONLY: ${cname}"
                    log_warn "  Cookie '${cname}' on ${cpath} lacks HttpOnly"
                    (( cookie_issues++ )) || true
                fi
                if ! echo "$cookie_line" | grep -qi "Secure"; then
                    echo "  MISSING_SECURE: ${cname}"
                    log_warn "  Cookie '${cname}' on ${cpath} lacks Secure flag"
                    (( cookie_issues++ )) || true
                fi
                if ! echo "$cookie_line" | grep -qi "SameSite"; then
                    echo "  MISSING_SAMESITE: ${cname}"
                fi
            done <<< "$cookies"
            _tier_pause
        done
        echo ""
        echo "Cookie attribute issues: ${cookie_issues}"
        [[ "$cookie_issues" -gt 0 ]] && echo "COOKIE_SECURITY_ISSUES: ${cookie_issues}"
    } | tee "$cookie_out"
    log_ok "  Cookie security: ${cookie_out}"

    if grep -q "COOKIE_SECURITY_ISSUES:" "$cookie_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "Insecure Cookie Attributes — Missing HttpOnly or Secure Flag" \
            "medium" \
            "One or more session or authentication cookies on ${base} are missing required security attributes. HttpOnly prevents JavaScript access (mitigates XSS session theft). Secure ensures cookies are only transmitted over HTTPS." \
            "Set HttpOnly on all session cookies. Set the Secure flag on all cookies served over HTTPS. Configure SameSite=Strict or SameSite=Lax to prevent CSRF. Audit cookie configuration in web server, load balancer, and application framework." \
            "ev-08-${host_safe}-012"
    fi
    _tier_pause

    # ── 10. Sensitive Data Exposure ───────────────────────────────────────────
    local sensitive_out="${dir}/app_sensitive_${port}_${ts}.txt"
    {
        echo "# Sensitive Data Exposure — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        local sensitive_paths=("/api/users" "/api/profile" "/api/me" "/api/data" "/api/export")
        for spath in "${sensitive_paths[@]}"; do
            local sc body
            sc=$(_curl -o /dev/null -w "%{http_code}" "${base}${spath}")
            if [[ "${sc:-000}" == "000" || "${sc:-000}" == "404" ]]; then continue; fi
            body=$(_curl "${base}${spath}" | head -c 2000)
            echo "  [${sc}] ${spath}"
            echo "  Response (first 2000 bytes):"
            echo "$body"
            echo ""
            # Email addresses
            if echo "$body" | grep -qoE '[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'; then
                echo "  PII_EMAIL: email addresses found"
                log_warn "  PII email in ${spath}"
                (( sensitive_found++ )) || true
            fi
            # API key / secret prefixes
            if echo "$body" | grep -qoE '(sk|pk|AKIA|ghp|gho|glpat|xoxb|xoxp)[_\-][A-Za-z0-9]{10,}'; then
                echo "  SECRET_KEY: API key pattern found"
                log_warn "  API key pattern in ${spath}"
                (( sensitive_found++ )) || true
            fi
            # Plaintext password fields in JSON
            if echo "$body" | grep -qiE '"password"\s*:\s*"[^"]{4,}"|"passwd"\s*:\s*"[^"]{4,}"'; then
                echo "  PII_PASSWORD: plaintext password field in response"
                log_warn "  Plaintext password in JSON response at ${spath}"
                (( sensitive_found++ )) || true
            fi
            _tier_pause
        done
        echo ""
        echo "Sensitive data findings: ${sensitive_found}"
        [[ "$sensitive_found" -gt 0 ]] && echo "SENSITIVE_DATA_EXPOSED: ${sensitive_found}"
    } | tee "$sensitive_out"
    log_ok "  Sensitive data: ${sensitive_out}"

    if grep -q "SENSITIVE_DATA_EXPOSED:" "$sensitive_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "Sensitive Data Exposure in API Responses" \
            "high" \
            "The API at ${base} returns sensitive data in responses — including email addresses, API key patterns, or plaintext password fields. This allows data harvesting by anyone who can reach these endpoints." \
            "Apply response filtering with explicit field allowlists. Mask or redact PII and credentials in all API responses. Enforce HTTPS end-to-end. Conduct a full data classification review for all API endpoints." \
            "ev-08-${host_safe}-013"
    fi
    _tier_pause

    # ── 11. Error Handling Verbosity ──────────────────────────────────────────
    local error_out="${dir}/app_errors_${port}_${ts}.txt"
    {
        echo "# Error Handling Verbosity — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        # Trigger error responses via malformed input
        local -a probe_specs=(
            "POST|/api/login|application/json|{bad json"
            "GET|/api/users?id=1'--|application/json|"
            "GET|/api/../etc/passwd|application/json|"
            "POST|/api/|application/json|{\"a\":\"$(printf '%0.sa' {1..500})\"}"
        )
        for spec in "${probe_specs[@]}"; do
            local pmethod ppath pctype pbody
            IFS='|' read -r pmethod ppath pctype pbody <<< "$spec"
            echo "--- Probe: ${pmethod} ${ppath}"
            local presp psc
            if [[ "$pmethod" == "POST" ]]; then
                presp=$(_curl -X POST -H "Content-Type: ${pctype}" -d "${pbody}" \
                    -w "\n__SC__%{http_code}" "${base}${ppath}")
            else
                presp=$(_curl -H "Accept: */*" -w "\n__SC__%{http_code}" "${base}${ppath}")
            fi
            psc=$(echo "$presp" | grep '__SC__' | sed 's/__SC__//' | tr -d '\r\n' || echo "000")
            local rbody; rbody=$(echo "$presp" | grep -v '__SC__' | head -c 1500)
            echo "  HTTP: ${psc}"
            echo "  Body:"
            echo "$rbody"
            echo ""
            if echo "$rbody" | grep -qiE \
                "Traceback|stack trace|at line [0-9]|Exception in|java\.lang\.|NullPointerException|\.py.*line|/home/|/var/www/|/usr/local/|DEBUG=True|SQLSTATE|ORA-[0-9]+|syntax error near|ProgrammingError|OperationalError|psycopg2|sqlite3\.OperationalError|django|flask|express|laravel"; then
                echo "  VERBOSE_ERROR: internal detail in error response"
                log_warn "  Verbose error at ${pmethod} ${ppath}"
                (( verbose_errors++ )) || true
            fi
            _tier_pause
        done
        echo ""
        echo "Verbose error findings: ${verbose_errors}"
        [[ "$verbose_errors" -gt 0 ]] && echo "VERBOSE_ERRORS_FOUND: ${verbose_errors}"
    } | tee "$error_out"
    log_ok "  Error handling: ${error_out}"

    if grep -q "VERBOSE_ERRORS_FOUND:" "$error_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "Verbose Error Messages Expose Internal Details" \
            "medium" \
            "Error responses from ${base} include stack traces, internal file paths, framework version information, or database error messages. This assists an attacker in fingerprinting the technology stack and crafting targeted exploits." \
            "Configure production error handlers to return generic messages only. Disable debug mode (DEBUG=False). Log detailed errors server-side only. Ensure all frameworks use production-grade error handling. Never echo back internal paths, SQL errors, or exception names in HTTP responses." \
            "ev-08-${host_safe}-014"
    fi
    _tier_pause

    # ── 12. Authorization / Broken Function Level Authorization (BFLA) ─────────
    local authz_out="${dir}/app_authz_${port}_${ts}.txt"
    {
        echo "# Authorization / BFLA Test — ${base}"
        echo "# Engagement: ${PROJECT_NAME}"
        echo "# Date/Time:  $(_now)"
        echo "---"
        # Probe admin and privileged paths without credentials
        local admin_paths=(
            "/admin" "/api/admin" "/api/v1/admin" "/api/admin/users"
            "/api/admin/settings" "/api/management" "/api/internal"
            "/api/system" "/actuator" "/actuator/env" "/actuator/mappings"
            "/api/debug" "/.well-known/admin"
        )
        echo "=== Unauthenticated admin endpoint probe ==="
        for apath in "${admin_paths[@]}"; do
            local asc
            asc=$(_curl -o /dev/null -w "%{http_code}" "${base}${apath}")
            asc="${asc:-000}"
            echo "  [${asc}] ${apath}"
            if [[ "$asc" != "404" && "$asc" != "000" && "$asc" != "401" && "$asc" != "403" && "$asc" != "301" && "$asc" != "302" ]]; then
                echo "  BFLA_CANDIDATE: ${apath} returned ${asc} without authentication"
                log_warn "  BFLA: admin path ${apath} → ${asc}"
                (( authz_issues++ )) || true
            fi
            _tier_pause
        done

        # HTTP verb tampering — try HEAD/OPTIONS on restricted paths
        echo ""
        echo "=== HTTP Verb Tampering ==="
        for apath in "/api/admin" "/api/admin/users"; do
            for verb in HEAD OPTIONS; do
                local vsc
                vsc=$(_curl -X "$verb" -o /dev/null -w "%{http_code}" "${base}${apath}")
                vsc="${vsc:-000}"
                echo "  [${verb} ${vsc}] ${apath}"
                if [[ "$vsc" == "200" || "$vsc" == "204" ]]; then
                    echo "  VERB_TAMPER_HIT: ${verb} ${apath} → ${vsc}"
                    log_warn "  Verb tamper: ${verb} ${apath} → ${vsc}"
                    (( authz_issues++ )) || true
                fi
            done
            _tier_pause
        done

        echo ""
        echo "Authorization issues: ${authz_issues}"
        [[ "$authz_issues" -gt 0 ]] && echo "AUTHZ_ISSUES_FOUND: ${authz_issues}"
    } | tee "$authz_out"
    log_ok "  Authorization: ${authz_out}"

    if grep -q "AUTHZ_ISSUES_FOUND:" "$authz_out" 2>/dev/null; then
        emit_finding "$host_safe" \
            "Broken Function Level Authorization (BFLA/OWASP API5)" \
            "high" \
            "Administrative or privileged API endpoints at ${base} are accessible without proper authentication or authorization. Unauthenticated access to admin paths, or HTTP verb tampering bypasses were confirmed, allowing unauthorized users access to restricted functions." \
            "Apply function-level authorization checks on all sensitive endpoints — never rely on obscurity alone. Implement RBAC at the API gateway or middleware level. Remove or disable debug/actuator endpoints in production. Conduct a complete endpoint authorization review against all defined roles." \
            "ev-08-${host_safe}-015"
    fi

    log_ok "Done: ${base} | findings so far: ${_FIND_CTR}"
    echo ""

    # Return per-target summary values via printed tokens for main() to parse
    printf "SUMMARY_ROW|%s|%s|%d|%d|%d|%d|%d|%d|%d|%d|%d\n" \
        "$ip" "$port" \
        "$_FIND_CTR" \
        "$schema_exposed" \
        "$auth_bypass_found" \
        "$(grep -c "RATE_LIMIT: MISSING" "${rate_out:-/dev/null}" 2>/dev/null || echo 0)" \
        "$(grep -c "CORS_MISCONFIG_HIGH:\|CORS_MISCONFIG_LOW:" "${cors_out:-/dev/null}" 2>/dev/null || echo 0)" \
        "${cookie_issues}" \
        "${sensitive_found}" \
        "${verbose_errors}" \
        "${authz_issues}"
}

# =============================================================================
# MRK:08_MAIN — MAIN entry point | main,entry,point | L617-720
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    echo -e "${GREEN}"
    echo "════════════════════════════════════════════════"
    echo "  08_app_api_review.sh"
    echo "  TechGuard."
    echo "  Project: ${PROJECT_NAME}"
    echo "  Tier:    ${TIER}"
    echo "  Mode:    $([ "$FAST_MODE" -eq 1 ] && echo "fast (headers+schema only)" || echo "full")"
    echo "════════════════════════════════════════════════"
    echo -e "${NC}"

    parse_db_conf

    # Trail: phase start
    local _08_t_start; _08_t_start=$(date +%s)
    trail_phase_start phase "08_app_api" project "${PROJECT_NAME:-}" mode "${MODE:-}" \
        session "${SESSION_TS:-$(_ts)}" ts "$(date -u +%FT%TZ)" \
        fast_mode "${FAST_MODE:-0}" 2>/dev/null || true

    # Initialise summary file
    mkdir -p "${EVIDENCE_BASE}/_sweep" working
    local summary_file="working/app_api_summary_${SESSION_TS}.md"
    cat > "$summary_file" << EOF
# App / API Review Summary — ${PROJECT_NAME}
*Generated: $(_now) | Session: ${SESSION_TS} | Tier: ${TIER}*

| host | tests | findings | schema | auth_bypass | rate_limit | cors | cookies | sensitive | errors | authz |
|------|-------|----------|--------|-------------|------------|------|---------|-----------|--------|-------|
EOF

    # Initialise findings JSONL
    : > "working/08_app_api_findings_${SESSION_TS}.jsonl"

    local targets; targets="$(assemble_targets)"
    if [[ -z "$targets" ]]; then
        log_err "No targets found. Use --from-db, --targets <file>, or --host <IP:PORT>"
        exit 1
    fi

    local count; count=$(echo "$targets" | grep -c '[0-9]' || echo 0)
    log "API review targets: ${count}"
    scope_confirm "$count"

    local total_findings=0

    while IFS= read -r target; do
        [[ -z "$target" ]] && continue
        local t_ip="${target%%:*}"
        t_ip="${t_ip%%/*}"
        local t_port="${target##*:}"

        # Capture the SUMMARY_ROW line from test_target
        local row_line
        row_line=$(test_target "$t_ip" "$t_port" 2>&1 | grep "^SUMMARY_ROW|" | tail -1 || true)

        if [[ -n "$row_line" ]]; then
            local r_host r_port r_finds r_schema r_auth r_rate r_cors r_cookie r_sensitive r_error r_authz
            IFS='|' read -r _ r_host r_port r_finds r_schema r_auth r_rate r_cors r_cookie r_sensitive r_error r_authz <<< "$row_line"
            (( total_findings += r_finds )) || true
            printf "| %s:%s | 12 | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n" \
                "$r_host" "$r_port" \
                "${r_finds:-0}" "${r_schema:-0}" "${r_auth:-0}" "${r_rate:-0}" \
                "${r_cors:-0}" "${r_cookie:-0}" "${r_sensitive:-0}" \
                "${r_error:-0}" "${r_authz:-0}" \
                >> "$summary_file"
        else
            # Fallback row if parsing failed
            printf "| %s:%s | 12 | ? | ? | ? | ? | ? | ? | ? | ? | ? |\n" "$t_ip" "$t_port" >> "$summary_file"
        fi
    done <<< "$targets"

    # Finalise summary
    {
        echo ""
        echo "## Totals"
        echo ""
        local jl_count
        jl_count=$(wc -l < "working/08_app_api_findings_${SESSION_TS}.jsonl" 2>/dev/null || echo 0)
        jl_count="${jl_count//[[:space:]]/}"
        echo "Total findings written to JSONL: **${jl_count}**"
        echo ""
        echo "## Evidence Files"
        find "${EVIDENCE_BASE}" -maxdepth 2 \( \
             -name "app_methods_*" -o \
             -name "app_schema_*" -o \
             -name "app_auth_*" -o \
             -name "app_rate_limit_*" -o \
             -name "app_cors_*" -o \
             -name "app_mass_assign_*" -o \
             -name "app_idor_*" -o \
             -name "app_api_headers_*" -o \
             -name "app_cookies_*" -o \
             -name "app_sensitive_*" -o \
             -name "app_errors_*" -o \
             -name "app_authz_*" \) 2>/dev/null | \
             sort | sed 's/^/- /'
        echo ""
        echo "---"
        echo "*08_app_api_review.sh | TechGuard.*"
    } >> "$summary_file"

    # Trail: phase end
    local _08_t_end; _08_t_end=$(date +%s)
    trail_phase_end phase "08_app_api" project "${PROJECT_NAME:-}" \
        session "${SESSION_TS:-}" \
        duration_sec "$((_08_t_end - _08_t_start))" \
        findings_count "${total_findings}" \
        ts "$(date -u +%FT%TZ)" 2>/dev/null || true

    log_ok "App / API review complete"
    log_ok "Findings JSONL: working/08_app_api_findings_${SESSION_TS}.jsonl"
    log_ok "Summary:        ${summary_file}"
    log_ok "Per-host output: ${EVIDENCE_BASE}/<IP>/"
}

main

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
