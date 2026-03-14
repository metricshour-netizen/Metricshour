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

    # Bottom brand bar (consistent with other templates)
    draw.rectangle([(0, H - 56), (W, H)], fill=SURFACE)
    logo_sz = 34
    lx, ly = 36, H - 56 + (56 - logo_sz) // 2
    draw.rounded_rectangle([(lx, ly), (lx + logo_sz, ly + logo_sz)], radius=6, fill=accent)
    draw.text((lx + logo_sz // 2, ly + logo_sz // 2), "M", font=_font(20, bold=True), fill=bg_color, anchor="mm")
    draw.text((lx + logo_sz + 12, H - 28), "MetricsHour", font=_font(20, bold=True), fill=WHITE, anchor="lm")
    draw.text((W - 36, H - 28), "metricshour.com", font=_font(17), fill=GRAY, anchor="rm")

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

    title_y = H - 130
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
    flag: str,
    title: str,
    subtitle: str,
    hero_number: str,
    hero_desc: str,
    facts: list[str],
    source: str,
    accent: tuple[int, int, int] = GREEN,
) -> bytes:
    """
    720x1280 portrait social card — pixel-matched to Telegram template.
    Fixed layout positions (all left-aligned):
      y=40   category pill (outline, left-aligned)
      y=102  "Did you know?" 58px bold white
      y=178  entity row: red 64px square + 28px green title + gray subtitle below
      y=268  hero card h=148: 70px number left | description RIGHT-ALIGNED right col
      y=436  KEY FACTS 14px gray label
      y=458  facts card 3x48px rows with gray square outline bullets
      y=1098 source text (fixed)
      y=1128 CTA button partial-width left pill
      y=1207 thin divider
      y=1215 brand bar: outlined M box + MetricsHour white + metricshour.com accent
    """
    BG_COL   = (10, 14, 26)
    SURF_COL = (17, 24, 39)
    FLAG_RED = (220, 38, 38)
    PAD      = 40

    img  = Image.new("RGB", (SW, SH), BG_COL)
    draw = ImageDraw.Draw(img)

    # 1. Category pill — y=40, left, outline only
    pf  = _font(15, bold=True)
    ptw = int(draw.textlength(category.upper(), font=pf))
    pw, ph = ptw + 28, 32
    draw.rounded_rectangle([(PAD, 40), (PAD + pw, 40 + ph)], radius=ph // 2, outline=accent, width=2)
    draw.text((PAD + pw // 2, 40 + ph // 2), category.upper(), font=pf, fill=accent, anchor="mm")

    # 2. "Did you know?" — y=102, 58px bold white, left
    draw.text((PAD, 102), "Did you know?", font=_font(58, bold=True), fill=WHITE, anchor="lt")

    # 3. Entity row — y=178
    sq = 64
    draw.rounded_rectangle([(PAD, 178), (PAD + sq, 242)], radius=10, fill=FLAG_RED)
    draw.text((PAD + sq // 2, 210), flag[:2] if flag else "?", font=_font(30), fill=WHITE, anchor="mm")

    tx = PAD + sq + 16
    tf = _font(28, bold=True)
    tmax = SW - tx - PAD
    tlines = _wrap(draw, title, tf, tmax)
    ty = 183
    for tl in tlines[:2]:
        draw.text((tx, ty), tl, font=tf, fill=accent, anchor="lt")
        ty += 36
    draw.text((tx, ty + 2), subtitle, font=_font(19), fill=GRAY, anchor="lt")

    # 4. Hero stat card — y=268, h=148, number left 70px, desc right-aligned
    CY, CH = 268, 148
    draw.rounded_rectangle([(PAD, CY), (SW - PAD, CY + CH)], radius=10, fill=SURF_COL)
    draw.rounded_rectangle([(PAD, CY), (PAD + 5, CY + CH)], radius=3, fill=accent)

    nf = _font(70, bold=True)
    nw = int(draw.textlength(hero_number, font=nf))
    draw.text((PAD + 18, CY + CH // 2), hero_number, font=nf, fill=accent, anchor="lm")

    # Description: right column, RIGHT-aligned, vertically centred
    dx0  = PAD + 18 + nw + 10
    dx1  = SW - PAD - 16
    dmax = dx1 - dx0
    df   = _font(19)
    dlines = _wrap(draw, hero_desc, df, dmax)
    bh   = len(dlines[:3]) * 25
    dy   = CY + (CH - bh) // 2
    for dl in dlines[:3]:
        draw.text((dx1, dy), dl, font=df, fill=GRAY_LT, anchor="rt")
        dy += 25

    # 5. KEY FACTS label — y=436
    draw.text((PAD, 436), "KEY FACTS", font=_font(14, bold=True), fill=GRAY, anchor="lt")

    # 6. Facts card — y=458
    fc_y, fc_h = 458, 3 * 48 + 20
    draw.rounded_rectangle([(PAD, fc_y), (SW - PAD, fc_y + fc_h)], radius=10, fill=SURF_COL)
    fy = fc_y + 16
    ff = _font(19)
    for fact in facts[:3]:
        bx, by = PAD + 16, fy + 9
        draw.rectangle([(bx, by), (bx + 8, by + 8)], outline=GRAY, width=1)
        fd = fact if draw.textlength(fact, font=ff) <= (SW - PAD - PAD - 40) else fact[:52] + "\u2026"
        draw.text((PAD + 38, fy + 1), fd, font=ff, fill=WHITE, anchor="lt")
        fy += 48

    # 7. Source — fixed y=1098
    draw.text((PAD, 1098), f"Source: {source}", font=_font(15), fill=GRAY, anchor="lt")

    # 8. CTA button — partial width, left pill, y=1128
    cl = "Explore the data  \u2192"
    cf = _font(21, bold=True)
    cw = int(draw.textlength(cl, font=cf)) + 44
    draw.rounded_rectangle([(PAD, 1128), (PAD + cw, 1128 + 52)], radius=26, fill=accent)
    draw.text((PAD + cw // 2, 1154), cl, font=cf, fill=BG_COL, anchor="mm")

    # 9. Thin divider — y=1207
    draw.rectangle([(PAD, 1207), (SW - PAD, 1208)], fill=(31, 41, 55))

    # 10. Brand bar — y=1215
    lx, ly = PAD, 1215
    draw.rounded_rectangle([(lx, ly), (lx + 38, ly + 38)], radius=7, outline=accent, width=2)
    draw.text((lx + 19, ly + 19), "M", font=_font(21, bold=True), fill=accent, anchor="mm")
    draw.text((lx + 50, ly + 8), "MetricsHour", font=_font(21, bold=True), fill=WHITE, anchor="lt")
    draw.text((lx + 50, ly + 32), "metricshour.com", font=_font(15), fill=accent, anchor="lt")

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
        subtitle=f"({gdp_year} data)" if gdp_year else "",
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="World Bank / MetricsHour",
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
        subtitle=a.name[:32] + "…" if len(a.name) > 32 else a.name,
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="Yahoo Finance / MetricsHour",
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
        flag=exp.flag_emoji or "",
        title=f"{exp.name} ↔ {imp.name}",
        subtitle=f"({p.year} data)" if p.year else "",
        hero_number=hero_num,
        hero_desc=hero_desc,
        facts=facts,
        source="UN Comtrade / MetricsHour",
        accent=(251, 191, 36),   # amber for trade cards
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
