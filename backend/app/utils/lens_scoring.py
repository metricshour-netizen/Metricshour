"""Lens risk scoring engine — all calculations, zero LLM."""
from typing import Optional


def score_stock(
    revenues: list[dict],
    macro_by_country: dict[str, dict],
    earnings_in_30d: bool,
    earnings_in_7d: bool,
) -> dict:
    """
    Score a stock's pre-trade risk based on geographic exposure and macro factors.

    revenues: list of {country_code, revenue_pct}
    macro_by_country: {country_code: {inflation_pct, political_risk, active_tariffs, active_sanctions, currency_stress}}
    earnings_in_30d / earnings_in_7d: whether upcoming earnings are near

    Returns: {score, level, breakdown}
    level: 'LOW' | 'MODERATE' | 'ELEVATED'
    """
    score = 0
    breakdown: list[dict] = []

    # 1. China exposure
    china_pct = next((r['revenue_pct'] for r in revenues if r.get('country_code') == 'CN'), 0)
    if china_pct > 20:
        score += 3
        breakdown.append({'factor': 'China exposure >20%', 'points': 3})
    elif china_pct > 10:
        score += 2
        breakdown.append({'factor': f'China exposure {china_pct:.0f}%', 'points': 2})
    elif china_pct > 5:
        score += 1
        breakdown.append({'factor': f'China exposure {china_pct:.0f}%', 'points': 1})

    # 2. Top country macro risk
    top_countries = sorted(revenues, key=lambda r: r.get('revenue_pct', 0), reverse=True)[:3]
    for rev in top_countries:
        code = rev.get('country_code')
        if not code:
            continue
        macro = macro_by_country.get(code, {})
        country_score = 0

        if macro.get('active_tariffs') or macro.get('active_sanctions'):
            country_score += 3
            breakdown.append({'factor': f'{code}: active tariffs/sanctions', 'points': 3})
        elif (macro.get('inflation_pct') or 0) > 5:
            country_score += 2
            breakdown.append({'factor': f'{code}: inflation {macro.get("inflation_pct", 0):.1f}%', 'points': 2})
        elif macro.get('political_risk'):
            country_score += 2
            breakdown.append({'factor': f'{code}: political instability', 'points': 2})
        elif macro.get('currency_stress'):
            country_score += 1
            breakdown.append({'factor': f'{code}: currency stress', 'points': 1})

        score += min(country_score, 3)  # cap per-country contribution

    # 3. Revenue concentration
    if revenues:
        top_pct = revenues[0].get('revenue_pct', 0) if revenues else 0
        if top_pct > 50:
            score += 2
            breakdown.append({'factor': f'>50% revenue from single country', 'points': 2})
        elif top_pct > 30:
            score += 1
            breakdown.append({'factor': f'{top_pct:.0f}% from single country', 'points': 1})

    # 4. Earnings proximity
    if earnings_in_7d:
        score += 2
        breakdown.append({'factor': 'Earnings within 7 days', 'points': 2})
    elif earnings_in_30d:
        score += 1
        breakdown.append({'factor': 'Earnings within 30 days', 'points': 1})

    level = 'ELEVATED' if score >= 6 else 'MODERATE' if score >= 3 else 'LOW'
    return {'score': score, 'level': level, 'breakdown': breakdown}


def score_forex(
    base_rate: Optional[float],
    quote_rate: Optional[float],
    base_inflation: Optional[float],
    quote_inflation: Optional[float],
    base_gdp_growth: Optional[float],
    quote_gdp_growth: Optional[float],
    trade_deficit_usd: Optional[float],
    base_political_risk: bool = False,
    quote_political_risk: bool = False,
    base_debt_gdp: Optional[float] = None,
    quote_debt_gdp: Optional[float] = None,
) -> dict:
    """
    Score a forex pair's volatility risk.

    Returns: {score, level, breakdown}
    level: 'STABLE' | 'MODERATE' | 'HIGH VOLATILITY'
    """
    score = 0
    breakdown: list[dict] = []

    # Rate differential
    if base_rate is not None and quote_rate is not None:
        diff = abs(base_rate - quote_rate)
        if diff > 1:
            score += 2
            breakdown.append({'factor': f'Rate differential {diff:.1f}%', 'points': 2})

    # Inflation gap
    if base_inflation is not None and quote_inflation is not None:
        gap = abs(base_inflation - quote_inflation)
        if gap > 2:
            score += 2
            breakdown.append({'factor': f'Inflation gap {gap:.1f}%', 'points': 2})

    # Trade deficit
    if trade_deficit_usd is not None and abs(trade_deficit_usd) > 50_000_000_000:
        score += 2
        breakdown.append({'factor': f'Large trade imbalance', 'points': 2})

    # GDP growth gap
    if base_gdp_growth is not None and quote_gdp_growth is not None:
        gap = abs(base_gdp_growth - quote_gdp_growth)
        if gap > 2:
            score += 1
            breakdown.append({'factor': f'GDP growth gap {gap:.1f}%', 'points': 1})

    # Political risk
    if base_political_risk:
        score += 2
        breakdown.append({'factor': 'Political risk (base)', 'points': 2})
    if quote_political_risk:
        score += 2
        breakdown.append({'factor': 'Political risk (quote)', 'points': 2})

    # Debt/GDP
    if (base_debt_gdp and base_debt_gdp > 150) or (quote_debt_gdp and quote_debt_gdp > 150):
        score += 1
        breakdown.append({'factor': 'Debt/GDP >150%', 'points': 1})

    level = 'HIGH VOLATILITY' if score >= 6 else 'MODERATE' if score >= 3 else 'STABLE'
    return {'score': score, 'level': level, 'breakdown': breakdown}


def get_geo_risk_level(country_code: str, macro: dict) -> str:
    """Determine per-country risk emoji/level for Lens geo risk section."""
    if macro.get('active_tariffs') or macro.get('active_sanctions'):
        return 'high'
    inflation = macro.get('inflation_pct') or 0
    if inflation > 5 or macro.get('political_risk') or macro.get('crisis'):
        return 'high'
    if inflation > 3 or macro.get('currency_stress') or macro.get('trade_tension'):
        return 'medium'
    return 'low'


def geo_risk_icon(level: str) -> str:
    return {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(level, '🟡')


def get_macro_pressure_tags(
    pair: str,
    base_code: str,
    quote_code: str,
    base_macro: dict,
    quote_macro: dict,
    rate_differential: float,
) -> list[dict]:
    """Generate rule-based macro pressure tags for forex pair — max 3."""
    tags = []

    # Rate differential direction
    base_rate = base_macro.get('interest_rate_pct') or 0
    quote_rate = quote_macro.get('interest_rate_pct') or 0
    if base_rate > quote_rate + 0.5:
        tags.append({
            'signal': 'green',
            'text': f'Favours {base_code}: rate differential {base_rate - quote_rate:.1f}% in {base_code} favour',
        })
    elif quote_rate > base_rate + 0.5:
        tags.append({
            'signal': 'red',
            'text': f'Headwind for {base_code}: {quote_code} rates {quote_rate - base_rate:.1f}% higher',
        })

    # Inflation comparison
    base_inf = base_macro.get('inflation_pct') or 0
    quote_inf = quote_macro.get('inflation_pct') or 0
    if base_inf > quote_inf + 1.5:
        tags.append({
            'signal': 'red',
            'text': f'Headwind for {base_code}: inflation {base_inf:.1f}% vs {quote_inf:.1f}% in {quote_code}',
        })
    elif quote_inf > base_inf + 1.5:
        tags.append({
            'signal': 'green',
            'text': f'Favours {base_code}: lower inflation {base_inf:.1f}% vs {quote_inf:.1f}% in {quote_code}',
        })

    # GDP growth
    base_gdp = base_macro.get('gdp_growth_pct') or 0
    quote_gdp = quote_macro.get('gdp_growth_pct') or 0
    if abs(base_gdp - quote_gdp) < 0.5:
        tags.append({'signal': 'neutral', 'text': f'Neutral: similar GDP growth ({base_gdp:.1f}% vs {quote_gdp:.1f}%)'})
    elif base_gdp > quote_gdp:
        tags.append({'signal': 'green', 'text': f'Favours {base_code}: GDP growth {base_gdp:.1f}% vs {quote_gdp:.1f}%'})
    else:
        tags.append({'signal': 'red', 'text': f'Headwind for {base_code}: GDP growth {base_gdp:.1f}% vs {quote_gdp:.1f}%'})

    return tags[:3]


def calc_stock_cost(
    price: float,
    size_usd: float,
    market_cap_usd: Optional[float],
) -> dict:
    """Calculate estimated entry costs for a stock position."""
    # Slippage by market cap tier
    if market_cap_usd and market_cap_usd >= 100_000_000_000:
        slippage_pct = 0.0005  # 0.05%
    elif market_cap_usd and market_cap_usd >= 10_000_000_000:
        slippage_pct = 0.0015  # 0.15%
    else:
        slippage_pct = 0.003   # 0.30%

    fee_pct = 0.0005  # 0.05% flat

    slippage_usd = size_usd * slippage_pct
    fee_usd = size_usd * fee_pct
    total_cost_usd = slippage_usd + fee_usd
    effective_size = size_usd + total_cost_usd
    break_even_pct = total_cost_usd / size_usd * 100

    shares = size_usd / price if price > 0 else 0
    effective_price = effective_size / shares if shares > 0 else price

    return {
        'entry_price': round(price, 4),
        'slippage_usd': round(slippage_usd, 2),
        'slippage_pct': round(slippage_pct * 100, 3),
        'fee_usd': round(fee_usd, 2),
        'fee_pct': round(fee_pct * 100, 3),
        'effective_price': round(effective_price, 4),
        'break_even_pct': round(break_even_pct, 3),
        'disclaimer': 'Estimated — actual costs vary by broker',
    }


def calc_forex_cost(
    rate: float,
    size_usd: float,
    pair_type: str,  # major, minor, exotic
) -> dict:
    """Calculate estimated entry costs for a forex position."""
    spread_map = {'major': 0.0002, 'minor': 0.0005, 'exotic': 0.001}
    spread_pct = spread_map.get(pair_type, 0.0005)
    spread_usd = size_usd * spread_pct
    pips_to_break_even = spread_pct * rate * 10000  # approximate pips

    return {
        'entry_rate': round(rate, 5),
        'spread_pct': round(spread_pct * 100, 4),
        'spread_usd': round(spread_usd, 2),
        'effective_rate': round(rate * (1 + spread_pct), 5),
        'break_even_pips': round(pips_to_break_even, 1),
        'pair_type': pair_type,
        'disclaimer': 'Estimated — actual costs vary by broker',
    }


def calc_stress_test(
    country_code: str,
    revenue_pct: float,
    analyst_eps: Optional[float],
    trailing_pe: Optional[float],
    price: float,
    size_usd: Optional[float] = None,
    drop_pct: float = 0.20,
) -> Optional[dict]:
    """
    Estimate impact of a 20% revenue drop from top country.
    Returns None if insufficient data.
    """
    if analyst_eps is None or trailing_pe is None:
        return None

    eps_impact = (revenue_pct / 100) * analyst_eps * drop_pct
    price_impact = eps_impact * trailing_pe
    price_impact_pct = (price_impact / price) * 100 if price > 0 else 0

    result = {
        'country_code': country_code,
        'scenario': f'If {country_code} revenue drops {drop_pct * 100:.0f}%',
        'eps_impact': round(eps_impact, 2),
        'price_impact_usd': round(price_impact, 2),
        'price_impact_pct': round(price_impact_pct, 2),
        'disclaimer': 'Scenario estimate — not financial advice',
    }

    if size_usd and price > 0:
        shares = size_usd / price
        position_impact = shares * price_impact
        result['position_impact_usd'] = round(position_impact, 2)

    return result
