<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../ORC-INDEX.md -->

<!-- MRK:ORIENTATION_NAV_TOC — Section index | nav,toc,index | L4-15 -->
<!-- - MRK:IDX_S0 — §0. MRK Naming Convention | idx,s0,mrk,naming,convention | L16-43 -->
<!-- - MRK:IDX_S1 — §1. Suite Overview | idx,s1,suite,overview | L44-63 -->
<!-- - MRK:IDX_S2 — §2. Data Flow | idx,s2,data,flow | L64-82 -->
<!-- - MRK:IDX_S3 — §3. Engagement Config | idx,s3,engagement,config | L83-149 -->
<!-- - MRK:IDX_S4 — §4. Evidence Directory Layout | idx,s4,evidence,directory,layout | L150-241 -->
<!-- - MRK:IDX_S5 — §5. Stealth Tier Reference | idx,s5,stealth,tier,reference | L242-277 -->
<!-- NAV-LEN: 6 entries | Integrity-hash: e9cc056ac6e95ebd | Last-indexed: 2026-04-24T20:37:14Z -->

Load this file for orientation. For function-level code reference load docs/funcs.md instead.
Do NOT load both docs/orientation.md and docs/funcs.md together — pick the one matching your task.

## MRK:IDX_S0 — §0. MRK Naming Convention | idx,s0,mrk,naming,convention | L16-43

No single flat map of every MRK tag exists — the convention below is the map. Given any `MRK:<TAG>`
you can infer which file owns it and grep there directly. This keeps the scheme drift-free: each
file carries its own NAV table at the top; no central index to fall out of sync.

| Prefix | Owning file | What it tags |
|--------|------------|--------------|
| `MRK:IDX_*` | `docs/orientation.md` | Suite-index sections (this file) |
| `MRK:S00`–`MRK:S07` | `docs/funcs.md` | Per-script function index sections |
| `MRK:CTX` | `docs/funcs.md` | Context preamble (DB paths, error handling, `host(address)`) |
| `MRK:PATTERNS` | `docs/design.md` (primary) / `docs/funcs.md` (pointer) | Shared patterns (RC scan, DRY_RUN, set -e split, array guards) |
| `MRK:GOTCHAS` | `docs/design.md` (primary) / `docs/funcs.md` (pointer) | Key design decisions and gotchas table |
| `MRK:TOOLS` | `docs/design.md` (primary) / `docs/funcs.md` (pointer) | Tool dependencies table |
| `MRK:D03` (D0N pattern) | `docs/design.md` | Per-script architecture/design deep-dive |
| `MRK:03_<TAG>` (0N_TAG pattern) | Inside script N | In-script section anchor (e.g. `MRK:03_DB`, `MRK:03_NAV`) |
| `MRK:INPROG` / `BLOCKERS` / `SUITE` / `SKILLS` / `LLM` / `DOCS` / `REPORT` / `DOCHAND` / `INFRA` / `POST` / `IMPROVE` / `UNSORTED` | `planning/action-plan.md` | Active-work categories |
| `MRK:BUGS_CL` / `MRK:DONE` | `planning/features-log.md` | Closed bugs / completed-work log |

### Using the convention

- **Know the prefix → know the file.** `MRK:S04` is in `docs/funcs.md`. `MRK:GOTCHAS` is in `docs/design.md`. `MRK:03_DB` is inside `03_comp_scan.sh`. No lookup needed.
- **Grep is the universal tool.** `grep -r "MRK:<TAG>" /path/to/repo` gives exact match anywhere.
- **Each file's own NAV table** (top of file) lists only its own tags — drift-free because there is no flat list to keep in sync.
- **When adding a new section:** pick a prefix that matches the owning file's pattern above. Do not invent new prefix families without adding a row to this table.

---

## MRK:IDX_S1 — §1. Suite Overview | idx,s1,suite,overview | L44-63

| # | File | Mode | Purpose | Runs as |
|---|------|------|---------|---------|
| 00 | `00_pt-orc.sh` | all | Suite orchestrator — runs 01–07 sequentially; `--yes` suppresses all prompts | root |
| 01 | `01_dns_recon.sh` | PTE | DNS/OSINT recon — subdomain enum, IP resolution, live check → `scripts/targets.txt` | root |
| 02 | `02_ip_analysis.sh` | PTE | Passive IP intelligence — ASN, PTR, BGP, geo, cloud detection. No active probes. | any |
| 03 | `03_comp_scan.sh` | PTI+PTE | Network scan — TCP/UDP/enum/report, MSF DB-driven, phase-aware | root |
| 04 | `04_tls_scan.sh` | PTI+PTE | TLS/cert assessment — testssl, openssl, cipher enum, 10 security headers | root |
| 05 | `05_web_enum.sh` | PTI+PTE | Web enumeration — headers (×10), CORS, tech, gobuster, nikto, API, webcreds, WP-detect | root |
| 06 | `06_wpscan.sh` | PTI+PTE | WordPress detection sweep + full WPScan assessment | any |
| 07 | `07_service_verify.sh` | PTI+PTE | Priority probe queue from manual_followup MDs — Redis/MySQL/PG/Mongo/SMB/FTP/SSH/SMTP/SNMP/SSRF/TLS/headers/MSSQL/NFS/Telnet/IPMI/RDP/WinRM/web. Native→MSF→MANUAL chain. | root |

**Config:** all scripts source `pt-orc.conf` at startup — one file per engagement.
**Orchestrator auto-detection:** `00_pt-orc` prefers unversioned `0N_*.sh` when present; falls back to highest-versioned `0N_*_v*.sh`. Excludes `ACTUAL_RUN/`. `03_comp_scan.sh` uses the unversioned name.
**PTI flow:** start at 03 directly. Skip 01 and 02.
**PTE flow:** 01 → 02 → 03 → 04 → 05 → 06 → 07 (or `00_pt-orc --yes`).

---

## MRK:IDX_S2 — §2. Data Flow | idx,s2,data,flow | L64-82

| Script | Reads | Writes |
|--------|-------|--------|
| 00 | `pt-orc.conf` | `working/pt-orc_<TS>.log` |
| 01 | `pt-orc.conf` (TARGET_DOMAINS, TARGET_IPS) | `scripts/targets.txt`, `evidence/_dns/`, `working/dns_summary_<TS>.md` |
| 02 | `scripts/targets.txt` (or TARGET_IPS) | `evidence/_ip_analysis/<IP>/` (per-IP), `working/ip_range_report_<TS>.md` |
| 03 | `scripts/targets.txt` (PTE) or TARGET_SUBNETS/TARGET_IPS (PTI) | MSF DB, `evidence/_sweep/`, `evidence/_msf/`, `evidence/_exports/services_tcp_*.csv`, `working/tls_targets.txt` |
| 04 | `working/tls_targets.txt` | `evidence/<IP>/testssl_*`, `working/tls_summary_<TS>.md` |
| 05 | MSF DB or `--targets` file | `evidence/<IP>/headers_*` etc., `working/web_summary_<TS>.md`, `scripts/wp_targets.txt` (appends) |
| 06 | `scripts/wp_targets.txt` | `evidence/_wpscan/<label>/` (per-target), `working/wpscan_report_<TS>.md` |
| 07 | `working/manual_followup_*.md` (auto-discover latest), optionally `tls_summary_*.md`, `web_summary_*.md`, MSF DB | `working/verify_summary_<TS>.md`, `evidence/_verify/<IP>/`, `evidence/_msf/verify_*` |

**Key dependency:** `evidence/_exports/services_tcp_*.csv` — written by `export_db` at end of `phase_tcp`; used as CSV fallback by 03 enum phases and by 05 if DB unavailable. (04 reads `TARGETS_FILE` directly — no MSF DB query or CSV fallback.)
**TLS handoff:** `working/tls_targets.txt` written by `phase_enum`/`phase_enum_pte` in 03; consumed by 04.
**WP handoff:** `scripts/wp_targets.txt` populated by 05 WP detection; consumed by 06.

---

## MRK:IDX_S3 — §3. Engagement Config | idx,s3,engagement,config | L83-149

### pt-orc.conf — edit once per engagement

| Variable | Default | Set to |
|----------|---------|--------|
| `PROJECT_NAME` | `ClientCode-PTE-MonYear-Orc-0.76` | MSF workspace name — must match DB workspace exactly |
| `MODE` | `pte` | `pti` or `pte` |
| `TARGET_DOMAINS` | `""` | Space-separated domains (consumed by 01) |
| `TARGET_IPS` | `""` | Seed IPs in scope (01, 02, 03) |
| `TARGET_SUBNETS` | `""` | CIDRs — PTI only; **must be `""` for PTE** (03) |
| `TESTER_IP` | `""` | Outbound egress IP — scripts abort on mismatch (01, 03) |
| `TESTER_EXCLUDE_IPS` | `""` | Jump boxes / secondary hosts to exclude from scans (03) |
| `GLOBAL_TIER` | `normal` | `ghost\|normal\|loud\|evasion` — downgrade reactively if filtering observed |
| `SUBNET_TIER_MAP` | `()` | `"CIDR:tier"` per-zone overrides (03) — empty for PTE |
| `SHODAN_API_KEY` | `""` | Optional — Shodan (01, 02) |
| `CENSYS_API_ID/SECRET` | `""` | Optional — Censys (01) |
| `SECURITYTRAILS_API_KEY` | `""` | Optional — SecurityTrails (01) |
| `WPSCAN_API_TOKEN` | `""` | wpscan.com token — 25 free calls/day (06) |
| `WPSCAN_API_BUDGET` | `25` | Max API calls per day; 0 = no API (06) |
| `AMASS_BRUTE` | `0` | 1 = amass brute-force — **requires explicit RoE for PTE** (01) |
| `FAST_TCP_SCANNER` | `masscan` | Pass 1 backend for 03: `masscan`, `naabu`, or `db_nmap` |
| `MASSCAN_RATE_GHOST/NORMAL/LOUD` | `500/5000/10000` | masscan pps per tier (03) |
| `NAABU_THREADS_GHOST/NORMAL/LOUD` | `10/25/40` | naabu per-tier worker concurrency for Pass 1 (03) |
| `NAABU_THREADS` | `25` | Fallback/global naabu worker count if a per-tier value is unset (03) |
| `NAABU_TIMEOUT` | `1500` | naabu probe timeout in ms for Pass 1 (03) |
| `NAABU_RETRIES` | `1` | naabu retries for Pass 1 (03) |
| `DB_NMAP_FAST_MIN_RATE_*` | `2000/8000/20000` | fast `db_nmap` Pass 1 minimum rate shaping for `ghost/normal/loud` (03) |
| `DB_NMAP_FAST_MAX_RATE_*` | `15000/50000/120000` | fast `db_nmap` Pass 1 maximum rate shaping for `ghost/normal/loud` (03) |
| `DB_NMAP_FAST_MIN_HOSTGROUP_*` | `16/32/64` | fast `db_nmap` Pass 1 minimum hostgroup shaping for `ghost/normal/loud` (03) |
| `DB_NMAP_FAST_MAX_HOSTGROUP_*` | `64/128/256` | fast `db_nmap` Pass 1 maximum hostgroup shaping for `ghost/normal/loud` (03) |
| `DB_NMAP_FAST_MAX_RETRIES_*` | `2/2/1` | fast `db_nmap` Pass 1 retry count for `ghost/normal/loud` (03) |
| `DB_NMAP_FAST_INITIAL_RTT_TIMEOUT_*` | `150ms/100ms/50ms` | fast `db_nmap` Pass 1 initial RTT timeout by tier (03) |
| `DB_NMAP_FAST_MAX_RTT_TIMEOUT_*` | `500ms/350ms/200ms` | fast `db_nmap` Pass 1 max RTT timeout by tier (03) |
| `DB_NMAP_FAST_HOST_TIMEOUT_*` | `2m/1m/30s` | fast `db_nmap` Pass 1 host timeout by tier (03) |
| `DB_NMAP_FAST_DEFEAT_RST_RATELIMIT_*` | `1/1/1` | toggles `--defeat-rst-ratelimit` for fast `db_nmap` Pass 1 by tier (03) |
| `MAX_PARALLEL_SCANS` | `4` | Concurrent masscan jobs (03) |
| `MASSCAN_INTERFACE` | `""` | Force NIC — set if masscan picks wrong interface on multi-homed host |
| `PTE_TARGETS_FILE` | `scripts/targets.txt` | 01 output → consumed by 02 + 03 |
| `WP_TARGETS_FILE` | `scripts/wp_targets.txt` | 05 output → consumed by 06 |

### Script-local defaults — tool behaviour, not engagement-specific

| Script | Variable | Default | Purpose |
|--------|----------|---------|---------|
| 01 | `THIRDPARTY_RANGES` | Cloudflare/Fastly/AWS/Azure CIDRs | CDN out-of-scope flag |
| 01 | `TAKEOVER_PATTERNS` | 9 patterns | Subdomain takeover fingerprints |
| 01 | `TOOL_TIMEOUT` | `120` | Generic tool timeout (s) |
| 02 | `IPINFO_DELAY` | `1` | Seconds between ipinfo.io calls (50k req/month cap) |
| 02 | `GEO_DELAY` | `1` | Seconds between ip-api.com calls (45 req/min cap) |
| 02 | `CLOUD_ORGS_REGEX` | AWS/GCP/Azure/CF/… | ASN cloud detection pattern |
| 03 | `BASELINE_PORTS` | 33 common ports | Always included in Pass 2 regardless of masscan results |
| 04 | `TESTSSL_TIMEOUT` | `300` | Seconds per host for testssl |
| 04 | `TARGETS_FILE` | `working/tls_targets.txt` | Override with `--targets` |
| 05 | `WORDLIST` | `/usr/share/wordlists/dirb/common.txt` | Gobuster wordlist |
| 05 | `GOBUSTER_TIMEOUT` | `180` | Seconds per host for gobuster |
| 05 | `CURL_TIMEOUT` | `10` | Max seconds per curl request |
| 05 | `CURL_CONNECT` | `5` | curl connect timeout |
| 06 | `DETECT_PORTS` | `80 443 8080 8443` | Ports probed during `--detect` sweep |
| 06 | `DETECT_TIMEOUT` | `8` | HTTP probe timeout per host in `--detect` sweep |
| 06 | `TIER` | `normal` | Controls WPScan throttle and threads |
| 06 | `WPSCAN_TIMEOUT` | `300` | Seconds per target for wpscan |
| 06 | `WPSCAN_THREADS` | `5` | Default wpscan thread count (1 in evasion) |
| 06 | `WPSCAN_ENUMERATE` | `vp,vt,u,tt,cb,dbe` | Enumeration targets passed to wpscan |

---

## MRK:IDX_S4 — §4. Evidence Directory Layout | idx,s4,evidence,directory,layout | L150-241

```
<engagement>/
├── scripts/
│   ├── pt-orc.conf                 — engagement config (edit once)
│   ├── 00–06_*.sh / legacy versioned scripts
│   ├── targets.txt                 — 01 output → 02 + 03 input
│   └── wp_targets.txt              — 05 output → 06 input
│
├── working/                        — all consolidated reports + handoff files
│   ├── pt-orc_<TS>.log             — 00 orchestrator run log
│   ├── tls_targets.txt             — 03 → 04 handoff (host:port)
│   ├── dns_summary_<TS>.md         — 01 summary
│   ├── ip_range_report_<TS>.md     — 02 consolidated report
│   ├── tls_summary_<TS>.md         — 04 consolidated report
│   ├── web_summary_<TS>.md         — 05 consolidated report
│   ├── wpscan_report_<TS>.md       — 06 consolidated report
│   └── manual_followup_<TS>.md     — 03 phase_report follow-up items
│
├── evidence/
│   ├── _sweep/                     — 03/04/05: scan output and run logs
│   │   ├── scan_<TS>.log                        ← 03 orchestration log
│   │   ├── tls_scan_<TS>.log                    ← 04 run log
│   │   ├── web_enum_<TS>.log                    ← 05 run log
│   │   ├── targets_<tier>.txt
│   │   ├── targets_all_sweep.txt
│   │   ├── targets_udp_fallback.txt
│   │   ├── masscan_fast_<tier>_<target>_<TS>.xml
│   │   ├── masscan_fast_<tier>_<target>_<TS>.log
│   │   ├── tcp_fast_evasion_<TS>.{nmap,xml,gnmap}
│   │   ├── tcp_deep_<tier>_<TS>.{nmap,xml,gnmap}
│   │   ├── nse_common_<TS>.{nmap,xml,gnmap}
│   │   ├── udp_<IP>_<TS>.{nmap,xml,gnmap}
│   │   ├── udp_fallback_<TS>.{nmap,xml,gnmap}
│   │   └── arp_discovery_<TS>.{nmap,xml,gnmap}
│   │
│   ├── _msf/                       — rc files + spool logs (tail -f *.log to follow live)
│   │   ├── <label>_<TS>.rc
│   │   ├── <label>_<TS>.log
│   │   ├── import_<label>_<TS>.rc
│   │   └── export_<phase>_<TS>.rc
│   │
│   ├── _exports/                   — MSF DB CSV snapshots per phase (03)
│   │   ├── hosts_<phase>_<TS>.csv
│   │   ├── services_<phase>_<TS>.csv   ← services_tcp_*.csv = CSV fallback source
│   │   └── notes_<phase>_<TS>.csv      ← NSE script output
│   │
│   ├── _dns/                       — 01 DNS/OSINT output
│   │   ├── crt_<domain>_<TS>.txt
│   │   ├── subfinder_<domain>_<TS>.txt
│   │   ├── amass_<domain>_<TS>.txt
│   │   ├── all_subdomains_<domain>_<TS>.txt
│   │   ├── takeover_candidates_<TS>.txt
│   │   └── httpx_<TS>.txt
│   │
│   ├── _ip_analysis/               — 02 per-IP OSINT output
│   │   └── <IP_safe>/
│   │       ├── whois_<IP_safe>.txt
│   │       ├── bgp_<IP_safe>.json
│   │       ├── geo_<IP_safe>.json
│   │       ├── traceroute_<IP_safe>.txt
│   │       ├── shodan_<IP_safe>.txt
│   │       └── summary_<IP>.md
│   │
│   ├── _wpscan/                    — 06 per-target WPScan output
│   │   └── <label>/
│   │       ├── wpscan_basic_<TS>.txt
│   │       ├── wpscan_full_<TS>.txt
│   │       ├── xmlrpc_<TS>.txt
│   │       ├── wpjson_users_<TS>.txt
│   │       └── summary_<TS>.md
│   │
│   └── <IP>/                       — per-host output (03 enum, 04 TLS, 05 web)
│       ├── cert_<port>_<TS>.txt
│       ├── tls_legacy_<port>_<TS>.txt
│       ├── testssl_<port>_<TS>.{html,json,log,console.txt}
│       ├── nmap_tls_<port>_<TS>.*
│       ├── headers_<port>_<TS>.txt
│       ├── sec_headers_<port>_<TS>.txt
│       ├── cors_<port>_<TS>.txt
│       ├── whatweb_<port>_<TS>.txt
│       ├── gobuster_<port>_<TS>.txt
│       ├── nikto_<port>_<TS>.txt
│       ├── api_endpoints_<port>_<TS>.txt
│       └── nmap_webcreds_<port>_<TS>.*
│
└── screens/                        — 04 --grab-screens: SSL Labs / SecurityHeaders.com screenshots
```

---

## MRK:IDX_S5 — §5. Stealth Tier Reference | idx,s5,stealth,tier,reference | L242-277

| Parameter | ghost | normal | loud | evasion |
|-----------|-------|--------|------|---------|
| nmap timing | -T2 | -T3 | -T4 | -T1 |
| max-rate | 100 | 2000 | 5000 | 5 |
| min-rate | — | 500 | 3000 | — |
| min-hostgroup | 8 | 16 | 32 | 1 |
| max-retries | 2 | 4 | 3 | 1 |
| host-timeout | 10m | 5m | 2m | 30m |
| script-timeout | 3m | 2m | 1m | 5m |
| version-intensity | 3 | 5 | 7 | 1 |
| extra flags | — | — | — | `-f --source-port 443 --scan-delay 2s --randomize-hosts --data-length 25 -n` |
| NSE (-sC) in Pass 2 | yes | yes | yes | **no** |
| fast Pass 1 backend | backend-selectable | backend-selectable | backend-selectable | **no - nmap only** |
| naabu Pass 1 | yes if selected | yes if selected | yes if selected | **no - nmap only** |
| fast db_nmap Pass 1 | yes if selected | yes if selected | yes if selected | **no - evasion keeps dedicated nmap path** |
| masscan Pass 1 | yes (500 pps) | yes (5000 pps) | yes (10000 pps) | **no — nmap only** |
| gobuster threads (05) | 5 | 20 | 50 | 1 |
| whatweb aggression (05) | 1 | 3 | 4 | 1 |
| nikto (05) | yes | yes | yes | **skipped** |
| WPScan (06) | throttle 2000 / 1 thread | default | default | throttle 2000 / 1 thread |

**Set globally:** `GLOBAL_TIER` in `pt-orc.conf`.
**Override per subnet (PTI):** `SUBNET_TIER_MAP=("192.168.1.0/24:loud" "10.0.0.0/16:ghost")` — 03 only.
**Override at runtime:** `--tier <t>` flag on 03, 05, 06, or via 00 orchestrator.
**Pass 1 backend selection:** `FAST_TCP_SCANNER` chooses `masscan`, `naabu`, or `db_nmap` for `ghost|normal|loud`.
**Fast db_nmap note:** Pass 1 keeps the tiered model. `LOUD` matches the explicit high-speed preset; `NORMAL` and `GHOST` use more conservative defaults in `pt-orc.conf`.
**PTE default = normal.** Switch reactively per-CIDR when IP blocks, TCP resets, 429s, or CAPTCHA observed.

---

*PT-Orc v0.95 | TechGuard.*

<!-- L2 NAV:v1 → ../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
