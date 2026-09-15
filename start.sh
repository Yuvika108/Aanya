#!/usr/bin/env bash
# =============================================================================
# Aanya — Auto-Restart Server Launcher
# Usage:  bash start.sh
# The server will restart automatically if it crashes.
# Press Ctrl+C once to stop it permanently.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Activate virtual-env if present ──────────────────────────────────────────
if [[ -d ".venv" ]]; then
  source .venv/bin/activate
  echo "✅  Virtual env activated (.venv)"
elif [[ -d "venv" ]]; then
  source venv/bin/activate
  echo "✅  Virtual env activated (venv)"
fi

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; RESET='\033[0m'

# ── Ensure .env is present ────────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  echo -e "${RED}❌  .env not found. Create it with GEMINI_API_KEY=<your-key>${RESET}"
  exit 1
fi

# ── Trap Ctrl+C so we can exit cleanly ───────────────────────────────────────
STOP=0
trap 'echo -e "\n${YELLOW}⏹  Stopping Aanya...${RESET}"; STOP=1; kill "$SERVER_PID" 2>/dev/null; exit 0' INT TERM

PORT="${PORT:-8000}"
RESTART_DELAY=3        # seconds to wait before restarting after a crash
CRASH_COUNT=0
MAX_CRASHES=10         # stop if it crashes this many times in a row

echo -e "${GREEN}"
echo "  ✦  AANYA — Auto-Restart Launcher"
echo "  Serving on http://localhost:${PORT}"
echo "  Press Ctrl+C to stop."
echo -e "${RESET}"

while [[ $STOP -eq 0 ]]; do
  # ── Start the server ───────────────────────────────────────────────────────
  python app.py &
  SERVER_PID=$!

  echo -e "${GREEN}🚀  Started  (PID ${SERVER_PID})  — $(date '+%H:%M:%S')${RESET}"

  wait "$SERVER_PID"
  EXIT_CODE=$?

  [[ $STOP -eq 1 ]] && break

  CRASH_COUNT=$((CRASH_COUNT + 1))
  echo -e "${RED}⚠️   Server exited (code ${EXIT_CODE}) — crash #${CRASH_COUNT}${RESET}"

  if [[ $CRASH_COUNT -ge $MAX_CRASHES ]]; then
    echo -e "${RED}❌  Too many crashes (${MAX_CRASHES}). Giving up. Check logs above.${RESET}"
    exit 1
  fi

  echo -e "${YELLOW}♻️   Restarting in ${RESTART_DELAY}s...${RESET}"
  sleep "$RESTART_DELAY"
done
