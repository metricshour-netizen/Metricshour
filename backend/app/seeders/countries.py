"""
Seed all 196 countries from the REST Countries API (no key required).
Idempotent — safe to run multiple times.

Run: python -m app.seeders.countries
"""

import logging
import re
import time
import requests

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Country
from app.seeders.groupings import (
    G7, G20, EU, EUROZONE, NATO, OPEC, BRICS, ASEAN, OECD, COMMONWEALTH,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REST_COUNTRIES_URL = "https://restcountries.com/v3.1/all"

# API limits to 10 fields per request — split into two batches and merge by cca2
FIELDS_BATCH_1 = "cca2,name,cca3,ccn3,capital,region,subregion,area,landlocked,borders"
FIELDS_BATCH_2 = "cca2,languages,currencies,flag,idd,tld,latlng,population,timezones,unMember"


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug


def _extract_calling_code(idd: dict) -> str | None:
    root = idd.get("root", "")
    suffixes = idd.get("suffixes", [])
    if not root:
        return None
    if len(suffixes) == 1:
        return f"{root}{suffixes[0]}"
    return root  # multiple suffixes means large country (US +1-XXX) — store root only


def _build_country_row(raw: dict) -> dict:
    code = raw.get("cca2", "")
    name_common = raw.get("name", {}).get("common", "")
    name_official = raw.get("name", {}).get("official", "")

    # Currency — take first currency in the dict
    currencies = raw.get("currencies", {})
    currency_code = None
    currency_name = None
    currency_symbol = None
    if currencies:
        first_key = next(iter(currencies))
        currency_code = first_key
        currency_name = currencies[first_key].get("name")
        currency_symbol = currencies[first_key].get("symbol")

    # Languages
    languages = list(raw.get("languages", {}).values()) or None

    # Lat/lng
    latlng = raw.get("latlng", [None, None])
    lat = latlng[0] if len(latlng) > 0 else None
    lng = latlng[1] if len(latlng) > 1 else None

    # Calling code
    calling_code = _extract_calling_code(raw.get("idd", {}))

    # TLD
    tld_list = raw.get("tld", [])
    tld = tld_list[0] if tld_list else None

    # Timezone
    timezones = raw.get("timezones", [])
    timezone_main = timezones[0] if timezones else None

    # Borders stored as list of alpha-3 codes (REST Countries uses alpha-3)
    borders = raw.get("borders", []) or None

    return {
        "code": code,
        "code3": raw.get("cca3", ""),
        "numeric_code": raw.get("ccn3") or None,
        "name": name_common,
        "name_official": name_official,
        "capital_city": (raw.get("capital") or [None])[0],
        "flag_emoji": raw.get("flag"),
        "slug": _slugify(name_common),
        "region": raw.get("region"),
        "subregion": raw.get("subregion"),
        "area_km2": raw.get("area"),
        "landlocked": raw.get("landlocked"),
        "island_nation": (
            not raw.get("landlocked", False)
            and not raw.get("borders")
            and bool(raw.get("area"))
        ),
        "latitude": lat,
        "longitude": lng,
        "borders": borders,
        "timezone_main": timezone_main,
        "currency_code": currency_code,
        "currency_name": currency_name,
        "currency_symbol": currency_symbol,
        "official_languages": languages,
        "calling_code": calling_code,
        "tld": tld,
        "un_member": raw.get("unMember", True),
        # Groupings
        "is_g7": code in G7,
        "is_g20": code in G20,
        "is_eu": code in EU,
        "is_eurozone": code in EUROZONE,
        "is_nato": code in NATO,
        "is_opec": code in OPEC,
        "is_brics": code in BRICS,
        "is_asean": code in ASEAN,
        "is_oecd": code in OECD,
        "is_commonwealth": code in COMMONWEALTH,
    }


def fetch_all_countries() -> list[dict]:
    log.info("Fetching all countries from REST Countries API (2 batches)...")
    r1 = requests.get(REST_COUNTRIES_URL, params={"fields": FIELDS_BATCH_1}, timeout=30)
    r1.raise_for_status()
    r2 = requests.get(REST_COUNTRIES_URL, params={"fields": FIELDS_BATCH_2}, timeout=30)
    r2.raise_for_status()

    # Merge by cca2
    batch2 = {c["cca2"]: c for c in r2.json()}
    merged = []
    for country in r1.json():
        code = country.get("cca2")
        if code and code in batch2:
            merged.append({**country, **batch2[code]})
        else:
            merged.append(country)

    log.info(f"Fetched {len(merged)} countries")
    return merged


def seed_countries(db: Session) -> int:
    raw_countries = fetch_all_countries()
    rows = [_build_country_row(r) for r in raw_countries if r.get("cca2")]

    # Upsert — update on conflict with code
    stmt = insert(Country).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["code"],
        set_={
            col: stmt.excluded[col]
            for col in rows[0].keys()
            if col != "code"
        },
    )
    db.execute(stmt)
    db.commit()

    log.info(f"Upserted {len(rows)} countries")
    return len(rows)


def run() -> None:
    db = SessionLocal()
    try:
        total = seed_countries(db)
        log.info(f"Done. {total} countries in database.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
