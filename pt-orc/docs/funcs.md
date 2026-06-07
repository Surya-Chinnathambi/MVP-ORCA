<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../ORC-INDEX.md -->

<!-- MRK:FUNCS_NAV_TOC — Section index | nav,toc,index | L4-15 -->
<!-- - MRK:CTX — §0. Context | ctx,context | L16-31 -->
<!-- - MRK:S00 — 00_pt-orc.sh | s00,pt,orc,sh | L32-50 -->
<!-- - MRK:S01 — 01_dns_recon.sh | s01,dns,recon,sh | L51-84 -->
<!-- - MRK:S03 — 03_comp_scan.sh | s03,comp,scan,sh | L85-200 -->
<!-- - MRK:S04 — 04_tls_scan.sh | s04,tls,scan,sh | L201-225 -->
<!-- - MRK:S05 — 05_web_enum.sh | s05,web,enum,sh | L226-259 -->
<!-- - MRK:S02 — 02_ip_analysis.sh | s02,ip,analysis,sh | L260-281 -->
<!-- - MRK:S06 — 06_wpscan.sh | s06,wpscan,sh | L282-306 -->
<!-- - MRK:S07 — 07_service_verify.sh | s07,service,verify,sh | L307-347 -->
<!-- NAV-LEN: 9 entries | Integrity-hash: 713c6067ef6418fa | Last-indexed: 2026-04-24T20:37:14Z -->

## MRK:CTX — §0. Context | ctx,context | L16-31

Scripts are **not standalone tools** — they operate within the pt-orc orchestration framework. Every scan call goes through `run_rc_scan`, which writes a `.rc` resource script and executes it via `msfconsole -q -r`. Hosts, services, and NSE output land in the MSF workspace DB. The `.rc` file is retained as reproducible audit evidence.

**Two DB connection paths — independent of each other:**
- `msfconsole` / `export_db` — Ruby pg adapter; always works on Kali regardless of psql state
- `db_query` / `psql` — direct TCP to 127.0.0.1 (hardcoded since v0.76; Unix socket path removed). `parse_db_conf` tests TCP; sets `DB_DIRECT_AVAILABLE=0` if it fails. Phases fall back to CSV data already on disk (`_exports/services_tcp_*.csv`).

**DB address column:** MSF `hosts.address` is `inet` type in PostgreSQL. All queries use `host(address)` — `split_part(inet, unknown, integer)` throws a type error and was silently swallowed by the error filter, producing empty results on every query.

**Error handling:** Scripts 01/03/04/05 use `set -uo pipefail`; 02 and 06 use `set -euo pipefail` (adds immediate exit on non-zero — use `|| true` guards for expected failures in those scripts). Bash 4.3+ required (`set +u`/`set -u` guards around potentially-empty arrays).

---

## §1. Function Index

### MRK:S00 — 00_pt-orc.sh | s00,pt,orc,sh | L32-50

| Function | Line | Purpose |
|----------|------|---------|
| `usage` | 119 | Help text |
| `find_script(n)` | 222 | Glob `SCRIPT_DIR/0N_*.sh`; prefers unversioned; falls back to highest `0N_*_v*.sh`; excludes `ACTUAL_RUN/` |
| `should_run(n)` | 199 | Returns 0 if step should run given `--only`/`--from`/`--skip` flags |
| `run_step(n, name, flags...)` | 219 | Finds script, prints banner, runs `bash script flags...`, records status+duration |
| `print_summary()` | 260 | Formatted table: step / name / script / status / duration; appended to log |
| `main()` | 321 | Banner → `cd SCRIPT_DIR` → build common flags → loop steps 1–6 via `should_run` + `run_step` |

**Result tracking:** `STEP_STATUS[n]` (`OK`/`SKIP`/`FAIL(rc=N)`/`NOT FOUND`), `STEP_DURATION[n]` (e.g. `2m34s`), `STEP_SCRIPT[n]` (basename). Written by `run_step`; read by `print_summary`.

**Flag forwarding:** `--yes`/`--dry-run` → all scripts. `--mode` → 02, 03, 06. `--tier` → 03, 05, 06. `--detect` → 06 (unless `--no-wp-detect`). `--skip-active` → 01. `--fast` → 04, 05. `--skip-gobuster`/`--skip-nikto` → 05. `--phase`/`--masscan-only` → 03 only.
**`find_script` logic:** prefers unversioned `0N_*.sh` (all scripts are de-versioned since v0.8); falls back to highest-versioned `0N_*_v*.sh` for legacy compat. All 8 canonical scripts are unversioned and picked up via the primary path.
**Step loop:** runs steps 1–7 via `should_run` + `run_step`.

---

### MRK:S01 — 01_dns_recon.sh | s01,dns,recon,sh | L51-84

| Function | Line | Purpose |
|----------|------|---------|
| `verify_source_ip` | 130 | curl ifconfig.me; abort if mismatch with TESTER_IP |
| `scope_confirm` | 150 | Interactive YES gate |
| `_ip_in_cidr` | 183 | Pure-bash CIDR containment check |
| `is_thirdparty` | 193 | Checks THIRDPARTY_RANGES; returns 0 if CDN/3P |
| `is_private_ip` | 204 | Pure-bash RFC1918/loopback/link-local filter; blocks private IPs at `add_ip` and `write_targets` pipeline |
| `check_takeover` | 219 | curl + grep TAKEOVER_PATTERNS; called in background from main with concurrency cap |
| `add_ip` | 245 | Validates IP format; blocks private IPs; routes to DISCOVERED_IPS or THIRDPARTY_IPS |
| `recon_crt` | 265 | crt.sh certificate transparency via curl+python3 |
| `recon_subfinder` | 285 | subfinder passive |
| `recon_amass` | 295 | amass enum -passive |
| `recon_amass_brute` | 305 | amass enum -brute (gated by AMASS_BRUTE=1) |
| `recon_harvester` | 315 | theHarvester — free sources only (google,bing,baidu,crt,dnsdumpster,hackertarget,certspotter) |
| `recon_securitytrails` | 329 | SecurityTrails API (gated on SECURITYTRAILS_API_KEY) |
| `recon_censys` | 348 | Censys API (gated on CENSYS_API_ID/SECRET) |
| `recon_shodan_domain` | 373 | Shodan domain search (gated on SHODAN_API_KEY) |
| `recon_shodan_ip` | 382 | Shodan IP lookup per-IP (gated on SHODAN_API_KEY) |
| `axfr_attempt` | 395 | dig AXFR against domain's NS records; skipped if SKIP_ACTIVE=1 |
| `brute_subdomains` | 422 | gobuster dns against domain; skipped if SKIP_ACTIVE=1; uses first available wordlist from seclists/dnsmap |
| `resolve_subdomain` | 447 | dig CNAME then A; calls add_ip; populates CNAME_TARGETS |
| `httpx_verify` | 466 | httpx live HTTP/S probe; curl fallback if httpx missing; populates CONFIRMED_LIVE |
| `write_targets` | 510 | Writes scripts/targets.txt; strips private IPs pipeline; sort by octet |
| `write_summary` | 538 | Writes working/dns_summary_<TS>.md |
| `main` | 626 | verify_source_ip → scope_confirm → seed IPs → per-domain loop → httpx_verify → Shodan enrichment → write_targets → write_summary |

**Global data structures:** `DISCOVERED_IPS` (assoc: ip→source), `CONFIRMED_LIVE` (assoc: ip/host→"confirmed"), `CNAME_TARGETS` (assoc: subdomain→cname), `THIRDPARTY_IPS` (assoc: ip→source)

**Takeover concurrency:** MAX_TAKEOVER_JOBS=20; `check_takeover` is backgrounded per subdomain; main loop reaps with `wait -n` to cap concurrent processes.

---

### MRK:S03 — 03_comp_scan.sh | s03,comp,scan,sh | L85-200

**In-script navigation:** `grep "MRK:03_" 03_comp_scan.sh` lists all 26 section anchors. Key anchors: MRK:03_DB (db helpers), MRK:03_P2 (TCP scan), MRK:03_NSE (NSE sweep), MRK:03_P4 (PTI enum). Full index at MRK:03_NAV (line 29 of the script).

#### Infrastructure / helpers

| Function | Line | Purpose |
|----------|------|---------|
| `tier_nmap_timing` | 161 | Returns -T flag for tier |
| `tier_min_rate` | 162 | Returns --min-rate flag (empty for ghost/evasion) |
| `tier_max_rate` | 163 | Returns --max-rate flag |
| `tier_min_hostgroup` | 164 | Returns --min-hostgroup flag |
| `tier_version_intensity` | 165 | Returns --version-intensity flag |
| `tier_max_retries` | 166 | Returns --max-retries flag |
| `tier_host_timeout` | 167 | Returns --host-timeout flag |
| `tier_script_timeout` | 168 | Returns --script-timeout flag |
| `tier_evasion_flags` | 171 | Returns `-f --source-port 443 ...` for evasion only; empty for other tiers |
| `tier_scripts` | 177 | Returns `-sC` for ghost/normal/loud; `""` for evasion |
| `masscan_rate_for_tier` | 180 | Returns pps rate for Pass 1 when backend is `masscan` |
| `naabu_threads_for_tier` | 190 | Returns per-tier `naabu -c` worker count |
| `db_nmap_fast_min_rate_for_tier` | 202 | Fast `db_nmap` Pass 1 minimum rate helper |
| `db_nmap_fast_max_rate_for_tier` | 211 | Fast `db_nmap` Pass 1 maximum rate helper |
| `db_nmap_fast_min_hostgroup_for_tier` | 220 | Fast `db_nmap` Pass 1 minimum hostgroup helper |
| `db_nmap_fast_max_hostgroup_for_tier` | 229 | Fast `db_nmap` Pass 1 maximum hostgroup helper |
| `db_nmap_fast_max_retries_for_tier` | 238 | Fast `db_nmap` Pass 1 retry helper |
| `db_nmap_fast_initial_rtt_timeout_for_tier` | 247 | Fast `db_nmap` Pass 1 initial RTT helper |
| `db_nmap_fast_max_rtt_timeout_for_tier` | 256 | Fast `db_nmap` Pass 1 max RTT helper |
| `db_nmap_fast_host_timeout_for_tier` | 265 | Fast `db_nmap` Pass 1 host timeout helper |
| `db_nmap_fast_defeat_rst_ratelimit_for_tier` | 274 | Fast `db_nmap` Pass 1 RST-rate-limit toggle helper |
| `db_nmap_fast_flags` | 283 | Assembles tier-specific fast `db_nmap` Pass 1 flags from config helpers |
| `setup_dirs` | 374 | mkdir evidence subdirs + working/ |
| `ip_dir` | 384 | mkdir + return absolute path for per-IP evidence dir |
| `parse_db_conf` | 399 | Read MSF DB creds from database.yml; hardcodes MSF_DB_HOST=127.0.0.1 (TCP only); sets DB_DIRECT_AVAILABLE=0 if TCP test fails |
| `db_query` | 433 | psql one-liner via TCP; logs errors to LOG_FILE only; returns empty on error |
| `run_rc_scan` | 464 | Write .rc file → msfconsole -q -r (all db_nmap calls go here) |
| `run_db_import` | 513 | Write import `.rc` → msfconsole; batches fast-scan XML after jobs finish; `--db-nmap` flag downgrades missing-XML warnings |
| `workspace_id` | 576 | SELECT id FROM workspaces WHERE name=PROJECT_NAME |
| `get_live_hosts` | 584 | Three-tier: DB host(address) → CSV → gnmap sweep files |
| `get_open_tcp` | 621 | Three-tier: DB host(address) → CSV → gnmap per IP |
| `port_open` | 652 | Three-tier: DB host(address) → CSV → gnmap; returns 0/1 |
| `any_port_open` | 679 | Loop `port_open` over port list; returns 0 if any match |
| `_latest_services_csv` | 696 | Find most recent `services_tcp_*.csv` in `_exports/` |
| `_latest_hosts_csv` | 702 | Find most recent `hosts_*.csv` in `_exports/` |
| `get_live_hosts_csv` | 709 | awk parse hosts CSV → IP list; CSV fallback tier 2 |
| `get_open_tcp_csv` | 718 | awk parse services CSV → port list for an IP; CSV fallback tier 2 |
| `port_open_csv` | 730 | awk parse services CSV → returns 0/1 for specific port/proto; CSV fallback tier 2 |
| `_sweep_gnmaps` | 751 | Find all gnmap files in `_sweep/`; used by gnmap fallback helpers |
| `get_live_hosts_gnmap` | 758 | grep gnmap sweep files for hosts with open ports; fallback tier 3 |
| `get_open_tcp_gnmap` | 769 | grep gnmap for open ports per IP; fallback tier 3 |
| `port_open_gnmap` | 780 | grep gnmap for specific port/IP; fallback tier 3 |
| `export_db` | 791 | hosts + services + notes CSV export via rc file |
| `ip_in_cidr` | 828 | Pure-bash CIDR containment check (no python3 dependency) |
| `resolve_tier` | 839 | Per-IP tier — walks SUBNET_TIER_MAP with ip_in_cidr; falls back to GLOBAL_TIER |
| `resolve_subnet_tier` | 851 | Per-subnet exact match in SUBNET_TIER_MAP; falls back to GLOBAL_TIER |
| `effective_tier_label` | 862 | Human-readable tier summary for banners and logs |
| `build_target_list` | 876 | printf all TARGET_SUBNETS + TARGET_IPS, one per line; exits if both empty |
| `all_targets` | 888 | Space-separated combined target string for nmap command lines |
| `nmap_tier_flags` | 894 | Assembles full nmap flag string for a tier; skip_idle param suppresses -sI for UDP/enum |
| `verify_source_ip` | 917 | PTE only: curl ifconfig.me; abort on mismatch with TESTER_IP |
| `scope_confirm` | 938 | Interactive YES gate (skipped if AUTO_YES=1) |
| `rate_self_test` | 970 | PTE: 10-probe nmap self-test; warns if no responses |
| `_msf_list_workspaces` | 1008 | msfconsole -x "workspace" — returns workspace list for existence check |
| `_msf_workspace_exists` | 1021 | grep PROJECT_NAME in workspace list |
| `ensure_workspace` | 1026 | Create/verify MSF workspace via msfconsole |
| `init_exclude_list` | 1089 | Auto-detect all local IPv4s + TESTER_EXCLUDE_IPS → EXCLUDE_IPS array |
| `nmap_exclude_args` | 1122 | Returns `--exclude ip,ip,...` from EXCLUDE_IPS |
| `masscan_exclude_args` | 1130 | Returns `--excludefile` path written from EXCLUDE_IPS |
| `get_scan_hosts` | 1299 | get_live_hosts minus EXCLUDE_IPS |
| `extract_open_ports` | 1354 | grep gnmap for open ports → comma-separated list |
| `extract_open_ports_xml` | 1365 | grep masscan/nmap XML for portid → comma-separated list |
| `naabu_exclude_args` | 1137 | Returns `-exclude-hosts ip,ip,...` from EXCLUDE_IPS for naabu |
| `masscan_route_args_for_target` | 1210 | Resolves interface/source/gateway hints per target; avoids inventing gateway for directly-attached subnets |
| `masscan_supported_for_target` | 1238 | Returns 0 if masscan routing is viable for target; 1 if naabu/db_nmap should be used instead |
| `naabu_json_to_nmap_xml` | 1253 | Converts naabu JSONL output to Nmap-style XML importable by run_db_import |

#### Phase functions

| Function | Line | Phase | What it does |
|----------|------|-------|--------------|
| `phase_discovery` | 1314 | 1 (optional) | ARP sweep (`-PR -sn -Pn`) via run_rc_scan; not in "all" |
| `phase_tcp` | 1372 | 2 | Fast Pass 1 (`masscan`, `naabu`, or `db_nmap`) → Pass 2 `db_nmap` per tier |
| `phase_sweep_nse` | 1653 | 2b | DB-gated NSE sweep: confirmed live hosts (DB→CSV→gnmap fallback); port set from DB query → Pass 1 XMLs → BASELINE_PORTS last resort; `-sV -O -sC` |
| `phase_os_detect` | 1750 | 2c | OS fingerprinting; DB→CSV→gnmap fallback; falls back to configured scope when evidence is empty |
| `phase_udp` | 1874 | 3 | DB-correlated UDP per live host; baseline UDP fallback of configured scope when evidence is empty |
| `add_followup` | 1969 | - | Append to FOLLOWUP_FILE markdown table |
| `init_followup` | 1974 | - | Create FOLLOWUP_FILE header |
| `phase_enum` | 1987 | 4 (PTI) | Per-host, per-port NSE scripts for 20+ services; DB→CSV→gnmap fallback |
| `phase_enum_pte` | 2276 | 4 (PTE) | Condensed enum: ssh, http, snmp, ldap, rdp, ike, smtp, ftp; DB→CSV→gnmap fallback |
| `phase_report` | 2439 | 5 | Findings summary, export_db, FOLLOWUP_FILE |
| `main` | 2509 | - | Setup → phase dispatch loop |

#### phase_tcp internal flow (lines 1262–1542)

```
1. Build `tier_targets` map (subnet/IP → ghost/normal/loud/evasion)
2. Pass 1 uses the configured backend for `ghost|normal|loud`:
   - `masscan`: per-target parallel jobs, XML imported after all jobs finish
   - `naabu`: per-target parallel JSONL jobs, converted to XML, then imported
   - `db_nmap`: one sequential full-port scan per tier target list via `run_rc_scan`
3. `evasion` never uses the fast backend; it keeps a dedicated `nmap -p-` path
4. `--masscan-only` stops after Pass 1 import/export
5. Pass 2 — for each tier:
   - `evasion`: full `nmap -p-` first, then extract open ports from gnmap
   - others: extract Pass 1 XML ports → merge `BASELINE_PORTS` → deduplicate
   - run `tcp_deep_<tier>` via `run_rc_scan`: `-sS -sV -O [-sC] --open -Pn <flags> -p <ports> -iL <tier_list>`
6. `phase_sweep_nse` ← DB-gated: confirmed live hosts (DB→CSV→gnmap fallback); port set = DB all-open-TCP query → Pass 1 XMLs → BASELINE_PORTS last resort
7. `phase_os_detect` ← DB/CSV/gnmap-driven; falls back to `build_target_list()` if all evidence tiers are empty
8. `export_db "tcp"` ← writes `services_tcp_*.csv` before enum phases run
```

#### phase_enum NSE coverage (PTI, lines 1987–2275)

SMB (445/139), NFS (2049/111), FTP (21), SSH (22), Telnet (23), VNC (5800/5900/5901), HTTP/HTTPS (all web ports), SNMP UDP (161), LDAP (389/636/3268/3269), MSSQL (1433), MySQL (3306), PostgreSQL (5432), Oracle (1521), RDP (3389), WinRM (5985/5986), Redis (6379), MongoDB (27017), Elasticsearch (9200), IPMI UDP (623), TFTP UDP (69), SIP (5060/5061), SMTP/IMAP/POP3, RPC (111).

---

### MRK:S04 — 04_tls_scan.sh | s04,tls,scan,sh | L201-225

| Function | Line | Purpose |
|----------|------|---------|
| `parse_db_conf` | 95 | Read MSF DB creds from database.yml; hardcodes MSF_DB_HOST=127.0.0.1 (TCP only); no DB_DIRECT_AVAILABLE check — 04 reads from targets file, not DB |
| `run_rc_scan` | 134 | db_nmap via rc file (same model as 03) |
| `export_db` | 168 | hosts/services/notes CSV export via rc file |
| `scope_confirm` | 197 | Interactive YES gate; takes target_count param for display |
| `assemble_targets` | 222 | Merges TARGETS_FILE + EXTRA_HOSTS; deduplicates; warn if file missing |
| `assess_host` | 254 | Per-target: cert → legacy protocols → testssl or nmap ssl-ciphers (--fast) → security headers |
| `run_grab_scores` | 454 | Optional: grab_scores_v2.2.py screenshots (requires --grab-screens flag) |
| `main` | 473 | parse_db_conf → summary header → assemble → scope_confirm → loop assess_host → run_grab_scores → export_db |

**No `db_query` in 04** — script reads from TARGETS_FILE, not MSF DB. DB credentials are parsed only to authenticate msfconsole for `run_rc_scan` and `export_db`.

**assess_host output per target (`evidence/<IP>/`):** `cert_<port>.txt`, `tls_legacy_<port>.txt`, `testssl_<port>.{html,json,log,console.txt}` (or `nmap_tls_<port>.*` if `--fast`), `headers_<port>.txt`, `sec_headers_<port>.txt`

**Legacy protocol probes (lines 296–316):** Loops ssl2, ssl3, tls1, tls1_1 only. Checks `openssl s_client -help` for flag support before each — skips silently on OpenSSL 3.x where ssl2/ssl3 are removed. `unexpected eof` = server rejected (expected/GOOD). `CONNECTED` = server accepted (FINDING).

**Non-HTTP port detection (lines 376–380):** Ports 25,110,143,465,587,993,995,636,389,3268,3269,5432,3306,27017,6379,1433 are flagged `_is_http=0` — security header analysis writes `[SKIP]` for these instead of running curl.

**Security headers checked (10):** Strict-Transport-Security, Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, Cross-Origin-Opener-Policy, Cross-Origin-Resource-Policy, Cross-Origin-Embedder-Policy.

---

### MRK:S05 — 05_web_enum.sh | s05,web,enum,sh | L226-259

| Function | Line | Purpose |
|----------|------|---------|
| `gobuster_threads` | 78 | ghost=5, normal=20, loud=50, evasion=1 |
| `whatweb_aggression` | 80 | aggression 1–4 for tier |
| `parse_db_conf` | 139 | Read MSF DB creds; hardcodes MSF_DB_HOST=127.0.0.1 (TCP only) |
| `db_query` | 151 | psql one-liner via TCP; errors suppressed (2>/dev/null) |
| `get_web_hosts_from_db` | 156 | SELECT host(h.address):port for web ports 80,443,8080,8443,4443,8888,9443,9200,10443,8006; falls back to `_get_web_hosts_csv` if workspace missing or empty |
| `_get_web_hosts_csv` | 184 | awk parse most-recent services_tcp_*.csv for web ports; CSV fallback when DB unavailable |
| `run_rc_scan` | 208 | db_nmap via rc file (same model as 03/04) |
| `export_db` | 241 | hosts/services/notes CSV export via rc file |
| `scope_confirm` | 270 | Interactive YES gate; shows tier, gobuster/nikto/API-probe status |
| `assemble_targets` | 297 | FROM_DB → file → --host args combined; deduplicates; FROM_DB=1 default |
| `detect_tls` | 336 | Fast-path on TLS_PORTS list; fallback openssl s_client probe if not in list |
| `enumerate_host` | 353 | Full per-host web enum (9 steps) |
| `main` | 641 | parse_db_conf → assemble → scope_confirm → optionally shuf targets (evasion) → loop enumerate_host → export_db |

**enumerate_host steps:**
1. curl -I headers → `headers_<port>_<ts>.txt`
2. Security header analysis (10 headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Permissions-Policy, COOP, CORP, COEP) → `sec_headers_<port>_<ts>.txt`
2b. CORS check (3 attacker origins: evil.com, null, IP.evil.com) → `cors_<port>_<ts>.txt`
3. whatweb → `whatweb_<port>_<ts>.txt`
4. gobuster dir (evasion: 3s delay, shuffled wordlist, random UA) → `gobuster_<port>_<ts>.txt`
5. nikto (skipped if evasion or --skip-nikto) → `nikto_<port>_<ts>.txt`
6. API endpoint probe (25 paths) → `api_endpoints_<port>_<ts>.txt`
7. nmap http-default-accounts → `nmap_webcreds_<port>_<ts>.*`
8. WordPress detection → greps whatweb output; appends URL to `scripts/wp_targets.txt` idempotently
9. Append row to `working/web_summary_<TS>.md`

**`--skip-api` flag** suppresses step 6. `--fast` sets SKIP_GOBUSTER=1 + SKIP_NIKTO=1 (steps 4+5). FROM_DB=0 when `--targets` or `--host` provided.

---

### MRK:S02 — 02_ip_analysis.sh | s02,ip,analysis,sh | L260-281

**Note:** Uses `set -euo pipefail` (strict, includes `-e`) unlike 01/03/04/05 which use `set -uo pipefail`. Any unhandled non-zero return aborts the script.

| Function | Line | Purpose |
|----------|------|---------|
| `usage` | 67 | Help text — flags: --yes, --dry-run, --mode, --targets, --shodan-key |
| `parse_args` | 91 | Argument parser; sets CLI_TARGETS_OVERRIDE=1 when --targets used |
| `check_deps` | 109 | whois/dig/curl fatal; traceroute/shodan warn-only; exits on missing required tools |
| `load_targets` | 148 | CLI_TARGETS_OVERRIDE=1 → TARGET_IPS; else PTE_TARGETS_FILE; validates IPv4 format; populates TARGETS array |
| `scope_confirm` | 187 | Interactive YES gate; lists each target IP in confirmation block |
| `run_cmd` | 220 | Dry-run wrapper: prints label+cmd in dry-run, executes `"$@"` in live mode; errors suppressed (2>/dev/null) |
| `analyze_ip` | 246 | Orchestrates all 7 per-IP steps → `evidence/_ip_analysis/<IP_safe>/`; populates assoc-array accumulators |
| `write_report` | 562 | Consolidated markdown: inventory table, cloud IPs, ASN grouping, BGP prefixes → `working/ip_range_report_<TS>.md` |
| `main` | 731 | parse_args → check_deps → load_targets → scope_confirm → per-IP loop → write_report |

**analyze_ip steps:** (1) WHOIS/ASN → `whois_<safe>.txt`, (2) PTR reverse DNS → `bgp_<safe>.json`, (3) BGP via ipinfo.io (rate: IPINFO_DELAY) → `bgp_<safe>.json`, (4) Geolocation via ip-api.com (rate: GEO_DELAY) → `geo_<safe>.json`, (5) Cloud/CDN detection (ASN+org+PTR vs CLOUD_ORGS_REGEX), (6) Traceroute → `traceroute_<safe>.txt`, (7) Shodan host summary → `shodan_<safe>.txt` (gated on SHODAN_API_KEY)

**Per-IP accumulators** (populated by analyze_ip, consumed by write_report): `IP_PTR`, `IP_ASN`, `IP_ORG`, `IP_COUNTRY`, `IP_PREFIX`, `IP_CLOUD`, `IP_HOPS`, `IP_PORTS`

---

### MRK:S06 — 06_wpscan.sh | s06,wpscan,sh | L282-306

**Note:** Uses `set -euo pipefail` (strict, includes `-e`) — same as 02. Any unhandled non-zero return aborts.

| Function | Line | Purpose |
|----------|------|---------|
| `usage` | 82 | Help text — flags: --yes, --dry-run, --mode, --tier, --api-token, --detect, --detect-only, --targets-file |
| `parse_args` | 111 | Argument parser; sets DO_DETECT=1/DETECT_ONLY=1; overrides WP_TARGETS_FILE and WPSCAN_API_TOKEN |
| `check_deps` | 132 | wpscan + curl required (fatal); nikto/whatweb warn-only |
| `detect_wordpress` | 163 | Phase 1: curl sweep of WEB_TARGETS_FILE (scripts/targets.txt) × DETECT_PORTS; body+header+path probes; appends to wp_targets.txt idempotently |
| `load_wp_targets` | 273 | Read WP_TARGETS_FILE → WP_TARGETS array; warns but does not abort if file missing |
| `scope_confirm` | 300 | Interactive YES gate; lists all WP targets, API token status, budget |
| `sanitize_label` | 334 | Strip protocol, replace `/:. ` with `_` for safe dir/filename |
| `assess_wordpress` | 362 | Full 7-step WPScan assessment per WordPress URL; populates per-label accumulators |
| `write_report` | 720 | Consolidated markdown: target table, critical findings, API budget usage → `working/wpscan_report_<TS>.md` |
| `main` | 887 | parse_args → check_deps → optional detect_wordpress → optional DETECT_ONLY exit → load_wp_targets → scope_confirm → per-URL loop → write_report |

**assess_wordpress steps:** (1) Basic WPScan (no API), (2) Full enum with API token (budget decremented, skipped at 0), (3) XML-RPC probe, (4) REST API user enum `/wp-json/wp/v2/users`, (5) Config file exposure (8 paths: wp-config.php, .env, backup files), (6) wp-admin login + rate-limit headers, (7) Security headers

**Per-target accumulators** (indexed by sanitized label): `WP_VERSION`, `WP_PLUGINS`, `WP_THEMES`, `WP_USERS`, `WP_VULN_COUNT`, `WP_XMLRPC`, `WP_JSON_USERS`, `WP_EXPOSED_FILES`, `WP_SEC_HEADERS`, `WP_API_USED`

**detect_wordpress** reads `WEB_TARGETS_FILE` (scripts/targets.txt — plain IPs) not wp_targets.txt. Probes body indicators (`wp-content`, `wp-includes`, `wp-login`, `wlwmanifest`), `X-Powered-By: WordPress` header, and HTTP codes on `/wp-login.php`, `/wp-admin/`, `/wp-json/`.

---

### MRK:S07 — 07_service_verify.sh | s07,service,verify,sh | L307-347

| Function | Purpose |
|----------|---------|
| `usage` | Help text — flags: --severity, --host, --port, --service, --yes, --dry-run, --mode |
| `run_msf_module` | Writes RC file + runs msfconsole -q -r; spool to evidence/_msf/verify_* |
| `add_result` | Append VULN/SAFE/MANUAL/ERROR row to verify_summary_<TS>.md |
| `parse_followup_category` | Extract IP+port+service entries from manual_followup_*.md by category heading; two-strategy: inline + block-section |
| `parse_followup_severity_tier` | Filter followup queue by --severity flag (critical/high/medium/all) |
| `build_probe_queue` | Assemble ordered probe queue from followup MDs + optional tls_summary/web_summary; deduplicates |
| `probe_redis` | NOAUTH check → INFO server/keyspace/KEYS; MSF redis_server fallback |
| `probe_mysql` | Anonymous login → SHOW DATABASES; MSF mysql_login/mysql_sql fallback |
| `probe_postgres` | Anonymous login → \l \du; MSF postgres_login/postgres_sql fallback |
| `probe_mongodb` | Anonymous login → listDatabases; MSF mongodb_login/mongodb_find fallback |
| `probe_ftp` | Anonymous FTP → LIST /; write-detect STOR; MSF ftp_anonymous fallback |
| `probe_smb` | Null session → smbclient share list + read attempt; MSF smb_enumshares fallback |
| `probe_ssh` | Banner grab → CVE-2024-6387 version check; Dropbear CVE check; MSF ssh_version fallback |
| `probe_smtp` | swaks --quit-after RCPT relay test; last server response line evaluated |
| `probe_snmp` | onesixtyone community sweep; MSF snmp_login fallback |
| `probe_ssrf` | 20-param SSRF sweep (http+https) against IMDS/internal endpoints |
| `probe_tls_cert` | openssl s_client cert grab; expiry + CN/SAN check |
| `probe_web_headers` | curl HEAD security header check (10 headers) |
| `run_all_probes` | Main dispatch loop: iterates probe queue, calls probe_* per service type |
| `main` | parse_db_conf → build_probe_queue → scope_confirm → run_all_probes → summary |

**Queue format:** `"CATEGORY:ip port svc"` — built by `parse_followup_category` from manual_followup MDs.
**RPORT status:** `smb_enumshares` fixed (no RPORT). `mssql_ping` bad — audit pending (see action-plan MRK:SUITE).
**Output:** `working/verify_summary_<TS>.md` + per-host evidence in `evidence/_verify/<IP>/`.

---

## Design decisions, gotchas, shared patterns, and tool dependencies

**Load docs/design.md for this content.** Grep `MRK:PATTERNS` for shared patterns, `MRK:GOTCHAS` for design decisions, `MRK:D03` for 03 architecture, `MRK:TOOLS` for tool deps.

---

*PT-Orc v0.95 | TechGuard.*

<!-- L2 NAV:v1 → ../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
