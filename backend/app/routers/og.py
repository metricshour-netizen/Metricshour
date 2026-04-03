"""
On-demand OG image generation — served directly from FastAPI.

GET /og/feed/{event_id}.png   → 1200x630 PNG for a feed event
GET /og/countries/{code}.png  → 1200x630 PNG for a country page
GET /og/stocks/{symbol}.png   → 1200x630 PNG for a stock page
GET /og/trade/{pair}.png      → 1200x630 PNG for a trade pair page (e.g. 'us-cn')
GET /og/indices/{symbol}.png  → 1200x630 PNG for an index page (e.g. 'dji')

Flow:
  1. CF Worker checks R2 for the key → serves from edge (global CDN, ~1ms) if found.
  2. On R2 miss, CF Worker forwards to this FastAPI endpoint.
  3. FastAPI generates the image, returns it, then uploads to R2 in the background.
  4. Next request is served from R2 edge — no origin hit.

R2_PUBLIC_URL must equal https://api.metricshour.com so the Cloudflare Worker
intercepts og:image URLs and routes them to R2.
"""
import io
import logging
import os
import threading

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from sqlalchemy import select, or_

from app.database import get_db
from app.models.feed import FeedEvent
from app.models.country import Country, CountryIndicator, TradePair
from app.models.asset import Asset, AssetType, Price

log = logging.getLogger(__name__)

router = APIRouter(tags=["og"])

# ── Colours ────────────────────────────────────────────────────────────────────
BG      = (10, 14, 26)
SURFACE = (17, 24, 39)
GREEN   = (52, 211, 153)
WHITE   = (255, 255, 255)
GRAY    = (107, 114, 128)
GRAY_LT = (156, 163, 175)

# ── Data source attributions (official/government sources only) ───────────────
_SOURCE_COUNTRY = "World Bank"
_SOURCE_TRADE   = "UN Comtrade"

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


def _source_line(draw: ImageDraw.ImageDraw, source: str) -> None:
    """Small source attribution bottom-left — official/government sources only."""
    if source:
        draw.text((56, H - 14), f"Source: {source}", font=_font(14), fill=GRAY, anchor="lm")


def _metric_card(
    draw: ImageDraw.ImageDraw,
    x0: int, y0: int, x1: int, y1: int,
    label: str, value: str,
    value_color: tuple = WHITE,
    accent: tuple = GREEN,
    value_size: int = 44,
) -> None:
    """Metric card with left accent bar — consistent with batch og_images layout."""
    draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=10, fill=SURFACE)
    draw.rounded_rectangle([(x0, y0), (x0 + 6, y1)], radius=3, fill=accent)
    draw.text((x0 + 24, y0 + 24), label, font=_font(20), fill=GRAY, anchor="lt")
    draw.text((x0 + 24, y0 + 72), value, font=_font(value_size, bold=True), fill=value_color, anchor="lt")


# ── Feed event renderer ────────────────────────────────────────────────────────

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, max_width: int, font, line_height: int) -> int:
    """Word-wrap text; returns the y position after the last line."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        test = f"{current} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)
    for line in lines[:3]:
        draw.text((x, y), line, font=font, fill=WHITE, anchor="lm")
        y += line_height
    return y


def _draw_glow(draw: ImageDraw.ImageDraw, accent: tuple, bg_color: tuple) -> None:
    """Radial glow centred in the upper half — bright centre, fading outward."""
    glow_r, glow_g, glow_b = accent
    # Draw large→small so smaller (brighter) ellipses paint on top
    steps = 14
    for i in range(steps, 0, -1):
        # Outermost (i=steps): faint.  Innermost (i=1): brightest.
        brightness = (steps - i + 1) / steps  # 1/14 → 14/14
        alpha = int(200 * brightness)
        rw = W * (i / steps) * 0.95
        rh = H * (i / steps) * 0.85
        x0 = (W - rw) / 2
        y0 = (H - rh) / 2 - H * 0.08
        color = (
            min(255, bg_color[0] + int((glow_r - bg_color[0]) * alpha / 255)),
            min(255, bg_color[1] + int((glow_g - bg_color[1]) * alpha / 255)),
            min(255, bg_color[2] + int((glow_b - bg_color[2]) * alpha / 255)),
        )
        draw.ellipse([x0, y0, x0 + rw, y0 + rh], fill=color)


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

    # Glow — fixed: large outer drawn first, small bright centre drawn last
    _draw_glow(draw, accent, bg_color)

    # Importance bar (top edge)
    bar_width = int(W * min(1.0, (importance or 5) / 10))
    draw.rectangle([(0, 0), (bar_width, 6)], fill=accent)

    # Brand (top-right)
    draw.text((W - 44, 44), "METRICSHOUR", font=_font(22, bold=True), fill=accent, anchor="rm")

    # Event type badge (top-left)
    TYPE_LABELS = {
        "price_move":        "PRICE MOVE",
        "indicator_release": "MACRO DATA",
        "macro_release":     "MACRO DATA",
        "trade_update":      "TRADE",
        "central_bank":      "CENTRAL BANK",
        "blog":              "ARTICLE",
        "daily_insight":     "AI INSIGHT",
        "geopolitical":      "GEOPOLITICAL",
        "commodity":         "COMMODITY",
        "commodity_move":    "COMMODITY",
    }
    badge_text = TYPE_LABELS.get(event_type, event_type.upper().replace("_", " "))
    draw.text((60, 44), badge_text, font=_font(20, bold=True), fill=accent, anchor="lm")

    # ── Hero (vertical centre, offset slightly up) ──────────────────────────────
    cy = H // 2 - 20

    if event_type == "price_move":
        change_pct = float(data.get("change_pct", 0) or 0)
        symbol     = str(data.get("symbol", ""))
        price      = data.get("price")
        sign       = "+" if change_pct >= 0 else ""
        pct_color  = (16, 185, 129) if change_pct >= 0 else (239, 68, 68)
        arrow      = "↑" if change_pct >= 0 else "↓"

        draw.text((W // 2, cy - 20), f"{sign}{change_pct:.2f}%", font=_font(120, bold=True), fill=pct_color, anchor="mm")
        draw.text((W // 2, cy + 100), f"{arrow}  {symbol}",      font=_font(52, bold=True),  fill=WHITE,     anchor="mm")
        if price:
            draw.text((W // 2, cy + 164), f"${float(price):,.2f}", font=_font(34), fill=GRAY_LT, anchor="mm")

    elif event_type in ("indicator_release", "macro_release"):
        country_code = str(data.get("country_code", "")).upper()
        value        = data.get("value")
        indicator    = str(data.get("indicator") or data.get("indicator_slug", "")).replace("_", " ").upper()

        if country_code:
            draw.text((W // 2, cy - 70), country_code, font=_font(88, bold=True), fill=accent, anchor="mm")
        if value is not None:
            n = float(value)
            if abs(n) >= 1e12:   val_str = f"${n / 1e12:.1f}T"
            elif abs(n) >= 1e9:  val_str = f"${n / 1e9:.1f}B"
            elif abs(n) >= 1e6:  val_str = f"${n / 1e6:.1f}M"
            else:                val_str = f"{n:.2f}" if abs(n) < 1000 else f"{n:,.0f}"
            draw.text((W // 2, cy + 40), val_str, font=_font(96, bold=True), fill=WHITE, anchor="mm")
        if indicator:
            ind_display = indicator[:50] + "…" if len(indicator) > 50 else indicator
            draw.text((W // 2, cy + 130), ind_display, font=_font(28), fill=GRAY_LT, anchor="mm")

    elif event_type == "trade_update":
        exp   = str(data.get("exporter", "")).upper()
        imp   = str(data.get("importer", "")).upper()
        value = data.get("value_usd")

        draw.text((180,     cy), exp,  font=_font(104, bold=True), fill=WHITE,  anchor="mm")
        draw.text((W // 2,  cy), "↔",  font=_font(72,  bold=True), fill=accent, anchor="mm")
        draw.text((W - 180, cy), imp,  font=_font(104, bold=True), fill=WHITE,  anchor="mm")
        if value:
            n = float(value)
            val_str = f"${n / 1e9:.0f}B" if n >= 1e9 else f"${n / 1e6:.0f}M"
            draw.text((W // 2, cy + 110), val_str, font=_font(52, bold=True), fill=accent, anchor="mm")

    else:
        # Generic / blog / daily_insight: show a large label
        draw.text((W // 2, cy), badge_text, font=_font(72, bold=True), fill=accent, anchor="mm")

    # ── Title block (bottom) ────────────────────────────────────────────────────
    clean_title = title.encode("ascii", "ignore").decode("ascii").strip(" →↑↓·–—") or title
    _wrap_text(draw, clean_title, 60, H - 148, W - 120, _font(34, bold=True), 46)

    # Bottom bar
    draw.rectangle([(0, H - 6), (W, H)], fill=accent)

    return _to_png_bytes(img)


# ── Country renderer ───────────────────────────────────────────────────────────

def _render_country(
    flag: str, name: str,
    gdp: float | None, growth: float | None,
    inflation: float | None = None,
    source: str = _SOURCE_COUNTRY,
    code: str = "",
) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (W, 6)], fill=GREEN)
    draw.text((W - 36, H - 14), "metricshour.com", font=_font(14), fill=GRAY, anchor="rm")
    PAD = 56

    # Header: flag + name
    if flag:
        draw.text((PAD, 24), flag, font=_font(62), fill=WHITE, anchor="lt")
        name_x = PAD + 80
    else:
        name_x = PAD
    name_disp = name if len(name) <= 20 else name[:18] + "…"
    draw.text((name_x, 22), name_disp, font=_font(54, bold=True), fill=WHITE, anchor="lt")
    draw.text((name_x, 84), "Economy Overview", font=_font(24), fill=GRAY, anchor="lt")

    # Hero card: GDP
    hero_y, hero_h = 124, 220
    draw.rounded_rectangle([(PAD, hero_y), (W - PAD, hero_y + hero_h)], radius=12, fill=SURFACE)
    draw.rounded_rectangle([(PAD, hero_y), (PAD + 8, hero_y + hero_h)], radius=4, fill=GREEN)
    draw.text((PAD + 38, hero_y + 26), "GDP", font=_font(24), fill=GRAY, anchor="lt")
    draw.text((PAD + 38, hero_y + 62), _fmt_large(gdp), font=_font(92, bold=True), fill=WHITE, anchor="lt")

    # Secondary row: Growth + Inflation
    GAP_X = 20
    sec_y = hero_y + hero_h + 16
    sec_h = H - sec_y - 32
    card_w = (W - PAD * 2 - GAP_X) // 2

    g_color = (GREEN if growth >= 0 else (248, 113, 113)) if growth is not None else GRAY_LT
    g_str = (f"+{growth:.1f}%" if growth >= 0 else f"{growth:.1f}%") if growth is not None else "—"
    _metric_card(draw, PAD, sec_y, PAD + card_w, sec_y + sec_h, "GDP Growth", g_str, value_color=g_color, value_size=54)

    if inflation is not None:
        inf_color = (248, 113, 113) if inflation > 8 else ((251, 191, 36) if inflation > 3 else GREEN)
        inf_str = f"{inflation:.1f}%"
    else:
        inf_color, inf_str = GRAY_LT, "—"
    _metric_card(draw, PAD + card_w + GAP_X, sec_y, W - PAD, sec_y + sec_h, "Inflation", inf_str, value_color=inf_color, value_size=54)

    _source_line(draw, source)
    return _to_png_bytes(img)


# ── Stock renderer ─────────────────────────────────────────────────────────────

def _render_stock(
    symbol: str, name: str,
    price: float | None, market_cap: float | None,
    change_pct: float | None = None,
) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (W, 6)], fill=GREEN)
    draw.text((W - 36, H - 14), "metricshour.com", font=_font(14), fill=GRAY, anchor="rm")
    PAD = 56

    # Header: symbol + name
    draw.text((PAD, 22), symbol, font=_font(62, bold=True), fill=GREEN, anchor="lt")
    display_name = name if len(name) <= 36 else name[:34] + "…"
    draw.text((PAD, 88), display_name, font=_font(28), fill=GRAY_LT, anchor="lt")

    # Hero card: Price
    hero_y, hero_h = 124, 220
    draw.rounded_rectangle([(PAD, hero_y), (W - PAD, hero_y + hero_h)], radius=12, fill=SURFACE)
    draw.rounded_rectangle([(PAD, hero_y), (PAD + 8, hero_y + hero_h)], radius=4, fill=GREEN)
    draw.text((PAD + 38, hero_y + 26), "Price (USD)", font=_font(24), fill=GRAY, anchor="lt")
    price_str = f"${price:,.2f}" if price is not None else "—"
    draw.text((PAD + 38, hero_y + 62), price_str, font=_font(92, bold=True), fill=WHITE, anchor="lt")

    # Secondary row: Day Change + Market Cap
    GAP_X = 20
    sec_y = hero_y + hero_h + 16
    sec_h = H - sec_y - 32
    card_w = (W - PAD * 2 - GAP_X) // 2

    ch_color = (GREEN if change_pct >= 0 else (248, 113, 113)) if change_pct is not None else GRAY_LT
    ch_str = (f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%") if change_pct is not None else "—"
    _metric_card(draw, PAD, sec_y, PAD + card_w, sec_y + sec_h, "Day Change", ch_str, value_color=ch_color, value_size=54)
    _metric_card(draw, PAD + card_w + GAP_X, sec_y, W - PAD, sec_y + sec_h, "Market Cap", _fmt_large(market_cap) if market_cap else "—", value_size=54)

    return _to_png_bytes(img)


# ── Trade renderer ─────────────────────────────────────────────────────────────

def _render_trade(
    flag_a: str, name_a: str, flag_b: str, name_b: str,
    trade_value: float | None,
    exports_usd: float | None = None,
    imports_usd: float | None = None,
    year: int | None = None,
    code_a: str = "",
    code_b: str = "",
) -> bytes:
    AMBER = (245, 158, 11)
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (W, 6)], fill=AMBER)
    draw.text((W - 36, H - 14), "metricshour.com", font=_font(14), fill=GRAY, anchor="rm")
    PAD = 56

    # Header: Country A ↔ Country B
    name_a_d = name_a if len(name_a) <= 16 else name_a[:14] + "…"
    name_b_d = name_b if len(name_b) <= 16 else name_b[:14] + "…"
    if flag_a:
        draw.text((PAD, 18), flag_a, font=_font(50), fill=WHITE, anchor="lt")
    draw.text((PAD, 72), name_a_d, font=_font(40, bold=True), fill=WHITE, anchor="lt")
    draw.text((W // 2, 50), "↔", font=_font(52, bold=True), fill=AMBER, anchor="mm")
    if flag_b:
        draw.text((W - PAD, 18), flag_b, font=_font(50), fill=WHITE, anchor="rt")
    draw.text((W - PAD, 72), name_b_d, font=_font(40, bold=True), fill=WHITE, anchor="rt")

    # Hero card: Trade volume
    vol_label = "Total Trade Volume" + (f"  ·  {year}" if year else "")
    _metric_card(draw, PAD, 120, W - PAD, 310, vol_label,
                 _fmt_large(trade_value) if trade_value else "—", accent=AMBER, value_size=72)

    # Secondary row: Exports + Imports
    GAP_X = 20
    card_w = (W - PAD * 2 - GAP_X) // 2
    y2 = 326
    card_h2 = H - y2 - 32
    lbl_a = (code_a or name_a[:3]).upper()
    lbl_b = (code_b or name_b[:3]).upper()
    _metric_card(draw, PAD, y2, PAD + card_w, y2 + card_h2,
                 f"Exports  {lbl_a} → {lbl_b}",
                 _fmt_large(exports_usd) if exports_usd else "—", accent=AMBER, value_size=52)
    _metric_card(draw, PAD + card_w + GAP_X, y2, W - PAD, y2 + card_h2,
                 f"Exports  {lbl_b} → {lbl_a}",
                 _fmt_large(imports_usd) if imports_usd else "—", accent=AMBER, value_size=52)

    _source_line(draw, _SOURCE_TRADE)
    return _to_png_bytes(img)


# ── R2 upload helper (runs in background thread — never blocks the response) ───

def _upload_to_r2_bg(key: str, data: bytes) -> None:
    """Upload PNG to R2 so the CF Worker can serve it from the edge on next request."""
    endpoint = os.environ.get("R2_ENDPOINT", "")
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    bucket = os.environ.get("R2_BUCKET_NAME", "metricshour-assets")
    if not (endpoint and access_key and secret_key):
        return
    try:
        import boto3
        from botocore.config import Config as BotoConfig
        r2 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="auto",
        )
        r2.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType="image/png",
            CacheControl="public, max-age=86400, s-maxage=86400, stale-while-revalidate=3600",
        )
    except Exception as exc:
        log.warning("R2 background upload failed for %s: %s", key, exc)


def _fire_r2_upload(key: str, data: bytes) -> None:
    """Spawn a daemon thread so R2 upload never adds latency to the HTTP response."""
    t = threading.Thread(target=_upload_to_r2_bg, args=(key, data), daemon=True)
    t.start()


# ── PNG response helper ────────────────────────────────────────────────────────

_PNG_HEADERS = {
    "Cache-Control": "public, max-age=86400, s-maxage=86400, stale-while-revalidate=3600",
    "Content-Type": "image/png",
}


# ── Section / generic image renderer ──────────────────────────────────────────

_SECTION_CONFIG: dict[str, dict] = {
    "home": {
        "label": "GLOBAL FINANCIAL INTELLIGENCE",
        "tagline": "Stocks · Macro · Trade · Commodities · FX · Crypto",
        "accent": GREEN,
    },
    "stocks": {
        "label": "STOCKS",
        "tagline": "Geographic revenue exposure · SEC EDGAR · 130+ assets",
        "accent": GREEN,
    },
    "countries": {
        "label": "COUNTRIES",
        "tagline": "196 countries · 80+ macro indicators · G7 G20 EU NATO BRICS",
        "accent": (59, 130, 246),  # blue-500
    },
    "trade": {
        "label": "BILATERAL TRADE",
        "tagline": "380 country pairs · Exports · Imports · GDP dependency",
        "accent": (245, 158, 11),  # amber-500
    },
    "commodities": {
        "label": "COMMODITIES",
        "tagline": "Energy · Metals · Agriculture · 20+ instruments tracked",
        "accent": (245, 158, 11),
    },
    "markets": {
        "label": "MARKETS",
        "tagline": "Crypto · Stocks · Indices · FX · Bonds · Real-time prices",
        "accent": (168, 85, 247),  # purple-500
    },
    "feed": {
        "label": "INTELLIGENCE FEED",
        "tagline": "Price moves · Macro releases · Trade updates · Personalised",
        "accent": GREEN,
    },
    "pricing": {
        "label": "PRICING",
        "tagline": "Free tier forever · Pro from $9.99/mo · No Bloomberg bill",
        "accent": GREEN,
    },
    "china": {
        "label": "CHINA A-SHARES",
        "tagline": "Shanghai & Shenzhen · 300+ stocks · Priced in CNY · Daily prices via Tiingo",
        "accent": (220, 38, 38),  # red-600
    },
}


def _render_section(section: str) -> bytes:
    cfg = _SECTION_CONFIG.get(section, _SECTION_CONFIG["home"])
    accent = cfg["accent"]

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle grid lines
    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 5), width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 5), width=1)

    # Diagonal accent stripe (visual texture)
    ar, ag, ab = accent
    for offset in range(0, W + H, 60):
        x1, y1 = offset, 0
        x2, y2 = 0, offset
        draw.line([(x1, y1), (x2, y2)], fill=(ar, ag, ab, 12), width=1)

    # Top bar
    draw.rectangle([(0, 0), (W, 6)], fill=accent)

    # MetricsHour logotype — large, centred, vertical-centre offset upward
    draw.text((W // 2, H // 2 - 90), "METRICSHOUR", font=_font(72, bold=True), fill=WHITE, anchor="mm")

    # Section label
    draw.text((W // 2, H // 2 - 10), cfg["label"], font=_font(28, bold=True), fill=accent, anchor="mm")

    # Tagline
    draw.text((W // 2, H // 2 + 50), cfg["tagline"], font=_font(22), fill=GRAY_LT, anchor="mm")

    # Bottom domain
    draw.text((W // 2, H - 44), "metricshour.com", font=_font(20, bold=True), fill=GRAY, anchor="mm")

    # Bottom bar
    draw.rectangle([(0, H - 6), (W, H)], fill=accent)

    return _to_png_bytes(img)


def _fallback_png(label: str = "MetricsHour") -> bytes:
    """Return a minimal 1200x630 branded fallback PNG. Uses default font if DejaVu unavailable."""
    try:
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (W, 5)], fill=GREEN)
        draw.text((W // 2, H // 2 - 20), "METRICSHOUR", font=_font(72, bold=True), fill=WHITE, anchor="mm")
        draw.text((W // 2, H // 2 + 50), label, font=_font(28), fill=GRAY_LT, anchor="mm")
        draw.rectangle([(0, H - 5), (W, H)], fill=GREEN)
        return _to_png_bytes(img)
    except Exception:
        # Last-resort: plain colored PNG with no text (never a 500)
        img = Image.new("RGB", (W, H), BG)
        return _to_png_bytes(img)


@router.get("/og/section/{section}.png", include_in_schema=False)
def og_section(section: str):
    """Branded 1200x630 OG image for static/listing pages."""
    try:
        png = _render_section(section)
        _fire_r2_upload(f"og/section/{section}.png", png)
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.warning("OG section render failed for %s: %s", section, exc)
        return Response(content=_fallback_png(section.upper()), media_type="image/png", headers=_PNG_HEADERS)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/og/feed/{event_id}.png", include_in_schema=False)
def og_feed(event_id: int, db: Session = Depends(get_db)):
    event = db.execute(select(FeedEvent).where(FeedEvent.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    try:
        png = _render_feed_event(
            event.event_type,
            event.title,
            event.event_data,
            event.importance_score,
        )
        # Upload to R2 in background — next request served from CF edge
        _fire_r2_upload(f"og/feed/{event_id}.png", png)
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.warning("OG image generation failed for feed/%s: %s", event_id, exc)
        return Response(content=_fallback_png("Feed Event"), media_type="image/png", headers=_PNG_HEADERS)


@router.get("/og/countries/{code}.png", include_in_schema=False)
def og_country(code: str, db: Session = Depends(get_db)):
    country = db.execute(select(Country).where(Country.code == code.upper())).scalar_one_or_none()
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
    inflation_row = db.execute(
        select(CountryIndicator)
        .where(CountryIndicator.country_id == country.id, CountryIndicator.indicator == "inflation_pct")
        .order_by(CountryIndicator.period_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    try:
        png = _render_country(
            country.flag_emoji or "",
            country.name,
            gdp_row.value if gdp_row else None,
            growth_row.value if growth_row else None,
            inflation=inflation_row.value if inflation_row else None,
            code=country.code,
        )
        _fire_r2_upload(f"og/countries/{code.lower()}.png", png)
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.warning("OG image generation failed for countries/%s: %s", code, exc)
        return Response(content=_fallback_png(code.upper()), media_type="image/png", headers=_PNG_HEADERS)


@router.get("/og/trade/{pair}.png", include_in_schema=False)
def og_trade(pair: str, db: Session = Depends(get_db)):
    """On-demand OG image for /trade/{pair} pages (e.g. 'us-cn')."""
    # pair = "us-cn" — split on first hyphen; country codes have no hyphens
    parts = pair.lower().split("-", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid pair format")
    exp_code, imp_code = parts[0].upper(), parts[1].upper()

    exp = db.execute(select(Country).where(Country.code == exp_code)).scalar_one_or_none()
    imp = db.execute(select(Country).where(Country.code == imp_code)).scalar_one_or_none()
    if not exp or not imp:
        raise HTTPException(status_code=404, detail="Country not found")

    # Grab trade value from either direction
    trade_row = db.execute(
        select(TradePair)
        .where(
            or_(
                (TradePair.exporter_id == exp.id) & (TradePair.importer_id == imp.id),
                (TradePair.exporter_id == imp.id) & (TradePair.importer_id == exp.id),
            )
        )
        .order_by(TradePair.year.desc())
        .limit(1)
    ).scalar_one_or_none()

    try:
        png = _render_trade(
            exp.flag_emoji or "",
            exp.name,
            imp.flag_emoji or "",
            imp.name,
            trade_row.trade_value_usd if trade_row else None,
            exports_usd=trade_row.exports_usd if trade_row else None,
            imports_usd=trade_row.imports_usd if trade_row else None,
            year=trade_row.year if trade_row else None,
            code_a=exp.code,
            code_b=imp.code,
        )
        _fire_r2_upload(f"og/trade/{pair.lower()}.png", png)
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.warning("OG image generation failed for trade/%s: %s", pair, exc)
        return Response(content=_fallback_png(pair.upper()), media_type="image/png", headers=_PNG_HEADERS)


@router.get("/og/indices/{symbol}.png", include_in_schema=False)
def og_index(symbol: str):
    """On-demand OG image for /indices/{symbol} pages — rendered as a section image."""
    # Indices don't have their own rich data model yet; render as a branded section image.
    cfg = {
        "label": symbol.upper(),
        "tagline": "Real-time index price · Markets · MetricsHour",
        "accent": (52, 211, 153),  # emerald-400
    }
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 5), width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 5), width=1)
    accent = cfg["accent"]
    draw.rectangle([(0, 0), (W, 6)], fill=accent)
    draw.text((W // 2, H // 2 - 90), "METRICSHOUR", font=_font(72, bold=True), fill=WHITE, anchor="mm")
    draw.text((W // 2, H // 2 - 10), cfg["label"], font=_font(40, bold=True), fill=accent, anchor="mm")
    draw.text((W // 2, H // 2 + 50), cfg["tagline"], font=_font(22), fill=GRAY_LT, anchor="mm")
    draw.text((W // 2, H - 44), "metricshour.com", font=_font(20, bold=True), fill=GRAY, anchor="mm")
    draw.rectangle([(0, H - 6), (W, H)], fill=accent)
    try:
        png = _to_png_bytes(img)
        _fire_r2_upload(f"og/indices/{symbol.lower()}.png", png)
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.warning("OG image generation failed for indices/%s: %s", symbol, exc)
        return Response(content=_fallback_png(symbol.upper()), media_type="image/png", headers=_PNG_HEADERS)


@router.get("/og/stocks/{symbol}.png", include_in_schema=False)
def og_stock(symbol: str, db: Session = Depends(get_db)):
    asset = db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.asset_type == AssetType.stock)
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    price_row = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.interval == "1d")
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()
    change_pct = None
    if price_row and price_row.open and price_row.close and price_row.open > 0:
        change_pct = (price_row.close - price_row.open) / price_row.open * 100
    try:
        png = _render_stock(
            asset.symbol,
            asset.name,
            price_row.close if price_row else None,
            asset.market_cap_usd,
            change_pct=change_pct,
        )
        _fire_r2_upload(f"og/stocks/{symbol.lower()}.png", png)
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.warning("OG image generation failed for stocks/%s: %s", symbol, exc)
        return Response(content=_fallback_png(symbol.upper()), media_type="image/png", headers=_PNG_HEADERS)


@router.get("/og/china/{symbol}.png", include_in_schema=False)
def og_china(symbol: str, db: Session = Depends(get_db)):
    asset = db.execute(
        select(Asset).where(
            Asset.symbol == symbol.upper(),
            Asset.exchange.in_(["SHG", "SHE"]),
            Asset.is_active == True,
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="China stock not found")
    price_row = db.execute(
        select(Price)
        .where(Price.asset_id == asset.id, Price.interval == "1d")
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()
    change_pct = None
    if price_row and price_row.open and price_row.close and price_row.open > 0:
        change_pct = (price_row.close - price_row.open) / price_row.open * 100
    try:
        png = _render_stock(
            asset.symbol,
            asset.name,
            price_row.close if price_row else None,
            asset.market_cap_usd,
            change_pct=change_pct,
        )
        _fire_r2_upload(f"og/china/{symbol.lower()}.png", png)
        return Response(content=png, media_type="image/png", headers=_PNG_HEADERS)
    except Exception as exc:
        log.warning("OG image generation failed for china/%s: %s", symbol, exc)
        return Response(content=_fallback_png(symbol.upper()), media_type="image/png", headers=_PNG_HEADERS)
