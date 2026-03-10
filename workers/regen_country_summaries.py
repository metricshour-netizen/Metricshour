"""
One-shot script: regenerate ALL country summaries via DeepSeek.
Run: cd /root/metricshour/workers && python regen_country_summaries.py

Clears the existing summary and rewrites using the updated prompt.
Processes all 196 countries with a small delay to avoid API rate limits.
"""
import sys, time, logging, os
sys.path.insert(0, "/root/metricshour/backend")
sys.path.insert(0, "/root/metricshour/workers")
# Load .env so AI keys are available
from dotenv import load_dotenv
load_dotenv("/root/metricshour/backend/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

from datetime import datetime, timezone
from app.database import SessionLocal
from app.models.country import Country
from app.models.summary import PageSummary
from tasks.summaries import _country_summary_text

def main():
    with SessionLocal() as db:
        # Skip countries already updated today (generated_at >= today) to resume safely
        from datetime import date as _date
        today = _date.today()
        already_done = {
            r.entity_code
            for r in db.query(PageSummary)
            .filter(PageSummary.entity_type == "country")
            .all()
            if r.generated_at.date() >= today
        }
        countries = [
            c for c in db.query(Country).order_by(Country.name).all()
            if c.code not in already_done
        ]
        log.info("Skipping %d already updated today", len(already_done))
        log.info("Found %d countries to process", len(countries))

        ok = 0
        fail = 0
        for i, country in enumerate(countries, 1):
            try:
                text = _country_summary_text(country, db)
                if not text or len(text.strip()) < 50:
                    log.warning("[%d/%d] %s — empty result, skipping", i, len(countries), country.name)
                    fail += 1
                    continue

                row = (
                    db.query(PageSummary)
                    .filter_by(entity_type="country", entity_code=country.code)
                    .first()
                )
                if row:
                    row.summary = text
                    row.generated_at = datetime.now(timezone.utc)
                else:
                    db.add(PageSummary(
                        entity_type="country",
                        entity_code=country.code,
                        summary=text,
                        generated_at=datetime.now(timezone.utc),
                    ))
                db.commit()
                words = len(text.split())
                log.info("[%d/%d] %-30s — %d words ✓", i, len(countries), country.name, words)
                ok += 1
                time.sleep(0.4)  # ~2.5 req/s — well within DeepSeek limits
            except Exception as exc:
                db.rollback()
                log.error("[%d/%d] %s — ERROR: %s", i, len(countries), country.name, exc)
                fail += 1

        log.info("Done — %d updated, %d failed", ok, fail)

if __name__ == "__main__":
    main()
