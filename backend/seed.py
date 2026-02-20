"""
Run all seeders in dependency order.
Usage: python seed.py [--only countries|world_bank]
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run_all() -> None:
    only = None
    if "--only" in sys.argv:
        idx = sys.argv.index("--only")
        only = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        if not only or only == "countries":
            log.info("=== Seeding countries ===")
            from app.seeders.countries import seed_countries
            seed_countries(db)

        if not only or only == "world_bank":
            log.info("=== Seeding World Bank indicators ===")
            from app.seeders.world_bank import seed_world_bank
            seed_world_bank(db)

        if not only or only == "assets":
            log.info("=== Seeding assets (stocks, commodities, crypto, FX) ===")
            from app.seeders.assets import seed_assets
            seed_assets(db)

        if not only or only == "trade":
            log.info("=== Seeding trade pairs (G20 bilateral flows) ===")
            from app.seeders.trade import seed_trade
            seed_trade(db)

        if not only or only == "edgar":
            log.info("=== Seeding stock geographic revenue (SEC EDGAR) ===")
            from app.seeders.edgar import seed_edgar
            seed_edgar(db)

    finally:
        db.close()

    log.info("=== All seeders complete ===")


if __name__ == "__main__":
    run_all()
