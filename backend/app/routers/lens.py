"""Lens — pre-trade analysis API.

GET /api/lens/stocks/{ticker}?size={usd}&direction={long|short}
GET /api/lens/forex/{pair}?size={usd}&direction={long|short}
"""
import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests as http_requests
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.database import get_db
from app.limiter import limiter
from app.models import Asset, AssetType, Country, Price, StockCountryRevenue, CountryIndicator
from app.models.earnings import EarningsEvent
from app.models.summary import PageInsight
from app.storage import cache_get, cache_set
from app.utils.lens_scoring import (
    score_stock, score_forex, get_geo_risk_level, geo_risk_icon,
    get_macro_pressure_tags, calc_stock_cost, calc_forex_cost, calc_stress_test,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lens", tags=["lens"])

# Forex pair → (base_country_code, quote_country_code)
PAIR_COUNTRIES: dict[str, tuple[str, str]] = {
    'EURUSD': ('EU', 'US'), 'GBPUSD': ('GB', 'US'), 'USDJPY': ('US', 'JP'),
    'AUDUSD': ('AU', 'US'), 'USDCAD': ('US', 'CA'), 'USDCHF': ('US', 'CH'),
    'NZDUSD': ('NZ', 'US'), 'EURGBP': ('EU', 'GB'), 'EURJPY': ('EU', 'JP'),
    'GBPJPY': ('GB', 'JP'), 'USDCNY': ('US', 'CN'), 'USDMXN': ('US', 'MX'),
    'USDBRL': ('US', 'BR'), 'USDSGD': ('US', 'SG'), 'USDINR': ('US', 'IN'),
    'USDKRW': ('US', 'KR'), 'USDTRY': ('US', 'TR'), 'USDZAR': ('US', 'ZA'),
    'EURCHF': ('EU', 'CH'), 'EURAUD': ('EU', 'AU'), 'EURCAD': ('EU', 'CA'),
    'GBPAUD': ('GB', 'AU'), 'GBPCAD': ('GB', 'CA'), 'AUDCAD': ('AU', 'CA'),
    'AUDNZD': ('AU', 'NZ'), 'AUDCHF': ('AU', 'CH'), 'CADJPY': ('CA', 'JP'),
    'CHFJPY': ('CH', 'JP'), 'NZDJPY': ('NZ', 'JP'),
}

# MAJOR/MINOR/EXOTIC classification for spread calc
MAJOR_PAIRS = {'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD'}
MINOR_PAIRS = {'EURGBP', 'EURJPY', 'GBPJPY', 'EURCHF', 'EURAUD', 'EURCAD', 'GBPAUD', 'GBPCAD',
               'AUDCAD', 'AUDNZD', 'AUDCHF', 'CADJPY', 'CHFJPY', 'NZDJPY'}

GEO_RISK_CONTEXT: dict[str, str] = {
    'CN': 'US tariffs at 145% — active earnings risk',
    'RU': 'Western sanctions in effect — restricted market',
    'IR': 'US and EU sanctions — restricted market',
    'KR': 'Trade tension with US and China active',
    'MX': 'USMCA tariff uncertainty',
    'IN': 'Elevated inflation, import tariff risks',
    'TR': 'Currency stress, inflation >50%',
    'AR': 'Currency crisis, capital controls',
    'VN': 'Supply chain hub, US trade scrutiny',
    'TW': 'Geopolitical risk with China elevated',
    'DE': 'Industrial slowdown, energy costs',
    'JP': 'BOJ normalisation underway',
    'GB': 'Post-Brexit trade friction',
    'US': 'Domestic demand, Fed policy path',
    'EU': 'Monetary union, ECB rate cycle',
}


def _get_macro_indicators(db: Session, country_code: str) -> dict:
    """Fetch latest economic indicators for a country."""
    from sqlalchemy import text as sql_text
    country = db.execute(
        select(Country).where(Country.code == country_code)
    ).scalar_one_or_none()
    if not country:
        return {}

    indicators: dict = {}
    WANTED = ['gdp_usd', 'gdp_growth_pct', 'inflation_pct', 'interest_rate_pct',
              'unemployment_pct', 'govt_debt_gdp_pct', 'current_account_gdp_pct',
              'political_stability_score']
    rows = db.execute(
        select(CountryIndicator)
        .where(CountryIndicator.country_id == country.id,
               CountryIndicator.indicator.in_(WANTED),
               CountryIndicator.value.isnot(None))
        .order_by(CountryIndicator.indicator, CountryIndicator.period_date.desc())
    ).scalars().all()
    seen: set = set()
    for r in rows:
        if r.indicator not in seen:
            seen.add(r.indicator)
            indicators[r.indicator] = float(r.value)

    # Derive risk signals
    inflation = indicators.get('inflation_pct', 0)
    stability = indicators.get('political_stability_score')
    indicators['inflation_pct'] = inflation
    indicators['active_tariffs'] = country_code in ('CN',)  # simplified — could be enriched
    indicators['political_risk'] = (stability is not None and stability < -0.5)
    indicators['currency_stress'] = country_code in ('TR', 'AR', 'EG', 'NG', 'BD')
    indicators['active_sanctions'] = country_code in ('RU', 'IR', 'KP', 'SY')
    indicators['credit_rating'] = getattr(country, 'credit_rating_sp', None)
    indicators['name'] = country.name
    indicators['flag'] = getattr(country, 'flag_emoji', '')
    return indicators


def _get_existing_insight(db: Session, ticker: str) -> Optional[str]:
    """Return a fresh (<24h) existing insight for this ticker, or None."""
    threshold = datetime.now(timezone.utc) - timedelta(hours=24)
    row = db.execute(
        select(PageInsight)
        .where(
            PageInsight.entity_type == 'stock_insight',
            PageInsight.entity_code == ticker.upper(),
            PageInsight.generated_at >= threshold,
        )
        .order_by(PageInsight.generated_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return row.summary if row else None


def _generate_lens_insight(data: dict, asset_type: str) -> Optional[str]:
    """Call Gemini to generate a Lens narrative. LLM narrates data — never invents."""
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return None

    asset_label = data.get('name', data.get('pair', 'this asset'))
    prompt = (
        "You are a senior financial analyst writing for active traders who already see the price data on screen.\n\n"
        "Your job is to explain what the data MEANS — not what it says.\n\n"
        "RULES:\n"
        "- Never restate numbers already visible on screen (price, change %, country names)\n"
        "- Explain the specific macro mechanism creating the current risk or opportunity\n"
        "- Reference one real current event or condition driving the situation\n"
        "- End with exactly one specific thing the trader should watch next\n"
        "- Maximum 3 sentences total\n"
        "- No jargon, no hedging, no filler phrases\n"
        "- Write directly and confidently\n"
        "- Must mention at least one specific number (rate, %, tariff level, etc.)\n\n"
        "BAD EXAMPLE: 'The stock is down. China is a large market. Risk is moderate.'\n\n"
        "GOOD EXAMPLE: 'Apple's China revenue faces direct pressure from 145% US tariffs currently "
        "in effect — a structural headwind that compounds with yuan weakness reducing dollar-converted "
        "earnings. Consumer spending softness in the US adds a second drag on the 20% domestic revenue "
        "base. Watch the next earnings call for China revenue guidance and any US-China trade negotiation signals.'\n\n"
        f"Asset: {asset_label}\n"
        f"Data: {json.dumps(data, default=str)}"
    )
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        resp = http_requests.post(
            url,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300},
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip any markdown
        text = re.sub(r'^[#*\-]+\s*', '', text, flags=re.MULTILINE).strip()
        if 15 <= len(text.split()) <= 150:
            return text
    except Exception as exc:
        logger.debug('Lens insight generation failed: %s', exc)
    return None


@router.get("/stocks/{ticker}")
@limiter.limit("30/minute")
def lens_stock(
    request: Request,
    ticker: str,
    size: Optional[float] = Query(default=None, gt=0, le=10_000_000),
    direction: str = Query(default='long', pattern='^(long|short)$'),
    db: Session = Depends(get_db),
) -> dict:
    """Pre-trade analysis for a stock."""
    ticker_upper = ticker.upper()

    # Cache key includes size/direction since cost section depends on them
    cache_key = f"lens:stock:{ticker_upper}:{size or 'none'}:{direction}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Fetch asset
    asset = db.execute(
        select(Asset).where(Asset.symbol == ticker_upper, Asset.is_active == True)
    ).scalar_one_or_none()
    if not asset or asset.asset_type != AssetType.stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Latest price
    latest_price = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.interval == '1d')
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()

    price_close = latest_price.close if latest_price else None
    price_change_pct = None
    if latest_price and latest_price.open and latest_price.open != 0:
        price_change_pct = (latest_price.close - latest_price.open) / latest_price.open * 100

    # Geographic revenue (top 3)
    rev_rows = db.execute(
        select(StockCountryRevenue, Country)
        .join(Country, StockCountryRevenue.country_id == Country.id)
        .where(StockCountryRevenue.asset_id == asset.id)
        .order_by(StockCountryRevenue.fiscal_year.desc(), StockCountryRevenue.revenue_pct.desc())
    ).all()
    seen_cty: set = set()
    revenues: list[dict] = []
    for rev, cty in rev_rows:
        if cty.id not in seen_cty and len(revenues) < 3:
            seen_cty.add(cty.id)
            revenues.append({
                'country_code': cty.code,
                'country_name': cty.name,
                'flag': getattr(cty, 'flag_emoji', ''),
                'revenue_pct': float(rev.revenue_pct),
            })

    # Macro data for top countries
    macro_by_country: dict = {}
    for rev in revenues:
        code = rev['country_code']
        macro_by_country[code] = _get_macro_indicators(db, code)

    # Upcoming earnings
    now = datetime.now(timezone.utc)
    upcoming_earnings = db.execute(
        select(EarningsEvent)
        .where(
            EarningsEvent.symbol == ticker_upper,
            EarningsEvent.report_date >= now.date(),
            EarningsEvent.report_date <= (now + timedelta(days=30)).date(),
        )
        .order_by(EarningsEvent.report_date)
        .limit(1)
    ).scalar_one_or_none()

    earnings_in_30d = upcoming_earnings is not None
    earnings_in_7d = (upcoming_earnings is not None and
                      upcoming_earnings.report_date <= (now + timedelta(days=7)).date())

    # Risk score
    risk = score_stock(revenues, macro_by_country, earnings_in_30d, earnings_in_7d)

    # LLM insight — check cache first, then existing DB insight, then generate
    insight_text = None
    insight_source = None

    insight_cache_key = f"lens:insight:stock:{ticker_upper}"
    cached_insight = cache_get(insight_cache_key)
    if cached_insight:
        insight_text = cached_insight
        insight_source = 'cache'
    else:
        # Check existing PageInsight
        existing = _get_existing_insight(db, ticker_upper)
        if existing:
            insight_text = existing
            insight_source = 'intelligence'
            cache_set(insight_cache_key, insight_text, ttl_seconds=86400)
        else:
            # Generate via Gemini
            insight_data = {
                'name': asset.name,
                'ticker': ticker_upper,
                'sector': asset.sector,
                'price': price_close,
                'change_pct': price_change_pct,
                'top_countries': [f"{r['country_name']} ({r['country_code']}): {r['revenue_pct']:.0f}%" for r in revenues],
                'risk_level': risk['level'],
                'earnings_soon': earnings_in_7d,
            }
            generated = _generate_lens_insight(insight_data, 'stock')
            if generated:
                insight_text = generated
                insight_source = 'generated'
                cache_set(insight_cache_key, insight_text, ttl_seconds=86400)

    # Geographic risk section
    geo_risk = []
    for rev in revenues:
        code = rev['country_code']
        macro = macro_by_country.get(code, {})
        level = get_geo_risk_level(code, macro)
        context = GEO_RISK_CONTEXT.get(code, 'No active macro threat identified')
        geo_risk.append({
            'country_code': code,
            'country_name': rev['country_name'],
            'flag': rev['flag'],
            'revenue_pct': rev['revenue_pct'],
            'risk_level': level,
            'risk_icon': geo_risk_icon(level),
            'context': context,
            'inflation_pct': macro.get('inflation_pct'),
        })

    # Cost estimate (if size provided)
    cost = None
    if size and price_close:
        cost = calc_stock_cost(price_close, size, asset.market_cap_usd)

    # Stress test (requires EPS data)
    stress = None
    if revenues and upcoming_earnings and upcoming_earnings.eps_estimate:
        # Use top revenue country for stress test
        top_rev = revenues[0]
        # Trailing P/E — approximate from price + EPS estimate
        est_eps = upcoming_earnings.eps_estimate
        trailing_pe = (price_close / est_eps) if (price_close and est_eps and est_eps > 0) else None
        if trailing_pe:
            stress = calc_stress_test(
                country_code=top_rev['country_code'],
                revenue_pct=top_rev['revenue_pct'],
                analyst_eps=est_eps,
                trailing_pe=trailing_pe,
                price=price_close,
                size_usd=size,
            )

    # What to watch (from macro calendar)
    from app.models.macro_calendar import MacroCalendarEvent
    what_to_watch: list[dict] = []
    rev_codes = [r['country_code'] for r in revenues]
    if rev_codes:
        watch_events = db.execute(
            select(MacroCalendarEvent)
            .where(
                MacroCalendarEvent.country_code.in_(rev_codes),
                MacroCalendarEvent.event_date >= now,
                MacroCalendarEvent.event_date <= now + timedelta(days=30),
                MacroCalendarEvent.impact == 'high',
            )
            .order_by(MacroCalendarEvent.event_date)
            .limit(3)
        ).scalars().all()
        for evt in watch_events:
            what_to_watch.append({
                'event': evt.event_name,
                'date': evt.event_date.strftime('%b %d'),
                'country_code': evt.country_code,
            })
    if upcoming_earnings and earnings_in_30d:
        what_to_watch.insert(0, {
            'event': f'{ticker_upper} Earnings',
            'date': str(upcoming_earnings.report_date),
            'country_code': 'US',
        })
    what_to_watch = what_to_watch[:3]

    result = {
        'ticker': ticker_upper,
        'name': asset.name,
        'sector': asset.sector,
        'exchange': asset.exchange,
        'currency': asset.currency,
        'price': price_close,
        'change_pct': round(price_change_pct, 2) if price_change_pct is not None else None,
        'market_cap_usd': asset.market_cap_usd,
        'direction': direction,
        'size_usd': size,
        'risk': risk,
        'insight': insight_text,
        'insight_source': insight_source,
        'geo_risk': geo_risk,
        'cost': cost,
        'stress_test': stress,
        'what_to_watch': what_to_watch,
        'last_updated': datetime.now(timezone.utc).isoformat(),
    }

    # Cache for 6 hours (risk score) — insight already cached separately for 24h
    cache_set(cache_key, result, ttl_seconds=21600)
    return result


@router.get("/forex/{pair}")
@limiter.limit("30/minute")
def lens_forex(
    request: Request,
    pair: str,
    size: Optional[float] = Query(default=None, gt=0, le=10_000_000),
    direction: str = Query(default='long', pattern='^(long|short)$'),
    db: Session = Depends(get_db),
) -> dict:
    """Pre-trade analysis for a forex pair."""
    pair_upper = pair.upper()

    cache_key = f"lens:forex:{pair_upper}:{size or 'none'}:{direction}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Fetch FX asset
    asset = db.execute(
        select(Asset).where(Asset.symbol == pair_upper, Asset.is_active == True)
    ).scalar_one_or_none()
    if not asset or asset.asset_type != AssetType.fx:
        raise HTTPException(status_code=404, detail="Forex pair not found")

    latest_price = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.interval == '1d')
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()

    rate = latest_price.close if latest_price else None
    change_pct = None
    if latest_price and latest_price.open and latest_price.open != 0:
        change_pct = (latest_price.close - latest_price.open) / latest_price.open * 100

    # Get country codes for this pair
    country_codes = PAIR_COUNTRIES.get(pair_upper)
    if not country_codes:
        # Try to infer from 6-char pair: first 3 = base, last 3 = quote currency
        # Use currency→country mapping
        base_curr = pair_upper[:3]
        quote_curr = pair_upper[3:6] if len(pair_upper) >= 6 else ''
        CURR_TO_COUNTRY = {
            'USD': 'US', 'EUR': 'EU', 'GBP': 'GB', 'JPY': 'JP', 'AUD': 'AU',
            'CAD': 'CA', 'CHF': 'CH', 'NZD': 'NZ', 'CNY': 'CN', 'MXN': 'MX',
            'BRL': 'BR', 'SGD': 'SG', 'INR': 'IN', 'KRW': 'KR', 'TRY': 'TR',
            'ZAR': 'ZA', 'HKD': 'HK', 'SEK': 'SE', 'NOK': 'NO', 'DKK': 'DK',
        }
        base_code = CURR_TO_COUNTRY.get(base_curr, base_curr)
        quote_code = CURR_TO_COUNTRY.get(quote_curr, quote_curr)
        country_codes = (base_code, quote_code)

    base_code, quote_code = country_codes

    # Macro data for both countries
    base_macro = _get_macro_indicators(db, base_code)
    quote_macro = _get_macro_indicators(db, quote_code)

    base_rate = base_macro.get('interest_rate_pct')
    quote_rate = quote_macro.get('interest_rate_pct')
    rate_differential = (base_rate - quote_rate) if (base_rate is not None and quote_rate is not None) else None

    # Fetch trade balance between countries (directional — base country's perspective)
    from app.models.country import TradePair
    base_country = db.execute(select(Country).where(Country.code == base_code)).scalar_one_or_none()
    quote_country = db.execute(select(Country).where(Country.code == quote_code)).scalar_one_or_none()
    trade_balance_usd = None
    if base_country and quote_country:
        tp = db.execute(
            select(TradePair)
            .where(
                TradePair.exporter_id.in_([base_country.id, quote_country.id]),
                TradePair.importer_id.in_([base_country.id, quote_country.id]),
            )
            .limit(1)
        ).scalar_one_or_none()
        if tp:
            trade_balance_usd = (tp.exports_usd or 0) - (tp.imports_usd or 0)

    # Risk score
    risk = score_forex(
        base_rate=base_rate,
        quote_rate=quote_rate,
        base_inflation=base_macro.get('inflation_pct'),
        quote_inflation=quote_macro.get('inflation_pct'),
        base_gdp_growth=base_macro.get('gdp_growth_pct'),
        quote_gdp_growth=quote_macro.get('gdp_growth_pct'),
        trade_deficit_usd=trade_balance_usd,
        base_political_risk=bool(base_macro.get('political_risk')),
        quote_political_risk=bool(quote_macro.get('political_risk')),
        base_debt_gdp=base_macro.get('govt_debt_gdp_pct'),
        quote_debt_gdp=quote_macro.get('govt_debt_gdp_pct'),
    )

    # Macro pressure tags
    macro_pressure = get_macro_pressure_tags(
        pair=pair_upper,
        base_code=base_code,
        quote_code=quote_code,
        base_macro=base_macro,
        quote_macro=quote_macro,
        rate_differential=rate_differential or 0,
    )

    # LLM insight
    insight_text = None
    insight_cache_key = f"lens:insight:forex:{pair_upper}"
    cached_insight = cache_get(insight_cache_key)
    if cached_insight:
        insight_text = cached_insight
    else:
        insight_data = {
            'pair': pair_upper,
            'rate': rate,
            'change_pct': change_pct,
            'base_country': base_macro.get('name', base_code),
            'quote_country': quote_macro.get('name', quote_code),
            'rate_differential': rate_differential,
            'base_rate': base_rate,
            'quote_rate': quote_rate,
            'base_inflation': base_macro.get('inflation_pct'),
            'quote_inflation': quote_macro.get('inflation_pct'),
            'risk_level': risk['level'],
        }
        generated = _generate_lens_insight(insight_data, 'forex')
        if generated:
            insight_text = generated
            cache_set(insight_cache_key, insight_text, ttl_seconds=86400)

    # Cost estimate
    cost = None
    if size and rate:
        pair_type = 'major' if pair_upper in MAJOR_PAIRS else 'minor' if pair_upper in MINOR_PAIRS else 'exotic'
        cost = calc_forex_cost(rate, size, pair_type)

    # Related pairs (same base or quote currency, max 3)
    related_pairs = []
    for p, (bc, qc) in PAIR_COUNTRIES.items():
        if p == pair_upper:
            continue
        if bc == base_code or qc == base_code or bc == quote_code or qc == quote_code:
            related_pairs.append(p)
        if len(related_pairs) >= 3:
            break

    # What to watch — upcoming events for both countries
    from app.models.macro_calendar import MacroCalendarEvent
    now = datetime.now(timezone.utc)
    watch_events = db.execute(
        select(MacroCalendarEvent)
        .where(
            MacroCalendarEvent.country_code.in_([base_code, quote_code]),
            MacroCalendarEvent.event_date >= now,
            MacroCalendarEvent.event_date <= now + timedelta(days=30),
            MacroCalendarEvent.impact == 'high',
        )
        .order_by(MacroCalendarEvent.event_date)
        .limit(3)
    ).scalars().all()
    what_to_watch = [
        {'event': e.event_name, 'date': e.event_date.strftime('%b %d'), 'country_code': e.country_code}
        for e in watch_events
    ]

    # Country comparison data
    comparison = {
        'base_code': base_code,
        'quote_code': quote_code,
        'base_name': base_macro.get('name', base_code),
        'quote_name': quote_macro.get('name', quote_code),
        'base_flag': base_macro.get('flag', ''),
        'quote_flag': quote_macro.get('flag', ''),
        'rows': [
            {
                'label': 'Interest Rate',
                'base': f"{base_rate:.2f}%" if base_rate is not None else '—',
                'quote': f"{quote_rate:.2f}%" if quote_rate is not None else '—',
            },
            {
                'label': 'Inflation',
                'base': f"{base_macro.get('inflation_pct', 0):.1f}%" if base_macro.get('inflation_pct') is not None else '—',
                'quote': f"{quote_macro.get('inflation_pct', 0):.1f}%" if quote_macro.get('inflation_pct') is not None else '—',
            },
            {
                'label': 'GDP Growth',
                'base': f"{base_macro.get('gdp_growth_pct', 0):.1f}%" if base_macro.get('gdp_growth_pct') is not None else '—',
                'quote': f"{quote_macro.get('gdp_growth_pct', 0):.1f}%" if quote_macro.get('gdp_growth_pct') is not None else '—',
            },
            {
                'label': 'Debt/GDP',
                'base': f"{base_macro.get('govt_debt_gdp_pct', 0):.0f}%" if base_macro.get('govt_debt_gdp_pct') is not None else '—',
                'quote': f"{quote_macro.get('govt_debt_gdp_pct', 0):.0f}%" if quote_macro.get('govt_debt_gdp_pct') is not None else '—',
            },
            {
                'label': 'S&P Rating',
                'base': base_macro.get('credit_rating') or '—',
                'quote': quote_macro.get('credit_rating') or '—',
            },
        ],
    }
    if rate_differential is not None:
        comparison['rate_differential'] = rate_differential

    result = {
        'pair': pair_upper,
        'base_code': base_code,
        'quote_code': quote_code,
        'rate': rate,
        'change_pct': round(change_pct, 4) if change_pct is not None else None,
        'direction': direction,
        'size_usd': size,
        'risk': risk,
        'insight': insight_text,
        'comparison': comparison,
        'macro_pressure': macro_pressure,
        'cost': cost,
        'what_to_watch': what_to_watch,
        'related_pairs': related_pairs,
        'last_updated': datetime.now(timezone.utc).isoformat(),
    }

    cache_set(cache_key, result, ttl_seconds=21600)
    return result
