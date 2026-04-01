"""
Live EDGAR geographic revenue fetcher.
Sources: SEC EDGAR XBRL companyfacts API (public, no key required).

For each stock missing stock_country_revenues data:
  1. Lookup CIK via SEC company_tickers.json
  2. Fetch companyfacts JSON
  3. Extract most recent 10-K geographic revenue segments
  4. Map segment names → ISO country codes
  5. Upsert into stock_country_revenues

Rate limit: 10 req/sec per SEC fair-use policy (we use 5 req/sec to be safe).
Run: python -m tasks.edgar_revenue  (or via Celery beat weekly Sunday 02:00 UTC)
"""

import logging
import time
import re
from datetime import date
from typing import Optional

import requests
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, StockCountryRevenue
from app.models.country import Country

log = logging.getLogger(__name__)

# SEC requires a descriptive User-Agent with contact info
HEADERS = {
    "User-Agent": "MetricsHour info@metricshour.com",
    "Accept-Encoding": "gzip, deflate",
}

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL   = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Revenue concept names to look for (in priority order)
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueGoodsNet",
    "RevenueFromRelatedParties",
]

# Geographic segment member → ISO 2-letter country code
# Covers XBRL standard (srt:) members + common company-specific labels
GEO_MAP: dict[str, str] = {
    # srt standard members
    "srt:unitedstatesMember":          "US",
    "srt:americasMember":              "US",  # treated as US-dominant; split below
    "srt:northAmericaMember":          "US",
    "srt:canadaMember":                "CA",
    "srt:europeMember":                "DE",  # proxy; split below
    "srt:europeanUnionMember":         "DE",
    "srt:asiaPacificMember":           "CN",  # proxy; split below
    "srt:japanMember":                 "JP",
    "srt:chinaMember":                 "CN",
    "srt:restOfWorldMember":           None,  # skip
    "srt:allOtherSegmentsMember":      None,

    # Country label patterns (lowercased, stripped of spaces/punctuation)
    "unitedstates":         "US",
    "unitedstatesofamerica":"US",
    "us":                   "US",
    "usa":                  "US",
    "domestics":            "US",
    "domestic":             "US",
    "americas":             "US",   # handled as region below
    "northamerica":         "US",
    "canada":               "CA",
    "mexico":               "MX",
    "brazil":               "BR",
    "latinamerica":         "BR",   # proxy
    "southamerica":         "BR",
    "unitedkingdom":        "GB",
    "uk":                   "GB",
    "greatbritain":         "GB",
    "germany":              "DE",
    "france":               "FR",
    "italy":                "IT",
    "spain":                "ES",
    "netherlands":          "NL",
    "switzerland":          "CH",
    "sweden":               "SE",
    "norway":               "NO",
    "denmark":              "DK",
    "austria":              "AT",
    "belgium":              "BE",
    "poland":               "PL",
    "europe":               "DE",   # proxy; split below
    "emea":                 "DE",   # proxy
    "restofeurope":         "DE",
    "japan":                "JP",
    "china":                "CN",
    "greaterchinese":       "CN",
    "greaterchina":         "CN",
    "taiwan":               "TW",
    "korea":                "KR",
    "southkorea":           "KR",
    "australia":            "AU",
    "india":                "IN",
    "singapore":            "SG",
    "hongkong":             "HK",
    "asiapacific":          "CN",   # proxy
    "asia":                 "CN",
    "apac":                 "CN",
    "restofasia":           "CN",
    "middleeast":           "SA",
    "africa":               "ZA",
    "israel":               "IL",
    "russia":               "RU",
    "international":        None,   # too vague; skip unless only segment
    "other":                None,
    "restofworld":          None,
    "otherworldwide":       None,
}

# Multi-country regions: split pct across constituent countries
REGION_SPLITS: dict[str, list[tuple[str, float]]] = {
    "US":  [("US", 1.0)],
    "DE":  [("DE", 0.35), ("GB", 0.20), ("FR", 0.15), ("IT", 0.10), ("ES", 0.08), ("NL", 0.07), ("CH", 0.05)],  # Europe proxy
    "CN":  [("CN", 0.55), ("JP", 0.18), ("KR", 0.10), ("AU", 0.08), ("IN", 0.05), ("SG", 0.04)],                # APAC proxy
    "BR":  [("BR", 0.55), ("MX", 0.25), ("AR", 0.10), ("CL", 0.10)],                                            # LatAm proxy
    "SA":  [("SA", 0.40), ("AE", 0.30), ("IL", 0.15), ("EG", 0.15)],                                            # Middle East proxy
    "ZA":  [("ZA", 0.50), ("NG", 0.25), ("KE", 0.15), ("EG", 0.10)],                                            # Africa proxy
}


def _normalize_label(label: str) -> str:
    """Strip punctuation/whitespace, lowercase."""
    return re.sub(r"[^a-z0-9]", "", label.lower())


def _segment_to_iso(segment: dict) -> Optional[str]:
    """
    segment = {"axis": "srt:StatementGeographicalAxis", "member": "srt:UnitedStatesMember"}
    Returns ISO2 code or None.
    """
    member = segment.get("member", "").lower()
    label  = segment.get("label", "").lower()

    # Try exact XBRL member match
    if member in GEO_MAP:
        return GEO_MAP[member]

    # Try normalised label
    norm = _normalize_label(label or member.split(":")[-1].replace("member", ""))
    return GEO_MAP.get(norm)


def _fetch_cik_map() -> dict[str, str]:
    """Return {ticker_upper: cik_10digit_padded}."""
    resp = requests.get(SEC_TICKERS_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    result = {}
    for entry in data.values():
        ticker = entry.get("ticker", "").upper()
        cik    = str(entry.get("cik_str", "")).zfill(10)
        if ticker:
            result[ticker] = cik
    return result


def _fetch_geo_revenue(cik: str, ticker: str) -> Optional[dict]:
    """
    Fetch companyfacts and extract the most recent 10-K geographic revenue breakdown.
    Returns {fiscal_year, total_revenue_usd, segments: [(iso2, pct)]} or None.
    """
    url = SEC_FACTS_URL.format(cik=cik)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except Exception as e:
        log.warning("%s: EDGAR fetch error: %s", ticker, e)
        return None

    facts = resp.json().get("facts", {}).get("us-gaap", {})

    # Try each revenue concept in priority order
    for concept in REVENUE_CONCEPTS:
        if concept not in facts:
            continue

        usd_facts = facts[concept].get("units", {}).get("USD", [])
        if not usd_facts:
            continue

        # Filter to 10-K annual filings with geographic segments
        geo_facts = [
            f for f in usd_facts
            if f.get("form") == "10-K"
            and f.get("segment", {}).get("axis") == "srt:StatementGeographicalAxis"
        ]
        if not geo_facts:
            continue

        # Get most recent filing accession
        geo_facts.sort(key=lambda f: f.get("end", ""), reverse=True)
        latest_end = geo_facts[0]["end"]
        filing_accn = geo_facts[0]["accn"]

        # All segments from the same filing
        filing_facts = [f for f in geo_facts if f["accn"] == filing_accn]

        # Also get total (no segment) for same filing to derive percentages
        total_facts = [
            f for f in usd_facts
            if f.get("form") == "10-K"
            and f.get("accn") == filing_accn
            and "segment" not in f
        ]
        total_rev = total_facts[0]["val"] if total_facts else None

        if not total_rev:
            # Sum segments as total
            total_rev = sum(f["val"] for f in filing_facts)

        if not total_rev or total_rev == 0:
            continue

        # Map segments → ISO codes
        raw_segments: dict[str, float] = {}
        for f in filing_facts:
            iso = _segment_to_iso(f["segment"])
            if iso is None:
                continue
            val = f["val"]
            # If proxy (region), split into constituent countries
            splits = REGION_SPLITS.get(iso, [(iso, 1.0)])
            for country_iso, weight in splits:
                raw_segments[country_iso] = raw_segments.get(country_iso, 0) + val * weight

        if not raw_segments:
            continue

        # Convert to percentages; cap at 100 total
        seg_total = sum(raw_segments.values())
        segments = [
            (iso, round(val / seg_total * 100, 2))
            for iso, val in raw_segments.items()
            if val / seg_total * 100 >= 0.5  # drop < 0.5% noise
        ]

        if not segments:
            continue

        # Fiscal year from end date
        fiscal_year = int(latest_end[:4])

        return {
            "fiscal_year": fiscal_year,
            "total_revenue_usd": total_rev,
            "segments": segments,
        }

    return None


def _upsert_revenue(db, asset_id: int, country_map: dict[str, int],
                    data: dict) -> int:
    """Upsert stock_country_revenues rows. Returns count inserted/updated."""
    rows = []
    for iso, pct in data["segments"]:
        country_id = country_map.get(iso)
        if not country_id:
            continue
        rows.append({
            "asset_id":       asset_id,
            "country_id":     country_id,
            "revenue_pct":    pct,
            "revenue_usd":    data["total_revenue_usd"] * pct / 100,
            "fiscal_year":    data["fiscal_year"],
            "fiscal_quarter": None,
        })

    if not rows:
        return 0

    stmt = pg_insert(StockCountryRevenue).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_stock_country_revenue",
        set_={"revenue_pct": stmt.excluded.revenue_pct,
              "revenue_usd": stmt.excluded.revenue_usd},
    )
    db.execute(stmt)
    return len(rows)


@app.task(name="edgar_revenue.fetch_all", bind=True, max_retries=2, time_limit=7200)
def fetch_edgar_revenue(self, force_all: bool = False):
    """
    Fetch geographic revenue for all stocks missing data.
    Set force_all=True to refresh existing data too.
    Runs weekly Sunday 02:00 UTC.
    """
    db = SessionLocal()
    try:
        # Build country code → id map
        country_rows = db.execute(select(Country.code, Country.id)).all()
        country_map  = {r.code: r.id for r in country_rows}

        # Get stocks needing data
        if force_all:
            stocks = db.execute(
                select(Asset.id, Asset.symbol)
                .where(Asset.asset_type == AssetType.stock)
            ).all()
        else:
            has_data = select(StockCountryRevenue.asset_id).distinct().scalar_subquery()
            stocks = db.execute(
                select(Asset.id, Asset.symbol)
                .where(Asset.asset_type == AssetType.stock)
                .where(Asset.id.not_in(has_data))
            ).all()

        log.info("EDGAR: %d stocks to process", len(stocks))

        # Fetch CIK map once
        cik_map = _fetch_cik_map()
        time.sleep(0.2)

        success, skipped, errors = 0, 0, 0
        for i, (asset_id, symbol) in enumerate(stocks):
            cik = cik_map.get(symbol.upper())
            if not cik:
                log.debug("%s: no CIK found", symbol)
                skipped += 1
                continue

            data = _fetch_geo_revenue(cik, symbol)
            time.sleep(0.2)  # 5 req/sec max

            if not data:
                log.debug("%s: no geographic revenue data in EDGAR", symbol)
                skipped += 1
                continue

            n = _upsert_revenue(db, asset_id, country_map, data)
            if n:
                db.commit()
                success += 1
                log.info("%s: upserted %d country rows (FY%d)", symbol, n, data["fiscal_year"])
            else:
                skipped += 1

            # Progress log every 50
            if (i + 1) % 50 == 0:
                log.info("EDGAR progress: %d/%d (success=%d skip=%d err=%d)",
                         i + 1, len(stocks), success, skipped, errors)

        log.info("EDGAR complete: success=%d skipped=%d errors=%d", success, skipped, errors)
        return {"processed": len(stocks), "success": success, "skipped": skipped, "errors": errors}

    except Exception as exc:
        db.rollback()
        log.error("EDGAR fetch error: %s", exc)
        raise self.retry(exc=exc, countdown=600)
    finally:
        db.close()


if __name__ == "__main__":
    # Direct run for testing/seeding
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Test single ticker first
    test_ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"\nTesting with {test_ticker}...")
    cik_map = _fetch_cik_map()
    cik = cik_map.get(test_ticker)
    if not cik:
        print(f"No CIK for {test_ticker}")
        sys.exit(1)
    print(f"CIK: {cik}")
    data = _fetch_geo_revenue(cik, test_ticker)
    if data:
        print(f"FY{data['fiscal_year']} — total: ${data['total_revenue_usd']:,.0f}")
        for iso, pct in sorted(data['segments'], key=lambda x: -x[1]):
            print(f"  {iso}: {pct:.1f}%")
    else:
        print("No geographic revenue data found")
