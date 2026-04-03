"""
us_rewrite.py — Force-regenerate summaries + insights for US stocks
that still reference stale 2023 data.

Reuses the existing _stock_summary_text / _stock_insight_text pipeline
so EDGAR geographic revenue data is included automatically.

Run:
    source /root/metricshour/workers/venv/bin/activate
    python us_rewrite.py [--insights-only | --summaries-only | --symbol AAPL]

Progress saved to /tmp/us_rewrite_state.json (resume-safe).
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _base)
sys.path.insert(0, os.path.join(_base, "..", "backend"))

from dotenv import load_dotenv
load_dotenv(os.path.join(_base, "..", "backend", ".env"))

from sqlalchemy import select, text
from app.database import SessionLocal
from app.models.asset import Asset
from app.models.summary import PageSummary, PageInsight
from tasks.summaries import _stock_summary_text, _stock_insight_text

STATE_FILE = Path("/tmp/us_rewrite_state.json")
REQUEST_DELAY = 1.5  # seconds between Gemini calls


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"done_summaries": [], "done_insights": [], "failed": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _upsert_summary(db, symbol: str, text_: str):
    existing = db.execute(
        select(PageSummary).where(
            PageSummary.entity_type == "stock",
            PageSummary.entity_code == symbol,
        )
    ).scalars().first()
    if existing:
        existing.summary = text_
        existing.generated_at = datetime.now(timezone.utc)
    else:
        db.add(PageSummary(
            entity_type="stock",
            entity_code=symbol,
            summary=text_,
            generated_at=datetime.now(timezone.utc),
        ))
    db.commit()


def _upsert_insight(db, symbol: str, text_: str):
    existing = db.execute(
        select(PageInsight).where(
            PageInsight.entity_type == "stock",
            PageInsight.entity_code == symbol,
        )
    ).scalars().first()
    if existing:
        existing.summary = text_
        existing.generated_at = datetime.now(timezone.utc)
    else:
        db.add(PageInsight(
            entity_type="stock",
            entity_code=symbol,
            summary=text_,
            generated_at=datetime.now(timezone.utc),
        ))
    db.commit()


def get_stale_symbols(db, only_symbol: str | None) -> list[str]:
    """Return symbols of US stocks whose summaries reference 2023."""
    if only_symbol:
        return [only_symbol.upper()]
    rows = db.execute(text(
        "SELECT entity_code FROM page_summaries "
        "WHERE entity_type='stock' AND entity_code NOT SIMILAR TO '[0-9]{6}' "
        "AND (summary ILIKE '%2023%' OR summary ILIKE '%FY2023%' "
        "     OR summary ILIKE '%fiscal year 2023%')"
        "ORDER BY entity_code"
    )).fetchall()
    return [r[0] for r in rows]


def run(do_summaries: bool = True, do_insights: bool = True, only_symbol: str | None = None):
    db = SessionLocal()
    state = load_state()

    try:
        stale = get_stale_symbols(db, only_symbol)
        log.info("Stale US stocks to process: %d", len(stale))

        # Load asset objects for stale symbols
        assets = {
            a.symbol: a
            for a in db.execute(
                select(Asset).where(Asset.symbol.in_(stale), Asset.asset_type == "stock")
            ).scalars().all()
        }

        # ── Summaries ─────────────────────────────────────────────────────────
        if do_summaries:
            todo = [s for s in stale if s not in state["done_summaries"]]
            log.info("Summaries to regenerate: %d", len(todo))
            for i, symbol in enumerate(todo, 1):
                asset = assets.get(symbol)
                if not asset:
                    log.warning("[%d/%d] asset not found: %s", i, len(todo), symbol)
                    state["failed"].append(f"summary:{symbol}")
                    save_state(state)
                    continue
                try:
                    text_ = _stock_summary_text(asset, db)
                    if text_ and len(text_.split()) >= 80:
                        _upsert_summary(db, symbol, text_)
                        state["done_summaries"].append(symbol)
                        save_state(state)
                        log.info("[%d/%d] summary OK: %s (%d words)", i, len(todo), symbol, len(text_.split()))
                    else:
                        state["failed"].append(f"summary:{symbol}")
                        save_state(state)
                        log.warning("[%d/%d] summary too short or empty: %s", i, len(todo), symbol)
                except Exception as e:
                    state["failed"].append(f"summary:{symbol}")
                    save_state(state)
                    log.error("[%d/%d] summary ERROR: %s — %s", i, len(todo), symbol, e)
                time.sleep(REQUEST_DELAY)

        # ── Insights ──────────────────────────────────────────────────────────
        if do_insights:
            # For insights, process all stale stocks (not just those in done_summaries)
            todo_i = [s for s in stale if s not in state["done_insights"]]
            log.info("Insights to regenerate: %d", len(todo_i))
            for i, symbol in enumerate(todo_i, 1):
                asset = assets.get(symbol)
                if not asset:
                    log.warning("[%d/%d] asset not found for insight: %s", i, len(todo_i), symbol)
                    state["failed"].append(f"insight:{symbol}")
                    save_state(state)
                    continue
                try:
                    text_ = _stock_insight_text(asset, db)
                    if text_ and len(text_.split()) >= 30:
                        _upsert_insight(db, symbol, text_)
                        state["done_insights"].append(symbol)
                        save_state(state)
                        log.info("[%d/%d] insight OK: %s (%d words)", i, len(todo_i), symbol, len(text_.split()))
                    else:
                        state["failed"].append(f"insight:{symbol}")
                        save_state(state)
                        log.warning("[%d/%d] insight too short or empty: %s", i, len(todo_i), symbol)
                except Exception as e:
                    state["failed"].append(f"insight:{symbol}")
                    save_state(state)
                    log.error("[%d/%d] insight ERROR: %s — %s", i, len(todo_i), symbol, e)
                time.sleep(REQUEST_DELAY)

    finally:
        db.close()

    log.info("=" * 60)
    log.info("Summaries done: %d", len(state["done_summaries"]))
    log.info("Insights done:  %d", len(state["done_insights"]))
    log.info("Failed:         %d", len(state["failed"]))
    if state["failed"]:
        log.warning("Failed: %s", state["failed"][:20])
    STATE_FILE.unlink(missing_ok=True)
    log.info("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate stale US stock summaries/insights")
    parser.add_argument("--summaries-only", action="store_true")
    parser.add_argument("--insights-only", action="store_true")
    parser.add_argument("--symbol", help="Single symbol only (testing)")
    args = parser.parse_args()

    run(
        do_summaries=not args.insights_only,
        do_insights=not args.summaries_only,
        only_symbol=args.symbol,
    )
