"""
Central bank policy rate fetcher — free public APIs, no auth required.
Stores as interest_rate_pct (monthly) — overrides World Bank annual data with current readings.

Sources (all free, no API key):
  BIS WS_CBPOL     → 38 central banks (AU BR CA CH CL CN CO CZ DK GB HK HU ID IL IN IS JP KR
                      KW MA MK MX MY NO NZ PE PH PL RO RS RU SA SE TH TR US ZA + XM)
  ECB Data Portal  → Eurozone individual countries (AT BE CY DE EE ES FI FR GR IE IT LT LU LV MT NL PT SI SK)
  Bank of Canada   → CA (overrides BIS — same-day decision updates)
  Reserve Bank AU  → AU (overrides BIS)
  Riksbank         → SE (overrides BIS)
  Norges Bank      → NO (overrides BIS)
  Bank of England  → GB (overrides BIS)
  FRED CSV         → US (DFF daily, overrides BIS), JP KR MX TR NZ ZA CZ HU PL DK CH IN ID

Run order: BIS first (baseline) → direct central bank APIs override for most-current data.

Runs daily: 6:15am UTC.
"""

import csv
import logging
from datetime import date, datetime
from io import StringIO

import requests
from sqlalchemy import select
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


# ── Manual fallback rates ──────────────────────────────────────────────────────
# Countries with independent central banks but no machine-readable public API.
# Update this dict when an official rate decision is announced.
# Format: iso2 → (rate_pct, year, month)  e.g. (27.5, 2025, 7)
# Source links in comments.

MANUAL_RATES: dict[str, tuple[float, int, int]] = {
    "NG": (27.50, 2025, 7),   # CBN MPR raised to 27.5% Jul 2025 — cbn.gov.ng
    "GH": (27.00, 2025, 5),   # Bank of Ghana — bankofghana.org
    "ET": (15.00, 2024, 1),   # National Bank of Ethiopia
    "TZ": (7.00,  2024, 6),   # Bank of Tanzania
    "KE": (13.00, 2024, 12),  # Central Bank of Kenya
    "UG": (9.75,  2024, 10),  # Bank of Uganda
    "ZM": (14.00, 2024, 11),  # Bank of Zambia
    "MW": (26.00, 2024, 6),   # Reserve Bank of Malawi
    "SD": (25.00, 2024, 1),   # Central Bank of Sudan
    "AO": (19.50, 2024, 6),   # Banco Nacional de Angola
    "MZ": (14.25, 2024, 12),  # Banco de Moçambique
}

# ── Currency peg inference ─────────────────────────────────────────────────────
# Countries that use USD/EUR/AED directly or maintain hard pegs — no independent CB.
# Their rate = the base currency rate.
# AED pegs exactly to USD (since 1997). XAF/XOF/XPF peg to EUR (CFA franc zone).

USD_PEGGED = {
    "AE",  # UAE — AED pegs to USD, CBUAE mirrors Fed
    "BH",  # Bahrain — BHD pegs to USD (already in BIS but re-affirmed here)
    "EC",  # Ecuador — uses USD directly
    "SV",  # El Salvador — USD legal tender
    "AS",  # American Samoa
    "GU",  # Guam
    "MP",  # N. Mariana Islands
    "PR",  # Puerto Rico
    "VI",  # US Virgin Islands
    "MH",  # Marshall Islands
    "PW",  # Palau
    "TC",  # Turks and Caicos
    "BQ",  # Caribbean Netherlands
    "UM",  # US Minor Outlying Islands
    "IO",  # British Indian Ocean Territory
    "VG",  # British Virgin Islands
}
EUR_PEGGED = {
    "AD",  # Andorra
    "MC",  # Monaco
    "SM",  # San Marino
    "VA",  # Vatican
    "ME",  # Montenegro (uses EUR unilaterally)
    "XK",  # Kosovo
    "AX",  # Åland Islands
    "GF",  # French Guiana
    "GP",  # Guadeloupe
    "MQ",  # Martinique
    "YT",  # Mayotte
    "RE",  # Réunion
    "PM",  # St Pierre & Miquelon
    "BL",  # St Barthélemy
    "MF",  # St Martin
    "TF",  # French Southern Territories
    "CM",  # Cameroon — XAF (CFA franc, EUR peg)
    "CF",  # Central African Republic
    "TD",  # Chad
    "CG",  # Republic of Congo
    "GQ",  # Equatorial Guinea
    "GA",  # Gabon
    "NC",  # New Caledonia — XPF
    "PF",  # French Polynesia
    "WF",  # Wallis and Futuna
}


# ── 0. BIS WS_CBPOL (38 central banks — baseline source) ──────────────────────
# Single call returns all 38 central banks. XM = Eurozone (skip — handled per-country via ECB).
# BIS data is monthly, typically 1-2 months behind. Direct bank APIs below override where fresher.

def fetch_bis() -> list[tuple[str, float, date]]:
    """Fetch BIS central bank policy rates dataset. Returns (iso2, rate, period_date) list."""
    url = "https://stats.bis.org/api/v1/data/WS_CBPOL?startperiod=2024-01-01&format=csv"
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "MetricsHour/1.0"})
        r.raise_for_status()
        reader = csv.DictReader(StringIO(r.text))
        # Keep only monthly rows (FREQ=M), skip Eurozone aggregate (XM)
        latest: dict[str, tuple[float, date]] = {}
        for row in reader:
            if row.get("FREQ") != "M":
                continue
            iso2 = row.get("REF_AREA", "")
            if iso2 == "XM":
                continue
            period_str = row.get("TIME_PERIOD", "")
            obs_str = row.get("OBS_VALUE", "").strip()
            if not obs_str or not period_str:
                continue
            try:
                rate = float(obs_str)
                year, month = period_str.split("-")
                d = date(int(year), int(month), 1)
            except (ValueError, TypeError):
                continue
            if iso2 not in latest or d > latest[iso2][1]:
                latest[iso2] = (rate, d)
        return [(iso2, v[0], v[1]) for iso2, v in latest.items()]
    except Exception:
        log.exception("BIS fetch failed")
        return []


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
    "DFF":               "US",   # US Daily Effective Federal Funds Rate (~1 business day lag)
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
    """Fetch central bank policy rates from official free APIs. Runs daily 6:15am UTC."""
    db = SessionLocal()
    try:
        iso2_map: dict[str, int] = {c.code: c.id for c in db.execute(select(Country.code, Country.id)).all()}
        total = 0

        # ── Pass 1: BIS baseline (38 central banks) ───────────────────────────
        # Upserted first so direct-source feeds below can override on the same period_date.
        log.info("Fetching BIS central bank rates...")
        bis_rows = fetch_bis()
        bis_batch = []
        for iso2, rate, period in bis_rows:
            cid = iso2_map.get(iso2)
            if cid:
                bis_batch.append(_row(cid, rate, period, source="bis"))
        if bis_batch:
            total += _upsert(db, bis_batch)
            db.commit()
        log.info(f"BIS: {len(bis_rows)} country rows")

        # ── Pass 2: direct central bank APIs (more current — override BIS) ────
        direct_batch = []

        # ECB → individual Eurozone countries
        log.info("Fetching ECB rate...")
        ecb_rows = fetch_ecb()
        for iso2, rate, period in ecb_rows:
            cid = iso2_map.get(iso2)
            if cid:
                direct_batch.append(_row(cid, rate, period))
        log.info(f"ECB: {len(ecb_rows)} country rows")

        # Bank of Canada
        log.info("Fetching Bank of Canada rate...")
        result = fetch_bank_of_canada()
        if result:
            cid = iso2_map.get("CA")
            if cid:
                direct_batch.append(_row(cid, result[0], result[1]))
                log.info(f"BoC: {result[0]}% at {result[1]}")

        # RBA
        log.info("Fetching RBA rate...")
        result = fetch_rba()
        if result:
            cid = iso2_map.get("AU")
            if cid:
                direct_batch.append(_row(cid, result[0], result[1]))
                log.info(f"RBA: {result[0]}% at {result[1]}")

        # Riksbank (Sweden)
        log.info("Fetching Riksbank rate...")
        result = fetch_riksbank()
        if result:
            cid = iso2_map.get("SE")
            if cid:
                direct_batch.append(_row(cid, result[0], result[1]))
                log.info(f"Riksbank: {result[0]}% at {result[1]}")

        # Norges Bank (Norway)
        log.info("Fetching Norges Bank rate...")
        result = fetch_norges_bank()
        if result:
            cid = iso2_map.get("NO")
            if cid:
                direct_batch.append(_row(cid, result[0], result[1]))
                log.info(f"Norges Bank: {result[0]}% at {result[1]}")

        # Bank of England
        log.info("Fetching BoE rate...")
        result = fetch_boe()
        if result:
            cid = iso2_map.get("GB")
            if cid:
                direct_batch.append(_row(cid, result[0], result[1]))
                log.info(f"BoE: {result[0]}% at {result[1]}")

        # FRED CSV series
        log.info("Fetching FRED series...")
        for series_id, iso2 in FRED_SERIES.items():
            result = fetch_fred_series(series_id)
            if result:
                cid = iso2_map.get(iso2)
                if cid:
                    direct_batch.append(_row(cid, result[0], result[1], source="fred"))
                    log.info(f"FRED {series_id}/{iso2}: {result[0]}% at {result[1]}")

        if direct_batch:
            total += _upsert(db, direct_batch)
            db.commit()

        # ── Pass 3: manual fallback + peg inference ────────────────────────────
        # Collect the current US and ECB rates from what we just stored
        us_id = iso2_map.get("US")
        de_id = iso2_map.get("DE")  # DE always has ECB rate
        from sqlalchemy import text as sa_text
        def _latest_rate(country_id: int) -> tuple[float, date] | None:
            row = db.execute(
                sa_text(
                    "SELECT value, period_date FROM country_indicators "
                    "WHERE country_id=:cid AND indicator='interest_rate_pct' "
                    "ORDER BY period_date DESC LIMIT 1"
                ),
                {"cid": country_id},
            ).fetchone()
            return (row[0], row[1]) if row else None

        us_rate = _latest_rate(us_id) if us_id else None
        ecb_rate = _latest_rate(de_id) if de_id else None

        fallback_batch = []

        # Manual known rates
        for iso2, (rate, year, month) in MANUAL_RATES.items():
            cid = iso2_map.get(iso2)
            if cid:
                fallback_batch.append(_row(cid, rate, date(year, month, 1), source="manual"))

        # USD-pegged countries
        if us_rate:
            for iso2 in USD_PEGGED:
                cid = iso2_map.get(iso2)
                if cid:
                    fallback_batch.append(_row(cid, us_rate[0], us_rate[1], source="peg_usd"))

        # EUR-pegged countries
        if ecb_rate:
            for iso2 in EUR_PEGGED:
                cid = iso2_map.get(iso2)
                if cid:
                    fallback_batch.append(_row(cid, ecb_rate[0], ecb_rate[1], source="peg_eur"))

        if fallback_batch:
            total += _upsert(db, fallback_batch)
            db.commit()
            log.info(f"Fallback/peg: {len(fallback_batch)} rows")

        log.info(f"Central bank rates: {total} rows upserted")
        return f"ok: {total} rows"

    except Exception as exc:
        db.rollback()
        log.exception("Central bank rates task failed")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
