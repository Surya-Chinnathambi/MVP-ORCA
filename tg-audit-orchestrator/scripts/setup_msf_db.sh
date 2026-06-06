#!/usr/bin/env bash
# =============================================================================
# setup_msf_db.sh — One-time MSF PostgreSQL database setup for PT-Orc
#
# Run this ONCE before your first vapt_run.sh.
# Safe to re-run — detects existing setup and just starts PostgreSQL if needed.
#
# Usage:
#   sudo scripts/setup_msf_db.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${CYAN}[msf-db]${NC} $*"; }
ok()   { echo -e "${GREEN}[msf-db] ✓${NC} $*"; }
warn() { echo -e "${YELLOW}[msf-db] ⚠${NC}  $*"; }
die()  { echo -e "${RED}[msf-db] ✗${NC} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Must run as root: sudo $0"

MSF_DB_CONF="/usr/share/metasploit-framework/config/database.yml"

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  MSF Database Setup — PT-Orc prerequisite${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ── 1. Check PostgreSQL is installed ─────────────────────────────────────────
log "Checking PostgreSQL installation..."
if ! command -v psql &>/dev/null; then
    log "psql not found — installing postgresql..."
    apt-get update -qq
    apt-get install -y postgresql
fi
ok "PostgreSQL binary found: $(psql --version)"

# ── 2. Enable postgresql to start on boot ────────────────────────────────────
systemctl enable postgresql 2>/dev/null || true
log "PostgreSQL enabled at boot"

# ── 3. Init or start the MSF database ────────────────────────────────────────
if [[ ! -f "$MSF_DB_CONF" ]]; then
    log "database.yml not found — running msfdb init (first-time, ~30 s)..."
    msfdb init
    ok "msfdb init complete"
else
    log "database.yml exists — starting PostgreSQL..."
    msfdb start || true
    sleep 3
fi

# ── 4. Verify connection ──────────────────────────────────────────────────────
log "Testing database connection..."
user=$(grep -m1 'username:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"")
pass=$(grep -m1 'password:' "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"")
db=$(grep -m1 'database:'   "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"")
port=$(grep -m1 'port:'     "$MSF_DB_CONF" | awk '{print $2}' | tr -d "'\"")
port="${port:-5432}"

result=$(PGPASSWORD="$pass" psql -h 127.0.0.1 -p "$port" -U "$user" -d "$db" \
         -t -A -c "SELECT version();" 2>&1)

if echo "$result" | grep -q "PostgreSQL"; then
    ok "Connection successful"
    log "  Host    : 127.0.0.1:$port"
    log "  User    : $user"
    log "  Database: $db"
else
    warn "Connection test failed:"
    echo "  $result"
    die "Fix: check 'systemctl status postgresql' and 'msfdb status'"
fi

# ── 5. Verify msfconsole can reach the DB ────────────────────────────────────
log "Testing msfconsole db_status..."
result=$(msfconsole -q -x "db_status; exit" 2>/dev/null | grep -i "connected\|postgresql\|error" | head -3)
if echo "$result" | grep -qi "connected\|postgresql"; then
    ok "msfconsole sees DB: $result"
else
    warn "msfconsole db_status output: $result"
    warn "If this shows 'not connected' but psql works, check:"
    warn "  cat $MSF_DB_CONF"
fi

# ── 6. Write credentials to pt-orc.conf ──────────────────────────────────────
PTORC_CONF="/home/kali/audit-orc-vapt/pt-orc/scripts/pt-orc.conf"
if [[ -f "$PTORC_CONF" ]]; then
    log "Ensuring pt-orc.conf has correct MSF_DB_CONF path..."
    if ! grep -q "^MSF_DB_CONF=" "$PTORC_CONF"; then
        echo "" >> "$PTORC_CONF"
        echo "# MSF database config (set by setup_msf_db.sh)" >> "$PTORC_CONF"
        echo "MSF_DB_CONF=\"$MSF_DB_CONF\"" >> "$PTORC_CONF"
    fi
    if ! grep -q "^MSF_DB_PASS=" "$PTORC_CONF"; then
        echo "MSF_DB_PASS=\"$pass\"" >> "$PTORC_CONF"
        echo "MSF_DB_USER=\"$user\"" >> "$PTORC_CONF"
        echo "MSF_DB_NAME=\"$db\"" >> "$PTORC_CONF"
        echo "MSF_DB_PORT=\"$port\"" >> "$PTORC_CONF"
    fi
    ok "pt-orc.conf updated with MSF DB credentials"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}MSF database is ready.${NC}"
echo ""
echo "  database.yml : $MSF_DB_CONF"
echo "  PostgreSQL   : 127.0.0.1:$port"
echo "  MSF user     : $user / db: $db"
echo ""
echo -e "  You can now run: ${CYAN}sudo scripts/vapt_run.sh --client ... --domains ...${NC}"
echo ""
