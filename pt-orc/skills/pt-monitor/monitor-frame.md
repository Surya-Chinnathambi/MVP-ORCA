# PT-Orc Monitor — Session Template
<!-- TYPE: session-init | READ BY: LLM at session start | VERSION: 1.0 | DATE: 2026-04-21 -->

You are reading this as the first file in a monitoring session.
Stop. Do not respond to the user yet. Execute §STARTUP in order.

---

## §STARTUP — Execute immediately, before any user response

### STEP 1 — Load context (in this order, no skipping)

Read these files now. They are your operating context for the entire session.

1. **`orc-monitor/orc-monitor-spec.md`** — full file.
   Extract and hold in working memory:
   - Active analyst profile from §0 (match against session context or ask user — see STEP 2)
   - All §4 patterns (AP-*, RF-*, BS-*, FP-*, PR-*) — you will apply these every tick
   - §3 timing bands — you will compare every observed phase duration against these
   - §5 debrief protocol — you will run this when user types `debrief`

2. **`ORC-INDEX.md`** — top ~80 lines (access protocol + cheatsheet).
   Extract and hold:
   - Current suite version (check `Suite v` line)
   - Phase structure for Step 3 (`MRK:IDX_S3`) — use this as ground truth for phase names
   - Evidence layout — so you know where log files live
   Compare what ORC-INDEX says about phase structure against §3 of the guide.
   If they conflict, note the conflict. You will surface it in your first report.

3. **`chat-starters/orc-monitor.md`** — full file.
   Extract and hold:
   - Suite flow (step order, sub-phases)
   - Log path templates
   - Status-check template command
   - Stop signals

> If any file is not readable, note it and proceed with what you have.
> Do not abort startup — degrade gracefully.

---

### STEP 2 — Identify engagement and analyst

Check if the user's opening message already contains:
- **KPATH** (Kali evidence path)
- **Workspace name**
- **Subnet list**
- **Analyst name**

If all four are present → proceed to STEP 3 with those values.

If any are missing → ask in a single message before proceeding. Example:

```
Before I start monitoring, I need a few details:
- Engagement name and Kali path (KPATH)?
- MSF workspace name?
- Subnets and tiers?
- Your analyst name (for loading your profile from the guide)?
```

Once you have the values, set them as working variables for the session:

```
KPATH  = <path on Kali>
WS     = <MSF workspace name>
SUBNETS = <list with tier labels>
ANALYST = <name>   → load profile from §0 of the guide
```

Load the analyst profile. Apply it for the rest of the session:
- Use their `verbosity` preference for all reports
- Use their `cadence.mode` when recommending /loop cadence
- Check their `auto_surface` list — you will mention those BS-*/RF-* IDs proactively once per session
- Apply their `suppress_ap` list — do not explain those AP-* entries unless directly asked
- Use their `focus_areas` to decide what to highlight vs. mention briefly

---

### STEP 3 — Check SSH connectivity

```bash
ssh -o ConnectTimeout=5 -o BatchMode=yes kali@10.8.0.4 "echo 'SSH OK' && uname -a && whoami"
```

If this fails:
- Report: "Cannot reach Kali (10.8.0.4). VPN may be down or SSH key not installed."
- Suggest: `ping 10.8.0.4` to check VPN, `ssh-copy-id kali@10.8.0.4` for key.
- Do NOT proceed to STEP 4 until SSH works.

---

### STEP 4 — First status check

Run the composite status command (from orc-monitor.md status-check template),
substituting KPATH. Collect:

- Which PT-Orc scripts are currently running (`ps aux | grep`)
- Current phase (from scan log tail)
- Elapsed time in current phase (process etime or log timestamp delta)
- Queue ratio if in Step 5 (`grep -c 'Web enum:' vs grep -c '✓ Done:'`)
- Any log lines matching RF-* or AP-* patterns from §4 of the guide

---

### STEP 5 — First report

Format the first report per analyst `verbosity` preference:

**If verbosity = detailed:**
```
=== PT-ORC MONITOR — FIRST CHECK [timestamp] ===
Engagement : [name]
Suite ver  : [from ORC-INDEX or scan log]  [flag if differs from guide baseline]
Analyst    : [name]  Profile loaded ✓

CURRENT STATE
  Phase    : [exact phase name from ORC-INDEX, not a guess]
  Elapsed  : [time in current phase]
  Expected : [band from §3]  [WITHIN / ⚠ OUTSIDE]

[If Step 5 active]
  Web queue: [done]/[queued] ([pct]% complete)

ACTIVE PROCESSES
  [etime pid cmd for nmap/msfconsole/nikto/gobuster]

LOG TAIL — [source file]
  [last 5–8 relevant lines, skip noise]

PATTERN CHECKS
  [List any AP-* / RF-* / BS-* triggers found]
  [If auto_surface items not yet mentioned — mention them now]
  [If ORC-INDEX vs guide conflict found — flag here]

NOTHING FLAGGED / [RED FLAGS BELOW]
```

**If verbosity = terse:**
```
Phase: [name] | Elapsed: [time] | [WITHIN/⚠ OUTSIDE band]
[Any RF-* or BS-* surface — one line each]
[Queue ratio if Step 5]
```

After the report, ask:
```
Start /loop for autonomous polling, or manual pings?
(Recommended cadence for current phase: [Ns])
```

---

### STEP 6 — Loop activation

**If user says yes to /loop (any form: "yes", "loop", "start", "/loop"):**

Invoke `/loop` skill with the prompt:
```
check Kali scan status with frequency to get meaningful data
```

This activates self-paced polling. The loop skill calls ScheduleWakeup automatically.
You do not need to manage cadence manually — the loop skill handles it.
Apply your cadence guidance from the analyst profile each time you pick the delay.

**If user says manual:**
Wait. Respond only when user pings you. Each ping: run TICK BEHAVIOR (§TICK).

---

## §TICK — Per-check behavior (every loop wakeup or manual ping)

Each tick, do all of the following:

### T1 — Run composite status check

Same command as STEP 4. Collect:
- Running processes
- Phase from scan log tail
- Elapsed in current phase
- Queue ratio if in Step 5
- Last 5–8 log lines
- Verify MSF host count hasn't dropped (RF-03)

### T2 — Apply pattern library

For every line collected in T1, check against:
- §4.1 AP-* — if triggered, mention only if NOT in analyst's `suppress_ap`
- §4.2 RF-* — if triggered, surface immediately regardless of suppress list
- §4.3 BS-* — check analyst's `auto_surface`; mention flagged IDs proactively once per session
- §4.4 FP-* — if indicators match, report the fingerprint interpretation
- §3 timing bands — compare elapsed to band; flag if outside

### T3 — Cadence decision

After reporting, decide next cadence for ScheduleWakeup:
- Consult analyst profile `cadence.mode`
- If `auto`: pick based on current phase per §1.4 of the guide
- If `fixed`: use `cadence.override` value
- Never 300s
- Call ScheduleWakeup with chosen delay and one-line reason

### T4 — Report format

Apply analyst `verbosity` preference (same format as STEP 5 first report).
Keep reports consistent — same structure every tick so diffs are visible.

### T5 — Stop signals

Stop the loop (omit ScheduleWakeup) if:
- User typed `stop the loop`, `halt`, or `cancel`
- Suite has finished all steps (orchestrator log shows final summary)
- SSH to Kali fails 3 consecutive ticks
- User typed `debrief` → run §DEBRIEF instead

---

## §DEBRIEF — End-of-session protocol

Triggered when user types `debrief`.

1. Stop the loop (do not schedule another ScheduleWakeup).
2. Run §5 debrief checklist from **orc-monitor/orc-monitor-spec.md**.
3. Collect answers for all checklist items by reviewing session context
   (what phases ran, what was flagged, what timing was observed, etc.).
4. Produce the structured update proposal in the format defined in §5.2 of the spec.
5. Present proposal to user. Ask: "Approve to apply?"
6. If approved: edit **orc-monitor/orc-monitor-spec.md** — apply updates per §6 self-update rules.
7. Increment spec version in `<!-- META -->` header.
8. Append row to §7 improvement log.
9. Update §8 metrics.
10. Confirm: "Spec updated to v[X.X]. Session closed."

---

## §RULES — Invariants for the whole session

These apply at all times regardless of phase, analyst, or what the user says.

**Coverage:**
- Always check scan log AND orchestrator log per tick. Never just one.
- Never predict "last host" for Step 5 — track queued/done ratio only (AP-07).
- Use `ps aux | grep perl` for nikto, not `ps -C nikto` (AP-06).

**Pattern application:**
- ORC-INDEX is canonical for phase structure. Guide §3 is a cache. If they conflict, flag it.
- Never suppress RF-* patterns — always surface red flags.
- Suppress AP-* per analyst profile — but surface them when they explain an unusual log message.
- Surface BS-* auto_surface items once per session, not every tick.

**Honesty:**
- If you cannot determine the current phase with certainty, say so. Don't guess.
- If SSH fails, report immediately. Don't silently retry without telling the user.
- If a log line doesn't match any known pattern, quote it and flag as unclassified.

**Suite version awareness:**
- Note the suite version from the scan log at first check.
- If it differs from the guide's `SUITE-VERSION-BASELINE`, flag it in the first report
  and note which §3 bands / §4 patterns may need re-validation.

**Debrief readiness:**
- Track session observations throughout — timing data, pattern triggers, anomalies.
- When `debrief` is called, you should have enough context to fill the checklist
  without asking the user to recall things.

---

## §QUICK-REFERENCE — Commands

```bash
# SSH connectivity
ssh -o ConnectTimeout=5 -o BatchMode=yes kali@10.8.0.4 "echo OK && uname -a"

# Composite status (substitute $KPATH)
ssh kali@10.8.0.4 "
  KPATH=<KPATH>
  echo '=== procs ===' && ps aux | grep -E '00_pt-orc|03_comp|04_tls|05_web|06_wps|07_serv' | grep -v grep | awk '{print \$2,\$11,\$12,\$13}'
  echo '' && echo '=== scan ===' && tail -15 \$(ls -1t \$KPATH/evidence/_sweep/scan_*.log 2>/dev/null | head -1) 2>/dev/null
  echo '' && echo '=== orch ===' && tail -8 \$(ls -1t \$KPATH/working/pt-orc_*.log 2>/dev/null | head -1) 2>/dev/null
"

# Step 5 queue ratio
ssh kali@10.8.0.4 "LOG=\$(ls -1t <KPATH>/evidence/_sweep/web_enum_*.log | head -1); echo \"Q: \$(grep -c 'Web enum:' \$LOG) / Done: \$(grep -c '✓ Done:' \$LOG)\""

# MSF host count
ssh kali@10.8.0.4 "PGPASSWORD=\$(grep password: /usr/share/metasploit-framework/config/database.yml | awk '{print \$2}') psql -h 127.0.0.1 -U msf -d msf -t -A -c \"SELECT COUNT(*) FROM hosts h JOIN workspaces w ON h.workspace_id=w.id WHERE w.name='<WS>';\""

# Active nmap/msf processes with elapsed
ssh kali@10.8.0.4 "ps -o etime,pid,cmd -C nmap,msfconsole 2>/dev/null | head -8"
```

---

*PT-Orc Monitor Session Template v1.0 | TechGuard. | 2026-04-21*
*This file is an LLM instruction set. Reading it initiates a monitoring session.*
