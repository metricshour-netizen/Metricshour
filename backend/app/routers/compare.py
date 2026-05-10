import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.limiter import limiter
from app.models import Country, CountryIndicator

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("/{slug}/download")
@limiter.limit("20/minute")
def download_compare_csv(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
):
    """Download side-by-side comparison of two countries' economic indicators as CSV."""
    parts = slug.lower().split('-vs-')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HTTPException(status_code=400, detail="Invalid compare slug. Expected format: {code}-vs-{code}")

    code_a, code_b = sorted([parts[0].upper(), parts[1].upper()])

    country_a = db.execute(
        select(Country).where(Country.code == code_a)
    ).scalar_one_or_none()
    country_b = db.execute(
        select(Country).where(Country.code == code_b)
    ).scalar_one_or_none()

    if not country_a or not country_b:
        raise HTTPException(status_code=404, detail="One or both countries not found")

    # Fetch latest indicator per type for each country
    def latest_indicators(country: Country) -> dict:
        rows = db.execute(
            select(CountryIndicator)
            .where(CountryIndicator.country_id == country.id, CountryIndicator.value.isnot(None))
            .order_by(CountryIndicator.indicator, CountryIndicator.period_date.desc())
        ).scalars().all()
        seen: set = set()
        result: dict = {}
        for r in rows:
            if r.indicator not in seen:
                seen.add(r.indicator)
                result[r.indicator] = {'value': r.value, 'period_date': str(r.period_date) if r.period_date else ''}
        return result

    ind_a = latest_indicators(country_a)
    ind_b = latest_indicators(country_b)

    all_indicators = sorted(set(ind_a.keys()) | set(ind_b.keys()))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Indicator',
        f'{country_a.name} ({code_a}) Value',
        f'{country_a.name} ({code_a}) Date',
        f'{country_b.name} ({code_b}) Value',
        f'{country_b.name} ({code_b}) Date',
        'Source',
    ])
    for indicator in all_indicators:
        a = ind_a.get(indicator, {})
        b = ind_b.get(indicator, {})
        writer.writerow([
            indicator,
            a.get('value', ''),
            a.get('period_date', ''),
            b.get('value', ''),
            b.get('period_date', ''),
            'MetricsHour (metricshour.com) — World Bank',
        ])

    output.seek(0)
    today = date.today().isoformat()
    filename = f"metricshour-compare-{code_a.lower()}-vs-{code_b.lower()}-{today}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )
