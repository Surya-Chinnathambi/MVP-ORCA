---
name: pt-evidence
version: "0.72"
description: >
  [v0.72] L2 — Evidence processor. Converts raw tool output into structured finding
  stubs. Input: pasted tool output or file reference. Output: validated finding stub
  ready to append to Findings .md. Handles three-stream correlation and validation
  state assignment. Do NOT load directly — pt-orc dispatches this.
---

<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->

<!-- MRK:SKILL_NAV_TOC — Section index | nav,toc,index | L14-26 -->
<!-- - MRK:PT_EVIDENCE_RECEIVED — Received from L1 (pt-orc) | pt,evidence,received,l1,orc | L27-37 -->
<!-- - MRK:PT_EVIDENCE_EXIT — Exit Criteria | pt,evidence,exit,criteria | L38-47 -->
<!-- - MRK:PT_EVIDENCE_PIPELINE — Processing Pipeline | pt,evidence,pipeline,processing,steps | L48-154 | ⚠ read-toc-first -->
<!-- - MRK:PT_EVIDENCE_TOOL_GUIDE — Tool Output Interpretation Guide | pt,evidence,tool,guide,output | L155-225 | ⚠ read-toc-first -->
<!-- - MRK:PT_EVIDENCE_OUTPUT — Output — Evidence Processing Block | pt,evidence,output,processing,block | L226-263 -->
<!-- NAV-LEN: 5 entries | Integrity-hash: 823035b042462217 | Last-indexed: 2026-04-24T20:37:14Z -->

# pt-evidence — Evidence Processor
*L2 — Loaded when raw output needs processing into structured findings. Drop after stubs produced.*

---

## MRK:PT_EVIDENCE_RECEIVED — Received from L1 (pt-orc) | pt,evidence,received,l1,orc | L27-37

On dispatch, L1 passes:
- Raw output: pasted text OR file reference (`evidence/<IP>/<file>` or `evidence/_wpscan/<label>/<file>`)
- Source tool: what generated the output (or "unknown" if unclear)
- Target IP and port/service if known
- Existing findings index (to check for duplicates / updates vs. new)
- Any analyst annotation accompanying the output

---

## MRK:PT_EVIDENCE_EXIT — Exit Criteria | pt,evidence,exit,criteria | L38-47

- All issues in the raw output identified and classified
- Each issue: new stub produced OR existing stub updated
- Validation states assigned
- Nothing in the raw output left unclassified
- Output block handed to L1

---

## MRK:PT_EVIDENCE_PIPELINE — Processing Pipeline | pt,evidence,pipeline,processing,steps | L48-154
<!-- NAV-RULE: read-toc-first -->

### Step 1 — Parse and Inventory

Read the raw output. Produce an inventory of all security-relevant items found:

```
[ITEM] <brief description> | <tool signal> | <potential severity>
```

Flag items that are:
- Definitive findings (clear misconfiguration, confirmed vulnerability, anonymous access, etc.)
- Potential findings (version number requiring CVE check, non-default behaviour, unexpected open port)
- Noise (expected services, informational only, tester's own IPs)
- Ambiguous (needs second stream or analyst confirmation)

**DNS/OSINT output (from 01_dns_recon.sh or pasted recon output):**
- Subdomain takeover candidate → definitive finding (Critical or High depending on service)
- Third-party/CDN IP in scope → flag as out-of-scope, do not create finding
- Zone transfer success (AXFR) → High finding — internal DNS data exposed
- Subdomain resolving to internal RFC1918 IP → flag for scope review
- CNAME pointing to unclaimed service → definitive finding (takeover candidate)

**IP range analysis output (from 02_ip_range_analysis.sh):**
- Cloud-hosted IP confirmed client-owned → inventory note only; no finding
- Cloud-hosted IP with unclear ownership → flag as open issue; do not create finding until confirmed
- BGP/ASN mismatch with stated scope → flag for client confirmation
- Multiple IPs sharing ASN/prefix → group in inventory; may indicate scope expansion opportunity

### Step 2 — Deduplicate Against Existing Findings

For each item, check against the findings index from L1:
- **Exact match:** Update existing stub — add this evidence as additional stream. Promote validation state if warranted.
- **Related match:** Note relationship in both stubs.
- **New:** Assign next available FID (or placeholder `F-NEW-<desc>` if FID sequence not confirmed).

### Step 3 — Three-Stream Classification

For each issue, determine which streams are populated:

| Stream | Signal |
|---|---|
| MSF DB | Output from `db_nmap`, `hosts`, `services`, or imported scan |
| Automated | Tool output: nmap, testssl, masscan, snmpwalk, nikto, enum4linux, wpscan, hydra, etc. |
| Manual | curl, smbclient, dig, manual terminal session, analyst observation |

Assign validation state:
- 1 stream only → `detected`
- 2 streams or 1 stream + analyst annotation → `suspected`
- Confirmed by exploitation / active proof / 2 independent tool streams → `validated`
- Validated + screenshot or console log excerpt → `high_confidence`

### Step 4 — Severity Assignment

Assign severity based on **impact**, not tool rating:

| Severity | Basis |
|---|---|
| Critical | RCE, unauthenticated admin access, exfiltration path, privileged credential exposure |
| High | Strong path to Critical (e.g. write access to sensitive share, auth bypass, CVE with known exploit) |
| Medium | Information disclosure, weak auth, exploitable with credentials or chaining |
| Low | Minor misconfiguration, hardening gap, limited exposure |
| Informational | No direct risk; context for the assessor |

**Precautionary rule:** If severity is Critical or High based on version match / CVE but exploitation was not performed or not possible under RoE — mark `[Precautionary]` and set confidence to LIKELY. Do not downgrade severity; downgrade confidence instead.

**PTI scale:** No Critical tier. High is the maximum severity for internal engagements. Any finding that would be Critical externally is rated High in PTI.

**PTE external exposure escalation:** When processing output from a PTE engagement, apply the following severity baseline — external exposure alone escalates severity regardless of exploitability:

| Service externally exposed | Minimum severity |
|---|---|
| Any database (MySQL, MSSQL, MongoDB, Redis, Elasticsearch) | Critical candidate |
| Telnet | Critical |
| RDP | High |
| LDAP (anonymous bind or open) | High |
| FTP (anonymous login) | High |
| SNMP (public community) | High |
| Admin panel / management interface | High |
| WordPress XML-RPC enabled (brute vector) | Medium–High |
| WordPress user enumeration via REST API | Medium |

Cross-reference with pt-enum external exposure severity table when mode is PTE.

### Step 5 — Produce Stubs

One stub per finding using the schema from pt-enum. For updates to existing stubs, produce a delta block:

```markdown
## UPDATE: <FID> — <Title>

### New Evidence Added
| Stream | Path | Description |
|---|---|---|
| <stream> | <path> | <what it adds> |

### Validation State Change
<old state> → <new state>
Basis: <what justified the promotion>

### Notes
<any analyst context or caveats>
```

---

## MRK:PT_EVIDENCE_TOOL_GUIDE — Tool Output Interpretation Guide | pt,evidence,tool,guide,output | L155-225
<!-- NAV-RULE: read-toc-first -->

Quick reference for common tools — what to look for:

**nmap / db_nmap**
- Open ports → inventory; unexpected ports → potential finding
- Service version → CVE lookup trigger
- Script output (smb-protocols, smb2-security-mode, ftp-anon, snmp-info) → direct finding signals
- OS fingerprint → inventory; EOL OS → finding

**testssl**
- Grade F / expired cert → Critical or High
- SSLv2/SSLv3/TLS 1.0/1.1 enabled → Medium or High depending on exposure
- Weak ciphers (RC4, DES, EXPORT) → Medium-High
- Missing HSTS / cert chain issues → Low-Medium
- POODLE, BEAST, LUCKY13, LOGJAM, SWEET32, DROWN, Heartbleed → severity per CVE

**snmpwalk / snmp-check**
- Response to `public` community → confirmed SNMPv1/v2c misconfiguration
- Sensitive MIB data (interface IPs, routing table, installed software) → escalates severity

**enum4linux / enum4linux-ng**
- Null session → High
- User enumeration → Medium
- Share list without auth → High if sensitive shares exposed

**showmount / nfs**
- `*` in exports or world-accessible export → Critical (write) or High (read)
- Confirm with mount attempt if RoE permits

**ftp (nmap ftp-anon script or manual)**
- Anonymous login → confirm with STOR test
- Write confirmed → Critical (persistent access path)
- Read only → High (data exposure)

**nikto / dirb / ffuf**
- Admin panels exposed → High
- Default credentials page → High
- Backup files / config exposure → Medium-High
- Directory listing → Low-Medium

**CrackMapExec / crackmapexec smb**
- Signing: False → High (relay attack surface)
- Guest / anonymous access → High
- Password policy → context for brute force findings

**wpscan / 06_wpscan.sh output**
- Vulnerable plugin with known CVE → High if RCE/auth bypass, Medium if info disclosure
- Vulnerable theme → same severity logic as plugin
- XML-RPC enabled → Medium (brute-force vector); escalate if paired with user enumeration
- User enumeration via REST API (`/wp-json/wp/v2/users`) → Medium
- wp-config.php / debug.log exposed → Critical (credentials) or High (debug data)
- readme.html / install.php exposed → Low-Medium (version disclosure, installer exposure)
- wp-admin login with no rate limiting → Medium
- Outdated WordPress core with known CVE → severity per CVE

**02_ip_range_analysis.sh / ip_range_report**
- Cloud-hosted IP with client-confirmed ownership → inventory note, no finding
- Cloud-hosted IP (AWS/GCP/Azure/CF) not confirmed client-owned → open issue, do not scan
- IP in BGP prefix not matching stated ASN → flag for client review
- PTR resolving to cloud provider pattern → cloud flag; verify ownership

**05_web_enum.sh headers / CORS output**
- Missing security headers (CSP, HSTS, X-Frame-Options, etc.) → Low-Medium per header
- CORS reflected origin + `Access-Control-Allow-Credentials: true` → High
- CORS wildcard (`*`) without credentials → Low-Medium
- API endpoint returning non-404 with unexpected data → potential finding; requires follow-up

---

## MRK:PT_EVIDENCE_OUTPUT — Output — Evidence Processing Block | pt,evidence,output,processing,block | L226-263

Return to L1 on exit:

```markdown
## Evidence Processing — <OrgCode> — <source> — <YYYYMMDD>

### Source
- Tool: <tool name>
- Target: <IP>:<port> or <hostname> or <WordPress URL>
- File: evidence/<IP>/<filename> (or evidence/_wpscan/<label>/<filename>) (or "pasted")

### Items Identified
| Item | Classification | Action |
|---|---|---|
| XML-RPC enabled, methodResponse returned | New finding — Medium (brute vector) | F-NEW-xmlrpc → stub below |
| WP user enumeration via REST API | New finding — Medium | F-NEW-wp-usenum → stub below |
| readme.html exposed | Low | F-NEW-wp-readme → stub below |

### Stubs Produced
<paste stubs here>

### Updates to Existing Findings
<paste delta blocks here>

### Unclassified / Needs Follow-up
- <item requiring second stream, analyst verification, or client input>

### Recommended Next Actions
- <e.g. "Confirm wp-config.php exposure with curl; screenshot required for high_confidence">
- <e.g. "Confirm cloud IP ownership with client before including in active scan">
```

---
*pt-evidence SKILL.md v0.72 — L2 | dispatched by pt-orc*

<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
