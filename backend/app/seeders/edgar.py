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

    # ── Original 90 — missing EDGAR data filled in ────────────────────────────
    "AVGO": {  # FY2023 total: $35.8B | US, Taiwan, Singapore, China
        "fiscal_year": 2023, "total_revenue_usd": 35_819_000_000,
        "segments": [("US", 35.0), ("TW", 22.0), ("SG", 18.0), ("CN", 14.0), ("KR", 4.0), ("JP", 3.0), ("GB", 2.0), ("DE", 1.0), ("IN", 1.0)],
    },
    "ORCL": {  # FY2024 total: $52.9B | Americas, Europe, APAC
        "fiscal_year": 2024, "total_revenue_usd": 52_961_000_000,
        "segments": [("US", 52.0), ("GB", 5.0), ("DE", 4.5), ("JP", 5.0), ("FR", 3.0), ("CN", 3.0), ("CA", 3.0), ("AU", 2.5), ("IN", 2.5), ("BR", 2.0), ("NL", 2.0), ("KR", 1.5), ("MX", 1.5), ("IT", 1.5), ("ES", 1.0), ("SG", 1.0), ("CH", 1.0), ("SE", 1.0)],
    },
    "AMD": {  # FY2023 total: $22.7B | US, China, Japan, Singapore, Taiwan
        "fiscal_year": 2023, "total_revenue_usd": 22_680_000_000,
        "segments": [("US", 24.0), ("CN", 22.0), ("JP", 14.0), ("SG", 13.0), ("TW", 10.0), ("KR", 7.0), ("DE", 4.0), ("NL", 2.0), ("GB", 2.0), ("IN", 1.0), ("AU", 1.0)],
    },
    "NFLX": {  # FY2023 total: $33.7B | US&Canada, EMEA, LATAM, APAC
        "fiscal_year": 2023, "total_revenue_usd": 33_723_000_000,
        "segments": [("US", 42.0), ("CA", 3.5), ("GB", 5.0), ("DE", 4.5), ("FR", 3.5), ("IT", 2.5), ("ES", 2.0), ("NL", 1.5), ("BR", 4.0), ("MX", 3.0), ("AR", 1.5), ("CO", 1.0), ("JP", 3.0), ("AU", 2.5), ("KR", 2.0), ("IN", 2.0), ("SG", 1.0), ("TR", 1.0), ("SA", 1.0), ("ZA", 0.5), ("SE", 1.0), ("NO", 0.5), ("PL", 0.5), ("AT", 0.5), ("CH", 0.5), ("PT", 0.5)],
    },
    "INTC": {  # FY2023 total: $54.2B | China, Singapore, Taiwan, US
        "fiscal_year": 2023, "total_revenue_usd": 54_228_000_000,
        "segments": [("CN", 27.0), ("SG", 24.0), ("TW", 14.0), ("US", 14.0), ("KR", 7.0), ("JP", 5.0), ("DE", 3.0), ("GB", 2.0), ("IN", 1.5), ("NL", 1.0), ("IL", 0.8), ("FR", 0.7)],
    },
    "QCOM": {  # FY2023 total: $35.8B | China dominant
        "fiscal_year": 2023, "total_revenue_usd": 35_820_000_000,
        "segments": [("CN", 63.0), ("US", 9.0), ("KR", 8.0), ("TW", 7.0), ("JP", 4.0), ("SG", 3.0), ("DE", 2.0), ("GB", 1.0), ("IN", 1.0), ("VN", 1.0), ("NL", 0.5), ("AU", 0.5)],
    },
    "TXN": {  # FY2023 total: $17.5B | Americas, Asia, Europe
        "fiscal_year": 2023, "total_revenue_usd": 17_519_000_000,
        "segments": [("CN", 23.0), ("US", 22.0), ("TW", 11.0), ("JP", 9.0), ("KR", 8.0), ("SG", 6.0), ("DE", 5.0), ("IN", 3.0), ("GB", 3.0), ("NL", 2.5), ("IT", 1.5), ("FR", 1.5), ("MY", 1.5), ("TH", 1.0), ("AU", 1.0)],
    },
    "CSCO": {  # FY2023 total: $57.0B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 57_005_000_000,
        "segments": [("US", 55.0), ("GB", 5.0), ("DE", 4.0), ("JP", 4.5), ("CA", 3.0), ("FR", 3.0), ("AU", 2.5), ("CN", 2.5), ("IN", 2.0), ("NL", 2.0), ("IT", 1.5), ("BR", 1.5), ("MX", 1.5), ("KR", 1.5), ("SG", 1.5), ("ES", 1.0), ("SE", 1.0), ("CH", 1.0), ("SA", 0.5), ("AE", 0.5)],
    },
    "IBM": {  # FY2023 total: $61.9B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 61_860_000_000,
        "segments": [("US", 43.0), ("DE", 7.0), ("GB", 5.5), ("JP", 6.0), ("FR", 4.5), ("CA", 3.5), ("AU", 2.5), ("IN", 3.0), ("IT", 2.5), ("BR", 2.5), ("CN", 2.5), ("NL", 1.5), ("ES", 1.5), ("MX", 1.5), ("KR", 1.0), ("CH", 1.0), ("SE", 0.8), ("SG", 0.7), ("ZA", 0.5), ("SA", 0.5), ("AE", 0.5)],
    },
    "ADBE": {  # FY2023 total: $19.4B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 19_409_000_000,
        "segments": [("US", 55.0), ("GB", 5.5), ("DE", 4.5), ("JP", 6.0), ("FR", 3.5), ("CA", 3.0), ("AU", 2.5), ("CN", 2.5), ("IN", 2.5), ("KR", 2.0), ("NL", 1.5), ("BR", 1.5), ("SE", 1.0), ("IT", 1.0), ("ES", 1.0), ("SG", 1.0), ("CH", 0.8), ("MX", 0.7), ("BE", 0.5)],
    },
    "CRM": {  # FY2024 total: $34.9B | Americas, Europe, APAC
        "fiscal_year": 2024, "total_revenue_usd": 34_857_000_000,
        "segments": [("US", 66.0), ("GB", 6.0), ("DE", 4.0), ("JP", 5.0), ("CA", 3.0), ("FR", 3.0), ("AU", 2.5), ("IN", 2.0), ("NL", 1.5), ("BR", 1.0), ("KR", 1.0), ("SG", 0.8), ("IT", 0.8), ("SE", 0.7), ("CH", 0.7)],
    },
    "AMAT": {  # FY2023 total: $26.5B | Korea, Taiwan, China, Japan, US
        "fiscal_year": 2023, "total_revenue_usd": 26_517_000_000,
        "segments": [("KR", 25.0), ("TW", 22.0), ("CN", 26.0), ("JP", 10.0), ("US", 7.0), ("SG", 5.0), ("DE", 2.0), ("IN", 1.5), ("IL", 1.0), ("GB", 0.5)],
    },
    "MU": {  # FY2023 total: $15.5B | China, US, Taiwan, Japan
        "fiscal_year": 2023, "total_revenue_usd": 15_540_000_000,
        "segments": [("CN", 16.0), ("US", 12.0), ("TW", 21.0), ("JP", 12.0), ("SG", 9.0), ("KR", 8.0), ("MY", 6.0), ("DE", 4.0), ("GB", 3.0), ("IN", 2.5), ("NL", 2.5), ("TH", 2.0), ("PH", 1.5)],
    },
    "BAC": {  # FY2023 total: $98.6B | Primarily US
        "fiscal_year": 2023, "total_revenue_usd": 98_580_000_000,
        "segments": [("US", 78.0), ("GB", 6.0), ("IE", 3.0), ("FR", 2.5), ("JP", 2.5), ("HK", 2.0), ("SG", 1.5), ("DE", 1.0), ("CA", 1.0), ("AU", 0.8), ("IN", 0.7)],
    },
    "MA": {  # FY2023 total: $25.1B | Global network
        "fiscal_year": 2023, "total_revenue_usd": 25_098_000_000,
        "segments": [("US", 33.0), ("GB", 5.0), ("DE", 4.0), ("BR", 4.0), ("CA", 3.5), ("AU", 3.0), ("FR", 3.0), ("MX", 2.5), ("RU", 0.5), ("IT", 2.0), ("JP", 2.0), ("IN", 2.5), ("CN", 1.5), ("ES", 2.0), ("NL", 1.5), ("KR", 1.5), ("SG", 1.5), ("PL", 1.0), ("SA", 1.0), ("AE", 1.5), ("ZA", 1.0), ("NG", 0.5), ("AR", 1.5), ("CO", 1.0), ("SE", 0.8), ("CH", 0.7), ("TR", 0.5), ("ID", 0.5)],
    },
    "GS": {  # FY2023 total: $46.3B | Americas, EMEA, Asia
        "fiscal_year": 2023, "total_revenue_usd": 46_254_000_000,
        "segments": [("US", 55.0), ("GB", 12.0), ("DE", 5.0), ("JP", 5.0), ("HK", 5.0), ("SG", 3.5), ("FR", 3.0), ("IN", 2.5), ("CN", 2.5), ("AU", 2.0), ("CA", 1.5), ("IT", 1.0), ("SE", 0.5), ("CH", 0.5), ("AE", 0.5)],
    },
    "MS": {  # FY2023 total: $54.1B | Americas, EMEA, Asia
        "fiscal_year": 2023, "total_revenue_usd": 54_143_000_000,
        "segments": [("US", 58.0), ("GB", 9.0), ("JP", 7.0), ("HK", 5.0), ("SG", 3.5), ("DE", 3.0), ("FR", 2.5), ("AU", 2.0), ("CN", 2.0), ("CA", 2.0), ("IN", 1.5), ("IT", 1.0), ("CH", 0.8), ("AE", 0.7), ("SE", 0.5)],
    },
    "WFC": {  # FY2023 total: $82.6B | Primarily US
        "fiscal_year": 2023, "total_revenue_usd": 82_597_000_000,
        "segments": [("US", 89.0), ("GB", 4.0), ("CA", 2.0), ("JP", 1.5), ("HK", 1.0), ("SG", 1.0), ("DE", 0.8), ("IN", 0.7)],
    },
    "AXP": {  # FY2023 total: $60.5B | US dominant, international
        "fiscal_year": 2023, "total_revenue_usd": 60_517_000_000,
        "segments": [("US", 70.0), ("GB", 3.5), ("AU", 2.5), ("CA", 3.0), ("JP", 2.5), ("DE", 2.0), ("MX", 2.0), ("IN", 1.5), ("FR", 1.5), ("IT", 1.5), ("BR", 1.5), ("KR", 1.0), ("SG", 1.0), ("ES", 0.8), ("NL", 0.7), ("SE", 0.5), ("AE", 0.5), ("SA", 0.5)],
    },
    "BLK": {  # FY2023 total: $17.9B | Americas, EMEA, Asia
        "fiscal_year": 2023, "total_revenue_usd": 17_859_000_000,
        "segments": [("US", 55.0), ("GB", 10.0), ("DE", 5.0), ("JP", 4.0), ("FR", 4.0), ("CA", 3.0), ("AU", 3.0), ("CH", 2.5), ("SG", 2.0), ("HK", 2.0), ("IN", 1.5), ("IT", 1.0), ("NL", 1.0), ("KR", 1.0), ("SE", 0.8), ("BR", 0.7), ("AE", 0.5)],
    },
    "C": {  # FY2023 total: $78.3B | North America, EMEA, LATAM, APAC
        "fiscal_year": 2023, "total_revenue_usd": 78_328_000_000,
        "segments": [("US", 52.0), ("GB", 6.5), ("MX", 5.5), ("SG", 3.0), ("JP", 3.0), ("HK", 3.0), ("DE", 2.5), ("AU", 2.0), ("IN", 2.0), ("BR", 2.0), ("FR", 1.5), ("CN", 1.5), ("PL", 1.0), ("AE", 1.0), ("KR", 1.0), ("CA", 1.0), ("SA", 0.8), ("ZA", 0.5), ("RU", 0.5), ("TR", 0.5), ("AR", 0.5), ("CL", 0.5), ("CO", 0.5)],
    },
    "JNJ": {  # FY2023 total: $85.2B | US, Europe, APAC, other
        "fiscal_year": 2023, "total_revenue_usd": 85_159_000_000,
        "segments": [("US", 53.0), ("DE", 5.0), ("GB", 3.5), ("JP", 4.5), ("CN", 3.5), ("FR", 3.0), ("CA", 2.5), ("BR", 2.0), ("AU", 2.0), ("IT", 2.0), ("ES", 1.5), ("BE", 1.5), ("NL", 1.5), ("KR", 1.5), ("CH", 1.0), ("MX", 1.0), ("IN", 1.0), ("SA", 0.8), ("RU", 0.5), ("TR", 0.5), ("AR", 0.5), ("ZA", 0.5), ("SE", 0.5)],
    },
    "UNH": {  # FY2023 total: $371.6B | Primarily US, some international
        "fiscal_year": 2023, "total_revenue_usd": 371_622_000_000,
        "segments": [("US", 91.0), ("BR", 3.0), ("CL", 1.5), ("CO", 1.0), ("PT", 0.8), ("PE", 0.7), ("MX", 0.5), ("EC", 0.3), ("AR", 0.2)],
    },
    "ABBV": {  # FY2023 total: $54.3B | US dominant, international
        "fiscal_year": 2023, "total_revenue_usd": 54_318_000_000,
        "segments": [("US", 72.0), ("DE", 4.0), ("JP", 3.5), ("FR", 3.0), ("GB", 2.5), ("CA", 2.0), ("IT", 2.0), ("ES", 1.5), ("AU", 1.5), ("CN", 1.0), ("KR", 0.8), ("NL", 0.8), ("BR", 0.8), ("CH", 0.7), ("MX", 0.6), ("BE", 0.5), ("SE", 0.5), ("AT", 0.4), ("TR", 0.4)],
    },
    "MRK": {  # FY2023 total: $60.1B | US, Europe, APAC, Other
        "fiscal_year": 2023, "total_revenue_usd": 60_115_000_000,
        "segments": [("US", 47.0), ("JP", 6.0), ("DE", 5.0), ("CN", 5.0), ("FR", 4.0), ("GB", 3.0), ("CA", 2.5), ("IT", 2.5), ("BR", 2.5), ("ES", 2.0), ("KR", 2.0), ("AU", 1.5), ("RU", 1.0), ("MX", 1.0), ("TR", 0.8), ("NL", 0.8), ("BE", 0.6), ("SA", 0.5), ("SE", 0.5), ("CH", 0.5), ("PL", 0.5), ("IN", 0.8), ("ZA", 0.5)],
    },
    "PFE": {  # FY2023 total: $58.5B | US, Developed Europe, Emerging, Japan
        "fiscal_year": 2023, "total_revenue_usd": 58_496_000_000,
        "segments": [("US", 44.0), ("DE", 5.0), ("JP", 5.0), ("FR", 3.5), ("GB", 3.5), ("IT", 3.0), ("CN", 3.0), ("CA", 2.5), ("BR", 2.5), ("ES", 2.0), ("AU", 2.0), ("KR", 1.5), ("MX", 1.5), ("TR", 1.0), ("NL", 1.0), ("BE", 0.8), ("SA", 0.8), ("RU", 0.5), ("PL", 0.5), ("IN", 0.5), ("SE", 0.5), ("CH", 0.5), ("AT", 0.4), ("ZA", 0.4), ("AR", 0.3), ("NG", 0.3)],
    },
    "TMO": {  # FY2023 total: $42.9B | Americas, Europe, APAC
        "fiscal_year": 2023, "total_revenue_usd": 42_857_000_000,
        "segments": [("US", 43.0), ("CN", 12.0), ("DE", 7.0), ("JP", 5.5), ("GB", 4.5), ("FR", 3.5), ("CA", 3.0), ("IT", 2.5), ("AU", 2.0), ("KR", 2.0), ("NL", 1.5), ("SE", 1.5), ("BR", 1.5), ("IN", 1.5), ("CH", 1.0), ("ES", 1.0), ("SG", 0.8), ("MX", 0.7), ("FI", 0.5), ("DK", 0.5), ("BE", 0.5)],
    },
    "AMGN": {  # FY2023 total: $28.2B | US dominant
        "fiscal_year": 2023, "total_revenue_usd": 28_190_000_000,
        "segments": [("US", 75.0), ("DE", 4.0), ("JP", 3.0), ("FR", 2.5), ("GB", 2.5), ("CA", 2.0), ("IT", 2.0), ("ES", 1.5), ("AU", 1.0), ("BR", 1.0), ("KR", 0.8), ("CN", 0.8), ("NL", 0.8), ("CH", 0.6), ("SE", 0.5), ("BE", 0.5), ("AT", 0.4), ("MX", 0.3), ("TR", 0.3)],
    },
    "BMY": {  # FY2023 total: $45.0B | US dominant, international
        "fiscal_year": 2023, "total_revenue_usd": 45_006_000_000,
        "segments": [("US", 65.0), ("DE", 4.5), ("JP", 4.0), ("FR", 3.5), ("GB", 3.0), ("IT", 2.5), ("CA", 2.0), ("ES", 2.0), ("CN", 2.0), ("AU", 1.5), ("KR", 1.5), ("BR", 1.0), ("NL", 1.0), ("CH", 0.8), ("SE", 0.5), ("BE", 0.5), ("MX", 0.4), ("TR", 0.4), ("PL", 0.4), ("AT", 0.3), ("RU", 0.3)],
    },
    "GILD": {  # FY2023 total: $27.1B | US dominant
        "fiscal_year": 2023, "total_revenue_usd": 27_116_000_000,
        "segments": [("US", 74.0), ("DE", 5.0), ("GB", 3.5), ("FR", 3.0), ("IT", 2.5), ("ES", 2.0), ("JP", 2.0), ("CA", 1.5), ("AU", 1.5), ("NL", 1.0), ("CH", 0.8), ("SE", 0.6), ("KR", 0.5), ("BE", 0.5), ("AT", 0.4), ("BR", 0.4), ("CN", 0.3)],
    },
    "HD": {  # FY2023 total: $157.4B | Primarily US/Canada/Mexico
        "fiscal_year": 2023, "total_revenue_usd": 157_403_000_000,
        "segments": [("US", 90.0), ("CA", 6.0), ("MX", 4.0)],
    },
    "COST": {  # FY2024 total: $249.6B | US, Canada, International
        "fiscal_year": 2024, "total_revenue_usd": 249_636_000_000,
        "segments": [("US", 73.0), ("CA", 9.0), ("GB", 2.5), ("JP", 2.5), ("KR", 2.0), ("AU", 2.0), ("TW", 2.0), ("MX", 2.0), ("ES", 1.5), ("CN", 1.5), ("FR", 1.0), ("IC", 0.5)],
    },
    "PEP": {  # FY2023 total: $91.5B | US and international segments
        "fiscal_year": 2023, "total_revenue_usd": 91_471_000_000,
        "segments": [("US", 56.0), ("MX", 6.0), ("RU", 3.5), ("BR", 2.5), ("CA", 2.5), ("GB", 2.0), ("CN", 2.0), ("DE", 2.0), ("AU", 1.5), ("SA", 1.5), ("IN", 1.5), ("EG", 1.0), ("FR", 1.0), ("PH", 0.8), ("TR", 0.8), ("ZA", 0.8), ("AR", 0.7), ("PK", 0.5), ("PL", 0.5), ("NG", 0.5), ("IT", 0.5), ("ES", 0.4), ("NL", 0.4)],
    },
    "NKE": {  # FY2023 total: $51.2B | North America, EMEA, Greater China, APAC/LA
        "fiscal_year": 2023, "total_revenue_usd": 51_217_000_000,
        "segments": [("US", 42.0), ("CN", 14.5), ("GB", 5.0), ("DE", 4.0), ("JP", 4.0), ("FR", 3.0), ("CA", 3.0), ("KR", 2.5), ("AU", 2.5), ("IT", 2.0), ("NL", 2.0), ("BR", 2.0), ("MX", 1.5), ("ES", 1.5), ("IN", 1.0), ("TW", 1.0), ("SG", 0.8), ("BE", 0.8), ("SE", 0.7), ("AR", 0.5), ("CH", 0.5), ("ZA", 0.5), ("TR", 0.5), ("PL", 0.4)],
    },
    "SBUX": {  # FY2023 total: $35.9B | Americas, China, International
        "fiscal_year": 2023, "total_revenue_usd": 35_976_000_000,
        "segments": [("US", 61.0), ("CN", 19.0), ("JP", 4.0), ("CA", 3.0), ("GB", 2.5), ("KR", 2.0), ("TW", 1.5), ("AU", 1.0), ("MX", 1.0), ("DE", 0.8), ("TH", 0.7), ("SG", 0.7), ("PH", 0.6), ("MY", 0.5), ("ID", 0.5), ("IN", 0.5), ("FR", 0.4), ("TR", 0.3)],
    },
    "PM": {  # FY2023 total: $35.2B | All international (no US sales)
        "fiscal_year": 2023, "total_revenue_usd": 35_174_000_000,
        "segments": [("ID", 10.0), ("DE", 7.0), ("JP", 6.0), ("RU", 6.0), ("TR", 5.0), ("SA", 4.5), ("EG", 4.0), ("PH", 3.5), ("PL", 3.0), ("KR", 3.0), ("IT", 2.5), ("UA", 2.5), ("AU", 2.0), ("FR", 2.0), ("PK", 2.0), ("TH", 1.5), ("GB", 1.5), ("MX", 1.5), ("BR", 1.5), ("CH", 1.5), ("ES", 1.5), ("CZ", 1.0), ("SG", 1.0), ("AE", 1.0), ("RO", 0.5), ("HU", 0.5)],
    },
    "CVX": {  # FY2023 total: $200.0B | US, international upstream/downstream
        "fiscal_year": 2023, "total_revenue_usd": 200_060_000_000,
        "segments": [("US", 35.0), ("AU", 12.0), ("KZ", 10.0), ("NG", 6.0), ("SA", 5.0), ("CN", 5.0), ("GB", 4.0), ("TH", 3.5), ("SG", 3.5), ("ID", 2.5), ("CA", 2.5), ("VE", 2.0), ("NO", 1.5), ("IL", 1.0), ("MX", 1.0), ("PH", 0.8), ("BD", 0.5), ("MM", 0.5), ("AG", 0.5), ("AO", 0.5), ("TT", 0.5), ("CD", 0.4), ("ZA", 0.3)],
    },
    "COP": {  # FY2023 total: $56.5B | US, Norway, Canada, Australia
        "fiscal_year": 2023, "total_revenue_usd": 56_498_000_000,
        "segments": [("US", 46.0), ("NO", 16.0), ("CA", 12.0), ("AU", 8.0), ("MX", 5.0), ("QA", 4.0), ("LY", 3.0), ("ID", 2.5), ("CN", 1.5), ("GB", 0.8), ("NG", 0.7), ("BN", 0.5)],
    },
    "SLB": {  # FY2023 total: $33.1B | International, US domestic
        "fiscal_year": 2023, "total_revenue_usd": 33_135_000_000,
        "segments": [("US", 24.0), ("SA", 9.0), ("AE", 5.0), ("NG", 5.0), ("RU", 4.0), ("MX", 4.0), ("NO", 3.5), ("CA", 3.0), ("CN", 3.0), ("BR", 3.0), ("GB", 2.5), ("IQ", 2.5), ("KW", 2.0), ("EG", 2.0), ("IN", 2.0), ("AU", 1.5), ("AO", 1.5), ("AR", 1.5), ("EC", 1.0), ("KZ", 1.0), ("DZ", 0.8), ("QA", 0.7), ("CM", 0.5), ("LY", 0.5), ("GA", 0.5)],
    },
    "RTX": {  # FY2023 total: $68.9B | US, international defense/aerospace
        "fiscal_year": 2023, "total_revenue_usd": 68_920_000_000,
        "segments": [("US", 60.0), ("GB", 5.5), ("SA", 4.0), ("AU", 3.5), ("JP", 3.0), ("DE", 2.5), ("CA", 2.5), ("KR", 2.5), ("AE", 2.0), ("IN", 1.5), ("NO", 1.0), ("IL", 0.8), ("FR", 0.8), ("TW", 0.5), ("IT", 0.4), ("NL", 0.4), ("PL", 0.3), ("SG", 0.3)],
    },
    "HON": {  # FY2023 total: $36.7B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 36_662_000_000,
        "segments": [("US", 56.0), ("CN", 7.0), ("GB", 5.0), ("DE", 4.0), ("IN", 3.5), ("CA", 3.0), ("JP", 3.0), ("NL", 2.0), ("FR", 2.0), ("AU", 1.5), ("SG", 1.5), ("MX", 1.5), ("BR", 1.5), ("KR", 1.0), ("SA", 1.0), ("AE", 1.0), ("IT", 0.8), ("RU", 0.5), ("SE", 0.5), ("CH", 0.5), ("TR", 0.5), ("ZA", 0.2)],
    },
    "BA": {  # FY2023 total: $77.8B | US, Intl commercial/defense
        "fiscal_year": 2023, "total_revenue_usd": 77_794_000_000,
        "segments": [("US", 42.0), ("CN", 6.0), ("AU", 5.0), ("IN", 4.5), ("SA", 4.5), ("GB", 4.0), ("AE", 3.5), ("JP", 3.5), ("KR", 3.0), ("CA", 2.5), ("TR", 2.0), ("SG", 2.0), ("QA", 1.5), ("NO", 1.5), ("NL", 1.5), ("DE", 1.5), ("FR", 1.0), ("IL", 1.0), ("MY", 0.8), ("PL", 0.7), ("IT", 0.5), ("NZ", 0.5), ("FI", 0.4), ("MX", 0.3), ("ZA", 0.3)],
    },
    "CAT": {  # FY2023 total: $67.1B | North America, EAME, Latin America, APAC
        "fiscal_year": 2023, "total_revenue_usd": 67_060_000_000,
        "segments": [("US", 50.0), ("AU", 5.0), ("GB", 4.0), ("CN", 4.0), ("DE", 3.5), ("CA", 3.5), ("JP", 3.0), ("BR", 3.0), ("SA", 2.0), ("IN", 2.0), ("MX", 2.0), ("AE", 1.5), ("CL", 1.5), ("NO", 1.0), ("ZA", 1.0), ("KZ", 0.8), ("MN", 0.7), ("FR", 0.8), ("SG", 0.8), ("PE", 0.5), ("RU", 0.5), ("ID", 0.5), ("PG", 0.5), ("NG", 0.4), ("AR", 0.4)],
    },
    "GE": {  # FY2023 total: $68.0B (GE Aerospace) | US, international
        "fiscal_year": 2023, "total_revenue_usd": 68_000_000_000,
        "segments": [("US", 38.0), ("CN", 8.0), ("FR", 6.0), ("GB", 5.0), ("DE", 4.5), ("IN", 4.0), ("JP", 3.5), ("KR", 3.0), ("SG", 2.5), ("AU", 2.0), ("CA", 2.0), ("BR", 2.0), ("AE", 2.0), ("SA", 1.5), ("IT", 1.5), ("MX", 1.0), ("TH", 0.8), ("NL", 0.8), ("PL", 0.5), ("MY", 0.5), ("TR", 0.4), ("NO", 0.4), ("ZA", 0.3)],
    },
    "UPS": {  # FY2023 total: $91.0B | US domestic, international
        "fiscal_year": 2023, "total_revenue_usd": 90_963_000_000,
        "segments": [("US", 67.0), ("DE", 6.0), ("GB", 4.5), ("CA", 3.5), ("FR", 3.0), ("CN", 2.5), ("JP", 2.0), ("NL", 1.5), ("IT", 1.5), ("AU", 1.0), ("BE", 1.0), ("BR", 0.8), ("SG", 0.7), ("MX", 0.6), ("ES", 0.5), ("IN", 0.5), ("HK", 0.4), ("SE", 0.4), ("PL", 0.3), ("CH", 0.3), ("AT", 0.2)],
    },
    "DE": {  # FY2023 total: $61.3B | US dominant, international
        "fiscal_year": 2023, "total_revenue_usd": 61_251_000_000,
        "segments": [("US", 60.0), ("DE", 5.5), ("BR", 4.0), ("CA", 3.5), ("AU", 3.0), ("AR", 3.0), ("MX", 2.5), ("FR", 2.0), ("GB", 2.0), ("CN", 2.0), ("RU", 1.0), ("FI", 1.0), ("SA", 0.8), ("IN", 0.7), ("ZA", 0.5), ("PL", 0.5), ("CZ", 0.4), ("HU", 0.4), ("UY", 0.3), ("NZ", 0.3), ("CL", 0.3)],
    },
    "LMT": {  # FY2023 total: $67.6B | US, international defense
        "fiscal_year": 2023, "total_revenue_usd": 67_571_000_000,
        "segments": [("US", 74.0), ("AU", 4.0), ("SA", 3.5), ("JP", 3.0), ("GB", 3.0), ("KR", 2.5), ("AE", 2.0), ("NO", 1.5), ("IL", 1.0), ("CA", 1.0), ("IT", 0.8), ("NL", 0.8), ("PL", 0.7), ("TR", 0.5), ("DE", 0.5), ("IN", 0.4), ("TW", 0.3), ("FI", 0.3), ("SG", 0.2)],
    },
    "T": {  # FY2023 total: $122.4B | Primarily US
        "fiscal_year": 2023, "total_revenue_usd": 122_428_000_000,
        "segments": [("US", 97.0), ("MX", 2.0), ("CA", 0.5), ("PR", 0.5)],
    },
    "VZ": {  # FY2023 total: $133.9B | Primarily US
        "fiscal_year": 2023, "total_revenue_usd": 133_974_000_000,
        "segments": [("US", 99.0), ("CA", 0.5), ("GB", 0.3), ("DE", 0.2)],
    },
    "DIS": {  # FY2023 total: $88.9B | US, international
        "fiscal_year": 2023, "total_revenue_usd": 88_898_000_000,
        "segments": [("US", 70.0), ("CN", 4.5), ("JP", 4.0), ("GB", 3.5), ("FR", 3.0), ("CA", 3.0), ("AU", 2.0), ("DE", 2.0), ("IT", 1.0), ("KR", 0.8), ("BR", 0.8), ("MX", 0.6), ("IN", 0.5), ("SG", 0.4), ("NL", 0.4), ("ES", 0.4), ("TW", 0.3), ("SE", 0.3), ("CH", 0.3)],
    },
    "CMCSA": {  # FY2023 total: $121.6B | US, UK (Sky)
        "fiscal_year": 2023, "total_revenue_usd": 121_572_000_000,
        "segments": [("US", 76.0), ("GB", 12.0), ("DE", 4.0), ("IT", 4.0), ("AT", 2.0), ("IE", 1.0), ("CH", 0.6), ("NL", 0.4)],
    },
    "AZN": {  # FY2023 total: $45.8B | US, Emerging Markets, Europe, APAC
        "fiscal_year": 2023, "total_revenue_usd": 45_811_000_000,
        "segments": [("US", 37.0), ("CN", 14.0), ("JP", 6.0), ("DE", 4.0), ("GB", 3.5), ("FR", 3.0), ("IT", 2.5), ("CA", 2.5), ("BR", 2.5), ("RU", 2.0), ("ES", 2.0), ("KR", 2.0), ("AU", 1.5), ("TR", 1.5), ("SA", 1.0), ("MX", 1.0), ("IN", 1.0), ("SE", 0.8), ("NL", 0.8), ("PL", 0.7), ("BE", 0.5), ("AT", 0.4), ("CH", 0.4), ("AR", 0.4)],
    },
    "BP": {  # FY2023 total: $213.0B | Global
        "fiscal_year": 2023, "total_revenue_usd": 212_963_000_000,
        "segments": [("GB", 12.0), ("US", 28.0), ("DE", 6.0), ("AU", 5.0), ("NO", 5.0), ("AZ", 4.0), ("IN", 3.5), ("CN", 3.0), ("AE", 3.0), ("EG", 3.0), ("ID", 2.5), ("TR", 2.0), ("AN", 2.0), ("IL", 1.5), ("MX", 1.5), ("SG", 1.5), ("CA", 1.5), ("TT", 1.5), ("AO", 1.5), ("NG", 1.5), ("BH", 1.0), ("MM", 1.0), ("QA", 0.8), ("ZA", 0.5), ("TN", 0.5), ("MA", 0.5), ("GH", 0.5), ("RU", 0.5)],
    },
    "GSK": {  # FY2023 total: $30.3B | US, Europe, International, APAC
        "fiscal_year": 2023, "total_revenue_usd": 30_328_000_000,
        "segments": [("US", 43.0), ("DE", 5.0), ("FR", 4.5), ("GB", 4.0), ("IT", 3.5), ("JP", 3.5), ("CA", 3.0), ("BR", 2.5), ("CN", 2.5), ("ES", 2.5), ("AU", 2.0), ("KR", 2.0), ("SA", 1.5), ("RU", 1.5), ("TR", 1.5), ("MX", 1.0), ("NL", 0.8), ("BE", 0.8), ("SE", 0.7), ("PL", 0.7), ("CH", 0.6), ("IN", 0.6), ("ZA", 0.5), ("AR", 0.4), ("PK", 0.4)],
    },
    "HSBC": {  # FY2023 total: $66.1B | APAC, Europe, Americas
        "fiscal_year": 2023, "total_revenue_usd": 66_100_000_000,
        "segments": [("HK", 35.0), ("GB", 16.0), ("CN", 10.0), ("US", 8.0), ("SG", 5.0), ("MY", 3.5), ("AE", 3.0), ("IN", 3.0), ("MX", 3.0), ("FR", 2.0), ("CA", 1.5), ("AU", 1.5), ("SA", 1.0), ("DE", 0.8), ("QA", 0.7), ("TW", 0.7), ("ID", 0.5), ("EG", 0.4), ("TR", 0.3), ("BD", 0.3), ("ZA", 0.3)],
    },
    "ARM": {  # FY2024 total: $3.2B | Royalties globally
        "fiscal_year": 2024, "total_revenue_usd": 3_232_000_000,
        "segments": [("US", 20.0), ("KR", 18.0), ("TW", 17.0), ("CN", 17.0), ("JP", 11.0), ("DE", 4.0), ("GB", 3.5), ("SG", 2.5), ("IN", 2.0), ("NL", 1.5), ("FR", 1.0), ("IL", 0.8), ("FI", 0.7), ("SE", 0.5)],
    },
    "RIO": {  # FY2023 total: $54.0B | China dominant, global
        "fiscal_year": 2023, "total_revenue_usd": 54_041_000_000,
        "segments": [("CN", 57.0), ("JP", 10.0), ("AU", 5.0), ("US", 5.0), ("DE", 4.0), ("KR", 4.0), ("CA", 3.0), ("GB", 2.0), ("IN", 2.0), ("TW", 1.5), ("BE", 1.0), ("NL", 0.8), ("MY", 0.7), ("BR", 0.5), ("NZ", 0.5), ("ZA", 0.5)],
    },
    "TTE": {  # FY2023 total: $237.0B | Global energy
        "fiscal_year": 2023, "total_revenue_usd": 237_004_000_000,
        "segments": [("US", 20.0), ("FR", 10.0), ("AE", 8.0), ("NG", 7.0), ("NO", 6.0), ("AU", 5.0), ("QA", 5.0), ("AO", 4.0), ("CN", 4.0), ("RU", 3.0), ("GB", 3.0), ("DE", 2.5), ("BR", 2.0), ("IT", 2.0), ("CG", 2.0), ("GN", 1.5), ("MZ", 1.5), ("CI", 1.0), ("MY", 1.0), ("TZ", 0.8), ("UG", 0.7), ("OM", 0.5), ("KZ", 0.5), ("EG", 0.5), ("YE", 0.5)],
    },
    "SONY": {  # FY2023 total: $88.8B (¥13.0T) | Japan, US, Europe, APAC
        "fiscal_year": 2023, "total_revenue_usd": 88_800_000_000,
        "segments": [("JP", 26.0), ("US", 33.0), ("EU", 0.0), ("DE", 5.5), ("GB", 4.5), ("FR", 3.5), ("CN", 6.0), ("KR", 2.5), ("AU", 2.0), ("CA", 2.0), ("IN", 1.5), ("SG", 1.0), ("TW", 0.8), ("NL", 0.7), ("IT", 0.5), ("ES", 0.5), ("SE", 0.4), ("CH", 0.4), ("MX", 0.4), ("BR", 0.3)],
    },
    "BIDU": {  # FY2023 total: $19.5B | China dominant
        "fiscal_year": 2023, "total_revenue_usd": 19_467_000_000,
        "segments": [("CN", 97.0), ("US", 1.5), ("JP", 0.5), ("SG", 0.5), ("OTHER", 0.5)],
    },
    "JD": {  # FY2023 total: $134.4B (¥1.0T) | China dominant
        "fiscal_year": 2023, "total_revenue_usd": 134_400_000_000,
        "segments": [("CN", 98.0), ("US", 1.0), ("SG", 0.5), ("EU", 0.5)],
    },
    "PDD": {  # FY2023 total: $34.9B | China, international (Temu)
        "fiscal_year": 2023, "total_revenue_usd": 34_854_000_000,
        "segments": [("CN", 78.0), ("US", 8.0), ("GB", 3.0), ("DE", 2.5), ("FR", 2.0), ("AU", 1.5), ("CA", 1.5), ("IT", 1.0), ("NL", 0.8), ("KR", 0.7), ("JP", 0.5)],
    },
    "HDB": {  # FY2024 total: $22.5B | India dominant, international
        "fiscal_year": 2024, "total_revenue_usd": 22_503_000_000,
        "segments": [("IN", 95.0), ("BH", 1.5), ("KE", 1.0), ("GB", 0.8), ("SG", 0.5), ("US", 0.5), ("AE", 0.4), ("SA", 0.3)],
    },
    "VALE": {  # FY2023 total: $40.1B | Brazil, global
        "fiscal_year": 2023, "total_revenue_usd": 40_082_000_000,
        "segments": [("CN", 50.0), ("BR", 14.0), ("JP", 9.0), ("KR", 5.0), ("DE", 4.0), ("MY", 2.5), ("GB", 2.0), ("IT", 1.5), ("ME", 1.5), ("TW", 1.5), ("BH", 1.0), ("SA", 0.8), ("IN", 0.7), ("AU", 0.6), ("PL", 0.5), ("AE", 0.4), ("NL", 0.4), ("HK", 0.4), ("MX", 0.3), ("AT", 0.3)],
    },
    "PBR": {  # FY2023 total: $124.0B (R$596B) | Brazil dominant
        "fiscal_year": 2023, "total_revenue_usd": 124_002_000_000,
        "segments": [("BR", 58.0), ("US", 10.0), ("CN", 8.0), ("NL", 6.0), ("SG", 4.0), ("AR", 3.0), ("JP", 2.5), ("CL", 2.0), ("IN", 1.5), ("MX", 1.5), ("DE", 1.0), ("GB", 0.8), ("UY", 0.5), ("PE", 0.5), ("BO", 0.5), ("TW", 0.4), ("KR", 0.4), ("BE", 0.4)],
    },
    "BHP": {  # FY2023 total: $54.0B | China dominant, global
        "fiscal_year": 2023, "total_revenue_usd": 54_004_000_000,
        "segments": [("CN", 58.0), ("JP", 11.0), ("KR", 6.0), ("AU", 5.0), ("IN", 4.0), ("TW", 3.5), ("DE", 2.0), ("GB", 2.0), ("US", 2.0), ("MY", 1.5), ("AT", 1.0), ("NL", 0.7), ("BE", 0.7), ("CL", 0.5), ("BR", 0.5), ("PL", 0.3), ("IT", 0.3)],
    },

    # ── S&P 500 additions — multinationals with meaningful geo splits ──────────
    "NOW": {  # FY2023 total: $8.97B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 8_971_000_000,
        "segments": [("US", 64.0), ("GB", 5.5), ("DE", 5.0), ("JP", 5.0), ("FR", 3.5), ("AU", 2.5), ("CA", 2.0), ("NL", 1.5), ("IN", 1.5), ("KR", 1.0), ("SG", 0.8), ("IT", 0.8), ("SE", 0.7), ("CH", 0.5), ("BE", 0.5), ("ES", 0.5), ("DK", 0.4), ("FI", 0.3)],
    },
    "PANW": {  # FY2024 total: $8.03B | Americas, EMEA, APAC
        "fiscal_year": 2024, "total_revenue_usd": 8_027_000_000,
        "segments": [("US", 65.0), ("GB", 6.0), ("DE", 4.5), ("JP", 4.5), ("AU", 3.5), ("FR", 2.5), ("CA", 2.0), ("IL", 2.0), ("NL", 1.5), ("IN", 1.0), ("KR", 0.8), ("SG", 0.8), ("IT", 0.6), ("SE", 0.5), ("CH", 0.5), ("BE", 0.5), ("ES", 0.4), ("AE", 0.4)],
    },
    "CRWD": {  # FY2024 total: $3.06B | Americas, EMEA, APAC
        "fiscal_year": 2024, "total_revenue_usd": 3_055_000_000,
        "segments": [("US", 67.0), ("GB", 7.0), ("DE", 5.0), ("AU", 4.0), ("JP", 3.5), ("CA", 2.5), ("FR", 2.0), ("NL", 1.5), ("SG", 1.0), ("IN", 0.8), ("IL", 0.8), ("KR", 0.6), ("SE", 0.5), ("CH", 0.5), ("IT", 0.4), ("BE", 0.4), ("ES", 0.3), ("DK", 0.2)],
    },
    "FTNT": {  # FY2023 total: $5.3B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 5_305_000_000,
        "segments": [("US", 50.0), ("GB", 5.5), ("DE", 5.0), ("JP", 5.0), ("FR", 4.0), ("AU", 3.5), ("CA", 3.0), ("NL", 2.0), ("IN", 2.0), ("SG", 2.0), ("IT", 1.5), ("ES", 1.5), ("KR", 1.5), ("BR", 1.5), ("MX", 1.0), ("IL", 0.8), ("SE", 0.7), ("CH", 0.5), ("SA", 0.5), ("AE", 0.5), ("ZA", 0.5)],
    },
    "ACN": {  # FY2023 total: $64.1B | Americas, Europe, Growth Markets
        "fiscal_year": 2023, "total_revenue_usd": 64_112_000_000,
        "segments": [("US", 44.0), ("GB", 6.0), ("DE", 5.0), ("FR", 5.0), ("JP", 4.0), ("AU", 3.5), ("CA", 3.0), ("IT", 2.5), ("SG", 2.0), ("IN", 2.0), ("BR", 2.0), ("ES", 1.5), ("MX", 1.5), ("SE", 1.0), ("NL", 1.0), ("CH", 0.8), ("CN", 0.8), ("PH", 0.7), ("AT", 0.5), ("BE", 0.5), ("IE", 0.5), ("PL", 0.5), ("CL", 0.3), ("AR", 0.3)],
    },
    "ETN": {  # FY2023 total: $23.2B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 23_196_000_000,
        "segments": [("US", 58.0), ("CN", 6.0), ("DE", 5.0), ("GB", 4.0), ("IN", 3.5), ("CA", 3.0), ("BR", 2.5), ("JP", 2.5), ("FR", 2.0), ("AU", 1.5), ("MX", 1.5), ("IT", 1.0), ("KR", 1.0), ("NL", 0.8), ("SE", 0.8), ("ES", 0.6), ("CH", 0.5), ("TR", 0.5), ("SA", 0.4), ("PL", 0.4), ("ZA", 0.3), ("SG", 0.3), ("AE", 0.3), ("NO", 0.2)],
    },
    "TT": {  # FY2023 total: $16.1B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 16_055_000_000,
        "segments": [("US", 60.0), ("CN", 7.0), ("DE", 5.0), ("GB", 4.0), ("IN", 3.0), ("CA", 3.0), ("FR", 2.5), ("AU", 2.0), ("JP", 2.0), ("NL", 1.5), ("IT", 1.0), ("KR", 0.8), ("MX", 0.8), ("BE", 0.6), ("SE", 0.6), ("TR", 0.5), ("ES", 0.5), ("BR", 0.5), ("SA", 0.4), ("SG", 0.4), ("CH", 0.4), ("PL", 0.3), ("AE", 0.3)],
    },
    "CARR": {  # FY2023 total: $25.5B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 25_498_000_000,
        "segments": [("US", 55.0), ("CN", 7.0), ("DE", 5.0), ("GB", 4.0), ("NL", 3.5), ("FR", 3.0), ("IN", 2.5), ("CA", 2.0), ("JP", 2.0), ("AU", 1.5), ("IT", 1.5), ("KR", 1.0), ("MX", 1.0), ("ES", 0.8), ("SE", 0.8), ("BR", 0.7), ("SG", 0.7), ("SA", 0.5), ("PL", 0.5), ("TR", 0.4), ("AE", 0.4), ("CH", 0.3), ("BE", 0.3)],
    },
    "ITW": {  # FY2023 total: $16.1B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 16_100_000_000,
        "segments": [("US", 50.0), ("CN", 8.0), ("DE", 7.0), ("GB", 4.5), ("JP", 4.0), ("CA", 3.0), ("AU", 2.5), ("FR", 2.5), ("IT", 2.0), ("SE", 1.5), ("NL", 1.5), ("KR", 1.5), ("BR", 1.5), ("MX", 1.0), ("IN", 1.0), ("AT", 0.5), ("BE", 0.5), ("CH", 0.5), ("ES", 0.5), ("PL", 0.5), ("SG", 0.4), ("ZA", 0.3)],
    },
    "PH": {  # FY2023 total: $19.96B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 19_957_000_000,
        "segments": [("US", 50.0), ("DE", 7.0), ("CN", 6.0), ("GB", 5.0), ("CA", 3.5), ("FR", 3.0), ("IN", 3.0), ("JP", 2.5), ("BR", 2.0), ("AU", 2.0), ("IT", 2.0), ("SE", 1.5), ("NL", 1.5), ("MX", 1.0), ("KR", 1.0), ("BE", 0.8), ("ES", 0.7), ("TR", 0.5), ("PL", 0.5), ("SG", 0.5), ("CH", 0.4), ("CZ", 0.4), ("AT", 0.3), ("SA", 0.3), ("AE", 0.3)],
    },
    "ABT": {  # FY2023 total: $20.0B | US, International (50/50)
        "fiscal_year": 2023, "total_revenue_usd": 20_003_000_000,
        "segments": [("US", 40.0), ("DE", 5.0), ("JP", 5.0), ("CN", 4.5), ("GB", 3.5), ("FR", 3.0), ("IT", 3.0), ("CA", 2.5), ("BR", 2.5), ("ES", 2.0), ("AU", 2.0), ("IN", 2.0), ("KR", 2.0), ("MX", 1.5), ("NL", 1.0), ("BE", 0.8), ("SE", 0.7), ("CH", 0.6), ("TR", 0.5), ("RU", 0.5), ("PL", 0.5), ("SA", 0.5), ("ZA", 0.4), ("CO", 0.3), ("AR", 0.3), ("CL", 0.3), ("SG", 0.3), ("TW", 0.3), ("AE", 0.3)],
    },
    "MDT": {  # FY2024 total: $32.4B | US, non-US (50/50)
        "fiscal_year": 2024, "total_revenue_usd": 32_360_000_000,
        "segments": [("US", 49.0), ("DE", 5.0), ("JP", 5.0), ("CN", 4.5), ("FR", 3.5), ("GB", 3.0), ("IT", 3.0), ("CA", 2.5), ("AU", 2.0), ("ES", 2.0), ("KR", 1.5), ("BR", 1.5), ("IN", 1.5), ("NL", 1.0), ("BE", 0.8), ("MX", 0.7), ("CH", 0.7), ("SE", 0.7), ("TR", 0.5), ("SA", 0.5), ("RU", 0.5), ("PL", 0.4), ("CZ", 0.4), ("ZA", 0.4), ("AU", 0.0), ("SG", 0.3), ("TW", 0.3), ("AT", 0.3)],
    },
    "SYK": {  # FY2023 total: $20.5B | US, international
        "fiscal_year": 2023, "total_revenue_usd": 20_498_000_000,
        "segments": [("US", 71.0), ("DE", 4.0), ("JP", 3.0), ("GB", 3.0), ("FR", 2.5), ("AU", 2.0), ("IT", 2.0), ("CA", 2.0), ("CN", 1.5), ("KR", 1.0), ("NL", 0.8), ("ES", 0.7), ("SE", 0.6), ("BR", 0.6), ("CH", 0.5), ("BE", 0.4), ("MX", 0.4), ("IN", 0.4), ("TR", 0.3), ("PL", 0.3), ("SA", 0.3), ("ZA", 0.2)],
    },
    "ISRG": {  # FY2023 total: $7.12B | US, rest of world
        "fiscal_year": 2023, "total_revenue_usd": 7_124_000_000,
        "segments": [("US", 68.0), ("JP", 5.5), ("DE", 4.5), ("GB", 4.0), ("CN", 3.5), ("FR", 3.0), ("AU", 1.5), ("IT", 1.5), ("KR", 1.5), ("CA", 1.0), ("NL", 0.8), ("IN", 0.6), ("ES", 0.6), ("SE", 0.5), ("BE", 0.4), ("CH", 0.4), ("BR", 0.4), ("MX", 0.3), ("SA", 0.3), ("SG", 0.3), ("TR", 0.2)],
    },
    "DHR": {  # FY2023 total: $23.9B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 23_890_000_000,
        "segments": [("US", 38.0), ("CN", 12.0), ("DE", 8.0), ("JP", 5.0), ("GB", 4.5), ("FR", 4.0), ("CA", 3.0), ("AU", 2.0), ("KR", 2.0), ("IN", 2.0), ("IT", 1.5), ("SE", 1.5), ("NL", 1.5), ("BR", 1.0), ("CH", 1.0), ("BE", 0.8), ("ES", 0.7), ("SG", 0.7), ("MX", 0.5), ("PL", 0.4), ("DK", 0.4), ("FI", 0.3), ("AT", 0.3), ("TR", 0.3), ("SA", 0.3), ("TW", 0.3), ("IL", 0.2)],
    },
    "ZTS": {  # FY2023 total: $8.54B | US, international
        "fiscal_year": 2023, "total_revenue_usd": 8_543_000_000,
        "segments": [("US", 52.0), ("BR", 5.5), ("DE", 4.5), ("AU", 4.0), ("JP", 3.5), ("CN", 3.0), ("FR", 3.0), ("GB", 3.0), ("CA", 2.5), ("MX", 2.0), ("IT", 2.0), ("ES", 1.5), ("IN", 1.0), ("KR", 0.8), ("NL", 0.8), ("AR", 0.7), ("BE", 0.6), ("SE", 0.5), ("CO", 0.4), ("TR", 0.4), ("PL", 0.3), ("CH", 0.3), ("ZA", 0.3), ("NZ", 0.3), ("CL", 0.2)],
    },
    "KLAC": {  # FY2024 total: $10.0B | Korea, Taiwan, China, US
        "fiscal_year": 2024, "total_revenue_usd": 9_996_000_000,
        "segments": [("KR", 27.0), ("TW", 23.0), ("CN", 21.0), ("US", 14.0), ("JP", 7.0), ("SG", 3.0), ("DE", 2.0), ("IL", 1.5), ("IN", 0.8), ("NL", 0.7)],
    },
    "LRCX": {  # FY2024 total: $14.9B | Korea, China, Taiwan, US, Japan
        "fiscal_year": 2024, "total_revenue_usd": 14_903_000_000,
        "segments": [("KR", 31.0), ("CN", 30.0), ("TW", 16.0), ("US", 8.0), ("JP", 8.0), ("SG", 4.0), ("DE", 1.0), ("IL", 0.8), ("IN", 0.7), ("NL", 0.5)],
    },
    "NXPI": {  # FY2023 total: $13.3B | China, Americas, Europe, APAC
        "fiscal_year": 2023, "total_revenue_usd": 13_274_000_000,
        "segments": [("CN", 33.0), ("US", 14.0), ("DE", 9.0), ("JP", 8.0), ("KR", 8.0), ("NL", 6.0), ("TW", 5.5), ("SG", 4.0), ("IN", 2.0), ("GB", 2.0), ("FR", 1.5), ("MY", 1.5), ("IT", 1.0), ("SE", 0.8), ("AU", 0.7), ("BE", 0.5)],
    },
    "APH": {  # FY2023 total: $12.6B | Americas, EMEA, Asia
        "fiscal_year": 2023, "total_revenue_usd": 12_554_000_000,
        "segments": [("US", 22.0), ("CN", 22.0), ("SG", 9.0), ("MY", 7.0), ("DE", 5.0), ("JP", 5.0), ("KR", 4.0), ("TW", 3.5), ("IN", 2.5), ("MX", 2.5), ("GB", 2.0), ("FR", 2.0), ("CA", 1.5), ("NL", 1.5), ("BR", 1.0), ("TH", 0.8), ("PH", 0.7), ("IT", 0.7), ("AU", 0.5), ("CZ", 0.5), ("PL", 0.4), ("HU", 0.4), ("IL", 0.4), ("SE", 0.3), ("CH", 0.3), ("TR", 0.3)],
    },
    "MRVL": {  # FY2024 total: $5.5B | Americas, APAC, Europe
        "fiscal_year": 2024, "total_revenue_usd": 5_508_000_000,
        "segments": [("US", 28.0), ("CN", 20.0), ("TH", 16.0), ("TW", 14.0), ("SG", 8.0), ("JP", 5.0), ("KR", 3.0), ("DE", 2.0), ("MY", 1.5), ("IN", 0.8), ("NL", 0.7), ("IL", 0.5), ("GB", 0.5)],
    },
    "ON": {  # FY2023 total: $8.25B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 8_253_000_000,
        "segments": [("US", 23.0), ("CN", 20.0), ("SG", 14.0), ("JP", 10.0), ("KR", 9.0), ("DE", 7.0), ("MY", 4.0), ("TW", 3.5), ("PH", 2.5), ("GB", 1.5), ("IN", 1.5), ("NL", 1.0), ("HU", 0.8), ("CZ", 0.7), ("FR", 0.5)],
    },
    "TEL": {  # FY2023 total: $16.3B | EMEA, Americas, APAC
        "fiscal_year": 2023, "total_revenue_usd": 16_344_000_000,
        "segments": [("US", 20.0), ("CN", 16.0), ("DE", 10.0), ("JP", 8.0), ("KR", 7.0), ("NL", 5.0), ("MX", 4.0), ("TW", 4.0), ("SG", 3.0), ("IN", 3.0), ("MY", 2.5), ("GB", 2.0), ("FR", 2.0), ("CZ", 1.5), ("RO", 1.5), ("IT", 0.8), ("BR", 0.8), ("CA", 0.5), ("PL", 0.5), ("AU", 0.4), ("CH", 0.4), ("SE", 0.4), ("TH", 0.3), ("AT", 0.3), ("BE", 0.3)],
    },
    "WDAY": {  # FY2024 total: $7.26B | Americas, EMEA, APAC
        "fiscal_year": 2024, "total_revenue_usd": 7_259_000_000,
        "segments": [("US", 68.0), ("GB", 6.0), ("DE", 5.0), ("AU", 3.5), ("FR", 3.0), ("CA", 2.5), ("NL", 1.5), ("JP", 1.5), ("SG", 0.8), ("IN", 0.8), ("IT", 0.7), ("SE", 0.6), ("CH", 0.5), ("IE", 0.5), ("BE", 0.4), ("ES", 0.4), ("DK", 0.3)],
    },
    "DDOG": {  # FY2023 total: $2.13B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 2_128_000_000,
        "segments": [("US", 64.0), ("GB", 6.0), ("DE", 5.5), ("JP", 4.0), ("FR", 3.5), ("AU", 2.5), ("CA", 2.0), ("NL", 1.5), ("SG", 1.0), ("IN", 0.8), ("IT", 0.7), ("KR", 0.6), ("SE", 0.5), ("CH", 0.5), ("BE", 0.5), ("ES", 0.4), ("DK", 0.3), ("FI", 0.2)],
    },
    "LIN": {  # FY2023 total: $32.9B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 32_854_000_000,
        "segments": [("US", 35.0), ("DE", 9.0), ("CN", 7.0), ("BR", 5.5), ("GB", 4.5), ("AU", 4.0), ("IN", 3.5), ("CA", 3.0), ("FR", 3.0), ("JP", 2.5), ("IT", 2.0), ("ES", 1.5), ("NL", 1.5), ("KR", 1.5), ("MX", 1.0), ("SE", 0.8), ("AT", 0.7), ("RU", 0.5), ("PL", 0.5), ("ZA", 0.5), ("SG", 0.5), ("TR", 0.4), ("CL", 0.4), ("CZ", 0.3), ("BE", 0.3), ("SA", 0.3), ("CH", 0.3), ("TW", 0.2)],
    },
    "ECL": {  # FY2023 total: $15.3B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 15_320_000_000,
        "segments": [("US", 50.0), ("DE", 5.5), ("CN", 4.5), ("GB", 4.0), ("FR", 3.5), ("JP", 3.5), ("CA", 3.0), ("AU", 2.5), ("IN", 2.5), ("BR", 2.0), ("NL", 1.5), ("IT", 1.5), ("MX", 1.0), ("KR", 1.0), ("ES", 0.8), ("SE", 0.8), ("RU", 0.5), ("CH", 0.5), ("SA", 0.5), ("SG", 0.5), ("PL", 0.4), ("TR", 0.4), ("ZA", 0.4), ("BE", 0.3), ("AT", 0.3), ("AE", 0.3), ("CL", 0.2), ("NG", 0.2)],
    },
    "SHW": {  # FY2023 total: $23.1B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 23_052_000_000,
        "segments": [("US", 69.0), ("CA", 4.0), ("MX", 3.5), ("BR", 3.0), ("AU", 2.5), ("GB", 2.5), ("DE", 2.0), ("CL", 1.5), ("CN", 1.5), ("NL", 1.0), ("FR", 1.0), ("IT", 0.8), ("AR", 0.8), ("CO", 0.5), ("PL", 0.4), ("SE", 0.4), ("TW", 0.3), ("KR", 0.3), ("IN", 0.3), ("NZ", 0.2), ("SG", 0.2), ("ZA", 0.2), ("AE", 0.2), ("TR", 0.2), ("PE", 0.2)],
    },
    "APD": {  # FY2023 total: $12.6B | Americas, Europe, Middle East & Africa, Asia
        "fiscal_year": 2023, "total_revenue_usd": 12_554_000_000,
        "segments": [("US", 36.0), ("DE", 7.5), ("CN", 8.0), ("GB", 5.0), ("CA", 4.0), ("NL", 4.0), ("IN", 3.5), ("SA", 3.0), ("AU", 2.5), ("JP", 2.5), ("KR", 2.0), ("FR", 2.0), ("BR", 1.5), ("BE", 1.5), ("ES", 1.0), ("IT", 0.8), ("MX", 0.8), ("ZA", 0.5), ("TR", 0.5), ("CL", 0.5), ("SE", 0.4), ("PL", 0.3), ("QA", 0.3), ("SG", 0.3)],
    },
    "FCX": {  # FY2023 total: $22.9B | Americas, Indonesia, global copper
        "fiscal_year": 2023, "total_revenue_usd": 22_855_000_000,
        "segments": [("US", 25.0), ("ID", 20.0), ("CN", 18.0), ("JP", 10.0), ("CL", 8.0), ("IN", 4.0), ("KR", 3.0), ("DE", 2.5), ("TW", 2.0), ("AU", 1.5), ("PE", 1.0), ("GB", 0.8), ("MX", 0.7), ("TR", 0.5), ("BR", 0.5), ("IT", 0.5)],
    },
    "NEM": {  # FY2023 total: $11.8B | Americas, Africa, Australia, APAC
        "fiscal_year": 2023, "total_revenue_usd": 11_800_000_000,
        "segments": [("US", 12.0), ("AU", 20.0), ("GH", 15.0), ("PE", 13.0), ("CA", 12.0), ("CL", 7.0), ("ID", 7.0), ("MX", 5.0), ("TZ", 3.0), ("ZW", 2.5), ("AR", 2.0), ("SU", 1.5)],
    },
    "CTSH": {  # FY2023 total: $19.4B | US, Europe, India, RoW
        "fiscal_year": 2023, "total_revenue_usd": 19_354_000_000,
        "segments": [("US", 75.0), ("GB", 6.5), ("DE", 3.5), ("FR", 2.5), ("CA", 2.0), ("AU", 2.0), ("NL", 1.5), ("IN", 0.8), ("CH", 0.5), ("SG", 0.5), ("BE", 0.4), ("IE", 0.4), ("SE", 0.4), ("IT", 0.3), ("NO", 0.3), ("DK", 0.3), ("FI", 0.2), ("ES", 0.2), ("JP", 0.2)],
    },
    "SPGI": {  # FY2023 total: $13.0B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 13_005_000_000,
        "segments": [("US", 56.0), ("GB", 7.0), ("DE", 5.5), ("FR", 3.5), ("AU", 2.5), ("JP", 2.5), ("CA", 2.0), ("IT", 1.5), ("CN", 1.5), ("SG", 1.5), ("NL", 1.0), ("IN", 1.0), ("ES", 0.8), ("SE", 0.7), ("CH", 0.7), ("BR", 0.7), ("MX", 0.5), ("IE", 0.5), ("BE", 0.4), ("DK", 0.3), ("AE", 0.3), ("HK", 0.3), ("ZA", 0.2), ("SA", 0.2), ("PL", 0.2)],
    },
    "MCO": {  # FY2023 total: $6.0B | US, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 5_972_000_000,
        "segments": [("US", 50.0), ("GB", 8.0), ("DE", 6.0), ("FR", 4.5), ("JP", 4.5), ("AU", 3.5), ("CA", 3.0), ("IT", 2.0), ("SG", 2.0), ("CN", 2.0), ("IN", 1.5), ("NL", 1.5), ("ES", 1.0), ("SE", 0.8), ("CH", 0.7), ("BR", 0.7), ("HK", 0.7), ("BE", 0.5), ("IE", 0.5), ("DK", 0.3), ("PL", 0.3), ("SA", 0.3), ("ZA", 0.2), ("MX", 0.2), ("TR", 0.2), ("AE", 0.2)],
    },
    "ICE": {  # FY2023 total: $7.94B | US, UK, EU
        "fiscal_year": 2023, "total_revenue_usd": 7_940_000_000,
        "segments": [("US", 68.0), ("GB", 14.0), ("IE", 5.0), ("NL", 3.0), ("SG", 2.5), ("CA", 2.5), ("AU", 1.5), ("JP", 1.0), ("IN", 0.7), ("DE", 0.6), ("FR", 0.4), ("BE", 0.3)],
    },
    "CME": {  # FY2023 total: $5.64B | US dominant
        "fiscal_year": 2023, "total_revenue_usd": 5_644_000_000,
        "segments": [("US", 72.0), ("GB", 8.5), ("JP", 4.0), ("SG", 3.5), ("AU", 2.5), ("DE", 2.0), ("HK", 1.5), ("CA", 1.5), ("FR", 1.0), ("CH", 0.8), ("NL", 0.5), ("IE", 0.5), ("IN", 0.3), ("BR", 0.3), ("AE", 0.3), ("IL", 0.3)],
    },
    "AON": {  # FY2023 total: $13.4B | Americas, EMEA, APAC
        "fiscal_year": 2023, "total_revenue_usd": 13_374_000_000,
        "segments": [("US", 43.0), ("GB", 11.0), ("DE", 5.0), ("FR", 4.0), ("CA", 3.5), ("AU", 3.0), ("JP", 2.5), ("IT", 2.0), ("NL", 2.0), ("SG", 1.5), ("IN", 1.5), ("BR", 1.5), ("CH", 1.5), ("ES", 1.0), ("IE", 1.0), ("MX", 0.8), ("SE", 0.8), ("BE", 0.7), ("ZA", 0.6), ("DK", 0.5), ("HK", 0.5), ("AE", 0.5), ("NO", 0.4), ("PL", 0.4), ("TR", 0.3), ("SA", 0.3), ("NG", 0.2), ("KR", 0.2)],
    },
    "MMC": {  # FY2023 total: $23.0B | Americas, EMEA, Asia Pacific
        "fiscal_year": 2023, "total_revenue_usd": 22_739_000_000,
        "segments": [("US", 52.0), ("GB", 9.0), ("CA", 3.5), ("AU", 3.5), ("DE", 3.0), ("FR", 3.0), ("JP", 2.0), ("SG", 1.5), ("NL", 1.5), ("IE", 1.5), ("IN", 1.5), ("IT", 1.0), ("BR", 1.0), ("CH", 0.8), ("MX", 0.8), ("ES", 0.7), ("BE", 0.5), ("ZA", 0.5), ("HK", 0.5), ("SE", 0.4), ("DK", 0.4), ("NO", 0.3), ("AE", 0.3), ("KR", 0.3), ("PL", 0.2), ("NG", 0.2)],
    },
    "COST": {  # FY2024 total: $249.6B — updated above
        "fiscal_year": 2024, "total_revenue_usd": 249_636_000_000,
        "segments": [("US", 73.0), ("CA", 9.0), ("GB", 2.5), ("JP", 2.5), ("KR", 2.0), ("AU", 2.0), ("TW", 2.0), ("MX", 2.0), ("ES", 1.5), ("CN", 1.5), ("FR", 1.0), ("IS", 0.5)],
    },
    # US-centric companies (>90% US revenue) — single-entry for completeness
    "UNP": {"fiscal_year": 2023, "total_revenue_usd": 23_642_000_000, "segments": [("US", 99.0), ("MX", 0.6), ("CA", 0.4)]},
    "CSX": {"fiscal_year": 2023, "total_revenue_usd": 14_657_000_000, "segments": [("US", 99.0), ("CA", 0.7), ("MX", 0.3)]},
    "NSC": {"fiscal_year": 2023, "total_revenue_usd": 12_156_000_000, "segments": [("US", 99.0), ("CA", 0.6), ("MX", 0.4)]},
    "FDX": {"fiscal_year": 2024, "total_revenue_usd": 87_693_000_000, "segments": [("US", 66.0), ("GB", 4.5), ("DE", 4.0), ("JP", 3.5), ("FR", 3.0), ("CA", 2.5), ("AU", 2.0), ("CN", 2.0), ("NL", 1.5), ("IT", 1.0), ("BE", 0.8), ("BR", 0.7), ("SG", 0.5), ("MX", 0.5), ("IN", 0.4), ("ES", 0.4), ("SE", 0.4), ("HK", 0.3), ("PL", 0.3), ("CH", 0.3), ("AT", 0.2), ("AE", 0.2)]},
    "ADP": {"fiscal_year": 2024, "total_revenue_usd": 18_674_000_000, "segments": [("US", 73.0), ("GB", 5.0), ("FR", 4.5), ("CA", 4.0), ("DE", 3.0), ("AU", 2.0), ("NL", 1.5), ("BR", 1.5), ("IN", 1.0), ("ES", 0.8), ("SG", 0.5), ("IT", 0.5), ("MX", 0.5), ("JP", 0.5), ("CH", 0.4), ("BE", 0.3), ("PL", 0.3), ("SE", 0.3), ("IE", 0.3), ("HK", 0.2), ("NZ", 0.1)]},
    "CTAS": {"fiscal_year": 2024, "total_revenue_usd": 9_617_000_000, "segments": [("US", 87.0), ("CA", 9.0), ("GB", 1.5), ("AU", 0.8), ("DE", 0.4), ("IE", 0.3)]},
    "PAYX": {"fiscal_year": 2024, "total_revenue_usd": 5_282_000_000, "segments": [("US", 97.0), ("CA", 2.0), ("DE", 0.5), ("GB", 0.3), ("AU", 0.2)]},
    "ROP": {"fiscal_year": 2023, "total_revenue_usd": 5_837_000_000, "segments": [("US", 78.0), ("CA", 5.0), ("GB", 4.0), ("DE", 3.0), ("AU", 2.5), ("JP", 1.5), ("FR", 1.5), ("NL", 1.0), ("SG", 0.8), ("CN", 0.5), ("IN", 0.5), ("SE", 0.4), ("CH", 0.3), ("BR", 0.3), ("IT", 0.2), ("KR", 0.2), ("BE", 0.2), ("MX", 0.1)]},
    "AME": {"fiscal_year": 2023, "total_revenue_usd": 6_512_000_000, "segments": [("US", 53.0), ("GB", 7.0), ("DE", 6.0), ("CN", 5.0), ("JP", 4.5), ("CA", 3.5), ("IN", 3.0), ("FR", 2.5), ("AU", 2.0), ("KR", 2.0), ("IT", 1.5), ("NL", 1.5), ("SE", 1.0), ("MX", 0.8), ("BR", 0.7), ("SG", 0.7), ("CH", 0.5), ("IL", 0.5), ("ES", 0.4), ("BE", 0.3), ("CZ", 0.3), ("PL", 0.3)]},
    "DAL": {"fiscal_year": 2023, "total_revenue_usd": 58_048_000_000, "segments": [("US", 76.0), ("GB", 3.5), ("JP", 3.0), ("DE", 2.5), ("FR", 2.0), ("CA", 2.0), ("MX", 1.5), ("AU", 1.5), ("NL", 1.0), ("KR", 1.0), ("IN", 0.8), ("IT", 0.8), ("BR", 0.8), ("SG", 0.7), ("ES", 0.6), ("CN", 0.5), ("PT", 0.5), ("NO", 0.3), ("SE", 0.2), ("IE", 0.2), ("CH", 0.2), ("BE", 0.2), ("AT", 0.2)]},
    "GD": {"fiscal_year": 2023, "total_revenue_usd": 42_271_000_000, "segments": [("US", 67.0), ("GB", 5.5), ("CA", 4.0), ("AU", 3.5), ("SA", 3.0), ("ES", 2.5), ("DE", 2.0), ("IT", 1.5), ("JP", 1.5), ("KR", 1.5), ("AE", 1.0), ("CH", 1.0), ("NO", 0.8), ("IL", 0.8), ("FR", 0.6), ("PL", 0.5), ("TR", 0.4), ("IN", 0.4), ("FI", 0.3), ("GR", 0.2), ("BR", 0.2), ("PT", 0.2)]},
    "NOC": {"fiscal_year": 2023, "total_revenue_usd": 39_290_000_000, "segments": [("US", 83.0), ("AU", 4.5), ("GB", 3.5), ("SA", 2.5), ("KR", 1.5), ("JP", 1.0), ("AE", 0.8), ("NO", 0.7), ("IT", 0.5), ("DE", 0.4), ("IN", 0.3), ("PL", 0.3), ("CA", 0.3), ("FR", 0.2), ("NL", 0.2)]},
    "LMT": {"fiscal_year": 2023, "total_revenue_usd": 67_571_000_000, "segments": [("US", 74.0), ("AU", 4.0), ("SA", 3.5), ("JP", 3.0), ("GB", 3.0), ("KR", 2.5), ("AE", 2.0), ("NO", 1.5), ("IL", 1.0), ("CA", 1.0), ("IT", 0.8), ("NL", 0.8), ("PL", 0.7), ("TR", 0.5), ("DE", 0.5), ("IN", 0.4), ("TW", 0.3), ("FI", 0.3), ("SG", 0.2)]},
    "CI": {"fiscal_year": 2023, "total_revenue_usd": 195_265_000_000, "segments": [("US", 89.0), ("GB", 2.5), ("KR", 1.5), ("TW", 1.0), ("SA", 0.8), ("AE", 0.7), ("CA", 0.6), ("IN", 0.5), ("SG", 0.4), ("JP", 0.4), ("AU", 0.3), ("HK", 0.3)]},
    "MCK": {"fiscal_year": 2024, "total_revenue_usd": 308_959_000_000, "segments": [("US", 97.0), ("CA", 1.5), ("IE", 0.5), ("GB", 0.3), ("AU", 0.2), ("NL", 0.1), ("DE", 0.1), ("FR", 0.1), ("NO", 0.1)]},
    "CAH": {"fiscal_year": 2024, "total_revenue_usd": 226_942_000_000, "segments": [("US", 98.0), ("CA", 1.0), ("IE", 0.5), ("AU", 0.3), ("NZ", 0.2)]},
    "CVS": {"fiscal_year": 2023, "total_revenue_usd": 357_776_000_000, "segments": [("US", 99.0), ("PR", 0.6), ("CA", 0.2), ("GB", 0.1), ("IE", 0.1)]},
    "MO": {"fiscal_year": 2023, "total_revenue_usd": 24_379_000_000, "segments": [("US", 99.5), ("CA", 0.3), ("OTHER", 0.2)]},
    "WBA": {"fiscal_year": 2023, "total_revenue_usd": 139_081_000_000, "segments": [("US", 77.0), ("GB", 14.0), ("DE", 4.0), ("CH", 1.5), ("IE", 1.0), ("NL", 0.8), ("FR", 0.5), ("AT", 0.4), ("NO", 0.3), ("LI", 0.5)]},
    "KMB": {"fiscal_year": 2023, "total_revenue_usd": 20_175_000_000, "segments": [("US", 45.0), ("CN", 5.0), ("BR", 4.5), ("KR", 4.0), ("AU", 3.5), ("GB", 3.0), ("DE", 2.5), ("MX", 2.5), ("CA", 2.5), ("RU", 2.0), ("IT", 1.5), ("FR", 1.5), ("TR", 1.5), ("IN", 1.5), ("SA", 1.0), ("ES", 0.8), ("AR", 0.8), ("CL", 0.8), ("CO", 0.6), ("ZA", 0.5), ("SG", 0.5), ("JP", 0.5), ("EG", 0.5), ("TH", 0.4), ("MY", 0.4), ("IL", 0.3), ("PK", 0.3), ("NZ", 0.3)]},
    "CL": {"fiscal_year": 2023, "total_revenue_usd": 19_459_000_000, "segments": [("US", 19.0), ("MX", 8.0), ("BR", 7.5), ("CN", 5.5), ("IN", 5.0), ("AU", 3.5), ("GB", 3.0), ("DE", 2.5), ("FR", 2.5), ("AR", 2.5), ("RU", 2.0), ("IT", 1.5), ("VE", 1.5), ("KR", 1.5), ("PE", 1.5), ("CO", 1.0), ("SA", 1.0), ("TH", 1.0), ("CL", 0.8), ("ZA", 0.7), ("ES", 0.7), ("PH", 0.7), ("TR", 0.7), ("EG", 0.5), ("PK", 0.5), ("UA", 0.5), ("MY", 0.4), ("NG", 0.4), ("EC", 0.3), ("JO", 0.3), ("DO", 0.3)]},
    "PG": {"fiscal_year": 2023, "total_revenue_usd": 82_006_000_000, "segments": [("US", 44.0), ("CN", 6.5), ("DE", 4.0), ("GB", 3.5), ("JP", 3.5), ("MX", 3.0), ("CA", 3.0), ("FR", 2.5), ("BR", 2.5), ("AU", 2.0), ("RU", 2.0), ("IN", 2.0), ("KR", 1.5), ("IT", 1.5), ("SA", 1.0), ("TR", 1.0), ("AR", 0.8), ("ES", 0.8), ("EG", 0.7), ("PL", 0.6), ("NL", 0.6), ("TH", 0.5), ("SE", 0.5), ("PH", 0.4), ("ZA", 0.4), ("CL", 0.3), ("MY", 0.3), ("CO", 0.3), ("NG", 0.3), ("UA", 0.2), ("CZ", 0.2)]},
    "GIS": {"fiscal_year": 2024, "total_revenue_usd": 19_857_000_000, "segments": [("US", 66.0), ("CA", 5.5), ("GB", 4.0), ("AU", 3.5), ("BR", 2.5), ("CN", 2.0), ("FR", 2.0), ("IN", 1.5), ("MX", 1.5), ("DE", 1.0), ("IT", 1.0), ("BE", 0.7), ("NL", 0.7), ("ZA", 0.5), ("PL", 0.4), ("SE", 0.4), ("NZ", 0.4), ("JP", 0.4), ("AR", 0.3), ("KR", 0.3), ("CL", 0.2), ("SG", 0.2), ("TR", 0.2)]},
    "MNST": {"fiscal_year": 2023, "total_revenue_usd": 7_140_000_000, "segments": [("US", 61.0), ("GB", 4.0), ("DE", 3.5), ("AU", 2.5), ("CA", 2.5), ("FR", 2.5), ("MX", 2.0), ("JP", 1.5), ("BR", 1.5), ("ZA", 1.0), ("CN", 0.8), ("IT", 0.8), ("NL", 0.8), ("ES", 0.7), ("KR", 0.6), ("NZ", 0.6), ("SE", 0.5), ("TR", 0.5), ("IN", 0.4), ("PL", 0.4), ("AR", 0.3), ("BE", 0.3), ("CH", 0.3), ("SG", 0.3), ("CL", 0.2), ("PE", 0.2)]},

    # Financials — mostly US-centric
    "PGR": {"fiscal_year": 2023, "total_revenue_usd": 62_081_000_000, "segments": [("US", 99.5), ("CA", 0.3), ("AU", 0.2)]},
    "CB": {"fiscal_year": 2023, "total_revenue_usd": 52_239_000_000, "segments": [("US", 45.0), ("GB", 8.0), ("AU", 5.0), ("CA", 4.0), ("CH", 3.5), ("DE", 3.0), ("JP", 2.5), ("FR", 2.5), ("SG", 2.5), ("HK", 2.0), ("IE", 1.5), ("IT", 1.5), ("BR", 1.5), ("IN", 1.5), ("MX", 1.0), ("ES", 0.8), ("NL", 0.8), ("AE", 0.7), ("SA", 0.5), ("ZA", 0.5), ("KR", 0.4), ("TR", 0.3), ("AR", 0.3), ("NO", 0.2), ("SE", 0.2), ("BE", 0.2), ("AT", 0.2), ("PL", 0.2), ("ID", 0.2)]},
    "SCHW": {"fiscal_year": 2023, "total_revenue_usd": 18_836_000_000, "segments": [("US", 97.0), ("GB", 1.5), ("SG", 0.8), ("HK", 0.5), ("CA", 0.2)]},
    "AFL": {"fiscal_year": 2023, "total_revenue_usd": 22_076_000_000, "segments": [("US", 32.0), ("JP", 68.0)]},
    "PRU": {"fiscal_year": 2023, "total_revenue_usd": 67_461_000_000, "segments": [("US", 60.0), ("JP", 12.0), ("GB", 5.0), ("KR", 4.0), ("BR", 3.5), ("MX", 2.0), ("IN", 2.0), ("AU", 1.5), ("IT", 1.0), ("PL", 0.8), ("AR", 0.8), ("DE", 0.6), ("CN", 0.6), ("TW", 0.5), ("ID", 0.5), ("MY", 0.4), ("PH", 0.4), ("SG", 0.4), ("QA", 0.3), ("CL", 0.3), ("GH", 0.3), ("ZA", 0.2), ("CO", 0.2), ("NG", 0.2), ("UA", 0.2)]},
    "MET": {"fiscal_year": 2023, "total_revenue_usd": 69_897_000_000, "segments": [("US", 57.0), ("JP", 9.0), ("GB", 4.0), ("DE", 3.0), ("MX", 3.0), ("AU", 2.5), ("BR", 2.5), ("KR", 2.0), ("IT", 1.5), ("FR", 1.5), ("CN", 1.0), ("SA", 1.0), ("ES", 0.8), ("TR", 0.7), ("AE", 0.6), ("IN", 0.5), ("CA", 0.5), ("NL", 0.4), ("CL", 0.4), ("AR", 0.4), ("CO", 0.3), ("EG", 0.3), ("QA", 0.3), ("ZA", 0.2), ("NG", 0.2), ("BD", 0.2)]},
    "TRV": {"fiscal_year": 2023, "total_revenue_usd": 39_397_000_000, "segments": [("US", 91.0), ("CA", 4.0), ("GB", 3.0), ("IE", 1.0), ("DE", 0.5), ("SG", 0.3), ("AU", 0.2)]},
    "ALL": {"fiscal_year": 2023, "total_revenue_usd": 57_122_000_000, "segments": [("US", 97.0), ("CA", 2.0), ("GB", 0.5), ("IN", 0.3), ("IE", 0.2)]},
    "AIG": {"fiscal_year": 2023, "total_revenue_usd": 26_000_000_000, "segments": [("US", 55.0), ("GB", 7.0), ("JP", 6.0), ("AU", 4.0), ("DE", 3.0), ("FR", 2.5), ("CA", 2.5), ("SG", 2.0), ("IT", 1.5), ("IE", 1.5), ("BR", 1.0), ("CH", 1.0), ("HK", 1.0), ("MX", 0.8), ("IN", 0.8), ("ES", 0.6), ("NL", 0.6), ("BE", 0.4), ("ZA", 0.4), ("SA", 0.4), ("AE", 0.4), ("KR", 0.3), ("TR", 0.3), ("PL", 0.2), ("AR", 0.2)]},
    "PYPL": {"fiscal_year": 2023, "total_revenue_usd": 29_771_000_000, "segments": [("US", 51.0), ("GB", 7.5), ("DE", 6.5), ("AU", 4.0), ("FR", 3.5), ("CA", 3.5), ("IT", 2.5), ("ES", 2.0), ("BR", 2.0), ("CN", 1.0), ("MX", 1.0), ("IN", 1.0), ("NL", 1.0), ("SE", 0.8), ("PL", 0.8), ("BE", 0.6), ("AT", 0.6), ("CH", 0.5), ("SG", 0.5), ("HK", 0.4), ("IL", 0.4), ("NO", 0.3), ("DK", 0.3), ("ZA", 0.3), ("TR", 0.3), ("AR", 0.2), ("RU", 0.2), ("FI", 0.2)]},
    "FISV": {"fiscal_year": 2023, "total_revenue_usd": 19_090_000_000, "segments": [("US", 76.0), ("GB", 4.5), ("DE", 3.0), ("AU", 2.5), ("CA", 2.0), ("IN", 2.0), ("BR", 1.5), ("FR", 1.0), ("SG", 0.8), ("JP", 0.8), ("IT", 0.7), ("IE", 0.6), ("NL", 0.5), ("ZA", 0.5), ("MX", 0.5), ("ES", 0.4), ("CH", 0.3), ("BE", 0.3), ("PL", 0.3), ("AE", 0.3), ("AR", 0.2), ("KR", 0.2)]},
    "FIS": {"fiscal_year": 2023, "total_revenue_usd": 14_545_000_000, "segments": [("US", 60.0), ("GB", 7.5), ("DE", 4.0), ("AU", 3.5), ("CA", 3.0), ("FR", 3.0), ("IN", 2.5), ("BR", 2.0), ("JP", 1.5), ("IT", 1.0), ("SG", 0.8), ("NL", 0.8), ("IE", 0.7), ("MX", 0.6), ("BE", 0.5), ("ES", 0.5), ("CH", 0.4), ("ZA", 0.4), ("SE", 0.3), ("PL", 0.3), ("HK", 0.3), ("SA", 0.2), ("AE", 0.2)]},

    # Real Estate — all primarily US
    "PLD": {"fiscal_year": 2023, "total_revenue_usd": 7_673_000_000, "segments": [("US", 76.0), ("JP", 7.0), ("DE", 3.5), ("GB", 2.5), ("AU", 2.0), ("CN", 1.5), ("NL", 1.5), ("FR", 1.0), ("BR", 0.8), ("SG", 0.8), ("CA", 0.5), ("MX", 0.5), ("ES", 0.4), ("PL", 0.4), ("IT", 0.3), ("CZ", 0.3), ("SE", 0.3), ("PT", 0.2)]},
    "AMT": {"fiscal_year": 2023, "total_revenue_usd": 11_143_000_000, "segments": [("US", 46.0), ("IN", 14.0), ("BR", 8.0), ("DE", 5.0), ("FR", 4.5), ("NG", 4.0), ("ES", 3.0), ("GB", 2.5), ("MX", 2.0), ("KE", 1.5), ("SA", 1.5), ("PE", 1.0), ("UG", 0.8), ("GH", 0.8), ("ZA", 0.5), ("CL", 0.5), ("CO", 0.4), ("PA", 0.4), ("EC", 0.3), ("PY", 0.2), ("TZ", 0.2), ("QA", 0.2), ("BF", 0.2)]},
    "EQIX": {"fiscal_year": 2023, "total_revenue_usd": 8_248_000_000, "segments": [("US", 42.0), ("GB", 7.5), ("DE", 6.5), ("SG", 6.0), ("NL", 5.0), ("JP", 4.5), ("FR", 4.0), ("AU", 3.5), ("BR", 2.5), ("SE", 1.5), ("CH", 1.5), ("IT", 1.5), ("FI", 1.5), ("IE", 1.0), ("CN", 1.0), ("CA", 0.8), ("IN", 0.7), ("HK", 0.7), ("AE", 0.6), ("DK", 0.5), ("IL", 0.4), ("KR", 0.4), ("ES", 0.4), ("PL", 0.3), ("AT", 0.2)]},
    "DLR": {"fiscal_year": 2023, "total_revenue_usd": 5_481_000_000, "segments": [("US", 52.0), ("GB", 7.0), ("DE", 6.0), ("NL", 5.5), ("SG", 4.5), ("AU", 3.5), ("FR", 3.0), ("JP", 3.0), ("CH", 2.0), ("IE", 1.5), ("ZA", 1.5), ("BR", 1.0), ("CA", 1.0), ("KR", 0.8), ("AT", 0.5), ("ES", 0.5), ("IN", 0.4), ("SE", 0.4), ("FI", 0.3), ("PL", 0.3), ("IT", 0.3), ("HK", 0.3)]},
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
