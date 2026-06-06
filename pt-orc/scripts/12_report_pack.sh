#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ./ORC-INDEX.md

# MRK:12_NAV_TOC — Section index | nav,toc,index | L5-22
# - MRK:12_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L23-90 | ⚠ no-insert-before; propose-before-edit; read-toc-first
# - MRK:12_LOG — COLOURS AND LOGGING | log,colours,logging | L91-120 | ⚠ no-insert-before
# - MRK:12_ARGS — ARGUMENT PARSING | args,argument,parsing | L121-155 | ⚠ no-insert-before
# - MRK:12_VALIDATE — VALIDATION | validate,project,id,required | L156-177 | ⚠ no-insert-before
# - MRK:12_SCOPE — BUILD SCOPE JSON | scope,targets,window,json | L178-245 | ⚠ no-insert-before; read-toc-first
# - MRK:12_EVIDENCE — BUILD EVIDENCE MANIFEST | evidence,manifest,walk,sha256 | L246-360 | ⚠ no-insert-before; read-toc-first
# - MRK:12_FINDINGS — COLLECT FINDINGS | findings,pattern,detect,jsonl | L361-580 | ⚠ no-insert-before; read-toc-first
# - MRK:12_BUNDLE — BUILD REPORT BUNDLE | bundle,residual,risk,counts | L581-635 | ⚠ no-insert-before; read-toc-first
# - MRK:12_WRITE — WRITE OUTPUT FILES | write,output,export,dir | L636-710 | ⚠ no-insert-before; read-toc-first
# - MRK:12_MAIN — MAIN entry point | main,entry,point | L711-760 | ⚠ no-insert-before; read-toc-first
# NAV-LEN: 10 entries | Integrity-hash: pending | Last-indexed: 2026-06-06T00:00:00Z

# =============================================================================
# 12_report_pack.sh — TechGuard. [VAPT-Enhanced v1.0 — 2026-06-06]
# Report Pack — reads all scan evidence and produces 4 files for TG Audit Orchestrator
#
# Output files (strict Pydantic validation on import):
#   scope.json            — engagement scope, targets, window, RoE
#   evidence_manifest.jsonl — one evidence record per file (sha256, phase, summary)
#   findings.jsonl        — deduplicated, severity-ranked findings
#   report_bundle.json    — counts, residual risk, metadata
# =============================================================================
# USAGE:
#   ./12_report_pack.sh [OPTIONS]
#
# OPTIONS:
#   --project-id <uuid>   Override ORCHESTRATOR_PROJECT_ID from conf (required if not in conf)
#   --profile <profile>   Override ENGAGEMENT_PROFILE (external|internal|web|api|ai_llm|cloud|ad|hybrid|retest)
#   --output-dir <dir>    Directory to create run/ output under (default: ${SCRIPT_DIR}/run)
#   --retest              Set retest_status to "pending" in report_bundle (for retest runs)
#   --dry-run             Compute everything but do not write output files
#
# REQUIRES: jq, sha256sum
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# MRK:12_CONF — ENGAGEMENT CONFIGURATION | conf,engagement,configuration,edit,pt | L23-90
# NAV-RULE: no-insert-before; propose-before-edit; read-toc-first
# =============================================================================

# Load shared engagement config
# shellcheck source=pt-orc.conf
[[ -f "${SCRIPT_DIR}/pt-orc.conf" ]] && source "${SCRIPT_DIR}/pt-orc.conf" \
    || echo "[WARN] pt-orc.conf not found in ${SCRIPT_DIR} — defaults used"

# Shared helpers (logging, trail/notes writer)
# shellcheck source=orc-common-lib.sh
[[ -f "${SCRIPT_DIR}/orc-common-lib.sh" ]] && source "${SCRIPT_DIR}/orc-common-lib.sh" \
    || echo "[WARN] orc-common-lib.sh not found — trail writes disabled"

EVIDENCE_BASE="${EVIDENCE_BASE:-${SCRIPT_DIR}/evidence}"
[[ "$EVIDENCE_BASE" != /* ]] && EVIDENCE_BASE="${SCRIPT_DIR}/evidence"

# ---------------------------------------------------------------------------
# Orchestrator integration variables — read from conf, override via args
# ---------------------------------------------------------------------------
ORCHESTRATOR_PROJECT_ID="${ORCHESTRATOR_PROJECT_ID:-}"
ENGAGEMENT_PROFILE="${ENGAGEMENT_PROFILE:-external}"
TESTING_DEPTH="${TESTING_DEPTH:-standard}"
AUTH_LEVEL="${AUTH_LEVEL:-none}"
RULES_OF_ENGAGEMENT="${RULES_OF_ENGAGEMENT:-No DoS. Testing window business hours only.}"
WINDOW_START="${WINDOW_START:-}"
WINDOW_END="${WINDOW_END:-}"

OUTPUT_DIR="${SCRIPT_DIR}/run"
DRY_RUN=0
RETEST=0

# =============================================================================
# MRK:12_LOG — COLOURS AND LOGGING | log,colours,logging | L91-120
# NAV-RULE: no-insert-before
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

_ts()  { date +'%Y%m%d_%H%M%S'; }
_now() { date +'%Y-%m-%d %H:%M:%S'; }

SESSION_TS="$(_ts)"

WORKING_DIR="${SCAN_WORKING_DIR:-${SCRIPT_DIR}/working}"; mkdir -p "$WORKING_DIR"
LOG_FILE="${WORKING_DIR}/report_pack_${SESSION_TS}.log"

log()      { local m="[$(_now)] $1";            echo -e "${BLUE}${m}${NC}" >&2;       echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_ok()   { local m="[$(_now)] [OK] $1";       echo -e "${GREEN}${m}${NC}" >&2;      echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_warn() { local m="[$(_now)] [WARN] $1";     echo -e "${YELLOW}${m}${NC}" >&2;     echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_err()  { local m="[$(_now)] [ERR] $1";      echo -e "${RED}${m}${NC}" >&2;        echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_info() { local m="[$(_now)]   $1";          echo -e "${CYAN}${m}${NC}" >&2;       echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }
log_find() { local m="[$(_now)] FINDING: $1";   echo -e "${BOLD}${RED}${m}${NC}" >&2; echo "${m}" >> "$LOG_FILE" 2>/dev/null || true; }

# =============================================================================
# MRK:12_ARGS — ARGUMENT PARSING | args,argument,parsing | L121-155
# NAV-RULE: no-insert-before
# =============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-id)
            [[ -z "${2:-}" ]] && { echo "[ERR] --project-id requires a value"; exit 1; }
            ORCHESTRATOR_PROJECT_ID="$2"; shift 2 ;;
        --profile)
            [[ -z "${2:-}" ]] && { echo "[ERR] --profile requires a value"; exit 1; }
            ENGAGEMENT_PROFILE="$2"; shift 2 ;;
        --output-dir)
            [[ -z "${2:-}" ]] && { echo "[ERR] --output-dir requires a value"; exit 1; }
            OUTPUT_DIR="$2"; shift 2 ;;
        --retest)
            RETEST=1; shift ;;
        --dry-run)
            DRY_RUN=1; shift ;;
        *)
            log_err "Unknown argument: $1"; exit 1 ;;
    esac
done

# =============================================================================
# MRK:12_VALIDATE — VALIDATION | validate,project,id,required | L156-177
# NAV-RULE: no-insert-before
# =============================================================================

if [[ -z "$ORCHESTRATOR_PROJECT_ID" ]]; then
    echo ""
    echo -e "${RED}${BOLD}[ERROR] ORCHESTRATOR_PROJECT_ID is not set.${NC}"
    echo ""
    echo "  Set it one of two ways:"
    echo "    1. Add to pt-orc.conf:   ORCHESTRATOR_PROJECT_ID=\"<uuid-from-orchestrator>\""
    echo "    2. Pass as argument:      --project-id <uuid>"
    echo ""
    echo "  The UUID is assigned when you create the project in the TG Audit Orchestrator."
    echo "  Example: ./12_report_pack.sh --project-id a1b2c3d4-1234-5678-abcd-ef0123456789"
    echo ""
    exit 1
fi

if ! command -v jq &>/dev/null; then
    log_err "jq is required but not found. Install: apt-get install -y jq"
    exit 1
fi

log "12_report_pack.sh — TechGuard. | Project: ${ORCHESTRATOR_PROJECT_ID}"
log "Evidence base: ${EVIDENCE_BASE}"
log "Output dir:    ${OUTPUT_DIR}"
[[ "$DRY_RUN" -eq 1 ]] && log_warn "DRY-RUN mode — no output files will be written"

# =============================================================================
# MRK:12_SCOPE — BUILD SCOPE JSON | scope,targets,window,json | L178-245
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

build_scope_json() {
    log "Building scope.json ..."

    # Assemble raw target list from all three sources then deduplicate + sort
    local -a raw_targets=()

    # Source 1: targets.txt (IPs produced by 01_dns_recon)
    local tgt_file="${SCRIPT_DIR}/targets.txt"
    if [[ -f "$tgt_file" ]]; then
        while IFS= read -r line; do
            # Strip comments and blank lines
            line="${line%%#*}"; line="${line// /}"
            [[ -n "$line" ]] && raw_targets+=("$line")
        done < "$tgt_file"
        log_info "  targets.txt: ${#raw_targets[@]} entries"
    else
        log_warn "  targets.txt not found — skipping (run 01_dns_recon first)"
    fi

    # Source 2: TARGET_DOMAINS from conf
    for d in ${TARGET_DOMAINS:-}; do
        [[ -n "$d" ]] && raw_targets+=("$d")
    done

    # Source 3: TARGET_IPS from conf
    for ip in ${TARGET_IPS:-}; do
        [[ -n "$ip" ]] && raw_targets+=("$ip")
    done

    # Deduplicate + sort into a clean newline-separated list
    local targets_sorted
    targets_sorted=$(printf '%s\n' "${raw_targets[@]}" | sort -u | grep -v '^$' || true)
    local target_count
    target_count=$(echo "$targets_sorted" | grep -c '.' 2>/dev/null || echo 0)
    log_ok "  Targets consolidated: ${target_count} unique entries"

    # Window: use conf values; fall back to today ± 14 days
    local today; today=$(date +'%Y-%m-%d')
    local ws="${WINDOW_START:-}"
    local we="${WINDOW_END:-}"
    if [[ -z "$ws" ]]; then
        ws=$(date -d "today - 14 days" +'%Y-%m-%d' 2>/dev/null || date -v-14d +'%Y-%m-%d' 2>/dev/null || echo "$today")
        log_warn "  WINDOW_START not set — using ${ws} (today-14d)"
    fi
    if [[ -z "$we" ]]; then
        we=$(date -d "today + 14 days" +'%Y-%m-%d' 2>/dev/null || date -v+14d +'%Y-%m-%d' 2>/dev/null || echo "$today")
        log_warn "  WINDOW_END not set — using ${we} (today+14d)"
    fi

    # Build JSON array of targets using jq
    local targets_json
    targets_json=$(echo "$targets_sorted" | jq -R . | jq -s .)

    SCOPE_JSON=$(jq -n \
        --arg project_ref    "$ORCHESTRATOR_PROJECT_ID" \
        --arg eng_profile    "$ENGAGEMENT_PROFILE" \
        --arg testing_depth  "$TESTING_DEPTH" \
        --arg auth_level     "$AUTH_LEVEL" \
        --argjson targets    "$targets_json" \
        --arg roe            "$RULES_OF_ENGAGEMENT" \
        --arg ws             "$ws" \
        --arg we             "$we" \
        '{
            project_ref:        $project_ref,
            engagement_profile: $eng_profile,
            testing_depth:      $testing_depth,
            auth_level:         $auth_level,
            targets:            $targets,
            rules_of_engagement: $roe,
            window: { start: $ws, end: $we }
        }')

    SCOPE_TARGET_COUNT="$target_count"
    log_ok "scope.json built — ${target_count} targets, window ${ws} → ${we}"
}

# =============================================================================
# MRK:12_EVIDENCE — BUILD EVIDENCE MANIFEST | evidence,manifest,walk,sha256 | L246-360
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

# Global maps used by MRK:12_FINDINGS to link files to ev-NNN ids
declare -A EV_ID_BY_PATH    # absolute_path -> ev-NNN
declare -A EV_ID_BY_BASE    # basename -> ev-NNN (last writer wins; sufficient for matching)

build_evidence_manifest() {
    log "Building evidence_manifest.jsonl ..."

    EVIDENCE_LINES=()   # array of JSONL lines
    local ev_count=0

    # Walk evidence base recursively; process regular files only
    while IFS= read -r -d '' fpath; do
        local fname; fname="$(basename "$fpath")"
        local fdir;  fdir="$(dirname "$fpath")"

        # Skip: log files
        [[ "$fname" == *.log ]] && continue
        # Skip: MSF resource files
        [[ "$fname" == *.rc  ]] && continue
        # Skip: files inside _msf/ directory
        [[ "$fdir" == */_msf* || "$fdir" == */_msf ]] && continue
        # Skip: summary markdown in working/
        [[ "$fdir" == */working && "$fname" == *.md ]] && continue
        # Skip: zero-size files
        [[ ! -s "$fpath" ]] && continue

        # Phase detection from path components
        local phase="05_web"   # catchall default
        if [[ "$fdir" == *_dns* || "$fname" == *_dns_* ]]; then
            phase="01_dns"
        elif [[ "$fname" == ip_analysis* ]]; then
            phase="02_ip"
        elif [[ "$fname" == nmap_* || ( "$fdir" == *_sweep* && "$fname" == *comp_scan* ) ]]; then
            phase="03_network"
        elif [[ "$fname" == tls_* || "$fname" == testssl_* || "$fname" == cert_* ]]; then
            phase="04_tls"
        elif [[ "$fname" == headers_* || "$fname" == sec_headers_* || \
                "$fname" == gobuster_* || "$fname" == nikto_* || \
                "$fname" == whatweb_* || "$fname" == sensitive_* || \
                "$fname" == cors_*    || "$fname" == graphql_* || \
                "$fname" == api_endpoints_* ]]; then
            phase="05_web"
        elif [[ "$fname" == wp_* ]]; then
            phase="06_wordpress"
        elif [[ "$fname" == service_* ]]; then
            phase="07_service"
        elif [[ "$fname" == app_* ]]; then
            phase="08_app_api"
        elif [[ "$fname" == llm_* || "$fname" == ai_* ]]; then
            phase="09_ai_llm"
        fi

        # Compute sha256
        local sha256
        sha256=$(sha256sum "$fpath" 2>/dev/null | awk '{print $1}') || { log_warn "  sha256 failed: $fpath"; continue; }

        # Increment counter and build ID
        (( ev_count++ )) || true
        local ev_id; ev_id="ev-$(printf '%03d' "$ev_count")"

        # Generate a human-readable summary from filename
        # Strip leading timestamp-like suffixes (YYYYMMDD_HHMMSS) and underscores
        local summary; summary="$fname"
        # Remove extension
        summary="${summary%.*}"
        # Strip trailing timestamp _YYYYMMDD_HHMMSS
        summary=$(echo "$summary" | sed 's/_[0-9]\{8\}_[0-9]\{6\}$//')
        # Replace underscores with spaces
        summary="${summary//_/ }"

        # Build JSONL record
        local ev_line
        ev_line=$(jq -n \
            --arg id      "$ev_id" \
            --arg phase   "$phase" \
            --arg srcfile "$fname" \
            --arg sha256  "$sha256" \
            --arg summary "$summary" \
            '{"id":$id,"phase":$phase,"source_file":$srcfile,"sha256":$sha256,"summary":$summary}')

        EVIDENCE_LINES+=("$ev_line")

        # Register in maps for findings linkage
        EV_ID_BY_PATH["$fpath"]="$ev_id"
        EV_ID_BY_BASE["$fname"]="$ev_id"

        log_info "  ${ev_id}  [${phase}]  ${fname}"

    done < <(find "$EVIDENCE_BASE" -type f -print0 2>/dev/null | sort -z)

    EVIDENCE_COUNT="${#EVIDENCE_LINES[@]}"
    log_ok "Evidence manifest built — ${EVIDENCE_COUNT} items"
}

# =============================================================================
# MRK:12_FINDINGS — COLLECT FINDINGS | findings,pattern,detect,jsonl | L361-580
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

# Global arrays populated by this section
FINDINGS_LINES=()
FINDING_SEVERITIES=()   # parallel array — severity string per finding for residual calc

_make_finding() {
    # _make_finding <id> <title> <severity> <phase> <ev_ids_json> <description> <recommendation> [retest_status] [residual_risk]
    local fid="$1" title="$2" sev="$3" phase="$4" ev_ids="$5" desc="$6" rec="$7"
    local retest="${8:-n/a}" residual="${9:-}"
    jq -n \
        --arg id          "$fid" \
        --arg title       "$title" \
        --arg severity    "$sev" \
        --arg phase       "$phase" \
        --argjson evidence_ids "$ev_ids" \
        --arg description "$desc" \
        --arg recommendation "$rec" \
        --arg retest_status  "$retest" \
        --arg residual_risk  "$residual" \
        '{"id":$id,"title":$title,"severity":$severity,"phase":$phase,"evidence_ids":$evidence_ids,"description":$description,"recommendation":$recommendation,"retest_status":$retest_status,"residual_risk":$residual_risk}'
}

_ev_ids_for_file() {
    # Returns a JSON array of ev-NNN IDs for a given absolute path (or empty array)
    local fpath="$1"
    local fname; fname="$(basename "$fpath")"
    local ev_id="${EV_ID_BY_PATH[$fpath]:-${EV_ID_BY_BASE[$fname]:-}}"
    if [[ -n "$ev_id" ]]; then
        echo "[\"${ev_id}\"]"
    else
        echo "[]"
    fi
}

collect_findings() {
    log "Collecting findings ..."
    local f_count=0

    # -------------------------------------------------------------------------
    # Step 1: Read pre-generated findings from phase scripts (08, 09)
    # -------------------------------------------------------------------------
    log "  Step 1: pre-generated findings from phase scripts ..."

    local -a pregen_files=()
    while IFS= read -r -d '' f; do
        pregen_files+=("$f")
    done < <(find "${WORKING_DIR}" -maxdepth 1 \
        \( -name "08_app_api_findings_*.jsonl" -o -name "09_ai_llm_findings_*.jsonl" \) \
        -type f -print0 2>/dev/null | sort -z)

    for pf in "${pregen_files[@]:-}"; do
        [[ -z "$pf" || ! -f "$pf" ]] && continue
        log_info "  Loading pre-generated findings: $(basename "$pf")"
        while IFS= read -r fline; do
            [[ -z "$fline" ]] && continue
            (( f_count++ )) || true
            local new_id; new_id="f-$(printf '%03d' "$f_count")"
            local sev; sev=$(echo "$fline" | jq -r '.severity // "info"')

            # Remap evidence_ids: replace any source_file-based references with ev-NNN
            # Strategy: for each source_file name in the finding's evidence_ids field,
            # look up our manifest map; fall back to the original id if not found.
            local remapped_ev
            remapped_ev=$(echo "$fline" | jq -r '.evidence_ids // [] | @json')
            # Try to rebuild from source_file field if present
            local src_file; src_file=$(echo "$fline" | jq -r '.source_file // empty')
            if [[ -n "$src_file" ]]; then
                local mapped="${EV_ID_BY_BASE[$src_file]:-}"
                if [[ -n "$mapped" ]]; then
                    remapped_ev="[\"${mapped}\"]"
                fi
            fi

            local relined
            relined=$(echo "$fline" | jq \
                --arg new_id "$new_id" \
                --argjson ev_ids "$remapped_ev" \
                '.id = $new_id | .evidence_ids = $ev_ids')
            FINDINGS_LINES+=("$relined")
            FINDING_SEVERITIES+=("$sev")
            log_find "Pre-generated [${sev}] $(echo "$fline" | jq -r '.title // "unknown"')"
        done < "$pf"
    done
    log_info "  Pre-generated findings loaded: ${f_count}"

    # -------------------------------------------------------------------------
    # Step 2: Pattern-based finding detection from evidence files
    # -------------------------------------------------------------------------
    log "  Step 2: pattern-based detection across evidence files ..."

    while IFS= read -r -d '' fpath; do
        local fname; fname="$(basename "$fpath")"
        local fdir;  fdir="$(dirname "$fpath")"

        # Skip files that were excluded from the manifest (same rules)
        [[ "$fname" == *.log ]] && continue
        [[ "$fname" == *.rc  ]] && continue
        [[ "$fdir"  == */_msf* ]] && continue
        [[ "$fdir"  == */working && "$fname" == *.md ]] && continue
        [[ ! -s "$fpath" ]] && continue

        local ev_ids; ev_ids="$(_ev_ids_for_file "$fpath")"

        # ---- 04_tls: TLS 1.0/1.1 legacy files ----
        if [[ "$fname" == tls_legacy_* ]]; then
            if grep -qiE "TLSv1 |TLSv1\.1" "$fpath" 2>/dev/null && \
               grep -qiE "ENABLED|YES|Offered|supported" "$fpath" 2>/dev/null; then
                (( f_count++ )) || true
                local fid; fid="f-$(printf '%03d' "$f_count")"
                local rec="Disable TLS 1.0 and TLS 1.1; enforce TLS 1.2+."
                local desc="Legacy TLS protocol versions (TLSv1.0 and/or TLSv1.1) are active on the target. These versions are deprecated and vulnerable to known attacks (POODLE, BEAST). Evidence: ${fname}"
                FINDINGS_LINES+=("$(_make_finding "$fid" "TLS 1.0/1.1 still active" "medium" "04_tls" "$ev_ids" "$desc" "$rec")")
                FINDING_SEVERITIES+=("medium")
                log_find "medium [04_tls] TLS 1.0/1.1 still active — ${fname}"
            fi
        fi

        # ---- 04_tls: testssl JSON HIGH/CRITICAL findings ----
        if [[ "$fname" == testssl_*.json ]]; then
            local testssl_results
            testssl_results=$(jq -r '.scanResult[]?.findings[]? | select(.severity == "HIGH" or .severity == "CRITICAL") | .severity + "|||" + .id + ": " + .finding' "$fpath" 2>/dev/null || true)
            if [[ -n "$testssl_results" ]]; then
                while IFS= read -r tline; do
                    [[ -z "$tline" ]] && continue
                    local tsev="${tline%%|||*}"
                    local ttext="${tline#*|||}"
                    local normalized_sev="high"
                    [[ "$tsev" == "CRITICAL" ]] && normalized_sev="critical"
                    (( f_count++ )) || true
                    local fid; fid="f-$(printf '%03d' "$f_count")"
                    local desc="testssl.sh reported a ${tsev} severity finding: ${ttext}"
                    local rec="Remediate per testssl recommendation."
                    FINDINGS_LINES+=("$(_make_finding "$fid" "testssl: ${ttext:0:80}" "$normalized_sev" "04_tls" "$ev_ids" "$desc" "$rec")")
                    FINDING_SEVERITIES+=("$normalized_sev")
                    log_find "${normalized_sev} [04_tls] testssl: ${ttext:0:60}"
                done <<< "$testssl_results"
            fi
        fi

        # ---- 05_web: security headers missing ----
        if [[ "$fname" == sec_headers_* || "$fname" == headers_* ]]; then
            local missing_count
            missing_count=$(grep -ciE "MISSING|NOT PRESENT|not set|absent" "$fpath" 2>/dev/null || echo 0)
            if [[ "$missing_count" -ge 3 ]]; then
                (( f_count++ )) || true
                local fid; fid="f-$(printf '%03d' "$f_count")"
                local desc="Security header analysis identified ${missing_count} missing HTTP security headers on the target. Missing headers increase exposure to clickjacking, MIME sniffing, and XSS attacks. Evidence: ${fname}"
                local rec="Add X-Content-Type-Options, X-Frame-Options, CSP, HSTS, X-XSS-Protection headers."
                FINDINGS_LINES+=("$(_make_finding "$fid" "Multiple security headers missing" "medium" "05_web" "$ev_ids" "$desc" "$rec")")
                FINDING_SEVERITIES+=("medium")
                log_find "medium [05_web] Multiple security headers missing (${missing_count}) — ${fname}"
            fi
        fi

        # ---- 05_web: sensitive files / directories exposed ----
        if [[ "$fname" == sensitive_files_* || "$fname" == sensitive_* ]]; then
            if grep -qE "HTTP/1\.[01] 200|HTTP/2 200" "$fpath" 2>/dev/null; then
                (( f_count++ )) || true
                local fid; fid="f-$(printf '%03d' "$f_count")"
                local hits; hits=$(grep -cE "HTTP/1\.[01] 200|HTTP/2 200" "$fpath" 2>/dev/null || echo 1)
                local desc="Sensitive file or directory probing returned HTTP 200 responses (${hits} hit(s)). Exposed backup files, configuration, or version control metadata can disclose credentials and source code. Evidence: ${fname}"
                local rec="Block access to backup files, .git, .env, and config directories in webserver config."
                FINDINGS_LINES+=("$(_make_finding "$fid" "Sensitive file or directory exposed" "high" "05_web" "$ev_ids" "$desc" "$rec")")
                FINDING_SEVERITIES+=("high")
                log_find "high [05_web] Sensitive file or directory exposed — ${fname}"
            fi
        fi

        # ---- 01_dns: subdomain takeover candidates ----
        if [[ "$fname" == takeover_candidates_* ]]; then
            local line_count; line_count=$(wc -l < "$fpath" 2>/dev/null | tr -d ' ' || echo 0)
            if [[ "$line_count" -gt 0 ]]; then
                (( f_count++ )) || true
                local fid; fid="f-$(printf '%03d' "$f_count")"
                local context; context=$(head -5 "$fpath" 2>/dev/null | tr '\n' '; ')
                local desc="One or more subdomains appear to be candidates for subdomain takeover. These subdomains resolve to external services that are no longer claimed by the organisation. Context (first 5): ${context}"
                local rec="Remove dangling DNS records or reclaim the third-party service."
                FINDINGS_LINES+=("$(_make_finding "$fid" "Subdomain takeover candidate detected" "high" "01_dns" "$ev_ids" "$desc" "$rec")")
                FINDING_SEVERITIES+=("high")
                log_find "high [01_dns] Subdomain takeover candidate (${line_count} entries) — ${fname}"
            fi
        fi

        # ---- 05_web / 06_wordpress: nikto findings ----
        if [[ "$fname" == nikto_*.txt ]]; then
            # Extract meaningful nikto output lines
            local nikto_hits
            nikto_hits=$(grep -E "^\+ (OSVDB|/|Server)" "$fpath" 2>/dev/null | head -10 || true)
            if [[ -n "$nikto_hits" ]]; then
                (( f_count++ )) || true
                local fid; fid="f-$(printf '%03d' "$f_count")"
                # Derive host:port from filename (nikto_<host>_<port>_*.txt)
                local hostport; hostport=$(echo "$fname" | sed 's/^nikto_//' | sed 's/_[0-9]\{8\}_[0-9]\{6\}\.txt$//' | tr '_' ':')
                local desc_body; desc_body=$(echo "$nikto_hits" | tr '\n' '|')
                local desc="Nikto scanner identified configuration weaknesses on ${hostport}. Findings (top 10): ${desc_body}"
                local rec="Review individual Nikto findings and remediate configuration weaknesses."
                local nikto_phase="05_web"
                [[ "$fdir" == *wp* || "$fname" == *wp_* ]] && nikto_phase="06_wordpress"
                FINDINGS_LINES+=("$(_make_finding "$fid" "Nikto scanner findings on ${hostport}" "low" "$nikto_phase" "$ev_ids" "$desc" "$rec")")
                FINDING_SEVERITIES+=("low")
                log_find "low [${nikto_phase}] Nikto scanner findings — ${fname}"
            fi
        fi

        # ---- 08_app_api: auth bypass candidates ----
        if [[ "$fname" == app_auth_* ]]; then
            local bypass_count; bypass_count=$(grep -c "AUTH_BYPASS_CANDIDATE" "$fpath" 2>/dev/null || echo 0)
            if [[ "$bypass_count" -gt 0 ]]; then
                (( f_count++ )) || true
                local fid; fid="f-$(printf '%03d' "$f_count")"
                local desc="API authentication bypass candidates detected (${bypass_count} endpoint(s)). These endpoints appear to return successful responses without valid authentication tokens. Evidence: ${fname}"
                local rec="Enforce authentication on all API endpoints. Implement consistent authorization checks server-side. Review access control design."
                FINDINGS_LINES+=("$(_make_finding "$fid" "API endpoint accessible without authentication" "high" "08_app_api" "$ev_ids" "$desc" "$rec")")
                FINDING_SEVERITIES+=("high")
                log_find "high [08_app_api] API auth bypass candidates (${bypass_count}) — ${fname}"
            fi
        fi

        # ---- 08_app_api: missing rate limiting ----
        if [[ "$fname" == app_rate_limit_* ]]; then
            if grep -q "RATE_LIMIT: MISSING" "$fpath" 2>/dev/null; then
                local rl_count; rl_count=$(grep -c "RATE_LIMIT: MISSING" "$fpath" 2>/dev/null || echo 1)
                (( f_count++ )) || true
                local fid; fid="f-$(printf '%03d' "$f_count")"
                local desc="Rate limiting is absent on ${rl_count} API endpoint(s). Without rate limiting, endpoints are vulnerable to credential stuffing, enumeration, and denial-of-service via request flooding. Evidence: ${fname}"
                local rec="Implement rate limiting on all API endpoints. Consider token-bucket or sliding-window algorithms. Return HTTP 429 with Retry-After header."
                FINDINGS_LINES+=("$(_make_finding "$fid" "No rate limiting on API endpoints" "medium" "08_app_api" "$ev_ids" "$desc" "$rec")")
                FINDING_SEVERITIES+=("medium")
                log_find "medium [08_app_api] No rate limiting on API endpoints — ${fname}"
            fi
        fi

        # ---- 09_ai_llm: prompt injection ----
        if [[ "$fname" == llm_injection_* || "$fname" == ai_injection_* ]]; then
            if grep -qE "INJECTION_SUCCESS|INJECTION: SUCCESS" "$fpath" 2>/dev/null; then
                (( f_count++ )) || true
                local fid; fid="f-$(printf '%03d' "$f_count")"
                local desc="Prompt injection was confirmed against the AI/LLM endpoint. The model accepted injected instructions that overrode its system prompt or changed its output behaviour. This can lead to data exfiltration, safety bypass, and indirect command execution. Evidence: ${fname}"
                local rec="Implement robust input sanitisation and output validation for all LLM integrations. Use a separate instruction channel from user data. Apply content filtering and monitoring."
                FINDINGS_LINES+=("$(_make_finding "$fid" "Prompt injection vulnerability confirmed" "high" "09_ai_llm" "$ev_ids" "$desc" "$rec")")
                FINDING_SEVERITIES+=("high")
                log_find "high [09_ai_llm] Prompt injection confirmed — ${fname}"
            fi
        fi

    done < <(find "$EVIDENCE_BASE" -type f -print0 2>/dev/null | sort -z)

    FINDINGS_COUNT="${#FINDINGS_LINES[@]}"
    log_ok "Findings collected — ${FINDINGS_COUNT} total"
}

# =============================================================================
# MRK:12_BUNDLE — BUILD REPORT BUNDLE | bundle,residual,risk,counts | L581-635
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

build_report_bundle() {
    log "Building report_bundle.json ..."

    # Compute residual risk from highest finding severity present
    local has_critical=0 has_high=0 has_medium=0 has_low=0 has_info=0
    local cnt_critical=0 cnt_high=0 cnt_medium=0 cnt_low=0 cnt_info=0

    for sev in "${FINDING_SEVERITIES[@]:-}"; do
        case "$sev" in
            critical) (( has_critical++ )) || true; (( cnt_critical++ )) || true ;;
            high)     (( has_high++     )) || true; (( cnt_high++     )) || true ;;
            medium)   (( has_medium++   )) || true; (( cnt_medium++   )) || true ;;
            low)      (( has_low++      )) || true; (( cnt_low++      )) || true ;;
            info)     (( has_info++     )) || true; (( cnt_info++     )) || true ;;
        esac
    done

    local residual="None identified"
    if [[ "$has_critical" -gt 0 ]]; then
        residual="Critical — immediate remediation required"
    elif [[ "$has_high" -gt 0 ]]; then
        residual="High — remediation required before closure"
    elif [[ "$has_medium" -gt 0 ]]; then
        residual="Medium — remediation recommended"
    elif [[ "$has_low" -gt 0 || "$has_info" -gt 0 ]]; then
        residual="Low — advisory items only"
    fi

    local retest_val="n/a"
    [[ "$RETEST" -eq 1 ]] && retest_val="pending"

    REPORT_BUNDLE=$(jq -n \
        --arg project_ref    "$ORCHESTRATOR_PROJECT_ID" \
        --arg profile        "$ENGAGEMENT_PROFILE" \
        --arg retest_status  "$retest_val" \
        --arg residual_risk  "$residual" \
        --argjson findings   "$FINDINGS_COUNT" \
        --argjson evidence   "$EVIDENCE_COUNT" \
        '{
            project_ref:    $project_ref,
            profile:        $profile,
            retest_status:  $retest_status,
            residual_risk:  $residual_risk,
            counts: {
                findings: $findings,
                evidence: $evidence
            }
        }')

    RESIDUAL_RISK="$residual"
    SEVERITY_COUNTS="C:${cnt_critical} H:${cnt_high} M:${cnt_medium} L:${cnt_low} I:${cnt_info}"
    log_ok "report_bundle.json built — residual: ${residual}"
}

# =============================================================================
# MRK:12_WRITE — WRITE OUTPUT FILES | write,output,export,dir | L636-710
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

write_output() {
    local run_dir="${OUTPUT_DIR}/${ORCHESTRATOR_PROJECT_ID}_${SESSION_TS}"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log_warn "DRY-RUN: would write to ${run_dir}/"
        log_warn "DRY-RUN: scope.json — ${SCOPE_TARGET_COUNT} targets"
        log_warn "DRY-RUN: evidence_manifest.jsonl — ${EVIDENCE_COUNT} items"
        log_warn "DRY-RUN: findings.jsonl — ${FINDINGS_COUNT} findings"
        log_warn "DRY-RUN: report_bundle.json — residual: ${RESIDUAL_RISK}"
        RUN_DIR_DISPLAY="${run_dir}/"
        return 0
    fi

    mkdir -p "$run_dir"
    log "Writing output to ${run_dir}/ ..."

    # scope.json
    echo "$SCOPE_JSON" > "${run_dir}/scope.json"
    log_ok "  scope.json written"

    # evidence_manifest.jsonl
    : > "${run_dir}/evidence_manifest.jsonl"
    for line in "${EVIDENCE_LINES[@]:-}"; do
        echo "$line" >> "${run_dir}/evidence_manifest.jsonl"
    done
    log_ok "  evidence_manifest.jsonl written (${EVIDENCE_COUNT} items)"

    # findings.jsonl
    : > "${run_dir}/findings.jsonl"
    for line in "${FINDINGS_LINES[@]:-}"; do
        echo "$line" >> "${run_dir}/findings.jsonl"
    done
    log_ok "  findings.jsonl written (${FINDINGS_COUNT} findings)"

    # report_bundle.json
    echo "$REPORT_BUNDLE" > "${run_dir}/report_bundle.json"
    log_ok "  report_bundle.json written"

    RUN_DIR_DISPLAY="${run_dir}/"

    # Compute phases represented in evidence for summary
    local phases_present
    phases_present=$(for l in "${EVIDENCE_LINES[@]:-}"; do echo "$l" | jq -r '.phase'; done \
        | sort -u | tr '\n' ',' | sed 's/,$//')

    {
        echo "# Session End — 12_report_pack.sh"
        echo "# Time:        $(_now)"
        echo "# Project:     ${ORCHESTRATOR_PROJECT_ID}"
        echo "# Run dir:     ${run_dir}"
        echo "# Evidence:    ${EVIDENCE_COUNT}"
        echo "# Findings:    ${FINDINGS_COUNT} (${SEVERITY_COUNTS})"
        echo "# Residual:    ${RESIDUAL_RISK}"
    } >> "$LOG_FILE"

    PHASES_DISPLAY="${phases_present:-none}"
    EVIDENCE_COUNT_DISPLAY="${EVIDENCE_COUNT}"
}

# =============================================================================
# MRK:12_MAIN — MAIN entry point | main,entry,point | L711-760
# NAV-RULE: no-insert-before; read-toc-first
# =============================================================================

main() {
    echo -e "${GREEN}"
    echo "════════════════════════════════════════════════════════════"
    echo "  12_report_pack.sh"
    echo "  TechGuard."
    echo "  Project:  ${ORCHESTRATOR_PROJECT_ID}"
    echo "  Profile:  ${ENGAGEMENT_PROFILE}"
    echo "  Evidence: ${EVIDENCE_BASE}"
    [[ "$DRY_RUN" -eq 1 ]] && echo "  Mode:     DRY-RUN"
    [[ "$RETEST"  -eq 1 ]] && echo "  Retest:   YES (retest_status=pending)"
    echo "════════════════════════════════════════════════════════════"
    echo -e "${NC}"

    {
        echo "# Session Start — 12_report_pack.sh"
        echo "# Time:        $(_now)"
        echo "# Project:     ${ORCHESTRATOR_PROJECT_ID}"
        echo "# Profile:     ${ENGAGEMENT_PROFILE}"
        echo "# Dry run:     ${DRY_RUN}"
        echo "# Retest:      ${RETEST}"
        echo "# Evidence:    ${EVIDENCE_BASE}"
    } >> "$LOG_FILE"

    # Check for jq before doing any real work (belt-and-suspenders; also caught in validate)
    command -v jq &>/dev/null || { log_err "jq required"; exit 1; }
    command -v sha256sum &>/dev/null || { log_err "sha256sum required"; exit 1; }

    # Run each section
    build_scope_json
    build_evidence_manifest
    collect_findings
    build_report_bundle
    write_output

    # Compute phases from evidence lines for display
    local phases_str="${PHASES_DISPLAY:-unknown}"

    echo ""
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  12_report_pack.sh — Export complete${NC}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════${NC}"
    printf "  %-14s %s\n" "Run dir:"     "${RUN_DIR_DISPLAY:-<dry-run>}"
    printf "  %-14s %s\n" "scope.json:"  "${SCOPE_TARGET_COUNT} targets"
    printf "  %-14s %s\n" "evidence:"    "${EVIDENCE_COUNT} items across ${phases_str} phases"
    printf "  %-14s %s\n" "findings:"    "${FINDINGS_COUNT} findings (${SEVERITY_COUNTS})"
    printf "  %-14s %s\n" "residual:"    "${RESIDUAL_RISK}"
    echo ""
    if [[ "$DRY_RUN" -eq 0 ]]; then
        echo "  To import into TG Audit Orchestrator:"
        echo "  python -m ptorc_adapter.import \\"
        echo "    --project ${ORCHESTRATOR_PROJECT_ID} \\"
        echo "    --run-dir ${RUN_DIR_DISPLAY}"
    else
        echo -e "${YELLOW}  DRY-RUN complete — no files written.${NC}"
    fi
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo ""
}

main

# L2 NAV:v1 → ./ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
