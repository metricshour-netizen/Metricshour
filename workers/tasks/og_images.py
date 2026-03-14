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

    # Top accent bar
    draw.rectangle([(0, 0), (W, 5)], fill=GREEN)

    # Bottom brand bar
    draw.rectangle([(0, H - 56), (W, H)], fill=SURFACE)

    # M logo box
    logo_sz = 34
    lx, ly = 36, H - 56 + (56 - logo_sz) // 2
    draw.rounded_rectangle([(lx, ly), (lx + logo_sz, ly + logo_sz)], radius=6, fill=GREEN)
    draw.text((lx + logo_sz // 2, ly + logo_sz // 2), "M", font=_font(20, bold=True), fill=BG, anchor="mm")

    draw.text((lx + logo_sz + 12, H - 28), "MetricsHour", font=_font(20, bold=True), fill=WHITE, anchor="lm")
    draw.text((W - 36, H - 28), "metricshour.com", font=_font(17), fill=GRAY, anchor="rm")

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

    PAD = 64
    cy = H // 2 - 30

    # Flag square
    if flag:
        flag_sz = 80
        draw.rounded_rectangle([(PAD, cy - flag_sz // 2 - 40), (PAD + flag_sz, cy - flag_sz // 2 + 40)], radius=12, fill=SURFACE)
        draw.text((PAD + flag_sz // 2, cy - flag_sz // 2 + 40 - flag_sz // 2), flag, font=_font(52), fill=WHITE, anchor="mm")
        tx = PAD + flag_sz + 28
    else:
        tx = PAD

    # Country name
    name_disp = name if len(name) <= 22 else name[:20] + "…"
    draw.text((tx, cy - 50), name_disp, font=_font(68, bold=True), fill=WHITE, anchor="lm")

    # GDP card
    gdp_str = _fmt_large(gdp)
    card_x0, card_x1 = tx, W - PAD
    draw.rounded_rectangle([(card_x0, cy + 10), (card_x1, cy + 100)], radius=10, fill=SURFACE)
    draw.rounded_rectangle([(card_x0, cy + 10), (card_x0 + 6, cy + 100)], radius=3, fill=GREEN)
    draw.text((card_x0 + 24, cy + 55), f"GDP  {gdp_str}", font=_font(36, bold=True), fill=WHITE, anchor="lm")

    if growth is not None:
        color = GREEN if growth >= 0 else (248, 113, 113)
        sign = "+" if growth >= 0 else ""
        draw.text((card_x1 - 16, cy + 55), f"{sign}{growth:.1f}%", font=_font(32, bold=True), fill=color, anchor="rm")

    # Sub-label
    draw.text((PAD, H - 88), "Economy & Macro Intelligence", font=_font(22), fill=GRAY, anchor="lm")

    return _to_png_bytes(img)


def _stock_image(symbol: str, name: str, price: float | None, market_cap: float | None) -> bytes:
    img, draw = _base_canvas()

    PAD = 64
    cy = H // 2 - 20

    # Ticker (large green)
    draw.text((PAD, cy - 70), symbol, font=_font(100, bold=True), fill=GREEN, anchor="lm")

    # Company name
    display_name = name if len(name) <= 32 else name[:30] + "…"
    draw.text((PAD, cy + 10), display_name, font=_font(38), fill=WHITE, anchor="lm")

    # Price card
    if price is not None or market_cap is not None:
        draw.rounded_rectangle([(PAD, cy + 60), (W - PAD, cy + 160)], radius=10, fill=SURFACE)
        draw.rounded_rectangle([(PAD, cy + 60), (PAD + 6, cy + 160)], radius=3, fill=GREEN)
        if price is not None:
            draw.text((PAD + 24, cy + 100), f"${price:,.2f}", font=_font(42, bold=True), fill=WHITE, anchor="lm")
        if market_cap is not None:
            draw.text((W - PAD - 16, cy + 100), f"Cap  {_fmt_large(market_cap)}", font=_font(28), fill=GRAY_LT, anchor="rm")

    draw.text((PAD, H - 88), "Geographic Revenue & Market Intelligence", font=_font(22), fill=GRAY, anchor="lm")

    return _to_png_bytes(img)


def _trade_image(flag_a: str, name_a: str, flag_b: str, name_b: str, trade_value: float | None) -> bytes:
    img, draw = _base_canvas()

    PAD = 48
    cy = H // 2 - 30

    # Country A block (left)
    name_a_disp = name_a if len(name_a) <= 14 else name_a[:12] + "…"
    draw.text((PAD, cy - 50), flag_a, font=_font(72), fill=WHITE, anchor="lm")
    draw.text((PAD, cy + 20), name_a_disp, font=_font(40, bold=True), fill=WHITE, anchor="lm")

    # Arrow (center)
    draw.text((W // 2, cy - 14), "↔", font=_font(64, bold=True), fill=GREEN, anchor="mm")

    # Country B block (right)
    name_b_disp = name_b if len(name_b) <= 14 else name_b[:12] + "…"
    draw.text((W - PAD, cy - 50), flag_b, font=_font(72), fill=WHITE, anchor="rm")
    draw.text((W - PAD, cy + 20), name_b_disp, font=_font(40, bold=True), fill=WHITE, anchor="rm")

    # Trade value card
    if trade_value is not None:
        draw.rounded_rectangle([(PAD, cy + 70), (W - PAD, cy + 160)], radius=10, fill=SURFACE)
        draw.rounded_rectangle([(PAD, cy + 70), (PAD + 6, cy + 160)], radius=3, fill=GREEN)
        draw.text((W // 2, cy + 115), f"Trade volume  {_fmt_large(trade_value)}", font=_font(34, bold=True), fill=WHITE, anchor="mm")

    draw.text((PAD, H - 88), "Bilateral Trade Intelligence · UN Comtrade", font=_font(22), fill=GRAY, anchor="lm")

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
    flag: str,
    title: str,
    year: str | int | None,
    hero_number: str,
    hero_desc: str,
    facts: list[str],
    source: str,
) -> bytes:
    """
    720×1280 portrait "Did you know?" social card.
    Layout: category pill → headline → entity row → hero stat card → key facts → source → CTA → brand bar.
    """
    img = Image.new("RGB", (SW, SH), BG)
    draw = ImageDraw.Draw(img)

    PAD = 36
    INNER = SW - PAD * 2
    y = 60

    # ── Category pill (centered, green outline) ────────────────────────────
    pill_font = _font(19, bold=True)
    pill_text = category.upper()
    pill_tw = int(draw.textlength(pill_text, font=pill_font))
    pill_w, pill_h = pill_tw + 40, 38
    px0 = (SW - pill_w) // 2
    draw.rounded_rectangle([(px0, y), (px0 + pill_w, y + pill_h)], radius=14, outline=GREEN, width=2)
    draw.text((SW // 2, y + pill_h // 2), pill_text, font=pill_font, fill=GREEN, anchor="mm")
    y += pill_h + 22

    # ── "Did you know?" headline ───────────────────────────────────────────
    h1_font = _font(54, bold=True)
    draw.text((SW // 2, y + 32), "Did you know?", font=h1_font, fill=WHITE, anchor="mm")
    y += 72

    # ── Entity row: flag square + name (green) + year (gray) ──────────────
    flag_sz = 50
    if flag:
        draw.rounded_rectangle([(PAD, y), (PAD + flag_sz, y + flag_sz)], radius=8, fill=SURFACE)
        draw.text((PAD + flag_sz // 2, y + flag_sz // 2), flag, font=_font(30), fill=WHITE, anchor="mm")
        tx = PAD + flag_sz + 14
    else:
        tx = PAD

    name_font = _font(26, bold=True)
    max_name_w = SW - tx - PAD - 64
    name_disp = title if draw.textlength(title, font=name_font) <= max_name_w else title[:26] + "…"
    draw.text((tx, y + flag_sz // 2), name_disp, font=name_font, fill=GREEN, anchor="lm")

    if year:
        yr_font = _font(21)
        draw.text((SW - PAD, y + flag_sz // 2), str(year), font=yr_font, fill=GRAY, anchor="rm")
    y += flag_sz + 26

    # ── Hero stat card (dark bg, 6px green left border) ────────────────────
    card_h = 134
    draw.rounded_rectangle([(PAD, y), (SW - PAD, y + card_h)], radius=10, fill=SURFACE)
    draw.rounded_rectangle([(PAD, y), (PAD + 6, y + card_h)], radius=3, fill=GREEN)

    num_font = _font(54, bold=True)
    draw.text((PAD + 24, y + 40), hero_number, font=num_font, fill=GREEN, anchor="lm")

    desc_font = _font(21)
    desc_lines = _wrap(draw, hero_desc, desc_font, INNER - 32)
    dy = y + 86
    for line in desc_lines[:2]:
        draw.text((PAD + 24, dy), line, font=desc_font, fill=GRAY_LT, anchor="lm")
        dy += 26
    y += card_h + 26

    # ── KEY FACTS ─────────────────────────────────────────────────────────
    lbl_font = _font(17, bold=True)
    draw.text((PAD, y + 10), "KEY FACTS", font=lbl_font, fill=GRAY, anchor="lm")
    y += 30

    facts_to_show = facts[:3]
    fact_font = _font(21)
    fact_card_h = max(96, 20 + len(facts_to_show) * 52)
    draw.rounded_rectangle([(PAD, y), (SW - PAD, y + fact_card_h)], radius=10, fill=SURFACE)

    fy = y + 22
    for fact in facts_to_show:
        draw.rectangle([(PAD + 16, fy + 7), (PAD + 24, fy + 15)], fill=GREEN)
        fact_disp = fact if draw.textlength(fact, font=fact_font) <= INNER - 50 else fact[:52] + "…"
        draw.text((PAD + 38, fy + 1), fact_disp, font=fact_font, fill=WHITE, anchor="lm")
        fy += 48
    y += fact_card_h + 16

    # ── Source ────────────────────────────────────────────────────────────
    draw.text((PAD, y + 10), f"Source: {source}", font=_font(17), fill=GRAY, anchor="lm")
    y += 34

    # ── CTA button (green, full-width minus padding) ───────────────────────
    brand_h = 72
    cta_h = 56
    cta_y = SH - brand_h - cta_h - 28
    cta_y = max(cta_y, y + 8)
    draw.rounded_rectangle([(PAD, cta_y), (SW - PAD, cta_y + cta_h)], radius=12, fill=GREEN)
    draw.text((SW // 2, cta_y + cta_h // 2), "Explore the data →", font=_font(24, bold=True), fill=BG, anchor="mm")

    # ── Brand bar ─────────────────────────────────────────────────────────
    brand_y = SH - brand_h
    draw.rectangle([(0, brand_y), (SW, SH)], fill=SURFACE)

    # M logo box
    logo_sz = 42
    lx = PAD
    ly = brand_y + (brand_h - logo_sz) // 2
    draw.rounded_rectangle([(lx, ly), (lx + logo_sz, ly + logo_sz)], radius=7, fill=GREEN)
    draw.text((lx + logo_sz // 2, ly + logo_sz // 2), "M", font=_font(26, bold=True), fill=BG, anchor="mm")

    draw.text((lx + logo_sz + 14, brand_y + brand_h // 2), "MetricsHour", font=_font(24, bold=True), fill=WHITE, anchor="lm")
    draw.text((SW - PAD, brand_y + brand_h // 2), "metricshour.com", font=_font(18), fill=GRAY, anchor="rm")

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

    return _social_card(
        category="Global Economy",
        flag=c.flag_emoji or "",
        title=c.name,
        year=gdp_year,
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="World Bank",
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
        flag="📈",
        title=a.symbol,
        year=year,
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="Yahoo Finance",
    )


def _trade_social_card(exp, imp, p) -> bytes:
    hero_num = _fmt_large(p.trade_value_usd) if p.trade_value_usd else "N/A"
    hero_desc = f"{exp.name} ↔ {imp.name} annual trade volume"

    facts: list[str] = []
    if p.export_value_usd:
        facts.append(f"Exports {exp.code}→{imp.code}: {_fmt_large(p.export_value_usd)}")
    if p.import_value_usd:
        facts.append(f"Imports {imp.code}→{exp.code}: {_fmt_large(p.import_value_usd)}")
    if p.top_products:
        top = p.top_products
        if isinstance(top, list) and top:
            facts.append(f"Top product: {str(top[0])[:40]}")
        elif isinstance(top, str):
            facts.append(f"Top product: {top[:40]}")
    while len(facts) < 3:
        facts.append("Data: UN Comtrade / metricshour.com")

    return _social_card(
        category="Global Trade",
        flag=f"{exp.flag_emoji or ''}{imp.flag_emoji or ''}",
        title=f"{exp.code} ↔ {imp.code}",
        year=p.year,
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="UN Comtrade / WITS",
    )


@shared_task(name="tasks.og_images.generate_social_cards", max_retries=1)
def generate_social_cards() -> dict:
    """Generate 720×1280 portrait 'Did you know?' social cards for all entities. Upload to R2 social/."""
    import sys
    sys.path.insert(0, "/var/www/metricshour/backend")

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
