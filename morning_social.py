#!/root/openclaw/venv/bin/python3
"""
Daily social content — zero LLM.
Queries Netcup DB → finds best angle → generates 4 distribution-ready cards → sends to Telegram.
Each card is followed by a platform copy block (Instagram / X / LinkedIn) ready to paste.
Runs at 09:05 UTC daily via crontab.
"""
import sys, asyncio, subprocess, requests, argparse, json
from datetime import datetime, timezone

sys.path.insert(0, "/root/openclaw")
from image_gen import (
    generate_stat_spotlight,
    generate_trade_shift,
    generate_ranking_visual,
    generate_did_you_know,
    send_telegram,
)

TELEGRAM_BOT_TOKEN = "8675605406:AAGl8wIqkGPbRYXXD5sidAY8ihSoZWVbC5M"
TELEGRAM_CHAT_ID   = "7884960961"
NETCUP = "10.0.0.1"
ENV    = "set -a; source /root/metricshour/backend/.env 2>/dev/null; set +a; "

_DATA_CURRENCY: dict = {}

STATE_FILE = "/root/.moltis/morning_social_state.json"

def _load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"corridors": [], "indicators": [], "ranking_types": [], "countries": []}

def _save_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


# ─── helpers ──────────────────────────────────────────────────────────────────

def _ssh(sql: str, timeout: int = 30) -> list[list[str]]:
    import time
    cmd = sql.strip().replace("\n", " ").replace('"', '\\"')
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
                 f"root@{NETCUP}", f'{ENV} psql $DATABASE_URL -t -A -F"|" -c "{cmd}"'],
                capture_output=True, text=True, timeout=timeout,
            )
            out = (r.stdout + r.stderr).strip()
            rows = []
            for line in out.splitlines():
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 1 and parts[0] and not parts[0].startswith("ERROR"):
                    rows.append(parts)
            return rows
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return []


def _send_text(text: str) -> None:
    """Send a plain text message to Telegram."""
    import time
    for attempt in range(3):
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
                timeout=15,
            )
            if resp.status_code == 200:
                return
            if attempt < 2:
                time.sleep(2 ** attempt)
        except Exception as e:
            if attempt == 2:
                print(f"  _send_text error: {e}")


def _check_data_currency() -> dict:
    global _DATA_CURRENCY
    trade_rows = _ssh("SELECT MAX(year) FROM trade_pairs")
    trade_year = int(trade_rows[0][0]) if trade_rows and trade_rows[0][0] else 2023
    ind_rows = _ssh("SELECT MAX(period_date) FROM country_indicators WHERE period_date <= CURRENT_DATE")
    ind_date_str = ind_rows[0][0] if ind_rows and ind_rows[0][0] else "2024-01-01"
    ind_year = int(ind_date_str[:4]) if ind_date_str else 2024
    current_year = datetime.now(timezone.utc).year
    _DATA_CURRENCY = {
        "trade_year":  trade_year,
        "ind_year":    ind_year,
        "ind_date":    ind_date_str,
        "trade_stale": current_year - trade_year > 4,
        "ind_stale":   current_year - ind_year > 3,
    }
    return _DATA_CURRENCY


def _fmt(v: float) -> str:
    if v >= 1e12: return f"${v/1e12:.1f}T"
    if v >= 1e9:  return f"${v/1e9:.0f}B"
    if v >= 1e6:  return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


KNOWN_ISO = {
    "United States": "US", "China": "CN", "Germany": "DE", "Japan": "JP",
    "France": "FR", "United Kingdom": "GB", "Netherlands": "NL",
    "South Korea": "KR", "Italy": "IT", "Canada": "CA", "Mexico": "MX",
    "Russia": "RU", "Brazil": "BR", "India": "IN", "Australia": "AU",
    "Spain": "ES", "Belgium": "BE", "Switzerland": "CH", "Poland": "PL",
    "Sweden": "SE", "Vietnam": "VN", "Indonesia": "ID", "Thailand": "TH",
    "Malaysia": "MY", "Singapore": "SG", "Saudi Arabia": "SA",
    "United Arab Emirates": "AE", "Turkey": "TR", "South Africa": "ZA",
    "Argentina": "AR", "Ireland": "IE", "Taiwan": "TW", "Hong Kong": "HK",
    "Austria": "AT", "Denmark": "DK", "Norway": "NO", "Finland": "FI",
    "Czech Republic": "CZ", "Hungary": "HU", "Romania": "RO",
    "Ukraine": "UA", "Egypt": "EG", "Chile": "CL", "Colombia": "CO",
    "Philippines": "PH", "Pakistan": "PK", "Bangladesh": "BD",
    "New Zealand": "NZ", "Portugal": "PT", "Greece": "GR", "Panama": "PA",
}

# Country → hashtag slug (no # prefix)
COUNTRY_TAGS = {
    "United States": ["USA", "USEconomy", "USTrade"],
    "China": ["China", "ChineseEconomy", "ChinaTrade"],
    "Germany": ["Germany", "GermanEconomy"],
    "Japan": ["Japan", "JapanEconomy"],
    "United Kingdom": ["UK", "BritishEconomy"],
    "France": ["France", "FrenchEconomy"],
    "India": ["India", "IndianEconomy"],
    "South Korea": ["SouthKorea", "KoreanEconomy"],
    "Canada": ["Canada", "CanadianEconomy"],
    "Netherlands": ["Netherlands", "DutchTrade"],
    "Australia": ["Australia", "AussieEconomy"],
    "Mexico": ["Mexico", "MexicanEconomy"],
    "Brazil": ["Brazil", "BrazilEconomy"],
    "Russia": ["Russia", "RussianEconomy"],
    "Saudi Arabia": ["SaudiArabia", "SaudiEconomy"],
    "Singapore": ["Singapore", "SGEconomy"],
    "Vietnam": ["Vietnam", "VietnamEconomy"],
    "Indonesia": ["Indonesia", "IndonesianEconomy"],
}

INDICATOR_TAGS = {
    "gdp_usd":                 ["GDP", "NationalEconomy", "EconomicSize"],
    "gdp_growth_pct":          ["EconomicGrowth", "GDP", "GrowthRate"],
    "exports_usd":             ["Exports", "TradeData", "GlobalTrade"],
    "government_debt_gdp_pct": ["NationalDebt", "PublicFinance", "FiscalPolicy"],
    "gini_coefficient":        ["Inequality", "WealthGap", "IncomeInequality"],
    "inflation_cpi_pct":       ["Inflation", "CPI", "CostOfLiving"],
    "unemployment_rate_pct":   ["Unemployment", "JobMarket", "LaborMarket"],
    "current_account_gdp_pct": ["CurrentAccount", "TradeBalance", "GlobalFinance"],
    "gdp_per_capita_usd":      ["GDPPerCapita", "LivingStandards", "WealthByCountry"],
}

INDICATOR_WHY = {
    "gdp_usd":                 "GDP size determines bargaining power in trade and financial markets.",
    "gdp_growth_pct":          "Growth rate signals where capital will flow next.",
    "exports_usd":             "Export strength reflects industrial competitiveness and global reach.",
    "government_debt_gdp_pct": "High debt-to-GDP constrains fiscal policy and often pressures the currency.",
    "gini_coefficient":        "Inequality shapes consumer spending, political stability, and investment risk.",
    "inflation_cpi_pct":       "Inflation data drives central bank decisions that move global markets.",
    "unemployment_rate_pct":   "Unemployment shapes consumer demand and monetary policy direction.",
    "current_account_gdp_pct": "Current account balance reveals whether a country lives within its means.",
    "gdp_per_capita_usd":      "GDP per capita is the most direct measure of average living standards.",
}


def _iso(name: str) -> str:
    return KNOWN_ISO.get(name, name[:2].upper())


# ─── platform copy engine ─────────────────────────────────────────────────────

_BRAND_TAGS = ["MetricsHour", "FinancialData"]

def _hashtag_block(base: list[str], countries: list[str] = None, indicator: str = None,
                   limit: int = 12, add_brand: bool = True) -> str:
    """Build a hashtag string. base = list of slug strings without #.
    Brand tags (#MetricsHour #FinancialData) appended last when add_brand=True."""
    tags = list(base)
    for c in (countries or []):
        tags += COUNTRY_TAGS.get(c, [c.replace(" ", "")])
    if indicator:
        tags += INDICATOR_TAGS.get(indicator, [])
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)
    # Reserve last 2 slots for brand tags
    cap = max(0, limit - (2 if add_brand else 0))
    result = unique[:cap]
    if add_brand:
        for bt in _BRAND_TAGS:
            if bt.lower() not in {r.lower() for r in result}:
                result.append(bt)
    return " ".join(f"#{t}" for t in result)


def _platform_copy_trade(corridor: dict) -> str:
    """Generate IG / X / LinkedIn copy for trade corridor cards."""
    exp, imp = corridor["exporter"], corridor["importer"]
    val = corridor["now_val"]
    yr  = corridor["year_now"]
    then_val = corridor.get("then_val")
    year_then = corridor.get("year_then")
    day_idx = datetime.now(timezone.utc).timetuple().tm_yday

    if then_val and year_then:
        pct = ((val / then_val) - 1) * 100
        years = yr - year_then
        if pct >= 100:
            ig_variants = [
                (f"{_fmt(val)}/year — that's what {exp} and {imp} trade today.\n"
                 f"Up {pct:.0f}% from {_fmt(then_val)} in {year_then}.\n"
                 f"This corridor built real dependencies. And those don't unwind quietly."),
                (f"Most people don't track the {exp}–{imp} trade corridor.\n"
                 f"They probably should.\n"
                 f"{_fmt(then_val)} in {year_then}. {_fmt(val)} today. {pct:.0f}% expansion in {years} years.\n"
                 f"Every tariff move touches this number."),
                (f"{pct:.0f}% growth in {years} years. {exp} → {imp}.\n"
                 f"From {_fmt(then_val)} to {_fmt(val)}.\n"
                 f"That kind of trajectory creates supply chain dependencies the headlines rarely price in."),
                (f"The {exp}–{imp} trade relationship is worth {_fmt(val)}/year.\n"
                 f"That's {pct:.0f}% higher than {year_then}.\n"
                 f"Somewhere in that number are the stocks your portfolio is already exposed to."),
            ]
            x_variants = [
                f"{exp}–{imp} trade: +{pct:.0f}% in {years} years. Now {_fmt(val)}. ({yr})",
                f"{_fmt(val)}/year between {exp} and {imp}. Up {pct:.0f}% since {year_then}. The dependency is deeper than it looks.",
                f"{exp} ↔ {imp}: {_fmt(val)} in {yr} trade. That's {pct:.0f}% growth in {years} years.",
            ]
            li_variants = [
                (f"The {exp}–{imp} trade corridor grew {pct:.0f}% over {years} years to {_fmt(val)} in {yr}. "
                 f"That scale of expansion creates durable revenue dependencies for multinational companies operating in both markets — "
                 f"and material exposure to any policy shift that disrupts the flow."),
                (f"Trade data that tends to be underweighted in equity analysis: {exp}–{imp} bilateral trade reached {_fmt(val)} in {yr}, "
                 f"up {pct:.0f}% from {_fmt(then_val)} in {year_then}. "
                 f"Companies with significant revenue in either market carry more correlated risk than most portfolio models suggest."),
            ]
            hook_ig  = ig_variants[day_idx % len(ig_variants)]
            hook_x   = x_variants[day_idx % len(x_variants)]
            hook_li  = li_variants[day_idx % len(li_variants)]
        elif pct <= -20:
            ig_variants = [
                (f"{exp}–{imp} trade is down {abs(pct):.0f}% in {years} years.\n"
                 f"{_fmt(then_val)} → {_fmt(val)}.\n"
                 f"Structural declines like this reprice entire sectors. The question is which ones."),
                (f"The {exp}–{imp} corridor fell {abs(pct):.0f}% in {years} years.\n"
                 f"From {_fmt(then_val)} to {_fmt(val)} — and the contraction isn't done.\n"
                 f"Companies still priced for the old relationship have the most to lose."),
                (f"Here's a trade story most analysts missed.\n"
                 f"{exp}–{imp}: down {abs(pct):.0f}% in {years} years.\n"
                 f"The corridor that used to be worth {_fmt(then_val)} is now {_fmt(val)}.\n"
                 f"That's a structural shift, not a cycle."),
            ]
            x_variants = [
                f"{exp}–{imp} trade fell {abs(pct):.0f}% in {years} years. Now {_fmt(val)}. Structural, not cyclical.",
                f"The {exp}–{imp} corridor: -{abs(pct):.0f}% over {years} years. {_fmt(val)} remaining. ({yr})",
            ]
            li_variants = [
                (f"The {exp}–{imp} trade corridor contracted {abs(pct):.0f}% over {years} years, from {_fmt(then_val)} to {_fmt(val)} by {yr}. "
                 f"The decline reflects structural factors — not cyclical softness — and has material implications for companies "
                 f"with revenue concentrated in either market."),
            ]
            hook_ig  = ig_variants[day_idx % len(ig_variants)]
            hook_x   = x_variants[day_idx % len(x_variants)]
            hook_li  = li_variants[day_idx % len(li_variants)]
        else:
            ig_variants = [
                (f"{exp} ↔ {imp}: {_fmt(val)}/year in trade ({yr}).\n"
                 f"{'Up' if pct >= 0 else 'Down'} {abs(pct):.0f}% from {year_then}.\n"
                 f"The goods mix shifts. The dependency doesn't."),
                (f"{_fmt(val)}. That's the {exp}–{imp} trade corridor in {yr}.\n"
                 f"{abs(pct):.0f}% {'higher' if pct >= 0 else 'lower'} than {years} years ago.\n"
                 f"The corridor is smaller than the headlines — but the leverage is real."),
            ]
            x_variants = [
                f"{exp} ↔ {imp}: {_fmt(val)}/year ({yr}). {'+' if pct >= 0 else ''}{pct:.0f}% vs {year_then}.",
                f"{exp}–{imp} trade: {_fmt(val)} in {yr}. {abs(pct):.0f}% {'growth' if pct >= 0 else 'decline'} over {years} years.",
            ]
            li_variants = [
                (f"The {exp}–{imp} bilateral trade corridor registered {_fmt(val)} in {yr}, "
                 f"{abs(pct):.0f}% {'above' if pct >= 0 else 'below'} its {year_then} level. "
                 f"Data for 200+ countries tracked at metricshour.com."),
            ]
            hook_ig  = ig_variants[day_idx % len(ig_variants)]
            hook_x   = x_variants[day_idx % len(x_variants)]
            hook_li  = li_variants[day_idx % len(li_variants)]
    else:
        # No comparison data — size-based hook
        if val >= 500e9:
            ig_variants = [
                (f"{exp} and {imp} move {_fmt(val)} worth of goods every year.\n"
                 f"That makes this one of the largest bilateral trade corridors on earth.\n"
                 f"Every tariff announcement touches this number."),
                (f"{_fmt(val)}/year. {exp} ↔ {imp}.\n"
                 f"One of the world's biggest trade corridors.\n"
                 f"The stocks exposed to both markets are worth checking."),
            ]
            hook_ig = ig_variants[day_idx % len(ig_variants)]
            hook_x  = f"{exp} ↔ {imp}: {_fmt(val)}/year ({yr}). One of the world's largest trade corridors."
            hook_li = (f"The {exp}–{imp} corridor reached {_fmt(val)} in {yr}, "
                       f"placing it among the world's largest bilateral trade relationships.")
        else:
            ig_variants = [
                (f"{exp} → {imp}: {_fmt(val)} in annual trade ({yr}).\n"
                 f"Smaller than the top corridors — but the goods dependency runs deep.\n"
                 f"The companies in the middle of this flow are worth knowing."),
                (f"The {exp}–{imp} trade corridor: {_fmt(val)}/year.\n"
                 f"Not the biggest number. But the dependencies it creates are real — and they show up in revenue lines."),
            ]
            hook_ig = ig_variants[day_idx % len(ig_variants)]
            hook_x  = f"{exp} ↔ {imp}: {_fmt(val)} in annual trade ({yr}). Full data → metricshour.com"
            hook_li = (f"The {exp}–{imp} bilateral trade corridor registered {_fmt(val)} in {yr}. "
                       f"Geographic revenue concentration from both markets is trackable at the stock level on metricshour.com.")

    # Facebook copy
    if then_val and year_then:
        pct = ((val / then_val) - 1) * 100
        years = yr - year_then
        dir_word = "grew" if pct >= 0 else "fell"
        fb_variants = [
            (f"The {exp}–{imp} trade corridor {dir_word} {abs(pct):.0f}% over {years} years, "
             f"reaching {_fmt(val)} in {yr} (from {_fmt(then_val)} in {year_then}).\n\n"
             f"That shift changes which companies carry the most revenue exposure. "
             f"The full bilateral breakdown — including which listed stocks are most affected — is at metricshour.com."),
            (f"{exp}–{imp} trade: {_fmt(then_val)} in {year_then}. {_fmt(val)} in {yr}. "
             f"A {abs(pct):.0f}% {'expansion' if pct >= 0 else 'contraction'} in {years} years.\n\n"
             f"See the full corridor data and stock exposure breakdown at metricshour.com."),
        ]
        hook_fb = fb_variants[day_idx % len(fb_variants)]
    else:
        fb_variants = [
            (f"{exp} and {imp} exchange {_fmt(val)} annually ({yr} data).\n\n"
             f"The size of a trade corridor determines which companies feel every policy shift first. "
             f"Full bilateral breakdown — and the stocks most exposed — at metricshour.com."),
            (f"One corridor. {_fmt(val)}/year. {exp} ↔ {imp}.\n\n"
             f"Most investors don't look at bilateral trade data until it's too late. "
             f"Full data at metricshour.com."),
        ]
        hook_fb = fb_variants[day_idx % len(fb_variants)]

    tags_ig = _hashtag_block(
        ["GlobalTrade", "TradeData", "InternationalTrade",
         "Economics", "MacroEconomics", "TradePolicy"],
        countries=[exp, imp],
        limit=12,
    )
    tags_x  = _hashtag_block(["TradeData", "GlobalTrade"], countries=[exp, imp], limit=3, add_brand=False)
    tags_li = _hashtag_block(["GlobalTrade", "TradeData", "Economics"], countries=[exp, imp], limit=5, add_brand=False)

    x_text = f"{hook_x}\n\n→ metricshour.com {tags_x}"
    if len(x_text) > 280:
        x_text = x_text[:276] + "..."

    return (
        f"━━ CARD 1 & 2 — TRADE CORRIDOR ━━\n\n"
        f"📸 <b>INSTAGRAM</b>\n{hook_ig}\n\nFull corridor data at metricshour.com\n\n{tags_ig}\n\n"
        f"🐦 <b>X / TWITTER</b>\n{x_text}\n\n"
        f"👔 <b>LINKEDIN</b>\n{hook_li} Full corridor data at metricshour.com.\n\n{tags_li}\n\n"
        f"📘 <b>FACEBOOK</b>\n{hook_fb}"
    )


def _platform_copy_ranking(items: list) -> str:
    """Generate IG / X / LinkedIn copy for ranking card."""
    if not items:
        return ""
    title  = items[0].get("_title", "World's Top Exporters")
    metric = items[0].get("_metric", "Trade volume")
    top    = items[0]["label"]
    top_v  = items[0]["value"]
    second = items[1]["label"] if len(items) > 1 else ""
    day_idx = datetime.now(timezone.utc).timetuple().tm_yday

    # Multi-variant hooks keyed by title: (ig_variants, x_variants, li_variants, fb_variants)
    HOOK_VARIANTS = {
        "World's Top Exporters": (
            [
                f"10 countries move most of the world's goods.\n\n{top} is #1 — {top_v} in exports.\n{f'{second} is close behind.' if second else ''}\nThese rankings define which supply chains run the world.",
                f"Where do global exports actually come from?\n\n{top}: {top_v}. {f'{second} is #2.' if second else ''}\nThe full picture is messier — and more useful — than most macro maps show.",
                f"Top global exporters by volume — ranked.\n\n{top} leads at {top_v}.\nCompany-level exposure tracked at metricshour.com.",
            ],
            [
                f"World's top exporters: {top} #1 at {top_v}.",
                f"Largest export economies: {top} leads at {top_v}. {f'{second} is #2.' if second else ''} Full list below.",
                f"{top} leads global exports at {top_v}. The full ranking → metricshour.com",
            ],
            [
                f"The world's 10 largest exporters by volume — {top} leads at {top_v}. These rankings shift slowly, but the companies that depend on each corridor feel every move in real-time.",
                f"Export concentration data: {top} leads globally at {top_v}. For equity investors, company exposure to each top exporter's trade flows is trackable at metricshour.com.",
            ],
            [
                f"Where does the world's trade actually originate?\n\n{top} leads with {top_v} in exports. {f'{second} ranks second.' if second else ''}\n\nThese rankings don't change often. But when they do, entire industries reprice. Full data at metricshour.com.",
                f"The world's 10 biggest export economies — and {top} is still #1 at {top_v}.\n\nUnderstanding who drives global trade is the starting point for understanding which stocks carry the real exposure. Full breakdown at metricshour.com.",
            ],
        ),
        "World's Top Importers": (
            [
                f"The 10 biggest import markets on earth.\n\n{top} is #1 — {top_v} in imports.\n{f'{second} is #2.' if second else ''}\nEvery export-dependent stock has a relationship with these numbers.",
                f"Who absorbs the world's goods?\n\n{top}: {top_v} in imports. {f'{second} is right behind.' if second else ''}\nThese are the markets where trade policy matters most.",
            ],
            [
                f"World's top importers: {top} #1 at {top_v}.",
                f"Largest import markets: {top} leads at {top_v}. Every trade tariff announcement lands here first.",
            ],
            [
                f"The world's 10 largest import markets — {top} leads at {top_v}. These rankings determine where export-dependent companies make or lose margin when trade conditions shift.",
                f"Import market ranking: {top} at #1 with {top_v}. {f'{second} at #2.' if second else ''} The revenue exposure of S&P 500 companies to top import markets is quantifiable — and rarely fully priced in.",
            ],
            [
                f"The world's biggest import markets define where trade policy has the most teeth.\n\n{top} is #1 at {top_v}. {f'{second} is close behind.' if second else ''}\n\nFull import data for 80+ countries at metricshour.com.",
            ],
        ),
        "Largest G20 Economies": (
            [
                f"G20 economies ranked by GDP.\n\n{top}: {top_v}. That's the world's biggest economy.\n{f'{second} is #2.' if second else ''}\nThe gap at the top shapes every rate decision and trade negotiation.",
                f"Size matters in economics.\n\n{top}: {top_v} GDP — #1 in the G20.\n{f'{second} trails.' if second else ''}\nWhere the money is determines where the rules get set.",
            ],
            [
                f"G20 GDP ranking: {top} #1 at {top_v}.",
                f"Largest G20 economies: {top} leads at {top_v}. {f'{second} is #2.' if second else ''}",
            ],
            [
                f"G20 GDP ranking: {top} leads at {top_v}. {f'{second} is second.' if second else ''} The size differential at the top of the global economy shapes monetary policy divergence, currency dynamics, and multinational revenue exposure.",
                f"Economic scale data: {top} remains the world's largest G20 economy at {top_v}. For companies with significant international revenue, the relative size of these markets is a primary driver of FX exposure and demand risk.",
            ],
            [
                f"G20 economies by GDP — and {top} is still #1 at {top_v}.\n\n{f'{second} is #2.' if second else ''} The gap between the world's largest economies shapes everything from interest rates to currency movements to how much your international stocks are worth.\n\nFull data at metricshour.com.",
            ],
        ),
        "Fastest Growing Economies": (
            [
                f"The fastest-growing economies right now.\n\n{top}: {top_v} GDP growth. {f'{second} is #2.' if second else ''}\nGrowth at this pace attracts capital — and creates the kind of inflation that forces central bank hands.",
                f"GDP growth leaders.\n\n{top} is growing fastest at {top_v}.\nCapital follows growth — until inflation forces the central bank to slam the brakes.",
            ],
            [
                f"Fastest growing economies: {top} #1 at {top_v} GDP growth.",
                f"GDP growth leaders: {top} at {top_v}. Fast growth attracts capital — and policy risk.",
            ],
            [
                f"GDP growth rate leaders: {top} at #1 with {top_v} growth. {f'{second} follows.' if second else ''} The fastest-growing economies often run elevated inflation — the central bank response is the risk that equity investors typically underweight.",
                f"Growth rate ranking: {top} leads at {top_v}. Rapid GDP expansion tends to compress credit spreads and attract FDI — until overheating forces a policy response. The trajectory matters more than the snapshot.",
            ],
            [
                f"The world's fastest-growing economies — and {top} is leading at {top_v}.\n\nFast growth attracts capital, compresses spreads, and eventually forces inflation policy responses. The full ranking at metricshour.com.",
            ],
        ),
    }

    variants = HOOK_VARIANTS.get(title)
    if variants:
        ig_vars, x_vars, li_vars, fb_vars = variants
        ig_hook = ig_vars[day_idx % len(ig_vars)]
        x_hook  = x_vars[day_idx % len(x_vars)]
        li_hook = li_vars[day_idx % len(li_vars)]
        fb_hook = fb_vars[day_idx % len(fb_vars)]
    else:
        ig_hook = f"{title}\n\n#1: {top} at {top_v}.\n{f'#2: {second}.' if second else ''}\nFull data → metricshour.com"
        x_hook  = f"{title}: {top} leads at {top_v}."
        li_hook = f"{title}: {top} leads at {top_v}. Full data at metricshour.com."
        fb_hook = f"{title}: {top} leads at {top_v}. {f'{second} is #2.' if second else ''} Full breakdown at metricshour.com."

    is_trade_based = metric in ("Export volume", "Import volume")
    base_tags = (
        ["GlobalTrade", "TradeData", "WorldTrade", "InternationalTrade",
         "Economics", "MacroEconomics", "EconomicData"]
        if is_trade_based else
        ["Economics", "GDP", "MacroEconomics", "EconomicData",
         "WorldEconomy", "GlobalFinance", "EconomicGrowth"]
    )
    tags_ig = _hashtag_block(base_tags, countries=[top, second] if second else [top], limit=12)
    tags_x  = _hashtag_block(["Economics", "DataViz"], countries=[top], limit=3, add_brand=False)
    tags_li = _hashtag_block(["Economics", "MacroEconomics"], countries=[top], limit=5, add_brand=False)

    x_text = f"{x_hook}\n\nFull ranking → metricshour.com {tags_x}"
    if len(x_text) > 280:
        x_text = x_text[:276] + "..."

    return (
        f"━━ CARD 3 — RANKING ━━\n\n"
        f"📸 <b>INSTAGRAM</b>\n{ig_hook}\n\nFull ranking at metricshour.com\n\n{tags_ig}\n\n"
        f"🐦 <b>X / TWITTER</b>\n{x_text}\n\n"
        f"👔 <b>LINKEDIN</b>\n{li_hook} Full data at metricshour.com.\n\n{tags_li}\n\n"
        f"📘 <b>FACEBOOK</b>\n{fb_hook}"
    )


def _platform_copy_macro(fact: dict) -> str:
    """Generate IG / X / LinkedIn copy for macro fact card."""
    country  = fact["country"]
    label    = fact["label"]
    ind_key  = fact["indicator"]
    val      = fact["value"]
    rank     = fact.get("rank", 1)
    order    = fact.get("order", "DESC")
    source   = fact["source"]
    data_yr  = fact.get("data_year", "")
    runner   = fact.get("runner_up", "")
    runner_v = fact.get("runner_up_val")

    if ind_key in ("gdp_usd", "exports_usd", "gdp_per_capita_usd"):
        val_str = _fmt(val)
    else:
        val_str = f"{val:.1f}%"

    rank_word = {1: "leads", 2: "is #2", 3: "is #3"}.get(rank, f"ranks #{rank}")
    dir_word  = "lowest" if order == "ASC" else "highest"
    day_idx   = datetime.now(timezone.utc).timetuple().tm_yday

    why = INDICATOR_WHY.get(ind_key, "")
    yr_label = f" ({data_yr})" if data_yr else ""
    runner_val_str = ""
    runner_line = ""
    if runner and runner_v:
        rv_str = _fmt(runner_v) if ind_key in ("gdp_usd", "exports_usd", "gdp_per_capita_usd") else f"{runner_v:.1f}%"
        runner_val_str = rv_str
        runner_line = f"\nRunner-up: {runner} at {rv_str}."

    # Multi-variant hooks — varied by indicator and day
    HOOK_VARIANTS_IG = {
        "gdp_usd": [
            f"{country} has a {val_str} economy — {'the largest in the world' if rank==1 else f'#{rank} globally'}{yr_label}.\n{runner_line.strip()}\n{why}",
            f"The world's {'largest' if rank==1 else f'#{rank}'} economy: {country} at {val_str} GDP.\n{runner_line.strip()}\n{why}",
            f"{val_str}. That's {country}'s total GDP{yr_label}.\nAt this scale, fiscal decisions here send shockwaves across every major market.",
        ],
        "gdp_growth_pct": [
            f"{country} {'grew' if order == 'DESC' else 'contracted'} {val_str} — {'fastest' if rank==1 else f'#{rank}'} in the world{yr_label}.\n{runner_line.strip()}\n{why}",
            f"{val_str} GDP {'growth' if order == 'DESC' else 'contraction'}. {country} is {'#1 globally' if rank==1 else f'#{rank}'}{yr_label}.\n{why}",
            f"{'Fastest' if rank==1 else f'#{rank}'} growing major economy: {country} at {val_str}{yr_label}.\nCapital follows this number — until inflation forces the policy response.",
        ],
        "exports_usd": [
            f"{country} exports {val_str}/year — {'the largest exporter globally' if rank==1 else f'#{rank} globally'}{yr_label}.\n{runner_line.strip()}\n{why}",
            f"{val_str} in annual exports. {country} is {'the top exporter globally' if rank==1 else f'#{rank}'}{yr_label}.\n{why}",
            f"{'#1' if rank==1 else f'#{rank}'} in global exports: {country} at {val_str}{yr_label}.\nEvery supply chain that touches this country runs through these numbers.",
        ],
        "government_debt_gdp_pct": [
            f"{country} carries {val_str} debt-to-GDP — {'the highest' if rank==1 else f'#{rank}'} in the world{yr_label}.\n{runner_line.strip()}\n{why}",
            f"{val_str} debt-to-GDP. {country} ranks {'#1' if rank==1 else f'#{rank}'} globally{yr_label}.\n{why}",
            f"Debt at {val_str} of GDP. {country} is {'the most indebted major economy' if rank==1 else f'#{rank} globally'}{yr_label}.\nThis level constrains fiscal options and pressures the currency.",
        ],
        "gini_coefficient": [
            f"{country} has the {'highest' if rank==1 else f'#{rank}'} income inequality globally — Gini {val_str}{yr_label}.\n{runner_line.strip()}\n{why}",
            f"Inequality index: {country} at {val_str} Gini{yr_label}.\n{'Highest in the world.' if rank==1 else f'#{rank} globally.'}\n{why}",
            f"{val_str} Gini coefficient — {country} ranks {'#1' if rank==1 else f'#{rank}'} in income inequality{yr_label}.\nInequality shapes political stability, consumer spending, and investment risk.",
        ],
        "inflation_cpi_pct": [
            f"{country}: {val_str} inflation — {'highest' if rank==1 else f'#{rank}'} on record{yr_label}.\n{runner_line.strip()}\n{why}",
            f"{val_str} CPI. {country} is running {'the hottest inflation on earth' if rank==1 else f'#{rank} globally'}{yr_label}.\n{why}",
            f"Inflation at {val_str}. {country} ranks {'#1' if rank==1 else f'#{rank}'} globally{yr_label}.\nAt this level, central bank decisions here move currencies and bond markets worldwide.",
        ],
        "unemployment_rate_pct": [
            f"{country}: {val_str} unemployment rate — {'highest' if rank==1 else f'#{rank}'} globally{yr_label}.\n{runner_line.strip()}\n{why}",
            f"{val_str} unemployment. {country} ranks {'#1' if rank==1 else f'#{rank}'} in the world{yr_label}.\n{why}",
        ],
        "current_account_gdp_pct": [
            f"{country} runs a {val_str} current account {'surplus' if val > 0 else 'deficit'} — {'the largest' if rank==1 else f'#{rank}'} globally{yr_label}.\n{runner_line.strip()}\n{why}",
            f"{val_str} current account balance. {country} is {'#1' if rank==1 else f'#{rank}'} globally{yr_label}.\n{why}",
            (f"{'Largest current account surplus globally' if val > 0 and rank == 1 else f'#{rank} current account balance'}: {country} at {val_str} of GDP{yr_label}.\n"
             f"This number is the single best indicator of whether a country lives within its means."),
        ],
        "gdp_per_capita_usd": [
            f"{country}: {val_str}/person in GDP per capita — {'highest' if rank==1 else f'#{rank}'} globally{yr_label}.\n{runner_line.strip()}\n{why}",
            f"{val_str} GDP per capita. {country} is {'the richest major economy by this metric' if rank==1 else f'#{rank} globally'}{yr_label}.\n{why}",
        ],
    }

    HOOK_VARIANTS_LI = {
        "gdp_usd": [
            f"{country} GDP: {val_str} — {'the largest economy globally' if rank==1 else f'#{rank} globally'}{yr_label}. At this scale, fiscal policy decisions in {country} have direct implications for trade flows, currency dynamics, and the revenue exposure of multinational companies. ({source})",
            f"Economic size data: {country} at {val_str} GDP{yr_label}. {why} The full indicator series for 200+ countries is tracked at metricshour.com.",
        ],
        "gdp_growth_pct": [
            f"{country} GDP {'growth' if order=='DESC' else 'contraction'}: {val_str}{yr_label} — {'#1 globally' if rank==1 else f'#{rank} globally'}. {why} This trajectory has direct read-through to domestic consumer spending and the revenue outlook for companies with significant {country} exposure. ({source})",
        ],
        "exports_usd": [
            f"{country} exports: {val_str}/year — {'largest exporter globally' if rank==1 else f'#{rank} globally'}{yr_label}. {why} The geographic revenue concentration from this export base is quantifiable at the stock level on metricshour.com.",
        ],
        "government_debt_gdp_pct": [
            f"{country} debt-to-GDP: {val_str} — {'highest globally' if rank==1 else f'#{rank} globally'}{yr_label}. {why} This level of fiscal constraint is a material variable for bond markets and any equity exposure to {country}'s domestic economy. ({source})",
        ],
        "gini_coefficient": [
            f"{country} Gini coefficient: {val_str} — {'highest globally' if rank==1 else f'#{rank}'}{yr_label}. {why} Inequality at this level introduces structural risk to consumer-facing businesses operating in the market. ({source})",
        ],
        "inflation_cpi_pct": [
            f"{country} CPI: {val_str} — {'the highest globally' if rank==1 else f'#{rank}'}{yr_label}. {why} At this inflation level, central bank policy divergence becomes a significant FX risk factor for any portfolio with {country} exposure. ({source})",
        ],
        "unemployment_rate_pct": [
            f"{country} unemployment: {val_str} — {'highest globally' if rank==1 else f'#{rank}'}{yr_label}. {why} Sustained unemployment at this level suppresses domestic consumption and increases political risk for any long-term equity exposure. ({source})",
        ],
        "current_account_gdp_pct": [
            f"{country} current account: {val_str} of GDP — {'largest globally' if rank==1 else f'#{rank}'}{yr_label}. {why} A current account at this scale is a leading indicator of currency strength and sovereign credit quality. ({source})",
        ],
        "gdp_per_capita_usd": [
            f"{country} GDP per capita: {val_str} — {'highest globally' if rank==1 else f'#{rank}'}{yr_label}. {why} Per capita income tracks closely with domestic consumer spending and consumer-sector revenue. ({source})",
        ],
    }

    def_ig_variants = [f"{country} leads in {label} at {val_str}{yr_label}.\n{runner_line.strip()}\n{why}"]
    def_li = f"{country} ranks #{rank} globally in {label} at {val_str}{yr_label}. {why} Full data at metricshour.com."

    ig_vars = HOOK_VARIANTS_IG.get(ind_key, def_ig_variants)
    li_vars = HOOK_VARIANTS_LI.get(ind_key, [def_li])
    ig_core = ig_vars[day_idx % len(ig_vars)]
    li_core = li_vars[day_idx % len(li_vars)]

    ig_text = (
        f"{ig_core}\n\n"
        f"Full indicator data for 200+ countries at metricshour.com"
    )
    x_text_raw = (
        f"{country} #{rank} globally in {label}: {val_str}{yr_label}. "
        f"{f'Runner-up: {runner} at {runner_val_str}. ' if runner else ''}"
        f"Source: {source}. → metricshour.com"
    )
    li_text = f"{li_core}\n\nFull indicator data for 200+ countries → metricshour.com"
    fb_text = (
        f"{country} ranks #{rank} globally in {label} at {val_str}{yr_label}."
        f"{runner_line}\n\n{why}\n\nFull data for 200+ countries at metricshour.com."
    )

    tags_ig = _hashtag_block(
        ["MacroEconomics", "Economics", "EconomicData", "GlobalFinance", "DataViz"],
        countries=[country], indicator=ind_key, limit=12,
    )
    tags_x  = _hashtag_block(["Economics", "MacroData"], countries=[country], indicator=ind_key, limit=3, add_brand=False)
    tags_li = _hashtag_block(["Economics", "MacroEconomics"], countries=[country], indicator=ind_key, limit=5, add_brand=False)

    x_full = f"{x_text_raw} {tags_x}"
    if len(x_full) > 280:
        x_full = x_full[:276] + "..."

    return (
        f"━━ CARD 4 — MACRO FACT ━━\n\n"
        f"📸 <b>INSTAGRAM</b>\n{ig_text}\n\n{tags_ig}\n\n"
        f"🐦 <b>X / TWITTER</b>\n{x_full}\n\n"
        f"👔 <b>LINKEDIN</b>\n{li_text}\n\n{tags_li}\n\n"
        f"📘 <b>FACEBOOK</b>\n{fb_text}"
    )


def _platform_copy_stock_angle(country_code: str, country_name: str, stocks: list[dict]) -> str:
    """
    Generate copy for the stock exposure angle.
    stocks = [{"symbol": "NVDA", "name": "NVIDIA", "revenue_pct": 17.0}, ...]
    """
    if not stocks:
        return ""
    day_idx = datetime.now(timezone.utc).timetuple().tm_yday

    lines = "\n".join(
        f"{i+1}. {s['symbol']} ({s['name']}) — {s['revenue_pct']:.0f}% of revenue from {country_name}"
        for i, s in enumerate(stocks)
    )
    top = stocks[0]
    url = f"https://www.metricshour.com/countries/{country_code.lower()}"

    ig_variants = [
        (f"If {country_name}'s economy moves, these are the US stocks that feel it first.\n\n"
         f"{lines}\n\n"
         f"Geographic revenue concentration is not shown in standard screeners.\n"
         f"Full data → metricshour.com"),
        (f"Stocks with the most {country_name} revenue exposure:\n\n"
         f"{lines}\n\n"
         f"{top['symbol']} is #1 at {top['revenue_pct']:.0f}%. "
         f"That's not a macro trade — it's sitting in your portfolio right now.\n"
         f"Full data → metricshour.com"),
        (f"Stocks with the most {country_name} revenue exposure — data from SEC EDGAR:\n\n"
         f"{lines}\n\n"
         f"Full breakdown at metricshour.com"),
    ]
    x_list = "  ".join(f"{s['symbol']} {s['revenue_pct']:.0f}%" for s in stocks[:4])
    x_variants = [
        f"US stocks most exposed to {country_name} revenue: {x_list}. Full data → metricshour.com",
        f"{country_name} revenue leaders: {x_list}. Source: SEC EDGAR annual filings.",
        f"Check your {country_name} exposure: {x_list}. All data at metricshour.com",
    ]
    li_variants = [
        (f"Geographic revenue concentration from {country_name} — ranked:\n\n"
         f"{lines}\n\n"
         f"{top['symbol']} carries the highest disclosed {country_name} revenue dependency at {top['revenue_pct']:.0f}%. "
         f"Full company-level data at metricshour.com."),
        (f"For investors assessing {country_name} risk in their portfolios: here is the revenue exposure data ranked by disclosed percentage.\n\n"
         f"{lines}\n\n"
         f"MetricsHour tracks geographic revenue at the stock level for 90+ companies. {url}"),
    ]
    fb_variants = [
        (f"If you hold US stocks and you're watching {country_name}, these are the names with the most direct revenue exposure:\n\n"
         f"{lines}\n\n"
         f"{top['symbol']} leads at {top['revenue_pct']:.0f}%. Revenue from a single country at that scale "
         f"is geographic revenue concentration — data from SEC EDGAR.\n\n"
         f"Full data at metricshour.com/countries/{country_code.lower()}"),
    ]

    ig_hook = ig_variants[day_idx % len(ig_variants)]
    x_hook  = x_variants[day_idx % len(x_variants)]
    li_hook = li_variants[day_idx % len(li_variants)]
    fb_hook = fb_variants[day_idx % len(fb_variants)]

    tags_ig = _hashtag_block(
        ["StockMarket", "Investing", "PortfolioRisk", "GeographicRevenue",
         "StockAnalysis", "EarningsRisk", "GlobalStocks"],
        countries=[country_name], limit=12,
    )
    tags_x  = _hashtag_block(["Stocks", "Investing"], countries=[country_name], limit=3, add_brand=False)
    tags_li = _hashtag_block(["Investing", "StockMarket", "PortfolioManagement"], limit=5, add_brand=False)

    x_text = f"{x_hook} {tags_x}"
    if len(x_text) > 280:
        x_text = x_text[:276] + "..."

    return (
        f"━━ CARD 5 — STOCK EXPOSURE ANGLE ━━\n\n"
        f"📸 <b>INSTAGRAM</b>\n{ig_hook}\n\n{tags_ig}\n\n"
        f"🐦 <b>X / TWITTER</b>\n{x_text}\n\n"
        f"👔 <b>LINKEDIN</b>\n{li_hook}\n\n{tags_li}\n\n"
        f"📘 <b>FACEBOOK</b>\n{fb_hook}"
    )


# ─── data queries ─────────────────────────────────────────────────────────────

def _find_stock_angle(country_code: str) -> list[dict]:
    """Find top stocks by revenue exposure to a given country code."""
    rows = _ssh(f"""
        SELECT a.symbol, a.name, scr.revenue_pct
        FROM stock_country_revenues scr
        JOIN assets a ON a.id = scr.asset_id
        JOIN countries c ON c.id = scr.country_id
        WHERE c.code = '{country_code.upper()}'
          AND scr.revenue_pct >= 5
        ORDER BY scr.revenue_pct DESC
        LIMIT 5
    """)
    stocks = []
    for r in rows:
        try:
            stocks.append({"symbol": r[0], "name": r[1], "revenue_pct": float(r[2])})
        except (ValueError, IndexError):
            pass
    return stocks


def _find_top_corridor(recent_corridors: list | None = None) -> dict | None:
    data_year = _DATA_CURRENCY.get("trade_year", 2023)
    recent = set((recent_corridors or [])[-14:])

    # Fetch top 80 corridors — pick first not recently shown
    rows = _ssh(f"""
        SELECT c1.name, c1.code, c2.name, c2.code, tp.trade_value_usd
        FROM trade_pairs tp
        JOIN countries c1 ON c1.id = tp.exporter_id
        JOIN countries c2 ON c2.id = tp.importer_id
        WHERE tp.year = {data_year}
          AND c1.code NOT IN ('HK') AND c2.code NOT IN ('HK')
        ORDER BY tp.trade_value_usd DESC
        LIMIT 80
    """)
    if not rows:
        return None

    chosen = None
    for row in rows:
        if len(row) < 5:
            continue
        key = f"{row[1]}_{row[3]}"
        if key not in recent:
            chosen = row
            break
    if chosen is None:
        chosen = rows[0]  # all recently shown — cycle back to top

    try:
        now_val = float(chosen[4])
        exp_code, imp_code = chosen[1], chosen[3]
        corridor_key = f"{exp_code}_{imp_code}"

        # Fetch historical data — no fallback; hooks handle missing hist gracefully
        hist = _ssh(f"""
            SELECT tp.year, tp.trade_value_usd
            FROM trade_pairs tp
            JOIN countries c1 ON c1.id = tp.exporter_id
            JOIN countries c2 ON c2.id = tp.importer_id
            WHERE c1.code = '{exp_code}' AND c2.code = '{imp_code}'
              AND tp.year < {data_year}
            ORDER BY tp.year ASC LIMIT 1
        """)
        then_year = int(hist[0][0]) if hist and len(hist[0]) >= 2 else None
        then_val  = float(hist[0][1]) if hist and len(hist[0]) >= 2 else None

        return {
            "exporter": chosen[0], "exp_code": exp_code,
            "importer": chosen[2], "imp_code": imp_code,
            "now_val": now_val, "year_now": data_year,
            "then_val": then_val, "year_then": then_year,
            "_corridor_key": corridor_key,
        }
    except (ValueError, IndexError):
        return None


def _get_trend(exp_code: str, imp_code: str) -> list[float]:
    rows = _ssh(f"""
        SELECT tp.year, tp.trade_value_usd
        FROM trade_pairs tp
        JOIN countries c1 ON c1.id = tp.exporter_id
        JOIN countries c2 ON c2.id = tp.importer_id
        WHERE c1.code = '{exp_code}' AND c2.code = '{imp_code}'
        ORDER BY tp.year
    """)
    vals = []
    for r in rows:
        try: vals.append(float(r[1]) / 1e9)
        except (ValueError, IndexError): pass
    return vals if vals else [0.0]


def _find_top_exporters(limit: int = 10, recent_types: list | None = None) -> list[dict]:
    data_year = _DATA_CURRENCY.get("trade_year", 2023)
    day = datetime.now(timezone.utc).timetuple().tm_yday
    recent_t = set(str(x) for x in (recent_types or [])[-6:])
    rank_type = next((((day + i) % 8) for i in range(8) if str((day + i) % 8) not in recent_t), day % 8)

    if rank_type == 0:
        title = "World's Top Exporters"; subtitle = f"by total export volume · {data_year}"
        sql = f"""
            SELECT c.name, c.code, SUM(tp.trade_value_usd) AS total
            FROM trade_pairs tp JOIN countries c ON c.id = tp.exporter_id
            WHERE tp.year = (SELECT MAX(year) FROM trade_pairs)
            GROUP BY c.name, c.code ORDER BY total DESC LIMIT {limit}
        """
        metric = "Export volume"
    elif rank_type == 1:
        title = "World's Top Importers"; subtitle = f"by total import volume · {data_year}"
        sql = f"""
            SELECT c.name, c.code, SUM(tp.trade_value_usd) AS total
            FROM trade_pairs tp JOIN countries c ON c.id = tp.importer_id
            WHERE tp.year = (SELECT MAX(year) FROM trade_pairs)
            GROUP BY c.name, c.code ORDER BY total DESC LIMIT {limit}
        """
        metric = "Import volume"
    elif rank_type == 2:
        title = "Largest G20 Economies"; subtitle = "by GDP · World Bank"
        sql = f"""
            SELECT c.name, c.code, ci.value AS total
            FROM country_indicators ci JOIN countries c ON c.id = ci.country_id
            WHERE ci.indicator = 'gdp_usd' AND c.is_g20 = TRUE
              AND ci.period_date <= CURRENT_DATE
            ORDER BY ci.period_date DESC, ci.value DESC LIMIT {limit}
        """
        metric = "GDP"
    elif rank_type == 3:
        title = "Fastest Growing Economies"; subtitle = "GDP growth rate · World Bank"
        sql = f"""
            SELECT c.name, c.code, ci.value AS total
            FROM country_indicators ci JOIN countries c ON c.id = ci.country_id
            WHERE ci.indicator = 'gdp_growth_pct' AND ci.period_date <= CURRENT_DATE
            ORDER BY ci.period_date DESC, ci.value DESC LIMIT {limit}
        """
        metric = "GDP growth %"
    elif rank_type == 4:
        title = "Highest Government Debt"; subtitle = "debt as % of GDP · IMF"
        sql = f"""
            SELECT c.name, c.code, ci.value AS total
            FROM country_indicators ci JOIN countries c ON c.id = ci.country_id
            WHERE ci.indicator = 'government_debt_gdp_pct' AND ci.period_date <= CURRENT_DATE
            ORDER BY ci.period_date DESC, ci.value DESC LIMIT {limit}
        """
        metric = "Debt/GDP %"
    elif rank_type == 5:
        title = "Highest Inflation Rates"; subtitle = "CPI inflation · World Bank"
        sql = f"""
            SELECT c.name, c.code, ci.value AS total
            FROM country_indicators ci JOIN countries c ON c.id = ci.country_id
            WHERE ci.indicator = 'inflation_cpi_pct' AND ci.value > 0
              AND ci.period_date <= CURRENT_DATE
            ORDER BY ci.period_date DESC, ci.value DESC LIMIT {limit}
        """
        metric = "Inflation %"
    elif rank_type == 6:
        title = "Highest Unemployment"; subtitle = "unemployment rate · World Bank"
        sql = f"""
            SELECT c.name, c.code, ci.value AS total
            FROM country_indicators ci JOIN countries c ON c.id = ci.country_id
            WHERE ci.indicator = 'unemployment_rate_pct' AND ci.period_date <= CURRENT_DATE
            ORDER BY ci.period_date DESC, ci.value DESC LIMIT {limit}
        """
        metric = "Unemployment %"
    else:
        title = "Highest GDP Per Capita"; subtitle = "GDP per person · World Bank"
        sql = f"""
            SELECT c.name, c.code, ci.value AS total
            FROM country_indicators ci JOIN countries c ON c.id = ci.country_id
            WHERE ci.indicator = 'gdp_per_capita_usd' AND ci.period_date <= CURRENT_DATE
            ORDER BY ci.period_date DESC, ci.value DESC LIMIT {limit}
        """
        metric = "GDP per capita"

    src_map = {0: "UN Comtrade", 1: "UN Comtrade", 2: "World Bank", 3: "World Bank",
               4: "IMF", 5: "World Bank", 6: "World Bank", 7: "World Bank"}
    item_source = src_map.get(rank_type, "World Bank")

    rows = _ssh(sql)
    items = []
    for i, row in enumerate(rows, 1):
        try:
            total = float(row[2])
            dollar_types = (0, 1, 2, 7)
            val_str = _fmt(total) if rank_type in dollar_types else f"{total:.1f}%"
            items.append({"rank": i, "label": row[0], "iso": row[1],
                          "value": val_str, "raw": total / (1e9 if rank_type in dollar_types else 1),
                          "_title": title, "_subtitle": subtitle, "_metric": metric,
                          "_source": item_source, "_rank_type": rank_type})
        except (ValueError, IndexError):
            pass
    return items


def _find_macro_fact(recent_indicators: list | None = None) -> dict | None:
    ind_year = _DATA_CURRENCY.get("ind_year", 2024)
    indicators = [
        ("gdp_usd",                  "GDP",           "World Bank", "DESC"),
        ("gdp_growth_pct",           "GDP Growth",    "World Bank", "DESC"),
        ("exports_usd",              "Exports",       "World Bank", "DESC"),
        ("government_debt_gdp_pct",  "Debt/GDP",      "IMF",        "DESC"),
        ("gini_coefficient",         "Inequality",    "World Bank", "DESC"),
        ("inflation_cpi_pct",        "Inflation",     "World Bank", "DESC"),
        ("unemployment_rate_pct",    "Unemployment",  "World Bank", "DESC"),
        ("current_account_gdp_pct",  "Current Acct",  "World Bank", "DESC"),
        ("gdp_per_capita_usd",       "GDP per Capita","World Bank", "DESC"),
        ("gdp_growth_pct",           "GDP Contraction","World Bank","ASC"),
    ]
    day = datetime.now(timezone.utc).timetuple().tm_yday
    recent_ind = set((recent_indicators or [])[-12:])
    # Find first indicator+rank combo not recently shown
    chosen_idx = 0; chosen_rank = 0
    for i in range(len(indicators) * 3):
        idx = (day + i) % len(indicators)
        rank = (day // len(indicators) + i // len(indicators)) % 3
        if f"{indicators[idx][0]}_{rank}" not in recent_ind:
            chosen_idx = idx; chosen_rank = rank; break
    ind_key, ind_label, source, order = indicators[chosen_idx]
    rank_offset = chosen_rank
    rows = _ssh(f"""
        SELECT c.name, c.code, ci.value
        FROM country_indicators ci JOIN countries c ON c.id = ci.country_id
        WHERE ci.indicator = '{ind_key}' AND ci.period_date <= CURRENT_DATE
        ORDER BY ci.period_date DESC, ci.value {order}
        LIMIT 5
    """)
    if not rows or len(rows) <= rank_offset:
        return None
    try:
        top = rows[rank_offset]
        next_row = rows[rank_offset + 1] if len(rows) > rank_offset + 1 else None
        return {"country": top[0], "iso": top[1], "value": float(top[2]),
                "indicator": ind_key, "label": ind_label, "source": source,
                "order": order, "rank": rank_offset + 1,
                "runner_up": next_row[0] if next_row else None,
                "runner_up_val": float(next_row[2]) if next_row else None,
                "data_year": ind_year,
                "_indicator_key": f"{ind_key}_{rank_offset}"}
    except (ValueError, IndexError):
        return None


# ─── card generators ──────────────────────────────────────────────────────────

async def _card1_stat_spotlight(c: dict) -> str | None:
    if not c: return None
    exp, imp = c["exporter"], c["importer"]
    day_idx = datetime.now(timezone.utc).timetuple().tm_yday

    if c.get("then_val") and c.get("year_then"):
        pct = ((c["now_val"] / c["then_val"]) - 1) * 100
        years = c["year_now"] - c["year_then"]
        dir_word = "grew" if pct >= 0 else "fell"
        hooks = [
            f"{exp}–{imp} trade {dir_word} {abs(pct):.0f}% in {years} years.",
            f"{_fmt(c['then_val'])} in {c['year_then']}. {_fmt(c['now_val'])} today.",
            f"In {years} years, this corridor {dir_word} from {_fmt(c['then_val'])} to {_fmt(c['now_val'])}.",
        ]
        comparisons = [
            f"From {_fmt(c['then_val'])} ({c['year_then']}) to {_fmt(c['now_val'])} ({c['year_now']}) — {abs(pct):.0f}% {'growth' if pct >= 0 else 'decline'}.",
            f"{abs(pct):.0f}% {'expansion' if pct >= 0 else 'contraction'} in {years} years. The stocks exposed to both markets feel every move.",
            f"That's {abs(pct):.0f}% in {years} years — and the dependency is deeper than the headlines show.",
        ]
        hook = hooks[day_idx % len(hooks)]
        comparison = comparisons[day_idx % len(comparisons)]
    else:
        hooks = [
            f"{exp} and {imp} move {_fmt(c['now_val'])} in goods every year.",
            f"The {exp}–{imp} corridor: {_fmt(c['now_val'])} in annual trade ({c['year_now']}).",
            f"Annual trade: {exp}–{imp} = {_fmt(c['now_val'])} ({c['year_now']}).",
        ]
        comparisons = [
            f"One of the largest bilateral trade corridors on earth — every tariff announcement touches this number.",
            f"The companies exposed to both markets carry correlated revenue risk.",
            f"At {_fmt(c['now_val'])}/year, this corridor shapes supply chains across dozens of sectors.",
        ]
        hook = hooks[day_idx % len(hooks)]
        comparison = comparisons[day_idx % len(comparisons)]

    return await generate_stat_spotlight(
        category="TRADE FACT",
        hook=hook,
        number=_fmt(c["now_val"]),
        number_label=f"Annual trade: {exp} ↔ {imp} ({c['year_now']})",
        comparison=comparison,
        country=exp, iso=_iso(exp),
        source="UN Comtrade", filename="social_stat_spotlight.png",
    )

async def _card2_trade_shift(c: dict, trend: list[float]) -> str | None:
    if not c: return None
    exp, imp = c["exporter"], c["importer"]
    exp_code = c["exp_code"]
    data_year = c["year_now"]

    # If historical comparison data exists, render trade-shift card
    if c.get("then_val"):
        now_val = c["now_val"]; then_val = c["then_val"]
        y_then = c["year_then"]; y_now = data_year
        pct = ((now_val / then_val) - 1) * 100
        if abs(pct) >= 0.5:
            context = [
                f"From {_fmt(then_val)} ({y_then}) to {_fmt(now_val)} ({y_now})",
                f"{'+' if pct >= 0 else ''}{pct:.0f}% in {y_now - y_then} years",
                "Track every corridor → metricshour.com",
            ]
            return await generate_trade_shift(
                country_a=exp, iso_a=_iso(exp), country_b=imp, iso_b=_iso(imp),
                year_then=y_then, value_then=then_val, year_now=y_now, value_now=now_val,
                change_pct=pct, trend_values=trend if trend else [then_val/1e9, now_val/1e9],
                context_lines=context, source="UN Comtrade", filename="social_trade_shift.png",
            )

    # Fallback: top export destinations of the exporter country
    rows = _ssh(f"""
        SELECT c2.name, c2.code, tp.trade_value_usd
        FROM trade_pairs tp
        JOIN countries c1 ON c1.id = tp.exporter_id
        JOIN countries c2 ON c2.id = tp.importer_id
        WHERE c1.code = '{exp_code}' AND tp.year = {data_year}
        ORDER BY tp.trade_value_usd DESC LIMIT 8
    """)
    if not rows or len(rows) < 2:
        return None
    total = sum(float(r[2]) for r in rows if r[2])
    items = []
    for idx, r in enumerate(rows, 1):
        val = float(r[2])
        items.append({
            "rank": idx,
            "label": r[0], "iso": r[1].upper() if r[1] else "",
            "value": _fmt(val),
            "raw": val / 1e9,
            "change": round(val / total * 100, 1) if total else 0,
            "context": f"{val/total*100:.0f}% of {exp} exports" if total else "",
            "_title": f"{exp}: Top Export Destinations",
            "_subtitle": f"by trade volume ({data_year})",
            "_metric": "Trade volume",
            "_source": "UN Comtrade",
        })
    return await generate_ranking_visual(
        title=f"{exp}: Top Export Destinations",
        subtitle=f"by trade volume ({data_year})",
        items=items,
        metric_label="Trade volume",
        highlight_rank=1,
        source="UN Comtrade",
        filename="social_trade_shift.png",
    )

async def _card3_ranking(items: list) -> str | None:
    if not items: return None
    return await generate_ranking_visual(
        title=items[0].get("_title", "World's Top Exporters"),
        subtitle=items[0].get("_subtitle", "by total trade volume"),
        items=items,
        metric_label=items[0].get("_metric", "Trade volume"),
        highlight_rank=1,
        source=items[0].get("_source", "UN Comtrade"),
        filename="social_ranking.png",
    )

async def _card4_did_you_know(fact: dict) -> str | None:
    if not fact: return None
    country, iso = fact["country"], fact["iso"]
    ind_key, label, source = fact["indicator"], fact["label"], fact["source"]
    val = fact["value"]; runner = fact.get("runner_up"); runner_v = fact.get("runner_up_val")
    data_year = fact.get("data_year", "")
    val_str = _fmt(val) if ind_key in ("gdp_usd","exports_usd") else f"{val:.1f}%"
    runner_str = ""
    if runner and runner_v:
        rv_str = _fmt(runner_v) if ind_key in ("gdp_usd","exports_usd") else f"{runner_v:.1f}%"
        runner_str = f"Runner up: {runner} at {rv_str}"
    rank = fact.get("rank", 1); order = fact.get("order", "DESC")
    rank_label = {1:"#1",2:"#2",3:"#3"}.get(rank, f"#{rank}")
    worst_best = "lowest" if order == "ASC" else "highest"
    q_map = {
        "gdp_usd":                 f"Which country has the {worst_best} GDP?",
        "gdp_growth_pct":          f"Which economy {'contracted' if order=='ASC' else 'grew'} the {'least' if order=='ASC' else 'most'} recently?",
        "exports_usd":             f"Which country exports the {worst_best} amount?",
        "government_debt_gdp_pct": f"Which country has the {worst_best} debt-to-GDP ratio?",
        "gini_coefficient":        f"Which country has the {worst_best} income inequality?",
        "inflation_cpi_pct":       f"Which country has the {worst_best} inflation rate?",
        "unemployment_rate_pct":   f"Which country has the {worst_best} unemployment rate?",
        "current_account_gdp_pct": f"Which country has the {worst_best} current account balance?",
        "gdp_per_capita_usd":      f"Which country has the {worst_best} GDP per capita?",
    }
    a_map = {
        "gdp_usd":                 f"{rank_label}: {country} — {val_str} total GDP",
        "gdp_growth_pct":          f"{rank_label}: {country} — {val_str}/year",
        "exports_usd":             f"{rank_label}: {country} — {val_str} annual exports",
        "government_debt_gdp_pct": f"{rank_label}: {country} — {val_str} of GDP in debt",
        "gini_coefficient":        f"{rank_label}: {country} — Gini index {val_str}",
        "inflation_cpi_pct":       f"{rank_label}: {country} — {val_str} inflation",
        "unemployment_rate_pct":   f"{rank_label}: {country} — {val_str} unemployment",
        "current_account_gdp_pct": f"{rank_label}: {country} — {val_str} of GDP",
        "gdp_per_capita_usd":      f"{rank_label}: {country} — {val_str} per person",
    }
    year_label = f" · {data_year}" if data_year else ""

    stat_context_map = {
        "gdp_usd":                 f"{'world\'s largest economy' if rank==1 else f'#{rank} largest economy'} by GDP{year_label}",
        "gdp_growth_pct":          f"{'fastest' if order=='DESC' else 'slowest'} growing major economy{year_label}",
        "exports_usd":             f"{'world\'s top exporter' if rank==1 else f'#{rank} largest exporter'} by volume{year_label}",
        "government_debt_gdp_pct": f"{'highest' if rank==1 else f'#{rank} highest'} debt-to-GDP globally{year_label}",
        "gini_coefficient":        f"{'most unequal' if rank==1 else f'#{rank} most unequal'} by Gini index{year_label}",
        "inflation_cpi_pct":       f"{'highest' if rank==1 else f'#{rank} highest'} CPI inflation globally{year_label}",
        "unemployment_rate_pct":   f"{'highest' if rank==1 else f'#{rank} highest'} unemployment globally{year_label}",
        "current_account_gdp_pct": f"current account {'surplus' if val > 0 else 'deficit'} as % of GDP{year_label}",
        "gdp_per_capita_usd":      f"{'highest' if rank==1 else f'#{rank} highest'} GDP per capita{year_label}",
    }
    stat_context = stat_context_map.get(ind_key, f"#{rank} globally{year_label}")

    why_map = {
        "gdp_usd":                 "GDP size sets a country's weight in global rate decisions and FX markets.",
        "gdp_growth_pct":          "Growth rate signals where capital allocators look next.",
        "exports_usd":             "Export volume reflects industrial capacity and global trade leverage.",
        "government_debt_gdp_pct": "High debt-to-GDP constrains fiscal policy and pressures the currency.",
        "gini_coefficient":        "Inequality shapes political risk, consumer spending, and investment climate.",
        "inflation_cpi_pct":       "CPI drives central bank decisions that move rates, bonds, and equities.",
        "unemployment_rate_pct":   "Unemployment shapes consumer demand and monetary policy direction.",
        "current_account_gdp_pct": "Current account reveals whether a country lives within its means.",
        "gdp_per_capita_usd":      "GDP per capita is the most direct measure of average living standards.",
    }
    why_line = why_map.get(ind_key, f"Macro data drives policy — and policy moves markets.")
    facts = [
        f"{label}: {val_str}",
        runner_str or f"Data source: {source}",
        why_line,
        "Track 80+ macro indicators → metricshour.com",
    ]
    return await generate_did_you_know(
        question=q_map.get(ind_key, f"Which country leads in {label}?"),
        answer=a_map.get(ind_key, f"{country} — {val_str}"),
        answer_sub=f"{source} data{year_label}",
        big_stat=val_str,
        stat_context=stat_context,
        facts=[f for f in facts if f],
        iso=iso, category=label.upper(), source=source,
        filename="social_did_you_know.png",
    )


# ─── main ─────────────────────────────────────────────────────────────────────

async def main():
    import os as _os
    parser = argparse.ArgumentParser()
    parser.add_argument('--card', default='all',
        choices=['1','2','3','4','stock','all'],
        help='Which card to send (default: all)')
    args = parser.parse_args()
    card = args.card

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # State file guard only for full run (not individual cards)
    if card == 'all':
        state_file = "/tmp/morning_social_last_run.txt"
        try:
            if _os.path.exists(state_file):
                with open(state_file) as _f:
                    if _f.read().strip() == today:
                        print(f"[{today}] Already ran today — skipping")
                        return
            with open(state_file, "w") as _f:
                _f.write(today)
        except Exception:
            pass

    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] Starting social content run...")
    sent, errors = 0, []

    data = _check_data_currency()
    print(f"  Data currency: trade={data['trade_year']} | indicators={data['ind_year']} ({data['ind_date']})")
    if data["trade_stale"]:
        print(f"  WARNING: Trade data ({data['trade_year']}) >4y old — skipping trade cards")
    if data["ind_stale"]:
        print(f"  WARNING: Indicator data ({data['ind_year']}) >3y old — skipping macro cards")

    _state = _load_state()
    corridor      = _find_top_corridor(_state.get("corridors", []))      if not data["trade_stale"] else None
    trend         = _get_trend(corridor["exp_code"], corridor["imp_code"]) if corridor else []
    top_exporters = _find_top_exporters(10, _state.get("ranking_types", []))   if not data["trade_stale"] else []
    macro_fact    = _find_macro_fact(_state.get("indicators", []))         if not data["ind_stale"]   else None

    # Stock angle: use exporter from corridor if available, else fall back to macro country
    stock_country_code = corridor["exp_code"] if corridor else (macro_fact["iso"] if macro_fact else "CN")
    stock_country_name = corridor["exporter"] if corridor else (macro_fact["country"] if macro_fact else "China")
    stock_angle = _find_stock_angle(stock_country_code)

    if corridor:
        print(f"  Corridor: {corridor['exporter']} ↔ {corridor['importer']} = {_fmt(corridor['now_val'])} ({corridor['year_now']})")
    print(f"  Exporters: {len(top_exporters)}")
    if macro_fact:
        print(f"  Macro: {macro_fact['country']} — {macro_fact['label']} ({macro_fact.get('data_year','')})")
    print(f"  Stock angle: {stock_country_name} — {len(stock_angle)} stocks")

    rank_title = top_exporters[0].get("_title","World's Top Exporters") if top_exporters else "World's Top Exporters"

    # Track which card groups sent for platform copy
    trade_cards_sent = False
    ranking_sent     = False
    macro_sent       = False

    all_cards = [
        (1, lambda: _card1_stat_spotlight(corridor),
            lambda: (f"📊 <b>{corridor['exporter']} ↔ {corridor['importer']}: {_fmt(corridor['now_val'])} in annual trade ({corridor['year_now']})</b>") if corridor else None),
        (2, lambda: _card2_trade_shift(corridor, trend),
            lambda: (
                f"📈 <b>{corridor['exporter']} ↔ {corridor['importer']}: Trade evolution {corridor.get('year_then','?')}→{corridor['year_now']}</b>"
                if corridor and corridor.get('then_val')
                else f"🌐 <b>{corridor['exporter']}: Top Export Destinations ({corridor['year_now']})</b>"
            ) if corridor else None),
        (3, lambda: _card3_ranking(top_exporters),
            lambda: (f"🌍 <b>{rank_title}</b> — #1: {top_exporters[0]['label']} at {top_exporters[0]['value']}") if top_exporters else None),
        (4, lambda: _card4_did_you_know(macro_fact),
            lambda: (f"💡 <b>{macro_fact['country']}: {macro_fact['label']}</b>") if macro_fact else None),
    ]

    # Filter to requested card
    cards_to_run = all_cards if card == 'all' else [c for c in all_cards if str(c[0]) == card]

    for card_num, coro, tg_caption_fn in cards_to_run:
        try:
            path = await coro()
            if path:
                caption = tg_caption_fn()
                if caption:
                    result = send_telegram(path, caption, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
                    print(f"  Card {card_num}: {result}")
                    if result.startswith("Sent:"):
                        sent += 1
                    else:
                        errors.append(f"Card{card_num}:TG:{result[:80]}")
                    if card_num in (1, 2):
                        trade_cards_sent = True
                    elif card_num == 3:
                        ranking_sent = True
                    elif card_num == 4:
                        macro_sent = True
        except Exception as e:
            errors.append(f"Card{card_num}:{e}")
            print(f"  Card {card_num} ERROR: {e}")

    # Platform copy — send for each card run, or stock-angle
    if card in ('1', '2', 'all') and trade_cards_sent and corridor:
        _send_text(_platform_copy_trade(corridor))
    if card in ('3', 'all') and ranking_sent and top_exporters:
        _send_text(_platform_copy_ranking(top_exporters))
    if card in ('4', 'all') and macro_sent and macro_fact:
        _send_text(_platform_copy_macro(macro_fact))
    if card in ('stock', 'all') and stock_angle:
        _send_text(_platform_copy_stock_angle(stock_country_code, stock_country_name, stock_angle))
        print(f"  Stock angle copy sent: {stock_country_name}")

    # Persist dedup state for next run
    if corridor and "_corridor_key" in corridor:
        _state["corridors"] = (_state.get("corridors", []) + [corridor["_corridor_key"]])[-20:]
    if macro_fact and "_indicator_key" in macro_fact:
        _state["indicators"] = (_state.get("indicators", []) + [macro_fact["_indicator_key"]])[-20:]
    if top_exporters and "_rank_type" in top_exporters[0]:
        _state["ranking_types"] = (_state.get("ranking_types", []) + [str(top_exporters[0]["_rank_type"])])[-20:]
    if corridor and corridor.get("exp_code"):
        _state["countries"] = (_state.get("countries", []) + [corridor["exp_code"]])[-20:]
    _save_state(_state)
    log_line = f"[{datetime.now(timezone.utc).strftime('%b %d %H:%M UTC')}] Social content: {sent}/4 cards sent"
    if errors:
        log_line += f" | ERRORS: {'; '.join(errors)}"
    print(log_line)


if __name__ == "__main__":
    asyncio.run(main())
