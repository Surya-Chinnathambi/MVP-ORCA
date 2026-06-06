---
name: pt-recon
version: "0.72"
description: >
  [v0.72] L2 — Passive reconnaissance, OSINT, and broad sweep (Stages 1–2). Loaded by
  pt-orc when performing host discovery, DNS enumeration, IP range analysis, external
  surface mapping, or initial sweep. Drop after stage exit criteria met.
  Do NOT load directly — pt-orc dispatches this.
---

<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->

<!-- MRK:SKILL_NAV_TOC — Section index | nav,toc,index | L14-27 -->
<!-- - MRK:PT_RECON_RECEIVED — Received from L1 (pt-orc) | pt,recon,received,l1,orc | L28-38 -->
<!-- - MRK:PT_RECON_EXIT — Exit Criteria | pt,recon,exit,criteria,handback | L39-48 -->
<!-- - MRK:PT_RECON_S1 — S1 — Passive Reconnaissance | pt,recon,s1,passive,reconnaissance | L49-113 | ⚠ read-toc-first -->
<!-- - MRK:PT_RECON_S2 — S2 — Broad Sweep / Surface Mapping | pt,recon,s2,broad,sweep | L114-163 | ⚠ read-toc-first -->
<!-- - MRK:PT_RECON_RETURN — Return Pass Behaviour | pt,recon,return,pass,behaviour | L164-175 -->
<!-- - MRK:PT_RECON_OUTPUT — Output — Recon Summary Block | pt,recon,output,summary,block | L176-228 -->
<!-- NAV-LEN: 6 entries | Integrity-hash: f1bc046a440e863c | Last-indexed: 2026-04-24T20:37:14Z -->

# pt-recon — Reconnaissance and Sweep
*L2 — Loaded for S1/S2. Drop when sweep complete and host/service inventory handed back to L1.*

---

## MRK:PT_RECON_RECEIVED — Received from L1 (pt-orc) | pt,recon,received,l1,orc | L28-38

On dispatch, L1 passes:
- Scope: subnet CIDRs (PTI) or domain list (PTE)
- Tester IPs (to exclude from findings)
- MSF workspace name
- Existing host list (if return pass — do not re-document known hosts)
- Pass type: `INITIAL` or `RETURN_PASS <N> — <reason>`

---

## MRK:PT_RECON_EXIT — Exit Criteria | pt,recon,exit,criteria,handback | L39-48

- **PTI:** All in-scope subnets swept; host/service inventory populated in MSF DB; `evidence/_exports/hosts_<phase>_<TS>.csv`, `services_<phase>_<TS>.csv`, and `notes_<phase>_<TS>.csv` on disk; `working/target_priority_<YYYYMMDD>.md` produced.
- **PTE:** Subdomain list finalised; IP ownership confirmed via 02 (`ip_range_report` reviewed); cloud-hosted IPs flagged and RoE verified; `scripts/targets.txt` populated; takeover candidates and third-party exclusions reviewed; initial port scan complete on confirmed in-scope IPs.
- **Return pass:** Specific objective stated by L1 is complete; new findings/hosts appended to inventory.

On exit: produce **Recon Summary Block** (see Output section) and hand to L1 for state snapshot update.

---

## MRK:PT_RECON_S1 — S1 — Passive Reconnaissance | pt,recon,s1,passive,reconnaissance | L49-113
<!-- NAV-RULE: read-toc-first -->

### PTI — Internal Passive

Passive observation before any active packet. Listen on interface, review DHCP leases, check any provided network documentation.

Goals:
- Identify broadcast traffic (MDNS, NBNS, LLMNR, ARP)
- Note any exposed credentials or sensitive data in clear-text protocols
- Map domain name, NetBIOS name, any visible DCs

L3 commands: load `pt-commands` → group **PASSIVE / CAPTURE**

### PTE — External OSINT and Surface Mapping

**Source IP (VPN exit):** Before any active probe, verify tester outbound IP matches the
whitelisted VPN exit IP in scope. Set `TESTER_IP` in scripts 01 and 03. Re-verify at the
start of each active phase — VPN exits can rotate. Script will abort on mismatch.

**Stealth tier:** Default `normal` for PTE. Use `evasion` reactively if WAF/IDS/filtering observed. Set `GLOBAL_TIER` in scripts before running.

**PTE S1 sequence — two scripts, run in order:**

#### Step 1 — Run `01_dns_recon.sh`

Primary DNS/OSINT automation. Produces `scripts/targets.txt`.

- crt.sh, subfinder, amass, theHarvester (free sources only), SecurityTrails, Censys (API-key gated), Shodan per-domain + per-IP (API-key gated)
- AXFR zone transfer attempts on all nameservers (`AMASS_BRUTE=0` by default — requires explicit RoE to enable)
- DNS brute force via dnsrecon
- CNAME tracking + third-party/CDN detection and exclusion
- Subdomain takeover fingerprinting (9 patterns)
- httpx live verification
- Outputs: `evidence/_dns/`, `scripts/targets.txt`, `working/dns_summary_<TS>.md`

**Ownership confirmation rule:** Every IP in `targets.txt` must be confirmed client-owned before scanning. Third-party/CDN IPs are automatically excluded by 01. Any manually added IPs must be verified.

#### Step 2 — Run `02_ip_range_analysis.sh` (after 01, before 03)

Passive IP intelligence — **no direct probes to targets**. Reads `scripts/targets.txt`.

- WHOIS/ASN ownership per IP (OrgName, ASN, netname, country, CIDR)
- Reverse DNS (PTR) — flags cloud PTR patterns
- BGP info via bgpview.io (rate-limited: `BGP_DELAY=2s`)
- Geolocation via ip-api.com (rate-limited: `GEO_DELAY=1s`)
- Cloud/CDN detection — ASN name + org + PTR vs `CLOUD_ORGS_REGEX` (AWS, GCP, Azure, Cloudflare, Fastly, etc.)
- Optional traceroute topology (fallback to `tracepath` if not root)
- Optional Shodan host summary per scope IP (`SHODAN_API_KEY` required)
- Outputs: `evidence/_ip_analysis/<IP_safe>/` per IP, consolidated `ip_range_report_<TS>.md`

**Cloud IP rule:** Any IP flagged cloud-hosted by 02 must be reviewed before scanning. Confirm ownership with client. Cloud-confirmed client-owned = proceed; unclear = open issue, do not scan. Document in state snapshot: `Cloud-hosted IPs flagged by 02`.

**Manual supplement / return pass:** For targeted follow-up not covered by 01/02:
L3 commands: load `pt-commands` → group **DNS / OSINT**

Key outputs summary:
- `evidence/_dns/` — all raw DNS/OSINT tool output (01)
- `evidence/_ip_analysis/` — per-IP WHOIS/ASN/BGP/geo/cloud output (02)
- `scripts/targets.txt` — confirmed in-scope IPs (input to `03 --mode pte` and `02`)
- `working/dns_summary_<TS>.md` — analyst summary with takeover candidates (01)
- `ip_range_report_<TS>.md` — consolidated IP ownership, cloud flags, ASN grouping (02)

---

## MRK:PT_RECON_S2 — S2 — Broad Sweep / Surface Mapping | pt,recon,s2,broad,sweep | L114-163
<!-- NAV-RULE: read-toc-first -->

### PTI — Network Sweep

**Primary automation:** Run `03_comprehensive_scan.sh --mode pti`.
TCP SYN with `-Pn` as primary discovery. Optional ARP sweep (`--phase discovery`) for local segments — not included in `--phase all`.

Goals:
- Discover all live hosts across in-scope subnets (SYN scan, not ping)
- Identify OS fingerprints at sweep level
- Produce initial port map for prioritisation
- Export hosts, services, **and notes** CSVs from MSF DB after each phase

L3 commands (manual/supplement): load `pt-commands` → group **SWEEP**

`target_priority.md` schema:
```markdown
# Target Priority — <OrgCode> — <YYYYMMDD>

## Priority 1 — Immediate (servers, gateways, network devices)
| IP | Hostname | OS | Key Ports | Reason |
|---|---|---|---|---|

## Priority 2 — Standard (workstations, printers)
| IP | Hostname | OS | Key Ports | Reason |
|---|---|---|---|---|

## Priority 3 — Low (IoT, non-interactive)
| IP | Hostname | OS | Key Ports | Reason |
|---|---|---|---|---|

## Excluded from active testing
| IP | Reason |
|---|---|
```

### PTE — Perimeter Port Scan

**Primary automation:** Run `03_comprehensive_scan.sh --mode pte` after `01` and `02`.
Reads `scripts/targets.txt`. Two-pass TCP: masscan full-port Pass 1 → nmap version/NSE Pass 2 on open ports only. `services_tcp_*.csv` written by `export_db` at end of `phase_tcp` — enum phases use this as CSV fallback if psql unavailable.

Tier default: `normal`. Downgrade reactively to `ghost` or `evasion` if IP filtering, TCP resets, 429s, or CAPTCHA observed — per-CIDR via `SUBNET_TIER_MAP`.

Note: `-Pn` is mandatory — external hosts behind FW will not respond to ICMP.

L3 commands (manual/supplement): load `pt-commands` → group **SWEEP**

---

## MRK:PT_RECON_RETURN — Return Pass Behaviour | pt,recon,return,pass,behaviour | L164-175

When `pass_type = RETURN_PASS`:
1. Receive specific objective from L1 (e.g. "sweep new subnet", "re-check DNS", "run 02 on additional IPs").
2. Do not re-run or re-document work already in existing host inventory.
3. Scope all actions to the stated objective only.
4. Append new hosts/services to existing inventory — do not replace.
5. Mark new entries with `[RP<N> <date>]` in the Notes column.
6. Produce delta-only Recon Summary Block (new findings only).

---

## MRK:PT_RECON_OUTPUT — Output — Recon Summary Block | pt,recon,output,summary,block | L176-228

Return this block to L1 on exit:

```markdown
## Recon Summary — <OrgCode> — <YYYYMMDD> [INITIAL / RP<N>]

### Hosts Discovered
- Total live hosts: <N>
- New (this pass): <N>
- Per subnet: <subnet> → <N> hosts

### Key Observations (pre-enum — do not assign FID yet)
- <IP>: <banner / service / anomaly observed>

### Cloud/Ownership Notes (PTE — from 02_ip_range_analysis)
- <IP>: <ASN / Org / cloud provider — RoE confirmed Y/N>
- Takeover candidates: <subdomain → cname target>

### Evidence Produced
- evidence/_sweep/tcp_<tier>_<TS>.{nmap,xml,gnmap}
- evidence/_exports/hosts_<phase>_<TS>.csv
- evidence/_exports/services_<phase>_<TS>.csv
- evidence/_exports/notes_<phase>_<TS>.csv  ← NSE script output lives here
- [PTI] evidence/_captures/*.pcapng — if passive capture run
- [PTE] evidence/_dns/* — all DNS/OSINT tool output (01)
- [PTE] evidence/_ip_analysis/* — per-IP WHOIS/ASN/BGP/geo (02)
- [PTE] working/dns_summary_<TS>.md — takeover candidates, exclusions (01)
- [PTE] ip_range_report_<TS>.md — consolidated ownership + cloud report (02)

### Working Files Produced
- [PTI] working/target_priority_<YYYYMMDD>.md — host priority list by risk
- working/manual_followup_<TS>.md — script-generated follow-up list
- working/tls_targets.txt — HTTPS hosts for 04_tls_scan.sh

### MSF DB Status
- Hosts imported: <N>
- DB_DIRECT_AVAILABLE: <1 (psql working) | 0 (CSV fallback mode)>
- Caveats: <any misidentifications noted>

### Recommended Next (S3 targets, in order)
1. <IP> — <reason for priority>
2. <IP> — <reason>

### Open Issues Raised
- <scope ambiguity, ownership questions, cloud confirmation needed, exclusion queries>
```

---
*pt-recon SKILL.md v0.72 — L2 | dispatched by pt-orc*

<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
