---
name: pt-orc-monitor
description: Use when monitoring live PT-Orc scans — setup, periodic checks, anomaly spotting, session debrief. Activates on mentions of "monitoring", "live scan", "watch scan", "ssh to tester", "/loop", "debrief", or when the user asks to start or continue a PT-Orc monitoring session. Derives log paths and phase structure from ORC-INDEX (canonical) rather than hardcoding. Personalised per analyst via profiles in monitor-spec.md. Self-improves via the `debrief` trigger at session end, which appends learnings to monitor-spec.md.
---

<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->

<!-- MRK:SKILL_NAV_TOC — Section index | nav,toc,index | L9-25 -->
<!-- - MRK:MON_ACTIVATE — Activate when | mon,activate | L26-33 -->
<!-- - MRK:MON_FIRSTREAD — First read | mon,firstread,first,read | L34-45 -->
<!-- - MRK:MON_CORELOOP — Core loop | mon,coreloop,core,loop | L46-53 -->
<!-- - MRK:MON_CADENCE — /loop cadence | mon,cadence,loop | L54-61 -->
<!-- - MRK:MON_ANOMALY — Anomaly discipline | mon,anomaly,discipline | L62-72 -->
<!-- - MRK:MON_DEBRIEF — Debrief protocol | mon,debrief,protocol | L73-86 -->
<!-- - MRK:MON_ORCNAV — Integration with /orc-nav | mon,orcnav,integration,orc,nav | L87-115 -->
<!-- - MRK:MON_DONT — Don't | mon,dont,don | L116-126 -->
<!-- - MRK:MON_PERMS — Permissions | mon,perms,permissions | L127-148 -->
<!-- - MRK:MON_INSTALL — Install as user-global skill (optional) | mon,install,user,global,skill | L149-161 -->
<!-- NAV-LEN: 10 entries | Integrity-hash: c1811d1c95a3a2d2 | Last-indexed: 2026-04-24T20:37:14Z -->

# PT-Orc Monitor Skill

Companion to [`monitor-spec.md`](monitor-spec.md) (the Living Guide) and [`monitor-frame.md`](monitor-frame.md) (operational frame). This skill orchestrates how an LLM behaves during a live-scan monitoring session.

## MRK:MON_ACTIVATE — Activate when | mon,activate | L26-33

- User is actively running a PT-Orc phase (`00_pt-orc.sh`, `03_comp_scan.sh`, etc.) and wants monitoring
- User says: "monitor the scan", "watch 03", "tail the log", "what's 03 doing", "check progress"
- User pastes a session-start message including `Analyst: <name>`
- User says `debrief` (session-end trigger — initiate self-update protocol)
- User opens `/loop` referencing monitor

## MRK:MON_FIRSTREAD — First read | mon,firstread,first,read | L34-45

On activation, load in this order:

1. [`monitor-spec.md`](monitor-spec.md) §0 — identify active analyst profile (cadence, verbosity, focus areas)
2. [`monitor-spec.md`](monitor-spec.md) §1 — setup checklist (VPN, SSH, paste, /loop)
3. [`monitor-spec.md`](monitor-spec.md) §2 — canonical log paths (or derive from `ORC-INDEX.md`)
4. [`monitor-spec.md`](monitor-spec.md) §3 — phase timing reference (expected bands)
5. [`monitor-frame.md`](monitor-frame.md) — behavioral defaults when the spec is silent

Do NOT bulk-load the whole spec. Fetch sections by MRK anchor per the `/orc-nav` skill's read-order protocol — this file itself is NAV-indexed.

## MRK:MON_CORELOOP — Core loop | mon,coreloop,core,loop | L46-53

1. **Setup**: confirm VPN, SSH to tester host, locate the active phase's log file (from ORC-INDEX or spec §2).
2. **Baseline**: snapshot current phase, elapsed time, queue ratios.
3. **Tick** (every N seconds per analyst profile cadence): sample log, compare to baseline, flag anomalies.
4. **Anomaly**: follow §4 pattern library to classify (red flag / anti-pattern / blind spot). Report per analyst verbosity.
5. **Session end / `debrief`**: run the debrief protocol (§5) — structured update proposal for monitor-spec.md.

## MRK:MON_CADENCE — /loop cadence | mon,cadence,loop | L54-61

Default cadence chosen from analyst profile's `cadence.mode`:
- `auto` → pick based on observed phase (ghost tier → 270s; normal → 180s; loud → 60s)
- `<Ns>` override → use fixed interval N seconds

Clamp to `[60, 3600]`. Stay under 270s while the phase is mid-pass (prompt cache hit). Drop to 1200–1800s when genuinely idle (e.g., waiting for db_nmap workspace import).

## MRK:MON_ANOMALY — Anomaly discipline | mon,anomaly,discipline | L62-72

Never just report "scan is running". Every tick-report includes at minimum:
- **Phase** (e.g., `03 pass_tcp pass 1`)
- **Elapsed** (since phase start)
- **Signal** (normal / watching / anomaly)

If anomaly: follow-up depth per analyst profile:
- `deep` → investigate before surfacing (SSH in, check log, form hypothesis)
- `shallow` → report and ask user to decide

## MRK:MON_DEBRIEF — Debrief protocol | mon,debrief,protocol | L73-86

When user says `debrief` (or session ends organically):

1. **Summarize** the session: phases observed, duration, anomalies caught, misses.
2. **Propose updates** to monitor-spec.md using its §6 self-update rules:
   - New anti-patterns observed → append to §4
   - Phase timing refinements → update §3
   - Analyst-profile tweaks → update §0 for this analyst
3. **Structured proposal** — diff-style, one section at a time. User approves or rejects each.
4. **Apply approved edits** to monitor-spec.md. Bump META `GUIDE-VERSION` (patch bump: 2.0 → 2.1) and increment `SESSIONS`.
5. **Reindex**: `python tools/orc-nav-reindex.py reindex monitor/monitor-spec.md`.
6. **Commit**: atomic, message like `monitor: v2.1 — <N> patterns + timing refinement from <date> session`.

## MRK:MON_ORCNAV — Integration with /orc-nav | mon,orcnav,integration,orc,nav | L87-115

Respect orc-nav read-order and edit protocol at all times — including mid-session when monitoring surfaces something that looks fixable.

### Reading any NAV:v1 file

Three steps, no shortcuts, no "obviously small file" exceptions:

1. **Header first** — lines 1–2 (MD) or 1–3 (shebang). Confirms v1 + tells you the index path.
2. **`MRK:NAV_TOC`** — match query keywords to a MRK anchor before fetching any content.
3. **Precise range fetch** — use the exact `L<start>-<end>` from the TOC entry. No default line count, no "read the next 50 lines".

### Before editing any NAV:v1 file

Never go straight from "found the problem" to "implementing the fix." The required flow is:

1. **Document** the finding — session log, follow-up tracker, or a quick summary to the user.
2. **Propose** the specific change: which file, which MRK section (with tag), what the edit is, and why it belongs there.
3. **Wait for explicit go-ahead** before touching any file.
4. **Then execute**: read NAV_TOC → precise-fetch the target section → make the edit → add/update MRK anchor if the section is new or moved → reindex → verify → commit atomically.

### Why the proposal gate matters during monitoring

Monitoring sessions create the strongest pressure to skip this: the bug is live, the fix is obvious, the context is fresh. That's exactly when the shortcut hurts most. A rushed edit to an indexed file can displace MRK line ranges, break TOC accuracy, and corrupt integrity hashes for every subsequent session. Five minutes saved now means a reindex audit later — not worth it.

### Miss tracking

Track miss events in the shared `session_lessons_log.md` (project root). Monitor-specific misses (e.g., log path not where spec said) go in the same log — they feed both skills' self-improvement.

## MRK:MON_DONT — Don't | mon,dont,don | L116-126

- Don't monitor without an analyst profile — creates generic, low-signal output.
- Don't edit monitor-spec.md without `debrief` trigger + user approval of each proposed change.
- Don't skip the reindex + commit after monitor-spec.md edits.
- Don't run /loop faster than 60s or slower than 3600s.
- Don't mix monitoring into implementation work — start a new session if the user pivots.
- Don't go from finding/anomaly directly to a file edit — document → propose → get explicit go-ahead → then edit with orc-nav protocol.
- Don't read or edit a NAV:v1 file without reading its header (lines 1–3) and `MRK:NAV_TOC` first.
- Don't treat "fix X" or "extend Y" as implicit permission to implement — propose the concrete change and wait for a yes.

## MRK:MON_PERMS — Permissions | mon,perms,permissions | L127-148

The skill invokes host-level tools (SSH, log tails, MSF/psql queries, network checks). PT-Orc ships the canonical permission set in [`.claude/settings.json`](../.claude/settings.json) (project-scoped — team-wide). Any team member cloning this repo inherits these permissions automatically.

Required categories (full list lives in `.claude/settings.json`):

- **Log inspection**: `tail`, `head`, `cat`, `less`, `grep`, `awk`, `sed`, `wc`
- **SSH / remote**: `ssh`, `scp`
- **MSF / DB**: `msfconsole`, `msfdb`, `psql`, `pg_dump`
- **Process inspection**: `ps`, `pgrep`, `pidof`, `uptime`
- **Network checks**: `ping`, `nc`, `curl`, `dig`, `nslookup`, `ss`, `netstat`
- **Net config (read-only)**: `ip`, `ifconfig`, `route`
- **VPN setup**: `openvpn`
- **File / disk**: `ls`, `find`, `stat`, `du`, `df`, `file`
- **Service status (read-only)**: `systemctl status`, `systemctl is-active`, `journalctl`
- **Running phase scripts**: `./00_pt-orc.sh … ./07_service_verify.sh`, `sudo ./00_pt-orc.sh`

Explicit denies (to prevent destructive ops even inside an interactive debug):
- `ssh * rm -rf`, `ssh * sudo rm`, `pkill`, `kill -9`, `systemctl stop|disable|enable|restart`, `service stop`, `iptables -F|-X`, `ufw disable`

Confirmation required (`ask`): `kill`, `scp * /` (root-dest scp).

## MRK:MON_INSTALL — Install as user-global skill (optional) | mon,install,user,global,skill | L149-161

To have this skill auto-activate outside the PT-Orc repo:
```bash
cp -r skills/pt-orc-monitor ~/.claude/skills/pt-orc-monitor
# then also copy the monitor-specific permissions into your
# ~/.claude/settings.json (allow / deny / ask arrays)
```

(Renamed at install-time because skills/ dir expects unique names; `monitor` is a generic word, `pt-orc-monitor` disambiguates globally.)

<!-- L2 NAV:v1 → ../../ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
