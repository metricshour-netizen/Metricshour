#!/root/openclaw/venv/bin/python3
"""
Daily reel wrapper — 3 slots per day (morning/midday/evening).
Usage:
  python3 daily_reel.py --slot morning   # 11:00 UTC
  python3 daily_reel.py --slot midday    # 14:00 UTC
  python3 daily_reel.py --slot evening   # 17:00 UTC
"""
import os, sys, subprocess, time, datetime, json, argparse, urllib.request

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
        data = json.dumps({"chat_id": CHAT_ID, "text": msg}).encode()
        req  = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


# ── 3-slot schedule (0=Mon … 6=Sun) ─────────────────────────────────────────
SCHEDULE = {
    "morning": {   # 11:00 UTC — flagship reel
        0: {"style": "stock_analysis",    "subject": "AAPL"},
        1: {"style": "crypto_update",     "subject": "bitcoin"},
        2: {"style": "trade_spotlight",   "subject": "US-CN"},
        3: {"style": "country_deep_dive", "subject": "US"},
        4: {"style": "commodities",       "subject": "gold"},
        5: {"style": "market_recap",      "subject": "markets"},
        6: {"style": "crypto_update",     "subject": "ethereum"},
    },
    "midday": {    # 14:00 UTC — different angle
        0: {"style": "market_recap",      "subject": "markets"},
        1: {"style": "country_deep_dive", "subject": "CN"},
        2: {"style": "crypto_update",     "subject": "ethereum"},
        3: {"style": "stock_analysis",    "subject": "NVDA"},
        4: {"style": "trade_spotlight",   "subject": "DE-CN"},
        5: {"style": "commodities",       "subject": "oil"},
        6: {"style": "country_deep_dive", "subject": "DE"},
    },
    "evening": {   # 17:00 UTC — close/recap
        0: {"style": "commodities",       "subject": "oil"},
        1: {"style": "trade_spotlight",   "subject": "US-MX"},
        2: {"style": "stock_analysis",    "subject": "MSFT"},
        3: {"style": "crypto_update",     "subject": "ethereum"},
        4: {"style": "market_recap",      "subject": "markets"},
        5: {"style": "stock_analysis",    "subject": "TSLA"},
        6: {"style": "trade_spotlight",   "subject": "CN-EU"},
    },
}

# ── API symbol map for live hook ─────────────────────────────────────────────
HOOK_API = {
    "AAPL":     ("stocks",      "AAPL"),
    "NVDA":     ("stocks",      "NVDA"),
    "MSFT":     ("stocks",      "MSFT"),
    "TSLA":     ("stocks",      "TSLA"),
    "bitcoin":  ("crypto",      "BTC"),
    "ethereum": ("crypto",      "ETH"),
    "gold":     ("commodities", "XAUUSD"),
    "oil":      ("commodities", "WTI"),
}

FALLBACK_HOOKS = {
    "market_recap":     "Markets update — key moves right now",
    "crypto_update":    "Crypto: where prices stand today",
    "trade_spotlight":  "Trade data: the real numbers",
    "country_deep_dive":"Economic snapshot — live data",
    "commodities":      "Commodities: prices that move markets",
    "stock_analysis":   "Stock spotlight — metrics that matter",
}


def build_hook(style: str, subject: str) -> str:
    if subject in HOOK_API:
        asset_type, sym = HOOK_API[subject]
        try:
            url = f"{API_BASE}/assets/{sym}?asset_type={asset_type}"
            req = urllib.request.Request(url, headers={"User-Agent": "daily_reel/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                d = json.loads(resp.read().decode())
            p    = d.get("price", {})
            close = p.get("close")
            chg   = p.get("change_pct")
            name  = d.get("name", subject)
            if close is not None and chg is not None:
                arrow = "▲" if chg >= 0 else "▼"
                sign  = "+" if chg >= 0 else ""
                price_str = f"${close:,.2f}" if close < 10000 else f"${close:,.0f}"
                return f"{name} {arrow} {sign}{chg:.2f}% — {price_str}"
        except Exception as e:
            log(f"hook fetch failed ({subject}): {e}")
    return FALLBACK_HOOKS.get(style, "Live market data — MetricsHour")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default="morning", choices=["morning", "midday", "evening"])
    args = parser.parse_args()

    dow  = datetime.datetime.now(datetime.timezone.utc).weekday()
    plan = SCHEDULE[args.slot][dow]
    style   = plan["style"]
    subject = plan["subject"]

    log(f"slot={args.slot} dow={dow} → style={style} subject={subject}")

    hook = build_hook(style, subject)
    log(f"Hook: {hook}")

    runner = "/root/openclaw/crons/run_smart_reel.py"
    cmd = [sys.executable, runner, "--style", style, "--subject", subject, "--hook", hook]

    log(f"Launching run_smart_reel ...")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        tg_error(f"❌ daily_reel [{args.slot}] failed (style={style} subject={subject})")
        sys.exit(result.returncode)
    log(f"done [{args.slot}]")


if __name__ == "__main__":
    main()
