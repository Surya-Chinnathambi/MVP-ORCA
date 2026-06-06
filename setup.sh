#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MVP_ORCA — Full Setup Script for Kali Linux
# Usage:  bash setup.sh
#         bash setup.sh --demo    (also creates sample team + VAPT project)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$REPO_ROOT/tg-audit-orchestrator"
PTORC_DIR="$REPO_ROOT/pt-orc"
TOOLS_DIR="$REPO_ROOT/tools"
DEMO_MODE=false

for arg in "$@"; do [[ "$arg" == "--demo" ]] && DEMO_MODE=true; done

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
info() { echo -e "${CYAN}[..] $*${NC}"; }
warn() { echo -e "${YELLOW}[!!]${NC}  $*"; }
die()  { echo -e "${RED}[ERR]${NC} $*"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗"
echo -e "║      MVP_ORCA — TG Audit Orchestrator Setup      ║"
echo -e "╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Check Python version ───────────────────────────────────────────────────
info "Checking Python version..."
PY=$(python3 --version 2>&1 | awk '{print $2}')
PYMAJ=$(echo "$PY" | cut -d. -f1)
PYMIN=$(echo "$PY" | cut -d. -f2)
if [[ $PYMAJ -lt 3 || ($PYMAJ -eq 3 && $PYMIN -lt 11) ]]; then
    die "Python 3.11+ required. Found: $PY"
fi
ok "Python $PY"

# ── 2. Install system packages ────────────────────────────────────────────────
info "Installing system dependencies (requires sudo)..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-venv python3-pip \
    tesseract-ocr tesseract-ocr-eng \
    nmap dnsutils curl wget git \
    libpq-dev gcc \
    > /dev/null 2>&1 || warn "Some apt packages may have failed — continuing"
ok "System packages installed"

# ── 3. Install jq shim ────────────────────────────────────────────────────────
info "Installing Python jq shim to ~/.local/bin/jq..."
mkdir -p "$HOME/.local/bin"
cp "$TOOLS_DIR/jq" "$HOME/.local/bin/jq"
chmod +x "$HOME/.local/bin/jq"
# Prepend to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
    SHELL_RC="$HOME/.bashrc"
    [[ -f "$HOME/.zshrc" ]] && SHELL_RC="$HOME/.zshrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    warn "Added ~/.local/bin to PATH in $SHELL_RC (reload your shell or run: source $SHELL_RC)"
fi
ok "jq shim installed at ~/.local/bin/jq"

# ── 4. Fix PT-Orc script permissions ─────────────────────────────────────────
info "Setting execute permissions on PT-Orc scripts..."
chmod +x "$PTORC_DIR"/scripts/*.sh 2>/dev/null || true
ok "PT-Orc scripts are executable"

# Update scan_runner.py SCRIPTS_DIR to point to this repo's pt-orc/scripts
RUNNER="$APP_DIR/app/services/scan_runner.py"
if [[ -f "$RUNNER" ]]; then
    PTORC_SCRIPTS="$PTORC_DIR/scripts"
    # Replace the hardcoded path
    sed -i "s|SCRIPTS_DIR = Path(\".*\")|SCRIPTS_DIR = Path(\"$PTORC_SCRIPTS\")|" "$RUNNER"
    ok "scan_runner.py SCRIPTS_DIR → $PTORC_SCRIPTS"
fi

# ── 5. Create Python virtual environment ─────────────────────────────────────
cd "$APP_DIR"
info "Creating Python virtual environment..."
if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
fi
ok "Virtual environment ready"

# ── 6. Install Python dependencies ───────────────────────────────────────────
info "Installing Python packages (this may take a few minutes)..."
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -e ".[dev]" --quiet
ok "Python packages installed"

# ── 7. Create .env file ───────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
    info "Creating .env from template..."
    cp .env.example .env
    # Generate a random SECRET_KEY
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|change-me-in-production-use-32-char-minimum|$SECRET|" .env
    ok ".env created with random SECRET_KEY"
    warn "Edit .env to set CLAUDE_API_KEY and TELEGRAM_BOT_TOKEN if needed"
else
    ok ".env already exists — skipping"
fi

# ── 8. Create data directories ────────────────────────────────────────────────
info "Creating data directories..."
mkdir -p data/{evidence,deliverables,scan_jobs,pilot_vapt_out,backups}
ok "data/ directories ready"

# ── 9. Run database migrations ────────────────────────────────────────────────
info "Running database migrations..."
alembic upgrade head
ok "Database migrations complete"

# ── 10. Seed roles + admin user ───────────────────────────────────────────────
info "Seeding roles and admin user..."
python scripts/seed.py
ok "Seed complete"

# ── 11. Demo team (optional) ──────────────────────────────────────────────────
if [[ "$DEMO_MODE" == true ]]; then
    info "Setting up demo VAPT team and project..."
    python scripts/setup_team_vapt.py
    ok "Demo team created"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗"
echo -e "║              Setup Complete!                    ║"
echo -e "╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}Start the platform:${NC}"
echo -e "    cd $APP_DIR"
echo -e "    source .venv/bin/activate"
echo -e "    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo -e "  ${CYAN}Open in browser:${NC}  http://localhost:8000"
echo ""
echo -e "  ${CYAN}Default admin login:${NC}"
echo -e "    Email   : admin@techguard.local"
echo -e "    Password: changeme"
echo ""

if [[ "$DEMO_MODE" == true ]]; then
    echo -e "  ${CYAN}Demo team credentials:${NC}"
    echo -e "    Hari (PM)         : hari@techguard.lab   / Hari\@TG2026"
    echo -e "    Surya (Lead)      : surya@techguardlabs.com / Surya\@TG2026"
    echo -e "    Shivani (Consult) : shivani@techguardlabs.com / Shivani\@TG2026"
    echo -e "    Srimithila (Consult): srimithila@techguardlabs.com / Srimithila\@TG2026"
    echo ""
fi

echo -e "  ${YELLOW}Note:${NC} Edit ${APP_DIR}/.env to set CLAUDE_API_KEY for AI features"
echo ""
