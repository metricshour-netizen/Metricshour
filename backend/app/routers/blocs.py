"""
Group/bloc pages — /api/groups/{slug}
Aggregates member country data for economic and political groupings.
Data source: boolean columns on the countries table (is_eu, is_g7, etc.)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.database import get_db
from app.limiter import limiter
from app.models import Country, CountryIndicator, StockCountryRevenue, Asset
from app.models.asset import AssetType
from app.storage import cache_get, cache_set

router = APIRouter(prefix="/blocs", tags=["blocs"])

# Canonical metadata for each grouping
GROUP_META = {
    "g7": {
        "name": "G7",
        "full_name": "Group of Seven",
        "description": "The G7 is a forum of seven of the world's largest advanced economies: Canada, France, Germany, Italy, Japan, the United Kingdom, and the United States. Together they account for roughly 45% of global GDP and shape international economic policy, trade rules, and monetary coordination.",
        "founded": 1975,
        "hq": "Rotating presidency",
        "website": "https://www.g7italy.it",
        "field": "is_g7",
        "emoji": "🌐",
        "keywords": ["G7 GDP", "G7 countries economy", "Group of Seven trade", "G7 economic data"],
    },
    "g20": {
        "name": "G20",
        "full_name": "Group of Twenty",
        "description": "The G20 brings together the world's major economies, representing around 85% of global GDP, 75% of global trade, and two-thirds of the world's population. It serves as the premier forum for international economic cooperation and financial stability.",
        "founded": 1999,
        "hq": "Rotating presidency",
        "website": "https://www.g20.org",
        "field": "is_g20",
        "emoji": "🌍",
        "keywords": ["G20 GDP", "G20 countries economy", "G20 trade", "global economic data"],
    },
    "eu": {
        "name": "European Union",
        "full_name": "European Union",
        "description": "The European Union is a political and economic union of 27 member states in Europe. With a single market, common trade policy, and the euro as its currency in the eurozone, the EU is the world's largest trading bloc and a major force in global regulatory standards.",
        "founded": 1993,
        "hq": "Brussels, Belgium",
        "website": "https://europa.eu",
        "field": "is_eu",
        "emoji": "🇪🇺",
        "keywords": ["EU GDP", "European Union economy", "EU trade data", "EU economic indicators"],
    },
    "eurozone": {
        "name": "Eurozone",
        "full_name": "Eurozone (Euro Area)",
        "description": "The Eurozone comprises the EU member states that have adopted the euro as their common currency. Monetary policy is set by the European Central Bank (ECB) in Frankfurt. The eurozone represents one of the world's largest currency areas by GDP.",
        "founded": 1999,
        "hq": "Frankfurt, Germany (ECB)",
        "website": "https://www.ecb.europa.eu",
        "field": "is_eurozone",
        "emoji": "💶",
        "keywords": ["Eurozone GDP", "euro area economy", "ECB monetary policy", "eurozone inflation"],
    },
    "nato": {
        "name": "NATO",
        "full_name": "North Atlantic Treaty Organization",
        "description": "NATO is a military alliance of 32 North American and European countries committed to collective defense under Article 5. Member states collectively account for over 55% of global defense spending, making NATO the world's most powerful military alliance.",
        "founded": 1949,
        "hq": "Brussels, Belgium",
        "website": "https://www.nato.int",
        "field": "is_nato",
        "emoji": "🛡️",
        "keywords": ["NATO countries GDP", "NATO defense spending", "NATO member economies", "North Atlantic alliance"],
    },
    "brics": {
        "name": "BRICS",
        "full_name": "BRICS Nations",
        "description": "BRICS is an intergovernmental organization of major emerging market economies: Brazil, Russia, India, China, South Africa, and newer members. BRICS nations collectively represent over 40% of the world's population and roughly 26% of global GDP at market exchange rates.",
        "founded": 2009,
        "hq": "Rotating presidency",
        "website": "https://www.brics2024.org",
        "field": "is_brics",
        "emoji": "🌏",
        "keywords": ["BRICS GDP", "BRICS countries economy", "emerging markets data", "BRICS trade"],
    },
    "opec": {
        "name": "OPEC",
        "full_name": "Organization of the Petroleum Exporting Countries",
        "description": "OPEC is a cartel of 12 oil-producing nations that collectively control about 80% of the world's proven crude oil reserves. OPEC's production decisions directly impact global oil prices, energy markets, and the fiscal revenues of member states.",
        "founded": 1960,
        "hq": "Vienna, Austria",
        "website": "https://www.opec.org",
        "field": "is_opec",
        "emoji": "🛢️",
        "keywords": ["OPEC countries GDP", "OPEC oil production", "OPEC member economies", "crude oil reserves"],
    },
    "asean": {
        "name": "ASEAN",
        "full_name": "Association of Southeast Asian Nations",
        "description": "ASEAN is a regional intergovernmental organization of ten Southeast Asian countries. As a collective, ASEAN is the world's fifth-largest economy and a key hub for global manufacturing, semiconductors, and trade flows between China, the US, and Japan.",
        "founded": 1967,
        "hq": "Jakarta, Indonesia",
        "website": "https://asean.org",
        "field": "is_asean",
        "emoji": "🌴",
        "keywords": ["ASEAN GDP", "Southeast Asia economy", "ASEAN trade data", "ASEAN economic indicators"],
    },
    "oecd": {
        "name": "OECD",
        "full_name": "Organisation for Economic Co-operation and Development",
        "description": "The OECD is an international organisation of 38 member countries committed to market-based economies and democratic governance. OECD nations represent the majority of global GDP and are the source of most standardized economic data on taxation, education, trade, and development.",
        "founded": 1961,
        "hq": "Paris, France",
        "website": "https://www.oecd.org",
        "field": "is_oecd",
        "emoji": "📊",
        "keywords": ["OECD countries GDP", "OECD economic data", "developed economies", "OECD indicators"],
    },
    "commonwealth": {
        "name": "Commonwealth",
        "full_name": "Commonwealth of Nations",
        "description": "The Commonwealth of Nations is a political association of 56 member states, mostly former territories of the British Empire. Members span every inhabited continent and represent about 2.5 billion people, roughly a third of the world's population.",
        "founded": 1949,
        "hq": "London, United Kingdom",
        "website": "https://thecommonwealth.org",
        "field": "is_commonwealth",
        "emoji": "🏛️",
        "keywords": ["Commonwealth countries GDP", "Commonwealth nations economy", "Commonwealth trade", "former British Empire economies"],
    },
}

FIELD_MAP = {meta["field"]: slug for slug, meta in GROUP_META.items()}


def _get_bool_col(country: Country, field: str) -> bool:
    return bool(getattr(country, field, False))


@router.get("")
@limiter.limit("60/minute")
def list_groups(request: Request) -> list[dict]:
    return [
        {
            "slug": slug,
            "name": meta["name"],
            "full_name": meta["full_name"],
            "emoji": meta["emoji"],
            "founded": meta["founded"],
            "hq": meta["hq"],
        }
        for slug, meta in GROUP_META.items()
    ]


@router.get("/{slug}")
@limiter.limit("120/minute")
def get_group(request: Request, slug: str, db: Session = Depends(get_db)) -> dict:
    meta = GROUP_META.get(slug.lower())
    if not meta:
        raise HTTPException(status_code=404, detail="Group not found")

    cache_key = f"api:group:{slug.lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    field = meta["field"]

    # Fetch all member countries
    members_raw = db.execute(
        select(Country).where(getattr(Country, field) == True).order_by(Country.name)
    ).scalars().all()

    if not members_raw:
        raise HTTPException(status_code=404, detail="No members found")

    member_ids = [c.id for c in members_raw]

    # Latest indicators for all members
    indicators_raw = db.execute(
        select(CountryIndicator)
        .where(CountryIndicator.country_id.in_(member_ids))
        .order_by(CountryIndicator.country_id, CountryIndicator.indicator, CountryIndicator.period_date.desc())
    ).scalars().all()

    # Deduplicate — keep latest per country+indicator
    ind_map: dict[int, dict[str, float]] = {}
    for row in indicators_raw:
        cid = row.country_id
        if cid not in ind_map:
            ind_map[cid] = {}
        if row.indicator not in ind_map[cid]:
            ind_map[cid][row.indicator] = row.value

    # Build member list
    members = []
    for c in members_raw:
        ind = ind_map.get(c.id, {})
        members.append({
            "code": c.code,
            "name": c.name,
            "flag": c.flag_emoji,
            "slug": c.slug,
            "region": c.region,
            "income_level": c.income_level,
            "gdp_usd": ind.get("gdp_usd"),
            "gdp_growth_pct": ind.get("gdp_growth_pct"),
            "gdp_per_capita_usd": ind.get("gdp_per_capita_usd"),
            "inflation_pct": ind.get("inflation_pct"),
            "unemployment_pct": ind.get("unemployment_pct"),
            "government_debt_gdp_pct": ind.get("government_debt_gdp_pct"),
            "credit_rating_sp": c.credit_rating_sp,
            "credit_rating_moodys": c.credit_rating_moodys,
        })

    # Sort by GDP descending
    members.sort(key=lambda m: m["gdp_usd"] or 0, reverse=True)

    # Aggregate stats
    gdp_values = [m["gdp_usd"] for m in members if m["gdp_usd"]]
    growth_values = [m["gdp_growth_pct"] for m in members if m["gdp_growth_pct"] is not None]
    inflation_values = [m["inflation_pct"] for m in members if m["inflation_pct"] is not None]
    unemp_values = [m["unemployment_pct"] for m in members if m["unemployment_pct"] is not None]

    total_gdp = sum(gdp_values) if gdp_values else None
    avg_growth = round(sum(growth_values) / len(growth_values), 2) if growth_values else None
    avg_inflation = round(sum(inflation_values) / len(inflation_values), 2) if inflation_values else None
    avg_unemployment = round(sum(unemp_values) / len(unemp_values), 2) if unemp_values else None

    # GDP-weighted average growth (more accurate)
    if gdp_values and growth_values:
        weighted_growth_num = sum(
            m["gdp_growth_pct"] * m["gdp_usd"]
            for m in members
            if m["gdp_growth_pct"] is not None and m["gdp_usd"]
        )
        weighted_gdp_denom = sum(m["gdp_usd"] for m in members if m["gdp_growth_pct"] is not None and m["gdp_usd"])
        if weighted_gdp_denom:
            avg_growth = round(weighted_growth_num / weighted_gdp_denom, 2)

    # Top stocks exposed to member countries
    rev_rows = db.execute(
        select(StockCountryRevenue, Asset, Country)
        .join(Asset, StockCountryRevenue.asset_id == Asset.id)
        .join(Country, StockCountryRevenue.country_id == Country.id)
        .where(StockCountryRevenue.country_id.in_(member_ids))
        .where(Asset.asset_type == AssetType.stock)
        .where(Asset.market_cap_usd.isnot(None))
        .order_by(StockCountryRevenue.fiscal_year.desc(), StockCountryRevenue.revenue_pct.desc())
    ).all()

    # Aggregate exposure per stock across all member countries
    stock_exposure: dict[int, dict] = {}
    for rev, asset, country in rev_rows:
        if asset.id not in stock_exposure:
            stock_exposure[asset.id] = {
                "symbol": asset.symbol,
                "name": asset.name,
                "sector": asset.sector,
                "market_cap_usd": asset.market_cap_usd,
                "total_exposure_pct": 0.0,
                "country_count": 0,
                "top_country": None,
                "top_country_pct": 0.0,
            }
        entry = stock_exposure[asset.id]
        entry["total_exposure_pct"] = round(entry["total_exposure_pct"] + rev.revenue_pct, 1)
        entry["country_count"] += 1
        if rev.revenue_pct > entry["top_country_pct"]:
            entry["top_country_pct"] = rev.revenue_pct
            entry["top_country"] = {"code": country.code, "name": country.name, "flag": country.flag_emoji}

    exposed_stocks = sorted(
        stock_exposure.values(),
        key=lambda s: s["total_exposure_pct"],
        reverse=True,
    )[:20]

    result = {
        "slug": slug.lower(),
        "name": meta["name"],
        "full_name": meta["full_name"],
        "description": meta["description"],
        "founded": meta["founded"],
        "hq": meta["hq"],
        "website": meta["website"],
        "emoji": meta["emoji"],
        "keywords": meta["keywords"],
        "member_count": len(members),
        "members": members,
        "stats": {
            "total_gdp_usd": total_gdp,
            "avg_gdp_growth_pct": avg_growth,
            "avg_inflation_pct": avg_inflation,
            "avg_unemployment_pct": avg_unemployment,
        },
        "exposed_stocks": exposed_stocks,
    }

    cache_set(cache_key, result, ttl_seconds=3600)
    return result
