"""
Generate a Reddit ad image (1200×628) for MetricsHour
and send it to Telegram.

Usage: python3 reddit_ad_gen.py
"""
import io
import math
import os
import subprocess
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

# ── Dimensions (Reddit standard feed ad) ──────────────────────────────────────
W, H = 1200, 628

# ── Brand colours ─────────────────────────────────────────────────────────────
BG       = (10, 14, 26)          # #0a0e1a  deep navy
SURFACE  = (17, 24, 39)          # #111827  card bg
BORDER   = (31, 41, 55)          # #1f2937
ACCENT   = (52, 211, 153)        # #34d399  emerald-400
ACCENT2  = (99, 102, 241)        # #6366f1  indigo-500 (secondary)
WHITE    = (255, 255, 255)
GRAY     = (107, 114, 128)
GRAY_LT  = (156, 163, 175)
YELLOW   = (251, 191, 36)        # amber-400

# ── Fonts (DejaVu guaranteed on Ubuntu) ───────────────────────────────────────
FONT_BASE = "/usr/share/fonts/truetype/dejavu"

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(FONT_BASE, name), size)


def _text_w(draw, text, font):
    return draw.textlength(text, font=font)


def _centered_text(draw, y, text, font, color=WHITE):
    w = _text_w(draw, text, font)
    draw.text(((W - w) / 2, y), text, font=font, fill=color)


def _draw_rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                           outline=outline, width=width)


# ── Sparkline helper ──────────────────────────────────────────────────────────
def _sparkline(draw, x, y, w, h, values, color):
    if len(values) < 2:
        return
    mn, mx = min(values), max(values)
    span = mx - mn or 1
    pts = []
    for i, v in enumerate(values):
        px = x + i * w / (len(values) - 1)
        py = y + h - (v - mn) / span * h
        pts.append((px, py))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=color, width=2)


# ── Stat card ─────────────────────────────────────────────────────────────────
def _stat_card(draw, x, y, w, h, label, value, change, spark_vals, accent):
    _draw_rounded_rect(draw, (x, y, x + w, y + h), radius=10, fill=SURFACE,
                       outline=BORDER, width=1)
    # label
    lf = _font(14)
    draw.text((x + 14, y + 14), label, font=lf, fill=GRAY_LT)
    # value
    vf = _font(26, bold=True)
    draw.text((x + 14, y + 36), value, font=vf, fill=WHITE)
    # change badge
    up = not change.startswith("-")
    badge_col = ACCENT if up else (248, 113, 113)
    arrow = "▲" if up else "▼"
    cf = _font(14, bold=True)
    badge_text = f" {arrow} {change} "
    bw = _text_w(draw, badge_text, cf)
    _draw_rounded_rect(draw, (x + 14, y + 72, x + 14 + bw, y + 92),
                       radius=6, fill=badge_col)
    draw.text((x + 14, y + 73), badge_text, font=cf, fill=BG)
    # sparkline
    _sparkline(draw, x + 14, y + 100, w - 28, 30, spark_vals, badge_col)


def generate() -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Background grid lines ──────────────────────────────────────────────────
    for gx in range(0, W, 80):
        draw.line([(gx, 0), (gx, H)], fill=(20, 27, 45), width=1)
    for gy in range(0, H, 60):
        draw.line([(0, gy), (W, gy)], fill=(20, 27, 45), width=1)

    # ── Left panel ─────────────────────────────────────────────────────────────
    panel_x, panel_y = 48, 0
    panel_w = 420

    # Logo / brand
    logo_f = _font(28, bold=True)
    logo_text = "MetricsHour"
    draw.text((panel_x, 52), logo_text, font=logo_f, fill=ACCENT)
    dot_x = panel_x + _text_w(draw, logo_text, logo_f) + 6
    draw.ellipse((dot_x, 63, dot_x + 7, 70), fill=ACCENT2)

    # Headline
    headline = "Real-time Global\nMarket Intelligence"
    hf = _font(52, bold=True)
    hy = 100
    for line in headline.split("\n"):
        draw.text((panel_x, hy), line, font=hf, fill=WHITE)
        hy += 62

    # Sub-text
    sub_lines = [
        "Stocks · Crypto · FX · Commodities",
        "Trade Flows · Economic Indicators",
    ]
    sf = _font(20)
    sy = hy + 16
    for line in sub_lines:
        draw.text((panel_x, sy), line, font=sf, fill=GRAY_LT)
        sy += 30

    # Features list
    features = [
        "300+ global stocks",
        "50 crypto assets",
        "30+ FX pairs",
        "Country economic profiles",
    ]
    ff = _font(17)
    fy = sy + 28
    for feat in features:
        draw.text((panel_x, fy), "✓  " + feat, font=ff, fill=ACCENT)
        fy += 26

    # CTA button
    btn_y = fy + 24
    btn_w, btn_h = 200, 48
    _draw_rounded_rect(draw, (panel_x, btn_y, panel_x + btn_w, btn_y + btn_h),
                       radius=10, fill=ACCENT)
    bf = _font(18, bold=True)
    btn_label = "Explore Free →"
    bw = _text_w(draw, btn_label, bf)
    draw.text((panel_x + (btn_w - bw) / 2, btn_y + 13), btn_label,
              font=bf, fill=BG)

    # URL
    uf = _font(15)
    draw.text((panel_x, btn_y + 60), "metricshour.com", font=uf, fill=GRAY)

    # ── Right panel — stat cards ───────────────────────────────────────────────
    cards_x = 516
    card_w   = 196
    card_h   = 148
    gap      = 14

    cards = [
        ("S&P 500",    "5,218",   "+0.84%",  [41,43,40,44,46,48,47,50,51,50,52], ACCENT),
        ("Bitcoin",    "$83,420", "+2.31%",  [60,58,61,65,63,68,70,69,72,74,75], ACCENT),
        ("EUR/USD",    "1.0842",  "-0.12%",  [50,51,49,50,48,47,49,48,47,48,47], (248,113,113)),
        ("Gold",       "$3,108",  "+1.15%",  [30,32,31,34,36,35,37,39,40,41,43], YELLOW),
        ("Oil (WTI)",  "$69.40",  "-0.63%",  [55,53,54,52,51,50,52,50,49,48,47], (248,113,113)),
        ("US 10Y",     "4.27%",   "+0.05%",  [40,41,42,41,43,44,43,44,45,44,45], ACCENT2),
    ]

    row, col = 0, 0
    for i, (label, val, chg, spark, acc) in enumerate(cards):
        cx = cards_x + col * (card_w + gap)
        cy = 48 + row * (card_h + gap)
        _stat_card(draw, cx, cy, card_w, card_h, label, val, chg, spark, acc)
        col += 1
        if col == 3:
            col = 0
            row += 1

    # ── Bottom strip ───────────────────────────────────────────────────────────
    strip_y = H - 42
    draw.rectangle([(0, strip_y), (W, H)], fill=(15, 20, 35))
    tags = [
        "Global Markets",  "Trade Analysis",  "Economic Data",
        "Crypto Tracker",  "FX Monitor",      "Earnings Calendar",
    ]
    tf = _font(14)
    tx = 48
    for tag in tags:
        tw = _text_w(draw, tag, tf)
        _draw_rounded_rect(draw, (tx - 8, strip_y + 8, tx + tw + 8, H - 8),
                           radius=6, fill=BORDER)
        draw.text((tx, strip_y + 11), tag, font=tf, fill=GRAY_LT)
        tx += tw + 32

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


def send_telegram(image_bytes: bytes, caption: str):
    import tempfile, requests

    token   = "8675605406:AAGl8wIqkGPbRYXXD5sidAY8ihSoZWVbC5M"
    chat_id = "7884960961"
    url     = f"https://api.telegram.org/bot{token}/sendPhoto"

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(image_bytes)
        tmp = f.name

    try:
        with open(tmp, "rb") as f:
            r = requests.post(url, data={"chat_id": chat_id, "caption": caption},
                              files={"photo": f}, timeout=30)
        if r.ok and r.json().get("ok"):
            print("Sent to Telegram ✓")
        else:
            print("Telegram error:", r.text)
    finally:
        os.unlink(tmp)


if __name__ == "__main__":
    print("Generating Reddit ad image …")
    data = generate()

    out = "/tmp/metricshour_reddit_ad.png"
    with open(out, "wb") as f:
        f.write(data)
    print(f"Saved → {out}  ({len(data)//1024} KB)")

    caption = (
        "🚀 MetricsHour Reddit Ad — 1200×628\n"
        "Ready to upload at ads.reddit.com\n"
        "Campaign: Brand Awareness / r/investing r/stocks r/MacroEconomics"
    )
    send_telegram(data, caption)
