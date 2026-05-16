"""
tasks/llms.py — Daily regeneration of /llms-full.txt

Pulls all published blog posts from the DB and writes a machine-readable
full-content file at frontend/public/llms-full.txt following the llmstxt.org spec.
Runs daily at 02:30 UTC via Celery beat.
"""
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from celery_app import app
from sqlalchemy import text
from app.database import SessionLocal

log = logging.getLogger(__name__)

BASE_URL = "https://metricshour.com"
_FRONTEND = Path(__file__).parents[2] / "frontend"
OUT_PATH = _FRONTEND / "public" / "llms-full.txt"          # source (included in next build)
OUT_PATH_SERVED = _FRONTEND / ".output" / "public" / "llms-full.txt"  # live-served by Nuxt
LLM_INDEX_PATH = _FRONTEND / "public" / "llms.txt"        # overview index (auto-generated)
LLM_INDEX_SERVED = _FRONTEND / ".output" / "public" / "llms.txt"


def _strip_markdown(text: str) -> str:
    """Strip markdown syntax, keeping clean prose for LLM consumption."""
    # Remove markdown links but keep link text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove images
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    # Remove headers markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove blockquote markers
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # Collapse excess blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _generate_llms_index(posts, counts: dict) -> str:
    """Generate the overview llms.txt from live DB counts and latest posts."""
    now = counts.get("generated", "unknown")
    blog_count = counts.get("blogs", len(posts))
    stock_count = counts.get("stocks", 789)
    country_count = counts.get("countries", 196)
    trade_count = counts.get("trade_pairs", 2708)

    recent_10 = posts[:10]
    selected_lines = "\n".join(
        f"- [{p[0]}]({BASE_URL}/blog/{p[1]})" for p in recent_10
    )

    return f"""# MetricsHour

> MetricsHour is a financial intelligence platform that maps geographic revenue exposure for stocks, tracks macro data for {country_count} countries, and surfaces bilateral trade flows between {trade_count:,}+ country pairs. Built for investors who want to understand where companies actually earn their money.

> Full content for AI indexing: {BASE_URL}/llms-full.txt (updated daily)

## Key Features

- [Geographic Revenue Screener]({BASE_URL}/screener/) — filter {stock_count}+ global stocks by revenue from any country (China, Europe, emerging markets)
- [Country Economy Pages]({BASE_URL}/countries/) — GDP, inflation, interest rates, trade balance, and 80+ indicators for {country_count} countries
- [Bilateral Trade Data]({BASE_URL}/trade/) — export/import flows between {trade_count:,}+ country pairs
- [Stock Pages]({BASE_URL}/stocks/) — geographic revenue breakdown from SEC 10-K filings for {stock_count}+ stocks
- [Smart Money Tracker]({BASE_URL}/smart-money/) — 13F filings from 15 top investors (Buffett, Burry, Dalio, ARK, Tiger Global)
- [Revenue Lens Pages]({BASE_URL}/lens/) — deep country-level revenue breakdown per stock (354 US stocks)
- [Yield Curve]({BASE_URL}/yield-curve/) — live US Treasury yield curve with historical comparisons
- [Interest Rates]({BASE_URL}/rates/) — central bank policy rates and FRED macro series
- [Earnings Calendar]({BASE_URL}/earnings/) — upcoming earnings with geographic revenue context
- [China A-Shares]({BASE_URL}/china/) — 300 Shanghai and Shenzhen stocks
- [Blog]({BASE_URL}/blog/) — {blog_count} data-driven articles on trade war exposure and macro trends

## Screener Pages (8 curated filters)

- [No China Exposure]({BASE_URL}/screener/no-china-exposure/)
- [Low China Exposure]({BASE_URL}/screener/low-china-exposure/)
- [China-Exposed Stocks]({BASE_URL}/screener/china-exposed-stocks/)
- [Tariff-Proof Stocks]({BASE_URL}/screener/tariff-proof-stocks/)
- [High US Revenue]({BASE_URL}/screener/high-us-revenue/)
- [India Growth Stocks]({BASE_URL}/screener/india-growth-stocks/)
- [Europe-Exposed Stocks]({BASE_URL}/screener/europe-exposed-stocks/)
- [Large Cap Stocks]({BASE_URL}/screener/large-cap-stocks/)

## Smart Money — 15 Tracked Investors

Format: {BASE_URL}/smart-money/{{investor-slug}}

- [Warren Buffett (Berkshire Hathaway)]({BASE_URL}/smart-money/warren-buffett)
- [Bill Ackman (Pershing Square)]({BASE_URL}/smart-money/bill-ackman)
- [Michael Burry (Scion Asset Management)]({BASE_URL}/smart-money/michael-burry)
- [Ray Dalio (Bridgewater)]({BASE_URL}/smart-money/ray-dalio)
- [Stanley Druckenmiller]({BASE_URL}/smart-money/stanley-druckenmiller)
- [Cathie Wood (ARK Invest)]({BASE_URL}/smart-money/cathie-wood)

## Country Groups

- [European Union]({BASE_URL}/blocs/eu)
- [G7]({BASE_URL}/blocs/g7)
- [G20]({BASE_URL}/blocs/g20)
- [BRICS]({BASE_URL}/blocs/brics)
- [ASEAN]({BASE_URL}/blocs/asean)
- [NATO]({BASE_URL}/blocs/nato)
- [OPEC]({BASE_URL}/blocs/opec)

## Market Data

- [Cryptocurrencies]({BASE_URL}/crypto/) — 50 assets
- [ETFs]({BASE_URL}/etfs/) — 100 ETFs
- [FX Pairs]({BASE_URL}/fx/) — major currency pairs
- [Commodities]({BASE_URL}/commodities/) — 24 commodities (energy, metals, agriculture)

## Blog ({blog_count} published posts — updated {now})

Selected recent articles:

{selected_lines}

Full list: {BASE_URL}/blog/
Full content: {BASE_URL}/llms-full.txt

## API

- Countries: https://api.metricshour.com/api/countries
- Stocks: https://api.metricshour.com/api/assets?type=stock
- Trade pairs: https://api.metricshour.com/api/trade
- Smart Money investors: https://api.metricshour.com/api/smartmoney/investors
- Sitemap: https://api.metricshour.com/sitemap.xml
"""


def generate_llms_full() -> int:
    """Generate llms-full.txt and llms.txt. Returns number of posts written."""
    db = SessionLocal()
    try:
        posts = db.execute(text(
            "SELECT title, slug, body, excerpt, published_at, category "
            "FROM blog_posts WHERE status='published' "
            "ORDER BY published_at DESC"
        )).fetchall()
        stock_count = db.execute(text(
            "SELECT COUNT(*) FROM assets WHERE is_active=true AND asset_type='stock'"
        )).scalar() or 789
        country_count = db.execute(text(
            "SELECT COUNT(*) FROM countries"
        )).scalar() or 196
        trade_count = db.execute(text(
            "SELECT COUNT(*) FROM trade_pairs"
        )).scalar() or 2708
    finally:
        db.close()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        "# MetricsHour",
        "",
        "> MetricsHour is a financial intelligence platform that maps geographic revenue exposure "
        "for stocks, tracks macro data for 250 countries, and surfaces bilateral trade flows "
        "between 2,700+ country pairs. Built for investors who need to understand where companies "
        "actually earn their money.",
        "",
        f"> Generated: {now} | Posts: {len(posts)} | Source: {BASE_URL}/llms-full.txt",
        "",
        "---",
        "",
    ]

    for post in posts:
        title, slug, body, excerpt, published_at, category = post
        url = f"{BASE_URL}/blog/{slug}"
        date_str = published_at.strftime("%Y-%m-%d") if published_at else "unknown"
        cat_str = f" | Category: {category}" if category else ""

        lines.append(f"## {title}")
        lines.append(f"URL: {url}")
        lines.append(f"Date: {date_str}{cat_str}")
        lines.append("")
        if excerpt:
            lines.append(_strip_markdown(excerpt))
            lines.append("")
        if body:
            lines.append(_strip_markdown(body))
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(content, encoding="utf-8")
    # Also write to .output/public/ so Nuxt SSR serves it immediately without a rebuild
    if OUT_PATH_SERVED.parent.exists():
        OUT_PATH_SERVED.write_text(content, encoding="utf-8")
    log.info("llms-full.txt written: %d posts, %d KB", len(posts), len(content) // 1024)

    # Auto-generate the llms.txt overview index so counts never go stale
    counts = {
        "generated": now,
        "blogs": len(posts),
        "stocks": stock_count,
        "countries": country_count,
        "trade_pairs": trade_count,
    }
    index_content = _generate_llms_index(posts, counts)
    LLM_INDEX_PATH.write_text(index_content, encoding="utf-8")
    if LLM_INDEX_SERVED.parent.exists():
        LLM_INDEX_SERVED.write_text(index_content, encoding="utf-8")
    log.info("llms.txt index written: %d posts, %d stocks, %d countries", len(posts), stock_count, country_count)

    return len(posts)


@app.task(name="tasks.llms.generate_llms_full", bind=True, max_retries=2)
def generate_llms_full_task(self):
    try:
        count = generate_llms_full()
        return {"posts": count}
    except Exception as exc:
        log.error("generate_llms_full failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)
