#!/root/openclaw/venv/bin/python3
"""
Daily reel wrapper — runs once per day at 11:00 UTC.
Rotates through reel styles by day-of-week, fetches a live price hook,
then delegates to run_smart_reel.py.

Schedule:
  Mon: stock_analysis  — AAPL
  Tue: crypto_update   — bitcoin
  Wed: trade_spotlight — US-CN
  Thu: country_deep_dive — US
  Fri: commodities     — gold
  Sat: market_recap    — markets
  Sun: crypto_update   — ethereum
"""
import os, sys, subprocess, time, datetime, json

LOG_FILE = "/var/log/openclaw_crons.log"
API_BASE = "https://api.metricshour.com/api"

# Load env
_env_file = "/root/.config/moltis/.env"
try:
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
except Exception:
    pass

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    line = f"[{ts}] [daily_reel] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def tg_error(msg: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        import urllib.request
        data = json.dumps({"chat_id": CHAT_ID, "text": msg}).encode()
        req  = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


# ── Day-of-week schedule (0=Mon … 6=Sun) ────────────────────────────────────
SCHEDULE = {
    0: {"style": "stock_analysis",   "subject": "AAPL"},
    1: {"style": "crypto_update",    "subject": "bitcoin"},
    2: {"style": "trade_spotlight",  "subject": "US-CN"},
    3: {"style": "country_deep_dive","subject": "US"},
    4: {"style": "commodities",      "subject": "gold"},
    5: {"style": "market_recap",     "subject": "markets"},
    6: {"style": "crypto_update",    "subject": "ethereum"},
}

# ── Hook templates per style ─────────────────────────────────────────────────
def build_hook(style: str, subject: str) -> str:
    """Fetch live price data and return a one-line hook for the title card."""
    try:
        import urllib.request
        symbol_map = {
            "AAPL":     ("stocks",      "AAPL"),
            "bitcoin":  ("crypto",      "BTC"),
            "ethereum": ("crypto",      "ETH"),
            "gold":     ("commodities", "XAUUSD"),
        }
        if subject in symbol_map:
            asset_type, sym = symbol_map[subject]
            url = f"{API_BASE}/assets/{sym}?asset_type={asset_type}"
            req = urllib.request.Request(url, headers={"User-Agent": "daily_reel/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            price  = data.get("price", {})
            close  = price.get("close")
            chg    = price.get("change_pct")
            name   = data.get("name", subject)
            if close and chg is not None:
                direction = "▲" if chg >= 0 else "▼"
                return f"{name} {direction} {abs(chg):.1f}% — trading at ${close:,.2f}"
    except Exception as e:
        log(f"hook fetch failed: {e}")

    # Fallback hooks per style
    fallbacks = {
        "market_recap":     "Markets update: key moves you need to know",
        "crypto_update":    "Crypto markets: where prices stand right now",
        "trade_spotlight":  "US-China trade: the latest numbers",
        "country_deep_dive":"US economic snapshot — live data",
        "commodities":      "Commodities: gold, oil, copper in focus",
        "stock_analysis":   "Stock spotlight: key metrics that matter",
    }
    return fallbacks.get(style, "Latest market data — live update")


def main() -> None:
    dow = datetime.datetime.utcnow().weekday()  # 0=Mon
    plan = SCHEDULE[dow]
    style   = plan["style"]
    subject = plan["subject"]

    log(f"Day {dow} → style={style} subject={subject}")

    hook = build_hook(style, subject)
    log(f"Hook: {hook}")

    runner = "/root/openclaw/crons/run_smart_reel.py"
    cmd = [
        sys.executable, runner,
        "--style",   style,
        "--subject", subject,
        "--hook",    hook,
    ]

    log(f"Launching: {' '.join(cmd[:4])} ...")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        tg_error(f"❌ daily_reel failed (style={style} subject={subject})")
        sys.exit(result.returncode)
    log("daily_reel complete")


if __name__ == "__main__":
    main()
