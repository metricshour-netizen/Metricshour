"""
Generate 1200x630 OG images for every country, stock, and trade pair page.
Upload to R2 under /og/{type}/{code}.png.
Schedule: daily at 3:30 AM UTC (after summaries at 2 AM, backup at 3 AM).
"""
import io
import logging
import os

from celery import shared_task
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# ── Colours — Bloomberg Terminal dark theme ────────────────────────────────────
BG       = (10, 14, 26)       # #0a0e1a
SURFACE  = (17, 24, 39)       # #111827
BORDER   = (31, 41, 55)       # #1f2937
GREEN    = (52, 211, 153)     # emerald-400
WHITE    = (255, 255, 255)
GRAY     = (107, 114, 128)    # gray-500
GRAY_LT  = (156, 163, 175)   # gray-400

W, H = 1200, 630

# ── Fonts (DejaVu — guaranteed on Ubuntu) ────────────────────────────────────
_FONT_BASE = "/usr/share/fonts/truetype/dejavu"

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(_FONT_BASE, name), size)


# ── Template loader ───────────────────────────────────────────────────────────
# 14 pre-built background templates in workers/templates/{name}.png
# Moltis overlays data text on top of these bases.

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

# Map content type → template filename (without .png)
TEMPLATE_MAP = {
    # "Did you know?" portrait cards
    "country_economy":    "did_you_know_country_economy",
    "country_trade":      "did_you_know_country_trade",
    "country_inflation":  "did_you_know_country_inflation",
    "country_growth":     "did_you_know_country_growth",
    "stock_price":        "did_you_know_stock_price",
    "stock_revenue":      "did_you_know_stock_revenue",
    "trade_pair":         "did_you_know_trade_pair",
    # Feed event cards
    "price_move_up":      "breaking_price_up",
    "price_move_down":    "breaking_price_down",
    "central_bank":       "central_bank_decision",
    "macro_gdp":          "macro_gdp",
    "macro_inflation":    "macro_inflation",
    "macro_employment":   "macro_employment",
    "market_intel":       "market_intelligence",
}

def _load_template(template_key: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Load a pre-built template PNG as the base canvas."""
    name = TEMPLATE_MAP.get(template_key, "did_you_know_country_economy")
    path = os.path.join(TEMPLATE_DIR, f"{name}.png")
    if os.path.exists(path):
        img = Image.open(path).convert("RGB")
    else:
        # Fallback: plain dark canvas if template file missing
        img = Image.new("RGB", (720, 1280), BG)
    return img, ImageDraw.ImageDraw(img)


# ── Canvas helpers ─────────────────────────────────────────────────────────────

def _metric_card(
    draw: ImageDraw.ImageDraw,
    x0: int, y0: int, x1: int, y1: int,
    label: str, value: str,
    value_color: tuple = WHITE,
    accent: tuple = GREEN,
    value_size: int = 44,
) -> None:
    """Draw a single metric card with a coloured left accent bar."""
    draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=10, fill=SURFACE)
    draw.rounded_rectangle([(x0, y0), (x0 + 6, y1)], radius=3, fill=accent)
    draw.text((x0 + 24, y0 + 22), label, font=_font(18), fill=GRAY, anchor="lt")
    draw.text((x0 + 24, y0 + 76), value, font=_font(value_size, bold=True), fill=value_color, anchor="lt")


def _base_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Thin top accent bar only — branding stays out of the data area
    draw.rectangle([(0, 0), (W, 4)], fill=GREEN)

    # Minimal watermark: small gray URL bottom-right, does not obstruct data
    draw.text((W - 36, H - 14), "metricshour.com", font=_font(13), fill=GRAY, anchor="rm")

    return img, draw


def _fmt_large(val) -> str:
    if val is None:
        return "—"
    if val >= 1e12:
        return f"${val / 1e12:.1f}T"
    if val >= 1e9:
        return f"${val / 1e9:.0f}B"
    return f"${val / 1e6:.0f}M"


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=7)
    buf.seek(0)
    return buf.read()


# ── Generators ────────────────────────────────────────────────────────────────

def _country_image(
    flag: str, name: str,
    gdp: float | None, growth: float | None,
    inflation: float | None = None, interest_rate: float | None = None,
) -> bytes:
    img, draw = _base_canvas()
    PAD = 56

    # ── Header: flag + name ────────────────────────────────────────────────
    flag_x = PAD
    if flag:
        draw.text((flag_x, 30), flag, font=_font(56), fill=WHITE, anchor="lt")
        name_x = flag_x + 70
    else:
        name_x = flag_x

    name_disp = name if len(name) <= 24 else name[:22] + "…"
    draw.text((name_x, 30), name_disp, font=_font(48, bold=True), fill=WHITE, anchor="lt")
    draw.text((name_x, 88), "Economy Overview", font=_font(20), fill=GRAY, anchor="lt")

    # ── 2 × 2 metric grid ─────────────────────────────────────────────────
    GAP_X, GAP_Y = 20, 14
    card_w = (W - PAD * 2 - GAP_X) // 2   # ≈ 534 px
    card_h = (600 - 120 - GAP_Y) // 2      # ≈ 233 px — taller now brand bar gone

    y_row1 = 120
    y_row2 = y_row1 + card_h + GAP_Y
    x_col1 = PAD
    x_col2 = PAD + card_w + GAP_X

    # GDP
    _metric_card(draw, x_col1, y_row1, x_col1 + card_w, y_row1 + card_h,
                 "GDP", _fmt_large(gdp) if gdp else "—")

    # GDP Growth
    if growth is not None:
        g_color = GREEN if growth >= 0 else (248, 113, 113)
        sign = "+" if growth >= 0 else ""
        g_str = f"{sign}{growth:.1f}%"
    else:
        g_color, g_str = GRAY_LT, "—"
    _metric_card(draw, x_col2, y_row1, x_col2 + card_w, y_row1 + card_h,
                 "GDP Growth", g_str, value_color=g_color)

    # Inflation
    if inflation is not None:
        if inflation > 8:
            inf_color = (248, 113, 113)
        elif inflation > 3:
            inf_color = (251, 191, 36)
        else:
            inf_color = GREEN
        inf_str = f"{inflation:.1f}%"
    else:
        inf_color, inf_str = GRAY_LT, "—"
    _metric_card(draw, x_col1, y_row2, x_col1 + card_w, y_row2 + card_h,
                 "Inflation", inf_str, value_color=inf_color)

    # Interest Rate
    ir_str = f"{interest_rate:.2f}%" if interest_rate is not None else "—"
    _metric_card(draw, x_col2, y_row2, x_col2 + card_w, y_row2 + card_h,
                 "Interest Rate", ir_str, value_color=GRAY_LT)

    return _to_png_bytes(img)


def _stock_image(
    symbol: str, name: str,
    price: float | None, market_cap: float | None,
    change_pct: float | None = None, sector: str | None = None,
) -> bytes:
    img, draw = _base_canvas()
    PAD = 56

    # ── Header: ticker + company name ─────────────────────────────────────
    draw.text((PAD, 28), symbol, font=_font(56, bold=True), fill=GREEN, anchor="lt")
    display_name = name if len(name) <= 36 else name[:34] + "…"
    draw.text((PAD, 88), display_name, font=_font(26), fill=GRAY_LT, anchor="lt")

    # ── 2 × 2 metric grid ─────────────────────────────────────────────────
    GAP_X, GAP_Y = 20, 14
    card_w = (W - PAD * 2 - GAP_X) // 2
    card_h = (600 - 120 - GAP_Y) // 2      # taller now brand bar gone

    y_row1 = 120
    y_row2 = y_row1 + card_h + GAP_Y
    x_col1 = PAD
    x_col2 = PAD + card_w + GAP_X

    # Price
    price_str = f"${price:,.2f}" if price is not None else "—"
    _metric_card(draw, x_col1, y_row1, x_col1 + card_w, y_row1 + card_h,
                 "Price (USD)", price_str)

    # Day Change %
    if change_pct is not None:
        ch_color = GREEN if change_pct >= 0 else (248, 113, 113)
        sign = "+" if change_pct >= 0 else ""
        ch_str = f"{sign}{change_pct:.2f}%"
    else:
        ch_color, ch_str = GRAY_LT, "—"
    _metric_card(draw, x_col2, y_row1, x_col2 + card_w, y_row1 + card_h,
                 "Day Change", ch_str, value_color=ch_color)

    # Market Cap
    _metric_card(draw, x_col1, y_row2, x_col1 + card_w, y_row2 + card_h,
                 "Market Cap", _fmt_large(market_cap) if market_cap else "—")

    # Sector
    sec_raw = sector or "—"
    sec_disp = sec_raw if len(sec_raw) <= 18 else sec_raw[:16] + "…"
    _metric_card(draw, x_col2, y_row2, x_col2 + card_w, y_row2 + card_h,
                 "Sector", sec_disp, value_color=GRAY_LT, value_size=32)

    return _to_png_bytes(img)


def _trade_image(
    flag_a: str, name_a: str, flag_b: str, name_b: str,
    trade_value: float | None,
    exports_usd: float | None = None,
    imports_usd: float | None = None,
    year: int | None = None,
) -> bytes:
    img, draw = _base_canvas()
    PAD = 56

    # ── Header: Country A  ↔  Country B ──────────────────────────────────
    name_a_d = name_a if len(name_a) <= 16 else name_a[:14] + "…"
    name_b_d = name_b if len(name_b) <= 16 else name_b[:14] + "…"

    draw.text((PAD, 22), flag_a, font=_font(44), fill=WHITE, anchor="lt")
    draw.text((PAD, 72), name_a_d, font=_font(36, bold=True), fill=WHITE, anchor="lt")
    draw.text((W // 2, 50), "↔", font=_font(46, bold=True), fill=GREEN, anchor="mm")
    draw.text((W - PAD, 22), flag_b, font=_font(44), fill=WHITE, anchor="rt")
    draw.text((W - PAD, 72), name_b_d, font=_font(36, bold=True), fill=WHITE, anchor="rt")

    # ── Trade volume — full-width card ────────────────────────────────────
    vol_label = "Total Trade Volume" + (f"  ·  {year}" if year else "")
    _metric_card(draw, PAD, 118, W - PAD, 298, vol_label,
                 _fmt_large(trade_value) if trade_value else "—", value_size=52)

    # ── Exports | Imports — side by side ──────────────────────────────────
    GAP_X = 20
    card_w = (W - PAD * 2 - GAP_X) // 2
    y2, card_h2 = 314, 230

    code_a = name_a[:3].upper()
    code_b = name_b[:3].upper()
    _metric_card(draw, PAD, y2, PAD + card_w, y2 + card_h2,
                 f"Exports  {code_a} → {code_b}",
                 _fmt_large(exports_usd) if exports_usd else "—")
    _metric_card(draw, PAD + card_w + GAP_X, y2, W - PAD, y2 + card_h2,
                 f"Exports  {code_b} → {code_a}",
                 _fmt_large(imports_usd) if imports_usd else "—")

    return _to_png_bytes(img)


# ── R2 upload helper ──────────────────────────────────────────────────────────

def _upload(key: str, data: bytes) -> None:
    import boto3
    from botocore.config import Config as BotoConfig
    r2 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )
    r2.put_object(
        Bucket=os.environ.get("R2_BUCKET_NAME", "metricshour-assets"),
        Key=key,
        Body=data,
        ContentType="image/png",
        CacheControl="public, max-age=86400",
    )


# ── Celery tasks ──────────────────────────────────────────────────────────────

@shared_task(name="tasks.og_images.generate_og_images", max_retries=1, time_limit=7200)
def generate_og_images() -> dict:
    """Generate + upload OG images for all countries, stocks, and trade pairs."""
    import sys
    sys.path.insert(0, "/root/metricshour/backend")
    os.environ.setdefault("PYTHONPATH", "/root/metricshour/backend")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy import select

    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    counts = {"countries": 0, "stocks": 0, "trade": 0, "errors": 0}

    with Session(engine) as db:
        # Import models inline to avoid circular deps
        from app.models.country import Country, CountryIndicator, TradePair
        from app.models.asset import Asset, AssetType, Price

        # ── Countries ──────────────────────────────────────────────────────
        countries = db.execute(select(Country)).scalars().all()

        def _ci(country_id: int, indicator: str) -> float | None:
            row = db.execute(
                select(CountryIndicator)
                .where(CountryIndicator.country_id == country_id,
                       CountryIndicator.indicator == indicator)
                .order_by(CountryIndicator.period_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            return row.value if row else None

        for c in countries:
            try:
                img_bytes = _country_image(
                    c.flag_emoji or "",
                    c.name,
                    gdp=_ci(c.id, "gdp_usd"),
                    growth=_ci(c.id, "gdp_growth_pct"),
                    inflation=_ci(c.id, "inflation_pct"),
                    interest_rate=_ci(c.id, "interest_rate"),
                )
                _upload(f"og/countries/{c.code.lower()}.png", img_bytes)
                counts["countries"] += 1
            except Exception as e:
                log.warning("OG country %s failed: %s", c.code, e)
                counts["errors"] += 1

        # ── Stocks ────────────────────────────────────────────────────────
        stocks = db.execute(
            select(Asset).where(Asset.asset_type == AssetType.stock, Asset.is_active == True)
        ).scalars().all()
        for a in stocks:
            try:
                price_row = db.execute(
                    select(Price)
                    .where(Price.asset_id == a.id, Price.interval == "1d")
                    .order_by(Price.timestamp.desc())
                    .limit(1)
                ).scalar_one_or_none()

                change_pct = None
                if price_row and price_row.open and price_row.close and price_row.open > 0:
                    change_pct = (price_row.close - price_row.open) / price_row.open * 100

                img_bytes = _stock_image(
                    a.symbol,
                    a.name,
                    price=price_row.close if price_row else None,
                    market_cap=a.market_cap_usd,
                    change_pct=change_pct,
                    sector=a.sector,
                )
                _upload(f"og/stocks/{a.symbol.lower()}.png", img_bytes)
                counts["stocks"] += 1
            except Exception as e:
                log.warning("OG stock %s failed: %s", a.symbol, e)
                counts["errors"] += 1

        # ── Trade pairs ───────────────────────────────────────────────────
        pairs = db.execute(select(TradePair)).scalars().all()
        # Deduplicate by (exp_id, imp_id) — keep latest year
        seen: set[tuple] = set()
        for p in sorted(pairs, key=lambda x: x.year or 0, reverse=True):
            key = (p.exporter_id, p.importer_id)
            if key in seen:
                continue
            seen.add(key)
            try:
                exp = db.get(Country, p.exporter_id)
                imp = db.get(Country, p.importer_id)
                if not exp or not imp:
                    continue
                img_bytes = _trade_image(
                    exp.flag_emoji or "",
                    exp.name,
                    imp.flag_emoji or "",
                    imp.name,
                    p.trade_value_usd,
                    exports_usd=p.exports_usd,
                    imports_usd=p.imports_usd,
                    year=p.year,
                )
                pair_key = f"{exp.code.lower()}-{imp.code.lower()}"
                _upload(f"og/trade/{pair_key}.png", img_bytes)
                counts["trade"] += 1
            except Exception as e:
                log.warning("OG trade %s-%s failed: %s", p.exporter_id, p.importer_id, e)
                counts["errors"] += 1

    log.info("OG images generated: %s", counts)
    return counts


# ── Feed event OG image ────────────────────────────────────────────────────────

# Accent colours per event type
_ACCENTS: dict[str, tuple[int, int, int]] = {
    "price_move":        (16, 185, 129),   # emerald-500
    "indicator_release": (59, 130, 246),   # blue-500
    "macro_release":     (59, 130, 246),
    "trade_update":      (245, 158, 11),   # amber-500
    "central_bank":      (168, 85, 247),   # purple-500
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


def _feed_event_image(
    event_type: str,
    title: str,
    event_data: dict | None,
    importance: float | None,
) -> bytes:
    """Render a 1200x630 OG image styled like the MetricsHour feed card."""
    data = event_data or {}
    accent = _ACCENTS.get(event_type, GREEN)
    bg_color = _BG_COLORS.get(event_type, BG)

    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Subtle centre glow
    glow_r, glow_g, glow_b = accent
    for i in range(10, 0, -1):
        alpha_f = i / 10 * 0.08
        rw, rh = int(W * (0.6 + i * 0.04)), int(H * (0.5 + i * 0.05))
        rx0, ry0 = (W - rw) // 2, (H - rh) // 2 - 40
        glow_col = (
            min(255, bg_color[0] + int((glow_r - bg_color[0]) * alpha_f)),
            min(255, bg_color[1] + int((glow_g - bg_color[1]) * alpha_f)),
            min(255, bg_color[2] + int((glow_b - bg_color[2]) * alpha_f)),
        )
        draw.ellipse([rx0, ry0, rx0 + rw, ry0 + rh], fill=glow_col)

    # Top importance bar
    if importance:
        bar_w = int(W * min(1.0, importance / 10))
        draw.rectangle([(0, 0), (bar_w, 5)], fill=accent)
    else:
        draw.rectangle([(0, 0), (W, 5)], fill=accent)

    # Minimal watermark only — no brand bar blocking content
    draw.text((W - 36, H - 14), "metricshour.com", font=_font(13), fill=GRAY, anchor="rm")

    # Event type badge pill (top-left)
    TYPE_LABELS = {
        "price_move": "PRICE MOVE",
        "indicator_release": "MACRO DATA",
        "macro_release": "MACRO DATA",
        "trade_update": "TRADE",
        "central_bank": "CENTRAL BANK",
        "blog": "ARTICLE",
    }
    badge_text = TYPE_LABELS.get(event_type, event_type.upper().replace("_", " "))
    badge_font = _font(18, bold=True)
    badge_tw = int(draw.textlength(badge_text, font=badge_font))
    bw = badge_tw + 32
    draw.rounded_rectangle([(48, 20), (48 + bw, 56)], radius=12, outline=accent, width=2)
    draw.text((48 + bw // 2, 38), badge_text, font=badge_font, fill=accent, anchor="mm")

    # ── Type-specific hero content ─────────────────────────────────────────
    cy = H // 2 - 30  # vertical centre anchor

    if event_type == "price_move":
        change_pct = float(data.get("change_pct", 0) or 0)
        symbol = str(data.get("symbol", ""))
        price = data.get("price")
        sign = "+" if change_pct >= 0 else ""
        pct_color = GREEN if change_pct >= 0 else (239, 68, 68)
        arrow = "↑" if change_pct >= 0 else "↓"

        draw.text((W // 2, cy - 10), f"{sign}{change_pct:.2f}%", font=_font(108, bold=True), fill=pct_color, anchor="mm")
        draw.text((W // 2, cy + 90), f"{arrow}  {symbol}", font=_font(46, bold=True), fill=WHITE, anchor="mm")
        if price:
            draw.text((W // 2, cy + 148), f"${float(price):,.2f}", font=_font(30), fill=GRAY_LT, anchor="mm")

    elif event_type in ("indicator_release", "macro_release"):
        country_code = str(data.get("country_code", "")).upper()
        value = data.get("value")
        indicator = str(data.get("indicator") or data.get("indicator_slug", "")).replace("_", " ").upper()

        if country_code:
            draw.text((W // 2, cy - 55), country_code, font=_font(76, bold=True), fill=accent, anchor="mm")

        if value is not None:
            n = float(value)
            if abs(n) >= 1e12:
                val_str = f"${n / 1e12:.1f}T"
            elif abs(n) >= 1e9:
                val_str = f"${n / 1e9:.1f}B"
            else:
                val_str = f"{n:.2f}" if abs(n) < 1000 else f"{n:,.0f}"
            # Value card
            draw.rounded_rectangle([(W // 2 - 280, cy + 5), (W // 2 + 280, cy + 95)], radius=10, fill=SURFACE)
            draw.rounded_rectangle([(W // 2 - 280, cy + 5), (W // 2 - 274, cy + 95)], radius=3, fill=accent)
            draw.text((W // 2, cy + 50), val_str, font=_font(72, bold=True), fill=WHITE, anchor="mm")

        if indicator:
            ind_display = indicator[:48] + "…" if len(indicator) > 48 else indicator
            draw.text((W // 2, cy + 118), ind_display, font=_font(26), fill=GRAY_LT, anchor="mm")

    elif event_type == "trade_update":
        exp = str(data.get("exporter", "")).upper()
        imp = str(data.get("importer", "")).upper()
        value = data.get("value_usd")

        draw.text((220, cy), exp, font=_font(92, bold=True), fill=WHITE, anchor="mm")
        draw.text((W // 2, cy), "↔", font=_font(68, bold=True), fill=accent, anchor="mm")
        draw.text((W - 220, cy), imp, font=_font(92, bold=True), fill=WHITE, anchor="mm")
        if value:
            n = float(value)
            val_str = f"${n / 1e9:.0f}B" if n >= 1e9 else f"${n / 1e6:.0f}M"
            draw.rounded_rectangle([(W // 2 - 200, cy + 70), (W // 2 + 200, cy + 140)], radius=10, fill=SURFACE)
            draw.text((W // 2, cy + 105), val_str, font=_font(44, bold=True), fill=accent, anchor="mm")

    elif event_type in ("central_bank", "blog"):
        # Generic: bold title centred
        pass  # handled below in title section

    # ── Title block (bottom area, above brand bar) ────────────────────────
    clean_title = title.encode("ascii", "ignore").decode("ascii").strip(" →↑↓·–—") or title
    words = clean_title.split()
    lines: list[str] = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= 52:
            current = (current + " " + w).strip()
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    lines = lines[:3]

    # title_y chosen so 3 lines × 42px all clear the brand bar (starts at H-56=574)
    # Line 2 centre = H-175+84 = 539 → text bottom ~558, 16px above brand bar
    title_y = H - 175
    for i, line in enumerate(lines):
        draw.text((56, title_y + i * 42), line, font=_font(32, bold=True), fill=WHITE, anchor="lm")

    return _to_png_bytes(img)


# ── Portrait social cards (720×1280, 9:16, "Did you know?" template) ──────────

SW, SH = 720, 1280   # social card dimensions


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _social_card(
    category: str,
    badge: str,
    title: str,
    subtitle: str,
    hero_number: str,
    hero_desc: str,
    facts: list[str],
    source: str,
    accent: tuple[int, int, int] = GREEN,
    cta: str = "Explore the data  \u2192",
) -> bytes:
    """720×1280 portrait 'Did you know?' social card — clean full-height layout."""
    BG     = (10, 14, 26)
    SURF   = (17, 24, 39)
    PAD    = 48

    img  = Image.new("RGB", (SW, SH), BG)
    draw = ImageDraw.Draw(img)

    # Soft accent glow behind hero area
    gr, gg, gb = accent
    for i in range(6, 0, -1):
        a = i / 6 * 0.04
        rw = SW + i * 40
        rh = 320 + i * 30
        draw.ellipse(
            [-(rw - SW) // 2, 480 - rh // 2, SW + (rw - SW) // 2, 480 + rh // 2],
            fill=(
                min(255, BG[0] + int((gr - BG[0]) * a)),
                min(255, BG[1] + int((gg - BG[1]) * a)),
                min(255, BG[2] + int((gb - BG[2]) * a)),
            ),
        )

    # ── Top accent bar ─────────────────────────────────────────────────────
    draw.rectangle([(0, 0), (SW, 5)], fill=accent)

    # ── 1. Category pill ───────────────────────────────────────────────────
    pf  = _font(14, bold=True)
    ptw = int(draw.textlength(category.upper(), font=pf))
    pw, ph = ptw + 30, 30
    draw.rounded_rectangle([(PAD, 52), (PAD + pw, 52 + ph)], radius=ph // 2, outline=accent, width=2)
    draw.text((PAD + pw // 2, 52 + ph // 2), category.upper(), font=pf, fill=accent, anchor="mm")

    # ── 2. Headline ────────────────────────────────────────────────────────
    draw.text((PAD, 110), "Did you know?", font=_font(64, bold=True), fill=WHITE, anchor="lt")

    # ── 3. Entity row ──────────────────────────────────────────────────────
    sq = 70
    draw.rounded_rectangle([(PAD, 212), (PAD + sq, 212 + sq)], radius=12, fill=accent)
    b   = badge[:4]
    bfz = 19 if len(b) == 4 else 23 if len(b) == 3 else 27
    draw.text((PAD + sq // 2, 212 + sq // 2), b, font=_font(bfz, bold=True), fill=BG, anchor="mm")

    tx   = PAD + sq + 18
    tf   = _font(30, bold=True)
    tmax = SW - tx - PAD
    ty   = 220
    for line in _wrap(draw, title, tf, tmax)[:2]:
        draw.text((tx, ty), line, font=tf, fill=accent, anchor="lt")
        ty += 38
    if subtitle:
        draw.text((tx, ty + 2), subtitle, font=_font(17), fill=GRAY, anchor="lt")

    # ── 4. Hero stat card ──────────────────────────────────────────────────
    HY, HH = 336, 216
    draw.rounded_rectangle([(PAD, HY), (SW - PAD, HY + HH)], radius=14, fill=SURF)
    draw.rounded_rectangle([(PAD, HY), (PAD + 5, HY + HH)], radius=3, fill=accent)
    draw.text((PAD + 24, HY + 78), hero_number, font=_font(86, bold=True), fill=accent, anchor="lm")
    dy = HY + 132
    for line in _wrap(draw, hero_desc, _font(18), SW - PAD * 2 - 44)[:2]:
        draw.text((PAD + 24, dy), line, font=_font(18), fill=GRAY_LT, anchor="lt")
        dy += 25

    # ── 5. Key facts ───────────────────────────────────────────────────────
    draw.text((PAD, 578), "KEY FACTS", font=_font(13, bold=True), fill=GRAY, anchor="lt")

    fy  = 608
    ff  = _font(20)
    fmw = SW - PAD * 2 - 28
    for fact in facts[:3]:
        # Left accent dot
        draw.ellipse([(PAD, fy + 8), (PAD + 7, fy + 15)], fill=accent)
        fd = fact if draw.textlength(fact, font=ff) <= fmw else fact[:46] + "\u2026"
        draw.text((PAD + 20, fy), fd, font=ff, fill=WHITE, anchor="lt")
        # Subtle row separator
        draw.rectangle([(PAD, fy + 34), (SW - PAD, fy + 35)], fill=(20, 28, 45))
        fy += 72

    # ── 6. CTA button ──────────────────────────────────────────────────────
    cl  = cta
    cf  = _font(22, bold=True)
    cw  = SW - PAD * 2
    draw.rounded_rectangle([(PAD, 950), (PAD + cw, 1010)], radius=30, fill=accent)
    draw.text((PAD + cw // 2, 980), cl, font=cf, fill=BG, anchor="mm")

    # ── 7. Source ──────────────────────────────────────────────────────────
    draw.text((PAD, 1040), f"Source: {source}", font=_font(14), fill=GRAY, anchor="lt")

    # ── 8. Brand bar ───────────────────────────────────────────────────────
    draw.rectangle([(0, 1160), (SW, 1280)], fill=SURF)
    lx, ly = PAD, 1195
    draw.rounded_rectangle([(lx, ly), (lx + 44, ly + 44)], radius=10, fill=accent)
    draw.text((lx + 22, ly + 22), "M", font=_font(24, bold=True), fill=BG, anchor="mm")
    draw.text((lx + 60, ly + 4), "MetricsHour", font=_font(24, bold=True), fill=WHITE, anchor="lt")
    draw.text((lx + 60, ly + 30), "metricshour.com", font=_font(16), fill=GRAY_LT, anchor="lt")

    return _to_png_bytes(img)



def _country_social_card(c, db) -> bytes:
    from sqlalchemy import select
    from app.models.country import CountryIndicator

    def _get(indicator: str):
        row = db.execute(
            select(CountryIndicator)
            .where(CountryIndicator.country_id == c.id, CountryIndicator.indicator == indicator)
            .order_by(CountryIndicator.period_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        return (row.value if row else None, row.period_date.year if row and row.period_date else None)

    gdp, gdp_year = _get("gdp_usd")
    growth, _ = _get("gdp_growth_pct")
    inflation, _ = _get("inflation_pct")
    population, _ = _get("population")

    hero_num = _fmt_large(gdp) if gdp else "N/A"
    hero_desc = "Gross Domestic Product (current USD)"

    facts: list[str] = []
    if growth is not None:
        sign = "+" if growth >= 0 else ""
        facts.append(f"GDP growth: {sign}{growth:.1f}%")
    if inflation is not None:
        facts.append(f"Inflation: {inflation:.1f}%")
    if population is not None:
        pop_m = population / 1e6
        facts.append(f"Population: {pop_m:.1f}M")
    while len(facts) < 3:
        facts.append("Data: metricshour.com")

    name_short = c.name if len(c.name) <= 18 else c.name[:16] + "\u2026"
    return _social_card(
        category="Global Economy",
        badge=c.code,
        title=c.name,
        subtitle=f"({gdp_year} data)" if gdp_year else "",
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="World Bank / MetricsHour",
        cta=f"Explore {name_short}  \u2192",
    )


def _stock_social_card(a, db) -> bytes:
    from sqlalchemy import select
    from app.models.asset import Price

    price_row = db.execute(
        select(Price)
        .where(Price.asset_id == a.id, Price.interval == "1d")
        .order_by(Price.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()

    price = price_row.close if price_row else None
    year = price_row.timestamp.year if price_row and price_row.timestamp else None

    hero_num = f"${price:,.2f}" if price else "N/A"
    hero_desc = f"{a.name} — latest close price"

    facts: list[str] = []
    if a.market_cap_usd:
        facts.append(f"Market cap: {_fmt_large(a.market_cap_usd)}")
    if a.sector:
        facts.append(f"Sector: {a.sector}")
    if a.exchange:
        facts.append(f"Exchange: {a.exchange}")
    while len(facts) < 3:
        facts.append("Data: metricshour.com")

    return _social_card(
        category="Equity Markets",
        badge=a.symbol[:4],
        title=a.symbol,
        subtitle=a.name[:32] + "\u2026" if len(a.name) > 32 else a.name,
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="Yahoo Finance / MetricsHour",
        cta=f"Track {a.symbol} on MetricsHour  \u2192",
    )


def _trade_social_card(exp, imp, p) -> bytes:
    hero_num = _fmt_large(p.trade_value_usd) if p.trade_value_usd else "N/A"
    hero_desc = f"{exp.name} ↔ {imp.name} annual trade volume"

    facts: list[str] = []
    if p.exports_usd:
        facts.append(f"Exports {exp.code}→{imp.code}: {_fmt_large(p.exports_usd)}")
    if p.imports_usd:
        facts.append(f"Imports {imp.code}→{exp.code}: {_fmt_large(p.imports_usd)}")
    if p.top_export_products:
        top = p.top_export_products
        if isinstance(top, list) and top:
            item = top[0]
            name = item.get("name", str(item)) if isinstance(item, dict) else str(item)
            facts.append(f"Top export: {name[:38]}")
        elif isinstance(top, str):
            facts.append(f"Top export: {top[:38]}")
    while len(facts) < 3:
        facts.append("Data: UN Comtrade / metricshour.com")

    return _social_card(
        category="Global Trade",
        badge=exp.code,
        title=f"{exp.name} \u2194 {imp.name}",
        subtitle=f"({p.year} data)" if p.year else "",
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="UN Comtrade / MetricsHour",
        accent=(251, 191, 36),
        cta=f"See {exp.code}\u2194{imp.code} trade flows  \u2192",
    )


@shared_task(name="tasks.og_images.generate_social_cards", max_retries=1, time_limit=7200)
def generate_social_cards() -> dict:
    """Generate 720×1280 portrait 'Did you know?' social cards for all entities. Upload to R2 social/."""
    import sys
    sys.path.insert(0, "/root/metricshour/backend")

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    counts = {"countries": 0, "stocks": 0, "trade": 0, "errors": 0}

    with Session(engine) as db:
        from app.models.country import Country, TradePair
        from app.models.asset import Asset, AssetType

        # Countries
        for c in db.execute(select(Country)).scalars().all():
            try:
                img_bytes = _country_social_card(c, db)
                _upload(f"social/countries/{c.code.lower()}.png", img_bytes)
                counts["countries"] += 1
            except Exception as e:
                log.warning("Social card country %s failed: %s", c.code, e)
                counts["errors"] += 1

        # Stocks
        for a in db.execute(select(Asset).where(Asset.asset_type == AssetType.stock, Asset.is_active == True)).scalars().all():
            try:
                img_bytes = _stock_social_card(a, db)
                _upload(f"social/stocks/{a.symbol.lower()}.png", img_bytes)
                counts["stocks"] += 1
            except Exception as e:
                log.warning("Social card stock %s failed: %s", a.symbol, e)
                counts["errors"] += 1

        # Trade pairs (latest year per pair)
        pairs = db.execute(select(TradePair)).scalars().all()
        seen: set[tuple] = set()
        for p in sorted(pairs, key=lambda x: x.year or 0, reverse=True):
            key = (p.exporter_id, p.importer_id)
            if key in seen:
                continue
            seen.add(key)
            try:
                exp = db.get(Country, p.exporter_id)
                imp = db.get(Country, p.importer_id)
                if not exp or not imp:
                    continue
                img_bytes = _trade_social_card(exp, imp, p)
                pair_key = f"{exp.code.lower()}-{imp.code.lower()}"
                _upload(f"social/trade/{pair_key}.png", img_bytes)
                counts["trade"] += 1
            except Exception as e:
                log.warning("Social card trade %s-%s failed: %s", p.exporter_id, p.importer_id, e)
                counts["errors"] += 1

    log.info("Social cards generated: %s", counts)
    return counts


@shared_task(name="tasks.og_images.generate_feed_og_images", max_retries=1, time_limit=3600)
def generate_feed_og_images() -> dict:
    """
    Generate + upload OG images for all feed events that don't yet have one.
    Runs after the main OG task (same daily schedule, or triggered on-demand).
    """
    import sys
    sys.path.insert(0, "/root/metricshour/backend")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy import select

    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    r2_public_url = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    counts = {"generated": 0, "skipped": 0, "errors": 0}

    with Session(engine) as db:
        from app.models.feed import FeedEvent

        events = db.execute(
            select(FeedEvent).order_by(FeedEvent.id).with_for_update(skip_locked=True)
        ).scalars().all()
        for ev in events:
            try:
                r2_key = f"og/feed/{ev.id}.png"
                img_bytes = _feed_event_image(
                    ev.event_type,
                    ev.title,
                    ev.event_data,
                    ev.importance_score,
                )
                _upload(r2_key, img_bytes)
                # Backfill image_url on the event row if not already set
                if not ev.image_url and r2_public_url:
                    ev.image_url = f"{r2_public_url}/{r2_key}"
                counts["generated"] += 1
            except Exception as e:
                log.warning("Feed OG event %s failed: %s", ev.id, e)
                counts["errors"] += 1

        db.commit()

    log.info("Feed OG images: %s", counts)
    return counts
