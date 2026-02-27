"""
On-demand OG image generation — served directly from FastAPI.

GET /og/feed/{event_id}.png   → 1200x630 PNG for a feed event
GET /og/countries/{code}.png  → 1200x630 PNG for a country page
GET /og/stocks/{symbol}.png   → 1200x630 PNG for a stock page

Social crawlers hit /s/{event_id} (share.py) which embeds these URLs as
og:image. Real browsers get redirected to the canonical feed page.

Cloudflare / nginx caches the images at the edge via Cache-Control headers.
If R2 pre-generation runs (og_images.py), event.image_url is used instead
(served from R2 CDN, faster). This endpoint acts as the fallback.
"""
import io
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.feed import FeedEvent
from app.models.country import Country, CountryIndicator
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

router = APIRouter(tags=["og"])

# ── Colours ────────────────────────────────────────────────────────────────────
BG      = (10, 14, 26)
GREEN   = (52, 211, 153)
WHITE   = (255, 255, 255)
GRAY    = (107, 114, 128)
GRAY_LT = (156, 163, 175)

W, H = 1200, 630

_ACCENTS: dict[str, tuple[int, int, int]] = {
    "price_move":        (16, 185, 129),
    "indicator_release": (59, 130, 246),
    "macro_release":     (59, 130, 246),
    "trade_update":      (245, 158, 11),
    "central_bank":      (168, 85, 247),
    "blog":              (168, 85, 247),
}
_BG_COLORS: dict[str, tuple[int, int, int]] = {
    "price_move":        (2, 16, 9),
    "indicator_release": (2, 8, 24),
    "macro_release":     (2, 8, 24),
    "trade_update":      (13, 8, 0),
    "central_bank":      (8, 2, 18),
    "blog":              (8, 2, 18),
}

# ── Font helpers ───────────────────────────────────────────────────────────────
_FONT_BASE = "/usr/share/fonts/truetype/dejavu"

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(_FONT_BASE, name), size)


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


def _fmt_large(val: float | None) -> str:
    if val is None:
        return "—"
    if val >= 1e12:
        return f"${val / 1e12:.1f}T"
    if val >= 1e9:
        return f"${val / 1e9:.0f}B"
    return f"${val / 1e6:.0f}M"


# ── Feed event renderer ────────────────────────────────────────────────────────

def _render_feed_event(
    event_type: str,
    title: str,
    event_data: dict | None,
    importance: float | None,
) -> bytes:
    data = event_data or {}
    accent = _ACCENTS.get(event_type, GREEN)
    bg_color = _BG_COLORS.get(event_type, BG)

    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Radial glow
    glow_r, glow_g, glow_b = accent
    for i in range(12, 0, -1):
        alpha = int(20 * (i / 12))
        rect_w, rect_h = W * (1 - i * 0.03), H * (1 - i * 0.05)
        x0 = (W - rect_w) / 2
        y0 = (H - rect_h) / 2 - H * 0.1
        glow_color = (
            max(0, bg_color[0] + int((glow_r - bg_color[0]) * alpha / 255)),
            max(0, bg_color[1] + int((glow_g - bg_color[1]) * alpha / 255)),
            max(0, bg_color[2] + int((glow_b - bg_color[2]) * alpha / 255)),
        )
        draw.ellipse([x0, y0, x0 + rect_w, y0 + rect_h], fill=glow_color)

    # Importance bar
    if importance:
        bar_width = int(W * min(1.0, importance / 10))
        draw.rectangle([(0, 0), (bar_width, 5)], fill=accent)

    # Brand
    draw.text((W - 32, 32), "METRICSHOUR", font=_font(20, bold=True), fill=accent, anchor="rm")

    # Event type badge
    TYPE_LABELS = {
        "price_move": "PRICE MOVE",
        "indicator_release": "MACRO DATA",
        "macro_release": "MACRO DATA",
        "trade_update": "TRADE",
        "central_bank": "CENTRAL BANK",
        "blog": "ARTICLE",
    }
    badge_text = TYPE_LABELS.get(event_type, event_type.upper().replace("_", " "))
    draw.text((60, 44), badge_text, font=_font(18, bold=True), fill=accent, anchor="lm")

    cy = H // 2 - 20

    if event_type == "price_move":
        change_pct = float(data.get("change_pct", 0) or 0)
        symbol = str(data.get("symbol", ""))
        price = data.get("price")
        sign = "+" if change_pct >= 0 else ""
        pct_color = (16, 185, 129) if change_pct >= 0 else (239, 68, 68)
        arrow = "↑" if change_pct >= 0 else "↓"

        draw.text((W // 2, cy - 20), f"{sign}{change_pct:.2f}%", font=_font(110, bold=True), fill=pct_color, anchor="mm")
        draw.text((W // 2, cy + 90), f"{arrow}  {symbol}", font=_font(48, bold=True), fill=WHITE, anchor="mm")
        if price:
            draw.text((W // 2, cy + 150), f"${float(price):,.2f}", font=_font(32), fill=GRAY_LT, anchor="mm")

    elif event_type in ("indicator_release", "macro_release"):
        country_code = str(data.get("country_code", "")).upper()
        value = data.get("value")
        indicator = str(data.get("indicator") or data.get("indicator_slug", "")).replace("_", " ").upper()

        if country_code:
            draw.text((W // 2, cy - 60), country_code, font=_font(80, bold=True), fill=accent, anchor="mm")
        if value is not None:
            n = float(value)
            if abs(n) >= 1e12:
                val_str = f"${n / 1e12:.1f}T"
            elif abs(n) >= 1e9:
                val_str = f"${n / 1e9:.1f}B"
            else:
                val_str = f"{n:.2f}" if abs(n) < 1000 else f"{n:,.0f}"
            draw.text((W // 2, cy + 30), val_str, font=_font(96, bold=True), fill=WHITE, anchor="mm")
        if indicator:
            ind_display = indicator[:50] + "…" if len(indicator) > 50 else indicator
            draw.text((W // 2, cy + 120), ind_display, font=_font(28), fill=GRAY_LT, anchor="mm")

    elif event_type == "trade_update":
        exp = str(data.get("exporter", "")).upper()
        imp = str(data.get("importer", "")).upper()
        value = data.get("value_usd")

        draw.text((200, cy), exp, font=_font(96, bold=True), fill=WHITE, anchor="mm")
        draw.text((W // 2, cy), "↔", font=_font(72, bold=True), fill=accent, anchor="mm")
        draw.text((W - 200, cy), imp, font=_font(96, bold=True), fill=WHITE, anchor="mm")
        if value:
            n = float(value)
            val_str = f"${n / 1e9:.0f}B" if n >= 1e9 else f"${n / 1e6:.0f}M"
            draw.text((W // 2, cy + 100), val_str, font=_font(48, bold=True), fill=accent, anchor="mm")

    # Title block (bottom)
    clean_title = title.encode("ascii", "ignore").decode("ascii").strip(" →↑↓·–—") or title
    words = clean_title.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= 55:
            current = (current + " " + w).strip()
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    lines = lines[:3]

    title_y = H - 120
    for i, line in enumerate(lines):
        draw.text((60, title_y + i * 44), line, font=_font(34, bold=True), fill=WHITE, anchor="lm")

    draw.rectangle([(0, H - 6), (W, H)], fill=accent)

    return _to_png_bytes(img)


# ── Country renderer ───────────────────────────────────────────────────────────

def _render_country(flag: str, name: str, gdp: float | None, growth: float | None) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Grid
    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 6), width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 6), width=1)

    draw.rectangle([(0, 0), (W, 4)], fill=GREEN)
    draw.text((W - 32, H - 40), "METRICSHOUR", font=_font(18, bold=True), fill=GREEN, anchor="rm")

    draw.text((80, H // 2 - 60), flag, font=_font(120), fill=WHITE, anchor="lm")
    draw.text((260, H // 2 - 50), name, font=_font(64, bold=True), fill=WHITE, anchor="lm")
    gdp_str = _fmt_large(gdp)
    draw.text((260, H // 2 + 30), f"GDP  {gdp_str}", font=_font(32), fill=GRAY_LT, anchor="lm")
    if growth is not None:
        color = GREEN if growth >= 0 else (248, 113, 113)
        sign = "+" if growth >= 0 else ""
        draw.text((260, H // 2 + 80), f"Growth  {sign}{growth:.1f}%", font=_font(28), fill=color, anchor="lm")

    draw.text((80, H - 40), "Economy & Macro Intelligence", font=_font(22), fill=GRAY, anchor="lm")
    return _to_png_bytes(img)


# ── Stock renderer ─────────────────────────────────────────────────────────────

def _render_stock(symbol: str, name: str, price: float | None, market_cap: float | None) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 6), width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 6), width=1)

    draw.rectangle([(0, 0), (W, 4)], fill=GREEN)
    draw.text((W - 32, H - 40), "METRICSHOUR", font=_font(18, bold=True), fill=GREEN, anchor="rm")

    draw.text((80, H // 2 - 80), symbol, font=_font(96, bold=True), fill=GREEN, anchor="lm")
    display_name = name if len(name) <= 30 else name[:28] + "…"
    draw.text((80, H // 2 + 20), display_name, font=_font(40), fill=WHITE, anchor="lm")
    if price is not None:
        draw.text((80, H // 2 + 90), f"${price:,.2f}", font=_font(32), fill=WHITE, anchor="lm")
    if market_cap is not None:
        draw.text((80, H // 2 + 140), f"Market cap  {_fmt_large(market_cap)}", font=_font(28), fill=GRAY_LT, anchor="lm")

    draw.text((80, H - 40), "Geographic Revenue & Market Intelligence", font=_font(22), fill=GRAY, anchor="lm")
    return _to_png_bytes(img)


# ── PNG response helper ────────────────────────────────────────────────────────

_PNG_HEADERS = {
    "Cache-Control": "public, max-age=86400, s-maxage=86400",
    "Content-Type": "image/png",
}


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/og/feed/{event_id}.png", include_in_schema=False)
def og_feed(event_id: int, db: Session = Depends(get_db)):
    event = db.query(FeedEvent).filter(FeedEvent.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    try:
        png = _render_feed_event(
            event.event_type,
            event.title,
            event.event_data,
            event.importance_score,
        )
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.error("OG feed render failed for event %s: %s", event_id, exc)
        raise HTTPException(status_code=500, detail="Image generation failed")


@router.get("/og/countries/{code}.png", include_in_schema=False)
def og_country(code: str, db: Session = Depends(get_db)):
    from sqlalchemy import select
    country = db.query(Country).filter(Country.code == code.upper()).first()
    if country is None:
        raise HTTPException(status_code=404, detail="Country not found")
    gdp_row = db.execute(
        select(CountryIndicator)
        .where(CountryIndicator.country_id == country.id, CountryIndicator.indicator == "gdp_usd")
        .order_by(CountryIndicator.period_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    growth_row = db.execute(
        select(CountryIndicator)
        .where(CountryIndicator.country_id == country.id, CountryIndicator.indicator == "gdp_growth_pct")
        .order_by(CountryIndicator.period_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    try:
        png = _render_country(
            country.flag_emoji or "",
            country.name,
            gdp_row.value if gdp_row else None,
            growth_row.value if growth_row else None,
        )
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.error("OG country render failed for %s: %s", code, exc)
        raise HTTPException(status_code=500, detail="Image generation failed")


@router.get("/og/stocks/{symbol}.png", include_in_schema=False)
def og_stock(symbol: str, db: Session = Depends(get_db)):
    from sqlalchemy import select
    asset = db.query(Asset).filter(
        Asset.symbol == symbol.upper(), Asset.asset_type == AssetType.stock
    ).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    price_row = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.interval == "1d")
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()
    try:
        png = _render_stock(
            asset.symbol,
            asset.name,
            price_row.close if price_row else None,
            asset.market_cap_usd,
        )
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.error("OG stock render failed for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail="Image generation failed")
