"""
Auto deep-link injector for blog post bodies.
Called during publish to ensure every post has internal links
to stock pages, country pages, and trade corridors.
Max 2 links per entity to avoid over-linking.
"""
import re

BASE = "https://www.metricshour.com"
MAX_PER_ENTITY = 999  # link every occurrence

STOCKS = {
    "AAPL":  ["Apple"],
    "ABBV":  ["AbbVie"],
    "ADBE":  ["Adobe"],
    "AMAT":  ["Applied Materials"],
    "AMD":   ["Advanced Micro Devices"],
    "AMGN":  ["Amgen"],
    "AMZN":  ["Amazon"],
    "ARM":   ["Arm Holdings"],
    "ASML":  ["ASML"],
    "AVGO":  ["Broadcom"],
    "AXP":   ["American Express"],
    "AZN":   ["AstraZeneca"],
    "BA":    ["Boeing"],
    "BABA":  ["Alibaba"],
    "BAC":   ["Bank of America"],
    "BHP":   ["BHP"],
    "BIDU":  ["Baidu"],
    "BLK":   ["BlackRock"],
    "BMY":   ["Bristol-Myers Squibb"],
    "CAT":   ["Caterpillar"],
    "CMCSA": ["Comcast"],
    "COP":   ["ConocoPhillips"],
    "COST":  ["Costco"],
    "CRM":   ["Salesforce"],
    "CSCO":  ["Cisco"],
    "CVX":   ["Chevron"],
    "DE":    ["John Deere"],
    "DIS":   ["Disney", "Walt Disney"],
    "DUK":   ["Duke Energy"],
    "GE":    ["GE Aerospace"],
    "GILD":  ["Gilead"],
    "GOOGL": ["Alphabet", "Google"],
    "GS":    ["Goldman Sachs"],
    "GSK":   ["GSK"],
    "HD":    ["Home Depot"],
    "HDB":   ["HDFC Bank"],
    "HON":   ["Honeywell"],
    "HSBC":  ["HSBC"],
    "IBM":   ["IBM"],
    "INFY":  ["Infosys"],
    "INTC":  ["Intel"],
    "JD":    ["JD.com"],
    "JNJ":   ["Johnson & Johnson"],
    "JPM":   ["JPMorgan", "JPMorgan Chase"],
    "KO":    ["Coca-Cola"],
    "KLAC":  ["KLA Corporation", "KLA"],
    "LRCX":  ["Lam Research"],
    "LLY":   ["Eli Lilly", "Lilly"],
    "LMT":   ["Lockheed Martin"],
    "LVS":   ["Las Vegas Sands"],
    "MA":    ["Mastercard"],
    "MCD":   ["McDonald's"],
    "META":  ["Meta", "Facebook"],
    "MGM":   ["MGM Resorts"],
    "MRK":   ["Merck"],
    "MSFT":  ["Microsoft"],
    "MU":    ["Micron"],
    "NFLX":  ["Netflix"],
    "NKE":   ["Nike"],
    "NOC":   ["Northrop Grumman"],
    "NVDA":  ["NVIDIA", "Nvidia"],
    "NVO":   ["Novo Nordisk"],
    "ORCL":  ["Oracle"],
    "PBR":   ["Petrobras"],
    "PDD":   ["PDD Holdings", "Pinduoduo"],
    "PEP":   ["PepsiCo", "Pepsi"],
    "PFE":   ["Pfizer"],
    "PG":    ["Procter & Gamble", "P&G"],
    "PLD":   ["Prologis"],
    "PM":    ["Philip Morris"],
    "QCOM":  ["Qualcomm"],
    "RIO":   ["Rio Tinto"],
    "RTX":   ["RTX", "Raytheon"],
    "SAP":   ["SAP"],
    "SBUX":  ["Starbucks"],
    "SHEL":  ["Shell"],
    "SLB":   ["Schlumberger"],
    "SONY":  ["Sony"],
    # "SSNLF": Samsung removed — OTC stock, no SEC EDGAR 10-K data, page shows no geo revenue
    "TM":    ["Toyota"],
    "TMO":   ["Thermo Fisher"],
    "TSLA":  ["Tesla"],
    "TSM":   ["TSMC", "Taiwan Semiconductor"],
    "TTE":   ["TotalEnergies"],
    "TXN":   ["Texas Instruments"],
    "UNH":   ["UnitedHealth"],
    "UPS":   ["UPS"],
    "VALE":  ["Vale"],
    "VZ":    ["Verizon"],
    "WFC":   ["Wells Fargo"],
    "WMT":   ["Walmart"],
    "WYNN":  ["Wynn Resorts", "Wynn"],
    "XOM":   ["ExxonMobil", "Exxon"],
    "QCOM":  ["Qualcomm"],
    "C":     [],  # skip — too ambiguous
    "V":     [],  # skip — too ambiguous
}

# Short tickers skip auto-match by ticker text
SKIP_TICKER_MATCH = {"C", "V", "T", "BA", "DE", "GE", "MS", "BP", "MA"}

COUNTRIES = {
    "China": "cn", "Germany": "de", "Japan": "jp", "India": "in",
    "United Kingdom": "gb", "UK": "gb", "France": "fr", "South Korea": "kr",
    "Italy": "it", "Canada": "ca", "Mexico": "mx", "Brazil": "br",
    "Australia": "au", "Netherlands": "nl", "Spain": "es", "Switzerland": "ch",
    "Taiwan": "tw", "Saudi Arabia": "sa", "Nigeria": "ng", "Vietnam": "vn",
    "Indonesia": "id", "Russia": "ru", "Turkey": "tr", "Poland": "pl",
    "Belgium": "be", "Sweden": "se", "Argentina": "ar", "South Africa": "za",
    "Thailand": "th", "Malaysia": "my", "Philippines": "ph", "Singapore": "sg",
    "Israel": "il", "UAE": "ae", "United Arab Emirates": "ae", "Egypt": "eg",
    "Guyana": "gy", "Colombia": "co", "Chile": "cl", "Peru": "pe",
    "Czech Republic": "cz", "Romania": "ro", "Hungary": "hu",
    "Denmark": "dk", "Finland": "fi", "Norway": "no", "Greece": "gr",
    "Portugal": "pt", "Ireland": "ie", "Austria": "at", "New Zealand": "nz",
    "Hong Kong": "hk", "Macau": "mo", "Morocco": "ma", "Kenya": "ke",
    "Ghana": "gh", "Greater China": "cn", "Pakistan": "pk",
}

BLOC_PHRASES: list[tuple[str, str]] = [
    ("European Union",            "eu"),
    ("the EU",                    "eu"),
    ("the Eurozone",              "eurozone"),
    ("euro area",                 "eurozone"),
    ("G7 countries",              "g7"),
    ("G7 nations",                "g7"),
    ("the G7",                    "g7"),
    ("G20 countries",             "g20"),
    ("G20 nations",               "g20"),
    ("the G20",                   "g20"),
    ("BRICS countries",           "brics"),
    ("BRICS nations",             "brics"),
    ("BRICS economies",           "brics"),
    ("NATO members",              "nato"),
    ("NATO countries",            "nato"),
    ("NATO allies",               "nato"),
    ("ASEAN countries",           "asean"),
    ("ASEAN nations",             "asean"),
    ("ASEAN economies",           "asean"),
    ("OPEC members",              "opec"),
    ("OPEC nations",              "opec"),
    ("OPEC countries",            "opec"),
    ("OECD countries",            "oecd"),
    ("OECD members",              "oecd"),
    ("Commonwealth nations",      "commonwealth"),
    ("Commonwealth countries",    "commonwealth"),
    ("African Union",             "africa"),
    ("AU member states",          "africa"),
    ("US-EU trade",               "eu"),
    ("US–EU trade",               "eu"),
    ("EU-US trade",               "eu"),
]

SECTOR_PHRASES: list[tuple[str, str]] = [
    ("Technology sector",             "technology"),
    ("tech sector",                   "technology"),
    ("semiconductor sector",          "technology"),
    ("Healthcare sector",             "healthcare"),
    ("pharma sector",                 "healthcare"),
    ("biotech sector",                "healthcare"),
    ("Financial sector",              "financials"),
    ("banking sector",                "financials"),
    ("Industrial sector",             "industrials"),
    ("Energy sector",                 "energy"),
    ("oil and gas sector",            "energy"),
    ("Consumer Discretionary sector", "consumer-discretionary"),
    ("Consumer Staples sector",       "consumer-staples"),
    ("Communication Services sector", "communication-services"),
    ("Materials sector",              "materials"),
    ("Real Estate sector",            "real-estate"),
    ("Utilities sector",              "utilities"),
]

CORRIDORS = [
    ("us", "cn", ["US-China trade", "US–China trade", "US and China trade", "China-US trade"]),
    ("us", "de", ["US-Germany trade", "US–Germany trade"]),
    ("us", "jp", ["US-Japan trade", "US–Japan trade"]),
    ("us", "gb", ["US-UK trade", "US–UK trade"]),
    ("us", "mx", ["US-Mexico trade", "US–Mexico trade"]),
    ("us", "in", ["US-India trade", "US–India trade"]),
    ("cn", "jp", ["China-Japan trade", "China–Japan trade"]),
    ("gb", "ng", ["UK-Nigeria trade", "UK–Nigeria trade"]),
]


def _is_html(body: str) -> bool:
    return bool(re.search(r'<(p|h[1-6]|ul|ol|table|div)\b', body[:500], re.IGNORECASE))


def _count_linked(body: str, text: str, html: bool) -> int:
    if html:
        return sum(1 for m in re.finditer(r'<a\b[^>]*>.*?</a>', body, re.DOTALL | re.IGNORECASE)
                   if re.search(re.escape(text), m.group(), re.IGNORECASE))
    return len(re.findall(r'\[' + re.escape(text) + r'\]', body))


def _replace_in_html_text(body: str, pattern: str, repl_fn, remaining: list) -> str:
    result = []
    pos = 0
    for m in re.finditer(r'(<a\b[^>]*>.*?</a>|<[^>]+>)', body, re.DOTALL | re.IGNORECASE):
        seg = body[pos:m.start()]
        if seg and remaining[0] > 0:
            def sub(mo, rem=remaining):
                if rem[0] <= 0:
                    return mo.group()
                rem[0] -= 1
                return repl_fn(mo.group())
            seg = re.sub(pattern, sub, seg)
        result.append(seg)
        result.append(m.group())
        pos = m.end()
    seg = body[pos:]
    if seg and remaining[0] > 0:
        def sub2(mo, rem=remaining):
            if rem[0] <= 0:
                return mo.group()
            rem[0] -= 1
            return repl_fn(mo.group())
        seg = re.sub(pattern, sub2, seg)
    result.append(seg)
    return "".join(result)


def _inject_stock(body: str, ticker: str, names: list, html: bool) -> str:
    url = f"{BASE}/stocks/{ticker}"

    def make_link_html(t): return f'<a href="{url}" class="link-stock">{t}</a>'
    def make_link_md(t): return f'[{t}]({url})'

    # Ticker match (skip ambiguous short tickers)
    if ticker not in SKIP_TICKER_MATCH:
        existing = _count_linked(body, ticker, html)
        rem = [max(0, MAX_PER_ENTITY - existing)]
        if rem[0] > 0:
            pat = r'\b' + re.escape(ticker) + r'\b(?!\s*[\"\)\(])'
            if html:
                body = _replace_in_html_text(body, pat, make_link_html, rem)
            else:
                def sub_md(mo, rem=rem):
                    if rem[0] <= 0: return mo.group()
                    start = mo.start()
                    before = body[:start]
                    # skip if inside existing link text [... or inside link URL ](url
                    if re.search(r'\[[^\]]*$', before) or re.search(r'\]\([^)]*$', before): return mo.group()
                    rem[0] -= 1
                    return make_link_md(mo.group())
                body = re.sub(pat, sub_md, body)

    # Name matches
    for name in names:
        if not name or len(name) < 4: continue
        existing = _count_linked(body, name, html)
        rem = [max(0, MAX_PER_ENTITY - existing)]
        if rem[0] <= 0: continue
        pat = r'\b' + re.escape(name) + r'\b'
        if html:
            body = _replace_in_html_text(body, pat, make_link_html, rem)
        else:
            def sub_md2(mo, rem=rem, n=name):
                if rem[0] <= 0: return mo.group()
                start = mo.start()
                before = body[:start]
                if re.search(r'\[[^\]]*$', before) or re.search(r'\]\([^)]*$', before): return mo.group()
                rem[0] -= 1
                return f'[{n}]({url})'
            body = re.sub(pat, sub_md2, body)

    return body


def _inject_country(body: str, name: str, code: str, html: bool) -> str:
    if name == "United States": return body
    url = f"{BASE}/countries/{code}"
    existing = _count_linked(body, name, html)
    rem = [max(0, MAX_PER_ENTITY - existing)]
    if rem[0] <= 0: return body
    pat = r'\b' + re.escape(name) + r'\b'
    if html:
        def ml(t): return f'<a href="{url}" class="link-country">{t}</a>'
        body = _replace_in_html_text(body, pat, ml, rem)
    else:
        def sub_md(mo, rem=rem):
            if rem[0] <= 0: return mo.group()
            start = mo.start()
            before = body[:start]
            if re.search(r'\[[^\]]*$', before) or re.search(r'\]\([^)]*$', before): return mo.group()
            rem[0] -= 1
            return f'[{name}]({url})'
        body = re.sub(pat, sub_md, body)
    return body


def _inject_corridors(body: str, html: bool) -> str:
    for exp, imp, phrases in CORRIDORS:
        url = f"{BASE}/trade/{exp}-{imp}"
        if url in body: continue
        for phrase in phrases:
            if phrase not in body: continue
            if html:
                body = body.replace(phrase, f'<a href="{url}" class="link-corridor">{phrase}</a>', 1)
            else:
                if f'[{phrase}]' in body: continue
                body = body.replace(phrase, f'[{phrase}]({url})', 1)
            break
    return body


def _inject_blocs(body: str, html: bool) -> str:
    """Inject links to /blocs/{slug} pages for recognizable bloc/grouping phrases."""
    for phrase, slug in BLOC_PHRASES:
        url = f"{BASE}/blocs/{slug}"
        if url in body:
            continue
        pat = r'\b' + re.escape(phrase) + r'\b'
        if html:
            if re.search(re.escape(phrase), body) and f'class="link-bloc"' in body:
                continue
            body = re.sub(pat, f'<a href="{url}" class="link-bloc">{phrase}</a>', body, count=1, flags=re.IGNORECASE)
        else:
            if f'[{phrase}]' in body:
                continue
            body = re.sub(pat, f'[{phrase}]({url})', body, count=1, flags=re.IGNORECASE)
    return body


def _inject_sectors(body: str, html: bool) -> str:
    """Inject links to sector pages for recognizable sector phrases."""
    for phrase, slug in SECTOR_PHRASES:
        url = f"{BASE}/sectors/{slug}"
        if url in body:
            continue
        pat = r'\b' + re.escape(phrase) + r'\b'
        if html:
            if re.search(f'class="link-sector"[^>]*>{re.escape(phrase)}', body):
                continue
            body = re.sub(pat, f'<a href="{url}" class="link-sector">{phrase}</a>', body, count=1)
        else:
            if f'[{phrase}]' in body:
                continue
            body = re.sub(pat, f'[{phrase}]({url})', body, count=1)
    return body



def _post_clean(body):
    """Remove double-link artifacts from the injector."""
    import re as _r
    body = _r.sub(r'\[(\[[^\]]+\]\([^\)]+\))\]\([^\)]+\)', lambda m: m.group(1), body)
    body = _r.sub(r'\[([^\[\]]+?)\s*\([^\)]*\[[^\]]+\]\([^\)]+\)[^\)]*\)\]\(([^\)]+)\)', lambda m: '[' + m.group(1) + '](' + m.group(2) + ')', body)
    body = _r.sub(r'\[([A-Za-z][^\[\]]+?)\s+\([A-Z]{2,5}\)\]\(([^\)]+)\)', lambda m: '[' + m.group(1) + '](' + m.group(2) + ')', body)
    # Remove duplicate link-in-parens: [X](url) ([X](url)) → [X](url)
    body = _r.sub(r'(\[[^\]]+\]\(https://www\.metricshour\.com/[^)]+\))\s*\(\1\)', r'\1', body)
    return body

def detect_entities(body: str) -> tuple[set[str], set[str]]:
    """
    Scan body text for mentioned stocks and countries using the same maps
    as inject_deep_links. Returns (set_of_tickers, set_of_country_codes).
    Used to auto-populate related_asset_ids / related_country_ids on publish.
    """
    if not body:
        return set(), set()

    # Strip HTML tags for plain-text scanning
    plain = re.sub(r'<[^>]+>', ' ', body)

    tickers_found: set[str] = set()
    for ticker, names in STOCKS.items():
        if not names and ticker in SKIP_TICKER_MATCH:
            continue
        # Check ticker (skip ambiguous short ones)
        if ticker not in SKIP_TICKER_MATCH:
            if re.search(r'\b' + re.escape(ticker) + r'\b', plain):
                tickers_found.add(ticker)
                continue
        # Check company names
        for name in names:
            if name and len(name) >= 4 and re.search(r'\b' + re.escape(name) + r'\b', plain, re.IGNORECASE):
                tickers_found.add(ticker)
                break

    countries_found: set[str] = set()
    for country_name, code in COUNTRIES.items():
        if re.search(r'\b' + re.escape(country_name) + r'\b', plain, re.IGNORECASE):
            countries_found.add(code)

    return tickers_found, countries_found


def inject_deep_links(body: str) -> str:
    """
    Main entry point. Call this on blog post body during publish.
    Returns body with deep internal links injected.
    """
    if not body:
        return body
    html = _is_html(body)
    for ticker, names in STOCKS.items():
        body = _inject_stock(body, ticker, names, html)
    for country_name, code in sorted(COUNTRIES.items(), key=lambda x: -len(x[0])):
        body = _inject_country(body, country_name, code, html)
    body = _inject_corridors(body, html)
    body = _inject_blocs(body, html)
    body = _inject_sectors(body, html)
    body = _post_clean(body)
    return body


