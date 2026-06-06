<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../ORC-INDEX.md -->

<!-- MRK:OPS_NAV_TOC — Section index | nav,toc,index | L4-16 -->
<!-- - MRK:OPS_SCRIPTS — Scripts at a Glance | ops,scripts,glance | L17-46 -->
<!-- - MRK:OPS_PIPELINE — Pipeline | ops,pipeline | L47-133 -->
<!-- - MRK:OPS_FLAGS — CLI Flags | ops,flags,cli | L134-221 -->
<!-- - MRK:OPS_OPERATIONS — Common Operations | ops,operations,common | L222-286 -->
<!-- - MRK:OPS_DIRS — Directory Structure | ops,dirs,directory,structure | L287-311 -->
<!-- NAV-LEN: 5 entries | Integrity-hash: 9b8a033656218134 | Last-indexed: 2026-04-24T20:37:14Z -->


*Operator cheat sheet — pipeline, flags, common commands. For code navigation see docs/funcs.md.*

---

## MRK:OPS_SCRIPTS — Scripts at a Glance | ops,scripts,glance | L17-46

**00 — Suite Orchestrator** `00_pt-orc.sh` | all modes | root
Runs all 7 scripts sequentially in one command. `--yes` suppresses all prompts. `--from N`, `--only N`, `--skip N` for partial/resume runs. Forwards `--mode`, `--tier`, `--dry-run` to each subscript. Step summary table with status + elapsed time. Log: `working/pt-orc_<TS>.log`.

**01 — DNS Recon** `01_dns_recon.sh` | PTE | root
Passive + active DNS enumeration. Produces `scripts/targets.txt` consumed by 02 and 03.

**02 — IP Range Analysis** `02_ip_analysis.sh` | PTE | no root
Passive OSINT per scope IP — no direct probes to targets. Run after 01, before 03.
WHOIS/ASN, reverse DNS, routing info (ipinfo.io), geolocation (ip-api.com), cloud/CDN detection, traceroute, optional Shodan. Groups IPs by ASN; flags cloud-hosted IPs for extra RoE care.

**03 — Comprehensive Scan** `03_comp_scan.sh` | PTI + PTE | root
Primary sweep and enumeration. Two-pass TCP (masscan → nmap), OS fingerprint, UDP, per-host NSE enum, MSF DB-driven throughout.
Phase-aware (`--phase tcp|udp|enum|report|all`). PTE default tier: `normal` — downgrade reactively if IP filtering, resets, or 429s observed.

**04 — TLS Scan** `04_tls_scan.sh` | PTI + PTE | root
Reads `working/tls_targets.txt` from 03. Full testssl assessment, cert grab, legacy protocol checks (ssl2/ssl3/tls1/tls1_1), security header analysis. Optionally runs GrabScores-v2.5.py (Playwright) for SSL Labs / SecurityHeaders.com screenshots.

**05 — Web Enum** `05_web_enum.sh` | PTI + PTE | root
Per-host web enumeration from MSF DB or target file. Tier-aware threading.
HTTP headers, CORS misconfig check, WhatWeb, Gobuster, Nikto, API endpoint discovery (25 paths), default credential checks (nmap http-default-accounts), WordPress detection.
Detected WordPress URLs appended to `scripts/wp_targets.txt` — WPScan is **not** run inline.

**06 — WPScan** `06_wpscan.sh` | PTI + PTE | no root
Two-phase WordPress assessment. Run after 05 (which populates `scripts/wp_targets.txt`), or standalone with `--detect`.
Full WPScan: plugins/themes/users/vulns, XML-RPC probe, `wp-json` user exposure, config file exposure, wp-admin check, security headers. API token: 25 free calls/day.

---

## MRK:OPS_PIPELINE — Pipeline | ops,pipeline | L47-133

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  PTE engagement flow                                                             │
│                                                                                  │
│  00_pt-orc.sh  (suite orchestrator — runs 01–07 sequentially)                   │
│  ├─ --yes, --from N, --only N, --skip N, --mode, --tier, --dry-run              │
│  └─ forwards step-specific flags to each subscript; prints summary table        │
│                    |                                                             │
│                    ▼                                                             │
│  01_dns_recon.sh                                                                 │
│  ├─ passive: crt.sh, subfinder, amass, theHarvester (free sources), Shodan      │
│  ├─ active:  AXFR, DNS brute; amass brute only if AMASS_BRUTE=1 (default:0)    │
│  ├─ httpx live-verify → evidence/_dns/httpx_<TS>.txt                            │
│  └─ OUTPUT: scripts/targets.txt  ← consumed by 02 + 03                          │
│                    |                                                             │
│                    ▼                                                             │
│  02_ip_analysis.sh  [PTE passive OSINT — no active probes to targets]     │
│  ├─ WHOIS/ASN lookup per IP                                                      │
│  ├─ Reverse DNS (PTR)                                                            │
│  ├─ BGP info (ipinfo.io API)                                                     │
│  ├─ Geolocation (ip-api.com)                                                     │
│  ├─ Cloud/CDN detection (AWS, GCP, Azure, Cloudflare, Fastly…)                  │
│  ├─ Traceroute topology                                                          │
│  ├─ Optional Shodan host summary                                                 │
│  └─ OUTPUT: evidence/_ip_analysis/ (per-IP), working/ip_range_report_<TS>.md   │
│                    |                                                             │
│                    ▼                                                             │
│  03_comp_scan.sh  (also runs standalone for PTI)                       │
│  ├─ Phase 1 [optional]: ARP discovery → MSF DB hosts                            │
│  ├─ Phase 2: TCP — masscan Pass 1 (all 65536 ports) → nmap Pass 2 deep         │
│  ├─ Phase 2b: NSE sweep — unconditional, BASELINE_PORTS + masscan results       │
│  ├─ Phase 2c: OS fingerprint — DB → CSV → gnmap → scope fallback chain          │
│  ├─ Phase 3: UDP — host list from DB/CSV/gnmap; fallback: scope sweep           │
│  ├─ Phase 4: Service enum — ports from DB/CSV/gnmap per host                    │
│  ├─ Phase 4 (PTE): condensed enum (ssh, http, snmp, ldap, rdp, ike, smtp)      │
│  ├─ Phase 5: Report — findings, FOLLOWUP_FILE, MSF export                       │
│  └─ SIDE OUTPUT: working/tls_targets.txt ← consumed by 04                      │
│                  scripts/wp_targets.txt  ← populated by 05, consumed by 06      │
│                    |                                                             │
│                    ▼                                                             │
│  04_tls_scan.sh                                                                  │
│  ├─ openssl cert grab + legacy protocol check (ssl2/ssl3/tls1/tls1_1)           │
│  ├─ testssl full scan (--warnings batch, --severity LOW, html+json+log)          │
│  ├─ nmap ssl-enum-ciphers (fast mode or testssl fallback)                        │
│  ├─ curl security headers + analysis                                             │
│  └─ OUTPUT: evidence/<IP>/testssl_<port>_<TS>.{html,json,log}                   │
│             working/tls_summary_<TS>.md                                          │
│                    |                                                             │
│                    ▼                                                             │
│  05_web_enum.sh                                                                  │
│  ├─ TARGET SOURCE: MSF DB (default) or --targets file or --host                 │
│  ├─ curl headers + security header analysis (9 headers checked)                 │
│  ├─ CORS misconfiguration check (3 attacker origins)                            │
│  ├─ whatweb tech detection                                                       │
│  ├─ gobuster dir brute (tier-aware threads)                                      │
│  ├─ nikto (skipped in evasion tier)                                             │
│  ├─ API endpoint probe (25 paths)                                                │
│  ├─ nmap http-default-accounts                                                   │
│  └─ WordPress detected → appends URL to scripts/wp_targets.txt                  │
│                    |                                                             │
│                    ▼                                                             │
│  06_wpscan.sh                                                                    │
│  ├─ Phase 1 [--detect]: curl WP detection sweep → populates wp_targets.txt      │
│  ├─ WPScan: plugins (vp), themes (vt), users (u), timthumbs, config backups     │
│  ├─ API token support with per-day budget counter (25 free calls/day)            │
│  ├─ XML-RPC probe, wp-json user enum, config file exposure                       │
│  ├─ wp-admin login exposure + rate-limit header check                            │
│  └─ OUTPUT: evidence/_wpscan/<label>/ (per-target), working/wpscan_report_<TS>.md │
│                    |                                                             │
│                    ▼                                                             │
│  07_service_verify.sh                                                            │
│  ├─ INPUT: working/manual_followup_*.md (auto-discovers latest)                  │
│  ├─ Priority probe queue per manual_followup flags                               │
│  ├─ Probes: Redis/MySQL/PG/Mongo/SMB/FTP/SSH/SMTP/SNMP/SSRF/TLS/              │
│  │   headers/MSSQL/NFS/Telnet/IPMI/RDP/WinRM/web-generic                       │
│  ├─ Probe chain: native → MSF module → MANUAL flag (3-tier)                     │
│  └─ OUTPUT: working/verify_summary_<TS>.md, evidence/_verify/<IP>/              │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**PTI flow:** Start at 03 directly (`--mode pti`). Set `TARGET_SUBNETS` and/or `TARGET_IPS`. Skip 01 and 02.
**PTE tier:** Default `normal`. Switch to `evasion` or `ghost` reactively if filtering observed — per-CIDR via `SUBNET_TIER_MAP`, or globally via `--tier`.

---

## MRK:OPS_FLAGS — CLI Flags | ops,flags,cli | L134-221

### 00_pt-orc.sh
```
--yes                 Bypass all interactive scope prompts across the suite
--mode <pti|pte>      Passed to scripts that accept it (02, 03, 06)
--tier <t>            ghost|normal|loud|evasion — passed to 03, 05, 06
--from <N>            Start from step N (1-7)
--only <N>            Run only step N
--skip <N>            Skip step N; repeatable (--skip 1 --skip 2)
--dry-run             No packets sent; passed to all scripts
--skip-active         01: skip AXFR and DNS brute-force
--fast                04+05: headers/tech detection only; skip gobuster+nikto
--skip-gobuster       05 only
--skip-nikto          05 only
--no-wp-detect        06: use existing wp_targets.txt; skip detection sweep
--continue-on-error   Continue to next step if a script fails
```

### 01_dns_recon.sh
```
--yes           Skip scope confirmation prompt
--dry-run       Print what would run; no packets sent
--skip-active   Passive sources only (no AXFR, no brute)
--append        Append to scripts/targets.txt (default: overwrite)
```

### 03_comp_scan.sh
```
--mode <pti|pte>        Engagement mode
--phase <name>          discovery|tcp|udp|enum|report|all
                        Note: "all" excludes discovery — run it explicitly
--continue              After --phase, continue all subsequent phases
--tier <t>              ghost|normal|loud|evasion — overrides GLOBAL_TIER
--yes                   Skip scope confirmation
--dry-run               Print db_nmap commands; no scanning
--decoys                Add -D RND:5 (PTE, requires RoE sign-off)
--idle-scan <zombie>    TCP idle scan via zombie IP (TCP phases only; RoE required)
```

### 04_tls_scan.sh
```
--targets <file>        File with host:port entries (default: working/tls_targets.txt)
--host <IP:PORT>        Single target (repeatable)
--fast                  Skip testssl; openssl + nmap ssl-enum-ciphers only
--output-dir <dir>      Screenshots dir (default: screens/)
--grab-screens          Run GrabScores-v2.5.py after testssl (needs Playwright)
--yes                   Skip scope confirmation prompt
--dry-run               Print db_nmap commands; no scanning
```

### 05_web_enum.sh
```
--targets <file>        File with host:port entries
--host <IP:PORT>        Single target (repeatable)
--from-db               Pull web hosts from MSF DB (default when no targets given)
--tier <t>              ghost|normal|loud|evasion
--skip-gobuster
--skip-nikto
--skip-api
--fast                  Headers + tech detection only (implies --skip-gobuster --skip-nikto)
--wordlist <path>       Gobuster wordlist
--dry-run
```

### 02_ip_analysis.sh
```
--yes                   Skip scope confirmation
--dry-run               Print commands; no network calls made
--mode <pti|pte>        Engagement mode
--targets "ip1 ip2"     Override TARGET_IPS inline
--shodan-key <key>      Override SHODAN_API_KEY inline
```

### 06_wpscan.sh
```
--yes                   Skip scope confirmation
--dry-run               Print wpscan commands; do not execute
--mode <pti|pte>
--tier <t>              ghost|normal|loud|evasion (controls throttle)
--api-token <token>     Override WPSCAN_API_TOKEN inline
--detect                Run WP detection sweep first, then scan
--detect-only           Detection sweep only; do not run wpscan
--targets-file <file>   Override WP_TARGETS_FILE
```

---

## MRK:OPS_OPERATIONS — Common Operations | ops,operations,common | L222-286

```bash
# ── New engagement setup — edit ONE file, then run ───────────────────────────
#    1. Copy and fill in pt-orc.conf (PROJECT_NAME, MODE, TARGET_DOMAINS, etc.)
#    2. All 7 scripts source it automatically — no other edits required.
nano pt-orc.conf

# ── Full suite — orchestrated (preferred) ────────────────────────────────────
sudo ./00_pt-orc.sh --yes                        # full run, no prompts
sudo ./00_pt-orc.sh --yes --from 3               # resume from comprehensive scan
sudo ./00_pt-orc.sh --yes --only 4               # TLS scan only
sudo ./00_pt-orc.sh --yes --skip 1 --skip 2     # skip DNS recon + IP analysis
sudo ./00_pt-orc.sh --yes --tier ghost           # all scripts at ghost tier
sudo ./00_pt-orc.sh --dry-run --yes              # rehearsal — no packets sent

# ── PTE manual step-by-step (for interactive scope review) ───────────────────
sudo ./01_dns_recon.sh                           # Step 1: DNS/OSINT → scripts/targets.txt
./02_ip_analysis.sh                        # Step 2: passive OSINT per IP
sudo ./03_comp_scan.sh --mode pte       # Step 3: scan
sudo ./04_tls_scan.sh                            # Step 4: TLS assessment
sudo ./05_web_enum.sh --from-db                  # Step 5: web enum → populates wp_targets.txt
./06_wpscan.sh                                   # Step 6: WPScan (if WordPress found)

# ── PTI full run ─────────────────────────────────────────────────────────────
sudo ./03_comp_scan.sh --yes

# ── Downgrade tier reactively if IP filtering observed ───────────────────────
sudo ./03_comp_scan.sh --mode pte --tier evasion

# ── Single phase, then stop ──────────────────────────────────────────────────
sudo ./03_comp_scan.sh --phase tcp --yes

# ── Single phase, continue through report ────────────────────────────────────
sudo ./03_comp_scan.sh --phase tcp --continue --yes

# ── Dry run rehearsal (no packets) ───────────────────────────────────────────
sudo ./03_comp_scan.sh --dry-run --yes

# ── TLS scan — single host, fast mode ────────────────────────────────────────
sudo ./04_tls_scan.sh --host 10.0.0.1:443 --fast --yes

# ── Web enum — specific target ───────────────────────────────────────────────
sudo ./05_web_enum.sh --host 10.0.0.1:8080

# ── WPScan — detect WordPress first, then scan ───────────────────────────────
./06_wpscan.sh --detect          # sweep + scan in one pass
./06_wpscan.sh --detect-only     # detection only; review wp_targets.txt first
./06_wpscan.sh                   # scan only (reads existing wp_targets.txt)

# ── IP range analysis — dry run preview ──────────────────────────────────────
./02_ip_analysis.sh --dry-run

# ── Follow a scan in progress ────────────────────────────────────────────────
tail -f evidence/_msf/tcp_deep_normal_<TS>.log

# ── Check what masscan found ─────────────────────────────────────────────────
grep -oP 'portid="\K\d+' evidence/_sweep/masscan_fast_*.xml | sort -un

# ── Dump all open services from DB export ────────────────────────────────────
cut -d, -f2,4,5 evidence/_exports/services_tcp_<TS>.csv | sort -u
```

---

## MRK:OPS_DIRS — Directory Structure | ops,dirs,directory,structure | L287-311

```
<engagement>/
  evidence/
    _sweep/        — masscan XML, nmap output (.nmap/.xml/.gnmap), session logs
    _msf/          — rc files + spool logs per scan call (tail -f *.log to follow)
    _exports/      — MSF DB CSV exports (hosts, services, notes) per phase
    _dns/          — 01: DNS/OSINT output
    _ip_analysis/  — 02: per-IP WHOIS/ASN/BGP/geo/cloud output
    _wpscan/       — 06: per-target WPScan output (consolidated report → working/)
    _captures/     — pcap files
    <IP>/          — per-host tool output (03 enum, 04, 05)
  screens/         — SSL Labs / SecurityHeaders.com screenshots (04 --grab-screens)
  scripts/         — 00–06 scripts + pt-orc.conf + targets.txt + wp_targets.txt
  reports/         — versioned .docx deliverables
  working/         — tls_targets.txt, all consolidated MD reports (02, 04, 05, 06), follow-up lists
```

---

*PT-Orc v0.95 | TechGuard.*

<!-- L2 NAV:v1 → ../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
