---
name: pt-report
version: "0.73"
description: >
  [v0.73] L2 — Report content generator. Converts finding stubs into polished report
  sections using TechGuard house style. Covers finding bodies, section text,
  executive summary, and appendices. Input: finding stubs + engagement metadata from
  state snapshot. Output: report-ready text for insertion into .docx via pt-orc →
  docx skill handoff. Do NOT load directly — pt-orc dispatches this.
---

<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->

<!-- MRK:SKILL_NAV_TOC — Section index | nav,toc,index | L15-42 -->
<!-- - MRK:PT_REPORT_RECEIVED — Received from L1 (pt-orc) | pt,report,received,l1,orc | L43-54 -->
<!-- - MRK:PT_REPORT_INPUTS — Input Sources | pt,report,inputs,input,sources | L55-94 -->
<!-- - MRK:PT_REPORT_EXIT — Exit Criteria | pt,report,exit,criteria | L95-103 -->
<!-- - MRK:PT_REPORT_STRUCTURE — Report Structure (PTI / PTE) | pt,report,structure,pti,pte | L104-150 | ⚠ read-toc-first -->
<!-- - MRK:PT_REPORT_VERSIONING — Document Versioning | pt,report,versioning,document,version | L151-166 -->
<!-- - MRK:PT_REPORT_HEADINGS — PTI Heading Structure | pt,report,headings,pti,heading | L167-186 -->
<!-- - MRK:PT_REPORT_EXEC_SUMMARY — Executive Summary | pt,report,exec,summary,executive | L187-225 -->
<!-- - MRK:PT_REPORT_BODY_RULES — Finding Body Writing Rules | pt,report,body,rules,finding | L226-271 | ⚠ read-toc-first -->
<!-- - MRK:PT_REPORT_OBSERVATIONS — Observations Writing Rules | pt,report,observations,writing,rules | L272-283 -->
<!-- - MRK:PT_REPORT_IDENTITY — Device Identity Verification Rule | pt,report,identity,device,verification | L284-304 -->
<!-- - MRK:PT_REPORT_PENDING — Pending Actions Pre-Delivery Checklist | pt,report,pending,actions,pre | L305-329 -->
<!-- - MRK:PT_REPORT_SUMMARY_TABLE — Findings Summary Table | pt,report,summary,table,findings | L330-344 -->
<!-- - MRK:PT_REPORT_SEVERITY — Severity Classification | pt,report,severity,classification,colors | L345-366 -->
<!-- - MRK:PT_REPORT_FINDING_TEMPLATE — Finding Body Template | pt,report,finding,template,body | L367-399 -->
<!-- - MRK:PT_REPORT_OBS_TEMPLATE — Observation Body Template | pt,report,obs,template,observation | L400-416 -->
<!-- - MRK:PT_REPORT_RETEST — Re-test Documentation (S8) | pt,report,retest,re,test | L417-440 -->
<!-- - MRK:PT_REPORT_SEC1 — Section 1 Introduction Templates | pt,report,sec1,section,introduction | L441-486 -->
<!-- - MRK:PT_REPORT_EVIDENCE_INDEX — Appendix C Evidence Index Template | pt,report,evidence,index,appendix | L487-502 -->
<!-- - MRK:PT_REPORT_STYLE — Style Rules Summary | pt,report,style,rules,summary | L503-518 -->
<!-- - MRK:PT_REPORT_PITFALLS — Common Pitfalls | pt,report,pitfalls,common,mistakes | L519-542 -->
<!-- NAV-LEN: 20 entries | Integrity-hash: 4ccb015a4c23d035 | Last-indexed: 2026-04-24T20:37:14Z -->

# pt-report — Report Content Generator
*L2 — Loaded for S7 (report generation). Drop after report section(s) complete.*

---

## MRK:PT_REPORT_RECEIVED — Received from L1 (pt-orc) | pt,report,received,l1,orc | L43-54

On dispatch, L1 passes:
- Findings index (full list of F-XX and OBS-XX from state snapshot)
- Finding stubs (from `working/<OrgCode>_Findings_vX.X.md`) — L1 fetches relevant stubs
- Engagement metadata (scope, type PTI/PTE, client, tester, dates)
- Severity distribution table
- Report version to produce
- Specific request: "write finding F-03", "draft section 2.3.1", "executive summary", etc.

---

## MRK:PT_REPORT_INPUTS — Input Sources | pt,report,inputs,input,sources | L55-94

### verify_summary_*.md (from 07_service_verify)
- **PRIMARY source** for service-level findings (DB NOAUTH, SSH CVE, FTP anon, web headers)
- Load before generating stubs for: database access, authentication, cleartext protocols
- Format: markdown tables with VULN / SAFE / UNKNOWN / MANUAL sections
- Evidence path per finding: `evidence/_verify/<ip>/<probe_type>_*.txt`
- Use VULN section rows directly as finding stubs — detail column → finding description
- UNKNOWN/MANUAL rows → flag for manual testing section of report; do not report as confirmed

### Finding Stub Templates from 07 Output

**DB NOAUTH → High finding stub (PTI) / Critical candidate (PTE):**
```
Title: Unauthenticated [MySQL/PostgreSQL/MSSQL] Access
Evidence: verify_summary VULN row + evidence/_verify/<ip>/[mysql|postgres|mssql]_noauth_*.txt
```

**SSH CVE-2024-6387 → High finding stub:**
```
Title: SSH regreSSHion Vulnerability Candidate (CVE-2024-6387)
Evidence: verify_summary VULN row + evidence/_verify/<ip>/ssh_version_*.txt
Note: "CANDIDATE" — exploitation requires race condition; confirm version before escalating
```

**FTP Anonymous → High finding stub:**
```
Title: FTP Anonymous Access Enabled
Evidence: verify_summary VULN row + evidence/_verify/<ip>/ftp_anon_*.txt
```

**Web Headers → Medium finding stub:**
```
Title: Missing HTTP Security Headers
Evidence: verify_summary VULN row + evidence/_verify/<ip>/web_generic_<port>_*.txt
Group all hosts missing same headers into one finding with affected hosts table
```

---

## MRK:PT_REPORT_EXIT — Exit Criteria | pt,report,exit,criteria | L95-103

- Requested content produced in report-ready format
- All content evidence-based (no speculative statements)
- Style rules applied (typography, severity indicators, recommendation verbs)
- Handed back to L1 for insertion into `.docx` via docx skill

---

## MRK:PT_REPORT_STRUCTURE — Report Structure (PTI / PTE) | pt,report,structure,pti,pte | L104-150
<!-- NAV-RULE: read-toc-first -->

### PTI Report
```
Cover Page                          ← version field must match filename
Section 1 — Introduction
  1.1 Scope and Objectives
  1.2 Methodology
  1.3 Limitations
  1.6 Executive Summary             ← written last; three bold callouts + body paragraphs
Section 2 — Findings and Recommendations
  2.1 Severity of Findings — Grading Table
  2.1.1 Findings Summary            ← Section column uses 2.3.x.y subsection numbers
  2.2 External findings (PTE)       ← placeholder text if PTE not yet conducted
  2.3 Internal findings (PTI)
    2.3.x. <Thematic section>       ← Heading3; ≤8 sections, hard cap 15
      2.3.x.y. F-YY — <Title>      ← Heading4; one per finding, immediately above severity table
Appendix A — Scope Details
Appendix B — Severity Classification
Appendix C — Evidence Index / Pending Actions Checklist
Appendix D — Evidence Screenshots
```

### PTE Report
```
Cover Page
Section 1 — Introduction
Section 2 — Findings
  2.2.1 DNS Reconnaissance
  2.2.2 Network Infrastructure
  2.2.3 TLS / Certificate Assessment
  2.2.4 Security Headers
  2.2.5 Outdated Software
  2.2.6 Authentication and Access Control
  2.2.7 WordPress Security          ← include only if WordPress assessed (06_wpscan.sh)
  [2.2.8+ additional categories if required]
Appendices
```

**PTE category sequence is fixed.** Do not reorder. Add categories after 2.2.6 only.
**WordPress (2.2.7):** Include this section only when `06_wpscan.sh` was run and produced findings. If WordPress was detected but not assessed (e.g. out of RoE), note in 1.3 Limitations instead. Typical findings grouped here: XML-RPC exposure, user enumeration, vulnerable plugins/themes, config file exposure, wp-admin access without rate limiting. Evidence from `evidence/_wpscan/<label>/`.
**PTI categories are thematic.** Group findings by technology/service area. Max 8
categories, ~15 findings across all.

---

## MRK:PT_REPORT_VERSIONING — Document Versioning | pt,report,versioning,document,version | L151-166

| Change type | Increment |
|---|---|
| Typo / minor fix | +0.01 |
| Multiple small fixes | +0.02–+0.03 |
| New finding or significant rewrite | +0.1 |
| Major restructure | +1.0 |
| Coordinated final release | Round to X.0 |

**CRITICAL:** Version must be bumped in BOTH the cover page field AND the filename
before every pack. Never reissue the same version number. Never skip incrementing.
This applies even for a single-field fix.

---

## MRK:PT_REPORT_HEADINGS — PTI Heading Structure | pt,report,headings,pti,heading | L167-186

### Section headings (Heading3)
Each thematic section (2.3.x) gets a Heading3. Example:
```
2.3.1. Network Segmentation and OT Boundary Failures
2.3.2. Unauthenticated Access to OT Devices
```

### Finding headings (Heading4)
Each individual finding gets a Heading4 immediately above its severity table.
Format: `2.3.x.y. F-YY — <Short title matching summary table>`

Heading4 style: bold, navy (#1F3864), 11pt. Not italic, not blue — override Word default.

The Heading4 subsection number must also appear in the **Findings Summary table**
Section column (e.g. 2.3.1.3, not just 2.3.1).

---

## MRK:PT_REPORT_EXEC_SUMMARY — Executive Summary | pt,report,exec,summary,executive | L187-225

Write last. Structure:

1. **Engagement overview** (1–2 sentences): what was tested, when, by whom.
2. **Overall posture** (2–3 sentences): high-level characterisation. Reference severity
   distribution. Do not list individual findings.
3. **Three bold callouts** — the most significant risk themes. Each callout:
   - Opens with a **bold statement** of the risk (not a finding title)
   - Followed by 3–5 sentences of plain-English explanation
   - References specific F-XX numbers inline (not in parenthetical footnotes)
   - Includes concrete details (IP counts, storage sizes, CVE numbers where material)
   - Does NOT name tools, scan dates, or methodology
4. **Immediate priority list** — 4–6 bullet points with F-XX references.

**Bold callout tone:** Direct, specific, risk-forward. Not alarmist. Not vague.
Each callout should tell a non-technical executive exactly what is broken and why it matters.

**Example structure (not content):**
```
**OT network segmentation is effectively absent.** Five independent confirmed bridges
exist between the corporate LAN and the OT/calibration subnet: [specifics]. One bridge
additionally [compound risk]. [Consequence sentence]. F-01, F-02, F-03.

**OT devices accept unauthenticated remote access.** [Device name and IP] accepts
[access type] and allows [confirmed capability]. [Specific risk to operations].
F-04, F-05.

**The perimeter firewall patch status is unverified against critical-severity CVEs.**
[Device] is confirmed as a model affected by [CVE, CVSS score]. [Attack surface].
[Consequence if unpatched]. F-07.
```

Tone: professional, direct, non-alarmist. Readable by a non-technical executive.
**No tool names. No scan dates. IP addresses MAY appear in callouts for specificity.**
CVE numbers MAY appear in callouts when the severity/score is the key risk driver.

---

## MRK:PT_REPORT_BODY_RULES — Finding Body Writing Rules | pt,report,body,rules,finding | L226-271
<!-- NAV-RULE: read-toc-first -->

These rules are derived from Greg's editing style across the WTech PTI engagement.
They override any general guidance where they conflict.

### What to include
- What was found and where (device, IP, service, port)
- How it was confirmed (one clean sentence — no tool names, no dates, no file refs)
- The specific risk to this client's environment
- Concrete detail: IP addresses, storage sizes, version strings, CVE numbers
- Write access / read access distinction — always state which was confirmed

### What to exclude
- Tool names in finding bodies (nmap, enum4linux, services-f3.csv, etc.)
- Scan dates (2026-04-07, D-05 verification, etc.)
- File references (services-f3.csv, goahead_banner_20260407T1125.txt, etc.)
- Internal tracking codes (C-01, D-05, D-06, etc.)
- Methodology narrative ("during passive capture", "Phase 1/2 enumeration")
- Scanning methodology language ("confirmed by NSE script", "returned by db_nmap")
- Verbose technical acronym explanations (SCPI, SAMR — use them without explaining)
- Duplicate recommendations (check for overlap before adding)

### Tone and structure
- State the risk clearly without storytelling
- Bold the sub-finding title; follow immediately with the evidence-based body
- 2–4 sentences per sub-finding — tight, factual, outcome-focused
- Recommendations: outcome-focused verbs, specific config paths where known

### Host(s) table cell
- Always list specific IPs — never "Multiple hosts" without IPs
- For large host lists (10+): group by subnet prefix, list last octets only
  Format: `192.168.1.x — .15 · .25 · .39 · .71 · [...]`
          `192.168.10.x — .5 · .6 · .10`
          `Signing enforced on 192.168.1.48 only` (italic, separate line)
- Notable hosts: call out role inline (e.g. `.243 (PCRDP) · .245 (SRV2019_2)`)
- OBS Host(s) cells: populate with confirmed IPs from evidence — never leave as
  "Multiple hosts" without the actual list

### Confidence cell
- Do not include scan dates, file names, or verification session codes
- State the confirmation method in plain terms: "anonymous FTP login confirmed;
  write access demonstrated by successful directory creation"

---

## MRK:PT_REPORT_OBSERVATIONS — Observations Writing Rules | pt,report,observations,writing,rules | L272-283

- 2–4 sentences max
- Factual, neutral — no risk language, no recommendations
- No tool names, no dates, no file references, no internal tracking codes
- No SCPI explanations, no Italian app names, no URL paths unless essential
- No "was not assessed" repeated multiple times — state once what was not assessed
- No "during passive capture" — just state what was observed
- Host(s) cell: always specific IPs, never "Multiple hosts" alone

---

## MRK:PT_REPORT_IDENTITY — Device Identity Verification Rule | pt,report,identity,device,verification | L284-304

**Always verify device identity from evidence before writing any finding.**
Nmap service banners are frequently wrong. The following are known failure modes:

- **Telnet service label** — nmap commonly misidentifies generic login prompts
  (User name / Password) as specific device types (e.g. "HP Integrated Lights Out
  telnetd"). This is a false positive pattern. Always cross-reference with:
  - MAC OUI (primary — confirms vendor)
  - OS fingerprint from hosts export (ZyNOS, ZyXEL = Zyxel device)
  - FTP banner (often names the actual device/vendor)
  - Browser login page screenshot (definitive)
- **iLO / BMC identification** — requires confirmed MAC OUI (HP = 3C:D9:2B etc.)
  plus management interface login page. A telnet banner alone is not sufficient.
- **When identity is wrong in an early version** — correct ALL occurrences:
  finding title, H4 heading, summary table, finding body, all recommendations,
  cross-references in other findings (e.g. F-19 "outdated components"), appendix
  evidence index entries, appendix screenshot captions.

---

## MRK:PT_REPORT_PENDING — Pending Actions Pre-Delivery Checklist | pt,report,pending,actions,pre | L305-329

The checklist table lives in Appendix B (or C depending on template). It tracks:
- **Blocking items** (🔴 BLOCKING) — report cannot be finalized without these
- **Required client actions** (🔴 REQUIRED) — client must act before delivery

Rules:
- This table must NOT appear in the Severity Grading Table (2.1) — if an orphaned
  row appears there, delete it and add to the checklist instead
- Completed items are removed from the checklist (not marked done)
- New tester artefacts requiring client cleanup are added as 🔴 REQUIRED rows
- Each artefact row names the specific file/directory, the host IP, and the method
  to remove it (e.g. "QNAP management interface or authenticated NFS session")

**Standard artefact cleanup row format:**
```
Item:   TechGuard IT artefact on .<last_octet>
Status: 🔴 REQUIRED
Detail: <Directory/file name> created at <path> on <IP> during active testing
        (<confirmation method>). Cannot be removed by tester session. Client must
        delete manually via <method> before report delivery (F-XX).
```

---

## MRK:PT_REPORT_SUMMARY_TABLE — Findings Summary Table | pt,report,summary,table,findings | L330-344

The Section column must use **full subsection numbers** (2.3.x.y), not section numbers
(2.3.x). These correspond to the Heading4 subsections added above each finding's
severity table.

Example:
```
High | NFS World-Readable Exports (~21 TB) (F-03) | 2.3.1.3
High | Dual-NIC QNAP OT Bridge (F-01)             | 2.3.1.1
High | SMB Signing Not Enforced (F-08)             | 2.3.3.2
```

---

## MRK:PT_REPORT_SEVERITY — Severity Classification | pt,report,severity,classification,colors | L345-366

| Severity | Hex | Definition |
|---|---|---|
| Critical | #7B1C2E | RCE, unauthenticated privileged access, exfiltration path, data destruction |
| High | #C25B6E | Strong path to Critical, auth bypass, sensitive data exposure, exploitable misconfiguration |
| Medium | #C47C3A | Exploitable with credentials or chaining, information disclosure, weak auth |
| Low | #8FAF6E | Minor misconfiguration, hardening gap, limited exploitability |
| Informational | #4A7BA7 | No direct risk; context for assessor or client |
| Observation | — | No severity assigned; informational only |

**PTI scale:** No Critical tier — High is the highest. Finding severity tops at High
for internal engagements unless engagement scope explicitly permits Critical.

Applied as: left border stripe + filled circle indicator in Word. **Never coloured text.**
Body text always #000000. Header text in report always #000000 (not styled to severity colour).

**Header "Confidential" label:** Must be navy (#1F3864), not severity red. This is a
common error — check header1.xml when building or editing the template.

---

## MRK:PT_REPORT_FINDING_TEMPLATE — Finding Body Template | pt,report,finding,template,body | L367-399

Every finding body follows this structure exactly. Adapt content; do not adapt structure.

```markdown
### F-XX — <Title> [Precautionary — if applicable]

**Severity:** High / Medium / Low / Informational   ← no Critical in PTI
**Confidence:** CERTAIN / LIKELY / UNCERTAIN
**Affected Systems:** <specific IP list — never "Multiple hosts" alone>
**CVE:** <CVE-YYYY-NNNNN> / N/A

---

#### Finding(s)

1. **F-XX — <Sub-finding title>:** <Body. What was found, where, what it means.
   No tool names, no dates, no file refs. Evidence-based only. 2–4 sentences.>

2. **F-XX — <Second sub-finding if applicable>:** <Same format.>

#### Recommendation(s)

1. <Action verb> <specific action>. <Config path or method if known.>
2. <Action verb> <specific action.>
```

**Precautionary findings:** Add `[Precautionary]` to title. State explicitly in body:
*"The firmware version could not be confirmed by any unauthenticated method. This finding
is rated [severity] on a precautionary basis and will be reviewed upon receipt of [D-XX]."*

---

## MRK:PT_REPORT_OBS_TEMPLATE — Observation Body Template | pt,report,obs,template,observation | L400-416

```markdown
### OBS-XX — <Title>

**Affected Systems:** <specific IPs>

<2–4 sentences. Factual. No risk language. No recommendations.
No tool names. No dates. No internal codes.>

*Informational observation. No remediation action required.*
```

No Recommendation section. No severity. If action is needed, promote to a Finding.

---

## MRK:PT_REPORT_RETEST — Re-test Documentation (S8) | pt,report,retest,re,test | L417-440

When re-testing previously reported findings, document the delta only.

```markdown
### F-XX — <Original Title> — Re-test

**Re-test date:** <date>
**Original report version:** <vX.X>
**Remediation status:** Resolved / Partially resolved / Not resolved

#### Re-test Evidence
<What was tested, how, what result was observed. No tool names in summary.>

Evidence file: `evidence/<IP>/retest_<TS>/<tool>_<TS>.txt`

#### Verdict
- **Resolved:** Vulnerability no longer present. <Brief confirmation.>
- **Partially resolved:** <What was fixed, what remains.>
- **Not resolved:** Finding stands. Original evidence and recommendation unchanged.
```

---

## MRK:PT_REPORT_SEC1 — Section 1 Introduction Templates | pt,report,sec1,section,introduction | L441-486

### 1.1 Scope and Objectives

```
TechGuard. was engaged by <Client> to conduct a <PTI/PTE>
penetration test of <scope description>. The assessment was conducted between
<start date> and <end date>.

The objectives of this engagement were to:
- Identify vulnerabilities within the assessed environment
- Evaluate the effectiveness of existing security controls
- Provide actionable recommendations to reduce risk

[PTI:] The internal assessment covered <N> hosts across <N> subnets.
[PTE:] The external assessment covered <N> confirmed in-scope IP addresses across <N> domains.
```

### 1.2 Methodology

```
Testing was conducted in accordance with industry-standard methodologies, incorporating
elements of OWASP, PTES, and NIST SP 800-115. The engagement proceeded through the
following phases: reconnaissance, enumeration, vulnerability assessment, and
[exploitation / validation — if applicable under RoE].

All testing was performed from [tester network position]. No social engineering or
physical testing was performed unless explicitly noted.
```

### 1.3 Limitations

```
This assessment represents a point-in-time evaluation. The security posture of the
environment may change after the assessment date.

[Add if applicable:]
- Certain hosts were excluded from active testing at the client's request: <list>
- Exploitation was limited by the Rules of Engagement to [describe limitation]
- Domain authentication enumeration required domain credentials not available during
  this engagement; targeted follow-up is recommended.
- [Any other scoping limitation]
```

---

## MRK:PT_REPORT_EVIDENCE_INDEX — Appendix C Evidence Index Template | pt,report,evidence,index,appendix | L487-502

```markdown
| Finding | Evidence File | Tool | Description |
|---|---|---|---|
| F-01 | evidence/<IP>/<tool>_<TS>.txt | <tool> | <what output shows> |
| F-01 | evidence/<IP>/manual_<desc>_<TS>.txt | manual | <what was confirmed> |
```

Screenshot captions in Appendix D: when a nmap service label is a known false positive
(e.g. "HP Integrated Lights Out telnetd" on a Zyxel switch), note it explicitly in the
caption: *"The Telnet service was incorrectly labeled by nmap as [label] — a false
positive on the generic login prompt. Right pane: browser confirms [actual device]."*

---

## MRK:PT_REPORT_STYLE — Style Rules Summary | pt,report,style,rules,summary | L503-518

- Body text: Arial, #000000, no exceptions
- H1 (section titles): Arial, #1F3864, white text on navy fill
- H2 (subsection): Arial, #2E75B6
- H4 (finding subsection): Arial, bold, #1F3864, 11pt — not italic, not blue
- Finding title row: severity colour fill, white bold text
- Tables: navy header (#1F3864) white bold text; alternating white/#F2F2F2 rows; thin #CCCCCC borders
- Severity indicator: left border stripe (4pt, severity colour) + filled circle (●) before title
- No coloured body text. No coloured Rating columns. Severity by fill/stripe only.
- Header "Confidential" label: #1F3864 navy — never severity red (#C25B6E)
- Finding IDs: F-XX (zero-padded), OBS-XX
- Version in filename AND internal cover page field — both must match

---

## MRK:PT_REPORT_PITFALLS — Common Pitfalls | pt,report,pitfalls,common,mistakes | L519-542

| Pitfall | Correct approach |
|---|---|
| Version not bumped before packing | Bump cover page field AND filename before every pack — no exceptions |
| "Multiple hosts" in Host(s) cell | Always list specific IPs; group by subnet prefix for large lists |
| Tool names in finding body | Remove — state what was found, not how it was found |
| Scan dates in finding body | Remove — no dates in finding prose |
| File references in body | Remove — no services-f3.csv, no log filenames |
| Internal codes (C-01, D-05) in body | Remove — for analyst working notes only |
| Nmap service banner accepted as device identity | Cross-check MAC OUI + OS fingerprint + FTP banner + browser screenshot |
| TechGuard IT artefact row in Grading Table | Move to Pending Actions checklist |
| Findings Summary Section column shows 2.3.x | Must be 2.3.x.y (full subsection number) |
| H4 heading missing above finding table | Insert Heading4 with subsection number before every severity table |
| F-18 body starts with "Life OS" | Correct prefix is "End-of-Life OS" — check replacement didn't strip "End-of" |
| Duplicate recommendation added | Review all existing recs before adding; merge if overlapping |
| Observation body references tool or date | Strip — observations are 2–4 factual sentences only |
| "Confidential" in header is red | Set to #1F3864 navy in header1.xml |

---
*pt-report SKILL.md v0.73 — L2 | dispatched by pt-orc*

<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
