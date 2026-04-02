#!/root/openclaw/venv/bin/python3
"""
Afternoon social — 13:00 UTC daily.
Cards: stock movers, crypto snapshot, commodities. Each followed by platform copy text.
"""
import sys, asyncio, subprocess, requests, os, time
from datetime import datetime, timezone

sys.path.insert(0, "/root/openclaw")
from image_gen import generate_weekly_movers, send_telegram

NETCUP = "10.0.0.1"
ENV    = "set -a; source /root/metricshour/backend/.env 2>/dev/null; set +a; "
LOG_FILE = "/var/log/openclaw_crons.log"

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


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    print(f"[{ts}] [afternoon_social] {msg}", flush=True)


def _ssh(sql, timeout=30):
    cmd = sql.strip().replace("\n", " ").replace('"', '\\"')
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
                 f"root@{NETCUP}", f'{ENV} psql $DATABASE_URL -t -A -F"|" -c "{cmd}"'],
                capture_output=True, text=True, timeout=timeout,
            )
            rows = []
            for ln in (r.stdout + r.stderr).strip().splitlines():
                parts = [p.strip() for p in ln.split("|")]
                if parts[0] and not parts[0].startswith("ERROR"):
                    rows.append(parts)
            return rows
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return []


def _send_text(text):
    for attempt in range(3):
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=15,
            )
            if resp.status_code == 200:
                return
        except Exception:
            if attempt < 2:
                time.sleep(2)


def _get_stock_movers():
    rows = _ssh("""
        SELECT DISTINCT ON (a.symbol)
               a.symbol, a.name, p.close,
               CASE WHEN p.open > 0 THEN ROUND(((p.close - p.open) / p.open * 100)::numeric, 2) END AS chg
        FROM assets a
        JOIN prices p ON p.asset_id = a.id
        WHERE a.asset_type = 'stock'
          AND p.interval = '1d'
          AND p.close IS NOT NULL AND p.open > 0 AND p.close > 1
        ORDER BY a.symbol, p.timestamp DESC
    """)
    items = []
    for r in rows:
        if len(r) < 4 or not r[3]:
            continue
        try:
            items.append({"symbol": r[0], "name": r[1], "close": float(r[2]), "chg": float(r[3])})
        except Exception:
            pass
    gainers = sorted([i for i in items if i["chg"] > 0.5], key=lambda x: -x["chg"])[:4]
    losers  = sorted([i for i in items if i["chg"] < -0.5], key=lambda x: x["chg"])[:3]
    return gainers, losers


def _get_crypto():
    rows = _ssh("""
        SELECT DISTINCT ON (a.symbol)
               a.symbol, a.name, p.close,
               CASE WHEN p.open > 0 THEN ROUND(((p.close - p.open) / p.open * 100)::numeric, 2) END AS chg
        FROM assets a
        JOIN prices p ON p.asset_id = a.id
        WHERE a.asset_type = 'crypto'
          AND p.interval = '1d'
          AND p.close IS NOT NULL AND p.open > 0
          AND a.symbol IN ('BTC','ETH','SOL','BNB','XRP','ADA')
        ORDER BY a.symbol, p.timestamp DESC
    """)
    seen = {}
    for r in rows:
        if len(r) < 4 or r[0] in seen or not r[3]:
            continue
        try:
            seen[r[0]] = {"symbol": r[0], "name": r[1], "close": float(r[2]), "chg": float(r[3])}
        except Exception:
            pass
    return [seen[s] for s in ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA"] if s in seen]


def _get_commodities():
    rows = _ssh("""
        SELECT DISTINCT ON (a.symbol)
               a.symbol, a.name, p.close,
               CASE WHEN p.open > 0 THEN ROUND(((p.close - p.open) / p.open * 100)::numeric, 2) END AS chg
        FROM assets a
        JOIN prices p ON p.asset_id = a.id
        WHERE a.asset_type = 'commodity'
          AND p.interval = '1d'
          AND p.close IS NOT NULL AND p.open > 0
          AND a.symbol IN ('XAUUSD','WTI','BRENT','XAGUSD','HG','NG')
        ORDER BY a.symbol, p.timestamp DESC
    """)
    seen = {}
    for r in rows:
        if len(r) < 4 or r[0] in seen or not r[3]:
            continue
        try:
            seen[r[0]] = {"symbol": r[0], "name": r[1], "close": float(r[2]), "chg": float(r[3])}
        except Exception:
            pass
    return [seen[s] for s in ["XAUUSD", "WTI", "BRENT", "XAGUSD", "HG", "NG"] if s in seen]


async def _movers_card(gainers, losers):
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")
    items = (
        [{"label": g["name"][:22], "iso": "", "value": f"${g['close']:,.2f}", "change": g["chg"], "context": g["symbol"]} for g in gainers] +
        [{"label": l["name"][:22], "iso": "", "value": f"${l['close']:,.2f}", "change": l["chg"], "context": l["symbol"]} for l in losers]
    )
    return await generate_weekly_movers(
        title="Today's Movers", subtitle="Biggest gainers & losers",
        week_label=today, items=items, accent_color="#10b981", filename="afternoon_movers.png")


async def _crypto_card(items):
    today = datetime.now(timezone.utc).strftime("%b %d, %Y")
    return await generate_weekly_movers(
        title="Crypto Prices", subtitle="Live snapshot", week_label=today,
        items=[{"label": c["name"], "iso": "",
                "value": f"${c['close']:,.0f}" if c["close"] >= 1000 else f"${c['close']:,.2f}",
                "change": c["chg"], "context": c["symbol"]} for c in items],
        accent_color="#f59e0b", filename="afternoon_crypto.png")


async def _commodity_card(items):
    labels = {"XAUUSD": "Gold", "WTI": "WTI Oil", "BRENT": "Brent", "XAGUSD": "Silver", "HG": "Copper", "NG": "Nat Gas"}
    today  = datetime.now(timezone.utc).strftime("%b %d, %Y")
    return await generate_weekly_movers(
        title="Commodities", subtitle="Live prices", week_label=today,
        items=[{"label": labels.get(c["symbol"], c["symbol"]), "iso": "",
                "value": f"${c['close']:,.0f}" if c["close"] >= 1000 else f"${c['close']:,.2f}",
                "change": c["chg"], "context": c["symbol"]} for c in items],
        accent_color="#8b5cf6", filename="afternoon_commodities.png")


def _fmt_price(v: float) -> str:
    return f"${v:,.0f}" if v >= 1000 else f"${v:,.2f}"


def _text_movers(gainers, losers):
    day_idx = datetime.now(timezone.utc).timetuple().tm_yday
    today   = datetime.now(timezone.utc).strftime("%b %d")
    top_g   = gainers[0] if gainers else None
    top_l   = losers[0]  if losers  else None
    g_lines = "\n".join(f"  {g['symbol']} {g['chg']:+.1f}% → {_fmt_price(g['close'])}" for g in gainers)
    l_lines = "\n".join(f"  {l['symbol']} {l['chg']:+.1f}% → {_fmt_price(l['close'])}" for l in losers)

    if top_g:
        gs  = top_g["symbol"]
        gch = f"+{top_g['chg']:.1f}%"
        ls  = top_l["symbol"] if top_l else ""
        lch = f"{top_l['chg']:.1f}%" if top_l else ""
        ln  = top_l["name"]   if top_l else ""
        ldecl = f"{top_l['name']} ({top_l['symbol']}) is the notable decliner at {top_l['chg']:.1f}%." if top_l else ""
        lpair = f"{top_l['symbol']} {top_l['chg']:.1f}%" if top_l else ""
        ig_hooks = [
            f"{gs} is up {top_g['chg']:.1f}% today.\n\nMost people won't notice until it's already moved.\nHere are the names worth watching right now.",
            f"The market doesn't wait.\n\n{gs} {gch}. {ls} {lch}.\nThese are today's biggest moves — and the ones behind the move matter more than the number.",
            f"Today's movers — no noise, just data.\n\n{gs} leads the gainers at {gch}.\nKnow what's moving before it trends.",
        ]
        x_hooks = [
            f"{gs} {gch} today. {lpair} Full mover list below.",
            f"Today's biggest stock moves: {gs} leads {gch}. Data → metricshour.com/stocks",
            f"Stocks moving right now: {gs} {gch}. {lpair}",
        ]
        li_hooks = [
            f"Midday stock movers — {today}. {top_g['name']} ({gs}) is leading the session at {gch}. {ldecl} Live data tracked across 300+ names at metricshour.com.",
            f"Today's price action — the names with the most movement. {gs} {gch}, {lpair}. Full data at metricshour.com/stocks.",
        ]
        ig_hook = ig_hooks[day_idx % len(ig_hooks)]
        x_hook  = x_hooks[day_idx % len(x_hooks)]
        li_hook = li_hooks[day_idx % len(li_hooks)]
    else:
        ig_hook = f"Today's stock movers — {today}."
        x_hook  = f"Stock movers — {today}. Data at metricshour.com/stocks"
        li_hook = f"Stock movers — {today}. Full data at metricshour.com/stocks."

    movers_block = ""
    if gainers:
        movers_block += f"🟢 Gainers\n{g_lines}"
    if losers:
        movers_block += f"\n\n🔴 Losers\n{l_lines}"

    # Dynamic hashtags — ticker tags for actual movers shown
    ticker_tags = [g["symbol"] for g in gainers[:3]] + [l["symbol"] for l in losers[:2]]
    ig_tags  = " ".join(f"#{t}" for t in ["StockMarket", "Investing", "Trading", "Equities", "MarketMovers", "MetricsHour"] + ticker_tags)
    x_tags   = "#StockMarket #investing"
    li_tags  = "#StockMarket #Investing #Equities #Finance"

    x_text = f"{x_hook}\n\n{movers_block}\n\n→ metricshour.com/stocks {x_tags}"
    if len(x_text) > 280:
        x_text = x_text[:276] + "..."

    return (
        f"━━ STOCK MOVERS — {today} ━━\n\n"
        f"📸 <b>INSTAGRAM</b>\n{ig_hook}\n\n{movers_block}\n\nmetricshour.com/stocks\n\n"
        f"{ig_tags}\n\n"
        f"🐦 <b>X / TWITTER</b>\n{x_text}\n\n"
        f"👔 <b>LINKEDIN</b>\n{li_hook}\n\n{li_tags}\n\n"
        f"📘 <b>FACEBOOK</b>\n{ig_hook}\n\n{movers_block}\n\nTrack live at metricshour.com/stocks"
    )


def _text_crypto(items):
    day_idx = datetime.now(timezone.utc).timetuple().tm_yday
    today   = datetime.now(timezone.utc).strftime("%b %d")
    btc     = next((c for c in items if c["symbol"] == "BTC"), items[0] if items else None)
    eth     = next((c for c in items if c["symbol"] == "ETH"), None)
    if not btc:
        return ""

    btc_price = _fmt_price(btc["close"])
    price_lines = "\n".join(
        f"  {c['symbol']}: {_fmt_price(c['close'])} {'▲' if c['chg'] >= 0 else '▼'} {c['chg']:+.1f}%"
        for c in items
    )

    eth_str  = f"Ethereum: {_fmt_price(eth['close'])}." if eth else ""
    eth_full = f"ETH {_fmt_price(eth['close'])} ({eth['chg']:+.1f}%)." if eth else ""
    eth_pair = f"ETH {_fmt_price(eth['close'])} ({eth['chg']:+.1f}%)." if eth else ""
    ig_hooks = [
        f"Bitcoin: {btc_price}. {eth_str}\n\nThe numbers don't lie. Here's where crypto stands right now.",
        f"Crypto update — {today}.\n\nBTC {btc_price} ({btc['chg']:+.1f}%). {eth_full}\nNo narrative. Just the data.",
        f"Where is crypto right now?\n\nBTC: {btc_price} {btc['chg']:+.1f}%.\n{eth_pair}\nLive prices updated on MetricsHour.",
    ]
    x_hooks = [
        f"BTC {btc_price} ({btc['chg']:+.1f}%). {eth_pair} Crypto snapshot — {today}.",
        f"Crypto right now: BTC {btc_price} {btc['chg']:+.1f}%. Full snapshot at metricshour.com/crypto",
        f"Bitcoin {btc_price} today ({btc['chg']:+.1f}%). Live crypto data → metricshour.com/crypto",
    ]
    eth_li   = f"Ethereum at {_fmt_price(eth['close'])} ({eth['chg']:+.1f}%)." if eth else ""
    eth_li2  = f"ETH {_fmt_price(eth['close'])}, " if eth else ""
    li_hooks = [
        f"Crypto prices — {today}. Bitcoin is at {btc_price} ({btc['chg']:+.1f}% today). {eth_li} Full live data across 50 assets at metricshour.com/crypto.",
        f"Midday crypto snapshot: BTC {btc_price}, {eth_li2}and {len(items) - 2} other assets tracked live. Data at metricshour.com/crypto.",
    ]

    ig_hook = ig_hooks[day_idx % len(ig_hooks)]
    x_hook  = x_hooks[day_idx % len(x_hooks)]
    li_hook = li_hooks[day_idx % len(li_hooks)]

    # Dynamic hashtags — only symbols actually shown
    sym_tag_map = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
                   "BNB": "BNB", "XRP": "XRP", "ADA": "Cardano"}
    sym_tags = [sym_tag_map.get(c["symbol"], c["symbol"]) for c in items]
    ig_tags  = " ".join(f"#{t}" for t in ["Crypto", "CryptoCurrency"] + sym_tags[:4] + ["CryptoMarket", "MetricsHour"])
    x_tags   = " ".join(f"#{t}" for t in sym_tags[:2] + ["crypto"])
    li_tags  = "#Crypto #CryptoCurrency #DigitalAssets #CryptoMarket"

    x_text = f"{x_hook}\n\n{price_lines}\n\n{x_tags}"
    if len(x_text) > 280:
        x_text = x_text[:276] + "..."

    return (
        f"━━ CRYPTO SNAPSHOT — {today} ━━\n\n"
        f"📸 <b>INSTAGRAM</b>\n{ig_hook}\n\n{price_lines}\n\nmetricshour.com/crypto\n\n"
        f"{ig_tags}\n\n"
        f"🐦 <b>X / TWITTER</b>\n{x_text}\n\n"
        f"👔 <b>LINKEDIN</b>\n{li_hook}\n\n{li_tags}\n\n"
        f"📘 <b>FACEBOOK</b>\n{ig_hook}\n\n{price_lines}\n\nLive data at metricshour.com/crypto"
    )


def _text_commodities(items):
    day_idx = datetime.now(timezone.utc).timetuple().tm_yday
    today   = datetime.now(timezone.utc).strftime("%b %d")
    labels  = {"XAUUSD": "Gold", "WTI": "WTI Oil", "BRENT": "Brent", "XAGUSD": "Silver", "HG": "Copper", "NG": "Nat Gas"}
    gold    = next((c for c in items if c["symbol"] == "XAUUSD"), None)
    oil     = next((c for c in items if c["symbol"] in ("WTI", "BRENT")), None)

    price_lines = "\n".join(
        f"  {labels.get(c['symbol'], c['symbol'])}: {_fmt_price(c['close'])} {'▲' if c['chg'] >= 0 else '▼'} {c['chg']:+.1f}%"
        for c in items
    )

    if gold:
        gp      = _fmt_price(gold["close"])
        gch     = f"{gold['chg']:+.1f}%"
        oil_str = f"Oil: {_fmt_price(oil['close'])}." if oil else ""
        oil_x   = f"Oil {_fmt_price(oil['close'])} ({oil['chg']:+.1f}%)." if oil else ""
        oil_li  = f"oil at {_fmt_price(oil['close'])} ({oil['chg']:+.1f}%)" if oil else ""
        oil_li2 = f"Oil {_fmt_price(oil['close'])}," if oil else ""
        ig_hooks = [
            f"Gold: {gp} ({gch} today).\n\nThe commodity markets don't wait for the headlines. Here's where everything stands right now.",
            f"Commodity prices — {today}.\n\nGold: {gp}. {oil_str}\nThe real economy moves here first.",
            f"When equities are noisy, watch commodities.\n\nGold {gp} {gch}. {oil_x}\nLive data on MetricsHour.",
        ]
        x_hooks = [
            f"Gold {gp} ({gch}). {oil_x} Commodity snapshot — {today}.",
            f"Commodities right now: Gold {gp} {gch}. Full data → metricshour.com",
            f"Gold: {gp} today. {oil_str} Live commodity prices at metricshour.com",
        ]
        li_hooks = [
            f"Commodity prices — {today}. Gold at {gp} ({gch}), {oil_li}. Commodity moves tend to lead equity sector rotation — the full data set is at metricshour.com.",
            f"Midday commodity snapshot: Gold {gp}, {oil_li2} and {len(items) - 2} other markets tracked live. Data at metricshour.com.",
        ]
        ig_hook = ig_hooks[day_idx % len(ig_hooks)]
        x_hook  = x_hooks[day_idx % len(x_hooks)]
        li_hook = li_hooks[day_idx % len(li_hooks)]
    else:
        ig_hook = f"Commodity prices — {today}."
        x_hook  = f"Commodity snapshot — {today}. Data at metricshour.com"
        li_hook = f"Commodity prices — {today}. Full data at metricshour.com."

    # Dynamic hashtags — only commodities actually shown
    comm_tag_map = {"XAUUSD": "Gold", "WTI": "CrudeOil", "BRENT": "BrentCrude",
                    "XAGUSD": "Silver", "HG": "Copper", "NG": "NaturalGas"}
    comm_tags = [comm_tag_map[c["symbol"]] for c in items if c["symbol"] in comm_tag_map]
    ig_tags   = " ".join(f"#{t}" for t in ["Commodities"] + comm_tags + ["CommodityMarket", "Trading", "MetricsHour"])
    x_tags    = " ".join(f"#{t}" for t in comm_tags[:2] + ["Commodities"])
    li_tags   = "#Commodities #" + " #".join(comm_tags[:3]) + " #MacroEconomics"

    x_text = f"{x_hook}\n\n{price_lines}\n\n{x_tags}"
    if len(x_text) > 280:
        x_text = x_text[:276] + "..."

    return (
        f"━━ COMMODITIES — {today} ━━\n\n"
        f"📸 <b>INSTAGRAM</b>\n{ig_hook}\n\n{price_lines}\n\nmetricshour.com\n\n"
        f"{ig_tags}\n\n"
        f"🐦 <b>X / TWITTER</b>\n{x_text}\n\n"
        f"👔 <b>LINKEDIN</b>\n{li_hook}\n\n{li_tags}\n\n"
        f"📘 <b>FACEBOOK</b>\n{ig_hook}\n\n{price_lines}\n\nFull commodity data at metricshour.com"
    )


async def main():
    import argparse as _ap
    parser = _ap.ArgumentParser()
    parser.add_argument("--card", default="all",
        choices=["movers", "crypto", "commodities", "all"],
        help="Which card to send (default: all)")
    args = parser.parse_args()
    card = args.card

    log(f"Starting card={card}...")
    sent = 0

    if card in ("movers", "all"):
        gainers, losers = _get_stock_movers()
        log(f"gainers={len(gainers)} losers={len(losers)}")
        if gainers or losers:
            try:
                path = await _movers_card(gainers, losers)
                top  = gainers[0] if gainers else losers[0]
                cap  = f"📊 <b>Today's movers — {top['symbol']} {top['chg']:+.1f}%</b>"
                r = send_telegram(path, cap, BOT_TOKEN, CHAT_ID)
                log(f"movers: {r}")
                if r.startswith("Sent:"):
                    sent += 1
                _send_text(_text_movers(gainers, losers))
            except Exception as e:
                log(f"movers ERROR: {e}")

    if card in ("crypto", "all"):
        crypto = _get_crypto()
        log(f"crypto={len(crypto)}")
        if crypto:
            try:
                path = await _crypto_card(crypto)
                btc  = next((c for c in crypto if c["symbol"] == "BTC"), crypto[0])
                cap  = f"₿ <b>BTC ${btc['close']:,.0f} {btc['chg']:+.1f}% today</b>"
                r = send_telegram(path, cap, BOT_TOKEN, CHAT_ID)
                log(f"crypto: {r}")
                if r.startswith("Sent:"):
                    sent += 1
                _send_text(_text_crypto(crypto))
            except Exception as e:
                log(f"crypto ERROR: {e}")

    if card in ("commodities", "all"):
        commodities = _get_commodities()
        log(f"commodities={len(commodities)}")
        if commodities:
            try:
                path = await _commodity_card(commodities)
                gold = next((c for c in commodities if c["symbol"] == "XAUUSD"), commodities[0])
                cap  = f"🏅 <b>Gold ${gold['close']:,.0f} {gold['chg']:+.1f}%</b>"
                r = send_telegram(path, cap, BOT_TOKEN, CHAT_ID)
                log(f"commodities: {r}")
                if r.startswith("Sent:"):
                    sent += 1
                _send_text(_text_commodities(commodities))
            except Exception as e:
                log(f"commodities ERROR: {e}")

    log(f"Done: {sent} card(s) sent")


if __name__ == "__main__":
    asyncio.run(main())
