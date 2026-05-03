"""
Bulk generate summaries + insights for all China A-share stocks (SHG/SHE).
Uses DeepSeek as primary AI (same as main summaries.py task).
Run: source /root/metricshour/workers/venv/bin/activate && python bulk_china_insights.py
"""
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _base)
sys.path.insert(0, os.path.join(_base, "..", "backend"))

from sqlalchemy import select
from app.database import SessionLocal
from app.models.asset import Asset
from app.models.summary import PageSummary, PageInsight
from tasks.summaries import _stock_summary_text, _stock_insight_text

EXCHANGES = ("SHG", "SHE")
MAX_WORKERS = 4


def run():
    db = SessionLocal()
    try:
        stocks = db.execute(
            select(Asset).where(Asset.exchange.in_(EXCHANGES))
        ).scalars().all()
        log.info("Found %d China A-share stocks", len(stocks))

        # ── 1. Summaries ──────────────────────────────────────────────────────
        existing_sums = set(
            r[0] for r in db.execute(
                select(PageSummary.entity_code)
                .where(PageSummary.entity_type == "stock",
                       PageSummary.entity_code.in_([s.symbol for s in stocks]))
            ).all()
        )
        missing_sums = [s for s in stocks if s.symbol not in existing_sums]
        log.info("Summaries to generate: %d", len(missing_sums))

        done_s = skipped_s = 0
        for asset in missing_sums:
            try:
                text = _stock_summary_text(asset, db)
                if text:
                    db.add(PageSummary(
                        entity_type="stock",
                        entity_code=asset.symbol,
                        summary=text,
                        generated_at=datetime.now(timezone.utc),
                    ))
                    db.commit()
                    done_s += 1
                    log.info("[summary] ✓ %s", asset.symbol)
                else:
                    skipped_s += 1
                    log.warning("[summary] empty: %s", asset.symbol)
            except Exception as e:
                db.rollback()
                skipped_s += 1
                log.error("[summary] error %s: %s", asset.symbol, e)

        log.info("Summaries done: %d / skipped: %d", done_s, skipped_s)

        # ── 2. Insights ───────────────────────────────────────────────────────
        existing_ins = set(
            r[0] for r in db.execute(
                select(PageInsight.entity_code)
                .where(PageInsight.entity_type == "stock",
                       PageInsight.entity_code.in_([s.symbol for s in stocks]))
            ).all()
        )
        missing_ins = [s for s in stocks if s.symbol not in existing_ins]
        log.info("Insights to generate: %d", len(missing_ins))

        done_i = skipped_i = 0

        def gen_insight(asset):
            local_db = SessionLocal()
            try:
                text = _stock_insight_text(asset, local_db)
                return asset.symbol, text
            except Exception as e:
                log.error("[insight] error %s: %s", asset.symbol, e)
                return asset.symbol, None
            finally:
                local_db.close()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(gen_insight, a): a for a in missing_ins}
            for future in as_completed(futures):
                symbol, text = future.result()
                if text:
                    try:
                        db.add(PageInsight(
                            entity_type="stock",
                            entity_code=symbol,
                            summary=text,
                            generated_at=datetime.now(timezone.utc),
                        ))
                        db.commit()
                        done_i += 1
                        log.info("[insight] ✓ %s", symbol)
                    except Exception as e:
                        db.rollback()
                        skipped_i += 1
                        log.error("[insight] db error %s: %s", symbol, e)
                else:
                    skipped_i += 1
                    log.warning("[insight] empty: %s", symbol)

        log.info("Insights done: %d / skipped: %d", done_i, skipped_i)

    finally:
        db.close()


if __name__ == "__main__":
    run()
