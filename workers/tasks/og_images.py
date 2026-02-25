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
