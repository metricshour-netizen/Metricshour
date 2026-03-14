"""
ECB daily FX reference rates — authoritative EUR cross rates.
Source: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml
Runs daily at 6:30am UTC (ECB publishes ~16:00 CET previous day).

Stores rates as:
  1. Price records for EUR FX pairs in `assets` table
  2. CountryIndicator rows: 'eur_fx_rate' (units of local currency per 1 EUR)
"""

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

import requests
from sqlalchemy.dialects.postgresql import insert as pg_insert

from celery_app import app
from app.database import SessionLocal
from app.models.asset import Asset, AssetType, Price
from app.models.country import Country, CountryIndicator

log = logging.getLogger(__name__)

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_NS = "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"

# Currency code → ISO-2 country code (primary country using that currency)
CURRENCY_COUNTRY: dict[str, str] = {
    "USD": "US", "GBP": "GB", "JPY": "JP", "CNY": "CN", "CHF": "CH",
    "AUD": "AU", "CAD": "CA", "SEK": "SE", "NOK": "NO", "DKK": "DK",
    "NZD": "NZ", "SGD": "SG", "HKD": "HK", "KRW": "KR", "INR": "IN",
    "MXN": "MX", "BRL": "BR", "ZAR": "ZA", "TRY": "TR", "PLN": "PL",
    "HUF": "HU", "CZK": "CZ", "RON": "RO", "BGN": "BG", "HRK": "HR",
    "ISK": "IS", "IDR": "ID", "MYR": "MY", "PHP": "PH", "THB": "TH",
    "ILS": "IL", "SAR": "SA", "AED": "AE",
}

# Maps EUR/XXX pair → our asset symbol in the DB
EUR_FX_ASSET_MAP: dict[str, str] = {
    "USD": "EURUSD", "GBP": "EURGBP", "JPY": "EURJPY", "CHF": "EURCHF",
    "AUD": "EURAUD", "CAD": "EURCAD", "CNY": "EURCNY", "SEK": "EURSEK",
    "NOK": "EURNOK", "DKK": "EURDKK", "NZD": "EURNZD", "SGD": "EURSGD",
    "HKD": "EURHKD", "KRW": "EURKRW", "INR": "EURINR", "MXN": "EURMXN",
    "BRL": "EURBRL", "ZAR": "EURZAR", "TRY": "EURTRY", "PLN": "EURPLN",
    "HUF": "EURHUF", "CZK": "EURCZK", "RON": "EURRON",
}


def _parse_ecb_xml() -> tuple[date | None, dict[str, float]]:
    """Fetch and parse ECB XML. Returns (reference_date, {currency: rate})."""
    r = requests.get(ECB_URL, timeout=15)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    # ECB XML structure: Envelope > Cube > Cube[time] > Cube[currency][rate]
    rates: dict[str, float] = {}
    ref_date: date | None = None

    for cube_time in root.iter(f"{{{ECB_NS}}}Cube"):
        time_attr = cube_time.get("time")
        if time_attr:
            ref_date = date.fromisoformat(time_attr)
        currency = cube_time.get("currency")
        rate = cube_time.get("rate")
        if currency and rate:
            rates[currency] = float(rate)

    return ref_date, rates


@app.task(name='tasks.ecb_fx_rates.update_ecb_fx', bind=True, max_retries=3, time_limit=600)
def update_ecb_fx(self):
    """Update ECB EUR reference rates. Runs daily at 6:30am UTC."""
    db = SessionLocal()
    try:
        ref_date, rates = _parse_ecb_xml()
        if not rates:
            log.warning("ECB: empty rate feed")
            return "skipped: no rates"

        log.info(f"ECB: {len(rates)} rates for {ref_date}")
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        # --- 1. Update FX asset prices ---
        price_rows = []
        assets = (
            db.query(Asset)
            .filter(Asset.asset_type == AssetType.fx, Asset.is_active == True)
            .all()
        )
        symbol_to_asset = {a.symbol: a for a in assets}

        for currency, rate in rates.items():
            symbol = EUR_FX_ASSET_MAP.get(currency)
            if symbol and symbol in symbol_to_asset:
                price_rows.append({
                    "asset_id": symbol_to_asset[symbol].id,
                    "timestamp": now,
                    "interval": "1d",
                    "open": None, "high": None, "low": None,
                    "close": rate,
                    "volume": None,
                })

        if price_rows:
            stmt = pg_insert(Price).values(price_rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_price_asset_time_interval",
                set_={"close": stmt.excluded.close},
            )
            db.execute(stmt)

        # --- 2. Store as CountryIndicator for each country's currency ---
        code_to_id: dict[str, int] = {
            c.code: c.id
            for c in db.query(Country.code, Country.id).all()
        }
        indicator_rows = []
        period = ref_date or date.today()

        for currency, rate in rates.items():
            country_code = CURRENCY_COUNTRY.get(currency)
            if not country_code:
                continue
            country_id = code_to_id.get(country_code)
            if not country_id:
                continue
            indicator_rows.append({
                "country_id": country_id,
                "indicator": "eur_fx_rate",
                "value": rate,
                "period_date": period,
                "period_type": "daily",
                "source": "ecb",
            })

        if indicator_rows:
            stmt = pg_insert(CountryIndicator).values(indicator_rows)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_country_indicator_date",
                set_={"value": stmt.excluded.value, "source": stmt.excluded.source},
            )
            db.execute(stmt)

        db.commit()
        log.info(f"ECB FX: {len(price_rows)} prices, {len(indicator_rows)} indicators updated")
        return f"ok: {len(price_rows)} fx prices, {len(indicator_rows)} indicators"

    except Exception as exc:
        db.rollback()
        log.exception("ECB FX update failed")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
