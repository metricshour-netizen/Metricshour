"""
Seed bilateral trade pairs for G20 countries.
Data: approximate 2022 figures from WTO/IMF public reports (USD billions).
Idempotent — safe to re-run.

Run: python seed.py --only trade
"""

import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Country, TradePair

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

B = 1_000_000_000  # 1 billion


def _prod(names_values: list[tuple[str, float]]) -> list[dict]:
    """Build top_export_products / top_import_products JSON."""
    return [{"name": n, "value_usd": int(v * B)} for n, v in names_values]


# Each row: (exporter, importer, exports_usd_B, imports_usd_B, top_export_products, top_import_products)
# exports = what exporter ships to importer; imports = what exporter receives from importer
# All values approximate 2022 data from WTO/IMF public statistics.
BILATERAL_FLOWS: list[tuple] = [
    # ── US bilateral ─────────────────────────────────────────────────────────
    ("US", "CN", 154.0, 537.0,
     _prod([("soybeans", 26), ("aircraft", 16), ("semiconductors", 9), ("petroleum products", 8), ("cotton", 5)]),
     _prod([("electronics", 107), ("machinery", 89), ("apparel & textiles", 64), ("toys & games", 27), ("furniture", 20)])),

    ("US", "CA", 356.0, 428.0,
     _prod([("petroleum products", 71), ("vehicles", 53), ("machinery", 43), ("plastics", 18), ("aircraft", 15)]),
     _prod([("crude oil", 110), ("vehicles", 85), ("machinery", 52), ("natural gas", 18), ("aluminum", 12)])),

    ("US", "MX", 324.0, 455.0,
     _prod([("petroleum products", 65), ("machinery", 58), ("electronics", 45), ("vehicles", 40), ("plastics", 22)]),
     _prod([("vehicles", 136), ("electronics", 91), ("medical devices", 45), ("machinery", 38), ("petroleum", 22)])),

    ("US", "DE", 66.0, 159.0,
     _prod([("aircraft", 13), ("machinery", 11), ("pharmaceuticals", 9), ("vehicles", 7), ("chemicals", 5)]),
     _prod([("vehicles", 48), ("pharmaceuticals", 27), ("machinery", 22), ("chemicals", 18), ("electronics", 10)])),

    ("US", "JP", 80.0, 148.0,
     _prod([("aircraft", 16), ("soybeans", 10), ("pharmaceuticals", 8), ("corn", 6), ("coal", 5)]),
     _prod([("vehicles", 44), ("machinery", 28), ("electronics", 22), ("steel", 10), ("chemicals", 8)])),

    ("US", "GB", 74.0, 56.0,
     _prod([("aircraft", 15), ("pharmaceuticals", 11), ("petroleum products", 9), ("machinery", 8), ("chemicals", 6)]),
     _prod([("pharmaceuticals", 14), ("vehicles", 10), ("machinery", 9), ("aerospace", 7), ("beverages", 5)])),

    ("US", "KR", 60.0, 102.0,
     _prod([("semiconductors", 15), ("petroleum products", 12), ("aircraft", 10), ("soybeans", 5), ("cotton", 4)]),
     _prod([("vehicles", 30), ("electronics", 25), ("machinery", 18), ("steel", 10), ("ships", 6)])),

    ("US", "FR", 42.0, 58.0,
     _prod([("aircraft", 10), ("pharmaceuticals", 7), ("machinery", 5), ("soybeans", 4), ("petroleum products", 4)]),
     _prod([("aircraft", 12), ("pharmaceuticals", 10), ("wines & spirits", 8), ("machinery", 8), ("luxury goods", 7)])),

    ("US", "IN", 64.0, 86.0,
     _prod([("petroleum products", 18), ("aircraft", 9), ("machinery", 8), ("gold", 6), ("chemicals", 5)]),
     _prod([("pharmaceuticals", 20), ("machinery", 14), ("diamonds", 12), ("textiles & apparel", 11), ("chemicals", 8)])),

    ("US", "IT", 28.0, 60.0,
     _prod([("pharmaceuticals", 7), ("aircraft", 5), ("machinery", 4), ("petroleum", 3), ("soybeans", 2)]),
     _prod([("machinery", 15), ("pharmaceuticals", 10), ("vehicles", 9), ("wines & spirits", 7), ("fashion", 6)])),

    ("US", "AU", 26.0, 14.0,
     _prod([("aircraft", 6), ("pharmaceuticals", 4), ("machinery", 3), ("petroleum", 3), ("vehicles", 2)]),
     _prod([("iron ore", 3), ("gold", 3), ("meat", 2), ("coal", 2), ("wine", 1)])),

    ("US", "BR", 43.0, 37.0,
     _prod([("petroleum products", 10), ("aircraft", 7), ("machinery", 6), ("chemicals", 5), ("electronics", 4)]),
     _prod([("crude oil", 8), ("iron ore", 6), ("aircraft", 6), ("soybeans", 5), ("meat", 4)])),

    ("US", "SA", 14.0, 13.0,
     _prod([("machinery", 4), ("vehicles", 3), ("aircraft", 3), ("defense equipment", 2), ("chemicals", 1)]),
     _prod([("crude oil", 8), ("petroleum products", 3), ("chemicals", 1)])),

    ("US", "TR", 12.0, 10.0,
     _prod([("aircraft", 3), ("machinery", 2), ("petroleum products", 2), ("vehicles", 2), ("chemicals", 1)]),
     _prod([("machinery", 3), ("vehicles", 2), ("iron & steel", 2), ("apparel", 1), ("chemicals", 1)])),

    ("US", "ID", 9.0, 27.0,
     _prod([("aircraft", 2), ("machinery", 2), ("soybeans", 1), ("cotton", 1), ("petroleum", 1)]),
     _prod([("electronics", 7), ("rubber", 5), ("machinery", 4), ("palm oil", 4), ("apparel", 3)])),

    ("US", "BR", 43.0, 37.0,
     _prod([("petroleum products", 10), ("aircraft", 7), ("machinery", 6), ("chemicals", 5), ("electronics", 4)]),
     _prod([("crude oil", 8), ("iron ore", 6), ("aircraft", 6), ("soybeans", 5), ("meat", 4)])),

    ("US", "AR", 9.0, 5.0,
     _prod([("petroleum products", 2), ("machinery", 2), ("aircraft", 1), ("chemicals", 1)]),
     _prod([("soybeans", 2), ("meat", 1), ("soybean oil", 1)])),

    ("US", "RU", 3.0, 2.0,
     _prod([("machinery", 1), ("aircraft", 1), ("chemicals", 0.5)]),
     _prod([("petroleum", 1), ("iron & steel", 0.5), ("fertilizers", 0.3)])),

    ("US", "ZA", 5.0, 12.0,
     _prod([("machinery", 1), ("aircraft", 1), ("petroleum", 1), ("vehicles", 0.7)]),
     _prod([("platinum", 5), ("vehicles", 3), ("iron ore", 2), ("gold", 1)])),

    ("US", "MX", 324.0, 455.0,
     _prod([("petroleum products", 65), ("machinery", 58), ("electronics", 45), ("vehicles", 40), ("plastics", 22)]),
     _prod([("vehicles", 136), ("electronics", 91), ("medical devices", 45), ("machinery", 38), ("petroleum", 22)])),

    # ── China bilateral ───────────────────────────────────────────────────────
    ("CN", "JP", 173.0, 142.0,
     _prod([("electronics", 52), ("machinery", 40), ("steel", 18), ("chemicals", 15), ("textiles", 12)]),
     _prod([("machinery", 38), ("vehicles", 28), ("electronics", 24), ("chemicals", 18), ("optical equipment", 10)])),

    ("CN", "KR", 199.0, 164.0,
     _prod([("electronics", 60), ("machinery", 45), ("steel", 22), ("chemicals", 18), ("textiles", 15)]),
     _prod([("semiconductors", 65), ("electronics", 35), ("chemicals", 25), ("petroleum products", 18), ("plastics", 12)])),

    ("CN", "DE", 104.0, 107.0,
     _prod([("electronics", 31), ("machinery", 24), ("textiles", 12), ("steel", 10), ("chemicals", 8)]),
     _prod([("vehicles", 32), ("machinery", 28), ("chemicals", 18), ("pharmaceuticals", 12), ("electronics", 9)])),

    ("CN", "GB", 68.0, 26.0,
     _prod([("electronics", 20), ("machinery", 15), ("textiles", 8), ("furniture", 6), ("toys", 5)]),
     _prod([("pharmaceuticals", 7), ("vehicles", 5), ("machinery", 5), ("chemicals", 4), ("aerospace", 3)])),

    ("CN", "FR", 39.0, 22.0,
     _prod([("electronics", 12), ("machinery", 9), ("textiles", 5), ("chemicals", 5), ("furniture", 4)]),
     _prod([("aircraft", 6), ("pharmaceuticals", 5), ("cosmetics", 4), ("wines & spirits", 3), ("machinery", 2)])),

    ("CN", "IT", 36.0, 13.0,
     _prod([("electronics", 11), ("machinery", 8), ("textiles", 5), ("furniture", 4), ("chemicals", 3)]),
     _prod([("machinery", 4), ("pharmaceuticals", 3), ("fashion & luxury", 3), ("chemicals", 2), ("vehicles", 1)])),

    ("CN", "AU", 70.0, 149.0,
     _prod([("electronics", 21), ("machinery", 16), ("steel", 8), ("chemicals", 7), ("vehicles", 5)]),
     _prod([("iron ore", 80), ("coal", 26), ("natural gas", 20), ("gold", 10), ("agricultural products", 6)])),

    ("CN", "CA", 75.0, 30.0,
     _prod([("electronics", 22), ("machinery", 17), ("textiles", 8), ("steel", 7), ("chemicals", 6)]),
     _prod([("timber & pulp", 8), ("petroleum", 7), ("grain", 6), ("potash", 5), ("copper", 2)])),

    ("CN", "RU", 77.0, 110.0,
     _prod([("electronics", 23), ("machinery", 18), ("textiles", 9), ("vehicles", 8), ("chemicals", 7)]),
     _prod([("crude oil", 55), ("natural gas", 18), ("coal", 14), ("timber", 9), ("metals", 6)])),

    ("CN", "IN", 102.0, 17.0,
     _prod([("electronics", 31), ("machinery", 23), ("chemicals", 15), ("steel", 12), ("organic chemicals", 8)]),
     _prod([("iron ore", 5), ("cotton", 4), ("pharmaceuticals", 3), ("diamonds", 2), ("agricultural products", 2)])),

    ("CN", "BR", 87.0, 89.0,
     _prod([("electronics", 26), ("machinery", 20), ("steel", 10), ("chemicals", 9), ("vehicles", 7)]),
     _prod([("soybeans", 45), ("iron ore", 22), ("crude oil", 12), ("meat", 6), ("sugar", 2)])),

    ("CN", "SA", 57.0, 70.0,
     _prod([("electronics", 17), ("machinery", 13), ("vehicles", 8), ("textiles", 7), ("chemicals", 6)]),
     _prod([("crude oil", 52), ("petroleum products", 10), ("chemicals", 5), ("plastics", 2)])),

    ("CN", "MX", 109.0, 9.0,
     _prod([("electronics", 33), ("machinery", 25), ("chemicals", 13), ("textiles", 10), ("steel", 9)]),
     _prod([("vehicles", 3), ("petroleum", 2), ("electronics", 2), ("agricultural products", 1)])),

    ("CN", "TR", 35.0, 3.0,
     _prod([("electronics", 10), ("machinery", 8), ("textiles", 5), ("chemicals", 5), ("steel", 4)]),
     _prod([("cotton", 1), ("iron ore", 0.8), ("machinery", 0.6), ("chemicals", 0.3)])),

    ("CN", "ID", 67.0, 36.0,
     _prod([("electronics", 20), ("machinery", 15), ("steel", 8), ("chemicals", 7), ("textiles", 6)]),
     _prod([("coal", 12), ("palm oil", 9), ("copper", 6), ("natural gas", 5), ("rubber", 3)])),

    ("CN", "AR", 15.0, 7.0,
     _prod([("electronics", 4), ("machinery", 3), ("vehicles", 2), ("chemicals", 2), ("steel", 1)]),
     _prod([("soybeans", 3), ("soybean oil", 2), ("meat", 1), ("copper", 0.5)])),

    ("CN", "ZA", 44.0, 20.0,
     _prod([("electronics", 13), ("machinery", 10), ("textiles", 5), ("steel", 4), ("chemicals", 4)]),
     _prod([("iron ore", 8), ("copper", 4), ("platinum", 3), ("coal", 3), ("chemicals", 1)])),

    # ── Japan bilateral ───────────────────────────────────────────────────────
    ("JP", "KR", 55.0, 32.0,
     _prod([("machinery", 15), ("chemicals", 12), ("electronics", 10), ("steel", 7), ("plastics", 5)]),
     _prod([("electronics", 9), ("steel", 7), ("petroleum products", 6), ("machinery", 5), ("ships", 4)])),

    ("JP", "DE", 22.0, 24.0,
     _prod([("vehicles", 7), ("machinery", 5), ("electronics", 4), ("chemicals", 3), ("optical equipment", 2)]),
     _prod([("vehicles", 7), ("machinery", 6), ("chemicals", 5), ("pharmaceuticals", 3), ("medical equipment", 2)])),

    ("JP", "AU", 21.0, 79.0,
     _prod([("vehicles", 6), ("machinery", 5), ("electronics", 4), ("steel", 3), ("chemicals", 2)]),
     _prod([("iron ore", 32), ("coal", 22), ("natural gas", 14), ("gold", 5), ("beef", 3)])),

    ("JP", "IN", 13.0, 8.0,
     _prod([("machinery", 4), ("vehicles", 3), ("electronics", 3), ("steel", 2), ("chemicals", 1)]),
     _prod([("petroleum products", 3), ("iron ore", 2), ("chemicals", 1), ("textiles", 1)])),

    ("JP", "SA", 15.0, 68.0,
     _prod([("vehicles", 5), ("machinery", 4), ("electronics", 3), ("steel", 2), ("chemicals", 1)]),
     _prod([("crude oil", 52), ("petroleum products", 10), ("petrochemicals", 4), ("fertilizers", 1)])),

    ("JP", "ID", 16.0, 26.0,
     _prod([("vehicles", 5), ("machinery", 4), ("electronics", 3), ("steel", 2), ("chemicals", 1)]),
     _prod([("coal", 9), ("copper", 5), ("natural gas", 5), ("palm oil", 4), ("nickel", 2)])),

    ("JP", "BR", 7.0, 5.0,
     _prod([("vehicles", 2), ("machinery", 2), ("electronics", 1), ("chemicals", 1)]),
     _prod([("iron ore", 2), ("soybeans", 1), ("meat", 1), ("pulp", 0.5)])),

    ("JP", "CA", 11.0, 10.0,
     _prod([("vehicles", 3), ("machinery", 3), ("electronics", 2), ("chemicals", 1)]),
     _prod([("petroleum", 3), ("timber", 2), ("wheat", 2), ("natural gas", 1)])),

    # ── Germany bilateral ─────────────────────────────────────────────────────
    ("DE", "FR", 115.0, 79.0,
     _prod([("vehicles", 28), ("machinery", 22), ("chemicals", 18), ("electronics", 14), ("pharmaceuticals", 10)]),
     _prod([("aircraft", 18), ("vehicles", 14), ("chemicals", 12), ("pharmaceuticals", 10), ("food & beverages", 8)])),

    ("DE", "GB", 87.0, 54.0,
     _prod([("vehicles", 21), ("machinery", 17), ("chemicals", 14), ("pharmaceuticals", 10), ("electronics", 8)]),
     _prod([("pharmaceuticals", 12), ("machinery", 10), ("vehicles", 9), ("chemicals", 8), ("aerospace", 7)])),

    ("DE", "IT", 80.0, 69.0,
     _prod([("vehicles", 19), ("machinery", 16), ("chemicals", 13), ("electronics", 10), ("pharmaceuticals", 8)]),
     _prod([("machinery", 18), ("vehicles", 13), ("chemicals", 11), ("pharmaceuticals", 9), ("food & beverages", 8)])),

    ("DE", "KR", 24.0, 12.0,
     _prod([("vehicles", 7), ("machinery", 5), ("chemicals", 5), ("pharmaceuticals", 3), ("electronics", 2)]),
     _prod([("electronics", 4), ("vehicles", 3), ("steel", 2), ("machinery", 2), ("chemicals", 1)])),

    ("DE", "TR", 25.0, 20.0,
     _prod([("vehicles", 6), ("machinery", 5), ("chemicals", 5), ("electronics", 4), ("pharmaceuticals", 2)]),
     _prod([("machinery", 5), ("vehicles", 4), ("textiles", 4), ("iron & steel", 3), ("chemicals", 2)])),

    ("DE", "IN", 16.0, 17.0,
     _prod([("machinery", 5), ("vehicles", 4), ("chemicals", 3), ("electronics", 2), ("pharmaceuticals", 1)]),
     _prod([("pharmaceuticals", 5), ("machinery", 4), ("textiles", 3), ("chemicals", 2), ("diamonds", 1)])),

    ("DE", "BR", 10.0, 8.0,
     _prod([("vehicles", 3), ("machinery", 3), ("chemicals", 2), ("pharmaceuticals", 1)]),
     _prod([("soybeans", 2), ("iron ore", 2), ("meat", 1), ("petroleum", 1)])),

    ("DE", "RU", 4.0, 8.0,
     _prod([("machinery", 1), ("vehicles", 1), ("chemicals", 1), ("pharmaceuticals", 0.5)]),
     _prod([("petroleum", 4), ("natural gas", 2), ("metals", 1), ("fertilizers", 0.5)])),

    ("DE", "AU", 7.0, 4.0,
     _prod([("vehicles", 2), ("machinery", 2), ("chemicals", 1), ("pharmaceuticals", 1)]),
     _prod([("iron ore", 1), ("coal", 1), ("gold", 0.8), ("meat", 0.5)])),

    ("DE", "SA", 8.0, 7.0,
     _prod([("vehicles", 2), ("machinery", 2), ("chemicals", 2), ("pharmaceuticals", 1)]),
     _prod([("petroleum", 5), ("chemicals", 1), ("plastics", 0.5)])),

    ("DE", "ZA", 4.0, 5.0,
     _prod([("vehicles", 1), ("machinery", 1), ("chemicals", 1)]),
     _prod([("platinum", 2), ("iron ore", 1), ("vehicles", 1), ("gold", 0.5)])),

    # ── UK bilateral ──────────────────────────────────────────────────────────
    ("GB", "FR", 48.0, 35.0,
     _prod([("petroleum products", 10), ("pharmaceuticals", 9), ("machinery", 8), ("vehicles", 6), ("chemicals", 5)]),
     _prod([("aircraft", 8), ("vehicles", 7), ("pharmaceuticals", 6), ("wines & spirits", 5), ("chemicals", 4)])),

    ("GB", "IT", 32.0, 28.0,
     _prod([("pharmaceuticals", 8), ("machinery", 6), ("petroleum products", 5), ("chemicals", 5), ("vehicles", 4)]),
     _prod([("machinery", 7), ("vehicles", 5), ("pharmaceuticals", 5), ("fashion", 4), ("food & beverages", 4)])),

    ("GB", "IN", 22.0, 18.0,
     _prod([("pharmaceuticals", 5), ("machinery", 4), ("vehicles", 4), ("gold", 3), ("chemicals", 3)]),
     _prod([("pharmaceuticals", 5), ("diamonds", 4), ("textiles & apparel", 3), ("machinery", 2), ("chemicals", 2)])),

    ("GB", "CA", 18.0, 10.0,
     _prod([("pharmaceuticals", 4), ("petroleum products", 4), ("machinery", 3), ("vehicles", 3), ("chemicals", 2)]),
     _prod([("petroleum", 3), ("gold", 2), ("vehicles", 2), ("timber", 1), ("grain", 1)])),

    ("GB", "AU", 10.0, 6.0,
     _prod([("pharmaceuticals", 3), ("machinery", 2), ("vehicles", 2), ("chemicals", 1)]),
     _prod([("gold", 2), ("iron ore", 1), ("coal", 1), ("wine", 0.8)])),

    ("GB", "TR", 12.0, 22.0,
     _prod([("machinery", 3), ("vehicles", 2), ("pharmaceuticals", 2), ("chemicals", 2)]),
     _prod([("apparel", 6), ("vehicles", 5), ("machinery", 4), ("textiles", 3), ("chemicals", 2)])),

    ("GB", "SA", 8.0, 9.0,
     _prod([("machinery", 2), ("vehicles", 2), ("pharmaceuticals", 1), ("chemicals", 1)]),
     _prod([("petroleum", 6), ("chemicals", 2), ("plastics", 0.5)])),

    ("GB", "ZA", 6.0, 8.0,
     _prod([("machinery", 2), ("pharmaceuticals", 1), ("vehicles", 1), ("chemicals", 1)]),
     _prod([("platinum", 3), ("gold", 2), ("iron ore", 1), ("coal", 1)])),

    # ── France bilateral ──────────────────────────────────────────────────────
    ("FR", "IT", 58.0, 50.0,
     _prod([("pharmaceuticals", 12), ("aircraft", 10), ("vehicles", 9), ("chemicals", 8), ("machinery", 7)]),
     _prod([("machinery", 12), ("vehicles", 9), ("chemicals", 9), ("pharmaceuticals", 8), ("fashion", 6)])),

    ("FR", "IN", 8.0, 8.0,
     _prod([("aircraft", 2), ("pharmaceuticals", 2), ("machinery", 2), ("chemicals", 1)]),
     _prod([("pharmaceuticals", 2), ("textiles", 2), ("chemicals", 1), ("machinery", 1)])),

    ("FR", "KR", 9.0, 7.0,
     _prod([("aircraft", 3), ("pharmaceuticals", 2), ("luxury goods", 2), ("machinery", 1)]),
     _prod([("electronics", 2), ("vehicles", 2), ("steel", 1), ("machinery", 1)])),

    ("FR", "SA", 8.0, 5.0,
     _prod([("aircraft", 2), ("vehicles", 2), ("machinery", 2), ("pharmaceuticals", 1)]),
     _prod([("petroleum", 3), ("chemicals", 1), ("plastics", 0.5)])),

    ("FR", "TR", 11.0, 8.0,
     _prod([("aircraft", 3), ("vehicles", 2), ("pharmaceuticals", 2), ("chemicals", 2)]),
     _prod([("apparel", 2), ("machinery", 2), ("textiles", 2), ("chemicals", 1)])),

    ("FR", "AU", 5.0, 3.0,
     _prod([("aircraft", 2), ("pharmaceuticals", 1), ("wines & spirits", 1)]),
     _prod([("iron ore", 1), ("coal", 0.8), ("gold", 0.5), ("wine", 0.3)])),

    # ── Italy bilateral ───────────────────────────────────────────────────────
    ("IT", "TR", 14.0, 13.0,
     _prod([("machinery", 4), ("pharmaceuticals", 3), ("vehicles", 3), ("chemicals", 2), ("fashion", 1)]),
     _prod([("apparel", 4), ("machinery", 3), ("textiles", 3), ("iron & steel", 2), ("vehicles", 1)])),

    ("IT", "IN", 4.0, 6.0,
     _prod([("machinery", 1), ("pharmaceuticals", 1), ("fashion", 1), ("chemicals", 0.7)]),
     _prod([("pharmaceuticals", 2), ("textiles", 2), ("chemicals", 1), ("machinery", 0.5)])),

    ("IT", "SA", 4.0, 6.0,
     _prod([("machinery", 1), ("fashion", 1), ("pharmaceuticals", 1), ("chemicals", 0.7)]),
     _prod([("petroleum", 4), ("chemicals", 1), ("plastics", 0.5)])),

    ("IT", "BR", 3.0, 2.0,
     _prod([("machinery", 1), ("pharmaceuticals", 0.8), ("chemicals", 0.7)]),
     _prod([("soybeans", 0.7), ("iron ore", 0.6), ("petroleum", 0.5)])),

    # ── Canada bilateral ──────────────────────────────────────────────────────
    ("CA", "GB", 10.0, 18.0,
     _prod([("petroleum", 3), ("gold", 2), ("vehicles", 2), ("timber", 1), ("grain", 1)]),
     _prod([("pharmaceuticals", 4), ("machinery", 4), ("vehicles", 3), ("chemicals", 3), ("aerospace", 2)])),

    ("CA", "KR", 7.0, 8.0,
     _prod([("petroleum", 2), ("grain", 2), ("potash", 1), ("timber", 1)]),
     _prod([("vehicles", 3), ("electronics", 2), ("steel", 1), ("machinery", 1)])),

    ("CA", "AU", 3.0, 6.0,
     _prod([("petroleum", 1), ("gold", 0.8), ("grain", 0.7)]),
     _prod([("iron ore", 2), ("coal", 1), ("gold", 1), ("meat", 0.8)])),

    ("CA", "IN", 5.0, 5.0,
     _prod([("petroleum", 1), ("grain", 1), ("potash", 1), ("chemicals", 0.7)]),
     _prod([("pharmaceuticals", 2), ("textiles", 1), ("machinery", 1), ("chemicals", 0.7)])),

    ("CA", "BR", 4.0, 4.0,
     _prod([("petroleum", 1), ("grain", 1), ("potash", 0.8)]),
     _prod([("iron ore", 1), ("soybeans", 1), ("aircraft", 0.8), ("petroleum", 0.7)])),

    # ── South Korea bilateral ─────────────────────────────────────────────────
    ("KR", "AU", 15.0, 39.0,
     _prod([("electronics", 5), ("vehicles", 4), ("steel", 3), ("chemicals", 2), ("machinery", 1)]),
     _prod([("iron ore", 14), ("coal", 12), ("natural gas", 7), ("gold", 3), ("copper", 2)])),

    ("KR", "IN", 20.0, 7.0,
     _prod([("electronics", 7), ("steel", 5), ("chemicals", 4), ("vehicles", 3), ("machinery", 1)]),
     _prod([("petroleum products", 2), ("iron ore", 2), ("chemicals", 1), ("textiles", 1)])),

    ("KR", "SA", 9.0, 62.0,
     _prod([("electronics", 3), ("vehicles", 2), ("steel", 2), ("ships", 1), ("machinery", 1)]),
     _prod([("crude oil", 48), ("petroleum products", 9), ("petrochemicals", 3), ("fertilizers", 1)])),

    ("KR", "ID", 12.0, 16.0,
     _prod([("electronics", 4), ("vehicles", 3), ("steel", 2), ("machinery", 2), ("chemicals", 1)]),
     _prod([("coal", 5), ("palm oil", 4), ("copper", 3), ("natural gas", 2), ("rubber", 1)])),

    ("KR", "MX", 9.0, 5.0,
     _prod([("electronics", 3), ("vehicles", 2), ("steel", 2), ("machinery", 1)]),
     _prod([("petroleum", 2), ("vehicles", 1), ("electronics", 1), ("agricultural products", 0.7)])),

    ("KR", "BR", 4.0, 4.0,
     _prod([("electronics", 1), ("vehicles", 1), ("steel", 1), ("chemicals", 0.7)]),
     _prod([("iron ore", 1), ("soybeans", 1), ("petroleum", 0.8), ("meat", 0.5)])),

    ("KR", "ZA", 4.0, 3.0,
     _prod([("electronics", 1), ("vehicles", 1), ("steel", 1), ("chemicals", 0.7)]),
     _prod([("iron ore", 1), ("platinum", 0.8), ("coal", 0.6), ("manganese", 0.4)])),

    # ── Australia bilateral ───────────────────────────────────────────────────
    ("AU", "IN", 15.0, 14.0,
     _prod([("coal", 5), ("gold", 3), ("natural gas", 3), ("iron ore", 2), ("copper", 1)]),
     _prod([("petroleum products", 5), ("pharmaceuticals", 3), ("machinery", 2), ("textiles", 2), ("chemicals", 1)])),

    ("AU", "SA", 3.0, 13.0,
     _prod([("coal", 1), ("gold", 0.8), ("grain", 0.6), ("meat", 0.4)]),
     _prod([("petroleum", 10), ("chemicals", 2), ("plastics", 0.8)])),

    ("AU", "ID", 8.0, 13.0,
     _prod([("coal", 3), ("gold", 2), ("grain", 1), ("meat", 1), ("iron ore", 0.8)]),
     _prod([("palm oil", 4), ("coal", 3), ("copper", 2), ("rubber", 1), ("natural gas", 1)])),

    ("AU", "TR", 2.0, 3.0,
     _prod([("coal", 0.8), ("gold", 0.5), ("grain", 0.5)]),
     _prod([("machinery", 1), ("textiles", 0.8), ("chemicals", 0.5), ("iron & steel", 0.4)])),

    # ── Brazil bilateral ──────────────────────────────────────────────────────
    ("BR", "AR", 15.0, 14.0,
     _prod([("petroleum products", 4), ("vehicles", 4), ("machinery", 3), ("chemicals", 2), ("soybeans", 1)]),
     _prod([("soybeans", 4), ("wheat", 3), ("natural gas", 3), ("vehicles", 2), ("chemicals", 1)])),

    ("BR", "IN", 7.0, 5.0,
     _prod([("soybeans", 2), ("crude oil", 2), ("iron ore", 1), ("meat", 0.8)]),
     _prod([("pharmaceuticals", 2), ("electronics", 1), ("machinery", 1), ("chemicals", 0.7)])),

    ("BR", "SA", 3.0, 7.0,
     _prod([("soybeans", 1), ("crude oil", 0.8), ("iron ore", 0.7), ("meat", 0.5)]),
     _prod([("petroleum", 5), ("chemicals", 1), ("plastics", 0.7)])),

    ("BR", "TR", 4.0, 4.0,
     _prod([("soybeans", 1), ("iron ore", 1), ("meat", 0.8), ("petroleum", 0.6)]),
     _prod([("machinery", 1), ("chemicals", 1), ("textiles", 0.8), ("iron & steel", 0.6)])),

    ("BR", "ID", 3.0, 5.0,
     _prod([("soybeans", 1), ("iron ore", 0.8), ("meat", 0.6), ("petroleum", 0.5)]),
     _prod([("palm oil", 2), ("rubber", 1), ("coal", 1), ("chemicals", 0.6)])),

    # ── India bilateral ───────────────────────────────────────────────────────
    ("IN", "SA", 15.0, 51.0,
     _prod([("petroleum products", 6), ("machinery", 3), ("pharmaceuticals", 3), ("textiles", 2), ("rice", 1)]),
     _prod([("crude oil", 38), ("petroleum products", 8), ("chemicals", 3), ("plastics", 1)])),

    ("IN", "ID", 8.0, 16.0,
     _prod([("petroleum products", 3), ("pharmaceuticals", 2), ("textiles", 1), ("machinery", 1)]),
     _prod([("palm oil", 6), ("coal", 4), ("copper", 2), ("natural gas", 1), ("rubber", 1)])),

    ("IN", "AU", 14.0, 15.0,
     _prod([("pharmaceuticals", 4), ("petroleum products", 3), ("textiles", 3), ("machinery", 2), ("chemicals", 1)]),
     _prod([("coal", 6), ("gold", 3), ("natural gas", 2), ("iron ore", 2), ("copper", 1)])),

    ("IN", "TR", 5.0, 3.0,
     _prod([("petroleum products", 2), ("pharmaceuticals", 1), ("textiles", 1), ("machinery", 0.7)]),
     _prod([("machinery", 1), ("chemicals", 0.8), ("gold", 0.6), ("iron & steel", 0.4)])),

    ("IN", "ZA", 6.0, 5.0,
     _prod([("petroleum products", 2), ("pharmaceuticals", 2), ("machinery", 1), ("textiles", 0.7)]),
     _prod([("coal", 2), ("platinum", 1), ("iron ore", 1), ("chemicals", 0.6)])),

    ("IN", "RU", 11.0, 32.0,
     _prod([("pharmaceuticals", 3), ("machinery", 2), ("textiles", 2), ("chemicals", 2), ("food", 1)]),
     _prod([("petroleum", 18), ("fertilizers", 6), ("coal", 4), ("metals", 2), ("diamonds", 1)])),

    ("IN", "MX", 4.0, 4.0,
     _prod([("pharmaceuticals", 1), ("machinery", 1), ("textiles", 0.8), ("chemicals", 0.7)]),
     _prod([("petroleum", 1), ("machinery", 1), ("vehicles", 0.8), ("electronics", 0.6)])),

    # ── Russia bilateral ──────────────────────────────────────────────────────
    ("RU", "TR", 22.0, 7.0,
     _prod([("petroleum", 10), ("natural gas", 5), ("coal", 3), ("metals", 2), ("wheat", 1)]),
     _prod([("machinery", 2), ("vehicles", 2), ("textiles", 1), ("chemicals", 0.8), ("food", 0.6)])),

    ("RU", "KR", 10.0, 3.0,
     _prod([("petroleum", 5), ("coal", 2), ("metals", 1), ("chemicals", 0.8)]),
     _prod([("electronics", 1), ("vehicles", 0.8), ("machinery", 0.7), ("ships", 0.5)])),

    ("RU", "ID", 3.0, 2.0,
     _prod([("petroleum", 1), ("metals", 0.8), ("fertilizers", 0.6), ("wheat", 0.4)]),
     _prod([("palm oil", 0.8), ("rubber", 0.5), ("coffee", 0.3)])),

    ("RU", "BR", 4.0, 3.0,
     _prod([("petroleum", 1), ("fertilizers", 1), ("metals", 0.8), ("wheat", 0.5)]),
     _prod([("soybeans", 1), ("meat", 0.8), ("iron ore", 0.6), ("agricultural products", 0.4)])),

    ("RU", "SA", 3.0, 4.0,
     _prod([("petroleum", 1), ("metals", 0.8), ("wheat", 0.6), ("chemicals", 0.4)]),
     _prod([("petroleum products", 2), ("chemicals", 0.8), ("food", 0.5)])),

    # ── Saudi Arabia bilateral ────────────────────────────────────────────────
    ("SA", "TR", 8.0, 5.0,
     _prod([("crude oil", 5), ("petroleum products", 2), ("chemicals", 0.7)]),
     _prod([("machinery", 2), ("vehicles", 1), ("textiles", 0.8), ("food", 0.6)])),

    ("SA", "ID", 7.0, 3.0,
     _prod([("crude oil", 5), ("petroleum products", 1), ("chemicals", 0.7)]),
     _prod([("palm oil", 1), ("rubber", 0.6), ("coffee", 0.4), ("food", 0.4)])),

    ("SA", "AU", 13.0, 3.0,
     _prod([("crude oil", 10), ("petroleum products", 2), ("chemicals", 0.8)]),
     _prod([("grain", 1), ("gold", 0.8), ("meat", 0.6), ("machinery", 0.5)])),

    ("SA", "MX", 4.0, 2.0,
     _prod([("crude oil", 3), ("petroleum products", 0.8)]),
     _prod([("vehicles", 0.8), ("electronics", 0.5), ("petroleum products", 0.4)])),

    # ── Turkey bilateral ──────────────────────────────────────────────────────
    ("TR", "IN", 3.0, 5.0,
     _prod([("machinery", 1), ("chemicals", 0.8), ("textiles", 0.7), ("iron & steel", 0.5)]),
     _prod([("petroleum products", 2), ("pharmaceuticals", 1), ("textiles", 0.8), ("chemicals", 0.7)])),

    ("TR", "BR", 4.0, 4.0,
     _prod([("machinery", 1), ("chemicals", 0.8), ("textiles", 0.8), ("iron & steel", 0.7)]),
     _prod([("soybeans", 1), ("iron ore", 0.8), ("petroleum", 0.7), ("chemicals", 0.5)])),

    ("TR", "ZA", 2.0, 2.0,
     _prod([("machinery", 0.6), ("textiles", 0.5), ("chemicals", 0.5)]),
     _prod([("platinum", 0.7), ("iron ore", 0.6), ("coal", 0.4)])),

    ("TR", "ID", 3.0, 2.0,
     _prod([("machinery", 0.8), ("chemicals", 0.6), ("textiles", 0.6), ("food", 0.5)]),
     _prod([("palm oil", 0.7), ("rubber", 0.5), ("coal", 0.4), ("coffee", 0.3)])),

    ("TR", "MX", 2.0, 3.0,
     _prod([("machinery", 0.6), ("textiles", 0.5), ("chemicals", 0.5)]),
     _prod([("petroleum", 0.8), ("vehicles", 0.7), ("electronics", 0.6), ("machinery", 0.5)])),

    # ── Indonesia bilateral ───────────────────────────────────────────────────
    ("ID", "IN", 16.0, 8.0,
     _prod([("palm oil", 5), ("coal", 4), ("copper", 3), ("rubber", 2), ("natural gas", 1)]),
     _prod([("petroleum products", 3), ("pharmaceuticals", 2), ("machinery", 1), ("textiles", 1)])),

    ("ID", "AU", 13.0, 8.0,
     _prod([("coal", 4), ("palm oil", 3), ("copper", 2), ("natural gas", 2), ("rubber", 1)]),
     _prod([("grain", 2), ("gold", 1), ("meat", 1), ("machinery", 1), ("coal", 0.8)])),

    ("ID", "BR", 5.0, 3.0,
     _prod([("palm oil", 2), ("coal", 1), ("rubber", 0.8), ("chemicals", 0.6)]),
     _prod([("soybeans", 1), ("meat", 0.7), ("iron ore", 0.6), ("petroleum", 0.5)])),

    ("ID", "ZA", 2.0, 2.0,
     _prod([("palm oil", 0.8), ("coal", 0.6), ("rubber", 0.4)]),
     _prod([("iron ore", 0.6), ("coal", 0.5), ("platinum", 0.4), ("chemicals", 0.3)])),

    ("ID", "MX", 3.0, 4.0,
     _prod([("palm oil", 1), ("electronics", 0.8), ("rubber", 0.6), ("coal", 0.5)]),
     _prod([("petroleum", 1), ("vehicles", 0.8), ("machinery", 0.7), ("electronics", 0.6)])),

    # ── Mexico bilateral ──────────────────────────────────────────────────────
    ("MX", "CA", 12.0, 22.0,
     _prod([("vehicles", 4), ("electronics", 3), ("petroleum products", 2), ("machinery", 2), ("food", 1)]),
     _prod([("petroleum", 7), ("vehicles", 5), ("grain", 3), ("machinery", 3), ("chemicals", 2)])),

    ("MX", "DE", 8.0, 8.0,
     _prod([("vehicles", 3), ("electronics", 2), ("petroleum", 1), ("food", 0.8)]),
     _prod([("vehicles", 3), ("machinery", 2), ("chemicals", 1), ("electronics", 1)])),

    ("MX", "JP", 5.0, 10.0,
     _prod([("vehicles", 2), ("electronics", 1), ("petroleum", 0.8), ("food", 0.7)]),
     _prod([("vehicles", 4), ("machinery", 3), ("electronics", 2), ("steel", 0.8)])),

    ("MX", "KR", 5.0, 9.0,
     _prod([("vehicles", 2), ("electronics", 1), ("petroleum", 0.8)]),
     _prod([("electronics", 3), ("vehicles", 3), ("steel", 1), ("machinery", 1)])),

    ("MX", "BR", 5.0, 8.0,
     _prod([("vehicles", 2), ("electronics", 1), ("petroleum", 0.8), ("food", 0.6)]),
     _prod([("petroleum", 2), ("soybeans", 2), ("iron ore", 1), ("aircraft", 1)])),

    ("MX", "IN", 4.0, 4.0,
     _prod([("petroleum", 1), ("vehicles", 1), ("electronics", 0.8)]),
     _prod([("pharmaceuticals", 1), ("textiles", 0.8), ("machinery", 0.8), ("chemicals", 0.7)])),

    ("MX", "AR", 4.0, 3.0,
     _prod([("vehicles", 1), ("electronics", 0.8), ("petroleum", 0.8), ("food", 0.7)]),
     _prod([("soybeans", 0.8), ("wheat", 0.7), ("natural gas", 0.6), ("vehicles", 0.5)])),

    # ── South Africa bilateral ────────────────────────────────────────────────
    ("ZA", "IN", 5.0, 6.0,
     _prod([("platinum", 2), ("iron ore", 1), ("coal", 0.8), ("chemicals", 0.7)]),
     _prod([("petroleum products", 2), ("pharmaceuticals", 2), ("machinery", 1), ("textiles", 0.8)])),

    ("ZA", "BR", 2.0, 2.0,
     _prod([("platinum", 0.7), ("iron ore", 0.5), ("coal", 0.4), ("chemicals", 0.3)]),
     _prod([("soybeans", 0.6), ("iron ore", 0.5), ("petroleum", 0.4), ("food", 0.3)])),

    ("ZA", "AU", 3.0, 2.0,
     _prod([("platinum", 1), ("iron ore", 0.8), ("coal", 0.6), ("gold", 0.5)]),
     _prod([("coal", 0.6), ("grain", 0.5), ("gold", 0.4), ("machinery", 0.4)])),

    ("ZA", "ID", 2.0, 2.0,
     _prod([("platinum", 0.8), ("iron ore", 0.5), ("coal", 0.4)]),
     _prod([("palm oil", 0.7), ("rubber", 0.5), ("coal", 0.4), ("chemicals", 0.3)])),

    ("ZA", "MX", 2.0, 2.0,
     _prod([("platinum", 0.8), ("iron ore", 0.5), ("coal", 0.4)]),
     _prod([("petroleum", 0.6), ("vehicles", 0.5), ("electronics", 0.4), ("machinery", 0.3)])),

    # ── Argentina bilateral ───────────────────────────────────────────────────
    ("AR", "BR", 14.0, 15.0,
     _prod([("soybeans", 4), ("soybean oil", 3), ("meat", 3), ("wheat", 2), ("natural gas", 1)]),
     _prod([("vehicles", 4), ("petroleum products", 3), ("natural gas", 3), ("machinery", 2), ("chemicals", 2)])),

    ("AR", "IN", 1.0, 2.0,
     _prod([("soybeans", 0.5), ("soybean oil", 0.3), ("meat", 0.2)]),
     _prod([("pharmaceuticals", 0.8), ("machinery", 0.5), ("textiles", 0.4)])),

    ("AR", "ID", 1.0, 2.0,
     _prod([("soybeans", 0.5), ("soybean oil", 0.3), ("meat", 0.2)]),
     _prod([("palm oil", 0.7), ("rubber", 0.4), ("fertilizers", 0.3)])),

    ("AR", "AU", 1.0, 2.0,
     _prod([("soybeans", 0.4), ("meat", 0.3), ("wine", 0.2)]),
     _prod([("grain", 0.6), ("coal", 0.4), ("gold", 0.3), ("machinery", 0.3)])),

    ("AR", "KR", 2.0, 4.0,
     _prod([("soybeans", 0.7), ("meat", 0.5), ("petroleum", 0.4), ("wine", 0.2)]),
     _prod([("electronics", 1), ("vehicles", 1), ("steel", 0.8), ("machinery", 0.5)])),

    ("AR", "SA", 1.0, 2.0,
     _prod([("soybeans", 0.4), ("meat", 0.3), ("wine", 0.2)]),
     _prod([("petroleum", 1), ("chemicals", 0.5), ("plastics", 0.3)])),

    ("AR", "TR", 1.0, 2.0,
     _prod([("soybeans", 0.4), ("meat", 0.3), ("wheat", 0.2)]),
     _prod([("machinery", 0.6), ("textiles", 0.5), ("chemicals", 0.4)])),

    ("AR", "MX", 3.0, 4.0,
     _prod([("soybeans", 0.8), ("petroleum", 0.7), ("meat", 0.6), ("agricultural products", 0.5)]),
     _prod([("vehicles", 1), ("electronics", 0.8), ("machinery", 0.7), ("chemicals", 0.5)])),

    ("AR", "ZA", 1.0, 1.0,
     _prod([("soybeans", 0.4), ("meat", 0.3), ("wine", 0.2)]),
     _prod([("platinum", 0.3), ("coal", 0.2), ("iron ore", 0.2), ("chemicals", 0.2)])),

    # ── Netherlands bilateral ─────────────────────────────────────────────────
    ("NL", "DE", 97.0, 90.0,
     _prod([("petroleum products", 22), ("machinery", 18), ("chemicals", 16), ("electronics", 12), ("food", 8)]),
     _prod([("machinery", 22), ("vehicles", 18), ("chemicals", 15), ("electronics", 12), ("pharmaceuticals", 9)])),
    ("NL", "GB", 43.0, 30.0,
     _prod([("petroleum products", 10), ("machinery", 8), ("chemicals", 7), ("food", 6), ("electronics", 5)]),
     _prod([("machinery", 7), ("pharmaceuticals", 6), ("vehicles", 5), ("chemicals", 5), ("food", 4)])),
    ("NL", "FR", 36.0, 30.0,
     _prod([("machinery", 8), ("chemicals", 7), ("petroleum products", 6), ("food", 6), ("electronics", 5)]),
     _prod([("aircraft", 7), ("chemicals", 6), ("pharmaceuticals", 5), ("food", 5), ("machinery", 4)])),
    ("NL", "BE", 58.0, 55.0,
     _prod([("petroleum products", 12), ("machinery", 10), ("chemicals", 9), ("food", 8), ("electronics", 7)]),
     _prod([("chemicals", 11), ("machinery", 10), ("petroleum products", 9), ("food", 8), ("pharmaceuticals", 6)])),
    ("NL", "US", 46.0, 32.0,
     _prod([("machinery", 10), ("chemicals", 8), ("petroleum products", 7), ("food", 6), ("pharmaceuticals", 5)]),
     _prod([("machinery", 8), ("chemicals", 7), ("aircraft", 5), ("pharmaceuticals", 5), ("electronics", 4)])),
    ("NL", "CN", 30.0, 82.0,
     _prod([("machinery", 7), ("chemicals", 6), ("food", 5), ("petroleum products", 4), ("pharmaceuticals", 3)]),
     _prod([("electronics", 25), ("machinery", 20), ("textiles", 10), ("chemicals", 8), ("furniture", 6)])),

    # ── Spain bilateral ───────────────────────────────────────────────────────
    ("ES", "FR", 52.0, 44.0,
     _prod([("vehicles", 12), ("machinery", 9), ("food & beverages", 8), ("chemicals", 7), ("petroleum products", 5)]),
     _prod([("vehicles", 10), ("machinery", 9), ("chemicals", 8), ("aircraft", 7), ("food", 5)])),
    ("ES", "DE", 32.0, 44.0,
     _prod([("vehicles", 8), ("machinery", 6), ("food", 5), ("chemicals", 5), ("petroleum products", 4)]),
     _prod([("vehicles", 12), ("machinery", 10), ("chemicals", 8), ("electronics", 6), ("pharmaceuticals", 4)])),
    ("ES", "IT", 28.0, 28.0,
     _prod([("vehicles", 7), ("food", 6), ("machinery", 5), ("chemicals", 4), ("petroleum products", 3)]),
     _prod([("machinery", 7), ("vehicles", 6), ("chemicals", 5), ("food", 4), ("pharmaceuticals", 3)])),
    ("ES", "GB", 18.0, 14.0,
     _prod([("food & beverages", 5), ("vehicles", 4), ("machinery", 3), ("chemicals", 3)]),
     _prod([("machinery", 4), ("pharmaceuticals", 3), ("vehicles", 2), ("chemicals", 2)])),
    ("ES", "US", 14.0, 16.0,
     _prod([("food & beverages", 4), ("machinery", 3), ("chemicals", 3), ("vehicles", 2)]),
     _prod([("aircraft", 4), ("machinery", 3), ("chemicals", 3), ("petroleum products", 2)])),
    ("ES", "CN", 6.0, 38.0,
     _prod([("food", 2), ("chemicals", 1), ("machinery", 1), ("vehicles", 0.8)]),
     _prod([("electronics", 12), ("machinery", 10), ("textiles", 6), ("chemicals", 4), ("furniture", 3)])),
    ("ES", "MX", 6.0, 5.0,
     _prod([("vehicles", 2), ("machinery", 1), ("chemicals", 1), ("food", 0.8)]),
     _prod([("petroleum", 2), ("vehicles", 1), ("electronics", 0.8), ("machinery", 0.7)])),

    # ── Switzerland bilateral ─────────────────────────────────────────────────
    ("CH", "DE", 40.0, 60.0,
     _prod([("pharmaceuticals", 12), ("chemicals", 8), ("machinery", 7), ("watches", 5), ("financial services", 4)]),
     _prod([("machinery", 15), ("vehicles", 12), ("chemicals", 10), ("pharmaceuticals", 8), ("electronics", 7)])),
    ("CH", "US", 30.0, 18.0,
     _prod([("pharmaceuticals", 10), ("chemicals", 7), ("machinery", 5), ("watches", 4), ("instruments", 3)]),
     _prod([("machinery", 5), ("pharmaceuticals", 4), ("aircraft", 3), ("chemicals", 3), ("electronics", 2)])),
    ("CH", "FR", 18.0, 20.0,
     _prod([("pharmaceuticals", 6), ("chemicals", 4), ("machinery", 3), ("watches", 2)]),
     _prod([("aircraft", 5), ("chemicals", 4), ("pharmaceuticals", 4), ("machinery", 3), ("food", 2)])),
    ("CH", "IT", 22.0, 20.0,
     _prod([("pharmaceuticals", 7), ("machinery", 4), ("chemicals", 4), ("watches", 3)]),
     _prod([("machinery", 5), ("vehicles", 4), ("chemicals", 4), ("food", 3), ("fashion", 2)])),
    ("CH", "CN", 18.0, 14.0,
     _prod([("pharmaceuticals", 6), ("machinery", 4), ("chemicals", 3), ("watches", 3)]),
     _prod([("electronics", 4), ("machinery", 3), ("chemicals", 3), ("textiles", 2)])),
    ("CH", "GB", 14.0, 10.0,
     _prod([("pharmaceuticals", 5), ("chemicals", 3), ("machinery", 2), ("watches", 2)]),
     _prod([("pharmaceuticals", 3), ("machinery", 2), ("chemicals", 2), ("financial services", 1)])),

    # ── Belgium bilateral ─────────────────────────────────────────────────────
    ("BE", "DE", 50.0, 55.0,
     _prod([("chemicals", 12), ("machinery", 10), ("pharmaceuticals", 9), ("food", 7), ("vehicles", 6)]),
     _prod([("machinery", 14), ("vehicles", 12), ("chemicals", 10), ("electronics", 7), ("pharmaceuticals", 6)])),
    ("BE", "FR", 45.0, 38.0,
     _prod([("chemicals", 10), ("machinery", 8), ("pharmaceuticals", 8), ("food", 7), ("vehicles", 5)]),
     _prod([("vehicles", 9), ("chemicals", 8), ("machinery", 7), ("pharmaceuticals", 6), ("food", 5)])),
    ("BE", "US", 28.0, 20.0,
     _prod([("pharmaceuticals", 8), ("chemicals", 6), ("machinery", 5), ("diamonds", 4), ("food", 3)]),
     _prod([("chemicals", 5), ("machinery", 4), ("aircraft", 3), ("pharmaceuticals", 3), ("electronics", 2)])),
    ("BE", "CN", 14.0, 50.0,
     _prod([("chemicals", 4), ("pharmaceuticals", 3), ("machinery", 3), ("food", 2)]),
     _prod([("electronics", 16), ("machinery", 13), ("chemicals", 7), ("textiles", 6), ("furniture", 4)])),

    # ── Sweden bilateral ──────────────────────────────────────────────────────
    ("SE", "DE", 20.0, 26.0,
     _prod([("machinery", 5), ("vehicles", 5), ("pharmaceuticals", 3), ("iron & steel", 2), ("electronics", 2)]),
     _prod([("vehicles", 7), ("machinery", 6), ("chemicals", 4), ("electronics", 3), ("pharmaceuticals", 3)])),
    ("SE", "US", 12.0, 10.0,
     _prod([("pharmaceuticals", 3), ("machinery", 3), ("vehicles", 2), ("electronics", 2)]),
     _prod([("machinery", 3), ("aircraft", 2), ("electronics", 2), ("chemicals", 1)])),
    ("SE", "CN", 8.0, 22.0,
     _prod([("machinery", 2), ("vehicles", 2), ("pharmaceuticals", 2), ("iron & steel", 1)]),
     _prod([("electronics", 7), ("machinery", 6), ("textiles", 3), ("chemicals", 2)])),
    ("SE", "NO", 14.0, 10.0,
     _prod([("machinery", 3), ("vehicles", 3), ("pharmaceuticals", 2), ("chemicals", 2), ("electronics", 2)]),
     _prod([("petroleum", 4), ("natural gas", 3), ("machinery", 1), ("chemicals", 1)])),
    ("SE", "GB", 10.0, 8.0,
     _prod([("machinery", 3), ("pharmaceuticals", 2), ("vehicles", 2), ("electronics", 1)]),
     _prod([("pharmaceuticals", 2), ("machinery", 2), ("vehicles", 1), ("chemicals", 1)])),

    # ── Poland bilateral ──────────────────────────────────────────────────────
    ("PL", "DE", 58.0, 52.0,
     _prod([("machinery", 14), ("vehicles", 12), ("electronics", 8), ("furniture", 6), ("food", 5)]),
     _prod([("machinery", 13), ("vehicles", 11), ("chemicals", 8), ("electronics", 7), ("pharmaceuticals", 5)])),
    ("PL", "FR", 14.0, 10.0,
     _prod([("machinery", 4), ("vehicles", 3), ("electronics", 2), ("food", 2)]),
     _prod([("vehicles", 3), ("chemicals", 2), ("machinery", 2), ("pharmaceuticals", 1)])),
    ("PL", "GB", 12.0, 8.0,
     _prod([("machinery", 3), ("electronics", 2), ("vehicles", 2), ("food", 2)]),
     _prod([("machinery", 2), ("chemicals", 2), ("pharmaceuticals", 1), ("vehicles", 1)])),
    ("PL", "CN", 4.0, 30.0,
     _prod([("machinery", 1), ("electronics", 0.8), ("food", 0.6), ("furniture", 0.5)]),
     _prod([("electronics", 10), ("machinery", 8), ("textiles", 4), ("chemicals", 3)])),
    ("PL", "US", 7.0, 6.0,
     _prod([("machinery", 2), ("electronics", 1), ("vehicles", 1), ("food", 0.8)]),
     _prod([("machinery", 2), ("chemicals", 1), ("aircraft", 1), ("electronics", 0.8)])),

    # ── Singapore bilateral ───────────────────────────────────────────────────
    ("SG", "CN", 58.0, 66.0,
     _prod([("electronics", 18), ("machinery", 12), ("chemicals", 10), ("petroleum products", 8), ("pharmaceuticals", 5)]),
     _prod([("electronics", 20), ("machinery", 16), ("chemicals", 10), ("petroleum products", 8), ("food", 5)])),
    ("SG", "US", 42.0, 36.0,
     _prod([("electronics", 13), ("machinery", 9), ("chemicals", 7), ("pharmaceuticals", 6), ("petroleum products", 4)]),
     _prod([("electronics", 10), ("machinery", 8), ("chemicals", 6), ("aircraft", 4), ("pharmaceuticals", 4)])),
    ("SG", "MY", 48.0, 44.0,
     _prod([("electronics", 15), ("machinery", 10), ("petroleum products", 8), ("chemicals", 7), ("food", 4)]),
     _prod([("electronics", 14), ("machinery", 9), ("petroleum products", 7), ("chemicals", 6), ("food", 4)])),
    ("SG", "JP", 22.0, 18.0,
     _prod([("electronics", 7), ("machinery", 5), ("chemicals", 4), ("petroleum products", 3)]),
     _prod([("machinery", 5), ("electronics", 4), ("vehicles", 3), ("chemicals", 3)])),
    ("SG", "KR", 18.0, 20.0,
     _prod([("electronics", 5), ("machinery", 4), ("chemicals", 4), ("petroleum products", 3)]),
     _prod([("electronics", 6), ("petroleum products", 5), ("machinery", 4), ("chemicals", 3)])),
    ("SG", "AU", 12.0, 8.0,
     _prod([("electronics", 4), ("machinery", 3), ("chemicals", 2), ("pharmaceuticals", 2)]),
     _prod([("natural gas", 3), ("coal", 2), ("gold", 1), ("grain", 1)])),
    ("SG", "IN", 16.0, 12.0,
     _prod([("electronics", 5), ("machinery", 4), ("chemicals", 3), ("pharmaceuticals", 2)]),
     _prod([("petroleum products", 4), ("machinery", 3), ("pharmaceuticals", 2), ("chemicals", 2)])),

    # ── UAE bilateral ─────────────────────────────────────────────────────────
    ("AE", "CN", 24.0, 62.0,
     _prod([("petroleum", 8), ("gold", 6), ("chemicals", 4), ("aluminum", 3), ("machinery", 2)]),
     _prod([("electronics", 20), ("machinery", 16), ("textiles", 8), ("chemicals", 6), ("furniture", 5)])),
    ("AE", "IN", 32.0, 50.0,
     _prod([("petroleum", 12), ("gold", 8), ("aluminum", 4), ("chemicals", 4), ("machinery", 3)]),
     _prod([("petroleum products", 14), ("machinery", 10), ("diamonds", 8), ("pharmaceuticals", 7), ("textiles", 6)])),
    ("AE", "US", 22.0, 18.0,
     _prod([("petroleum", 7), ("gold", 5), ("aluminum", 3), ("chemicals", 3), ("machinery", 2)]),
     _prod([("aircraft", 5), ("machinery", 4), ("vehicles", 3), ("defense equipment", 3), ("chemicals", 2)])),
    ("AE", "GB", 14.0, 10.0,
     _prod([("petroleum", 5), ("gold", 3), ("aluminum", 2), ("chemicals", 2)]),
     _prod([("machinery", 3), ("pharmaceuticals", 2), ("vehicles", 2), ("aerospace", 1)])),
    ("AE", "DE", 8.0, 10.0,
     _prod([("petroleum", 3), ("gold", 2), ("aluminum", 1), ("chemicals", 1)]),
     _prod([("machinery", 3), ("vehicles", 2), ("chemicals", 2), ("pharmaceuticals", 1)])),
    ("AE", "JP", 38.0, 14.0,
     _prod([("petroleum", 28), ("petroleum products", 6), ("chemicals", 2), ("aluminum", 1)]),
     _prod([("vehicles", 4), ("machinery", 4), ("electronics", 3), ("steel", 2)])),
    ("AE", "KR", 32.0, 10.0,
     _prod([("petroleum", 24), ("petroleum products", 5), ("chemicals", 2)]),
     _prod([("electronics", 3), ("vehicles", 2), ("machinery", 2), ("steel", 1)])),
    ("AE", "SA", 14.0, 22.0,
     _prod([("gold", 4), ("aluminum", 3), ("machinery", 3), ("food", 2), ("chemicals", 1)]),
     _prod([("petroleum products", 10), ("chemicals", 5), ("plastics", 3), ("food", 2)])),

    # ── Thailand bilateral ────────────────────────────────────────────────────
    ("TH", "CN", 30.0, 56.0,
     _prod([("electronics", 8), ("machinery", 6), ("rubber", 5), ("food", 5), ("vehicles", 4)]),
     _prod([("electronics", 16), ("machinery", 14), ("chemicals", 8), ("steel", 7), ("vehicles", 5)])),
    ("TH", "US", 24.0, 14.0,
     _prod([("electronics", 7), ("machinery", 5), ("rubber", 3), ("food", 4), ("vehicles", 2)]),
     _prod([("electronics", 4), ("machinery", 3), ("chemicals", 2), ("aircraft", 2), ("soybeans", 1)])),
    ("TH", "JP", 30.0, 32.0,
     _prod([("electronics", 8), ("machinery", 7), ("rubber", 4), ("food", 4), ("vehicles", 4)]),
     _prod([("machinery", 9), ("vehicles", 8), ("electronics", 7), ("steel", 4), ("chemicals", 3)])),
    ("TH", "AU", 10.0, 8.0,
     _prod([("food", 3), ("vehicles", 2), ("electronics", 2), ("rubber", 1)]),
     _prod([("coal", 3), ("gold", 2), ("natural gas", 1), ("grain", 1)])),
    ("TH", "IN", 6.0, 8.0,
     _prod([("electronics", 2), ("rubber", 1), ("food", 1), ("machinery", 1)]),
     _prod([("petroleum products", 3), ("steel", 2), ("machinery", 1), ("chemicals", 1)])),
    ("TH", "KR", 8.0, 14.0,
     _prod([("electronics", 2), ("rubber", 2), ("food", 2), ("machinery", 1)]),
     _prod([("electronics", 4), ("steel", 3), ("petroleum products", 3), ("machinery", 2)])),

    # ── Malaysia bilateral ────────────────────────────────────────────────────
    ("MY", "CN", 28.0, 58.0,
     _prod([("electronics", 8), ("palm oil", 6), ("petroleum products", 5), ("natural gas", 4), ("rubber", 3)]),
     _prod([("electronics", 18), ("machinery", 14), ("chemicals", 8), ("steel", 7), ("vehicles", 5)])),
    ("MY", "US", 22.0, 16.0,
     _prod([("electronics", 7), ("petroleum products", 4), ("natural gas", 3), ("palm oil", 2), ("rubber", 2)]),
     _prod([("electronics", 5), ("machinery", 4), ("chemicals", 3), ("aircraft", 2)])),
    ("MY", "JP", 20.0, 18.0,
     _prod([("electronics", 6), ("petroleum products", 4), ("natural gas", 4), ("palm oil", 3), ("rubber", 2)]),
     _prod([("machinery", 5), ("electronics", 4), ("vehicles", 4), ("steel", 2), ("chemicals", 2)])),
    ("MY", "AU", 6.0, 4.0,
     _prod([("electronics", 2), ("palm oil", 1), ("natural gas", 1), ("rubber", 0.8)]),
     _prod([("coal", 1), ("gold", 0.8), ("grain", 0.7), ("machinery", 0.5)])),
    ("MY", "IN", 8.0, 10.0,
     _prod([("palm oil", 3), ("electronics", 2), ("petroleum products", 1), ("rubber", 0.8)]),
     _prod([("petroleum products", 3), ("machinery", 2), ("steel", 2), ("chemicals", 1)])),
    ("MY", "KR", 8.0, 12.0,
     _prod([("electronics", 3), ("palm oil", 2), ("petroleum products", 2), ("natural gas", 1)]),
     _prod([("electronics", 4), ("steel", 3), ("petroleum products", 2), ("machinery", 2)])),

    # ── Vietnam bilateral ─────────────────────────────────────────────────────
    ("VN", "US", 114.0, 14.0,
     _prod([("electronics", 35), ("apparel & textiles", 20), ("footwear", 12), ("machinery", 10), ("furniture", 8)]),
     _prod([("aircraft", 3), ("machinery", 3), ("cotton", 2), ("soybeans", 2), ("electronics", 2)])),
    ("VN", "CN", 36.0, 118.0,
     _prod([("electronics", 10), ("machinery", 8), ("textiles", 7), ("footwear", 5), ("agricultural products", 4)]),
     _prod([("electronics", 38), ("machinery", 30), ("textiles & fabric", 16), ("steel", 10), ("chemicals", 8)])),
    ("VN", "JP", 22.0, 20.0,
     _prod([("electronics", 7), ("machinery", 5), ("textiles", 4), ("footwear", 3), ("furniture", 2)]),
     _prod([("machinery", 6), ("electronics", 5), ("vehicles", 4), ("steel", 2), ("chemicals", 2)])),
    ("VN", "KR", 24.0, 60.0,
     _prod([("electronics", 7), ("textiles", 5), ("machinery", 5), ("footwear", 4), ("furniture", 2)]),
     _prod([("electronics", 20), ("machinery", 15), ("steel", 8), ("chemicals", 7), ("plastics", 5)])),
    ("VN", "AU", 6.0, 4.0,
     _prod([("electronics", 2), ("apparel", 1), ("footwear", 1), ("food", 0.8)]),
     _prod([("coal", 1), ("natural gas", 1), ("grain", 0.7), ("gold", 0.5)])),

    # ── Nigeria bilateral ─────────────────────────────────────────────────────
    ("NG", "IN", 12.0, 6.0,
     _prod([("crude oil", 9), ("natural gas", 2), ("chemicals", 0.6)]),
     _prod([("pharmaceuticals", 2), ("petroleum products", 2), ("machinery", 1), ("textiles", 0.6)])),
    ("NG", "CN", 2.0, 18.0,
     _prod([("crude oil", 1), ("agricultural products", 0.6), ("chemicals", 0.3)]),
     _prod([("machinery", 6), ("electronics", 4), ("textiles", 3), ("steel", 2), ("vehicles", 1)])),
    ("NG", "US", 2.0, 4.0,
     _prod([("crude oil", 1), ("natural gas", 0.7), ("agricultural products", 0.2)]),
     _prod([("machinery", 1), ("vehicles", 0.8), ("aircraft", 0.6), ("petroleum products", 0.5)])),
    ("NG", "GB", 1.0, 3.0,
     _prod([("crude oil", 0.7), ("natural gas", 0.2)]),
     _prod([("machinery", 0.8), ("pharmaceuticals", 0.6), ("vehicles", 0.5), ("chemicals", 0.4)])),
    ("NG", "DE", 1.0, 2.0,
     _prod([("crude oil", 0.7), ("natural gas", 0.2)]),
     _prod([("machinery", 0.7), ("vehicles", 0.5), ("chemicals", 0.4), ("pharmaceuticals", 0.3)])),
    ("NG", "FR", 1.0, 2.0,
     _prod([("crude oil", 0.7), ("natural gas", 0.2)]),
     _prod([("aircraft", 0.5), ("machinery", 0.5), ("food", 0.4), ("chemicals", 0.3)])),

    # ── Egypt bilateral ───────────────────────────────────────────────────────
    ("EG", "CN", 2.0, 16.0,
     _prod([("petroleum", 0.8), ("agricultural products", 0.6), ("chemicals", 0.4)]),
     _prod([("machinery", 5), ("electronics", 4), ("textiles", 3), ("steel", 2), ("vehicles", 1)])),
    ("EG", "US", 2.0, 4.0,
     _prod([("petroleum products", 0.8), ("agricultural products", 0.6), ("textiles", 0.4)]),
     _prod([("machinery", 1), ("grain", 0.8), ("vehicles", 0.6), ("chemicals", 0.4)])),
    ("EG", "SA", 2.0, 6.0,
     _prod([("petroleum products", 0.8), ("food", 0.6), ("agricultural products", 0.4)]),
     _prod([("petroleum", 4), ("chemicals", 1), ("food", 0.6)])),
    ("EG", "DE", 1.0, 3.0,
     _prod([("petroleum products", 0.5), ("textiles", 0.3), ("agricultural products", 0.2)]),
     _prod([("machinery", 0.8), ("vehicles", 0.7), ("chemicals", 0.5), ("pharmaceuticals", 0.4)])),
    ("EG", "IT", 3.0, 4.0,
     _prod([("petroleum products", 1), ("textiles", 0.8), ("agricultural products", 0.6), ("chemicals", 0.4)]),
     _prod([("machinery", 1), ("pharmaceuticals", 0.8), ("chemicals", 0.7), ("fashion", 0.5)])),
    ("EG", "IN", 2.0, 3.0,
     _prod([("petroleum products", 0.7), ("textiles", 0.5), ("agricultural products", 0.4)]),
     _prod([("petroleum products", 1), ("pharmaceuticals", 0.8), ("machinery", 0.6), ("textiles", 0.4)])),

    # ── Norway bilateral ──────────────────────────────────────────────────────
    ("NO", "DE", 30.0, 14.0,
     _prod([("petroleum", 12), ("natural gas", 10), ("fish", 4), ("aluminum", 2), ("chemicals", 1)]),
     _prod([("machinery", 4), ("vehicles", 3), ("chemicals", 3), ("electronics", 2), ("pharmaceuticals", 1)])),
    ("NO", "GB", 38.0, 8.0,
     _prod([("petroleum", 18), ("natural gas", 14), ("fish", 3), ("aluminum", 1)]),
     _prod([("machinery", 2), ("pharmaceuticals", 2), ("vehicles", 1), ("chemicals", 1)])),
    ("NO", "FR", 12.0, 6.0,
     _prod([("petroleum", 5), ("natural gas", 4), ("fish", 2), ("aluminum", 0.8)]),
     _prod([("aircraft", 1), ("machinery", 1), ("pharmaceuticals", 1), ("food", 0.8)])),
    ("NO", "US", 10.0, 6.0,
     _prod([("petroleum", 4), ("natural gas", 3), ("fish", 1), ("aluminum", 0.8)]),
     _prod([("machinery", 2), ("aircraft", 1), ("chemicals", 0.8), ("electronics", 0.7)])),
    ("NO", "CN", 8.0, 16.0,
     _prod([("petroleum", 3), ("fish", 2), ("aluminum", 1), ("natural gas", 1)]),
     _prod([("electronics", 5), ("machinery", 4), ("textiles", 2), ("chemicals", 2)])),

    # ── Israel bilateral ──────────────────────────────────────────────────────
    ("IL", "US", 14.0, 18.0,
     _prod([("diamonds", 4), ("pharmaceuticals", 3), ("electronics", 3), ("machinery", 2), ("chemicals", 1)]),
     _prod([("diamonds", 5), ("electronics", 4), ("machinery", 3), ("aircraft", 2), ("chemicals", 2)])),
    ("IL", "CN", 4.0, 14.0,
     _prod([("electronics", 1), ("chemicals", 1), ("machinery", 0.8), ("pharmaceuticals", 0.7)]),
     _prod([("electronics", 4), ("machinery", 4), ("textiles", 2), ("chemicals", 2)])),
    ("IL", "GB", 4.0, 4.0,
     _prod([("diamonds", 1), ("pharmaceuticals", 1), ("electronics", 0.8), ("chemicals", 0.6)]),
     _prod([("pharmaceuticals", 1), ("machinery", 1), ("chemicals", 0.8), ("vehicles", 0.5)])),
    ("IL", "DE", 4.0, 6.0,
     _prod([("electronics", 1), ("chemicals", 0.8), ("pharmaceuticals", 0.8), ("diamonds", 0.6)]),
     _prod([("machinery", 1.5), ("vehicles", 1), ("chemicals", 1), ("pharmaceuticals", 0.8)])),

    # ── Chile bilateral ───────────────────────────────────────────────────────
    ("CL", "CN", 28.0, 20.0,
     _prod([("copper", 14), ("lithium", 4), ("iron ore", 3), ("wood pulp", 2), ("food", 2)]),
     _prod([("electronics", 6), ("machinery", 5), ("chemicals", 3), ("vehicles", 2), ("textiles", 2)])),
    ("CL", "US", 10.0, 12.0,
     _prod([("copper", 5), ("fruit", 2), ("wood pulp", 1), ("wine", 0.8)]),
     _prod([("petroleum", 3), ("machinery", 3), ("vehicles", 2), ("chemicals", 1)])),
    ("CL", "JP", 8.0, 6.0,
     _prod([("copper", 4), ("iron ore", 1), ("wood pulp", 0.8), ("food", 0.8)]),
     _prod([("vehicles", 2), ("machinery", 2), ("electronics", 1), ("chemicals", 0.7)])),
    ("CL", "BR", 5.0, 6.0,
     _prod([("copper", 2), ("fruit", 1), ("wine", 0.8), ("chemicals", 0.6)]),
     _prod([("petroleum products", 2), ("vehicles", 1), ("machinery", 1), ("chemicals", 0.8)])),
    ("CL", "KR", 8.0, 6.0,
     _prod([("copper", 4), ("iron ore", 1), ("food", 0.8)]),
     _prod([("vehicles", 2), ("electronics", 1), ("steel", 1), ("machinery", 0.8)])),
    ("CL", "AU", 2.0, 2.0,
     _prod([("copper", 0.8), ("fruit", 0.5), ("wine", 0.3)]),
     _prod([("coal", 0.7), ("machinery", 0.5), ("gold", 0.3), ("grain", 0.3)])),

    # ── Colombia bilateral ────────────────────────────────────────────────────
    ("CO", "US", 12.0, 16.0,
     _prod([("petroleum", 5), ("coal", 3), ("coffee", 1), ("flowers", 1), ("gold", 0.8)]),
     _prod([("machinery", 4), ("petroleum products", 3), ("vehicles", 3), ("chemicals", 2), ("electronics", 1)])),
    ("CO", "CN", 4.0, 12.0,
     _prod([("petroleum", 2), ("coal", 1), ("copper", 0.5), ("coffee", 0.4)]),
     _prod([("electronics", 4), ("machinery", 3), ("textiles", 2), ("chemicals", 1), ("vehicles", 0.8)])),
    ("CO", "BR", 2.0, 3.0,
     _prod([("petroleum", 0.8), ("coal", 0.5), ("coffee", 0.4), ("chemicals", 0.3)]),
     _prod([("petroleum products", 1), ("machinery", 0.8), ("vehicles", 0.6), ("chemicals", 0.4)])),
    ("CO", "MX", 3.0, 4.0,
     _prod([("petroleum", 1), ("coal", 0.6), ("coffee", 0.5), ("chemicals", 0.4)]),
     _prod([("petroleum products", 1), ("machinery", 0.8), ("vehicles", 0.7), ("chemicals", 0.5)])),

    # ── New Zealand bilateral ─────────────────────────────────────────────────
    ("NZ", "CN", 8.0, 10.0,
     _prod([("dairy", 3), ("meat", 2), ("wood", 1), ("wool", 0.8), ("seafood", 0.8)]),
     _prod([("electronics", 3), ("machinery", 2), ("textiles", 1), ("chemicals", 0.8)])),
    ("NZ", "AU", 8.0, 8.0,
     _prod([("dairy", 2), ("meat", 2), ("food", 1), ("machinery", 0.8), ("wine", 0.6)]),
     _prod([("petroleum products", 2), ("machinery", 2), ("vehicles", 1), ("chemicals", 0.8)])),
    ("NZ", "US", 4.0, 6.0,
     _prod([("dairy", 1), ("meat", 1), ("wood", 0.6), ("wine", 0.5)]),
     _prod([("aircraft", 1), ("machinery", 1), ("electronics", 0.8), ("chemicals", 0.6)])),
    ("NZ", "JP", 4.0, 2.0,
     _prod([("dairy", 1), ("meat", 1), ("seafood", 0.6), ("wood", 0.5)]),
     _prod([("vehicles", 0.8), ("machinery", 0.5), ("electronics", 0.4)])),

    # ── South Africa additional pairs ─────────────────────────────────────────
    ("ZA", "CN", 20.0, 44.0,
     _prod([("iron ore", 8), ("copper", 4), ("platinum", 3), ("coal", 3), ("chemicals", 1)]),
     _prod([("electronics", 13), ("machinery", 10), ("textiles", 5), ("steel", 4), ("chemicals", 4)])),
    ("ZA", "US", 12.0, 5.0,
     _prod([("platinum", 5), ("vehicles", 3), ("iron ore", 2), ("gold", 1), ("chemicals", 0.7)]),
     _prod([("machinery", 1), ("aircraft", 0.8), ("vehicles", 0.7), ("chemicals", 0.6)])),
    ("ZA", "DE", 5.0, 4.0,
     _prod([("platinum", 2), ("iron ore", 1), ("vehicles", 1), ("gold", 0.5)]),
     _prod([("vehicles", 1), ("machinery", 1), ("chemicals", 1), ("pharmaceuticals", 0.5)])),

    # ── Indonesia additional pairs ────────────────────────────────────────────
    ("ID", "US", 24.0, 8.0,
     _prod([("electronics", 7), ("rubber", 5), ("machinery", 4), ("palm oil", 4), ("apparel", 3)]),
     _prod([("machinery", 2), ("aircraft", 1), ("soybeans", 1), ("cotton", 0.8), ("petroleum", 0.8)])),
    ("ID", "JP", 26.0, 16.0,
     _prod([("coal", 9), ("copper", 5), ("natural gas", 5), ("palm oil", 4), ("nickel", 2)]),
     _prod([("vehicles", 5), ("machinery", 4), ("electronics", 3), ("steel", 2), ("chemicals", 1)])),
    ("ID", "CN", 36.0, 67.0,
     _prod([("coal", 12), ("palm oil", 9), ("copper", 6), ("natural gas", 5), ("rubber", 3)]),
     _prod([("electronics", 20), ("machinery", 15), ("steel", 8), ("chemicals", 7), ("textiles", 6)])),

    # ── Turkey additional pairs ───────────────────────────────────────────────
    ("TR", "US", 10.0, 12.0,
     _prod([("machinery", 3), ("vehicles", 2), ("iron & steel", 2), ("apparel", 1), ("chemicals", 1)]),
     _prod([("aircraft", 3), ("machinery", 2), ("petroleum products", 2), ("vehicles", 2), ("chemicals", 1)])),
    ("TR", "CN", 3.0, 35.0,
     _prod([("cotton", 1), ("iron ore", 0.8), ("machinery", 0.6), ("chemicals", 0.3)]),
     _prod([("electronics", 10), ("machinery", 8), ("textiles", 5), ("chemicals", 5), ("steel", 4)])),
    ("TR", "AU", 3.0, 2.0,
     _prod([("machinery", 1), ("textiles", 0.8), ("chemicals", 0.5), ("iron & steel", 0.4)]),
     _prod([("coal", 0.8), ("gold", 0.5), ("grain", 0.5)])),

    # ── Pakistan bilateral ────────────────────────────────────────────────────
    ("PK", "CN", 2.0, 18.0,
     _prod([("textiles", 0.8), ("rice", 0.4), ("chemicals", 0.3)]),
     _prod([("machinery", 6), ("electronics", 4), ("steel", 3), ("textiles", 2), ("chemicals", 2)])),
    ("PK", "US", 4.0, 2.0,
     _prod([("apparel", 1), ("textiles", 1), ("rice", 0.4), ("surgical instruments", 0.4)]),
     _prod([("machinery", 0.5), ("grain", 0.4), ("petroleum products", 0.4), ("chemicals", 0.3)])),
    ("PK", "GB", 3.0, 2.0,
     _prod([("apparel", 1), ("textiles", 0.8), ("rice", 0.3), ("leather", 0.3)]),
     _prod([("machinery", 0.5), ("pharmaceuticals", 0.4), ("chemicals", 0.3)])),
    ("PK", "SA", 2.0, 4.0,
     _prod([("food", 0.5), ("textiles", 0.4), ("chemicals", 0.3)]),
     _prod([("petroleum", 3), ("chemicals", 0.6), ("food", 0.3)])),
    ("PK", "AE", 2.0, 6.0,
     _prod([("food", 0.6), ("textiles", 0.5), ("chemicals", 0.3)]),
     _prod([("petroleum", 3), ("gold", 1), ("machinery", 0.8), ("chemicals", 0.5)])),

    # ── Bangladesh bilateral ──────────────────────────────────────────────────
    ("BD", "US", 8.0, 2.0,
     _prod([("apparel & textiles", 6), ("knitwear", 1.5), ("leather goods", 0.3)]),
     _prod([("cotton", 0.6), ("machinery", 0.4), ("petroleum products", 0.3)])),
    ("BD", "DE", 6.0, 2.0,
     _prod([("apparel", 4), ("knitwear", 1.5), ("textiles", 0.4)]),
     _prod([("machinery", 0.6), ("chemicals", 0.4), ("pharmaceuticals", 0.3)])),
    ("BD", "GB", 4.0, 1.0,
     _prod([("apparel", 3), ("knitwear", 0.8), ("textiles", 0.2)]),
     _prod([("pharmaceuticals", 0.3), ("machinery", 0.2), ("chemicals", 0.2)])),
    ("BD", "CN", 1.0, 16.0,
     _prod([("jute", 0.4), ("apparel", 0.3), ("seafood", 0.2)]),
     _prod([("cotton & fabric", 5), ("machinery", 4), ("electronics", 3), ("chemicals", 2), ("steel", 1)])),
    ("BD", "IN", 1.0, 12.0,
     _prod([("apparel", 0.4), ("jute", 0.3), ("seafood", 0.2)]),
     _prod([("cotton", 3), ("machinery", 2), ("chemicals", 2), ("petroleum products", 2), ("food", 1)])),

    # ── Morocco bilateral ─────────────────────────────────────────────────────
    ("MA", "FR", 8.0, 6.0,
     _prod([("apparel", 2), ("automotive parts", 1.5), ("phosphates", 1), ("food", 0.8), ("chemicals", 0.5)]),
     _prod([("aircraft", 1), ("machinery", 1), ("vehicles", 1), ("chemicals", 0.8), ("food", 0.6)])),
    ("MA", "ES", 10.0, 8.0,
     _prod([("automotive parts", 3), ("apparel", 2), ("food", 1.5), ("phosphates", 1), ("electronics", 0.8)]),
     _prod([("machinery", 2), ("vehicles", 1.5), ("chemicals", 1), ("petroleum products", 1), ("food", 0.8)])),
    ("MA", "CN", 1.0, 6.0,
     _prod([("phosphates", 0.5), ("food", 0.3), ("chemicals", 0.2)]),
     _prod([("electronics", 2), ("machinery", 1.5), ("textiles", 0.8), ("chemicals", 0.5)])),
    ("MA", "US", 2.0, 2.0,
     _prod([("apparel", 0.6), ("food", 0.5), ("phosphates", 0.4), ("chemicals", 0.3)]),
     _prod([("aircraft", 0.5), ("machinery", 0.4), ("petroleum products", 0.3), ("chemicals", 0.2)])),

    # ── Ethiopia bilateral ────────────────────────────────────────────────────
    ("ET", "CN", 1.0, 5.0,
     _prod([("coffee", 0.4), ("oilseeds", 0.3), ("gold", 0.2)]),
     _prod([("machinery", 1.5), ("electronics", 1), ("textiles", 0.8), ("steel", 0.6)])),
    ("ET", "US", 0.5, 0.8,
     _prod([("coffee", 0.2), ("oilseeds", 0.1), ("apparel", 0.1)]),
     _prod([("machinery", 0.2), ("aircraft", 0.2), ("grain", 0.2), ("petroleum products", 0.1)])),

    # ── Kenya bilateral ───────────────────────────────────────────────────────
    ("KE", "CN", 0.5, 5.0,
     _prod([("tea", 0.2), ("coffee", 0.1), ("flowers", 0.1)]),
     _prod([("machinery", 1.5), ("electronics", 1.5), ("textiles", 0.8), ("steel", 0.6)])),
    ("KE", "US", 0.6, 0.5,
     _prod([("apparel", 0.2), ("tea", 0.1), ("flowers", 0.1)]),
     _prod([("machinery", 0.1), ("aircraft", 0.1), ("petroleum products", 0.1)])),
    ("KE", "IN", 0.5, 2.0,
     _prod([("tea", 0.2), ("flowers", 0.1), ("coffee", 0.1)]),
     _prod([("petroleum products", 0.8), ("pharmaceuticals", 0.5), ("machinery", 0.3)])),
    ("KE", "AU", 0.2, 0.3,
     _prod([("tea", 0.1), ("flowers", 0.05), ("food", 0.04)]),
     _prod([("grain", 0.1), ("machinery", 0.07), ("gold", 0.05)])),

    # ── Ghana bilateral ───────────────────────────────────────────────────────
    ("GH", "CN", 1.0, 4.0,
     _prod([("gold", 0.5), ("cocoa", 0.3), ("petroleum", 0.1)]),
     _prod([("machinery", 1.2), ("electronics", 1), ("textiles", 0.6), ("steel", 0.5)])),
    ("GH", "IN", 2.0, 2.0,
     _prod([("gold", 0.8), ("cocoa", 0.5), ("petroleum", 0.3), ("timber", 0.2)]),
     _prod([("petroleum products", 0.7), ("pharmaceuticals", 0.5), ("machinery", 0.4), ("textiles", 0.2)])),
    ("GH", "US", 1.0, 0.5,
     _prod([("gold", 0.5), ("cocoa", 0.3), ("petroleum", 0.1)]),
     _prod([("machinery", 0.1), ("petroleum products", 0.1), ("aircraft", 0.1)])),

    # ── Peru bilateral ────────────────────────────────────────────────────────
    ("PE", "CN", 14.0, 10.0,
     _prod([("copper", 6), ("iron ore", 3), ("gold", 2), ("zinc", 1), ("lead", 0.8)]),
     _prod([("electronics", 3), ("machinery", 3), ("textiles", 1.5), ("chemicals", 1), ("vehicles", 0.8)])),
    ("PE", "US", 6.0, 8.0,
     _prod([("copper", 2), ("gold", 1.5), ("zinc", 0.8), ("textiles", 0.7), ("food", 0.6)]),
     _prod([("petroleum products", 2), ("machinery", 2), ("vehicles", 1), ("chemicals", 0.8)])),
    ("PE", "BR", 2.0, 2.0,
     _prod([("copper", 0.7), ("gold", 0.4), ("zinc", 0.3), ("food", 0.3)]),
     _prod([("petroleum products", 0.5), ("vehicles", 0.4), ("chemicals", 0.4), ("machinery", 0.3)])),

    # ── Philippines bilateral ─────────────────────────────────────────────────
    ("PH", "US", 10.0, 8.0,
     _prod([("electronics", 4), ("machinery", 2), ("coconut products", 1), ("apparel", 0.8), ("food", 0.8)]),
     _prod([("electronics", 2), ("machinery", 2), ("petroleum products", 1), ("aircraft", 0.8)])),
    ("PH", "JP", 12.0, 10.0,
     _prod([("electronics", 4), ("machinery", 3), ("coconut products", 1), ("food", 1), ("apparel", 0.8)]),
     _prod([("machinery", 3), ("electronics", 2), ("vehicles", 2), ("steel", 1), ("chemicals", 0.8)])),
    ("PH", "CN", 10.0, 26.0,
     _prod([("electronics", 3), ("copper", 2), ("coconut products", 1), ("food", 1), ("machinery", 0.8)]),
     _prod([("electronics", 8), ("machinery", 7), ("chemicals", 4), ("steel", 3), ("textiles", 2)])),
    ("PH", "KR", 6.0, 10.0,
     _prod([("electronics", 2), ("copper", 1), ("food", 0.8), ("machinery", 0.7)]),
     _prod([("electronics", 3), ("petroleum products", 2), ("machinery", 2), ("steel", 1), ("chemicals", 0.8)])),

    # ── Austria bilateral ─────────────────────────────────────────────────────
    ("AT", "DE", 40.0, 46.0,
     _prod([("machinery", 9), ("vehicles", 8), ("chemicals", 7), ("electronics", 5), ("pharmaceuticals", 4)]),
     _prod([("machinery", 11), ("vehicles", 10), ("chemicals", 8), ("electronics", 7), ("pharmaceuticals", 5)])),
    ("AT", "US", 8.0, 6.0,
     _prod([("machinery", 2), ("pharmaceuticals", 1.5), ("chemicals", 1), ("vehicles", 1)]),
     _prod([("machinery", 1.5), ("aircraft", 1), ("chemicals", 1), ("electronics", 0.8)])),
    ("AT", "CN", 4.0, 10.0,
     _prod([("machinery", 1), ("chemicals", 0.8), ("pharmaceuticals", 0.7), ("vehicles", 0.6)]),
     _prod([("electronics", 3), ("machinery", 3), ("chemicals", 1.5), ("textiles", 1)])),

    # ── Denmark bilateral ─────────────────────────────────────────────────────
    ("DK", "DE", 20.0, 22.0,
     _prod([("machinery", 5), ("pharmaceuticals", 4), ("food", 3), ("chemicals", 3), ("electronics", 2)]),
     _prod([("machinery", 5), ("vehicles", 4), ("chemicals", 4), ("electronics", 3), ("pharmaceuticals", 3)])),
    ("DK", "US", 8.0, 6.0,
     _prod([("pharmaceuticals", 3), ("machinery", 2), ("food", 1), ("chemicals", 1)]),
     _prod([("machinery", 1.5), ("aircraft", 1), ("chemicals", 1), ("electronics", 0.8)])),
    ("DK", "CN", 4.0, 12.0,
     _prod([("pharmaceuticals", 1), ("machinery", 1), ("food", 0.8), ("chemicals", 0.6)]),
     _prod([("electronics", 4), ("machinery", 3), ("textiles", 1.5), ("chemicals", 1)])),

    # ── Finland bilateral ─────────────────────────────────────────────────────
    ("FI", "DE", 10.0, 14.0,
     _prod([("machinery", 2.5), ("chemicals", 2), ("electronics", 1.5), ("paper & pulp", 1.5), ("metals", 1)]),
     _prod([("machinery", 3.5), ("vehicles", 3), ("chemicals", 2), ("electronics", 2), ("pharmaceuticals", 1)])),
    ("FI", "CN", 4.0, 10.0,
     _prod([("machinery", 1), ("chemicals", 0.8), ("paper & pulp", 0.6), ("metals", 0.5)]),
     _prod([("electronics", 3), ("machinery", 3), ("textiles", 1), ("chemicals", 1)])),
    ("FI", "US", 4.0, 4.0,
     _prod([("machinery", 1), ("electronics", 0.8), ("pharmaceuticals", 0.6), ("chemicals", 0.5)]),
     _prod([("machinery", 1), ("aircraft", 0.8), ("chemicals", 0.6), ("electronics", 0.5)])),

    # ── Portugal bilateral ────────────────────────────────────────────────────
    ("PT", "DE", 8.0, 12.0,
     _prod([("vehicles", 2), ("machinery", 1.5), ("apparel", 1), ("food", 1), ("chemicals", 0.8)]),
     _prod([("vehicles", 3), ("machinery", 3), ("chemicals", 2), ("electronics", 1.5), ("pharmaceuticals", 1)])),
    ("PT", "ES", 14.0, 18.0,
     _prod([("vehicles", 3), ("machinery", 2.5), ("food", 2), ("chemicals", 1.5), ("petroleum products", 1)]),
     _prod([("vehicles", 4), ("machinery", 3.5), ("chemicals", 2), ("food", 2), ("petroleum products", 1.5)])),
    ("PT", "FR", 6.0, 8.0,
     _prod([("vehicles", 1.5), ("machinery", 1), ("food", 1), ("chemicals", 0.8), ("apparel", 0.6)]),
     _prod([("vehicles", 2), ("machinery", 1.5), ("chemicals", 1.5), ("aircraft", 1), ("food", 0.8)])),
    ("PT", "US", 3.0, 3.0,
     _prod([("wine", 0.7), ("machinery", 0.5), ("apparel", 0.4), ("chemicals", 0.4)]),
     _prod([("machinery", 0.7), ("aircraft", 0.5), ("chemicals", 0.4), ("electronics", 0.3)])),

    # ── Czech Republic bilateral ──────────────────────────────────────────────
    ("CZ", "DE", 30.0, 28.0,
     _prod([("vehicles", 8), ("machinery", 6), ("electronics", 5), ("chemicals", 4), ("iron & steel", 2)]),
     _prod([("machinery", 7), ("vehicles", 6), ("chemicals", 5), ("electronics", 4), ("pharmaceuticals", 3)])),
    ("CZ", "CN", 3.0, 18.0,
     _prod([("machinery", 0.8), ("vehicles", 0.7), ("electronics", 0.6), ("chemicals", 0.5)]),
     _prod([("electronics", 6), ("machinery", 5), ("textiles", 2), ("chemicals", 2), ("vehicles", 1)])),
    ("CZ", "US", 4.0, 3.0,
     _prod([("machinery", 1), ("vehicles", 0.8), ("electronics", 0.7), ("chemicals", 0.5)]),
     _prod([("machinery", 0.8), ("aircraft", 0.5), ("chemicals", 0.4), ("electronics", 0.3)])),

    # ── Hungary bilateral ─────────────────────────────────────────────────────
    ("HU", "DE", 22.0, 20.0,
     _prod([("vehicles", 6), ("electronics", 5), ("machinery", 4), ("chemicals", 3), ("pharmaceuticals", 2)]),
     _prod([("machinery", 5), ("vehicles", 5), ("chemicals", 4), ("electronics", 3), ("pharmaceuticals", 2)])),
    ("HU", "CN", 2.0, 14.0,
     _prod([("machinery", 0.5), ("vehicles", 0.5), ("electronics", 0.4), ("chemicals", 0.3)]),
     _prod([("electronics", 5), ("machinery", 4), ("textiles", 1.5), ("chemicals", 1.5)])),

    # ── Romania bilateral ─────────────────────────────────────────────────────
    ("RO", "DE", 14.0, 16.0,
     _prod([("vehicles", 4), ("machinery", 3), ("electronics", 2), ("apparel", 1.5), ("chemicals", 1)]),
     _prod([("machinery", 4), ("vehicles", 3), ("chemicals", 2.5), ("electronics", 2), ("pharmaceuticals", 1.5)])),
    ("RO", "IT", 10.0, 8.0,
     _prod([("vehicles", 2.5), ("machinery", 2), ("apparel", 1.5), ("chemicals", 1), ("food", 0.8)]),
     _prod([("machinery", 2), ("vehicles", 1.5), ("chemicals", 1.5), ("pharmaceuticals", 1), ("fashion", 0.8)])),
    ("RO", "FR", 6.0, 6.0,
     _prod([("vehicles", 1.5), ("machinery", 1), ("apparel", 0.8), ("chemicals", 0.7)]),
     _prod([("vehicles", 1.5), ("machinery", 1.5), ("chemicals", 1), ("aircraft", 0.8)])),
    ("RO", "CN", 1.0, 6.0,
     _prod([("machinery", 0.3), ("chemicals", 0.2), ("food", 0.2)]),
     _prod([("electronics", 2), ("machinery", 2), ("textiles", 0.8), ("chemicals", 0.7)])),

    # ── Algeria bilateral ─────────────────────────────────────────────────────
    ("DZ", "IT", 12.0, 4.0,
     _prod([("petroleum", 6), ("natural gas", 5), ("chemicals", 0.6)]),
     _prod([("machinery", 1), ("vehicles", 0.8), ("food", 0.6), ("chemicals", 0.5)])),
    ("DZ", "FR", 10.0, 6.0,
     _prod([("petroleum", 5), ("natural gas", 4), ("chemicals", 0.5)]),
     _prod([("machinery", 1.5), ("vehicles", 1), ("food", 1), ("pharmaceuticals", 0.8)])),
    ("DZ", "ES", 8.0, 4.0,
     _prod([("petroleum", 4), ("natural gas", 3), ("chemicals", 0.4)]),
     _prod([("machinery", 1), ("food", 0.8), ("vehicles", 0.7), ("chemicals", 0.5)])),
    ("DZ", "CN", 1.0, 8.0,
     _prod([("petroleum", 0.6), ("natural gas", 0.3)]),
     _prod([("electronics", 2.5), ("machinery", 2.5), ("textiles", 1), ("steel", 0.8)])),
]


def seed_trade(db: Session) -> int:
    # Load all country codes → ids
    rows = db.execute(
        "SELECT id, code, numeric_code FROM countries"
    ).fetchall() if False else []

    # Use ORM select
    from sqlalchemy import select as sa_select
    rows = db.execute(sa_select(Country.id, Country.code)).all()
    country_map: dict[str, int] = {row.code: row.id for row in rows}

    # Load most recent GDP per country for gdp_share calculation
    from app.models.country import CountryIndicator
    gdp_rows = db.execute(
        sa_select(CountryIndicator.country_id, CountryIndicator.value)
        .where(CountryIndicator.indicator == "gdp_usd")
        .order_by(CountryIndicator.period_date.desc())
    ).all()
    gdp_map: dict[int, float] = {}
    for r in gdp_rows:
        if r.country_id not in gdp_map:
            gdp_map[r.country_id] = r.value

    def gdp_share(country_code: str, trade_usd: float) -> float | None:
        cid = country_map.get(country_code)
        gdp = gdp_map.get(cid) if cid else None
        if gdp and gdp > 0:
            return round((trade_usd / gdp) * 100, 2)
        return None

    records: list[dict] = []
    year = 2022

    # Deduplicate — avoid same (exporter, importer) appearing twice in source list
    seen: set[tuple[str, str]] = set()

    for row in BILATERAL_FLOWS:
        exp_code, imp_code, exports_b, imports_b, top_exp_prods, top_imp_prods = row
        exp_id = country_map.get(exp_code)
        imp_id = country_map.get(imp_code)
        if not exp_id or not imp_id:
            log.warning(f"Skipping {exp_code}→{imp_code}: country not found in DB")
            continue

        pair = (exp_code, imp_code)
        if pair in seen:
            continue
        seen.add(pair)

        exports_usd = exports_b * B
        imports_usd = imports_b * B
        trade_value = exports_usd + imports_usd

        # Forward pair: (exporter, importer)
        records.append({
            "exporter_id": exp_id,
            "importer_id": imp_id,
            "year": year,
            "trade_value_usd": trade_value,
            "exports_usd": exports_usd,
            "imports_usd": imports_usd,
            "balance_usd": exports_usd - imports_usd,
            "top_export_products": top_exp_prods,
            "top_import_products": top_imp_prods,
            "exporter_gdp_share_pct": gdp_share(exp_code, trade_value),
            "importer_gdp_share_pct": gdp_share(imp_code, trade_value),
        })

        # Reverse pair: (importer, exporter) — flip exports/imports and products
        rev_pair = (imp_code, exp_code)
        if rev_pair not in seen:
            seen.add(rev_pair)
            records.append({
                "exporter_id": imp_id,
                "importer_id": exp_id,
                "year": year,
                "trade_value_usd": trade_value,
                "exports_usd": imports_usd,
                "imports_usd": exports_usd,
                "balance_usd": imports_usd - exports_usd,
                "top_export_products": top_imp_prods,
                "top_import_products": top_exp_prods,
                "exporter_gdp_share_pct": gdp_share(imp_code, trade_value),
                "importer_gdp_share_pct": gdp_share(exp_code, trade_value),
            })

    if not records:
        log.warning("No trade records to insert")
        return 0

    stmt = pg_insert(TradePair).values(records)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_trade_pair_year",
        set_={
            col: stmt.excluded[col]
            for col in records[0].keys()
            if col not in ("exporter_id", "importer_id", "year")
        },
    )
    db.execute(stmt)
    db.commit()
    log.info(f"Upserted {len(records)} trade pair records ({len(records)//2} unique pairs × 2 directions)")
    return len(records)


def run() -> None:
    db = SessionLocal()
    try:
        total = seed_trade(db)
        log.info(f"Done. {total} trade pairs in database.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
