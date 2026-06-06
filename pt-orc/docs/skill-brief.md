<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../ORC-INDEX.md -->

<!-- MRK:SKILL_BRIEF_NAV_TOC — Section index | nav,toc,index | L4-28 -->
<!-- - MRK:SKL_HOWTO — How to Use This File | skl,howto,how,use | L29-32 -->
<!-- - MRK:SKL_S0 — §0. Skill Navigation Protocol — how the skill reads suite files efficiently | skl,s0,skill,navigation,protocol | L33-114 -->
<!-- - MRK:SKL_S1 — §1. Skill Role | skl,s1,skill,role | L115-134 -->
<!-- - MRK:SKL_S2 — §2. Reference File Loading Strategy | skl,s2,reference,loading,strategy | L135-147 -->
<!-- - MRK:SKL_S3 — §3. State Snapshot Schema | skl,s3,state,snapshot,schema | L148-219 -->
<!-- - MRK:SKL_S4 — §4. Phase → Skill Dispatch | skl,s4,phase,skill,dispatch | L220-238 -->
<!-- - MRK:SKL_S5 — §5. Evidence Consumption Map | skl,s5,evidence,consumption,map | L239-303 -->
<!-- - MRK:SKL_S6 — §6. Finding Severity Assignment | skl,s6,finding,severity,assignment | L304-324 -->
<!-- - MRK:SKL_S7 — §7. Hard Limits | skl,s7,hard,limits | L325-337 -->
<!-- - MRK:SKL_S8 — §8. Skill Version Tracking | skl,s8,skill,version,tracking | L338-353 -->
<!-- - MRK:SKL_S9 — §9. Session Start Checklist for Skill Builder | skl,s9,session,start,checklist | L354-368 -->
<!-- - MRK:SKL_S10 — §10. Multi-analyst + shared-Claude broker awareness | skl,s10,multi,analyst,shared | L369-402 -->
<!-- - MRK:SKL_S11 — §11. Cross-engagement correlation + finding-ID namespace | skl,s11,cross,engagement,correlation | L403-440 -->
<!-- - MRK:SKL_S12 — §12. NAV-RULE + Notes protocol integration | skl,s12,nav,rule,notes | L441-477 -->
<!-- - MRK:SKL_S13 — §13. Planning artefacts (`.in/`, `.deleted/`, `NEXT.md`, `techguard-workplan.md`) | skl,s13,planning,artefacts,deleted | L478-520 -->
<!-- NAV-LEN: 15 entries | Integrity-hash: 243721a418b279fa | Last-indexed: 2026-04-24T20:37:14Z -->


# PT-Orc Skill Integration Brief
**TechGuard. | Suite v0.95**
*For skill-creator use — describes what the PT-Orc skill family does, how it maps to the script suite, what it reads, and what it must never do.*

---

## MRK:SKL_HOWTO — How to Use This File | skl,howto,how,use | L29-32
> **Purpose:** Skill-creator reference — load when building or updating pt-orc skill family. Not for operator sessions.
> **Efficient access:** §0 (navigation protocol) and §3 (state schema) and §5 (evidence map) are the highest-value sections for skill implementation. Grep the §N tag to jump directly. Read §7 (hard limits) before writing any skill output logic.

## MRK:SKL_S0 — §0. Skill Navigation Protocol — how the skill reads suite files efficiently | skl,s0,skill,navigation,protocol | L33-114

**This section is the authoritative behaviour spec for the pt-orc skill's navigation and context discipline. All L1/L2/L3 skills in the pt-orc family MUST follow these rules.**

### §0.1 Orientation header — always read first, never skip

Every PT-Orc file carries an orientation header at the top. Read it BEFORE deciding whether or how much more of the file to load.

| File type | Lines to read | What's there |
|-----------|---------------|--------------|
| Shell scripts (`.sh`) | **3** (shebang + L1 + L2) | L1: `#!/bin/bash` · L2: `# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)` · L3: `# L2 NAV:v1 → ../ORC-INDEX.md` |
| PowerShell (`.ps1`) | **3** (shebang + L1 + L2) | L1: `#!/usr/bin/env pwsh` · L2: `# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)` · L3: `# L2 NAV:v1 → ../ORC-INDEX.md` |
| Markdown (`.md`) | **2** (L1 + L2) | L1: `<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->` · L2: `<!-- L2 NAV:v1 → [path to ORC-INDEX.md] -->` |

**The header is not decoration — it is instructions.** Process its routing pointers as authoritative, then act on them.

### §0.2 Decision tree after orientation

1. **"I only need to know what this file is"** → header is the whole answer. Stop.
2. **"I need one specific thing from it"** → grep for the relevant `MRK:TAG` and read only that section.
3. **"I don't know which file owns the topic"** → check `ORC-INDEX.md` (flat global anchor index, auto-generated via `./tools/pt-orc-reindex.sh --mrk`). Find the tag → grep that file.
4. **"Structural audit / full refactor"** → load whole file, state the reason first.

### §0.3 Session default (at session start, without explicit user request)

**Load only:**
- `prj_status.md` for the active engagement (minimal — ~75 lines)
- `planning/action-plan.md` restricted to `MRK:INPROG` (the in-progress section; typically ~20-40 lines)
- `ORC-INDEX.md MRK:INDEX_FILES` (directory listing — ~50 lines, default load). Load `MRK:INDEX_ALL` (263 flat anchor entries, 550+ lines total) only when doing cross-file anchor searches. Stating purpose before loading the full file is required per §0.4.

**Do NOT auto-load:**
- `docs/orientation.md` — load only when the user asks about suite structure or data flow
- `docs/funcs.md` — load only when the user asks about a specific function or line-number sync work
- `docs/design.md` — load only when the user asks about design rationale or a gotcha
- `docs/ops.md` — load only when the user asks about operator commands
- `docs/skill-brief.md` (this file) — load only when working on the skill family itself
- Any script (`0N_*.sh`) — load only when the user asks about a specific script or finding
- `README.md` — load only for repo-onboarding questions

### §0.4 Budget threshold

- Targeted loads (section via MRK tag, typically 30-150 lines) — load silently.
- Any load projected to exceed **~200 lines** — state in ONE sentence what you're looking for BEFORE loading. Operator can interrupt if wasteful.
- Never re-load a file already in the session's context. Grep / recall from context instead.
- Never load two reference MDs in parallel when one suffices (e.g. `docs/orientation.md` AND `docs/funcs.md` together is almost always wasteful — pick one; each file's own header tells you which is right).

### §0.5 Tools the skill should know about

| Tool | Purpose | When to reference |
|------|---------|------------------|
| `./tools/pt-orc-reindex.sh --verify` (or `.ps1`) | Per-file NAV↔section anchor consistency check. Exit 1 on drift. | CI / pre-commit; mention to operator when MRK edits just happened |
| `./tools/pt-orc-reindex.sh --mrk` | Regenerate `ORC-INDEX.md` from live anchors across the suite. | After adding new sections; before commit |
| `./tools/pt-orc-reindex.sh --fix-nav` | Auto-rebuild per-file `MRK:0N_NAV` blocks from actual section headers. | After adding/reordering sections; section headers are ground truth |

The skill is read-only with respect to these tools — it does not run them. It can **reference them** to the operator (e.g. "after this edit, suggest running `./tools/pt-orc-reindex.sh --verify`").

### §0.6 Hard limits (never override)

These extend the general hard limits in §7:

1. **Never load a file without a specific purpose.** Default is grep-and-read-section, not read-whole-file. Every full-file load requires a stated reason.
2. **Never load the same file twice in a session** if the first load still has the needed content in context.
3. **Never invent new MRK tag prefixes.** New prefix families must first be added to `docs/orientation.md MRK:IDX_S0`.
4. **Never bypass the orientation header.** Even if you think you know what's in a file, read the header — conventions evolve.

### §0.7 When the operator asks "what's in file X"

Your answer should be reconstructible from the orientation header + per-file NAV table alone. If it isn't, load only the specific MRK section you need to answer. If after that you still need more, ask the operator — don't speculatively load.

### §0.8 Cross-file navigation idioms

- **Finding the owner of a topic** → `ORC-INDEX.md` first (one-line per anchor, plus description). Cheap lookup.
- **Finding a function** → `docs/funcs.md MRK:S0N` where `N` is the script number. O(1) jump via grep.
- **Finding design rationale for "why is X done this way"** → `docs/design.md MRK:GOTCHAS` or `MRK:D03` (per-script design).
- **Finding a config variable** → `docs/orientation.md MRK:IDX_S3` (config table).
- **Finding where evidence lives** → `docs/orientation.md MRK:IDX_S4` (evidence tree).
- **Finding the stealth-tier parameter for tool X** → `docs/orientation.md MRK:IDX_S5`.

---

---

## MRK:SKL_S1 — §1. Skill Role | skl,s1,skill,role | L115-134

The PT-Orc skill family is an **AI co-operator** — not a script replacement or automation layer. The scripts run autonomously and produce evidence. The skill reads that evidence, reconstructs context, assists the human operator with interpretation, correlation, and report generation.

**The skill:**
- Loads engagement state from evidence and summary files
- Correlates findings across script outputs (e.g. open Redis from 03 + no auth header from 05 + no WAF from 04 = confirmed critical)
- Interprets ambiguous results and flags what needs human action
- Generates structured finding stubs for the pt-evidence workflow
- Produces report sections via pt-report

**The skill never:**
- Runs or instructs execution of any script
- Approves or modifies scope — that is a human gate
- Writes to `evidence/` or `working/` directories — read-only access to those paths
- Decides whether to exploit a finding — 08_exploit requires explicit human `--authorize` flag
- Treats script output as ground truth without noting confidence level

---

## MRK:SKL_S2 — §2. Reference File Loading Strategy | skl,s2,reference,loading,strategy | L135-147

Two reference files exist for different contexts. Never load both in the same session.

| File | Load when | Purpose |
|------|-----------|---------|
| `docs/orientation.md` | Session start; orientation; any reporting/correlation work | What scripts exist, where output goes, what config drives what, data flow. Answers: "what should I look for and where?" |
| `docs/funcs.md` | Only when reading or modifying script code | Full function index with line numbers, shared patterns, gotchas, design decisions |

**Default for PT-Orc skill sessions:** load `docs/orientation.md` only. Drop it once the evidence is fully loaded and findings work begins — it is orientation, not a working reference.

---

## MRK:SKL_S3 — §3. State Snapshot Schema | skl,s3,state,snapshot,schema | L148-219

The canonical state snapshot that the skill reconstructs at session start. All fields must be populated before the skill proceeds past orientation. Fields marked ★ are critical — if missing, ask the operator before continuing.

```
ENGAGEMENT
  project_name        ★ matches MSF workspace name exactly (from pt-orc.conf PROJECT_NAME)
  mode                ★ pte | pti
  date                ★ YYYY-MM-DD of scan run (from session timestamp in any working/ file)
  suite_version       ★ e.g. 0.95
  operator            optional — for report attribution

SCOPE
  target_domains        space-separated (PTE only; from pt-orc.conf)
  target_ips          ★ space-separated explicit IPs in scope
  target_subnets        PTI only; empty for PTE
  excluded_ips          tester IPs excluded from scanning

PHASE_STATUS          ★ for each phase: completed | skipped | partial | not_run
  phase_01_dns
  phase_02_ip
  phase_03_scan
  phase_04_tls
  phase_05_web
  phase_06_wpscan
  phase_07_verify
  phase_08_exploit      future; requires operator --authorize

DISCOVERY
  live_hosts          ★ list of IPs confirmed live (from scan_summary / MSF DB)
  host_count
  tls_targets           working/tls_targets.txt contents
  wp_targets            scripts/wp_targets.txt contents (populated by 05)

CRITICAL_FLAGS        ★ populated from manual_followup_<TS>.md CRITICAL rows
  exposed_services      list of IP:port:service flagged EXTERNALLY EXPOSED
  ssh_cve_candidates    IPs with SSH CVE-check items

FINDINGS_STATE
  stub_count            number of finding stubs generated so far
  stubs_validated       count with CONFIRMED vs NEEDS_VERIFICATION state
  report_sections_done  list of sections written by pt-report

WORKING_FILES         ★ actual filenames present (TS varies per run)
  scan_summary
  manual_followup
  dns_summary
  ip_range_report
  tls_summary
  web_summary
  wpscan_report

BROKER_CONTEXT        optional — populated when session runs under the shared-Claude broker
  broker_session_id     unique per-analyst session (e.g. tg-alice-01)
  broker_backend        anthropic | bedrock | vertex — which API backend the broker dispatched to
  concurrent_peers      count of other active analyst sessions on the same broker

ANALYST_CONTEXT       optional — populated when multi-analyst coordination is in effect
  analyst_name          human-readable analyst identifier
  analyst_role          lead | contributor | reviewer
  engagement_peers      other analysts active on the same engagement (IDs only)

CORRELATION
  cross_engagement_mode   ★ bool — default false (engagement hermetic); true = analyst opted in to see sibling engagements for same client
  finding_id_namespace    engagement-local | client-global — default engagement-local (F-XX). client-global uses <engRef>-F-XX
  sibling_engagements     list of engagement IDs visible when cross_engagement_mode=true
```

**How to populate:** read `working/scan_summary_<TS>.md` (host count, phases, evidence file list), `working/manual_followup_<TS>.md` (critical flags), and `pt-orc.conf` (scope, project name). The rest is inferred from which working/ files are present.

---

## MRK:SKL_S4 — §4. Phase → Skill Dispatch | skl,s4,phase,skill,dispatch | L220-238

| Phase | Script | L2 Skill | Trigger condition | Input files |
|-------|--------|----------|------------------|-------------|
| DNS/OSINT | 01 | `pt-recon` | Subdomain analysis, takeover candidates, cloud attribution of resolved IPs | `working/dns_summary_<TS>.md`, `evidence/_dns/` |
| IP Intel | 02 | `pt-recon` | ASN correlation, cloud/CDN attribution, scope clarification | `working/ip_range_report_<TS>.md`, `evidence/_ip_analysis/<IP>/` |
| Network scan | 03 | `pt-enum` | Service/version analysis, critical exposure triage | `working/scan_summary_<TS>.md`, `working/manual_followup_<TS>.md`, `evidence/_exports/services_tcp_*.csv` |
| TLS assessment | 04 | `pt-enum` | TLS weakness analysis, cert findings, cipher issues | `working/tls_summary_<TS>.md`, `evidence/<IP>/testssl_<port>_<TS>.json` |
| Web enum | 05 | `pt-enum` | Header misconfigs, CORS, tech fingerprint, path discovery | `working/web_summary_<TS>.md`, `evidence/<IP>/` (per-port files) |
| WordPress | 06 | `pt-enum` | Plugin/theme CVEs, user enumeration, exposure chain | `working/wpscan_report_<TS>.md`, `evidence/_wpscan/<label>/` |
| Service verify | 07 | `pt-orc-monitor` | Live probe monitoring; manual-followup flag queue; 3-tier probe chain (native → MSF → MANUAL) | `working/manual_followup_<TS>.md`, `working/verify_summary_<TS>.md`, `evidence/_verify/<IP>/` |
| Exploratory | any | `pt-focus` | Bounded scratchpad for exploratory analysis within an active engagement — `FOCUS ON: <objective>` opens, `FOCUS EXIT` closes with a `FOCUS_RESULT:` block. State-frozen during focus (no finding commits, no severity assignments, no stage progression). | Any phase evidence; results feed back to `pt-evidence` as candidate stubs |
| All phases | all | `pt-evidence` | Convert prioritised items to finding stubs | Any of the above |
| All phases | all | `pt-report` | Convert stubs to polished report sections | Finding stubs + state snapshot |

**Dispatch rule:** pt-orc (L1) loads docs/orientation.md + state snapshot, then dispatches to the appropriate L2 skill. L2 skills are loaded one at a time and dropped when their phase work is done. `pt-commands` (L3) is loaded by L2 only when specific tool command syntax is needed. `pt-orc-monitor` (monitoring) operates independently alongside any phase — it watches live scan output and surfaces anomalies without requiring a dispatch from pt-orc.

---

## MRK:SKL_S5 — §5. Evidence Consumption Map | skl,s5,evidence,consumption,map | L239-303

What each script produces and what finding types the skill should extract from it.

### 01 — DNS Recon
| File | Finding types |
|------|--------------|
| `working/dns_summary_<TS>.md` | Subdomain count, live hosts confirmed by httpx, takeover candidates, zone transfer success |
| `evidence/_dns/takeover_candidates_<TS>.txt` | Subdomain takeover — CNAME points to unclaimed resource |
| `evidence/_dns/httpx_<TS>.txt` | Live web surface — feeds into 04/05 scope confirmation |
| `evidence/_dns/all_subdomains_<domain>_<TS>.txt` | Full enumerated surface — cross-reference with 03 targets |

### 02 — IP Range Analysis
| File | Finding types |
|------|--------------|
| `working/ip_range_report_<TS>.md` | Cloud-hosted IPs (extra RoE care), ASN ownership, geolocation anomalies, CDN-fronted IPs |
| `evidence/_ip_analysis/<IP>/summary_<IP>.md` | Per-IP: PTR mismatch, shared hosting, cloud provider |
| `evidence/_ip_analysis/<IP>/shodan_<IP>.txt` | Historical exposure, previously open ports |

### 03 — Comprehensive Scan
| File | Finding types |
|------|--------------|
| `working/manual_followup_<TS>.md` | ★ **Primary triage source** — CRITICAL flags (exposed DBs), SSH CVE candidates, web service list |
| `working/scan_summary_<TS>.md` | Phase completion, host inventory, TLS handoff list |
| `evidence/_exports/services_tcp_<TS>.csv` | Full open port/service/version table — feed into module matching for 08 |
| `evidence/_exports/notes_<TS>.csv` | NSE script output — banner grabs, http-title, ssh-hostkey, smb-security-mode, etc. |
| `evidence/_sweep/nse_common_<TS>.nmap` | Detailed NSE results — parse for vuln script hits |
| `evidence/<IP>/nmap_http_<TS>.nmap` | Per-host HTTP enumeration from phase_enum |

**Critical flag pattern in manual_followup:** rows containing `EXTERNALLY EXPOSED — CRITICAL` are highest-priority stubs; generate immediately regardless of phase completion state.

### 04 — TLS Scan
| File | Finding types |
|------|--------------|
| `working/tls_summary_<TS>.md` | Summary table: host, grade, legacy protos enabled, weak ciphers, cert issues |
| `evidence/<IP>/testssl_<port>_<TS>.json` | Machine-readable — parse `findings[]` array; `severity` field: CRITICAL/HIGH/MEDIUM/LOW/INFO |
| `evidence/<IP>/cert_<port>_<TS>.txt` | Cert chain — expiry, CN mismatch, self-signed, weak key |
| `evidence/<IP>/tls_legacy_<port>_<TS>.txt` | Legacy protocol probe results (ssl2/ssl3/tls1/tls1.1) |
| `evidence/<IP>/sec_headers_<port>_<TS>.txt` | 04-phase security header analysis (pre-web-enum) |

**testssl JSON parsing:** `jq '.findings[] | select(.severity=="HIGH" or .severity=="CRITICAL")'` on the `.json` file gives a clean finding list without reading the full console output.

### 05 — Web Enum
| File | Finding types |
|------|--------------|
| `working/web_summary_<TS>.md` | Per-host summary: tech stack, missing headers, CORS flag, notable paths |
| `evidence/<IP>/sec_headers_<port>_<TS>.txt` | Missing/weak security headers (10 checked: CSP, HSTS, X-Frame-Options, etc.) |
| `evidence/<IP>/cors_<port>_<TS>.txt` | CORS misconfiguration — reflects attacker origin, allows credentials |
| `evidence/<IP>/headers_<port>_<TS>.txt` | Raw HTTP response headers — server version disclosure, cookie flags |
| `evidence/<IP>/whatweb_<port>_<TS>.txt` | Tech fingerprint — framework, CMS, version strings |
| `evidence/<IP>/nikto_<port>_<TS>.txt` | Nikto findings — parse `+ ` prefixed lines for hits |
| `evidence/<IP>/gobuster_<port>_<TS>.txt` | Discovered paths — look for /admin, /api, /backup, /.git, /env |
| `evidence/<IP>/api_endpoints_<port>_<TS>.txt` | API surface confirmed accessible |
| `evidence/<IP>/nmap_webcreds_<port>_<TS>.nmap` | Default credential hits from nmap http-default-accounts |

### 06 — WPScan
| File | Finding types |
|------|--------------|
| `working/wpscan_report_<TS>.md` | Per-target summary: version, plugins with CVEs, user list, exposure items |
| `evidence/_wpscan/<label>/wpscan_full_<TS>.txt` | Full WPScan output — parse `[!]` lines for vulnerabilities |
| `evidence/_wpscan/<label>/xmlrpc_<TS>.txt` | XML-RPC enabled/accessible — brute-force vector |
| `evidence/_wpscan/<label>/wpjson_users_<TS>.txt` | wp-json user enumeration results |

---

## MRK:SKL_S6 — §6. Finding Severity Assignment | skl,s6,finding,severity,assignment | L304-324

Use this mapping when generating stubs. Scripts flag CRITICAL themselves only for externally-exposed unprotected services; the skill applies judgment for everything else.

| Condition | Severity |
|-----------|----------|
| Externally exposed unauthenticated service (Redis, MySQL, PG, MongoDB) | CRITICAL |
| RCE-class CVE with confirmed vulnerable version | CRITICAL |
| XML-RPC enabled + no rate limit | HIGH |
| SSLv3/TLS 1.0 active + sensitive application | HIGH |
| CORS: reflects arbitrary origin + allows credentials | HIGH |
| Missing HSTS on login/auth endpoint | HIGH |
| wp-json user enumeration successful | MEDIUM |
| Missing CSP / X-Frame-Options on non-auth pages | MEDIUM |
| Server version disclosure (Apache/nginx/IIS) | LOW |
| Default credential attempt — no hit confirmed | INFO |

Confidence levels: `CONFIRMED` when tool output explicitly shows successful access/exploitation; `HIGH_CONFIDENCE` when version match to known CVE; `NEEDS_VERIFICATION` when indirect evidence only (e.g. port open but no banner, version inferred from headers).

---

## MRK:SKL_S7 — §7. Hard Limits | skl,s7,hard,limits | L325-337

These must be enforced by the skill unconditionally — not overridable by operator instruction in chat:

1. **No script execution.** Never emit `sudo ./0N_*` or `msfconsole` commands as instructions to execute. Reference ops quick guide (docs/ops.md) or tell operator which script to run and why.
2. **No scope expansion.** Never add hosts, IPs, or domains to scope. Scope is defined in `pt-orc.conf` and confirmed by the human operator at script startup. If a discovered asset is out-of-scope, flag it; do not assess it.
3. **No evidence writes.** The skill does not create, modify, or delete files in `evidence/` or `working/`. Finding stubs exist only in the skill session until the operator explicitly saves them.
4. **No exploit authorization.** The skill may identify exploitable conditions and describe what `08_exploit.sh` would do, but the `--authorize` flag and the actual run are always human actions.
5. **No API key handling.** If a pt-orc.conf is loaded or pasted, redact SHODAN_API_KEY, CENSYS_*, SECURITYTRAILS_*, WPSCAN_API_TOKEN before including in any output.
6. **No cross-engagement data leak without opt-in.** If `cross_engagement_mode=false` (default, see §3 CORRELATION), the current engagement is hermetic — no findings, hosts, credentials, or evidence from sibling engagements for the same client are visible or surfaced, even if other engagements exist for that client in the broker's knowledge surface. Cross-engagement surfacing requires the operator to explicitly toggle `cross_engagement_mode=true` or to issue a named cross-engagement query (e.g. "compare this CVE against prior Acme engagements").

---

## MRK:SKL_S8 — §8. Skill Version Tracking | skl,s8,skill,version,tracking | L338-353

| Skill | Current version | Aligned to suite version | Status |
|-------|----------------|-------------------------|--------|
| `pt-orc` (L1) | v0.72 | 0.72 | **Needs v0.77 bump** — script names/versions; §4 dispatch table now includes 07 row; 08 phase slot TBD |
| `pt-recon` (L2) | v0.72 | 0.72 | **Needs v0.77 bump** — 01 output file paths (httpx_`<TS>`.txt); is_private_ip behaviour |
| `pt-enum` (L2) | v0.72 | 0.72 | **Needs v0.77 bump** — testssl JSON field names; 10-header list; CORS 3-origin check; _get_web_hosts_csv fallback |
| `pt-evidence` (L2) | v0.72 | 0.72 | **Needs v0.77 bump** — severity table (§6 above); confidence level field |
| `pt-report` (L2) | v0.72 | 0.72 | **Needs v0.77 bump** — ERA house style finetune via skill-creator; confirm section structure |
| `pt-commands` (L3) | v0.72 | 0.72 | **Needs v0.77 bump** — gobuster dns (not dnsrecon); host(address) in psql queries |
| `pt-orc-monitor` | v0.95 | 0.95 | Current — live monitoring skill; Living Guide format; no dispatch dependency |

**Update approach (M1.5 in workplan):** do not update skills one at a time. After 07_service_verify is validated and scripts are renamed (M1.2 upstream push), do a single batch pass updating all L1/L2/L3 skills to v0.77. Ensures phase dispatch table is complete and consistent before skills ship. `pt-orc-monitor` tracks suite version independently — update separately as monitoring spec evolves.

---

## MRK:SKL_S9 — §9. Session Start Checklist for Skill Builder | skl,s9,session,start,checklist | L354-368

When building or updating the `pt-orc` L1 skill, verify it does these things in order:

1. Load `docs/orientation.md` (not docs/funcs.md)
2. Ask operator for engagement working directory or accept a pasted `scan_summary` + `manual_followup`
3. Reconstruct state snapshot (§3) — ask for any ★ fields that are missing
4. Display: phase completion status, host count, critical flags (if any), current position
5. Prompt operator: "What are we working on?" — do NOT auto-dispatch to L2 without confirmation
6. On operator instruction, dispatch to correct L2 skill (§4 table), passing state snapshot
7. Before dropping any L2 skill, confirm finding stubs are in a saveable state
8. Never load two L2 skills simultaneously

---

## MRK:SKL_S10 — §10. Multi-analyst + shared-Claude broker awareness | skl,s10,multi,analyst,shared | L369-402

The pt-orc skill family is designed to operate in three session shapes:

| Shape | When | Behaviour |
|-------|------|-----------|
| **Solo** (default) | One analyst, one Claude session | Current behaviour; no coordination required |
| **Multi-analyst same engagement** | Two or more analysts on the same engagement via their own sessions | `ANALYST_CONTEXT` populated (see §3); each analyst declares `analyst_role`; finding-ID handoff uses single engagement namespace |
| **Shared-Claude broker** | N analyst sessions (same or different engagements) multiplexed onto one Claude subscription via a VPN-accessible broker | `BROKER_CONTEXT` populated; skill respects per-session isolation and fairness budgets |

### Solo → Multi-analyst transition

When a second analyst joins:

1. The incoming analyst's skill instance reads the current `prj_status.md` (or an equivalent broker-pushed state snapshot) for the engagement.
2. The incoming skill registers its `analyst_name` + `analyst_role` in `ANALYST_CONTEXT` and fetches the `engagement_peers` list.
3. Finding commits go through a lightweight lock: if the primary analyst (`lead`) has a F-XX in-flight, contributors hold their stub as `F-XX-pending-merge` until the lead commits or declines.
4. Severity assignments require `lead` role — contributors propose, reviewers approve, lead commits.

### Shared-Claude broker rules

1. **Per-session isolation.** BROKER_CONTEXT.broker_session_id is the hard isolation boundary. No context, memory, or state from session A is visible in session B unless explicitly shared via a broker-mediated channel (e.g. engagement-peer handshake).
2. **Backend awareness.** `broker_backend` may be anthropic / bedrock / vertex; skill should not assume consistent prompt-cache behaviour across backends.
3. **Concurrent peers.** If `concurrent_peers` > 5, the skill shortens its own responses (terse mode) to reduce token contention. If > 15, the skill defers non-urgent status outputs.
4. **Failure behaviour.** If broker becomes unreachable mid-session, skill emits `⚠ broker-down — falling back to standalone; state preserved` and continues with local `prj_status.md` only. On broker recovery, skill re-registers but does not replay missed messages.
5. **Audit trail.** All skill actions logged with `broker_session_id` + timestamp to a broker-side audit log; the skill does not manage this log itself but must not disable it.

### Don't

- Don't assume `BROKER_CONTEXT`/`ANALYST_CONTEXT` are populated — absence means solo session. Default behaviour applies.
- Don't leak `broker_session_id` into evidence files or report content — it's session metadata, not engagement content.

---

## MRK:SKL_S11 — §11. Cross-engagement correlation + finding-ID namespace | skl,s11,cross,engagement,correlation | L403-440

Default: **engagement is hermetic.** Each engagement has its own F-XX namespace; findings are not visible across engagements. This preserves client confidentiality and simplifies finding-ID management.

### When cross-engagement mode matters

- Same client has multiple engagements (quarterly re-tests, parallel PTI+PTE, or follow-up validations)
- Same finding recurs across clients (ecosystem-level threat signal — opt-in only)
- Re-test engagement needs to reference findings from the baseline

### Finding-ID namespacing

| Namespace | Format | When |
|-----------|--------|------|
| `engagement-local` (default) | `F-01`, `F-02`, ... `OBS-01`, ... | Single engagement, no cross-references. F-IDs reset per engagement. |
| `client-global` | `<engRef>-F-01` (e.g. `Acme-PTI-Mar-2026-F-01`) | Client has multiple engagements and findings are tracked longitudinally. Use when the engagement is part of a subscription series or re-test cycle. |

The skill reads `CORRELATION.finding_id_namespace` from the state snapshot and uses the matching format consistently within a session.

### Cross-engagement correlation rules

1. **Opt-in required.** `cross_engagement_mode` must be explicitly `true`. Default `false`.
2. **Scope of visibility.** When `true`, the skill sees `sibling_engagements` for the **same client only**. No visibility into other clients' engagements regardless of `cross_engagement_mode`.
3. **Correlation surface.** The skill may:
   - Compare current-engagement findings against sibling-engagement findings (dedup, recurrence detection)
   - Surface "known-issue" status ("Acme-PTI-Dec-2025 reported F-07 same CVE; remediated or still present?")
   - Flag net-new findings vs. re-test baseline
4. **Correlation restrictions.** The skill does **not**:
   - Auto-merge findings across engagements (human gate)
   - Surface sibling findings in the current report (findings are engagement-local artefacts; correlation is analysis-only)
   - Share credentials, evidence files, or PII across engagement boundaries

### Cross-client ecosystem-level correlation (future)

Reserved. Requires client-opt-in contractual language + M4.2b implementation. Skill must refuse cross-client queries until explicitly enabled via broker-level flag + per-client opt-in record.

---

## MRK:SKL_S12 — §12. NAV-RULE + Notes protocol integration | skl,s12,nav,rule,notes | L441-477

The skill operates inside a NAV-indexed repo and must respect the full NAV-RULE + Notes protocol defined by the `/orc-nav` skill.

### NAV-RULE awareness

On arriving at any `MRK:<TAG>` anchor, the skill reads the line immediately after the anchor for a `NAV-RULE:` comment. Tokens enforced:

| Token | Skill behaviour |
|-------|-----------------|
| `no-edit` | Skill emits T1 alert and refuses to propose edits to this section |
| `propose-before-edit` | Skill emits T1 alert, states (file + MRK tag + what + why), waits for explicit operator YES |
| `read-toc-first` | Skill emits T2 gate, fetches full `MRK:NAV_TOC` for the file before any further action in the section |
| `no-insert-before` | Skill blocks inserting content above the anchor; redirects to safe location |
| `no-insert-after` | Skill blocks inserting content after the section's last line (before next anchor or EOF); redirects |
| `insert-here` | Skill treats this as the designated drop zone for new content of the section's type |
| `same-commit:<file>` | Skill reminds operator that changes here must land atomically with the named file |

### Notes protocol

When the skill spots observations during a session:

- **`ORC NAV:`** (exact inline prefix) — a lead that may advance a planned or existing issue. Follow with options for the operator to investigate or defer.
- **`=AI feedBACK OFFtopic=`** (exact casing; ABO in shorthand) — standalone meta/curious observation. Not a prompt; operator can engage or ignore.

At session close, the skill **proposes** (never auto-creates) a session-notes file at `planning/notes/ORC_NAV_NOTES_<project>_<YYYYMMDD-HHMMSS>.md` with five MRK sections: `INVESTIGATED`, `AI_OFFTOPIC`, `CONCLUSIONS`, `ORC_NAV_IMPROVEMENTS`, `MISSES`.

### Miss tracking

When a `MRK:NAV_TOC` lookup doesn't yield the needed info, classify silently: **anchor-miss** / **content-gap** / **search-miss** / **cross-file-miss**. At 2+ misses or task-end, propose logging to `session_lessons_log.md` so the index improves over time. Never silently drop a miss — it wastes the inference effort that produced it.

### Reindex discipline

After any MRK anchor add / rename / remove, run `python tools/orc-nav-reindex.py reindex` + `verify` before commit. The composite `bash tools/pt-orc-reindex.sh --pre-commit` (or `.ps1` on Windows) runs both in order. Commits with integrity-hash drift are forbidden.

---

## MRK:SKL_S13 — §13. Planning artefacts (`.in/`, `.deleted/`, `NEXT.md`, `techguard-workplan.md`) | skl,s13,planning,artefacts,deleted | L478-520

The skill honours four planning-layer artefacts:

### `.in/` — user-incoming drop zone

Located at repo root (e.g. `C:\ccrd\PT-Orc\.in\`). Users drop briefs, findings, feedback for the skill to process.

- **Session start**: list `.in/` contents (name + size + mtime). If NAV:v1 header detected (lines 1–3), surface the file's MRK:NAV_TOC as a one-line summary. Otherwise, surface name + first meaningful line.
- **Never silently load.** Ask the operator: summarize / load into context / parse into action-plan / acknowledge and skip.
- **On "parse into action-plan"**: after items land in `action-plan.md` (appropriate MRK section), propose moving the source file to `.deleted/` with YAML frontmatter `status: captured` + `source: .in/<name>` + `captured-at: <date>` + `action-plan-ref: MRK:<TAG>` (see WORKFLOW-1 in MRK:LLMTODOS).

### `.deleted/` — captured/solved source archive

Tracked (not gitignored). Stores source files that have been captured into action-plan **or** closed (moved out of active tracking). Complements `features-log.md`:

- `features-log.md` — curated one-liner done-log, per-item
- `.deleted/` — raw-source archive, per-file, with YAML frontmatter

Skill **proposes** moves; never auto-moves.

### `planning/NEXT.md` — session handoff

Session-start mandatory read. Contains: `MRK:NEXT_STATE` (where we are), `MRK:NEXT_NEXT` (what to do next, impact-ordered), `MRK:NEXT_INFLIGHT` (user-input-pending decisions), `MRK:NEXT_GOTCHAS` (trip-wires for new sessions).

Session-end update target. Skill proposes updates to `Last-updated`, `MRK:NEXT_STATE`, `MRK:NEXT_NEXT` re-ordering, and new `MRK:NEXT_GOTCHAS` entries. Never silently updates.

### `planning/techguard-workplan.md` — delivery roadmap

Phased milestone plan (M1 v1.0 / M2 SOC-scale / M3 delivery / M4 extensions) with hour estimates. Skill reads it on request for milestone/scope context:

- Operator asks "what's in M2" → skill fetches `MRK:TGWP_M2` precise range, summarizes
- Operator asks "how long until v1.0 ships?" → skill reads `MRK:TGWP_ROLLUP` + `MRK:TGWP_CRITPATH`
- Operator asks "estimate this new item" → skill consults `MRK:TGWP_METHOD` (buckets + confidence) and proposes

The skill does **not** auto-edit the workplan. Proposals go to operator; operator steers the update + reindex.

---

*PT-Orc v0.95 | TechGuard. | Skill integration reference — not for operator use*

<!-- L2 NAV:v1 → ../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
