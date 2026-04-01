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
    "other international":     "INTL",
    "other int'l":             "INTL",
    "other":                   None,
    "all other":               None,
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
    """
    True only if a SINGLE table contains BOTH geo segment header cells AND revenue numbers.
    Prevents false positives where geo keywords/numbers appear in different tables.
    """
    soup = BeautifulSoup(text, "html.parser")
    skip_norms = {"corporate", "total", "eliminations", "other", "worldwide"}
    for table in soup.find_all("table"):
        table_text = table.get_text(" ", strip=True)
        # Skip non-revenue tables (long-lived assets, PP&E, etc.)
        if re.search(r"long.?lived\s+assets|property.*plant.*equipment|total\s+assets"
                     r"|capital\s+expenditure|right.of.use|operating\s+lease", table_text, re.I):
            continue
        geo_count = 0
        num_count = 0
        for td in table.find_all(["td", "th"]):
            cell = td.get_text(" ", strip=True)
            if len(cell) <= 40 and _resolve_seg(cell) is not None:
                if _normalize_seg(cell) not in skip_norms:
                    geo_count += 1
            if re.match(r"^\$?\s*\(?\d{2,3},\d{3}\)?$", cell):
                num_count += 1
        if geo_count >= 2 and num_count >= 3:
            return True
    return False


def _find_geo_r_file(cik: str, accn: str, max_r: int = 200) -> Optional[str]:
    """
    Scan R1..R{max_r}.htm. Among all R-files that pass _r_file_has_geo AND
    yield valid data from _parse_geo_table, return the one with the HIGHEST
    total_revenue_usd.  This ensures we pick the net-sales geo table over
    smaller inventory/assets tables that share the same geographic structure.
    """
    base_cik = str(int(cik))
    best_html: Optional[str] = None
    best_rev: float = 0
    for n in range(1, max_r + 1):
        url = SEC_R_FILE.format(cik=base_cik, accn=accn, n=n)
        r = _get(url, timeout=15)
        if r is None:
            break
        if _r_file_has_geo(r.text):
            table = _find_geo_table(r.text)
            if table:
                parsed = _parse_geo_table(table)
                if parsed is not None:
                    rev = parsed.get("total_revenue_usd", 0)
                    if rev > best_rev:
                        best_rev = rev
                        best_html = r.text
        time.sleep(0.1)
    return best_html


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


def _find_geo_table(html: str):
    """
    Return the BeautifulSoup table element with geo segment headers AND revenue numbers.
    Prefers the SHORTEST qualifying table — avoids outer wrapper tables that contain
    multiple years of nested sub-tables.
    """
    soup = BeautifulSoup(html, "html.parser")
    skip_norms = {"corporate", "total", "eliminations", "other", "worldwide"}
    candidates = []
    for i, table in enumerate(soup.find_all("table")):
        table_text = table.get_text(" ", strip=True)
        # Skip non-revenue tables (long-lived assets, PP&E, balance sheet items)
        if re.search(r"long.?lived\s+assets|property.*plant.*equipment|total\s+assets"
                     r"|capital\s+expenditure|right.of.use|operating\s+lease", table_text, re.I):
            continue
        geo_count = 0
        num_count = 0
        for td in table.find_all(["td", "th"]):
            cell = td.get_text(" ", strip=True)
            if len(cell) <= 40 and _resolve_seg(cell) is not None:
                if _normalize_seg(cell) not in skip_norms:
                    geo_count += 1
            if re.match(r"^\$?\s*\(?\d{2,3},\d{3}\)?$", cell):
                num_count += 1
        if geo_count >= 2 and num_count >= 3:
            text_len = len(table_text)
            # Sort key: most geo cells first, then shortest text, then original order (i)
            # i as tiebreaker prevents TypeError comparing BeautifulSoup Tag objects
            candidates.append((-geo_count, text_len, i, table))
    if not candidates:
        return None
    candidates.sort()          # most geo cells first, then shortest (most specific)
    return candidates[0][3]


def _parse_table_rows(table) -> list[list[str]]:
    """Extract rows as list-of-cell-strings, dropping blank cells."""
    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows


def _parse_geo_table(table) -> Optional[dict]:
    """
    Parse geographic revenue from a BeautifulSoup table element.

    Strategy 1 — structured header rows (most companies):
      Find the row listing segment names (Americas, Europe…), then find the
      Net sales / Revenue row and pair values positionally.

    Strategy 2 — country-level table (U.S. $X China $Y…):
      Use regex to extract (country, value) pairs directly from the text.
    """
    full_text = table.get_text(" ", strip=True)

    # Fiscal year
    years = re.findall(r"\b(202[0-9]|201[5-9])\b", full_text)
    fiscal_year = int(years[0]) if years else 2024

    # Total revenue = largest number in table (millions assumed)
    big_nums = [int(n.replace(",", "")) for n in re.findall(r"\b(\d{2,3},\d{3})\b", full_text)]
    if not big_nums:
        return None
    total_rev = max(big_nums) * 1_000_000

    # ── Strategy 1: find header row with segment names ──────────────────────
    rows = _parse_table_rows(table)
    header_row = None
    header_idx = -1
    for i, row in enumerate(rows):
        matches = sum(1 for cell in row if _resolve_seg(cell) is not None
                      and _normalize_seg(cell) not in
                      {"corporate", "total", "eliminations", "other", "worldwide"})
        if matches >= 2:
            header_row = row
            header_idx = i
            break

    if header_row is not None:
        # Find Net sales / Revenue row after header
        netsales_row = None
        for row in rows[header_idx:]:
            if any(re.search(r"^net.?sales$|^revenues?$|^net.?revenues?$", c, re.I)
                   for c in row):
                netsales_row = row
                break

        if netsales_row:
            # Extract ordered numeric values (skip label + lone "$" cells)
            skip_segs = {"corporate", "total", "eliminations", "other", "worldwide",
                         "total net sales"}
            values: list[float] = []
            for cell in netsales_row:
                m = re.search(r"(\d{2,3},\d{3})", cell)
                if m:
                    v = int(m.group(1).replace(",", "")) * 1_000_000
                    if v > 100_000_000:
                        values.append(float(v))

            # Detect multi-year interleaving: colspan headers produce N values per
            # segment (e.g. 3 fiscal years → [A_Y1,A_Y2,A_Y3, B_Y1,B_Y2,B_Y3, …]).
            # Count resolvable geo segments in the header (skip Total/Corporate/etc.)
            # and use that to compute stride = len(values) // total_cols.
            expected_segs = sum(
                1 for seg in header_row
                if _resolve_seg(seg) is not None
                and _normalize_seg(seg) not in skip_segs
            )
            total_cols = expected_segs + 1  # +1 accounts for the Total column
            if total_cols > 1 and len(values) > total_cols and len(values) % total_cols == 0:
                stride = len(values) // total_cols
                values = [values[i * stride] for i in range(total_cols)]

            pairs: list[tuple] = []
            val_idx = 0
            for seg_label in header_row:
                norm = _normalize_seg(seg_label)
                if norm in skip_segs:
                    val_idx += 1
                    continue
                resolved = _resolve_seg(seg_label)
                if resolved is None:
                    val_idx += 1
                    continue
                if val_idx < len(values):
                    pairs.append((resolved, values[val_idx]))
                val_idx += 1

            if pairs:
                return _build_result(pairs, total_rev, fiscal_year)

    # ── Strategy 3: row-major table (each segment is a row label) ───────────
    # For transposed tables: [North America | $X | $Y | $Z]
    # Strategy 1 requires segments in column headers; this handles the inverse.
    seg_pairs: list[tuple] = []
    for row in rows:
        if len(row) < 2:
            continue
        norm = _normalize_seg(row[0])
        if norm in {"corporate", "total", "eliminations",
                    "other", "worldwide", "total net sales"}:
            continue
        resolved = _resolve_seg(row[0])
        if resolved is None:
            continue
        # Leftmost numeric value = most-recent year.
        # \d{1,3},\d{3} captures $1B+ segments (e.g. "1,907" for CA or MX).
        for cell in row[1:]:
            m = re.search(r"(\d{1,3},\d{3})", cell)
            if m:
                v = int(m.group(1).replace(",", "")) * 1_000_000
                if v > 50_000_000:
                    seg_pairs.append((resolved, float(v)))
                    break
    # Require >= 2 to avoid stopping _find_geo_r_file at a shallow table
    # (e.g. a single "United States" row in a footnote) before the real geo file.
    if len(seg_pairs) >= 2:
        result = _build_result(seg_pairs, total_rev, fiscal_year)
        if result:
            return result

    # ── Strategy 2: country-level regex scan ────────────────────────────────
    country_re = re.compile(
        r"(U\.S\.|United\s+States|China|Japan|Germany|France|United\s+Kingdom|"
        r"Canada|Mexico|Brazil|India|Australia|South\s+Korea|Korea|Singapore|"
        r"Taiwan|Hong\s+Kong|Netherlands|Switzerland|Italy|Spain|Sweden|"
        r"Israel|Saudi\s+Arabia|UAE|International|Rest\s+of\s+World)"
        r"[\s\(\d\)]*(?:\$\s*)?(\d{1,3},\d{3})", re.IGNORECASE
    )
    raw: dict[str, float] = {}
    for m in country_re.finditer(full_text):
        seg = m.group(1).strip()
        val = int(m.group(2).replace(",", "")) * 1_000_000
        if val > 50_000_000:
            norm = _normalize_seg(seg)
            if norm not in raw:
                raw[norm] = float(val)

    if raw:
        pairs = [(_resolve_seg(seg), val) for seg, val in raw.items()
                 if _resolve_seg(seg) is not None]
        return _build_result(pairs, total_rev, fiscal_year)

    return None


def _build_result(pairs, total_rev: float, fiscal_year: int) -> Optional[dict]:
    """Convert (resolved_seg, value) pairs → standard result dict."""
    country_vals: dict[str, float] = {}
    for resolved, val in pairs:
        if isinstance(resolved, list):
            for iso, weight in resolved:
                country_vals[iso] = country_vals.get(iso, 0) + val * weight
        elif isinstance(resolved, str):
            country_vals[resolved] = country_vals.get(resolved, 0) + val

    if not country_vals:
        return None
    seg_total = sum(country_vals.values())
    if seg_total < total_rev * 0.25:
        return None
    segments = [
        (iso, round(val / total_rev * 100, 2))
        for iso, val in country_vals.items()
        if val / total_rev * 100 >= 0.5
    ]
    segments.sort(key=lambda x: -x[1])
    return {"fiscal_year": fiscal_year, "total_revenue_usd": total_rev, "segments": segments}


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

    table = _find_geo_table(html)
    if not table:
        log.debug("%s: no geo table in R-file", ticker)
        return None

    data = _parse_geo_table(table)
    if not data:
        log.debug("%s: could not parse geo revenue from table", ticker)
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
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["AAPL", "MSFT", "NVDA", "JPM", "KO"]

    cik_map = _fetch_cik_map()
    for ticker in tickers:
        ticker = ticker.upper()
        cik = cik_map.get(ticker)
        if not cik:
            print(f"{ticker}: no CIK"); continue
        print(f"\n{ticker} (CIK={cik})")
        data = _fetch_geo_revenue(cik, ticker)
        if data:
            print(f"  FY{data['fiscal_year']} total=${data['total_revenue_usd']/1e9:.1f}B")
            for iso, pct in data["segments"][:8]:
                print(f"    {iso}: {pct:.1f}%")
        else:
            print("  No geographic revenue data found")
        time.sleep(0.3)
