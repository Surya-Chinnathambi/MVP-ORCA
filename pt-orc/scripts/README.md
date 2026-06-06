<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
<!-- L2 NAV:v1 → ../../AUDIT-ORC-INDEX.md -->

<!-- MRK:README_NAV_TOC — Section index | nav,toc,index | L4-10 -->
<!-- - MRK:SCRIPTS_README_PROTOCOL — Access protocol (P1 v3) | scripts,readme,protocol,access,p1 | L11-17 -->
<!-- - MRK:SCRIPTS_README_RULES — Hard rules (P2 v2) | scripts,readme,rules,hard,p2 | L18-26 -->
<!-- - MRK:SCRIPTS_README_CONFLICT — Conflict-resolution | scripts,readme,conflict,resolution | L27-34 -->
<!-- - MRK:SCRIPTS_README_CUSTOM — Custom context (preserved) | scripts,readme,custom,context,preserved | L35-47 -->
<!-- NAV-LEN: 4 entries | Integrity-hash: 50d089b579071115 | Last-indexed: 2026-04-26T23:37:20Z -->

## MRK:SCRIPTS_README_PROTOCOL — Access protocol (P1 v3) | scripts,readme,protocol,access,p1 | L11-17

1. **Read the file header first.** Every indexed file has L1 (rules) + L2 (`NAV:v1 → <path>`) on lines 1–2 (MD) or 2–3 (shebang script). `tail -2` gives the same orientation from the bottom (mirror).
2. **Use the per-file `MRK:NAV_TOC` block.** Each file carries a TOC listing entries with exact `L<start>-<end>` ranges. Match by keyword; fetch by range.
3. **Precise fetch only.** Use `L<start>-<end>` from the MRK line. No default line count. Range missing / stale → run `reindex` before reading.
4. **Miss? Log it.** When a TOC lookup didn't contain what you expected, record in `session_lessons_log.md` (see `/orc-nav` skill). No inference effort is wasted.

## MRK:SCRIPTS_README_RULES — Hard rules (P2 v2) | scripts,readme,rules,hard,p2 | L18-26

- Never open a file without a stated purpose.
- Never bulk-read an indexed file — use the TOC.
- Never re-load a file already in context — recall from memory.
- Loading >200 lines without a target → state in one sentence what you're looking for first.
- After adding/renaming/removing any MRK anchor → run `reindex` before commit.
- Before every commit → run the composite `reindex + verify`.

## MRK:SCRIPTS_README_CONFLICT — Conflict-resolution | scripts,readme,conflict,resolution | L27-34

When the session skill (`/nav`, `/profile`) conflicts with this README:

1. **README wins for project-local overrides** — if this README explicitly overrides a skill default, obey the README.
2. **Skill wins for protocol mechanics** — read-order, anchor syntax, NAV-RULE enforcement, and reindex steps are governed by the skill.
3. **In doubt** — ask the operator before proceeding.

## MRK:SCRIPTS_README_CUSTOM — Custom context (preserved) | scripts,readme,custom,context,preserved | L35-47

<!-- BEGIN README-CUSTOM (preserved across regen — edit to add project-local overrides) -->
<!--
    CUSTOM CONTEXT / LOCAL OVERRIDES
    (Empty by default. Add directory-specific context, overrides, or
    constraints here. Reindex PRESERVES this block — it is never
    overwritten by `orc-nav-reindex.py main-index`.)
-->
<!-- END README-CUSTOM -->

<!-- L2 NAV:v1 → ../../AUDIT-ORC-INDEX.md -->
<!-- L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count) -->
