"""Enrich company profiles with CEO, founded year, HQ, employees via Wikipedia API."""
import logging
import re
import time
from typing import Optional

import requests
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models.asset import Asset, AssetType
from app.models.company_profile import CompanyProfile

logger = logging.getLogger(__name__)

WIKIPEDIA_API = 'https://en.wikipedia.org/w/api.php'
RATE_LIMIT_SLEEP = 0.6  # 100 req/min safe ceiling

# Known SOEs (state-owned enterprises) — Chinese companies
CHINA_SOE_PREFIXES = {
    'ICBC', 'CCB', 'ABC', 'BOC', 'BOCOM', 'CITIC', 'PICC', 'CPIC',
    'COSCO', 'CNOOC', 'CNPC', 'SINOPEC', 'SAIC', 'FAW', 'AVIC',
    'CRRC', 'CHINALIFE', 'PINGAN',  # partial — checked by name
}

SOE_NAME_KEYWORDS = [
    'china national', 'state grid', 'china mobile', 'china telecom', 'china unicom',
    'industrial and commercial bank', 'china construction bank', 'bank of china',
    'agricultural bank', 'china life', 'sinopec', 'petrochina', 'cnooc',
    'china southern', 'air china', 'china eastern', 'cosco',
]


def _is_soe(name: str, symbol: str) -> bool:
    lower = name.lower()
    return any(kw in lower for kw in SOE_NAME_KEYWORDS) or symbol.upper() in CHINA_SOE_PREFIXES


def _search_wikipedia(query: str) -> Optional[str]:
    """Find the best Wikipedia page title for a company query."""
    params = {
        'action': 'query',
        'list': 'search',
        'srsearch': query,
        'srlimit': 3,
        'format': 'json',
    }
    try:
        resp = requests.get(WIKIPEDIA_API, params=params, timeout=8,
                            headers={'User-Agent': 'MetricsHour/1.0 (metricshour.com; research)'})
        resp.raise_for_status()
        results = resp.json().get('query', {}).get('search', [])
        if results:
            return results[0]['title']
    except Exception as exc:
        logger.debug('Wikipedia search failed for %s: %s', query, exc)
    return None


def _get_wikitext(title: str) -> Optional[str]:
    """Get raw wikitext for a page to extract infobox data."""
    params = {
        'action': 'parse',
        'page': title,
        'prop': 'wikitext',
        'format': 'json',
    }
    try:
        resp = requests.get(WIKIPEDIA_API, params=params, timeout=10,
                            headers={'User-Agent': 'MetricsHour/1.0 (metricshour.com; research)'})
        resp.raise_for_status()
        data = resp.json()
        return data.get('parse', {}).get('wikitext', {}).get('*')
    except Exception as exc:
        logger.debug('Wikipedia wikitext fetch failed for %s: %s', title, exc)
    return None


def _extract_infobox_value(wikitext: str, *keys: str) -> Optional[str]:
    """Extract a value from a Wikipedia infobox given possible field names."""
    for key in keys:
        pattern = rf'\|\s*{re.escape(key)}\s*=\s*([^\n|}}]+)'
        m = re.search(pattern, wikitext, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Remove wiki markup
            val = re.sub(r'\[\[([^|\]]+\|)?([^\]]+)\]\]', r'\2', val)
            val = re.sub(r'\{\{[^}]+\}\}', '', val)
            val = re.sub(r'<[^>]+>', '', val)
            val = re.sub(r"'''?", '', val)
            val = val.strip(' .,')
            if val and len(val) < 300:
                return val
    return None


def _parse_year(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r'\b(1[89]\d{2}|20[012]\d)\b', text)
    if m:
        return int(m.group(1))
    return None


def _parse_employees(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    text = text.replace(',', '').replace('.', '')
    m = re.search(r'(\d+)\s*(million|billion)?', text, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if m.group(2):
            mult = 1_000_000 if 'million' in m.group(2).lower() else 1_000_000_000
            return n * mult
        if n > 100:  # likely raw headcount
            return n
    return None


def _enrich_stock(symbol: str, name: str, exchange: Optional[str]) -> Optional[dict]:
    """Fetch enrichment data for a single stock from Wikipedia."""
    search_query = f"{name} company"
    title = _search_wikipedia(search_query)
    if not title:
        return None

    wikitext = _get_wikitext(title)
    if not wikitext:
        return None

    profile: dict = {}

    # CEO
    ceo_text = _extract_infobox_value(wikitext, 'key_people', 'CEO', 'ceo', 'president')
    if ceo_text:
        # Extract first name (usually "Name (title)")
        ceo_clean = re.split(r'\(|\n|,|;', ceo_text)[0].strip()
        if ceo_clean and 2 < len(ceo_clean) < 80:
            profile['ceo_name'] = ceo_clean

    # Founded year
    founded_text = _extract_infobox_value(wikitext, 'foundation', 'founded', 'established')
    yr = _parse_year(founded_text)
    if yr:
        profile['founded_year'] = yr

    # HQ
    hq_text = _extract_infobox_value(wikitext, 'headquarters', 'hq_location', 'location_city', 'location')
    if hq_text:
        hq_parts = [p.strip() for p in re.split(r',|;', hq_text) if p.strip()]
        if hq_parts:
            profile['hq_city'] = hq_parts[0][:100]

    # Employees
    emp_text = _extract_infobox_value(wikitext, 'num_employees', 'employees', 'num_employees_year')
    emp = _parse_employees(emp_text)
    if emp:
        profile['employees'] = emp

    # Website
    web_text = _extract_infobox_value(wikitext, 'website', 'url', 'homepage')
    if web_text:
        # Strip wiki external link syntax
        web_clean = re.sub(r'\[https?://([^\s\]]+)[^\]]*\]', r'https://\1', web_text)
        if 'http' in web_clean:
            profile['website'] = web_clean.split()[0][:300]

    # Chinese stocks: look for native name
    if exchange in ('SHG', 'SHE') or _has_chinese_chars(name):
        cn_name = _extract_infobox_value(wikitext, 'native_name', '中文名', 'simplified chinese')
        if cn_name and _has_chinese_chars(cn_name):
            profile['chinese_name'] = cn_name[:200]
        profile['is_soe'] = _is_soe(name, symbol)
        profile['primary_listing'] = exchange or 'SHG'

    if not profile:
        return None

    profile['data_source'] = 'wikipedia'
    return profile


def _has_chinese_chars(s: str) -> bool:
    return bool(re.search(r'[一-鿿]', s))


@shared_task(
    name='tasks.company_enrichment.enrich_companies',
    bind=True,
    max_retries=1,
    default_retry_delay=600,
    soft_time_limit=3600,
)
def enrich_companies(self, limit: int = 500, force: bool = False):
    """Enrich company profiles for top stocks using Wikipedia API.

    Runs weekly on Sunday 04:00 UTC. Rate-limited to ~100 req/min.
    Only fetches profiles that are missing or older than 30 days.
    """
    from datetime import datetime, timezone, timedelta
    stale_threshold = datetime.now(timezone.utc) - timedelta(days=30)

    db = SessionLocal()
    try:
        # Get stocks to enrich: ordered by market_cap DESC
        stocks = db.execute(
            select(Asset.id, Asset.symbol, Asset.name, Asset.exchange, Asset.market_cap_usd)
            .where(Asset.asset_type == AssetType.stock, Asset.is_active == True)
            .order_by(Asset.market_cap_usd.desc().nullslast())
            .limit(limit)
        ).all()

        # Find which ones already have fresh profiles
        existing = {
            row[0]: row[1] for row in db.execute(
                select(CompanyProfile.symbol, CompanyProfile.last_fetched)
            )
        }
    finally:
        db.close()

    enriched = 0
    skipped = 0
    failed = 0

    for asset_id, symbol, name, exchange, market_cap in stocks:
        if not force and symbol in existing:
            last = existing[symbol]
            if last and (not hasattr(last, 'tzinfo') or last.replace(tzinfo=timezone.utc) > stale_threshold):
                skipped += 1
                continue

        time.sleep(RATE_LIMIT_SLEEP)

        try:
            profile_data = _enrich_stock(symbol, name or symbol, exchange)
        except Exception as exc:
            logger.warning('Enrichment failed for %s: %s', symbol, exc)
            failed += 1
            continue

        if not profile_data:
            skipped += 1
            continue

        profile_data['asset_id'] = asset_id
        profile_data['symbol'] = symbol
        from datetime import datetime, timezone
        profile_data['last_fetched'] = datetime.now(timezone.utc)

        db2 = SessionLocal()
        try:
            stmt = pg_insert(CompanyProfile).values([profile_data])
            stmt = stmt.on_conflict_do_update(
                index_elements=['symbol'],
                set_={k: v for k, v in profile_data.items() if k not in ('asset_id', 'symbol')},
            )
            db2.execute(stmt)
            db2.commit()
        finally:
            db2.close()

        enriched += 1
        logger.debug('Enriched %s (%s)', symbol, name)

    logger.info('Company enrichment complete: %d enriched, %d skipped, %d failed', enriched, skipped, failed)
    return {'enriched': enriched, 'skipped': skipped, 'failed': failed}
