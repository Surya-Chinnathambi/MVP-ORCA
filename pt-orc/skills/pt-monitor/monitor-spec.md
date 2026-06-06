# PT-Orc Monitor — Living Guide
<!-- META
  GUIDE-VERSION: 2.0
  SESSIONS: 1
  PATTERNS: 12
  SUITE-VERSION-BASELINE: 0.95
  LAST-UPDATED: 2026-04-21
  ANALYSTS: madmin2
-->

**Purpose:** Definitive, self-improving template for monitoring live PT-Orc scans.
Personalised per analyst. Suite-version-aware. Derives phase structure and log paths
from ORC-INDEX (canonical) rather than hardcoding them here.

Trigger self-update: type `debrief` at end of any monitoring session.

---

## CONTENTS

| Section | What it covers |
|---|---|
| §0 Analyst profiles | Per-analyst preferences, cadence, focus — loaded at session start |
| §1 Setup | VPN, SSH, session start paste, /loop |
| §2 Log paths & commands | Canonical paths + how to derive them from ORC-INDEX |
| §3 Phase timing reference | Bands refined per session; suite-version-stamped |
| §4 Pattern library | Red flags, anti-patterns, blind spots, fingerprints — versioned |
| §5 Session debrief protocol | End-of-session checklist + structured update proposal |
| §6 Self-update specification | Rules for how Claude edits this guide |
| §7 Improvement log | Append-only session history |
| §8 Metrics | Session counts, catch rates, gap closure |

---

## §0 ANALYST PROFILES

Loaded at session start when analyst identifies themselves.
Claude applies the active profile throughout the session — cadence, verbosity,
what to surface automatically, what to suppress.

**To activate:** include `Analyst: <name>` in the session-start message.
**To add a profile:** run debrief and request "add analyst profile for <name>".

---

### PROFILE: madmin2

```yaml
name: madmin2
role: lead — engagement owner, suite author
timezone: IDT (UTC+3)

cadence:
  mode: auto          # Claude picks based on observed phase (see §1.4)
  override: null      # set to e.g. "270s" to force fixed interval

verbosity: detailed
  # detailed = full tick report: phase, elapsed, queue ratio, any log anomalies
  # terse    = phase + time + red flags only

follow_up_depth: deep
  # deep     = investigate before surfacing (SSH in, check log, form hypothesis)
  # shallow  = report and ask user to decide

focus_areas:
  - OT/SCADA coverage gaps
  - missed findings (ports/services outside normal scan scope)
  - suite self-improvement signals (new anti-patterns, timing anomalies)
  - MSF DB integrity (host/service count consistency)

auto_surface:
  # Always mention these even if not triggered, once per session
  - BS-01   # MongoDB and middleware port coverage (until Fix A/B2/C/D land)
  - BS-02   # phase_enum → MSF DB import gap (until Fix D lands)

suppress_ap: []
  # AP-* IDs to never explain again (madmin2 already knows these)
  # Add here as patterns become familiar: e.g. [AP-01, AP-02]

report_style: technical
  # technical = MRK refs, log line numbers, exact phase names
  # narrative = plain English first, technical on request

suite_version_expectation: "0.8"
  # Alert if suite version in scan log differs from this
```

---

<!-- TEMPLATE FOR NEW ANALYSTS — copy block, fill in, remove this comment
### PROFILE: <analyst_name>

```yaml
name: <analyst_name>
role: <role description>
timezone: <TZ>

cadence:
  mode: auto          # auto | fixed
  override: null      # e.g. "270s"

verbosity: detailed   # detailed | terse

follow_up_depth: deep # deep | shallow

focus_areas:
  - <what this analyst cares most about>

auto_surface: []      # BS-* or RF-* IDs to always mention

suppress_ap: []       # AP-* IDs analyst already knows well

report_style: technical   # technical | narrative

suite_version_expectation: "0.8"
```
-->

---

## §1 SETUP

### 1.1 Prerequisites

| Requirement | Verify with |
|---|---|
| OpenVPN connected | `ping <TESTER_IP>` replies |
| SSH pubkey installed on Kali | `ssh kali@<TESTER_IP> "echo OK"` — no password prompt |
| PT-Orc scan running | `ssh kali@<TESTER_IP> "ps aux | grep 00_pt-orc | grep -v grep"` |
| mongosh available (for MongoDB probes) | `ssh kali@<TESTER_IP> "which mongosh"` |

If SSH prompts for password: `ssh-copy-id kali@<TESTER_IP>`

### 1.2 Engagement variables

```bash
# Fill once per engagement — substitute everywhere below
TESTER_IP="<kali-host-ip>"
KPATH="<e.g. /home/kali/Documents/YYYY/engagement-slug/PT-ORC>"
WS="<workspace-name>"
SUBNETS="<subnet1/cidr> (normal)  <subnet2/cidr> (ghost/OT)  <subnet3/cidr> (normal)"
```

### 1.3 Session start — paste as first message

```
I need to monitor a live PT-Orc scan on Kali (<TESTER_IP>).
Analyst: <analyst_name>

Read @chat-starters/orc-monitor.md for flow, timing, and commands.
Read @orc-monitor/orc-monitor-spec.md — load my analyst profile (§0),
then use §3 timing bands and §4 pattern library for this session.
Also read ORC-INDEX.md top section — use it as ground truth for current phase
structure and log paths; flag any conflict with what you see in the guide.

Engagement: <engagement name>
Subnets: <subnet1/cidr> (normal), <subnet2/cidr> (ghost/OT), <subnet3/cidr> (normal)
Kali path: <KPATH>
Workspace: <workspace-name>

Do a first status check per my profile preferences. Then ask: /loop or manual pings?
At session end I'll say "debrief" — run §5 debrief protocol and propose guide updates.
```

**Substituting for a different engagement:** change the engagement block.
**Different analyst:** change `Analyst:` — Claude loads that profile from §0.

### 1.4 Autonomous loop

```
/loop check Kali scan status with frequency to get meaningful data
```

Claude picks cadence from active analyst profile + current phase:

| Phase | Default cadence | madmin2 override |
|---|---|---|
| ARP / Pass 1 transition | 240s | — (auto) |
| Pass 2 / NSE / UDP grind | 1200–1800s | — (auto) |
| Step 4–7 | 600s | — (auto) |
| Suite done / idle | 1800s | — (auto) |

**Never 300s** — cache-miss threshold without amortization benefit.

Stop: type `stop the loop`, `halt`, or `cancel`.

---

## §2 LOG PATHS & COMMANDS

### 2.1 Canonical paths

> **Important:** these paths are derived from suite v0.8 conventions. If the suite
> version in the scan log differs from `SUITE-VERSION-BASELINE` in this guide's header,
> **cross-check against ORC-INDEX.md** before relying on paths below. ORC-INDEX is
> canonical; this guide is a convenience cache.
>
> ORC-INDEX sections to check: `MRK:IDX_S3` (03 evidence layout), `MRK:IDX_S5` (tier table).

```bash
# Orchestrator (step boundaries, total elapsed)
ssh kali@<TESTER_IP> "tail -30 \$(ls -1t $KPATH/working/pt-orc_*.log | head -1)"

# Scan detail — 03 phase transitions, tier banners, host-timeout warnings
ssh kali@<TESTER_IP> "tail -50 \$(ls -1t $KPATH/evidence/_sweep/scan_*.log | head -1)"

# Web enum — 05 queue progress
ssh kali@<TESTER_IP> "tail -30 \$(ls -1t $KPATH/evidence/_sweep/web_enum_*.log | head -1)"

# Service verify — 07 VULN hits
ssh kali@<TESTER_IP> "tail -30 \$(ls -1t $KPATH/evidence/_verify/verify_*.log | head -1)"

# Active processes
ssh kali@<TESTER_IP> "ps -o etime,pid,cmd -C nmap,msfconsole 2>/dev/null | head -8"
```

### 2.2 Quick composite status

```bash
ssh kali@<TESTER_IP> "
  KPATH=$KPATH
  echo '=== running ===' && ps aux | grep -E '00_pt-orc|03_comp|04_tls|05_web|06_wps|07_serv' | grep -v grep | awk '{print \$2,\$11,\$12,\$13}'
  echo '' && echo '=== scan tail ===' && tail -15 \$(ls -1t \$KPATH/evidence/_sweep/scan_*.log 2>/dev/null | head -1) 2>/dev/null
  echo '' && echo '=== orch tail ===' && tail -8 \$(ls -1t \$KPATH/working/pt-orc_*.log 2>/dev/null | head -1) 2>/dev/null
"
```

### 2.3 Queue progress (05)

```bash
ssh kali@<TESTER_IP> "
  LOG=\$(ls -1t $KPATH/evidence/_sweep/web_enum_*.log | head -1)
  echo \"queued: \$(grep -c 'Web enum:' \$LOG)\"
  echo \"done:   \$(grep -c '✓ Done:' \$LOG)\"
"
```

Queue is dynamic — do NOT predict the last host. Track ratio only. (See AP-07.)

### 2.4 MSF DB queries

```bash
PGPW=$(ssh kali@<TESTER_IP> "grep password: /usr/share/metasploit-framework/config/database.yml | awk '{print \$2}'")

ssh kali@<TESTER_IP> "PGPASSWORD='$PGPW' psql -h 127.0.0.1 -U msf -d msf -t -A \
  -c \"SELECT COUNT(*) FROM hosts h JOIN workspaces w ON h.workspace_id=w.id WHERE w.name='$WS';\""

ssh kali@<TESTER_IP> "PGPASSWORD='$PGPW' psql -h 127.0.0.1 -U msf -d msf -t -A \
  -c \"SELECT COUNT(*) FROM services s JOIN hosts h ON s.host_id=h.id JOIN workspaces w ON h.workspace_id=w.id WHERE w.name='$WS' AND s.state='open';\""
```

### 2.5 Emergency stop (sudo required at Kali keyboard)

```bash
sudo pkill -9 -f '00_pt-orc\.sh' && sudo pkill -9 -f '03_comp_scan\.sh' && sudo pkill -9 msfconsole && sudo pkill -9 -f 'nmap -sS'

# Restart from TCP, preserve workspace
cd $KPATH && sudo ./00_pt-orc.sh --yes --mode pti --from 3 --phase tcp --continue --reuse-workspace
```

---

## §3 PHASE TIMING REFERENCE

> **Suite version note:** phase names, sub-phase ordering, and timing characteristics
> can change between suite versions. When the suite version differs from this guide's
> `SUITE-VERSION-BASELINE`, verify phase structure against ORC-INDEX (`MRK:IDX_S3`
> for scan phases, `orc-monitor.md` suite flow section). Treat bands below as
> starting estimates to be re-confirmed for the new version.

Each band is tagged `[Nv, Ms]` — N field-session data points, M suite versions observed.
Bands solidify only when N≥3 sessions on the same suite version agree.

| Phase | Typical | Red flag | Evidence | Suite ver | Notes |
|---|---|---|---|---|---|
| Orchestrator banner | <5s | >30s | [1v,1s] | 0.8 | DB/conf issue if slow |
| ARP discovery (3×/24) | 5–10 min | >15 min | [1v,1s] | 0.8 | Routed subnets → 0 hosts (normal, see AP-02) |
| Pass 1 ghost (60 hosts) | 4–10 min | >15 min | [1v,1s] | 0.8 | Low-rank ports (>~3000) missed under 3m host-timeout |
| Pass 1 normal (100 hosts) | 3–6 min | >10 min | [1v,1s] | 0.8 | — |
| Pass 2 deep per-tier | 10–30 min | >45 min | [1v,1s] | 0.8 | BASELINE_PORTS fallback = Pass 1 empty for that tier |
| NSE common-port sweep | 10–30 min | >45 min | [1v,1s] | 0.8 | db_query escape bug (fixed v0.77+) |
| UDP per-tier | 30–90 min | >120 min | [1v,1s] | 0.8 | open\|filtered ambiguity normal |
| Phase 4 enum | 5–20 min | >30 min | [1v,1s] | 0.8 | MSF RPORT errors expected |
| Step 4 TLS | 20–40 min | >60 min | [1v,1s] | 0.8 | testssl is the slow component |
| Step 5 web enum | 60–180 min | >300 min | [1v,1s] | 0.8 | Dynamic queue — ratio-track only |
| Step 7 service verify | 10–30 min | >60 min | [1v,1s] | 0.8 | 356 probes, <N> VULN in initial <engagement> run |

---

## §4 PATTERN LIBRARY

Each entry: ID | description | confidence | evidence `[Nv,Ms]` | suite versions valid | first seen.

Confidence: `field` = field-confirmed | `1x` = single observation | `theory` = code-read, not observed | `stale` = may not apply to current suite version.

### 4.1 Anti-patterns (AP) — looks like a bug, isn't

| ID | Symptom | Actual cause | Conf | Evidence | Suite valid | First seen |
|---|---|---|---|---|---|---|
| AP-01 | `[WARN] TCP [ghost] masscan found 0 open ports` | Hardcoded log string — fires regardless of Pass 1 backend. When backend=db_nmap, purely cosmetic. Not a masscan run result. | field | [1v,1s] | 0.8 | 2026-04-21 |
| AP-02 | `ARP discovery complete. Live hosts: 0` on some subnets | Routed subnet — ARP can't cross gateway. phase_tcp scans full CIDR anyway. | field | [1v,1s] | 0.8 | 2026-04-21 |
| AP-03 | MSF services = 0 after Pass 1 | Services populate only after Pass 2 (`-sV`). Normal until Pass 2 completes per tier. | field | [1v,1s] | 0.8 | 2026-04-21 |
| AP-04 | `Workspace 'X' already exists -- renaming to X_HHMM` | Re-run default. Prior workspace archived. Data NOT lost. | field | [1v,1s] | 0.8 | 2026-04-21 |
| AP-05 | `[db_query] psql error: syntax error at or near "$"` in NSE | `\${wid}` escape bug in db_query (fixed v0.77+). Silent BASELINE_PORTS fallback for NSE target list. | field | [1v,1s] | 0.8 (fixed 0.77+) | 2026-04-21 |
| AP-06 | `ps -C nikto` returns nothing | nikto runs as `/usr/bin/perl /var/lib/nikto/nikto.pl`. Use `ps aux | grep perl`. | field | [1v,1s] | 0.8 | 2026-04-21 |
| AP-07 | Step 5 "last host" is predictable | Queue is dynamic — MSF DB queried at runtime, grows throughout run. Track `grep -c 'Web enum:' vs grep -c '✓ Done:'` ratio only. | field | [1v,1s] | 0.8 | 2026-04-21 |

### 4.2 Red flags (RF) — investigate immediately

| ID | Symptom | Action | Conf | Evidence | Suite valid |
|---|---|---|---|---|---|
| RF-01 | Phase stalled >2× typical, no log advancement | SSH in, check processes, tail scan log. Report: likely hung. | theory | [0v] | 0.8 |
| RF-02 | `[db_query] psql error` in scan log | Report: degraded mode, BASELINE_PORTS fallback active. | field | [1v,1s] | 0.8 |
| RF-03 | MSF host count drops between checks | Investigate immediately — workspace rename/reset, data loss risk. | theory | [0v] | 0.8 |
| RF-04 | `--host-timeout` warnings for many hosts | Flag but don't stop. Data quality impact. Note count. | theory | [0v] | 0.8 |
| RF-05 | Step 5 done count stuck >20 min | Check `ps aux | grep perl` (nikto) and `ps aux | grep gobuster`. Likely one target hung. | theory | [0v] | 0.8 |

### 4.3 Suite blind spots (BS) — known coverage gaps

Each entry references the action-plan fix. Update Fix status when fix lands; increment
suite version in "Fixed in" column.

| ID | Gap | Root cause | Fix status | Fixed in | Evidence | First seen |
|---|---|---|---|---|---|---|
| BS-01 | MongoDB (27017) on ghost OT hosts missed | nmap rank #3083 + host-timeout 3m + absent from BASELINE_PORTS + no 07 probe | 4 items tracked in action-plan.md (Fix A/B2/C/D) | — | field [1v, CVSS 10.0] | <engagement> |
| BS-02 | Phase 4 enum results not in MSF DB | `phase_enum` has no `db_import` call; Step 7 can't target hosts missed in Pass 1/2 | action-plan.md Fix D | — | field [1v] | <engagement> |
| BS-03 | masscan unusable on multi-homed hosts | `MASSCAN_INTERFACE=""` auto-detect picks wrong NIC | action-plan.md Fix B | — | theory+config | — |
| BS-04 | BASELINE_PORTS misses middleware defaults | 6379 Redis, 11211 Memcached, 2181 ZooKeeper, 27017 MongoDB all absent | action-plan.md Fix A | — | field+theory | <engagement> |

### 4.4 Fingerprints (FP) — architecture patterns

Confirmed when ≥2 indicators observed together in the same engagement.

| ID | Pattern name | Indicators | Interpretation | Conf | Evidence | Suite valid |
|---|---|---|---|---|---|---|
| FP-01 | Microservices + authenticated gateway | ≥2 hosts on port 80, identical 14-path 401/308 fingerprint | API gateway fronts unauthenticated backends — probe backend IPs directly | field | [1v,1s] | 0.8 |
| FP-02 | Unauthenticated microservice backend | Port 80 + HTTP 200 on `/swagger-ui.html` + `/swagger.json` + `/openapi.json` | Auth bypassed — document all Swagger URLs, probe for data exposure | field | [1v,1s] | 0.8 |
| FP-03 | OT IPMI exposure | UDP/623 open + IPMI version response | CVE-2013-4786 RAKP hash capture → offline crack → BMC admin | field | [1v,1s] | 0.8 |

### 4.5 Confirmed VULN patterns (PR) — reference for findings

| ID | Service | Pattern | Probe command | Confirmed | Notes |
|---|---|---|---|---|---|
| PR-01 | NFS | World-accessible exports | `showmount -e <ip>` | <engagement> | — |
| PR-02 | SMB | Null session | `smbclient -N -L //<ip>` | <engagement> | — |
| PR-03 | FTP | Anonymous login | `ftp <ip>` user: anonymous | <engagement> | — |
| PR-04 | MongoDB | Unauthenticated admin | `mongosh --host <ip> --port 27017 --quiet --eval "db.adminCommand({listDatabases:1})"` | <engagement> | ok:1 without creds = critical |
| PR-05 | OpenSSH | Version check bug in 07 | — | <engagement> | OpenSSH_3.9p1 falsely flagged as CVE-2024-6387. String comparison bug in 07. Verify range 8.5p1–9.7p1 manually before reporting. |

### 4.6 Suite version delta log

When the suite version changes, entries here track what patterns were invalidated,
confirmed still valid, or added. Analysts should re-validate `stale`-tagged patterns
on the new version before relying on them.

| Suite ver change | Date | Patterns affected | Action taken |
|---|---|---|---|
| — (initial, v0.8 baseline) | 2026-04-21 | All patterns seeded at v0.8 | None — baseline |

---

## §5 SESSION DEBRIEF PROTOCOL

**Trigger:** user types `debrief`.

Claude runs the checklist, produces a structured update proposal. User approves;
Claude edits this file and commits to the improvement log.

### 5.1 Debrief checklist

**Suite version check:**
- [ ] What suite version ran? (grep `Suite v` in orchestrator log)
- [ ] Does it match this guide's `SUITE-VERSION-BASELINE`?
- [ ] If different: which §3 timing bands and §4 patterns need re-validation?

**Analyst profile check:**
- [ ] Which analyst ran this session? Were profile preferences honoured?
- [ ] Any preference that was wrong, missing, or should be adjusted?
- [ ] Should any AP-* IDs be added to the analyst's `suppress_ap` list?

**Timing data:**
- [ ] Any phase outside §3 bands? Faster or slower?
- [ ] Host-timeout events? How many / which tier?
- [ ] Step 5 queue peak and final done count?
- [ ] Total wall-clock?

**Pattern validation:**
- [ ] Any AP-* entries triggered? Did they behave as documented?
- [ ] New "looked like a bug but wasn't" moments not in §4.1?
- [ ] Any RF-* conditions triggered? Diagnosis accurate?
- [ ] Any new RF situations to add?

**Blind spots:**
- [ ] Any services/ports missed by the suite that manual testing found?
- [ ] Any coverage gap evidence not already in BS-*?
- [ ] Any BS-* items that got fixed this session (suite version bump)?

**Fingerprints & VULNs:**
- [ ] New architecture patterns recognised?
- [ ] New confirmed VULN probe patterns to add to §4.5?

**ORC-INDEX / NAV:**
- [ ] Did ORC-INDEX structure (phases, MRK tags, log paths) conflict with §2 or §3?
- [ ] If yes: which entries need updating, and what's the correct current value?

**New analyst onboarding:**
- [ ] Was a new analyst active this session? Profile to be added to §0?

### 5.2 Debrief output format

```
## DEBRIEF — [ENGAGEMENT] [DATE] | Suite v[X.X] | Analyst: [name]

### Suite version delta
[same version / differs — patterns needing re-validation listed]

### Analyst profile updates
[preference changes, suppress_ap additions, new analyst profiles]

### Timing data points
- [phase]: [observed] — [within/outside band; direction]

### Proposed §4 additions / updates
AP-xx | [symptom] | [cause] | conf: [field/1x/theory] | suite valid: [version]
RF-xx | [symptom] | [action] | conf: [field/1x/theory]
BS-xx | [gap] | [root cause] | fix status: [tracked/fixed in vX.X]
FP-xx | [pattern] | [indicators] | [interpretation] | conf: [field/1x]
PR-xx | [service] | [pattern] | [probe] | [confirmation]

### Stale pattern flags
[AP/RF/FP/PR IDs that may not apply to new suite version]

### ORC-INDEX conflicts found
[section → current guide text → correct text per ORC-INDEX]

### Proposed §7 log entry
[date] | v[guide version] | suite v[X.X] | analyst: [name] | [summary]

### Proposed §8 metric updates
Sessions: N+1 | Patterns added: N | [other counters]

Approve to apply?
```

---

## §6 SELF-UPDATE SPECIFICATION

Rules Claude follows when editing this guide after an approved debrief.
This section itself is **not updated without explicit redesign approval**.

### 6.1 Update rules by section

| Section | Rule |
|---|---|
| `<!-- META -->` header | Increment `GUIDE-VERSION` (patch for pattern adds, minor for new sections/timing updates, major for structural redesign). Update `SESSIONS`, `PATTERNS`, `LAST-UPDATED`. Update `SUITE-VERSION-BASELINE` only when majority of patterns have been re-validated on the new version. |
| §0 Analyst profiles | Add new analyst blocks using the template. Update existing profile fields only when analyst explicitly requests it during debrief. Never infer preference changes. |
| §3 timing bands | Add data point to Evidence `[Nv,Ms]`. Update `Suite ver` column. Adjust band only when N≥3 sessions on same suite version agree. Note direction of change. |
| §4.1–4.5 | Append new rows. Increment evidence counts. Mark `stale` (not delete) when suite version change makes validity uncertain. Mark `superseded by XX` (not delete) when contradicted. |
| §4.6 Suite version delta | Append one row per suite version encountered. List affected pattern IDs. |
| §7 Improvement log | Append one row. Never edit prior rows. |
| §8 Metrics | Update all counters. Recalculate rates where applicable. |

### 6.2 Confidence levels

| Level | Meaning |
|---|---|
| `field` | Observed in ≥1 real engagement run |
| `1x` | Observed once — treat as hypothesis until second confirmation |
| `theory` | Derived from code reading/docs, not observed in a run |
| `stale` | Observed in prior suite version; re-validation pending |
| `superseded` | Contradicted by later evidence; kept for audit trail |

### 6.3 What is NOT updated without explicit user approval

- §1 session start paste text
- §2 commands (log paths, queries)
- §5 debrief protocol structure
- §6 self-update specification
- §7 prior log entries
- §8 prior session rows in the history table

### 6.4 ORC-INDEX conflict resolution

When ORC-INDEX (suite canonical source) conflicts with guide content:
1. Note the conflict in the debrief output (§5.2 "ORC-INDEX conflicts").
2. After approval: update §2/§3 to match ORC-INDEX.
3. Add a row to §4.6 (suite version delta) noting what changed and when.
4. Mark affected patterns as `stale` pending re-validation.

**The guide is a cache of ORC-INDEX + field observations.
ORC-INDEX always wins on structure; field observations fill in what ORC-INDEX doesn't cover.**

### 6.5 Version numbering

```
MAJOR.MINOR.PATCH
  MAJOR — structural redesign (new sections, debrief protocol changed, profile system redesigned)
  MINOR — new subsection added, timing band solidified (N≥3), suite version baseline updated
  PATCH — pattern rows added/updated, evidence counts incremented, single session learnings
```

---

## §7 IMPROVEMENT LOG

Append-only. One row per guide update session.

| Date | Guide ver | Suite ver | Sessions | Analyst | Summary |
|---|---|---|---|---|---|
| 2026-04-21 | 1.0 | 0.8 | 1 | madmin2 | Initial guide — 12 patterns seeded from <engagement> run (7 AP, 2 RF, 4 BS, 3 FP, 5 PR). Single-session timing bands. |
| 2026-04-21 | 2.0 | 0.8 | 1 | madmin2 | Major redesign: analyst profiles (§0), suite-version stamps on all patterns, ORC-INDEX integration rule, self-update spec for all three dimensions. Profile template added. |

---

## §8 METRICS

### 8.1 Session summary

| Metric | Value |
|---|---|
| Total sessions | 1 |
| Suite runs observed | 1 (see §7 improvement log for details) |
| Suite versions seen | 1 (v0.8) |
| Analysts active | 1 (madmin2) |

### 8.2 Pattern library

| Category | Count | field | 1x | theory | stale | superseded |
|---|---|---|---|---|---|---|
| AP (anti-patterns) | 7 | 7 | 0 | 0 | 0 | 0 |
| RF (red flags) | 5 | 1 | 0 | 4 | 0 | 0 |
| BS (blind spots) | 4 | 2 | 0 | 2 | 0 | 0 |
| FP (fingerprints) | 3 | 3 | 0 | 0 | 0 | 0 |
| PR (VULN patterns) | 5 | 5 | 0 | 0 | 0 | 0 |
| **Total** | **24** | **18** | **0** | **6** | **0** | **0** |

### 8.3 Effectiveness

| Metric | Value | Notes |
|---|---|---|
| RF events correctly diagnosed | — | No RF events in session 1 |
| False alarms (RF triggered, was AP) | — | — |
| Critical findings surfaced by monitor | 1 | MongoDB no-auth CVSS 10.0 — manual follow-up, not automated |
| Suite blind spots confirmed | 2 | BS-01 MongoDB, BS-02 phase_enum db_import |
| AP patterns preventing wasted investigation | 7 | All 7 AP entries active in session 1 |

### 8.4 Coverage gap closure

| Gap | Tracked since | Fixed in suite ver | Status |
|---|---|---|---|
| BASELINE_PORTS missing middleware (Fix A) | 2026-04-21 | — | open |
| masscan multi-interface preflight (Fix B) | 2026-04-21 | — | open |
| ghost host-timeout 3m → 6m (Fix B2) | 2026-04-21 | — | open |
| MongoDB probe in 07 (Fix C) | 2026-04-21 | — | open |
| phase_enum db_import (Fix D) | 2026-04-21 | — | open |

*Update "Fixed in suite ver" and Status when action-plan items land.*

---

*TechGuard. | PT-Orc Monitor Living Guide v2.0 | 2026-04-21*
*Self-updating: type `debrief` at end of session. ORC-INDEX is canonical for suite structure.*
