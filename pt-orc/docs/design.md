<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../ORC-INDEX.md -->

<!-- MRK:DESIGN_NAV_TOC — Section index | nav,toc,index | L4-13 -->
<!-- - MRK:PATTERNS — Shared Patterns | patterns,shared | L14-61 -->
<!-- - MRK:GOTCHAS — Key Design Decisions and Gotchas | gotchas,key,design,decisions | L62-100 -->
<!-- - MRK:D03 — 03_comp_scan.sh Architecture | d03,comp,scan,sh,architecture | L101-167 -->
<!-- - MRK:TOOLS — Tool Dependencies | tools,tool,dependencies | L168-202 -->
<!-- NAV-LEN: 4 entries | Integrity-hash: f138e53067af5ba6 | Last-indexed: 2026-04-24T20:37:14Z -->

Load this file for structural changes, debugging, or when you need to understand WHY something works
the way it does. For function lookup load docs/funcs.md instead.

## MRK:PATTERNS — Shared Patterns | patterns,shared | L14-61

### RC Scan Model
Every db_nmap call goes through `run_rc_scan`:
```bash
run_rc_scan "<label>" <nmap_args>
# Writes: evidence/_msf/<label>_<TS>.rc   (audit trail)
#         evidence/_msf/<label>_<TS>.log  (spool -- tail -f to follow)
```

### DB Import Model (03 only)
```bash
run_db_import "<label>" file1.xml file2.xml ...
# Writes: evidence/_msf/import_<label>_<TS>.rc
# Filters: skips empty/missing files silently
```

### DRY_RUN Gate
```bash
[[ "${DRY_RUN:-0}" -eq 1 ]] && { log "  [DRY RUN] ..."; return 0; }
```
Applied in `run_rc_scan` and `run_db_import`.

### set +u / set -u Array Guard
Empty declared arrays throw `unbound variable` under `set -u` in bash 4.3. All loops:
```bash
set +u
for item in "${ARRAY[@]}"; do ...
done
set -u
```

### MSF DB Credentials
Read from `/usr/share/metasploit-framework/config/database.yml` by `parse_db_conf`.
Password exported as `MSF_DB_PASS`; passed as `PGPASSWORD` to psql.
`MSF_DB_HOST` hardcoded to `127.0.0.1` -- never Unix socket.
(Kali Unix socket uses peer auth, fails as root.)

### TESTER_IP Verification
01: always runs if TESTER_IP set. 03: PTE mode only. Both abort on mismatch (wrong VPN/interface).

### set -e Difference Between Scripts
02 and 06 use `set -euo pipefail` (includes `-e` -- any unhandled non-zero aborts).
01, 03, 04, 05 use `set -uo pipefail` (no `-e` -- callers handle errors explicitly).
Rule: add `|| true` in 02/06 wherever non-zero exit is expected and non-fatal.

---

## MRK:GOTCHAS — Key Design Decisions and Gotchas | gotchas,key,design,decisions | L62-100

| Topic | Decision / Gotcha |
|-------|-------------------|
| **masscan not a DB tool** | masscan output is XML; imported via `run_db_import` after all jobs finish. Never runs concurrent db_nmap -- DB lock contention. |
| **BASELINE_PORTS** | Merged into every Pass 2 and NSE sweep. Ensures minimum coverage if masscan finds nothing (wrong NIC, rate-limited switch). |
| **phase_sweep_nse** | Runs unconditionally after all tier scans. Uses `build_target_list` (no DB dependency). Also calls `run_db_import` -- DB gets populated even if masscan failed entirely. |
| **phase_udp fallback** | When `get_scan_hosts` returns empty, falls back to sweeping all configured targets with baseline UDP ports. |
| **evasion + masscan** | masscan cannot do `-f`/`--source-port 443`. Evasion tier uses nmap for Pass 1. `--host-timeout` stripped for evasion's full `-p-` scan. |
| **discovery not in "all"** | `--phase all` runs tcp->udp->enum->report. ARP discovery must be explicit: `--phase discovery`. |
| **TLS targets file** | `working/tls_targets.txt` written by `phase_enum`/`phase_enum_pte`. If 04 runs before 03 completes, file may be empty -- use `--host`. |
| **05 web ports** | DB query fixed list: `80,443,8080,8443,4443,8888,9443,9200,10443,8006`. Other ports: use `--host` or `--targets`. |
| **testssl command name** | Binary is `testssl` (no `.sh`). `--warnings batch` required -- without it testssl hangs on non-TLS ports. |
| **OpenSSL 3.x legacy probes** | `-ssl2`/`-ssl3` removed in OpenSSL 3.x. Script checks `openssl s_client -help` before each protocol. `unexpected eof` = actively rejected = correct. |
| **NSE notes in DB** | NSE output from `db_nmap --script` stored in MSF DB `notes` table. `export_db` exports notes CSV -- primary script output artifact. |
| **CIDR suffix in DB addresses** | masscan `db_import` stores addresses as `10.0.0.1/32` (inet type). All DB address queries use `host(address)` -- `split_part(inet, unknown, integer)` throws a type error, silently swallowed. In 04/05 `assess_host` strips CIDR suffix with `ip="${ip%%/*}"`. |
| **AUTO_YES=0 default** | Scope confirmation mandatory. `--yes` for PTI lab automation only. Never for PTE. |
| **rate_self_test live probe** | PTE mode: sends 10 actual SYN probes to first target. Prompts `Press ENTER / Ctrl-C` when AUTO_YES=0. Intentional. |
| **amass brute default=0** | DNS brute force triggers abuse-detection. Set 1 only with explicit RoE. |
| **theHarvester free sources** | Uses `google,bing,baidu,crt,dnsdumpster,hackertarget,certspotter` not `-b all`. `-b all` invokes API-keyed sources that error/timeout. |
| **VPN trigger ports (PTE)** | `phase_enum_pte` VPN check: 500/1194/1723 only. 4443/10443 are SSL-VPN web consoles -- HTTP section handles them; including here caused double-followup entries. |
| **CORS check in 05** | Origins: `https://evil.com`, `null`, `https://<IP>.evil.com`. Flags reflected origin and wildcard+credentials. Pure curl. |
| **WPScan evasion throttle** | `06_wpscan.sh` injects `--throttle 2000 --max-threads 1` for ghost/evasion. Without this, wpscan ignores tier. |
| **psql TCP only (v0.76+)** | `MSF_DB_HOST="127.0.0.1"` hardcoded. Unix socket peer auth fails as root. `DB_DIRECT_AVAILABLE=0` if TCP test fails. All of 03/04/05 use same TCP-only `parse_db_conf`. |
| **Three-tier fallback** | `get_live_hosts`, `get_open_tcp`, `port_open` -- DB first, then `_exports/services_tcp_*.csv`, then gnmap sweep files. Gnmap survives broken DB from start. CSV written by `export_db` end of `phase_tcp`. |
| **PTE tier default = normal** | Internet-facing hosts have background traffic. `evasion` wastes hours unnecessarily. Switch reactively via `SUBNET_TIER_MAP` on blocks/resets/429s. |
| **02 API rate limits** | ipinfo.io: 50k req/month (`IPINFO_DELAY=1`). ip-api.com: 45 req/min (`GEO_DELAY=1`). Do not reduce. |
| **06 API budget** | wpscan.com: 25 API calls/day. `WPSCAN_API_BUDGET` decrements per target. At 0, enum still works without API. |
| **WordPress detection** | 05 greps whatweb for `wordpress\|wp-content\|wp-login`. Appended idempotently to `scripts/wp_targets.txt`. WPScan not inline -- dedicated 06 for evidence, API budget, throttle. |
| **gobuster evasion** | 1 thread, 3000ms delay, random UA from 3-UA pool, shuffled wordlist via `shuf`. |
| **Shodan enrichment** | 01: per-domain + per-IP all DISCOVERED_IPS. 02: per-IP scope IPs. Both gated on `SHODAN_API_KEY`. |
| **Per-host evidence dirs** | Created lazily via `ip_dir()` in 03; hardcoded `$EVIDENCE_BASE/$ip` in 04/05. Same path scheme regardless of which script wrote it. |
| **--masscan-only legacy name** | Flag name is historical. Behavior is backend-agnostic fast-scan-only (Pass 1 + import, then stop). Works with masscan, naabu, and db_nmap backends. |
| **naabu import fidelity** | If `naabu_json_to_nmap_xml()` changes, validate that MSF still imports: hosts, open TCP ports, expected service rows for downstream phases. |
| **No exact CPU governor** | Tier-based rate and per-tier naabu -c shape load but do not guarantee exact CPU percentages. |
| **07 RPORT in MSF 6.4+** | Several MSF scanner modules reject RPORT (warn "Unknown datastore option: RPORT"). Module still runs but may silently probe default port instead of target port. Confirmed bad: mssql_ping. Audit pending -- see action-plan MRK:SUITE. |

---

## MRK:D03 — 03_comp_scan.sh Architecture | d03,comp,scan,sh,architecture | L101-167

### Runtime shape (main() execution order)
1. Root/safety checks
2. Load pt-orc.conf
3. Init directories and logs
4. Parse DB config, ensure MSF workspace
5. Detect tester/local exclusions
6. Print scope banner, confirm execution intent
7. Run selected phase(s)

Default `--phase all` flow: `tcp` -> `udp` -> `enum` or `enum_pte` -> `report`
`discovery` is explicit/optional -- not bundled into `all`.

### Fast TCP architecture (phase_tcp)

**Pass 1** (`ghost|normal|loud`):
- `masscan` backend: per-target parallel jobs, XML imported after all jobs finish via `run_db_import`
- `naabu` backend: per-target parallel JSONL jobs -> `naabu_json_to_nmap_xml()` -> `run_db_import`
- `db_nmap` backend: one sequential full-port scan per tier target list via `run_rc_scan`; MSF updated directly; open ports for Pass 2 extracted from written XML

**Pass 1 evasion:** always uses dedicated `nmap -p-` path -- masscan/naabu cannot do `-f`/`--source-port 443`.

**Pass 2** (`db_nmap`): `-sV -O`, `-sC` for non-evasion tiers. Ports = tier-wide union of Pass 1 open ports + `BASELINE_PORTS`. Default scripts applied to ports actually open per host, not blindly.

**Phase 2b** (`phase_sweep_nse`): unconditional common-port enrichment -- safety net if earlier data sparse.

**Phase 2c** (`phase_os_detect`): grouped by tier, uses `BASELINE_PORTS` union fast-scan-discovered ports.

### Data sources fallback hierarchy
1. Live PostgreSQL/MSF DB reads
2. Latest exported CSVs from `_exports/`
3. Parsed sweep gnmap files from `_sweep/`
4. Configured scope from `TARGET_SUBNETS` / `TARGET_IPS`

This hierarchy drives: live host determination, open TCP checks, enum targeting, OS targeting, UDP fallback.
**Critical:** configured scope is not the same as observed hosts. Changing this order silently widens scope or weakens evidence quality.

### Routing and exclusions
- `masscan_route_args_for_target()`: resolves interface/source/gateway hints; avoids inventing gateway for directly-attached subnets
- `masscan_supported_for_target()`: returns 0 if masscan routing viable; 1 if naabu/db_nmap preferred
- naabu is less dependent on router-MAC behavior than masscan -- preferred for directly-attached subnets with no usable gateway
- For `naabu`, interface selection applied but routing is less fragile

### Known risks and watchpoints
1. **Fallback order fragile** -- do not reorder DB -> CSV -> gnmap -> scope.
2. **Comment drift** -- behavior is dual-backend but comments may drift toward masscan phrasing.
3. **naabu import fidelity** -- validate `naabu_json_to_nmap_xml()` produces importable XML after any change.
4. **Routed vs on-link** -- masscan requires correct interface/gateway; naabu does not.
5. **--masscan-only** -- legacy flag name; behavior is backend-agnostic fast-scan-only.
6. **No exact CPU governor** -- rate/thread controls shape load; no CPU percentage guarantee.

### Safe modification guide
Classify the change before editing:
- Target selection | Fast scan backend | MSF import/export | Fallback data access
- Evidence naming | PTI/PTE behavior | Service enumeration logic

Pre-merge checklist:
- Does this widen scope?
- Does this alter what counts as a live host?
- Does this alter what counts as an open port?
- Does this alter how later phases discover prior evidence?
- Does this alter MSF import fidelity?
- Does this affect both masscan AND naabu paths consistently?

---

## MRK:TOOLS — Tool Dependencies | tools,tool,dependencies | L168-202

| Tool | Scripts | Used for | Install |
|------|---------|----------|---------|
| `nmap` | 03, 04, 05 | All scanning, db_nmap | `apt install nmap` |
| `masscan` | 03 | TCP Pass 1 full-port sweep (if FAST_TCP_SCANNER=masscan) | `apt install masscan` |
| `naabu` | 03 | TCP Pass 1 full-port sweep (if FAST_TCP_SCANNER=naabu) | ProjectDiscovery |
| `msfconsole` | 03, 04, 05 | db_nmap, db_import, workspace, export | Metasploit Framework |
| `psql` | 03, 04, 05 | Direct DB queries (TCP to 127.0.0.1) | `apt install postgresql-client` |
| `testssl` | 04 | Full TLS assessment | `apt install testssl.sh` (binary: `testssl`) |
| `httpx` | 01 | HTTP/S live verification | `go install github.com/projectdiscovery/httpx/cmd/httpx@latest` |
| `subfinder` | 01 | Subdomain enumeration | ProjectDiscovery |
| `amass` | 01 | Subdomain enum + brute | `apt install amass` |
| `theHarvester` | 01 | OSINT | `apt install theharvester` |
| `gobuster` | 01, 05 | DNS brute (01), dir brute (05) | `apt install gobuster` |
| `nikto` | 05 | Web vuln scan | `apt install nikto` |
| `whatweb` | 05 | Tech detection | `apt install whatweb` |
| `wpscan` | 06 | WordPress full assessment | `gem install wpscan` |
| `swaks` | 07 | SMTP relay test | `apt install swaks` |
| `onesixtyone` | 07 | SNMP community sweep | `apt install onesixtyone` |
| `smbclient` | 07 | SMB null session + share list | `apt install samba-client` |
| `whois` | 02 | ASN/ownership lookup | `apt install whois` |
| `traceroute` | 02 | Network topology | `apt install traceroute` (fallback: `tracepath`) |
| `shodan` | 01, 02 | Host summary (optional) | `pip install shodan` |
| `jq` | 04 | Parse testssl JSON for severity | `apt install jq` |
| `python3` | 01, 04 | crt.sh JSON parsing | standard |
| `curl` | all | HTTP probes, source IP verify | standard |
| `openssl` | 04, 05, 07 | Cert grab, legacy proto, TLS detect | standard |

---

*PT-Orc v0.95 | TechGuard.*

<!-- L2 NAV:v1 → ../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
