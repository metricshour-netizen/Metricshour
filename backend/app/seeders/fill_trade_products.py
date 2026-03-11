"""
Fill top_export_products / top_import_products for trade pairs that have
bilateral volume data but no product breakdown.

Strategy: uses a per-country top-exports lookup (based on WTO/UN Comtrade
annual reports). Not bilateral-specific but accurate for the country's
principal export commodities, which is what most users want to see.

Run:  python seed.py --only fill_products
      python seed.py --only fill_products --refresh   (overwrite all pairs incl. those with data)
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Country, TradePair

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

B = 1_000_000_000


def _p(name: str, value_b: float) -> dict:
    return {"name": name, "value_usd": int(value_b * B)}


# Country ISO2 → top 5 export products (WTO / UN Comtrade 2022-2023 data)
# value_b = approximate annual export value in USD billions (world total, not bilateral)
COUNTRY_TOP_EXPORTS: dict[str, list[dict]] = {
    "US": [_p("petroleum products", 180), _p("machinery", 120), _p("aircraft", 90), _p("electronics", 85), _p("vehicles", 70)],
    "CN": [_p("electronics", 620), _p("machinery", 510), _p("textiles & apparel", 180), _p("steel", 110), _p("chemicals", 90)],
    "DE": [_p("vehicles", 260), _p("machinery", 220), _p("chemicals", 130), _p("pharmaceuticals", 90), _p("electronics", 80)],
    "JP": [_p("vehicles", 140), _p("machinery", 130), _p("electronics", 100), _p("chemicals", 50), _p("precision instruments", 40)],
    "GB": [_p("machinery", 70), _p("pharmaceuticals", 65), _p("vehicles", 55), _p("petroleum products", 50), _p("chemicals", 40)],
    "FR": [_p("aircraft", 65), _p("machinery", 60), _p("pharmaceuticals", 55), _p("chemicals", 45), _p("wines & spirits", 22)],
    "KR": [_p("semiconductors", 130), _p("ships", 55), _p("vehicles", 50), _p("electronics", 90), _p("petrochemicals", 40)],
    "NL": [_p("petroleum products", 120), _p("chemicals", 70), _p("machinery", 55), _p("food & beverages", 50), _p("electronics", 40)],
    "IT": [_p("machinery", 100), _p("vehicles", 55), _p("pharmaceuticals", 45), _p("chemicals", 40), _p("fashion & luxury", 35)],
    "CA": [_p("petroleum", 130), _p("vehicles", 70), _p("machinery", 50), _p("gold", 20), _p("chemicals", 18)],
    "AU": [_p("iron ore", 120), _p("coal", 75), _p("liquefied natural gas", 70), _p("gold", 25), _p("meat", 15)],
    "BE": [_p("chemicals", 90), _p("pharmaceuticals", 70), _p("machinery", 40), _p("petroleum products", 35), _p("vehicles", 25)],
    "MX": [_p("vehicles", 95), _p("electronics", 85), _p("machinery", 55), _p("petroleum products", 30), _p("medical devices", 20)],
    "ES": [_p("vehicles", 50), _p("machinery", 40), _p("chemicals", 30), _p("food & beverages", 28), _p("pharmaceuticals", 22)],
    "CH": [_p("pharmaceuticals", 100), _p("machinery", 55), _p("watches & precision instruments", 30), _p("chemicals", 28), _p("precious metals", 25)],
    "RU": [_p("petroleum & natural gas", 230), _p("metals", 40), _p("chemicals & fertilizers", 30), _p("wheat", 12), _p("arms", 8)],
    "IN": [_p("pharmaceuticals", 25), _p("petroleum products", 90), _p("diamonds & jewellery", 30), _p("machinery", 22), _p("textiles & apparel", 18)],
    "BR": [_p("soybeans", 55), _p("iron ore", 45), _p("petroleum", 40), _p("meat", 20), _p("aircraft", 15)],
    "TW": [_p("semiconductors", 180), _p("electronics", 130), _p("machinery", 40), _p("petrochemicals", 22), _p("steel", 15)],
    "SG": [_p("electronics", 110), _p("petroleum products", 70), _p("machinery", 45), _p("chemicals", 35), _p("gold", 18)],
    "SE": [_p("machinery", 30), _p("vehicles", 20), _p("pharmaceuticals", 18), _p("paper & pulp", 12), _p("electronics", 10)],
    "PL": [_p("machinery", 35), _p("vehicles", 25), _p("electronics", 20), _p("chemicals", 15), _p("food & beverages", 12)],
    "NO": [_p("petroleum & natural gas", 130), _p("fish & seafood", 14), _p("machinery", 10), _p("chemicals", 8), _p("metals", 7)],
    "AT": [_p("machinery", 25), _p("vehicles", 18), _p("chemicals", 15), _p("pharmaceuticals", 12), _p("electronics", 10)],
    "DK": [_p("pharmaceuticals", 25), _p("machinery", 18), _p("food & beverages", 15), _p("chemicals", 10), _p("medical instruments", 8)],
    "AE": [_p("petroleum products", 130), _p("gold & precious metals", 60), _p("electronics", 30), _p("aluminum", 10), _p("chemicals", 8)],
    "SA": [_p("petroleum", 280), _p("chemicals & plastics", 25), _p("petroleum products", 22), _p("metals", 6), _p("machinery", 5)],
    "TH": [_p("electronics", 45), _p("vehicles", 20), _p("machinery", 18), _p("rubber", 12), _p("food & beverages", 10)],
    "MY": [_p("electronics", 100), _p("petroleum", 22), _p("palm oil", 18), _p("chemicals", 12), _p("rubber", 8)],
    "ID": [_p("coal", 38), _p("palm oil", 28), _p("iron ore & metals", 14), _p("electronics", 10), _p("rubber", 7)],
    "ZA": [_p("platinum & palladium", 14), _p("vehicles", 10), _p("iron ore & steel", 9), _p("gold", 8), _p("coal", 7)],
    "TR": [_p("machinery", 22), _p("vehicles", 18), _p("iron & steel", 12), _p("apparel", 18), _p("chemicals", 8)],
    "AR": [_p("soybeans & soybean products", 20), _p("meat", 8), _p("corn", 7), _p("petroleum", 6), _p("vehicles", 4)],
    "CL": [_p("copper", 45), _p("lithium", 8), _p("fruit & nuts", 7), _p("fish & seafood", 5), _p("wine", 3)],
    "CO": [_p("petroleum", 18), _p("coal", 8), _p("coffee", 4), _p("gold", 3), _p("flowers", 2)],
    "PE": [_p("copper", 14), _p("gold", 8), _p("zinc", 5), _p("petroleum", 4), _p("fish products", 4)],
    "PH": [_p("electronics", 45), _p("machinery", 10), _p("coconut oil", 3), _p("apparel", 3), _p("vegetables", 2)],
    "VN": [_p("electronics", 110), _p("machinery", 40), _p("apparel & footwear", 35), _p("furniture", 12), _p("food & beverages", 10)],
    "PK": [_p("textiles & apparel", 18), _p("cotton", 4), _p("leather goods", 3), _p("chemicals", 2), _p("food products", 2)],
    "BD": [_p("apparel & garments", 45), _p("textiles", 8), _p("leather goods", 2), _p("jute", 1), _p("seafood", 1)],
    "EG": [_p("petroleum products", 8), _p("textiles", 3), _p("food products", 2), _p("chemicals", 2), _p("metals", 1)],
    "NG": [_p("petroleum", 40), _p("liquefied natural gas", 10), _p("cocoa", 1), _p("sesame", 1), _p("cotton", 0.5)],
    "KE": [_p("tea", 2), _p("coffee", 1), _p("cut flowers", 1), _p("vegetables & fruit", 1), _p("petroleum products", 0.8)],
    "GH": [_p("cocoa", 3), _p("gold", 7), _p("petroleum", 4), _p("manganese", 1), _p("cashews", 0.5)],
    "QA": [_p("liquefied natural gas", 65), _p("petroleum", 20), _p("chemicals", 5), _p("aluminum", 3), _p("plastics", 2)],
    "IR": [_p("petroleum", 30), _p("chemicals & petrochemicals", 5), _p("pistachios & fruits", 3), _p("plastics", 2), _p("carpets", 1)],
    "IQ": [_p("petroleum", 85), _p("natural gas", 2), _p("gold", 0.5), _p("dates", 0.3), _p("chemicals", 0.2)],
    "KW": [_p("petroleum", 40), _p("petroleum products", 8), _p("chemicals", 2), _p("fertilizers", 1), _p("plastics", 0.8)],
    "NZ": [_p("dairy products", 12), _p("meat", 8), _p("fruit & nuts", 5), _p("wool", 2), _p("fish & seafood", 2)],
    "HK": [_p("electronics", 200), _p("machinery", 40), _p("gold & precious metals", 30), _p("diamonds & jewellery", 20), _p("chemicals", 10)],
    "CZ": [_p("machinery", 30), _p("vehicles", 22), _p("electronics", 18), _p("chemicals", 8), _p("plastics", 5)],
    "RO": [_p("machinery", 10), _p("vehicles", 8), _p("electronics", 6), _p("chemicals", 4), _p("food products", 3)],
    "HU": [_p("vehicles", 15), _p("machinery", 12), _p("electronics", 10), _p("pharmaceuticals", 5), _p("chemicals", 4)],
    "PT": [_p("vehicles", 10), _p("machinery", 8), _p("chemicals", 5), _p("food & beverages", 5), _p("apparel", 4)],
    "FI": [_p("machinery", 8), _p("electronics", 7), _p("paper & pulp", 6), _p("chemicals", 5), _p("ships", 4)],
    "GR": [_p("petroleum products", 10), _p("food & beverages", 6), _p("chemicals", 4), _p("machinery", 3), _p("aluminum", 2)],
    "UA": [_p("wheat & grain", 8), _p("iron ore & steel", 7), _p("sunflower oil", 4), _p("corn", 3), _p("machinery", 2)],
    "IL": [_p("diamonds", 7), _p("electronics", 10), _p("pharmaceuticals", 5), _p("machinery", 4), _p("chemicals", 3)],
    "CU": [_p("nickel", 1), _p("sugar", 0.5), _p("tobacco & cigars", 0.4), _p("seafood", 0.3), _p("medical services", 3)],
    "ET": [_p("coffee", 1), _p("cut flowers", 1), _p("sesame", 0.5), _p("vegetables", 0.3), _p("leather", 0.3)],
    "TZ": [_p("gold", 2), _p("coffee", 0.4), _p("tea", 0.3), _p("cashews", 0.3), _p("tobacco", 0.2)],
    "MZ": [_p("liquefied natural gas", 3), _p("aluminum", 1), _p("coal", 0.5), _p("tobacco", 0.3), _p("cashews", 0.2)],
    "ZM": [_p("copper", 6), _p("cobalt", 1), _p("tobacco", 0.3), _p("sugar", 0.2), _p("cotton", 0.1)],
    "AO": [_p("petroleum", 25), _p("diamonds", 2), _p("petroleum products", 1), _p("fish", 0.4), _p("chemicals", 0.2)],
    "MW": [_p("tobacco", 0.5), _p("tea", 0.1), _p("sugar", 0.1), _p("cotton", 0.05), _p("coffee", 0.05)],
}

# Fallback for countries not in the map — generic manufactured goods
_FALLBACK_PRODUCTS = [
    _p("machinery & equipment", 5),
    _p("manufactured goods", 4),
    _p("chemicals", 3),
    _p("food & beverages", 2),
    _p("raw materials", 1),
]


def _scale_products(products: list[dict], actual_exports_usd: float | None) -> list[dict]:
    """
    Scale product values proportionally to match actual bilateral exports_usd.
    If actual_exports_usd is unknown, return products as-is.
    """
    if not products or not actual_exports_usd or actual_exports_usd <= 0:
        return products
    total_base = sum(p["value_usd"] for p in products)
    if total_base <= 0:
        return products
    ratio = actual_exports_usd / total_base
    return [{"name": p["name"], "value_usd": max(1, int(p["value_usd"] * ratio))} for p in products]


def fill_trade_products(db: Session, refresh: bool = False) -> None:
    countries = db.execute(select(Country)).scalars().all()
    id_to_code: dict[int, str] = {c.id: c.code for c in countries if c.code}

    if refresh:
        pairs = db.execute(
            select(TradePair).where(TradePair.exports_usd.isnot(None))
        ).scalars().all()
    else:
        pairs = db.execute(
            select(TradePair).where(
                TradePair.exports_usd.isnot(None),
                TradePair.top_export_products.is_(None),
            )
        ).scalars().all()

    if not pairs:
        log.info("No pairs need product fill — nothing to do.")
        return

    log.info("Filling products for %d trade pairs...", len(pairs))
    updated = 0

    for pair in pairs:
        exp_code = id_to_code.get(pair.exporter_id)
        imp_code = id_to_code.get(pair.importer_id)
        if not exp_code or not imp_code:
            continue

        exp_prods = COUNTRY_TOP_EXPORTS.get(exp_code, _FALLBACK_PRODUCTS)
        imp_prods = COUNTRY_TOP_EXPORTS.get(imp_code, _FALLBACK_PRODUCTS)

        # Scale proportionally to actual bilateral values so the bar chart makes sense
        pair.top_export_products = _scale_products(exp_prods, pair.exports_usd)
        pair.top_import_products = _scale_products(imp_prods, pair.imports_usd)
        updated += 1

        if updated % 500 == 0:
            db.commit()
            log.info("Committed %d pairs...", updated)

    db.commit()
    log.info("fill_trade_products complete — %d pairs updated.", updated)


def run(refresh: bool = False) -> None:
    db = SessionLocal()
    try:
        fill_trade_products(db, refresh=refresh)
    finally:
        db.close()
