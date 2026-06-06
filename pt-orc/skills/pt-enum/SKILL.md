---
name: pt-enum
version: "0.72"
description: >
  [v0.72] L2 — Service enumeration and vulnerability assessment (Stages 3–5). Loaded by
  pt-orc when performing deep-dive on a specific service, protocol, or host. Dispatches
  L3 command groups by service/tech. PTI/PTE mode-aware — filters services and applies
  external exposure severity escalation in PTE mode. Drop after enumeration objective
  complete. Do NOT load directly — pt-orc dispatches this.
---

<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->

<!-- MRK:SKILL_NAV_TOC — Section index | nav,toc,index | L15-29 -->
<!-- - MRK:PT_ENUM_RECEIVED — Received from L1 (pt-orc) | pt,enum,received,l1,orc | L30-42 -->
<!-- - MRK:PT_ENUM_EXIT — Exit Criteria | pt,enum,exit,criteria,handback | L43-54 -->
<!-- - MRK:PT_ENUM_DISPATCH — L3 Dispatch Table | pt,enum,dispatch,l3,table | L55-104 | ⚠ read-toc-first -->
<!-- - MRK:PT_ENUM_APPROACH — Enumeration Approach by Stage | pt,enum,approach,enumeration,stage | L105-165 | ⚠ read-toc-first -->
<!-- - MRK:PT_ENUM_STUB_SCHEMA — Finding Stub Schema | pt,enum,stub,schema,finding | L166-204 | ⚠ same-commit:skills/pt-evidence/SKILL.md -->
<!-- - MRK:PT_ENUM_RETURN — Return Pass Behaviour | pt,enum,return,pass,behaviour | L205-215 -->
<!-- - MRK:PT_ENUM_OUTPUT — Output — Enum Summary Block | pt,enum,output,summary,block | L216-250 -->
<!-- NAV-LEN: 7 entries | Integrity-hash: 07a8298f74c1054f | Last-indexed: 2026-04-24T20:37:14Z -->

# pt-enum — Service Enumeration and Vulnerability Assessment
*L2 — Loaded per enumeration objective. Drop when finding stubs produced and handed back to L1.*

---

## MRK:PT_ENUM_RECEIVED — Received from L1 (pt-orc) | pt,enum,received,l1,orc | L30-42

On dispatch, L1 passes:
- Target: IP(s) and/or service/port(s) to enumerate
- Mode: `PTI` or `PTE` (determines service filter — see S3 table)
- Stealth tier: `ghost` / `normal` / `loud` / `evasion` (affects scan aggressiveness)
- Known services on target (from host/service inventory in state snapshot)
- Existing findings for this host (to avoid duplication)
- Pass type: `INITIAL` or `RETURN_PASS <N> — <reason>`
- Exploitation RoE (full / limited / no destructive)

---

## MRK:PT_ENUM_EXIT — Exit Criteria | pt,enum,exit,criteria,handback | L43-54

- Enumeration objective stated by L1 is complete
- All output saved to `evidence/<IP>/` (or `evidence/_wpscan/` for WordPress)
- Finding stubs produced for all identified issues
- Validation state assigned to each stub
- Evidence paths recorded

On exit: produce **Enum Summary Block** and finding stubs → hand to L1.

---

## MRK:PT_ENUM_DISPATCH — L3 Dispatch Table | pt,enum,dispatch,l3,table | L55-104
<!-- NAV-RULE: read-toc-first -->

Load `pt-commands` and navigate to the relevant group. Drop L3 after commands executed.

*Legend: PTI = internal only · PTE = external only · Both = applicable in both modes*

| Service / Tech | L3 Group | Mode | Trigger keywords |
|---|---|---|---|
| SMB / Windows shares | SMB | **PTI** | "SMB", "shares", "signing", "NTLM", "relay", "CrackMapExec", port 445/139 |
| NFS | NFS | **PTI** | "NFS", "exports", "showmount", "world-writeable", port 2049 |
| MQTT | MQTT | **PTI** | "MQTT", "broker", "topic", "subscribe", port 1883/8883 |
| IPMI / iLO / iDRAC | OOB | **PTI** | "iLO", "iDRAC", "IPMI", "BMC", "RomPager", port 623/443 |
| Network devices | NETDEV | **PTI** | "switch", "router", "CDP", "LLDP", Telnet/SSH to network gear |
| SNMP | SNMP | Both | "SNMP", "community string", "public", "MIB", port 161/162 |
| FTP | FTP | Both | "FTP", "anonymous", "write access", port 21 |
| TLS / HTTPS | TLS | Both | "TLS", "SSL", "certificate", "testssl", "cipher", "POODLE", port 443/8443 |
| HTTP / Web | HTTP | Both | "HTTP", "headers", "web app", "nikto", "directory", port 80/8080/8000 |
| WordPress | WP | Both | "WordPress", "WPScan", "wp-admin", "xmlrpc", "wp-config", "wp-json" |
| SSH | SSH | Both | "SSH", "OpenSSH", "version", "regreSSHion", port 22 |
| RDP | RDP | Both | "RDP", "remote desktop", "NLA", port 3389 |
| Telnet | TELNET | Both | "Telnet", port 23 — externally exposed = Critical |
| LDAP / AD | LDAP | Both | "LDAP", "Active Directory", "DC", "domain", port 389/636/3268 |
| Database | DB | Both | "MySQL", "MSSQL", "PostgreSQL", "MongoDB", port 1433/3306/5432/27017 — external = Critical |
| VPN / Gateway | VPN | Both | "VPN", "Zyxel", "FortiGate", "gateway", "firewall", port 500/4500/1194 |
| Mail | MAIL | **PTE** | "SMTP", "IMAP", "POP3", "open relay", port 25/110/143/465/587/993/995 |

**PTE mode:** Only dispatch L3 groups marked **Both** or **PTE** from the table above.
Services marked **PTI** (SMB, NFS, NETDEV, OOB, MQTT) are skipped in PTE unless the client
explicitly confirms external exposure — document rationale if overriding.

### L3 Dispatch Protocol

1. Identify service group(s) from the target/objective.
2. State: *"Loading pt-commands → [GROUP NAME] for [target]."*
3. Execute commands; save all output to `evidence/<IP>/` (WordPress: `evidence/_wpscan/<label>/`).
4. State: *"L3 [GROUP NAME] complete. Releasing L3 context."*
5. Process output into finding stubs directly. If raw output is voluminous or complex, flag to L1 (pt-orc) to dispatch pt-evidence — do not dispatch pt-evidence directly.

### WordPress (WP) — Special handling

When WordPress is detected by `05_web_enum.sh`, the URL is appended to `scripts/wp_targets.txt`. Full assessment is via `06_wpscan.sh` — do **not** attempt inline WPScan during 05. Dispatch WP enumeration group when:
- WordPress confirmed present and `07` output needs assessment/processing
- Manual follow-up needed on specific WP findings (XML-RPC, user enum, config exposure)
- WPScan not yet run and `--detect` needed to confirm WP presence

Output directory: `evidence/_wpscan/<label>/` (not `evidence/<IP>/` — WordPress output is always under `_wpscan/`)

---

## MRK:PT_ENUM_APPROACH — Enumeration Approach by Stage | pt,enum,approach,enumeration,stage | L105-165
<!-- NAV-RULE: read-toc-first -->

### S3 — Service Enumeration

**PTI vs PTE filter (automated by 03_comprehensive_scan.sh):**

| Service | PTI | PTE | Reason |
|---|---|---|---|
| SMB / NFS / RPC | ✓ | ✗ skip | Rarely externally exposed |
| OT/ICS (102/502/44818) | ✓ ghost only | ✗ skip | Not externally reachable |
| IPMI / MQTT | ✓ | ✗ skip | Internal management only |
| SSH / RDP / FTP | ✓ | ✓ | May be externally exposed |
| Web / TLS / LDAP / Mail / DB | ✓ | ✓ | Core external attack surface |
| VPN / Gateway ports | ✓ | ✓ | Perimeter — key PTE target |
| WordPress | ✓ | ✓ | Detected by 05; assessed by 07 |

**External exposure severity escalation (PTE only):**

| Service | External exposure severity |
|---|---|
| Database (any) externally exposed | Critical candidate |
| Telnet externally exposed | Critical |
| RDP externally exposed | High |
| LDAP externally exposed | High |
| FTP anonymous externally exposed | High |
| SNMP public externally exposed | High |
| WordPress XML-RPC exposed (brute vector) | Medium–High |
| WordPress user enumeration via REST API | Medium |

**PTI sequence within a host:** SMB/NFS/SNMP → web/TLS → application → authentication.
**PTE sequence within a host:** Web/TLS → VPN/gateway → auth → mail → SSH → databases → WordPress.

For each priority target:
1. Confirm open ports (from DB — already populated by 03_comprehensive_scan.sh).
2. For each relevant service (filtered by mode): dispatch L3 group → enumerate → capture output.
3. Identify misconfigurations, default credentials, anonymous access, outdated versions.
4. Assign initial finding stubs (`detected` or `suspected` state).
5. For PTE: apply external exposure severity escalation from table above.

### S4 — Vulnerability Assessment

For each finding stub at `suspected` or higher:
1. Cross-reference version against CVE databases / known vuln lists.
2. Attempt proof-of-concept where RoE permits and risk is low (banner grab, safe checks).
3. Promote validation state where evidence supports it.
4. Flag precautionary findings: known CVE, version matches, exploitation not performed.

### S5 — Exploitation / Validation

Only where RoE permits. Actions:
1. Confirm exploitability (safe check or limited PoC).
2. Document exploitation path without causing damage.
3. Capture proof: console output, screenshot, hash, file access — sufficient to demonstrate impact.
4. Clean up any test artefacts immediately.
5. Promote finding to `validated` or `high_confidence`.

**Hard stops:** No destructive actions. No lateral movement beyond RoE. No credential reuse outside scope. Stop and notify client on: unintended access, critical system instability, sensitive data exposure.

---

## MRK:PT_ENUM_STUB_SCHEMA — Finding Stub Schema | pt,enum,stub,schema,finding | L166-204
<!-- NAV-RULE: same-commit:skills/pt-evidence/SKILL.md -->

Produce one stub per finding. This is the output consumed by pt-evidence and pt-report.

```markdown
## STUB: <FID> — <Title> [Precautionary if applicable]

| Field | Value |
|---|---|
| ID | F-XX / OBS-XX |
| Title | <concise, action-noun format> |
| Category | <section number — assigned during report phase> |
| Severity | Critical / High / Medium / Low / Informational |
| Confidence | CERTAIN / LIKELY / UNCERTAIN |
| Validation state | detected / suspected / validated / high_confidence |
| Affected hosts | <IP list> |
| Port / Service | <port/protocol> |
| CVE | <CVE-YYYY-NNNNN or N/A> |
| Precautionary | Y / N |

### Evidence
| Stream | Path | Description |
|---|---|---|
| MSF DB | note: db.caveat if relevant | hosts/services record |
| Automated | evidence/<IP>/<tool>_<TS>.txt | <what it shows> |
| Manual | evidence/<IP>/manual_<desc>_<TS>.txt | <what it shows> |

### Technical Detail (brief — full text written in report phase)
<2–4 sentences: what was found, how, what it means>

### Validation Basis
<What evidence supports the validation state — be specific>
```

**WordPress finding stubs:** Evidence path uses `evidence/_wpscan/<label>/` instead of `evidence/<IP>/`.

---

## MRK:PT_ENUM_RETURN — Return Pass Behaviour | pt,enum,return,pass,behaviour | L205-215

When `pass_type = RETURN_PASS`:
1. Receive specific objective (e.g. "check NFS on <target-IP>", "re-enumerate SNMP after community string change", "assess WPScan output for <URL>").
2. Review existing findings for this host/service from L1-provided context.
3. Scope all actions to stated objective. Do not re-enumerate completed services unless specifically requested.
4. If finding already exists: update stub with new evidence, promote validation state if warranted, note `[RP<N> <date>]` in Technical Detail.
5. If new finding: produce new stub with `[RP<N>]` tag in title temporarily, to be cleaned up in report phase.

---

## MRK:PT_ENUM_OUTPUT — Output — Enum Summary Block | pt,enum,output,summary,block | L216-250

Return this block to L1 on exit:

```markdown
## Enum Summary — <OrgCode> — <target> — <YYYYMMDD> [INITIAL / RP<N>]

### Objective
<What was enumerated and why>

### Finding Stubs Produced
| Stub ID | Title | Sev | Validation State |
|---|---|---|---|
| F-XX | <title> | High | suspected |

### Evidence Files
- evidence/<IP>/<file>: <what it contains>
- evidence/_wpscan/<label>/<file>: <what it contains>  ← if WordPress assessed

### Validation State Changes
- <FID>: suspected → validated (basis: <what confirmed it>)

### Open Issues Raised
- <anything needing follow-up, client confirmation, or deeper pass>

### Recommended Follow-up
- <next enum targets or return pass triggers>
- <run 06_wpscan.sh if WordPress URLs found in scripts/wp_targets.txt>
```

---
*pt-enum SKILL.md v0.72 — L2 | dispatched by pt-orc*

<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
