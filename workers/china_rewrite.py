"""
china_rewrite.py — Rewrite all 300 China A-share stock summaries + insights using DeepSeek.

The old summaries used the US/SEC EDGAR template and are broken
(wrong HQ, "data pending" language, irrelevant geographic revenue framing).
This script wipes and regenerates with China-specific prompts.

Run:
    source /root/metricshour/workers/venv/bin/activate
    python china_rewrite.py [--summaries-only | --insights-only | --symbol 600028]

Progress is saved to /tmp/china_rewrite_state.json so it can be resumed safely.
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

import requests
from sqlalchemy import select, delete
from app.database import SessionLocal
from app.models.asset import Asset
from app.models.summary import PageSummary, PageInsight

# ── Config ────────────────────────────────────────────────────────────────────
EXCHANGES = ("SHG", "SHE")
STATE_FILE = Path("/tmp/china_rewrite_state.json")
RETRY_DELAY = 3      # seconds between retries
MAX_RETRIES = 3
REQUEST_DELAY = 0.8  # seconds between API calls (rate limit safety)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a financial data writer for an institutional equity terminal covering China A-share markets. "
    "OUTPUT ONLY the paragraph requested — no greeting, no sign-off, no 'Certainly', "
    "no meta-commentary, no markdown, no bullet points, no headers. "
    "Write in third person. Active voice. Assert — never hedge. "
    "Do not use: could, may, might, would likely, appears to, seems to, is expected to, is poised to. "
    "BANNED WORDS: navigates, robust, resilient, notable, significant, landscape, remains, amid, "
    "complex, dynamic, headwinds, tailwinds, uncertainty, poised, well-positioned, strategic, "
    "synergies, leverage, ecosystem, stakeholders, highlights, reflects, showcases, demonstrates, "
    "continues to, going forward, in conclusion, furthermore, moreover, additionally, importantly, "
    "comprehensive, pivotal, unprecedented, delve, hallmark, boasts, bolsters, underpins, spurs, "
    "it is worth noting, it should be noted, plays a key role, plays a crucial role."
)

# ── Exchange labels ───────────────────────────────────────────────────────────
EXCHANGE_LABEL = {
    "SHG": "Shanghai Stock Exchange (SSE)",
    "SHE": "Shenzhen Stock Exchange (SZSE)",
}


# ── DeepSeek call ─────────────────────────────────────────────────────────────
def _call_deepseek(prompt: str, min_words: int, max_words: int) -> str | None:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 600,
                    "temperature": 0.15,
                    "frequency_penalty": 0.3,
                },
                timeout=45,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            # Strip any accidental markdown
            text = text.lstrip("#").strip()
            words = len(text.split())
            if (min_words - 15) <= words <= (max_words + 20):
                return text
            log.warning("Word count %d outside [%d-%d], retrying", words, min_words, max_words)
        except Exception as e:
            log.warning("Attempt %d/%d failed for prompt: %s", attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
    return None


# ── Summary prompt ────────────────────────────────────────────────────────────
def _summary_prompt(symbol: str, name: str, exchange: str) -> str:
    exch_label = EXCHANGE_LABEL.get(exchange, exchange)
    return (
        f"China A-share stock overview — {name} ({symbol}) listed on {exch_label}. "
        f"220-260 words. Third-person. No title. No headings. No bullet points.\n\n"
        f"Write 5 paragraphs:\n"
        f"(1) Company identity: full legal name, exchange listing, and core business. "
        f"Describe what the company actually does — its primary products or services. "
        f"State whether it is state-owned or privately controlled.\n"
        f"(2) Market position: where does this company rank within its sector in China? "
        f"Name its primary competitive advantages, major customers or contracts if known, "
        f"and the geographic scope of its domestic operations.\n"
        f"(3) Revenue and earnings drivers: what are the top 2-3 factors that drive this "
        f"company's revenue and profit margins? Name specific inputs, prices, or volume metrics "
        f"that matter most (e.g. coal price per tonne, passenger load factor, net interest margin).\n"
        f"(4) China macro linkage: which specific Chinese economic indicators most directly "
        f"affect this stock's earnings? Name the data releases to watch — e.g. PBOC loan prime rate, "
        f"NBS industrial output, retail sales, property investment data, or PPI.\n"
        f"(5) Risk factors: name 2 specific risks — regulatory, competitive, commodity, or "
        f"currency-related — that could compress margins or reduce earnings in the next 12 months.\n"
        f"Every sentence contains at least one specific fact, number, or named entity. "
        f"No padding. End with a period."
    )


# ── Insight prompt ────────────────────────────────────────────────────────────
def _insight_prompt(symbol: str, name: str, exchange: str) -> str:
    exch_label = EXCHANGE_LABEL.get(exchange, exchange)
    return (
        f"China A-share investor insight — {name} ({symbol}), {exch_label}. "
        f"65-85 words. Three sentences only. No title. No headings. No bullet points.\n\n"
        f"Sentence 1: State the company's current market position or the dominant theme "
        f"shaping its sector in China right now — be specific with a number or named policy/event.\n"
        f"Sentence 2: Name the single most important catalyst or headwind for this stock "
        f"over the next 6-12 months — reference a specific macro variable, regulatory action, "
        f"or pricing trend by name.\n"
        f"Sentence 3: State what data point or event investors should watch to confirm or "
        f"invalidate the thesis — name the release, regulator, or metric precisely.\n"
        f"No hedging language. Every sentence asserts. End with a period."
    )


# ── Progress state ─────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"done_summaries": [], "done_insights": [], "failed": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Main ──────────────────────────────────────────────────────────────────────
def run(do_summaries: bool = True, do_insights: bool = True, only_symbol: str | None = None):
    db = SessionLocal()
    state = load_state()

    try:
        q = select(Asset).where(Asset.exchange.in_(EXCHANGES))
        if only_symbol:
            q = q.where(Asset.symbol == only_symbol)
        stocks = db.execute(q).scalars().all()
        log.info("Loaded %d China A-share stocks", len(stocks))

        # ── Step 1: Delete old broken entries (only for phases being run) ────
        symbols = [s.symbol for s in stocks]
        if do_summaries:
            log.info("Deleting old summaries for %d stocks...", len(symbols))
            db.execute(
                delete(PageSummary).where(
                    PageSummary.entity_type == "stock",
                    PageSummary.entity_code.in_(symbols)
                )
            )
        if do_insights:
            log.info("Deleting old insights for %d stocks...", len(symbols))
            db.execute(
                delete(PageInsight).where(
                    PageInsight.entity_type == "stock",
                    PageInsight.entity_code.in_(symbols)
                )
            )
        db.commit()
        log.info("Old entries deleted. Starting generation...")

        # ── Step 2: Summaries ─────────────────────────────────────────────────
        if do_summaries:
            todo = [s for s in stocks if s.symbol not in state["done_summaries"]]
            log.info("Summaries to generate: %d", len(todo))
            for i, asset in enumerate(todo, 1):
                prompt = _summary_prompt(asset.symbol, asset.name, asset.exchange or "SHG")
                text = _call_deepseek(prompt, min_words=180, max_words=300)
                if text:
                    db.merge(PageSummary(
                        entity_type="stock",
                        entity_code=asset.symbol,
                        summary=text,
                        generated_at=datetime.now(timezone.utc),
                    ))
                    db.commit()
                    state["done_summaries"].append(asset.symbol)
                    save_state(state)
                    log.info("[%d/%d] summary OK: %s (%d words)", i, len(todo), asset.symbol, len(text.split()))
                else:
                    state["failed"].append(f"summary:{asset.symbol}")
                    save_state(state)
                    log.warning("[%d/%d] summary FAILED: %s", i, len(todo), asset.symbol)
                time.sleep(REQUEST_DELAY)

        # ── Step 3: Insights ──────────────────────────────────────────────────
        if do_insights:
            todo = [s for s in stocks if s.symbol not in state["done_insights"]]
            log.info("Insights to generate: %d", len(todo))
            for i, asset in enumerate(todo, 1):
                prompt = _insight_prompt(asset.symbol, asset.name, asset.exchange or "SHG")
                text = _call_deepseek(prompt, min_words=55, max_words=95)
                if text:
                    db.merge(PageInsight(
                        entity_type="stock",
                        entity_code=asset.symbol,
                        summary=text,
                        generated_at=datetime.now(timezone.utc),
                    ))
                    db.commit()
                    state["done_insights"].append(asset.symbol)
                    save_state(state)
                    log.info("[%d/%d] insight OK: %s (%d words)", i, len(todo), asset.symbol, len(text.split()))
                else:
                    state["failed"].append(f"insight:{asset.symbol}")
                    save_state(state)
                    log.warning("[%d/%d] insight FAILED: %s", i, len(todo), asset.symbol)
                time.sleep(REQUEST_DELAY)

    finally:
        db.close()

    # ── Summary report ────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info("Summaries done: %d", len(state["done_summaries"]))
    log.info("Insights done:  %d", len(state["done_insights"]))
    log.info("Failed:         %d", len(state["failed"]))
    if state["failed"]:
        log.warning("Failed items: %s", state["failed"][:20])
    STATE_FILE.unlink(missing_ok=True)
    log.info("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rewrite China A-share summaries + insights")
    parser.add_argument("--summaries-only", action="store_true")
    parser.add_argument("--insights-only", action="store_true")
    parser.add_argument("--symbol", help="Process a single symbol only (for testing)")
    args = parser.parse_args()

    do_s = not args.insights_only
    do_i = not args.summaries_only

    run(do_summaries=do_s, do_insights=do_i, only_symbol=args.symbol)
