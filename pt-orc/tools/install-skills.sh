#!/bin/bash
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
# L2 NAV:v1 → ../ORC-INDEX.md

# MRK:INSTALL_SKILLS_NAV_TOC — Section index | nav,toc,index | L5-27
# - MRK:INSTALL_SKILLS_SETUP — Setup + arg parsing | install,skills,setup,arg,parsing | L28-59
# - MRK:INSTALL_SKILLS_SELECTION — Skill selection (default vs all) | install,skills,selection,skill,default | L60-69
# - MRK:INSTALL_SKILLS_HELPERS — Hash helpers + counters | install,skills,helpers,hash,counters | L70-84
# - MRK:INSTALL_SKILLS_MAIN_LOOP — Main install loop with drift check | install,skills,main,loop,drift | L85-142 | ⚠ read-toc-first
# - MRK:INSTALL_SKILLS_SUMMARY — Summary output | install,skills,summary,output | L143-151
# NAV-LEN: 5 entries | Integrity-hash: 50f8ee673c8cff8f | Last-indexed: 2026-04-24T20:37:15Z

# install-skills.sh — idempotent sync of project-local skills → user-global.
#
# Mitigates ABO-04: skill duplication drift between `skills/<name>/` (project)
# and `~/.claude/skills/<name>/` (user-global). Copies, reports deltas, checks
# integrity-hash match after copy.
#
# Default: sync only skills that CLAUDE.md marks as "user-global" (orc-nav,
# pt-orc-monitor). Use --all to sync every project-local skill.
#
# Usage:
#   bash tools/install-skills.sh            # sync default subset
#   bash tools/install-skills.sh --all      # sync every project-local skill
#   bash tools/install-skills.sh --dry-run  # show what would change
#   bash tools/install-skills.sh --check    # status only (no changes)

# MRK:INSTALL_SKILLS_SETUP — Setup + arg parsing | install,skills,setup,arg,parsing | L28-59
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_ROOT="${REPO_ROOT}/skills"
DST_ROOT="${HOME}/.claude/skills"

DEFAULT_SKILLS=(orc-nav pt-orc-monitor)

MODE="sync"
SELECTION="default"

for arg in "$@"; do
    case "$arg" in
        --all)      SELECTION="all" ;;
        --dry-run)  MODE="dry-run" ;;
        --check)    MODE="check" ;;
        --help|-h)
            grep -E "^# " "$0" | sed 's/^# \{0,1\}//' | head -25
            exit 0 ;;
        *)  echo "Unknown arg: $arg" >&2; exit 2 ;;
    esac
done

if [[ ! -d "$SRC_ROOT" ]]; then
    echo "ERR: skills/ dir not found at $SRC_ROOT" >&2
    exit 1
fi

mkdir -p "$DST_ROOT" 2>/dev/null || { echo "ERR: cannot create $DST_ROOT" >&2; exit 1; }

# MRK:INSTALL_SKILLS_SELECTION — Skill selection (default vs all) | install,skills,selection,skill,default | L60-69
declare -a SKILLS
if [[ "$SELECTION" == "all" ]]; then
    while IFS= read -r d; do
        SKILLS+=("$(basename "$d")")
    done < <(find "$SRC_ROOT" -maxdepth 1 -mindepth 1 -type d | sort)
else
    SKILLS=("${DEFAULT_SKILLS[@]}")
fi

# MRK:INSTALL_SKILLS_HELPERS — Hash helpers + counters | install,skills,helpers,hash,counters | L70-84
hash_of() {
    local f="$1"
    [[ -f "$f" ]] || { echo "-"; return; }
    grep -oE "Integrity-hash: [a-f0-9]{16}" "$f" 2>/dev/null | head -1 | awk '{print $2}' || echo "-"
}

OK_COUNT=0
DRIFT_COUNT=0
MISSING_COUNT=0
SYNCED_COUNT=0

printf "%-25s  %-18s  %-18s  %s\n" "SKILL" "SRC HASH" "DST HASH" "STATUS"
printf "%-25s  %-18s  %-18s  %s\n" "-----" "--------" "--------" "------"

# MRK:INSTALL_SKILLS_MAIN_LOOP — Main install loop with drift check | install,skills,main,loop,drift | L85-142
# NAV-RULE: read-toc-first
for name in "${SKILLS[@]}"; do
    src="$SRC_ROOT/$name"
    dst="$DST_ROOT/$name"
    src_skill="$src/SKILL.md"
    dst_skill="$dst/SKILL.md"

    if [[ ! -f "$src_skill" ]]; then
        printf "%-25s  %-18s  %-18s  %s\n" "$name" "-" "-" "SRC MISSING"
        MISSING_COUNT=$((MISSING_COUNT + 1))
        continue
    fi

    src_hash=$(hash_of "$src_skill")
    dst_hash=$(hash_of "$dst_skill")

    if [[ "$src_hash" == "$dst_hash" && "$dst_hash" != "-" ]]; then
        printf "%-25s  %-18s  %-18s  %s\n" "$name" "$src_hash" "$dst_hash" "ALIGNED"
        OK_COUNT=$((OK_COUNT + 1))
        continue
    fi

    if [[ ! -d "$dst" ]]; then
        status="INSTALL"
    else
        status="DRIFT -> sync"
    fi

    if [[ "$MODE" == "check" ]]; then
        printf "%-25s  %-18s  %-18s  %s\n" "$name" "$src_hash" "${dst_hash:--}" "$status"
        DRIFT_COUNT=$((DRIFT_COUNT + 1))
        continue
    fi

    if [[ "$MODE" == "dry-run" ]]; then
        printf "%-25s  %-18s  %-18s  %s\n" "$name" "$src_hash" "${dst_hash:--}" "$status (dry-run)"
        DRIFT_COUNT=$((DRIFT_COUNT + 1))
        continue
    fi

    rm -rf "$dst" 2>/dev/null
    if cp -r "$src" "$dst" 2>/dev/null; then
        dst_hash_new=$(hash_of "$dst_skill")
        if [[ "$src_hash" == "$dst_hash_new" ]]; then
            printf "%-25s  %-18s  %-18s  %s\n" "$name" "$src_hash" "$dst_hash_new" "SYNCED"
            SYNCED_COUNT=$((SYNCED_COUNT + 1))
        else
            printf "%-25s  %-18s  %-18s  %s\n" "$name" "$src_hash" "$dst_hash_new" "SYNC FAILED (hash mismatch)"
            exit 3
        fi
    else
        printf "%-25s  %-18s  %-18s  %s\n" "$name" "$src_hash" "-" "COPY FAILED"
        exit 4
    fi
done

echo ""
# MRK:INSTALL_SKILLS_SUMMARY — Summary output | install,skills,summary,output | L143-151
case "$MODE" in
    check)   echo "Summary: $OK_COUNT aligned, $DRIFT_COUNT drift/missing, $MISSING_COUNT src-missing (no changes made)" ;;
    dry-run) echo "Summary: $OK_COUNT aligned, $DRIFT_COUNT would-sync, $MISSING_COUNT src-missing (dry-run)" ;;
    sync)    echo "Summary: $OK_COUNT already-aligned, $SYNCED_COUNT synced, $MISSING_COUNT src-missing" ;;
esac

# L2 NAV:v1 → ../ORC-INDEX.md
# L1 ORC-NAV — read MRK:NAV_TOC first; fetch MRK ranges precisely (no default line count)
