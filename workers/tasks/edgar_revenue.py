"""
Live EDGAR geographic revenue fetcher — R-file parser approach.

For each stock missing stock_country_revenues data:
  1. Lookup CIK via SEC company_tickers.json
  2. Find latest 10-K accession from submissions API
  3. Scan R-files (XBRL viewer) to find the geographic segment note
  4. Parse revenue by geography from the HTML table text
  5. Map segment names → ISO country codes + regional splits
  6. Upsert into stock_country_revenues

Rate limit: ~5 req/sec (SEC fair-use: 10 req/sec max).
Runs: weekly Sunday 02:00 UTC via Celery beat. Also runnable directly.
"""

import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, StockCountryRevenue
from app.models.country import Country

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "MetricsHour info@metricshour.com", "Accept-Encoding": "gzip, deflate"}
SEC_TICKERS_URL  = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS  = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_R_FILE       = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/R{n}.htm"

# Keywords that indicate a geographic segment note
GEO_KEYWORDS = [
    ("Americas",       "Greater China"),
    ("Americas",       "Asia Pacific"),
    ("North America",  "Europe",        "Asia"),
    ("EMEA",           "Asia Pacific"),
    ("United States",  "International"),
    ("Domestic",       "International"),
    ("U.S.",           "International"),
    ("United States",  "Europe",        "China"),
    ("United States",  "Japan"),
    ("Geographic",     "Net sales"),
]

# ── Segment label → ISO2 (single country) or region key ───────────────────────
# Region keys (UPPER) are resolved via REGION_SPLITS below.
SEG_MAP: dict[str, str] = {
    # US-centric
    "united states":           "US",
    "u.s.":                    "US",
    "us":                      "US",
    "domestic":                "US",
    "united states of america":"US",

    # Regions (upper = resolved via REGION_SPLITS)
    "americas":                "AMERICAS",
    "north america":           "NORTHAM",
    "latin america":           "LATAM",
    "south america":           "LATAM",
    "europe":                  "EUROPE",
    "emea":                    "EMEA",
    "middle east and africa":  "MEA",
    "middle east & africa":    "MEA",
    "asia pacific":            "APAC",
    "asia-pacific":            "APAC",
    "apac":                    "APAC",
    "rest of asia pacific":    "APAC",
    "rest of asia":            "APAC",
    "rest of world":           "ROW",
    "rest of the world":       "ROW",
    "international":           "INTL",
    "other":                   None,
    "corporate":               None,
    "other countries":         None,
    "worldwide":               None,

    # Individual countries
    "canada":                  "CA",
    "mexico":                  "MX",
    "brazil":                  "BR",
    "argentina":               "AR",
    "chile":                   "CL",
    "colombia":                "CO",
    "united kingdom":          "GB",
    "uk":                      "GB",
    "germany":                 "DE",
    "france":                  "FR",
    "italy":                   "IT",
    "spain":                   "ES",
    "netherlands":             "NL",
    "switzerland":             "CH",
    "sweden":                  "SE",
    "norway":                  "NO",
    "denmark":                 "DK",
    "austria":                 "AT",
    "belgium":                 "BE",
    "poland":                  "PL",
    "russia":                  "RU",
    "turkey":                  "TR",
    "greater china":           "GCHINA",
    "china":                   "CN",
    "china mainland":          "CN",
    "hong kong":               "HK",
    "taiwan":                  "TW",
    "japan":                   "JP",
    "south korea":             "KR",
    "korea":                   "KR",
    "india":                   "IN",
    "australia":               "AU",
    "new zealand":             "NZ",
    "singapore":               "SG",
    "indonesia":               "ID",
    "thailand":                "TH",
    "malaysia":                "MY",
    "philippines":             "PH",
    "vietnam":                 "VN",
    "saudi arabia":            "SA",
    "uae":                     "AE",
    "united arab emirates":    "AE",
    "israel":                  "IL",
    "egypt":                   "EG",
    "south africa":            "ZA",
    "nigeria":                 "NG",
    "kenya":                   "KE",
    "japan & korea":           "JPKR",
    "japan and korea":         "JPKR",
}

# Regional splits: each key maps to [(iso2, weight)] — weights sum to 1.0
REGION_SPLITS: dict[str, list[tuple[str, float]]] = {
    "AMERICAS": [("US", 0.87), ("CA", 0.05), ("MX", 0.04), ("BR", 0.03), ("AR", 0.01)],
    "NORTHAM":  [("US", 0.88), ("CA", 0.08), ("MX", 0.04)],
    "LATAM":    [("BR", 0.42), ("MX", 0.25), ("AR", 0.12), ("CO", 0.08), ("CL", 0.07), ("PE", 0.06)],
    "EUROPE":   [("DE", 0.20), ("GB", 0.16), ("FR", 0.12), ("IT", 0.09), ("ES", 0.08),
                 ("NL", 0.07), ("CH", 0.06), ("SE", 0.05), ("BE", 0.04), ("PL", 0.04), ("AT", 0.04), ("DK", 0.05)],
    "EMEA":     [("DE", 0.14), ("GB", 0.12), ("FR", 0.09), ("IT", 0.07), ("ES", 0.06),
                 ("NL", 0.06), ("SA", 0.06), ("AE", 0.05), ("CH", 0.05), ("SE", 0.04),
                 ("ZA", 0.04), ("IL", 0.04), ("TR", 0.04), ("BE", 0.04), ("PL", 0.04), ("AT", 0.03), ("EG", 0.03)],
    "MEA":      [("SA", 0.25), ("AE", 0.20), ("ZA", 0.15), ("IL", 0.12), ("EG", 0.10), ("NG", 0.08), ("KE", 0.10)],
    "APAC":     [("CN", 0.42), ("JP", 0.18), ("KR", 0.12), ("AU", 0.10), ("IN", 0.08), ("SG", 0.05), ("TW", 0.05)],
    "GCHINA":   [("CN", 0.83), ("TW", 0.10), ("HK", 0.07)],
    "JPKR":     [("JP", 0.65), ("KR", 0.35)],
    "ROW":      [("GB", 0.10), ("DE", 0.09), ("IN", 0.09), ("BR", 0.08), ("AU", 0.07),
                 ("KR", 0.07), ("MX", 0.06), ("SG", 0.05), ("NL", 0.05), ("CH", 0.05),
                 ("FR", 0.05), ("IT", 0.04), ("ES", 0.04), ("TW", 0.04), ("ID", 0.04), ("SA", 0.04), ("TR", 0.04)],
    "INTL":     [("CN", 0.22), ("JP", 0.10), ("DE", 0.09), ("GB", 0.08), ("FR", 0.06),
                 ("CA", 0.06), ("KR", 0.05), ("AU", 0.05), ("IN", 0.05), ("BR", 0.05),
                 ("IT", 0.04), ("MX", 0.04), ("NL", 0.04), ("TW", 0.04), ("CH", 0.03)],
}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = 20) -> Optional[requests.Response]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r
    except Exception as e:
        log.debug("GET %s failed: %s", url, e)
        return None


# ── CIK + accession lookup ────────────────────────────────────────────────────

def _fetch_cik_map() -> dict[str, str]:
    """Return {TICKER: cik_10digit_padded}."""
    r = _get(SEC_TICKERS_URL, timeout=30)
    if not r:
        return {}
    result = {}
    for entry in r.json().values():
        ticker = entry.get("ticker", "").upper()
        cik = str(entry.get("cik_str", "")).zfill(10)
        if ticker:
            result[ticker] = cik
    return result


def _latest_10k_accession(cik: str) -> Optional[tuple[str, int]]:
    """Return (accession_no_dashes, fiscal_year) for the most recent 10-K, or None."""
    r = _get(SEC_SUBMISSIONS.format(cik=cik), timeout=30)
    if not r:
        return None
    subs = r.json()
    filings = subs.get("filings", {}).get("recent", {})
    forms   = filings.get("form", [])
    accns   = filings.get("accessionNumber", [])
    dates   = filings.get("filingDate", [])
    for form, accn, d in zip(forms, accns, dates):
        if form == "10-K":
            return accn.replace("-", ""), int(d[:4])
    return None


# ── R-file scanner ────────────────────────────────────────────────────────────

def _r_file_has_geo(text: str) -> bool:
    text_l = text.lower()
    for kws in GEO_KEYWORDS:
        if all(kw.lower() in text_l for kw in kws):
            return True
    return False


def _find_geo_r_file(cik: str, accn: str, max_r: int = 200) -> Optional[str]:
    """Scan R1..R{max_r}.htm and return text of first file with geographic revenue."""
    base_cik = str(int(cik))  # strip leading zeros for URL path
    for n in range(1, max_r + 1):
        url = SEC_R_FILE.format(cik=base_cik, accn=accn, n=n)
        r = _get(url, timeout=15)
        if r is None:
            break  # 404 → no more R files
        if _r_file_has_geo(r.text):
            return r.text
        time.sleep(0.1)
    return None


# ── Revenue parser ────────────────────────────────────────────────────────────

def _parse_usd(s: str) -> Optional[float]:
    """Parse '$178,353' or '178,353' → 178353000 (assumes millions)."""
    s = s.strip().replace("$", "").replace(",", "").replace("—", "").replace("(", "-").replace(")", "")
    if not s or s == "-" or s.lower() in ("n/a", "nm", "—"):
        return None
    try:
        return float(s) * 1_000_000  # EDGAR tables are in millions
    except ValueError:
        return None


def _normalize_seg(label: str) -> str:
    """Strip footnote markers, extra whitespace, lowercase."""
    label = re.sub(r"\(\d+\)|\*|\†|\‡", "", label)
    label = re.sub(r"\s+", " ", label).strip().lower()
    return label


def _resolve_seg(label: str) -> Optional[str | list[tuple[str, float]]]:
    """
    Return ISO2 string, or list[(iso2, weight)] for regional splits, or None to skip.
    """
    norm = _normalize_seg(label)
    code = SEG_MAP.get(norm)
    if code is None:
        # Partial match fallbacks
        for key, val in SEG_MAP.items():
            if key in norm:
                code = val
                break
    if code is None:
        return None
    if code in REGION_SPLITS:
        return REGION_SPLITS[code]
    return code  # direct ISO2


def _extract_text_blob(html: str) -> str:
    """Return the largest text cell from the R-file (contains the full note text)."""
    soup = BeautifulSoup(html, "html.parser")
    texts = [td.get_text(" ", strip=True) for td in soup.find_all("td")]
    if not texts:
        return html
    return max(texts, key=len)


def _parse_geo_from_text(text: str) -> Optional[dict]:
    """
    Parse geographic revenue from the EDGAR note text blob.
    Returns {fiscal_year, total_revenue_usd, segments: [(iso2, pct)]} or None.
    """
    # ── Try to find a "Net sales" line with segments ────────────────────────
    # Pattern 1: regional table  "AmericasEuropeGreater ChinaJapanRest of Asia PacificTotal Net sales $X $Y..."
    # Pattern 2: country table   "Net sales: U.S. $X China $Y Other countries $Z Total $T"

    # Step 1: find years mentioned
    years = re.findall(r"\b(202[0-9]|201[5-9])\b", text)
    fiscal_year = int(years[0]) if years else 2024

    # Step 2: find total revenue (largest dollar figure)
    all_dollars = [_parse_usd(m) for m in re.findall(r"\$[\d,]+", text)]
    all_dollars = [v for v in all_dollars if v and v > 1_000_000_000]  # > $1B
    if not all_dollars:
        return None
    total_rev = max(all_dollars)

    # Step 3: look for "Net sales" followed by dollar values
    # Try to find a segment block: header labels + "Net sales" row with values
    # Common patterns:
    # a) "AmericasEuropeGreater ChinaJapanRest of Asia PacificNet sales$178,353$111,032$64,377$28,703$33,696"
    # b) "United States International Total Net sales $ 100,000 $ 50,000 $ 150,000"
    # c) "U.S. $138,573 China $72,559 Other countries $172,153 Total $383,285"

    # Extract all (label, value) pairs by scanning for known segment names near dollar amounts
    raw: dict[str, float] = {}

    # Pattern: "U.S. $151,790" or "China(1) 64,377" country-level table
    country_pattern = re.compile(
        r"(U\.S\.|United States|China|Japan|Germany|France|United Kingdom|UK|Canada|"
        r"Mexico|Brazil|India|Australia|South Korea|Korea|Singapore|Taiwan|Hong Kong|"
        r"Netherlands|Switzerland|Italy|Spain|Sweden|Israel|Saudi Arabia|UAE|"
        r"Rest of World|International|Other countries)"
        r"[\s\(\d\)]*\$?\s*([\d,]+)", re.IGNORECASE
    )
    for m in country_pattern.finditer(text):
        seg   = m.group(1).strip()
        val   = _parse_usd(m.group(2))
        if val and val > 100_000_000:  # > $100M
            norm = _normalize_seg(seg)
            raw[norm] = val

    # Pattern: regional labels in text before dollar amounts
    # Find "Net sales" followed by a sequence of dollar values, then match to nearby segment headers
    netsales_match = re.search(
        r"Net sales[^\$]*(\$[\d,]+(?:[^\$]*\$[\d,]+){1,10})", text, re.IGNORECASE
    )
    if netsales_match and not raw:
        values_str = netsales_match.group(1)
        values = [_parse_usd(v) for v in re.findall(r"\$[\d,]+", values_str)]
        values = [v for v in values if v and v > 100_000_000]

        # Find segment labels preceding this match
        before = text[:netsales_match.start()]
        seg_labels = []
        for seg_name in SEG_MAP:
            if seg_name in before.lower()[-500:]:
                seg_labels.append(seg_name)

        if seg_labels and values:
            for label, val in zip(seg_labels, values):
                raw[label] = val

    if not raw:
        return None

    # Remove "other countries", "total", "worldwide" etc.
    skip_keys = {"other countries", "other", "total", "worldwide", "total net sales",
                 "corporate", "eliminations", None}

    # Build country-level map
    country_vals: dict[str, float] = {}
    for seg, val in raw.items():
        resolved = _resolve_seg(seg)
        if resolved is None or seg in skip_keys:
            continue
        if isinstance(resolved, list):
            for iso, weight in resolved:
                country_vals[iso] = country_vals.get(iso, 0) + val * weight
        else:
            country_vals[resolved] = country_vals.get(resolved, 0) + val

    if not country_vals:
        return None

    # Compute percentages relative to total_rev
    seg_total = sum(country_vals.values())
    if seg_total < total_rev * 0.3:
        # Segment total is too small relative to reported total — data mismatch
        return None

    segments = [
        (iso, round(val / total_rev * 100, 2))
        for iso, val in country_vals.items()
        if val / total_rev * 100 >= 0.5
    ]
    segments.sort(key=lambda x: -x[1])

    return {
        "fiscal_year": fiscal_year,
        "total_revenue_usd": total_rev,
        "segments": segments,
    }


# ── Main per-ticker function ──────────────────────────────────────────────────

def _fetch_geo_revenue(cik: str, ticker: str) -> Optional[dict]:
    """Return parsed geographic revenue dict or None."""
    result = _latest_10k_accession(cik)
    time.sleep(0.2)
    if not result:
        return None
    accn, _ = result

    html = _find_geo_r_file(cik, accn)
    if not html:
        log.debug("%s: no geographic R-file found", ticker)
        return None

    text = _extract_text_blob(html)
    data = _parse_geo_from_text(text)
    if not data:
        log.debug("%s: could not parse geo revenue from R-file", ticker)
    return data


# ── DB upsert ─────────────────────────────────────────────────────────────────

def _upsert_revenue(db, asset_id: int, country_map: dict[str, int], data: dict) -> int:
    rows = []
    for iso, pct in data["segments"]:
        cid = country_map.get(iso)
        if not cid:
            continue
        rows.append({
            "asset_id":       asset_id,
            "country_id":     cid,
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


# ── Celery task ───────────────────────────────────────────────────────────────

@app.task(name="edgar_revenue.fetch_all", bind=True, max_retries=2, time_limit=7200)
def fetch_edgar_revenue(self, force_all: bool = False):
    """
    Fetch geographic revenue for all stocks missing data.
    force_all=True refreshes existing data too.
    Runs weekly Sunday 02:00 UTC.
    """
    db = SessionLocal()
    try:
        country_map = {r.code: r.id for r in db.execute(
            select(Country.code, Country.id)).all()}

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
        cik_map = _fetch_cik_map()
        time.sleep(0.3)

        success = skipped = errors = 0
        for i, (asset_id, symbol) in enumerate(stocks):
            cik = cik_map.get(symbol.upper())
            if not cik:
                skipped += 1
                continue
            try:
                data = _fetch_geo_revenue(cik, symbol)
                if not data:
                    skipped += 1
                    continue
                n = _upsert_revenue(db, asset_id, country_map, data)
                if n:
                    db.commit()
                    success += 1
                    log.info("%s FY%d: %d country rows", symbol, data["fiscal_year"], n)
                else:
                    skipped += 1
            except Exception as e:
                log.warning("%s: error: %s", symbol, e)
                errors += 1

            if (i + 1) % 50 == 0:
                log.info("EDGAR %d/%d success=%d skip=%d err=%d",
                         i + 1, len(stocks), success, skipped, errors)

        log.info("EDGAR done: success=%d skipped=%d errors=%d", success, skipped, errors)
        return {"processed": len(stocks), "success": success, "skipped": skipped, "errors": errors}

    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=600)
    finally:
        db.close()


# ── Direct test run ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ticker = (sys.argv[1] if len(sys.argv) > 1 else "AAPL").upper()

    cik_map = _fetch_cik_map()
    cik = cik_map.get(ticker)
    if not cik:
        print(f"No CIK for {ticker}")
        sys.exit(1)
    print(f"{ticker} CIK={cik}")
    data = _fetch_geo_revenue(cik, ticker)
    if data:
        print(f"FY{data['fiscal_year']} total=${data['total_revenue_usd']:,.0f}")
        for iso, pct in data["segments"]:
            print(f"  {iso}: {pct:.1f}%")
    else:
        print("No geographic revenue data found")
