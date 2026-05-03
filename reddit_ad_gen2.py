"""
Reddit ad variant 2 — Trade & Macro angle (1200×628)
Bold split-screen: left = big stat, right = world heatmap-style grid + feature list.
"""
import io, os, math
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 628

# Brand colours
BG      = (10, 14, 26)
SURFACE = (17, 24, 39)
BORDER  = (31, 41, 55)
ACCENT  = (52, 211, 153)    # emerald
ACCENT2 = (99, 102, 241)    # indigo
RED     = (248, 113, 113)
YELLOW  = (251, 191, 36)
WHITE   = (255, 255, 255)
GRAY    = (107, 114, 128)
GRAY_LT = (156, 163, 175)

FONT_BASE = "/usr/share/fonts/truetype/dejavu"

def _font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(FONT_BASE, name), size)

def _tw(draw, text, font):
    return draw.textlength(text, font=font)

def _rr(draw, xy, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def generate() -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Subtle grid ───────────────────────────────────────────────────────────
    for gx in range(0, W, 60):
        draw.line([(gx, 0), (gx, H)], fill=(16, 22, 38), width=1)
    for gy in range(0, H, 60):
        draw.line([(0, gy), (W, gy)], fill=(16, 22, 38), width=1)

    # ── Vertical divider (slightly off-centre left) ───────────────────────────
    div_x = 480
    draw.rectangle([(div_x, 0), (div_x + 2, H)], fill=BORDER)

    # ═══════════════════════════════════════════════════════════════════════════
    # LEFT PANEL — bold hero stat + hook
    # ═══════════════════════════════════════════════════════════════════════════
    LX = 52

    # Eyebrow
    ey_f = _font(15)
    draw.text((LX, 52), "GLOBAL TRADE INTELLIGENCE", font=ey_f, fill=ACCENT2)

    # Giant stat
    num_f = _font(96, bold=True)
    num   = "$32T"
    draw.text((LX, 80), num, font=num_f, fill=ACCENT)

    # Label under number
    lbl_f = _font(22)
    draw.text((LX, 188), "in trade flows tracked", font=lbl_f, fill=GRAY_LT)

    # Divider line
    draw.rectangle([(LX, 228), (LX + 340, 230)], fill=BORDER)

    # Sub-headline
    sub_lines = [
        "See which countries",
        "drive every stock",
        "you own.",
    ]
    sh_f = _font(34, bold=True)
    sy = 244
    for line in sub_lines:
        draw.text((LX, sy), line, font=sh_f, fill=WHITE)
        sy += 44

    # Small proof points
    proofs = [
        "Apple: 19% China revenue",
        "ASML: 46% China revenue",
        "Tesla: 22% China revenue",
    ]
    pf = _font(17)
    py = sy + 16
    for p in proofs:
        draw.text((LX, py), "→  " + p, font=pf, fill=GRAY_LT)
        py += 26

    # CTA
    btn_y = py + 22
    _rr(draw, (LX, btn_y, LX + 220, btn_y + 50), r=10, fill=ACCENT)
    bf = _font(18, bold=True)
    bl = "See the data free →"
    bw = _tw(draw, bl, bf)
    draw.text((LX + (220 - bw) / 2, btn_y + 14), bl, font=bf, fill=BG)

    uf = _font(14)
    draw.text((LX, btn_y + 60), "metricshour.com", font=uf, fill=GRAY)

    # ═══════════════════════════════════════════════════════════════════════════
    # RIGHT PANEL — country heatmap grid + feature rows
    # ═══════════════════════════════════════════════════════════════════════════
    RX = div_x + 36

    # Section title
    rt_f = _font(15)
    draw.text((RX, 52), "COUNTRY ECONOMIC PROFILES", font=rt_f, fill=ACCENT2)

    # Heatmap-style country grid — rows of coloured tiles
    countries = [
        # (label, gdp_growth, trade_balance_colour)
        ("🇺🇸 United States", "+2.8%",  ACCENT),
        ("🇨🇳 China",          "+4.6%",  ACCENT),
        ("🇩🇪 Germany",        "+0.2%",  YELLOW),
        ("🇯🇵 Japan",          "+0.7%",  YELLOW),
        ("🇬🇧 UK",             "+1.1%",  ACCENT),
        ("🇮🇳 India",          "+6.4%",  ACCENT),
        ("🇧🇷 Brazil",         "-0.3%",  RED),
        ("🇰🇷 South Korea",    "+2.3%",  ACCENT),
        ("🇫🇷 France",         "+1.0%",  YELLOW),
        ("🇨🇦 Canada",         "+1.5%",  ACCENT),
    ]

    tile_w, tile_h, gap = 192, 40, 6
    cols = 3
    cx, cy = RX, 82

    nf  = _font(15, bold=True)
    vf2 = _font(15, bold=True)

    for i, (name, val, col) in enumerate(countries):
        row_i = i // cols
        col_i = i % cols
        tx = cx + col_i * (tile_w + gap)
        ty = cy + row_i * (tile_h + gap)
        _rr(draw, (tx, ty, tx + tile_w, ty + tile_h), r=6, fill=SURFACE, outline=BORDER, width=1)
        # coloured left bar
        draw.rectangle([(tx, ty), (tx + 4, ty + tile_h)], fill=col)
        # country name (strip emoji for font compat)
        plain_name = name.split(" ", 1)[1] if " " in name else name
        draw.text((tx + 12, ty + 12), plain_name, font=nf, fill=WHITE)
        # value right-aligned
        vw = _tw(draw, val, vf2)
        draw.text((tx + tile_w - vw - 10, ty + 12), val, font=vf2, fill=col)

    # Bottom feature pills row
    pill_y = cy + (math.ceil(len(countries) / cols)) * (tile_h + gap) + 18
    features = ["250 Countries", "700+ Stocks", "50 Crypto", "30 FX", "FRED Rates", "EDGAR Revenue"]
    pf2 = _font(14)
    px2 = RX
    row2_y = pill_y
    for feat in features:
        fw = _tw(draw, feat, pf2)
        pill_right = px2 + fw + 20
        if pill_right > W - 20:
            px2 = RX
            row2_y += 34
        _rr(draw, (px2, row2_y, px2 + fw + 20, row2_y + 28), r=6, fill=BORDER)
        draw.text((px2 + 10, row2_y + 7), feat, font=pf2, fill=GRAY_LT)
        px2 += fw + 28

    # ── Bottom brand bar ──────────────────────────────────────────────────────
    bar_y = H - 44
    draw.rectangle([(0, bar_y), (W, H)], fill=(14, 19, 33))
    brand_f = _font(17, bold=True)
    draw.text((52, bar_y + 13), "MetricsHour", font=brand_f, fill=ACCENT)
    tag_f = _font(15)
    draw.text((174, bar_y + 15), "· Real-time market & macro intelligence for everyone", font=tag_f, fill=GRAY_LT)

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
        print("Sent ✓" if r.ok and r.json().get("ok") else f"Error: {r.text}")
    finally:
        os.unlink(tmp)


if __name__ == "__main__":
    print("Generating Reddit ad variant 2 …")
    data = generate()
    out = "/tmp/metricshour_reddit_ad_v2.png"
    with open(out, "wb") as f:
        f.write(data)
    print(f"Saved → {out}  ({len(data)//1024} KB)")
    send_telegram(data, (
        "🚀 MetricsHour Reddit Ad — Variant 2 (Trade/Macro angle)\n"
        "1200×628 · Ready for ads.reddit.com\n"
        "Target: r/geopolitics r/Economics r/investing r/stocks"
    ))
