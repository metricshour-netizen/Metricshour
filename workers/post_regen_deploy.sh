#!/bin/bash
# post_regen_deploy.sh
# Waits for regen_short_summaries.py to finish, runs sanity checks, then deploys.
# Runs fully in background — survives session shutdown.

set -euo pipefail
LOG=/tmp/post_regen_deploy.log
exec >> "$LOG" 2>&1

REGEN_PID=${1:-""}
DEPLOY_HOOK=$(grep CF_PAGES_DEPLOY_HOOK /root/metricshour/backend/.env | cut -d= -f2-)
VENV=/root/metricshour/workers/venv/bin/python3
BACKEND=/root/metricshour/backend

echo "[$(date)] post_regen_deploy.sh started (watching PID $REGEN_PID)"

# ── 1. Wait for regen to finish ──────────────────────────────────────────────
if [ -n "$REGEN_PID" ]; then
  while kill -0 "$REGEN_PID" 2>/dev/null; do
    sleep 15
  done
  echo "[$(date)] Regen PID $REGEN_PID exited."
else
  echo "[$(date)] No PID given — proceeding immediately."
fi

# ── 2. Sanity checks ─────────────────────────────────────────────────────────
echo "[$(date)] Running sanity checks..."

$VENV - <<'PYEOF'
import sys
sys.path.insert(0, "/root/metricshour/backend")
from dotenv import load_dotenv
load_dotenv("/root/metricshour/backend/.env")
from app.database import SessionLocal
from app.models.summary import PageSummary

with SessionLocal() as db:
    rows = db.query(PageSummary).filter(PageSummary.entity_type == "country").all()
    total = len(rows)
    short = [r for r in rows if len(r.summary.split()) < 180]
    ok    = [r for r in rows if len(r.summary.split()) >= 180]
    avg   = sum(len(r.summary.split()) for r in rows) / total if total else 0

    print(f"Total country summaries : {total}")
    print(f"  >= 180 words          : {len(ok)}")
    print(f"  <  180 words          : {len(short)}")
    print(f"  Average word count    : {avg:.0f}")

    if short:
        print("  Still short:")
        for r in short[:20]:
            print(f"    {r.entity_code} — {len(r.summary.split())} words")

    # Fail if more than 20 countries are still short
    if len(short) > 20:
        print(f"FAIL: {len(short)} summaries still short — not deploying.")
        sys.exit(1)

    print("CHECK PASSED — proceeding to deploy.")
PYEOF

# ── 3. API health check ───────────────────────────────────────────────────────
echo "[$(date)] Checking API health..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$STATUS" != "200" ]; then
  echo "FAIL: API health check returned $STATUS — not deploying."
  exit 1
fi
echo "[$(date)] API healthy ($STATUS)."

# ── 4. Trigger Cloudflare Pages deploy ───────────────────────────────────────
echo "[$(date)] Triggering Cloudflare Pages deploy..."
RESULT=$(curl -s -X POST "$DEPLOY_HOOK")
echo "[$(date)] Deploy response: $RESULT"

SUCCESS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('success','false'))")
if [ "$SUCCESS" = "True" ] || [ "$SUCCESS" = "true" ]; then
  echo "[$(date)] Deploy triggered successfully. All done."
else
  echo "[$(date)] Deploy hook returned unexpected response."
  exit 1
fi
