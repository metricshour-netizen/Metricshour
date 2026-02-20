"""
Seed geographic revenue breakdown for top stocks.
Data: FY2023 annual reports (10-K filings) — approximate figures.
Source: SEC EDGAR, company IR pages.
Idempotent — safe to re-run.

Run: python seed.py --only edgar
"""

import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Asset, AssetType, Country, StockCountryRevenue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# FY2023 geographic revenue data from SEC 10-K filings.
# Format: {ticker: {fiscal_year, total_revenue_usd, segments: [(country_code, revenue_pct)]}}
# Percentages represent share of total disclosed geographic revenue.
# Multi-country segments (e.g. "Americas", "Europe") are split by dominant markets.

EDGAR_DATA: dict[str, dict] = {
    "AAPL": {  # FY2023 total: $383.3B | Segments: Americas, Europe, Greater China, Japan, Rest of APAC
        "fiscal_year": 2023,
        "total_revenue_usd": 383_285_000_000,
        "segments": [
            ("US", 38.1),  # Americas (42.3%) — ~90% US
            ("CA",  2.1),  # Americas rest
            ("MX",  1.3),  # Americas rest
            ("BR",  0.8),  # Americas rest
            ("CN", 18.9),  # Greater China
            ("JP",  6.3),  # Japan
            ("DE",  4.9),  # Europe (24.6%) — split 4 ways approx
            ("GB",  4.9),  # Europe
            ("FR",  3.7),  # Europe
            ("IT",  2.5),  # Europe
            ("NL",  2.5),  # Europe
            ("ES",  2.5),  # Europe
            ("KR",  3.1),  # Rest of APAC (7.8%) — KR/AU/IN
            ("AU",  2.3),
            ("IN",  1.6),
            ("SG",  0.8),
        ],
    },
    "MSFT": {  # FY2024 total: $245.1B | Segments: US, Other countries (50/50 approx)
        "fiscal_year": 2024,
        "total_revenue_usd": 245_122_000_000,
        "segments": [
            ("US", 52.0),
            ("DE",  5.5),
            ("JP",  4.5),
            ("GB",  4.5),
            ("FR",  3.0),
            ("CN",  3.0),
            ("CA",  2.5),
            ("AU",  2.0),
            ("IN",  2.0),
            ("KR",  1.5),
            ("IT",  1.5),
            ("BR",  1.5),
            ("NL",  1.5),
            ("SE",  1.0),
            ("SG",  1.0),
        ],
    },
    "NVDA": {  # FY2024 total: $60.9B | Segments: US, Taiwan, China, Singapore, Other
        "fiscal_year": 2024,
        "total_revenue_usd": 60_922_000_000,
        "segments": [
            ("US", 44.0),
            ("TW", 19.0),
            ("SG", 16.0),
            ("CN", 17.0),  # includes Hong Kong
            ("KR",  2.0),
            ("DE",  0.8),
            ("JP",  0.8),
            ("IN",  0.4),
        ],
    },
    "GOOGL": {  # FY2023 total: $307.4B | Segments: US, EMEA, APAC, Other Americas
        "fiscal_year": 2023,
        "total_revenue_usd": 307_394_000_000,
        "segments": [
            ("US", 47.0),
            ("GB",  7.0),  # EMEA (30%) — UK is Alphabet's largest European market
            ("DE",  5.5),
            ("FR",  4.0),
            ("NL",  3.5),
            ("JP",  5.0),  # APAC (14%)
            ("KR",  3.0),
            ("AU",  2.5),
            ("IN",  2.0),
            ("SG",  1.5),
            ("CA",  4.0),  # Other Americas (9%)
            ("BR",  2.5),
            ("MX",  1.5),
            ("AR",  1.0),
        ],
    },
    "META": {  # FY2023 total: $134.9B | Segments: US&Canada, Europe, APAC, Rest of World
        "fiscal_year": 2023,
        "total_revenue_usd": 134_902_000_000,
        "segments": [
            ("US", 41.0),  # US&Canada (44%)
            ("CA",  3.0),
            ("DE",  5.0),  # Europe (27%)
            ("GB",  5.0),
            ("FR",  4.0),
            ("IT",  3.0),
            ("NL",  2.5),
            ("ES",  2.5),
            ("JP",  4.0),  # APAC (20%)
            ("KR",  3.0),
            ("AU",  2.5),
            ("IN",  3.5),
            ("ID",  3.0),
            ("BR",  4.0),  # Rest of World (9%)
            ("MX",  2.0),
            ("TR",  1.5),
            ("SA",  0.5),
        ],
    },
    "AMZN": {  # FY2023 total: $574.8B | Segments: US, Germany, UK, Japan, Rest of World
        "fiscal_year": 2023,
        "total_revenue_usd": 574_785_000_000,
        "segments": [
            ("US", 69.0),
            ("DE",  7.0),
            ("GB",  6.0),
            ("JP",  5.0),
            ("CA",  2.5),
            ("FR",  2.0),
            ("IT",  1.5),
            ("AU",  1.5),
            ("IN",  1.5),
            ("BR",  1.0),
            ("MX",  1.0),
            ("ES",  0.8),
            ("NL",  0.7),
            ("SE",  0.5),
            ("PL",  0.5),
            ("SG",  0.5),
        ],
    },
    "TSLA": {  # FY2023 total: $96.8B | Segments: US, China, Other
        "fiscal_year": 2023,
        "total_revenue_usd": 96_773_000_000,
        "segments": [
            ("US", 50.0),
            ("CN", 22.0),
            ("DE",  5.0),
            ("NO",  3.0),
            ("AU",  2.5),
            ("GB",  2.5),
            ("NL",  2.0),
            ("FR",  2.0),
            ("CA",  2.0),
            ("KR",  1.5),
            ("JP",  1.5),
            ("AT",  1.0),
            ("CH",  1.0),
            ("SE",  1.0),
        ],
    },
    "JPM": {  # FY2023 total: $162.4B | Primarily US, significant international
        "fiscal_year": 2023,
        "total_revenue_usd": 162_415_000_000,
        "segments": [
            ("US", 65.0),
            ("GB",  8.0),
            ("DE",  4.0),
            ("JP",  3.5),
            ("CN",  3.0),
            ("FR",  2.5),
            ("IN",  2.0),
            ("SG",  2.0),
            ("AU",  1.5),
            ("CA",  1.5),
            ("BR",  1.5),
            ("HK",  1.5),
            ("CH",  1.0),
            ("MX",  1.0),
            ("AE",  1.0),
        ],
    },
    "V": {  # FY2023 total: $32.7B | US, International
        "fiscal_year": 2023,
        "total_revenue_usd": 32_653_000_000,
        "segments": [
            ("US", 44.0),
            ("GB",  5.0),
            ("DE",  4.5),
            ("AU",  4.0),
            ("CA",  4.0),
            ("BR",  4.0),
            ("FR",  3.5),
            ("MX",  3.0),
            ("JP",  3.0),
            ("RU",  0.0),  # exited Russia
            ("CN",  2.5),
            ("KR",  2.0),
            ("IT",  2.0),
            ("IN",  2.0),
            ("SG",  1.5),
            ("AR",  1.5),
            ("ES",  1.5),
            ("TR",  1.0),
            ("ZA",  1.0),
            ("ID",  1.0),
            ("SA",  1.0),
        ],
    },
    "WMT": {  # FY2024 total: $648.1B | US, Mexico (Walmex), Other International
        "fiscal_year": 2024,
        "total_revenue_usd": 648_125_000_000,
        "segments": [
            ("US", 83.0),
            ("MX",  6.0),
            ("CN",  3.5),
            ("CA",  2.5),
            ("GB",  0.0),  # Asda sold 2021
            ("IN",  1.0),
            ("JP",  0.0),  # Seiyu sold 2021
            ("BR",  1.0),
            ("CL",  0.8),
            ("AR",  0.7),
            ("CR",  0.5),
            ("GT",  0.5),
            ("HN",  0.5),
        ],
    },
    "NFLX": {  # FY2023 total: $33.7B | US&Canada, Europe, LATAM, APAC
        "fiscal_year": 2023,
        "total_revenue_usd": 33_723_000_000,
        "segments": [
            ("US", 38.0),  # US&Canada (42%)
            ("CA",  4.0),
            ("GB",  6.5),  # Europe (31%)
            ("DE",  5.0),
            ("FR",  4.5),
            ("IT",  3.0),
            ("ES",  2.5),
            ("NL",  2.0),
            ("BR",  5.0),  # LATAM (15%)
            ("MX",  4.0),
            ("AR",  2.5),
            ("CO",  1.5),
            ("JP",  4.0),  # APAC (12%)
            ("KR",  3.0),
            ("AU",  2.5),
            ("IN",  1.5),
        ],
    },
    "XOM": {  # FY2023 total: $398.7B | US, International
        "fiscal_year": 2023,
        "total_revenue_usd": 398_675_000_000,
        "segments": [
            ("US", 47.0),
            ("GB",  6.0),
            ("AU",  5.0),
            ("CA",  5.0),
            ("SG",  4.0),
            ("DE",  3.5),
            ("BE",  3.0),
            ("NL",  3.0),
            ("FR",  2.5),
            ("MY",  2.0),
            ("NG",  2.0),
            ("QA",  2.0),
            ("ID",  1.5),
            ("NO",  1.5),
            ("AO",  1.5),
            ("TZ",  1.0),
            ("MZ",  1.0),
        ],
    },
    "MCD": {  # FY2023 total: $25.8B | US, International Operated, International Developmental
        "fiscal_year": 2023,
        "total_revenue_usd": 25_760_000_000,
        "segments": [
            ("US", 42.0),
            ("FR",  7.5),  # International Operated Markets (IOM)
            ("DE",  7.0),
            ("AU",  6.0),
            ("GB",  5.0),
            ("CA",  5.0),
            ("IT",  3.5),
            ("ES",  3.0),
            ("JP",  4.0),
            ("CN",  3.0),
            ("BR",  2.5),
            ("KR",  2.0),
            ("RU",  0.0),  # exited Russia
            ("MX",  1.5),
            ("SA",  1.0),
            ("AR",  0.5),
        ],
    },
    "PG": {  # FY2023 total: $82.0B | North America, Europe, Asia Pacific, Greater China, etc.
        "fiscal_year": 2023,
        "total_revenue_usd": 82_006_000_000,
        "segments": [
            ("US", 43.0),  # North America
            ("CA",  4.0),
            ("MX",  3.0),
            ("DE",  4.5),  # Europe
            ("GB",  3.5),
            ("FR",  3.0),
            ("IT",  2.0),
            ("RU",  1.5),
            ("TR",  1.5),
            ("CN", 10.0),  # Greater China
            ("JP",  4.5),  # Asia Pacific
            ("IN",  3.0),
            ("AU",  2.0),
            ("KR",  1.5),
            ("ID",  1.5),
            ("SA",  1.5),  # Middle East & Africa
            ("ZA",  1.0),
            ("EG",  0.5),
        ],
    },
    "KO": {  # FY2023 total: $45.8B | North America, EMEA, APAC, Latin America
        "fiscal_year": 2023,
        "total_revenue_usd": 45_754_000_000,
        "segments": [
            ("US", 38.0),
            ("CA",  3.0),
            ("MX",  4.0),  # Latin America
            ("BR",  3.5),
            ("AR",  1.5),
            ("CO",  1.0),
            ("DE",  4.0),  # EMEA
            ("GB",  3.0),
            ("FR",  2.5),
            ("ZA",  2.0),
            ("TR",  1.5),
            ("RU",  0.0),
            ("SA",  1.0),
            ("JP",  4.5),  # APAC
            ("CN",  4.0),
            ("IN",  3.0),
            ("AU",  2.5),
            ("KR",  2.0),
            ("ID",  2.0),
            ("PH",  1.5),
            ("TH",  1.5),
        ],
    },
    "NVO": {  # FY2023 total: $33.7B (DKK converted) | US dominant, International
        "fiscal_year": 2023,
        "total_revenue_usd": 33_734_000_000,
        "segments": [
            ("US", 62.0),
            ("CN",  8.0),
            ("DE",  4.0),
            ("GB",  3.0),
            ("FR",  2.5),
            ("JP",  2.5),
            ("CA",  2.0),
            ("AU",  1.5),
            ("IT",  1.5),
            ("BR",  1.5),
            ("IN",  1.5),
            ("SA",  1.0),
            ("KR",  1.0),
            ("DK",  0.8),
            ("SE",  0.7),
        ],
    },
    "ASML": {  # FY2023 total: $27.6B (EUR converted) | TW, KR, CN dominant
        "fiscal_year": 2023,
        "total_revenue_usd": 27_632_000_000,
        "segments": [
            ("TW", 39.0),
            ("KR", 30.0),
            ("CN", 10.0),
            ("US", 14.0),
            ("JP",  5.0),
            ("DE",  1.0),
            ("NL",  0.5),
            ("SG",  0.5),
        ],
    },
    "TSM": {  # FY2023 total: $69.3B | Americas, APAC, EMEA, China, Japan
        "fiscal_year": 2023,
        "total_revenue_usd": 69_283_000_000,
        "segments": [
            ("US", 68.0),  # Americas — NVIDIA, Apple, AMD, Qualcomm all bill through US
            ("JP",  8.0),
            ("KR",  7.0),
            ("CN",  5.0),
            ("DE",  3.0),
            ("GB",  2.0),
            ("SG",  2.0),
            ("NL",  2.0),
            ("TW",  2.0),
            ("FR",  1.0),
        ],
    },
    "SHEL": {  # FY2023 total: $386B | Europe, Americas, Asia-Pacific/MEA
        "fiscal_year": 2023,
        "total_revenue_usd": 386_201_000_000,
        "segments": [
            ("GB", 22.0),
            ("NL", 17.0),
            ("US", 22.0),
            ("AU",  6.0),
            ("NG",  4.0),
            ("QA",  4.0),
            ("SG",  4.0),
            ("DE",  3.0),
            ("MY",  2.5),
            ("CN",  2.5),
            ("BR",  2.0),
            ("CA",  2.0),
            ("NO",  1.5),
            ("KZ",  1.5),
            ("AE",  1.0),
            ("EG",  1.0),
            ("TZ",  0.5),
            ("GA",  0.5),
        ],
    },
    "TM": {  # FY2023 total: $274.5B (JPY converted) | Japan, North America, Europe, Asia
        "fiscal_year": 2023,
        "total_revenue_usd": 274_491_000_000,
        "segments": [
            ("JP", 18.0),
            ("US", 28.0),  # North America
            ("CA",  3.5),
            ("MX",  2.5),
            ("DE",  5.0),  # Europe
            ("GB",  3.0),
            ("FR",  2.5),
            ("IT",  1.5),
            ("PL",  1.5),
            ("CN",  9.0),  # Asia
            ("IN",  3.0),
            ("AU",  2.5),
            ("ID",  2.0),
            ("TH",  2.5),
            ("MY",  1.5),
            ("SA",  1.5),  # Middle East & Africa
            ("ZA",  1.0),
            ("AE",  1.0),
            ("AR",  0.5),
            ("BR",  3.5),
            ("TR",  1.0),
        ],
    },
    "BABA": {  # FY2024 total: $130.4B | China dominant, international growing
        "fiscal_year": 2024,
        "total_revenue_usd": 130_352_000_000,
        "segments": [
            ("CN", 88.0),
            ("US",  2.5),
            ("GB",  1.0),
            ("DE",  0.8),
            ("AU",  0.8),
            ("KR",  0.8),
            ("JP",  0.8),
            ("SG",  0.8),
            ("IN",  0.5),
            ("ID",  0.5),
            ("MY",  0.5),
            ("BR",  0.5),
            ("AE",  0.5),
            ("FR",  0.5),
            ("CA",  0.5),
            ("IT",  0.3),
        ],
    },
    "SAP": {  # FY2023 total: $33.6B (EUR converted) | EMEA, Americas, APJ
        "fiscal_year": 2023,
        "total_revenue_usd": 33_573_000_000,
        "segments": [
            ("DE", 20.0),
            ("US", 28.0),
            ("GB",  5.0),
            ("FR",  4.0),
            ("JP",  4.0),
            ("AU",  3.0),
            ("CA",  3.0),
            ("BR",  3.0),
            ("CN",  3.0),
            ("IN",  3.0),
            ("CH",  2.5),
            ("IT",  2.0),
            ("MX",  2.0),
            ("KR",  2.0),
            ("NL",  2.0),
            ("SG",  1.5),
            ("AT",  1.0),
            ("SE",  1.0),
            ("ZA",  1.0),
            ("SA",  0.5),
            ("AE",  0.5),
        ],
    },
    "LLY": {  # FY2023 total: $34.1B | US dominant, international
        "fiscal_year": 2023,
        "total_revenue_usd": 34_124_000_000,
        "segments": [
            ("US", 73.0),
            ("DE",  3.5),
            ("JP",  3.0),
            ("FR",  2.5),
            ("GB",  2.5),
            ("CN",  2.5),
            ("IT",  2.0),
            ("CA",  1.5),
            ("ES",  1.5),
            ("AU",  1.0),
            ("BR",  1.0),
            ("KR",  0.8),
            ("MX",  0.7),
            ("AR",  0.5),
            ("SA",  0.5),
        ],
    },
    "INFY": {  # FY2024 total: $18.6B | North America dominant, Europe, RoW
        "fiscal_year": 2024,
        "total_revenue_usd": 18_562_000_000,
        "segments": [
            ("US", 60.0),
            ("CA",  5.0),
            ("GB",  9.0),
            ("DE",  5.0),
            ("FR",  3.5),
            ("AU",  3.5),
            ("NL",  2.0),
            ("IN",  3.0),
            ("SA",  1.5),
            ("JP",  2.0),
            ("SG",  1.5),
            ("AE",  1.0),
            ("CH",  1.0),
            ("SE",  0.5),
            ("FI",  0.5),
        ],
    },
}


def seed_edgar(db: Session) -> int:
    # Load all country codes → ids
    country_rows = db.execute(select(Country.id, Country.code)).all()
    country_map: dict[str, int] = {row.code: row.id for row in country_rows}

    # Load all stock assets → id
    asset_rows = db.execute(
        select(Asset.id, Asset.symbol)
        .where(Asset.asset_type == AssetType.stock, Asset.is_active == True)
    ).all()
    asset_map: dict[str, int] = {row.symbol: row.id for row in asset_rows}

    records: list[dict] = []

    for ticker, data in EDGAR_DATA.items():
        asset_id = asset_map.get(ticker)
        if not asset_id:
            log.warning(f"Skipping {ticker}: not found in assets table")
            continue

        fiscal_year = data["fiscal_year"]
        total_rev = data["total_revenue_usd"]

        for country_code, revenue_pct in data["segments"]:
            country_id = country_map.get(country_code)
            if not country_id:
                log.warning(f"  {ticker}: country {country_code} not found, skipping")
                continue
            if revenue_pct <= 0:
                continue

            records.append({
                "asset_id": asset_id,
                "country_id": country_id,
                "revenue_pct": revenue_pct,
                "revenue_usd": round(total_rev * (revenue_pct / 100)),
                "fiscal_year": fiscal_year,
                "fiscal_quarter": None,
            })

    if not records:
        log.warning("No EDGAR records to insert")
        return 0

    stmt = pg_insert(StockCountryRevenue).values(records)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_stock_country_revenue",
        set_={
            "revenue_pct": stmt.excluded.revenue_pct,
            "revenue_usd": stmt.excluded.revenue_usd,
        },
    )
    db.execute(stmt)
    db.commit()
    log.info(f"Upserted {len(records)} geo revenue rows for {len(EDGAR_DATA)} stocks")
    return len(records)


def run() -> None:
    db = SessionLocal()
    try:
        total = seed_edgar(db)
        log.info(f"Done. {total} geo revenue rows in database.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
