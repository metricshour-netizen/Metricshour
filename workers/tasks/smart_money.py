"""
Smart Money Tracker — SEC EDGAR 13F-HR filing parser.

Fetches quarterly 13F filings for tracked institutional investors.
Runs after each quarterly deadline (mid-Feb, mid-May, mid-Aug, mid-Nov).
"""
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models.smart_money import SmartMoneyInvestor, SmartMoneyFiling, SmartMoneyHolding

log = logging.getLogger(__name__)

EDGAR_BASE = "https://data.sec.gov"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
# SEC requires a User-Agent header with contact info
HEADERS = {
    "User-Agent": "MetricsHour contact@metricshour.com",
    "Accept": "application/json",
}

# Tier 1 — featured individuals
# Tier 2 — featured funds
INVESTOR_SEED = [
    # slug, name, fund_name, cik, tier, description
    ("warren-buffett",        "Warren Buffett",        "Berkshire Hathaway",      "0001067983", 1, "Chairman & CEO of Berkshire Hathaway, legendary value investor"),
    ("bill-ackman",           "Bill Ackman",           "Pershing Square Capital", "0001336528", 1, "Activist investor, founder of Pershing Square"),
    ("michael-burry",         "Michael Burry",         "Scion Asset Management",  "0001649339", 1, "Famous for shorting the housing market in 2008"),
    ("ray-dalio",             "Ray Dalio",             "Bridgewater Associates",  "0001350694", 1, "Founder of Bridgewater, creator of All Weather portfolio"),
    ("stanley-druckenmiller", "Stanley Druckenmiller", "Duquesne Family Office",  "0001536411", 1, "Former Soros CIO, legendary macro trader"),
    ("george-soros",          "George Soros",          "Soros Fund Management",   "0001029159", 1, "Pioneer of macro investing, broke the Bank of England"),
    ("david-tepper",          "David Tepper",          "Appaloosa Management",    "0001279910", 1, "Distressed debt specialist turned broad equity investor"),
    ("carl-icahn",            "Carl Icahn",            "Icahn Capital",           "0000813672", 1, "Prominent activist investor"),
    ("dan-loeb",              "Dan Loeb",              "Third Point LLC",         "0001040273", 1, "Activist investor and hedge fund manager"),
    ("david-einhorn",         "David Einhorn",         "Greenlight Capital",      "0001079114", 1, "Value investor known for shorting Lehman Brothers"),
    ("cathie-wood",           "Cathie Wood",           "ARK Investment Management","0001697248", 2, "Disruptive innovation fund manager"),
    ("tiger-global",          "Tiger Global",          "Tiger Global Management", "0001167483", 2, "Growth equity and hedge fund manager"),
    ("coatue-management",     "Coatue Management",     "Coatue Management",       "0001336766", 2, "Long/short technology-focused hedge fund"),
    ("point72",               "Steve Cohen",           "Point72 Asset Management","0001603466", 2, "Multi-strategy hedge fund manager"),
    ("de-shaw",               "DE Shaw",               "DE Shaw & Co",            "0001009362", 2, "Quantitative and systematic investment firm"),
]


def _quarter_label(d: date) -> str:
    """Return 'Q1 2026' style label for a date."""
    q = (d.month - 1) // 3 + 1
    return f"Q{q} {d.year}"


def _period_end_for_quarter(year: int, quarter: int) -> date:
    """Return the last day of a quarter."""
    ends = {1: date(year, 3, 31), 2: date(year, 6, 30), 3: date(year, 9, 30), 4: date(year, 12, 31)}
    return ends[quarter]


def _fetch_13f_filings(cik: str) -> list[dict]:
    """Fetch list of 13F-HR filings for a CIK from SEC EDGAR."""
    padded_cik = cik.lstrip("0").zfill(10)
    url = f"{EDGAR_BASE}/cgi-bin/browse-edgar?action=getcompany&CIK={padded_cik}&type=13F-HR&dateb=&owner=include&count=8&search_text="
    try:
        # Use the submissions API for structured data
        sub_url = f"{EDGAR_BASE}/submissions/CIK{padded_cik}.json"
        r = requests.get(sub_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        filings_data = data.get("filings", {}).get("recent", {})
        forms = filings_data.get("form", [])
        dates = filings_data.get("filingDate", [])
        accessions = filings_data.get("accessionNumber", [])
        periods = filings_data.get("reportDate", [])

        results = []
        for i, form in enumerate(forms):
            if form == "13F-HR":
                filed = dates[i] if i < len(dates) else None
                acc = accessions[i] if i < len(accessions) else None
                period = periods[i] if i < len(periods) else None
                if filed and acc:
                    results.append({
                        "filed_date": filed,
                        "accession_number": acc.replace("-", ""),
                        "period_of_report": period or filed,
                    })
        return results[:8]   # most recent 8 quarters
    except Exception as e:
        log.warning("EDGAR submissions fetch failed for CIK %s: %s", cik, e)
        return []


def _fetch_holdings(cik: str, accession_raw: str) -> list[dict]:
    """Parse holdings from a 13F-HR XML filing."""
    cik_int = int(cik.lstrip("0") or "0")
    accession = accession_raw.replace("-", "")
    acc_fmt = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
    dir_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/"

    primary_xml = None
    try:
        time.sleep(0.2)
        r = requests.get(dir_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        # Find XML files in the directory listing; skip primary_doc.xml and index files
        xml_files = re.findall(r'href="([^"]+\.xml)"', r.text, re.IGNORECASE)
        for fname in xml_files:
            basename = fname.split("/")[-1].lower()
            if "primary_doc" in basename or "index" in basename or "summary" in basename:
                continue
            primary_xml = fname.split("/")[-1]
            break
        # If nothing found, try grepping specifically for infotable reference
        if not primary_xml:
            match = re.search(r'href="[^"]*?/([^"/]+\.xml)"', r.text, re.IGNORECASE)
            if match:
                candidate = match.group(1).lower()
                if "primary_doc" not in candidate:
                    primary_xml = match.group(1).split("/")[-1]
    except Exception as e:
        log.debug("Filing directory fetch failed %s/%s: %s", cik, accession, e)
        return []

    if not primary_xml:
        log.debug("No XML found in filing directory for %s/%s", cik, accession)
        return []

    xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{primary_xml}"
    try:
        time.sleep(0.2)
        r = requests.get(xml_url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return []
        return _parse_13f_xml(r.text)
    except Exception as e:
        log.debug("Holdings XML fetch failed %s: %s", xml_url, e)
        return []


def _parse_13f_xml(xml_text: str) -> list[dict]:
    """Parse 13F-HR XML infoTable into list of holdings.
    Aggregates duplicate CUSIP entries (multiple subsidiary accounts for same stock).
    """
    raw: dict[str, dict] = {}   # keyed by cusip (or company name if no cusip)
    try:
        xml_clean = re.sub(r' xmlns[^"]*"[^"]*"', '', xml_text)
        root = ET.fromstring(xml_clean)

        for info in root.iter("infoTable"):
            name_el = info.find("nameOfIssuer")
            cusip_el = info.find("cusip")
            value_el = info.find("value")
            shares_el = info.find(".//sshPrnamt")
            if value_el is None:
                continue
            company_name = (name_el.text or "").strip() if name_el is not None else ""
            cusip = (cusip_el.text or "").strip() if cusip_el is not None else ""
            try:
                value_usd = float(value_el.text or 0)
            except (ValueError, TypeError):
                continue
            shares = None
            if shares_el is not None:
                try:
                    shares = int(shares_el.text or 0)
                except (ValueError, TypeError):
                    pass

            key = cusip if cusip else company_name
            if key in raw:
                raw[key]["value_usd"] += value_usd
                if shares:
                    raw[key]["shares"] = (raw[key]["shares"] or 0) + shares
            else:
                raw[key] = {"company_name": company_name, "cusip": cusip, "value_usd": value_usd, "shares": shares}
    except ET.ParseError as e:
        log.debug("XML parse error: %s", e)
    return list(raw.values())


def _resolve_symbol(company_name: str, cusip: str) -> Optional[str]:
    """Best-effort: look up ticker symbol from company name in our assets table."""
    if not company_name:
        return None
    db = SessionLocal()
    try:
        from app.models.asset import Asset, AssetType
        from sqlalchemy import func as sqlfunc
        row = db.execute(
            select(Asset.symbol)
            .where(Asset.asset_type == AssetType.stock)
            .where(Asset.is_active == True)
            .where(sqlfunc.lower(Asset.name).contains(company_name[:20].lower()))
            .limit(1)
        ).scalar_one_or_none()
        return row
    except Exception:
        return None
    finally:
        db.close()


def seed_investors():
    """Insert/update the tracked investor universe."""
    db = SessionLocal()
    try:
        for slug, name, fund_name, cik, tier, desc in INVESTOR_SEED:
            existing = db.execute(
                select(SmartMoneyInvestor).where(SmartMoneyInvestor.cik == cik)
            ).scalar_one_or_none()
            if not existing:
                db.add(SmartMoneyInvestor(
                    slug=slug, name=name, fund_name=fund_name,
                    cik=cik, tier=tier, description=desc, active=True,
                ))
        db.commit()
        log.info("Smart Money investor seed complete (%d investors)", len(INVESTOR_SEED))
    finally:
        db.close()


@shared_task(name="smart_money.fetch_13f_filings", bind=True, max_retries=2)
def fetch_13f_filings(self, cik: str = None):
    """Fetch and parse 13F filings. Pass cik to process one investor; omit for all."""
    seed_investors()
    db = SessionLocal()
    try:
        query = select(SmartMoneyInvestor).where(SmartMoneyInvestor.active == True)
        if cik:
            query = query.where(SmartMoneyInvestor.cik == cik)
        investors = db.execute(query).scalars().all()

        for investor in investors:
            log.info("Fetching 13F filings for %s (CIK %s)", investor.name, investor.cik)
            filings = _fetch_13f_filings(investor.cik)
            time.sleep(0.5)

            for f in filings:
                try:
                    filed_date = date.fromisoformat(f["filed_date"])
                    period_date = date.fromisoformat(f["period_of_report"])
                except (ValueError, KeyError):
                    continue

                quarter_label = _quarter_label(period_date)

                # Upsert filing record
                stmt = pg_insert(SmartMoneyFiling).values(
                    investor_id=investor.id,
                    cik=investor.cik,
                    accession_number=f["accession_number"],
                    filed_date=filed_date,
                    period_of_report=period_date,
                    quarter_label=quarter_label,
                    parsed=False,
                ).on_conflict_do_update(
                    constraint="uq_sm_filing_cik_period",
                    set_={"accession_number": f["accession_number"], "filed_date": filed_date},
                )
                db.execute(stmt)
            db.commit()

            # Update investor last_filing_date + count
            from sqlalchemy import func as sqlfunc
            latest = db.execute(
                select(sqlfunc.max(SmartMoneyFiling.filed_date))
                .where(SmartMoneyFiling.investor_id == investor.id)
            ).scalar_one_or_none()
            count = db.execute(
                select(sqlfunc.count(SmartMoneyFiling.id))
                .where(SmartMoneyFiling.investor_id == investor.id)
            ).scalar_one_or_none()
            investor.last_filing_date = latest
            investor.filing_count = count or 0
            db.commit()

        return {"investors_processed": len(investors)}
    except Exception as exc:
        db.rollback()
        log.error("13F filing fetch error: %s", exc)
        raise self.retry(exc=exc, countdown=600)
    finally:
        db.close()


@shared_task(name="smart_money.parse_holdings", bind=True, max_retries=2)
def parse_holdings(self, filing_id: int = None):
    """Parse holdings from 13F XML for unparsed filings."""
    db = SessionLocal()
    try:
        query = select(SmartMoneyFiling, SmartMoneyInvestor)\
            .join(SmartMoneyInvestor, SmartMoneyFiling.investor_id == SmartMoneyInvestor.id)\
            .where(SmartMoneyFiling.parsed == False)
        if filing_id:
            query = query.where(SmartMoneyFiling.id == filing_id)
        else:
            # Process most recent filing per investor first
            query = query.order_by(SmartMoneyFiling.period_of_report.desc()).limit(30)

        rows = db.execute(query).all()
        parsed_count = 0

        for filing, investor in rows:
            if not filing.accession_number:
                continue
            log.info("Parsing holdings for %s %s", investor.name, filing.quarter_label)
            raw_holdings = _fetch_holdings(investor.cik, filing.accession_number)
            time.sleep(0.3)

            if not raw_holdings:
                filing.parsed = True
                db.commit()
                continue

            # Calculate total portfolio value
            total_value = sum(h["value_usd"] for h in raw_holdings if h["value_usd"])
            filing.total_value_usd = total_value
            filing.holding_count = len(raw_holdings)

            # Fetch previous quarter's holdings for change calculation
            prev_filing = db.execute(
                select(SmartMoneyFiling)
                .where(SmartMoneyFiling.investor_id == investor.id)
                .where(SmartMoneyFiling.period_of_report < filing.period_of_report)
                .where(SmartMoneyFiling.parsed == True)
                .order_by(SmartMoneyFiling.period_of_report.desc())
                .limit(1)
            ).scalar_one_or_none()

            prev_holdings: dict[str, SmartMoneyHolding] = {}
            if prev_filing:
                prev_rows = db.execute(
                    select(SmartMoneyHolding)
                    .where(SmartMoneyHolding.filing_id == prev_filing.id)
                ).scalars().all()
                prev_holdings = {h.symbol: h for h in prev_rows if h.symbol}

            # Delete existing holdings for this filing before re-insert
            from sqlalchemy import delete
            db.execute(delete(SmartMoneyHolding).where(SmartMoneyHolding.filing_id == filing.id))

            holding_rows = []
            for h in raw_holdings:
                symbol = _resolve_symbol(h["company_name"], h["cusip"])
                pct = (h["value_usd"] / total_value * 100) if total_value else None

                change_type = "new"
                shares_change = h.get("shares")
                value_change = h["value_usd"]
                if symbol and symbol in prev_holdings:
                    prev = prev_holdings[symbol]
                    shares_change = (h.get("shares") or 0) - (prev.shares or 0)
                    value_change = h["value_usd"] - (prev.value_usd or 0)
                    if abs(shares_change) < 1:
                        change_type = "unchanged"
                    elif shares_change > 0:
                        change_type = "increased"
                    else:
                        change_type = "decreased"
                elif symbol and symbol not in prev_holdings and prev_filing:
                    change_type = "new"

                holding_rows.append({
                    "filing_id": filing.id,
                    "investor_id": investor.id,
                    "symbol": symbol or "",
                    "company_name": h["company_name"],
                    "cusip": h["cusip"],
                    "shares": h.get("shares"),
                    "value_usd": h["value_usd"],
                    "portfolio_pct": pct,
                    "change_type": change_type,
                    "shares_change": shares_change,
                    "value_change_usd": value_change,
                    "quarter_label": filing.quarter_label,
                })

            if holding_rows:
                db.execute(pg_insert(SmartMoneyHolding).values(holding_rows).on_conflict_do_nothing())

            filing.parsed = True
            db.commit()
            parsed_count += 1

        return {"parsed": parsed_count}
    except Exception as exc:
        db.rollback()
        log.error("Holdings parse error: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
