"""
Regenerate country summaries that are still too short (<180 words).
Calls DeepSeek directly (bypasses word-count gate in _call_ai).
Falls back to Gemini 2.5-flash if DeepSeek fails.
Run: cd /root/metricshour/workers && python regen_short_summaries.py
"""
import sys, time, logging, os, requests
sys.path.insert(0, "/root/metricshour/backend")
sys.path.insert(0, "/root/metricshour/workers")
from dotenv import load_dotenv
load_dotenv("/root/metricshour/backend/.env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

from datetime import datetime, timezone
import google.genai as genai
from app.database import SessionLocal
from app.models.country import Country, CountryIndicator
from app.models.summary import PageSummary

MIN_SAVE = 180
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

_gemini_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None


def _strip_markdown(text: str) -> str:
    import re
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^#{1,3}\s+.*$', '', text, flags=re.MULTILINE)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _build_prompt(country, indicators: dict) -> str:
    def v(key): return indicators.get(key)
    gdp = v("gdp_usd")
    growth = v("gdp_growth_pct")
    inflation = v("inflation_pct")
    rate = v("interest_rate_pct")
    unemployment = v("unemployment_pct")
    debt = v("government_debt_gdp_pct")

    if gdp is None:
        gdp_str = "N/A"
    elif gdp >= 1e12:
        gdp_str = f"{gdp/1e12:.1f} trillion dollars"
    elif gdp >= 1e9:
        gdp_str = f"{gdp/1e9:.0f} billion dollars"
    else:
        gdp_str = f"{gdp/1e6:.0f} million dollars"

    groups = [g for g in ["G7","G20","EU","Eurozone","NATO","OPEC","BRICS","ASEAN","OECD"]
              if getattr(country, f"is_{g.lower()}", False)]
    currency = f"{country.currency_name} ({country.currency_code})" if country.currency_code else country.currency_name or "N/A"
    dev_status = "developed" if country.is_oecd else ("emerging" if (gdp or 0) > 50e9 else "frontier")

    facts = (
        f"Country: {country.name} ({country.code})\n"
        f"Region: {country.region}, {country.subregion}\n"
        f"GDP: {gdp_str}\n"
        f"GDP growth: {f'{growth:.1f}%' if growth is not None else 'N/A'}\n"
        f"Inflation: {f'{inflation:.1f}%' if inflation is not None else 'N/A'}\n"
        f"Central bank policy rate: {f'{rate:.2f}%' if rate is not None else 'N/A'}\n"
        f"Unemployment: {f'{unemployment:.1f}%' if unemployment is not None else 'N/A'}\n"
        f"Government debt (% of GDP): {f'{debt:.0f}%' if debt is not None else 'N/A'}\n"
        f"S&P credit rating: {country.credit_rating_sp or 'N/A'}\n"
        f"International group memberships: {', '.join(groups) if groups else 'UN member'}\n"
        f"Currency: {currency}\n"
        f"Major exports: {country.major_exports or 'N/A'}\n"
    )
    return (
        f"Country overview — {country.name} — 220-280 words. Third-person. No title. No headings.\n\n"
        f"Data:\n{facts}\n\n"
        f"Write 5 tight paragraphs (2-3 sentences each):\n"
        f"1. GDP size and growth: classify the economy ({dev_status}), state GDP and growth rate. Compare to a well-known benchmark only if the comparison is meaningful.\n"
        f"2. Monetary policy: state the inflation rate and central bank policy rate. Describe the stance (restrictive/neutral/accommodative) and the real rate (policy minus inflation).\n"
        f"3. Labour and fiscal: state unemployment and government debt as % of GDP. Assess fiscal sustainability. State what the S&P rating (or its absence) implies about sovereign credit risk.\n"
        f"4. External position: major exports and the country's primary trade dependency. Use only data provided — do not invent trade share percentages.\n"
        f"5. Geopolitical and structural: bloc memberships that shape trade and capital flows, currency, and the single biggest structural risk or opportunity for investors.\n"
        f"Rules: use provided numbers only — never invent statistics. No filler phrases. No repeated points. Every paragraph must add new information. End with a period."
    )


def _call_deepseek(prompt: str, retries: int = 2) -> str | None:
    if not DEEPSEEK_KEY:
        return None
    for attempt in range(retries):
        try:
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "You are a financial data analyst. Write precisely to the requested word count."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 600,
                    "temperature": 0.2,
                },
                timeout=30,
            )
            resp.raise_for_status()
            text = _strip_markdown(resp.json()["choices"][0]["message"]["content"].strip())
            words = len(text.split())
            if words >= MIN_SAVE:
                return text
            log.debug("DeepSeek returned %d words (attempt %d)", words, attempt + 1)
        except Exception as exc:
            log.debug("DeepSeek error (attempt %d): %s", attempt + 1, exc)
            if attempt < retries - 1:
                time.sleep(2)
    return None


def _call_gemini(prompt: str, retries: int = 2) -> str | None:
    if not _gemini_client:
        return None
    for attempt in range(retries):
        try:
            r = _gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            text = _strip_markdown(r.text.strip())
            words = len(text.split())
            if words >= MIN_SAVE:
                return text
            log.debug("Gemini returned %d words (attempt %d)", words, attempt + 1)
        except Exception as exc:
            log.debug("Gemini error (attempt %d): %s", attempt + 1, exc)
            if attempt < retries - 1:
                time.sleep(3)
    return None


def _get_indicators(country, db) -> dict:
    rows = (
        db.query(CountryIndicator)
        .filter(CountryIndicator.country_id == country.id)
        .filter(CountryIndicator.indicator.in_([
            "gdp_usd", "gdp_growth_pct", "inflation_pct",
            "interest_rate_pct", "unemployment_pct",
            "government_debt_gdp_pct",
        ]))
        .order_by(CountryIndicator.period_date.desc())
        .limit(30)
        .all()
    )
    seen: set = set()
    out: dict = {}
    for r in rows:
        if r.indicator not in seen:
            out[r.indicator] = r.value
            seen.add(r.indicator)
    return out


def main():
    with SessionLocal() as db:
        all_summaries = {
            r.entity_code: r
            for r in db.query(PageSummary).filter(PageSummary.entity_type == "country").all()
        }
        short_codes = {
            code for code, row in all_summaries.items()
            if len(row.summary.split()) < MIN_SAVE
        }
        countries = [
            c for c in db.query(Country).order_by(Country.name).all()
            if c.code in short_codes or c.code not in all_summaries
        ]
        log.info("Found %d countries with summaries <%d words (or missing)", len(countries), MIN_SAVE)

        ok = fail = skip = 0
        for i, country in enumerate(countries, 1):
            try:
                indicators = _get_indicators(country, db)
                prompt = _build_prompt(country, indicators)

                # G20 → Gemini first; others → DeepSeek first
                if country.is_g20:
                    text = _call_gemini(prompt) or _call_deepseek(prompt)
                else:
                    text = _call_deepseek(prompt) or _call_gemini(prompt)

                if not text or len(text.split()) < MIN_SAVE:
                    log.warning("[%d/%d] %-30s — failed to get %d+ words, skipping",
                                i, len(countries), country.name, MIN_SAVE)
                    skip += 1
                    continue

                row = all_summaries.get(country.code)
                if row:
                    row.summary = text
                    row.generated_at = datetime.now(timezone.utc)
                else:
                    row = PageSummary(
                        entity_type="country",
                        entity_code=country.code,
                        summary=text,
                        generated_at=datetime.now(timezone.utc),
                    )
                    db.add(row)
                db.commit()
                words = len(text.split())
                log.info("[%d/%d] %-30s — %d words ✓", i, len(countries), country.name, words)
                ok += 1
                time.sleep(0.3)
            except Exception as exc:
                db.rollback()
                log.error("[%d/%d] %s — ERROR: %s", i, len(countries), country.name, exc)
                fail += 1

        log.info("Done — %d updated, %d skipped (AI failed), %d errors", ok, skip, fail)

if __name__ == "__main__":
    main()
