"""
Central bank policy rate fetcher — free public APIs, no auth required.
Stores as interest_rate_pct (monthly) — overrides World Bank annual data with current readings.

Sources (all free, no API key):
  ECB Data Portal  → Eurozone (20 countries)
  Bank of Canada   → CA
  Reserve Bank AU  → AU
  Riksbank         → SE
  Norges Bank      → NO
  Bank of England  → GB
  FRED CSV         → US, JP, KR, MX, TR, NZ, ZA, CZ, HU, PL, DK, CH, IN, ID, TH

Runs weekly: Sunday 2am UTC.
"""

import logging
from datetime import date, datetime
from io import StringIO

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.country import Country, CountryIndicator

log = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────────────────

def _upsert(db, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(CountryIndicator).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_country_indicator_date",
        set_={"value": stmt.excluded.value, "source": stmt.excluded.source},
    )
    db.execute(stmt)
    return len(rows)


def _row(country_id: int, value: float, period: date, source: str = "central_bank") -> dict:
    return {
        "country_id": country_id,
        "indicator": "interest_rate_pct",
        "value": value,
        "period_date": period,
        "period_type": "monthly",
        "source": source,
    }


# ── 1. ECB (Eurozone) ──────────────────────────────────────────────────────────
# One API call → rate for all 20 Eurozone countries

EUROZONE_ISO2 = [
    "AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR",
    "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PT", "SI", "SK",
]

def fetch_ecb() -> list[tuple[str, float, date]]:
    """Returns list of (iso2, rate, period_date) — same rate for all Eurozone countries."""
    url = (
        "https://data-api.ecb.europa.eu/service/data/FM"
        "/B.U2.EUR.4F.KR.MRR_FR.LEV"
        "?format=csvdata&detail=dataonly&lastNObservations=3"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        lines = [l for l in r.text.strip().splitlines() if l and not l.startswith("KEY")]
        if not lines:
            return []
        # Last line = most recent
        last = lines[-1].split(",")
        period_str, value_str = last[-2], last[-1]
        rate = float(value_str)
        d = datetime.strptime(period_str.strip(), "%Y-%m-%d").date()
        period = date(d.year, d.month, 1)
        return [(iso2, rate, period) for iso2 in EUROZONE_ISO2]
    except Exception:
        log.exception("ECB fetch failed")
        return []


# ── 2. Bank of Canada ──────────────────────────────────────────────────────────

def fetch_bank_of_canada() -> tuple[float, date] | None:
    """Target overnight rate from Bank of Canada Valet API."""
    url = "https://www.bankofcanada.ca/valet/observations/V39079/json?recent=3"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        if not obs:
            return None
        latest = obs[0]  # most recent first
        d = datetime.strptime(latest["d"], "%Y-%m-%d").date()
        rate = float(latest["V39079"]["v"])
        return rate, date(d.year, d.month, 1)
    except Exception:
        log.exception("Bank of Canada fetch failed")
        return None


# ── 3. Reserve Bank of Australia ───────────────────────────────────────────────

def fetch_rba() -> tuple[float, date] | None:
    """Cash rate target from RBA F1 table CSV."""
    url = "https://www.rba.gov.au/statistics/tables/csv/f1-data.csv"
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "MetricsHour/1.0"})
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        # Header rows: skip until we find data rows (lines starting with a date like "04-Jan-")
        data_lines = [l for l in lines if l and l[0].isdigit() or (len(l) > 2 and l[2] == "-")]
        # Filter actual date rows
        data_lines = [l for l in lines if len(l) > 5 and "-" in l[:10] and l[0].isdigit()]
        if not data_lines:
            return None
        last = data_lines[-1].split(",")
        date_str = last[0].strip()
        value_str = last[1].strip()
        if not value_str:
            return None
        rate = float(value_str)
        d = datetime.strptime(date_str, "%d-%b-%Y").date()
        return rate, date(d.year, d.month, 1)
    except Exception:
        log.exception("RBA fetch failed")
        return None


# ── 4. Riksbank (Sweden) ───────────────────────────────────────────────────────

def fetch_riksbank() -> tuple[float, date] | None:
    """Swedish policy rate from Riksbank open API."""
    today = date.today()
    url = f"https://api.riksbank.se/swea/v1/Observations/SECBREPOEFF/{today.year}-01-01/{today.isoformat()}"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        latest = data[-1]
        d = datetime.strptime(latest["date"], "%Y-%m-%d").date()
        return float(latest["value"]), date(d.year, d.month, 1)
    except Exception:
        log.exception("Riksbank fetch failed")
        return None


# ── 5. Norges Bank (Norway) ────────────────────────────────────────────────────

def fetch_norges_bank() -> tuple[float, date] | None:
    """Norwegian policy rate from Norges Bank SDMX-JSON API."""
    url = "https://data.norges-bank.no/api/data/IR/B.KPRA.SD.?format=sdmx-json&startPeriod=2024-01-01&locale=en"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        ds = data["data"]["dataSets"][0]
        series = ds.get("series", {})
        if not series:
            return None
        obs = next(iter(series.values())).get("observations", {})
        if not obs:
            return None
        time_vals = data["data"]["structure"]["dimensions"]["observation"][0]["values"]
        max_idx = max(int(k) for k in obs.keys())
        rate = float(obs[str(max_idx)][0])
        period_str = time_vals[max_idx]["id"]  # e.g. "2026-02-26"
        d = datetime.strptime(period_str, "%Y-%m-%d").date()
        return rate, date(d.year, d.month, 1)
    except Exception:
        log.exception("Norges Bank fetch failed")
        return None


# ── 6. Bank of England ─────────────────────────────────────────────────────────

def fetch_boe() -> tuple[float, date] | None:
    """Official Bank Rate from BoE database API."""
    today = date.today()
    url = (
        "https://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp"
        f"?csv.x=yes&Datefrom=01/Jan/2025&Dateto={today.strftime('%d/%b/%Y')}"
        "&SeriesCodes=IUDBEDR&CSVF=TT&UsingCodes=Y"
    )
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "MetricsHour/1.0"})
        r.raise_for_status()
        lines = [l for l in r.text.strip().splitlines() if l]
        # Skip 4-row header block, find data rows
        data_lines = [l for l in lines if l[0].isdigit()]
        if not data_lines:
            return None
        last = data_lines[-1].split(",")
        date_str = last[0].strip()
        value_str = last[1].strip()
        if not value_str:
            return None
        rate = float(value_str)
        d = datetime.strptime(date_str, "%d %b %Y").date()
        return rate, date(d.year, d.month, 1)
    except Exception:
        log.exception("Bank of England fetch failed")
        return None


# ── 7. FRED CSV (no API key needed for graph CSV endpoint) ─────────────────────
# Monthly series. Maps FRED series_id → ISO2 country code.

FRED_SERIES: dict[str, str] = {
    "FEDFUNDS":          "US",   # US Federal Funds Rate (monthly avg)
    "IRSTCI01JPM156N":   "JP",   # Japan 3-month rate
    "IRSTCI01KRM156N":   "KR",   # South Korea
    "IRSTCI01MXM156N":   "MX",   # Mexico
    "IRSTCI01TRM156N":   "TR",   # Turkey
    "IRSTCI01NZM156N":   "NZ",   # New Zealand
    "IRSTCI01ZAM156N":   "ZA",   # South Africa
    "IRSTCI01CZM156N":   "CZ",   # Czech Republic
    "IRSTCI01HUM156N":   "HU",   # Hungary
    "IRSTCI01PLM156N":   "PL",   # Poland
    "IRSTCI01DKM156N":   "DK",   # Denmark
    "IRSTCI01CHM156N":   "CH",   # Switzerland
    "IRSTCI01INM156N":   "IN",   # India
    "IRSTCI01IDM156N":   "ID",   # Indonesia
}

def fetch_fred_series(series_id: str) -> tuple[float, date] | None:
    """Fetch latest value from FRED public CSV export (no API key needed)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "MetricsHour/1.0"})
        r.raise_for_status()
        lines = [l for l in r.text.strip().splitlines() if l and not l.startswith("DATE")]
        if not lines:
            return None
        # Filter out missing values
        valid = [l for l in lines if "." in l.split(",")[1] and l.split(",")[1].strip() != "."]
        if not valid:
            return None
        last = valid[-1].split(",")
        d = datetime.strptime(last[0].strip(), "%Y-%m-%d").date()
        rate = float(last[1].strip())
        return rate, date(d.year, d.month, 1)
    except Exception:
        log.exception(f"FRED fetch failed: {series_id}")
        return None


# ── Main Celery task ────────────────────────────────────────────────────────────

@app.task(name="tasks.central_bank_rates.fetch_central_bank_rates", bind=True, max_retries=2)
def fetch_central_bank_rates(self):
    """Fetch central bank policy rates from official free APIs. Runs weekly Sunday 2am UTC."""
    db = SessionLocal()
    try:
        iso2_map: dict[str, int] = {c.code: c.id for c in db.query(Country.code, Country.id).all()}
        total = 0
        batch = []

        # 1. ECB → Eurozone
        log.info("Fetching ECB rate...")
        ecb_rows = fetch_ecb()
        for iso2, rate, period in ecb_rows:
            cid = iso2_map.get(iso2)
            if cid:
                batch.append(_row(cid, rate, period))
        log.info(f"ECB: {len(ecb_rows)} country rows")

        # 2. Bank of Canada
        log.info("Fetching Bank of Canada rate...")
        result = fetch_bank_of_canada()
        if result:
            cid = iso2_map.get("CA")
            if cid:
                batch.append(_row(cid, result[0], result[1]))
                log.info(f"BoC: {result[0]}% at {result[1]}")

        # 3. RBA
        log.info("Fetching RBA rate...")
        result = fetch_rba()
        if result:
            cid = iso2_map.get("AU")
            if cid:
                batch.append(_row(cid, result[0], result[1]))
                log.info(f"RBA: {result[0]}% at {result[1]}")

        # 4. Riksbank (Sweden)
        log.info("Fetching Riksbank rate...")
        result = fetch_riksbank()
        if result:
            cid = iso2_map.get("SE")
            if cid:
                batch.append(_row(cid, result[0], result[1]))
                log.info(f"Riksbank: {result[0]}% at {result[1]}")

        # 5. Norges Bank (Norway)
        log.info("Fetching Norges Bank rate...")
        result = fetch_norges_bank()
        if result:
            cid = iso2_map.get("NO")
            if cid:
                batch.append(_row(cid, result[0], result[1]))
                log.info(f"Norges Bank: {result[0]}% at {result[1]}")

        # 6. Bank of England
        log.info("Fetching BoE rate...")
        result = fetch_boe()
        if result:
            cid = iso2_map.get("GB")
            if cid:
                batch.append(_row(cid, result[0], result[1]))
                log.info(f"BoE: {result[0]}% at {result[1]}")

        # 7. FRED CSV series
        log.info("Fetching FRED series...")
        for series_id, iso2 in FRED_SERIES.items():
            result = fetch_fred_series(series_id)
            if result:
                cid = iso2_map.get(iso2)
                if cid:
                    batch.append(_row(cid, result[0], result[1], source="fred"))
                    log.info(f"FRED {series_id}/{iso2}: {result[0]}% at {result[1]}")

        # Upsert all
        if batch:
            total = _upsert(db, batch)
            db.commit()

        log.info(f"Central bank rates: {total} rows upserted")
        return f"ok: {total} rows"

    except Exception as exc:
        db.rollback()
        log.exception("Central bank rates task failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
