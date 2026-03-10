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


# ── Canvas helpers ─────────────────────────────────────────────────────────────

def _base_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle grid
    for x in range(0, W, 80):
        draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 6), width=1)
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill=(255, 255, 255, 6), width=1)

    # Top accent line
    draw.rectangle([(0, 0), (W, 4)], fill=GREEN)

    # MetricsHour brand — bottom right
    draw.text((W - 32, H - 40), "METRICSHOUR", font=_font(18, bold=True), fill=GREEN, anchor="rm")

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
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# ── Generators ────────────────────────────────────────────────────────────────

def _country_image(flag: str, name: str, gdp: float | None, growth: float | None) -> bytes:
    img, draw = _base_canvas()

    # Flag (large emoji via text — best effort; will render as box on some systems)
    draw.text((80, H // 2 - 60), flag, font=_font(120), fill=WHITE, anchor="lm")

    # Country name
    draw.text((260, H // 2 - 50), name, font=_font(64, bold=True), fill=WHITE, anchor="lm")

    # GDP
    gdp_str = _fmt_large(gdp)
    draw.text((260, H // 2 + 30), f"GDP  {gdp_str}", font=_font(32), fill=GRAY_LT, anchor="lm")

    # Growth
    if growth is not None:
        color = GREEN if growth >= 0 else (248, 113, 113)
        sign = "+" if growth >= 0 else ""
        draw.text((260, H // 2 + 80), f"Growth  {sign}{growth:.1f}%", font=_font(28), fill=color, anchor="lm")

    # Label
    draw.text((80, H - 40), "Economy & Macro Intelligence", font=_font(22), fill=GRAY, anchor="lm")

    return _to_png_bytes(img)


def _stock_image(symbol: str, name: str, price: float | None, market_cap: float | None) -> bytes:
    img, draw = _base_canvas()

    # Ticker
    draw.text((80, H // 2 - 80), symbol, font=_font(96, bold=True), fill=GREEN, anchor="lm")

    # Company name
    # Truncate long names
    display_name = name if len(name) <= 30 else name[:28] + "…"
    draw.text((80, H // 2 + 20), display_name, font=_font(40), fill=WHITE, anchor="lm")

    # Price + market cap
    if price is not None:
        draw.text((80, H // 2 + 90), f"${price:,.2f}", font=_font(32), fill=WHITE, anchor="lm")
    if market_cap is not None:
        draw.text((80, H // 2 + 140), f"Market cap  {_fmt_large(market_cap)}", font=_font(28), fill=GRAY_LT, anchor="lm")

    # Label
    draw.text((80, H - 40), "Geographic Revenue & Market Intelligence", font=_font(22), fill=GRAY, anchor="lm")

    return _to_png_bytes(img)


def _trade_image(flag_a: str, name_a: str, flag_b: str, name_b: str, trade_value: float | None) -> bytes:
    img, draw = _base_canvas()

    # Country A
    draw.text((80, H // 2 - 30), flag_a, font=_font(80), fill=WHITE, anchor="lm")
    draw.text((200, H // 2 - 30), name_a, font=_font(48, bold=True), fill=WHITE, anchor="lm")

    # Arrow
    draw.text((W // 2, H // 2 - 30), "↔", font=_font(56, bold=True), fill=GREEN, anchor="mm")

    # Country B — right side
    b_x = W - 80
    draw.text((b_x, H // 2 - 30), flag_b, font=_font(80), fill=WHITE, anchor="rm")
    draw.text((b_x - 130, H // 2 - 30), name_b, font=_font(48, bold=True), fill=WHITE, anchor="rm")

    # Trade value
    if trade_value is not None:
        draw.text((W // 2, H // 2 + 60), f"Trade volume  {_fmt_large(trade_value)}", font=_font(32), fill=GRAY_LT, anchor="mm")

    # Label
    draw.text((80, H - 40), "Bilateral Trade Intelligence · UN Comtrade", font=_font(22), fill=GRAY, anchor="lm")

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

@shared_task(name="tasks.og_images.generate_og_images", max_retries=1)
def generate_og_images() -> dict:
    """Generate + upload OG images for all countries, stocks, and trade pairs."""
    import sys
    sys.path.insert(0, "/var/www/metricshour/backend")
    os.environ.setdefault("PYTHONPATH", "/var/www/metricshour/backend")

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
        for c in countries:
            try:
                gdp_row = db.execute(
                    select(CountryIndicator)
                    .where(CountryIndicator.country_id == c.id, CountryIndicator.indicator == "gdp_usd")
                    .order_by(CountryIndicator.period_date.desc())
                    .limit(1)
                ).scalar_one_or_none()
                growth_row = db.execute(
                    select(CountryIndicator)
                    .where(CountryIndicator.country_id == c.id, CountryIndicator.indicator == "gdp_growth_pct")
                    .order_by(CountryIndicator.period_date.desc())
                    .limit(1)
                ).scalar_one_or_none()

                img_bytes = _country_image(
                    c.flag_emoji or "",
                    c.name,
                    gdp_row.value if gdp_row else None,
                    growth_row.value if growth_row else None,
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

                img_bytes = _stock_image(
                    a.symbol,
                    a.name,
                    price_row.close if price_row else None,
                    a.market_cap_usd,
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

    # Subtle radial glow (fake with a large blurred circle)
    # Draw concentric rects with decreasing opacity for glow effect
    glow_r, glow_g, glow_b = accent
    for i in range(12, 0, -1):
        alpha = int(20 * (i / 12))
        rect_w, rect_h = W * (1 - i * 0.03), H * (1 - i * 0.05)
        x0 = (W - rect_w) / 2
        y0 = (H - rect_h) / 2 - H * 0.1  # offset upward
        glow_color = (
            max(0, bg_color[0] + int((glow_r - bg_color[0]) * alpha / 255)),
            max(0, bg_color[1] + int((glow_g - bg_color[1]) * alpha / 255)),
            max(0, bg_color[2] + int((glow_b - bg_color[2]) * alpha / 255)),
        )
        draw.ellipse([x0, y0, x0 + rect_w, y0 + rect_h], fill=glow_color)

    # Top importance bar
    if importance:
        bar_width = int(W * min(1.0, importance / 10))
        draw.rectangle([(0, 0), (bar_width, 5)], fill=accent)

    # Brand watermark top-right
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

    # ── Type-specific hero content ─────────────────────────────────────────
    cy = H // 2 - 20  # vertical centre anchor

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

        # Big country code
        if country_code:
            draw.text((W // 2, cy - 60), country_code, font=_font(80, bold=True), fill=accent, anchor="mm")

        # Big value
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
            # Truncate
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

    else:
        # Blog / generic — just show title large
        pass

    # ── Title (bottom area) ──────────────────────────────────────────────
    # Strip leading emoji sequences (rough approach: skip non-ASCII prefix)
    clean_title = title.encode("ascii", "ignore").decode("ascii").strip(" →↑↓·–—") or title
    # Word-wrap at ~55 chars per line
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
    lines = lines[:3]  # max 3 lines

    title_y = H - 120
    for i, line in enumerate(lines):
        draw.text((60, title_y + i * 44), line, font=_font(34, bold=True), fill=WHITE, anchor="lm")

    # Subtle bottom border
    draw.rectangle([(0, H - 6), (W, H)], fill=accent)

    return _to_png_bytes(img)


@shared_task(name="tasks.og_images.generate_feed_og_images", max_retries=1)
def generate_feed_og_images() -> dict:
    """
    Generate + upload OG images for all feed events that don't yet have one.
    Runs after the main OG task (same daily schedule, or triggered on-demand).
    """
    import sys
    sys.path.insert(0, "/var/www/metricshour/backend")

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
