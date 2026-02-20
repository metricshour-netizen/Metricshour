"""
Seed assets: top ~100 stocks, 20 commodities, 10 crypto, 10 FX pairs.
Hardcoded — no external API required. Idempotent.

Must run AFTER countries seeder (needs country IDs).

Run: python seed.py --only assets
"""

import logging
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Asset, AssetType, Country

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# (symbol, name, exchange, sector, industry, hq_country_code, market_cap_usd)
STOCKS: list[tuple] = [
    # ── US Technology ──────────────────────────────────────────────────────────
    ("AAPL",  "Apple Inc.",                  "NASDAQ", "Technology",             "Consumer Electronics",  "US", 3_300_000_000_000),
    ("MSFT",  "Microsoft Corporation",       "NASDAQ", "Technology",             "Software",              "US", 2_900_000_000_000),
    ("NVDA",  "NVIDIA Corporation",          "NASDAQ", "Technology",             "Semiconductors",        "US", 3_000_000_000_000),
    ("GOOGL", "Alphabet Inc.",               "NASDAQ", "Technology",             "Internet Services",     "US", 2_100_000_000_000),
    ("META",  "Meta Platforms Inc.",         "NASDAQ", "Technology",             "Social Media",          "US", 1_600_000_000_000),
    ("AMZN",  "Amazon.com Inc.",             "NASDAQ", "Technology",             "E-Commerce",            "US", 2_200_000_000_000),
    ("TSLA",  "Tesla Inc.",                  "NASDAQ", "Consumer Discretionary", "Electric Vehicles",     "US",   700_000_000_000),
    ("AVGO",  "Broadcom Inc.",               "NASDAQ", "Technology",             "Semiconductors",        "US",   750_000_000_000),
    ("ORCL",  "Oracle Corporation",          "NYSE",   "Technology",             "Software",              "US",   430_000_000_000),
    ("AMD",   "Advanced Micro Devices",      "NASDAQ", "Technology",             "Semiconductors",        "US",   220_000_000_000),
    ("NFLX",  "Netflix Inc.",                "NASDAQ", "Technology",             "Streaming",             "US",   380_000_000_000),
    ("INTC",  "Intel Corporation",           "NASDAQ", "Technology",             "Semiconductors",        "US",   100_000_000_000),
    ("QCOM",  "Qualcomm Inc.",               "NASDAQ", "Technology",             "Semiconductors",        "US",   165_000_000_000),
    ("TXN",   "Texas Instruments",           "NASDAQ", "Technology",             "Semiconductors",        "US",   155_000_000_000),
    ("CSCO",  "Cisco Systems Inc.",          "NASDAQ", "Technology",             "Networking",            "US",   220_000_000_000),
    ("IBM",   "IBM Corporation",             "NYSE",   "Technology",             "IT Services",           "US",   200_000_000_000),
    ("ADBE",  "Adobe Inc.",                  "NASDAQ", "Technology",             "Software",              "US",   200_000_000_000),
    ("CRM",   "Salesforce Inc.",             "NYSE",   "Technology",             "Software",              "US",   280_000_000_000),
    ("AMAT",  "Applied Materials Inc.",      "NASDAQ", "Technology",             "Semiconductor Equipment","US",  180_000_000_000),
    ("MU",    "Micron Technology Inc.",      "NASDAQ", "Technology",             "Semiconductors",        "US",   120_000_000_000),
    # ── US Finance ────────────────────────────────────────────────────────────
    ("JPM",   "JPMorgan Chase & Co.",        "NYSE",   "Financials",             "Banking",               "US",   680_000_000_000),
    ("BAC",   "Bank of America Corp.",       "NYSE",   "Financials",             "Banking",               "US",   320_000_000_000),
    ("V",     "Visa Inc.",                   "NYSE",   "Financials",             "Payments",              "US",   550_000_000_000),
    ("MA",    "Mastercard Inc.",             "NYSE",   "Financials",             "Payments",              "US",   460_000_000_000),
    ("GS",    "Goldman Sachs Group",         "NYSE",   "Financials",             "Investment Banking",    "US",   185_000_000_000),
    ("MS",    "Morgan Stanley",              "NYSE",   "Financials",             "Investment Banking",    "US",   175_000_000_000),
    ("WFC",   "Wells Fargo & Company",       "NYSE",   "Financials",             "Banking",               "US",   210_000_000_000),
    ("AXP",   "American Express Company",    "NYSE",   "Financials",             "Payments",              "US",   180_000_000_000),
    ("BLK",   "BlackRock Inc.",              "NYSE",   "Financials",             "Asset Management",      "US",   150_000_000_000),
    ("C",     "Citigroup Inc.",              "NYSE",   "Financials",             "Banking",               "US",   140_000_000_000),
    # ── US Healthcare ─────────────────────────────────────────────────────────
    ("LLY",   "Eli Lilly and Company",       "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   750_000_000_000),
    ("JNJ",   "Johnson & Johnson",           "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   380_000_000_000),
    ("UNH",   "UnitedHealth Group",          "NYSE",   "Healthcare",             "Health Insurance",      "US",   480_000_000_000),
    ("ABBV",  "AbbVie Inc.",                 "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   310_000_000_000),
    ("MRK",   "Merck & Co. Inc.",            "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   260_000_000_000),
    ("PFE",   "Pfizer Inc.",                 "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   150_000_000_000),
    ("TMO",   "Thermo Fisher Scientific",    "NYSE",   "Healthcare",             "Life Sciences",         "US",   210_000_000_000),
    ("AMGN",  "Amgen Inc.",                  "NASDAQ", "Healthcare",             "Biotechnology",         "US",   155_000_000_000),
    ("BMY",   "Bristol-Myers Squibb",        "NYSE",   "Healthcare",             "Pharmaceuticals",       "US",   130_000_000_000),
    ("GILD",  "Gilead Sciences Inc.",        "NASDAQ", "Healthcare",             "Biotechnology",         "US",   115_000_000_000),
    # ── US Consumer ───────────────────────────────────────────────────────────
    ("WMT",   "Walmart Inc.",                "NYSE",   "Consumer Staples",       "Retail",                "US",   720_000_000_000),
    ("HD",    "The Home Depot Inc.",         "NYSE",   "Consumer Discretionary", "Home Improvement",      "US",   360_000_000_000),
    ("COST",  "Costco Wholesale",            "NASDAQ", "Consumer Staples",       "Retail",                "US",   370_000_000_000),
    ("PG",    "Procter & Gamble Co.",        "NYSE",   "Consumer Staples",       "Household Products",    "US",   350_000_000_000),
    ("KO",    "The Coca-Cola Company",       "NYSE",   "Consumer Staples",       "Beverages",             "US",   270_000_000_000),
    ("PEP",   "PepsiCo Inc.",                "NASDAQ", "Consumer Staples",       "Beverages",             "US",   210_000_000_000),
    ("MCD",   "McDonald's Corporation",      "NYSE",   "Consumer Discretionary", "Restaurants",           "US",   220_000_000_000),
    ("NKE",   "Nike Inc.",                   "NYSE",   "Consumer Discretionary", "Apparel",               "US",    85_000_000_000),
    ("SBUX",  "Starbucks Corporation",       "NASDAQ", "Consumer Discretionary", "Restaurants",           "US",    80_000_000_000),
    ("PM",    "Philip Morris International","NYSE",   "Consumer Staples",       "Tobacco",               "US",   185_000_000_000),
    # ── US Energy ─────────────────────────────────────────────────────────────
    ("XOM",   "ExxonMobil Corporation",      "NYSE",   "Energy",                 "Oil & Gas",             "US",   470_000_000_000),
    ("CVX",   "Chevron Corporation",         "NYSE",   "Energy",                 "Oil & Gas",             "US",   290_000_000_000),
    ("COP",   "ConocoPhillips",              "NYSE",   "Energy",                 "Oil & Gas",             "US",   140_000_000_000),
    ("SLB",   "SLB (Schlumberger)",          "NYSE",   "Energy",                 "Oil Field Services",    "US",    65_000_000_000),
    # ── US Industrials ────────────────────────────────────────────────────────
    ("RTX",   "RTX Corporation",             "NYSE",   "Industrials",            "Defense",               "US",   160_000_000_000),
    ("HON",   "Honeywell International",     "NASDAQ", "Industrials",            "Diversified Industrial","US",   140_000_000_000),
    ("BA",    "Boeing Company",              "NYSE",   "Industrials",            "Aerospace",             "US",   100_000_000_000),
    ("CAT",   "Caterpillar Inc.",            "NYSE",   "Industrials",            "Machinery",             "US",   155_000_000_000),
    ("GE",    "GE Aerospace",               "NYSE",   "Industrials",            "Aerospace",             "US",   180_000_000_000),
    ("UPS",   "United Parcel Service",       "NYSE",   "Industrials",            "Logistics",             "US",   120_000_000_000),
    ("DE",    "Deere & Company",             "NYSE",   "Industrials",            "Agricultural Machinery","US",   120_000_000_000),
    ("LMT",   "Lockheed Martin",             "NYSE",   "Industrials",            "Defense",               "US",   120_000_000_000),
    # ── US Telecom & Media ────────────────────────────────────────────────────
    ("T",     "AT&T Inc.",                   "NYSE",   "Communication Services", "Telecom",               "US",   150_000_000_000),
    ("VZ",    "Verizon Communications",      "NYSE",   "Communication Services", "Telecom",               "US",   170_000_000_000),
    ("DIS",   "The Walt Disney Company",     "NYSE",   "Communication Services", "Media & Entertainment", "US",   200_000_000_000),
    ("CMCSA", "Comcast Corporation",         "NASDAQ", "Communication Services", "Media & Telecom",       "US",   145_000_000_000),
    # ── International — UK ────────────────────────────────────────────────────
    ("SHEL",  "Shell plc",                   "NYSE",   "Energy",                 "Oil & Gas",             "GB",   220_000_000_000),
    ("AZN",   "AstraZeneca plc",             "NASDAQ", "Healthcare",             "Pharmaceuticals",       "GB",   230_000_000_000),
    ("BP",    "BP plc",                      "NYSE",   "Energy",                 "Oil & Gas",             "GB",   100_000_000_000),
    ("GSK",   "GSK plc",                     "NYSE",   "Healthcare",             "Pharmaceuticals",       "GB",    85_000_000_000),
    ("HSBC",  "HSBC Holdings plc",           "NYSE",   "Financials",             "Banking",               "GB",   175_000_000_000),
    ("ARM",   "Arm Holdings plc",            "NASDAQ", "Technology",             "Semiconductor IP",      "GB",   160_000_000_000),
    ("RIO",   "Rio Tinto plc",               "NYSE",   "Materials",              "Mining",                "GB",   100_000_000_000),
    # ── International — Europe ────────────────────────────────────────────────
    ("SAP",   "SAP SE",                      "NYSE",   "Technology",             "Software",              "DE",   260_000_000_000),
    ("TTE",   "TotalEnergies SE",            "NYSE",   "Energy",                 "Oil & Gas",             "FR",   150_000_000_000),
    ("NVO",   "Novo Nordisk A/S",            "NYSE",   "Healthcare",             "Pharmaceuticals",       "DK",   420_000_000_000),
    ("ASML",  "ASML Holding N.V.",           "NASDAQ", "Technology",             "Semiconductor Equipment","NL",  290_000_000_000),
    # ── International — Japan ─────────────────────────────────────────────────
    ("TM",    "Toyota Motor Corporation",    "NYSE",   "Consumer Discretionary", "Automobiles",           "JP",   220_000_000_000),
    ("SONY",  "Sony Group Corporation",      "NYSE",   "Consumer Discretionary", "Electronics",           "JP",   110_000_000_000),
    # ── International — Taiwan ────────────────────────────────────────────────
    ("TSM",   "Taiwan Semiconductor Mfg.",   "NYSE",   "Technology",             "Semiconductors",        "TW",   750_000_000_000),
    # ── International — China ─────────────────────────────────────────────────
    ("BABA",  "Alibaba Group Holding",       "NYSE",   "Technology",             "E-Commerce",            "CN",   210_000_000_000),
    ("BIDU",  "Baidu Inc.",                  "NASDAQ", "Technology",             "Internet Services",     "CN",    35_000_000_000),
    ("JD",    "JD.com Inc.",                 "NASDAQ", "Technology",             "E-Commerce",            "CN",    45_000_000_000),
    ("PDD",   "PDD Holdings Inc.",           "NASDAQ", "Technology",             "E-Commerce",            "CN",   170_000_000_000),
    # ── International — India ─────────────────────────────────────────────────
    ("INFY",  "Infosys Limited",             "NYSE",   "Technology",             "IT Services",           "IN",    75_000_000_000),
    ("HDB",   "HDFC Bank Limited",           "NYSE",   "Financials",             "Banking",               "IN",   130_000_000_000),
    # ── International — Brazil ────────────────────────────────────────────────
    ("VALE",  "Vale S.A.",                   "NYSE",   "Materials",              "Mining",                "BR",    65_000_000_000),
    ("PBR",   "Petróleo Brasileiro S.A.",    "NYSE",   "Energy",                 "Oil & Gas",             "BR",    80_000_000_000),
    # ── International — Australia ─────────────────────────────────────────────
    ("BHP",   "BHP Group Limited",           "NYSE",   "Materials",              "Mining",                "AU",   120_000_000_000),
    # ── International — South Korea (OTC/ADR) ─────────────────────────────────
    ("SSNLF", "Samsung Electronics",         "OTC",    "Technology",             "Semiconductors",        "KR",   260_000_000_000),
]

# (symbol, name, exchange, category)  — no country, no market cap
COMMODITIES: list[tuple] = [
    # Energy
    ("WTI",      "Crude Oil (WTI)",    "NYMEX", "Energy"),
    ("BRENT",    "Crude Oil (Brent)",  "ICE",   "Energy"),
    ("NG",       "Natural Gas",        "NYMEX", "Energy"),
    ("GASOLINE", "Gasoline",           "NYMEX", "Energy"),
    ("COAL",     "Coal",               "CME",   "Energy"),
    # Metals
    ("XAUUSD",   "Gold",               "COMEX", "Metals"),
    ("XAGUSD",   "Silver",             "COMEX", "Metals"),
    ("XPTUSD",   "Platinum",           "NYMEX", "Metals"),
    ("HG",       "Copper",             "COMEX", "Metals"),
    ("ALI",      "Aluminum",           "LME",   "Metals"),
    ("ZNC",      "Zinc",               "LME",   "Metals"),
    ("NI",       "Nickel",             "LME",   "Metals"),
    # Agriculture
    ("ZW",       "Wheat",              "CBOT",  "Agriculture"),
    ("ZC",       "Corn",               "CBOT",  "Agriculture"),
    ("ZS",       "Soybeans",           "CBOT",  "Agriculture"),
    ("KC",       "Coffee",             "ICE",   "Agriculture"),
    ("SB",       "Sugar",              "ICE",   "Agriculture"),
    ("CT",       "Cotton",             "ICE",   "Agriculture"),
    ("CC",       "Cocoa",              "ICE",   "Agriculture"),
    ("LE",       "Live Cattle",        "CME",   "Agriculture"),
]

# (symbol, name, market_cap_usd)
CRYPTO: list[tuple] = [
    ("BTC",  "Bitcoin",         1_800_000_000_000),
    ("ETH",  "Ethereum",          400_000_000_000),
    ("BNB",  "BNB",                90_000_000_000),
    ("SOL",  "Solana",            100_000_000_000),
    ("XRP",  "XRP",               140_000_000_000),
    ("DOGE", "Dogecoin",           50_000_000_000),
    ("ADA",  "Cardano",            30_000_000_000),
    ("AVAX", "Avalanche",          20_000_000_000),
    ("DOT",  "Polkadot",           12_000_000_000),
    ("LINK", "Chainlink",          20_000_000_000),
]

# (symbol, name, base_currency, quote_currency)
FX: list[tuple] = [
    ("EURUSD", "Euro / US Dollar",         "EUR", "USD"),
    ("GBPUSD", "British Pound / US Dollar","GBP", "USD"),
    ("USDJPY", "US Dollar / Japanese Yen", "USD", "JPY"),
    ("USDCNY", "US Dollar / Chinese Yuan", "USD", "CNY"),
    ("USDCHF", "US Dollar / Swiss Franc",  "USD", "CHF"),
    ("AUDUSD", "Australian Dollar / USD",  "AUD", "USD"),
    ("USDCAD", "US Dollar / Canadian Dollar","USD","CAD"),
    ("USDMXN", "US Dollar / Mexican Peso", "USD", "MXN"),
    ("USDBRL", "US Dollar / Brazilian Real","USD","BRL"),
    ("USDINR", "US Dollar / Indian Rupee", "USD", "INR"),
]


def seed_assets(db: Session) -> int:
    # Build country code → id lookup
    country_rows = db.execute(select(Country.code, Country.id)).all()
    country_map: dict[str, int] = {row.code: row.id for row in country_rows}

    if not country_map:
        log.warning("No countries in DB — run countries seeder first. Skipping country_id linking.")

    rows: list[dict] = []

    for symbol, name, exchange, sector, industry, country_code, market_cap in STOCKS:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.stock,
            "exchange": exchange,
            "currency": "USD",
            "sector": sector,
            "industry": industry,
            "country_id": country_map.get(country_code) if country_code else None,
            "market_cap_usd": market_cap,
            "is_active": True,
        })

    for symbol, name, exchange, _category in COMMODITIES:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.commodity,
            "exchange": exchange,
            "currency": "USD",
            "sector": None,
            "industry": None,
            "country_id": None,
            "market_cap_usd": None,
            "is_active": True,
        })

    for symbol, name, market_cap in CRYPTO:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.crypto,
            "exchange": "CRYPTO",
            "currency": "USD",
            "sector": None,
            "industry": None,
            "country_id": None,
            "market_cap_usd": market_cap,
            "is_active": True,
        })

    for symbol, name, base, quote in FX:
        rows.append({
            "symbol": symbol,
            "name": name,
            "asset_type": AssetType.fx,
            "exchange": "FOREX",
            "currency": quote,
            "sector": None,
            "industry": None,
            "country_id": None,
            "market_cap_usd": None,
            "base_currency": base,
            "quote_currency": quote,
            "is_active": True,
        })

    stmt = insert(Asset).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_asset_symbol_exchange",
        set_={col: stmt.excluded[col] for col in rows[0].keys() if col not in ("symbol", "exchange")},
    )
    db.execute(stmt)
    db.commit()

    log.info(f"Upserted {len(rows)} assets ({len(STOCKS)} stocks, {len(COMMODITIES)} commodities, {len(CRYPTO)} crypto, {len(FX)} FX)")
    return len(rows)


def run() -> None:
    db = SessionLocal()
    try:
        total = seed_assets(db)
        log.info(f"Done. {total} assets in database.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
