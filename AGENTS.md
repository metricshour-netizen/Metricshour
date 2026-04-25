# AGENTS.md — MetricsHour Project Context for AI Agents

This file provides complete operational context for AI agents (Gemini, Claude, etc.) working on this repository.

## Repository layout

```
metricshour/
├── backend/          FastAPI app (Python 3.12, SQLAlchemy 2.0, Alembic)
├── frontend/         Nuxt 3 SSR (Vue 3, Tailwind CSS, TypeScript)
├── workers/          Celery tasks (Python, Redis broker)
│   ├── celery_app.py     Task registry + Beat schedule
│   └── tasks/
│       ├── og_images.py          OG (1200×630) + social cards (720×1280)
│       ├── social_content.py     AI-generated social copy (Twitter/LinkedIn/Facebook)
│       ├── summaries.py          Country/stock/trade page summaries (Gemini)
│       ├── r2_snapshots.py       Daily JSON snapshots → Cloudflare R2
│       ├── security_monitor.py   Hourly security scan + Telegram alerts
│       └── ...
└── CLAUDE.md         Session guidance for Claude Code
```

## Infrastructure (current)

- **Netcup** (10.0.0.1 / 159.195.29.136) — PRIMARY server
  - FastAPI + Gunicorn (port 8000), Nuxt SSR (port 3000)
  - PostgreSQL 17 (port 5432), DragonflyDB (port 6379)
  - Celery worker + Beat managed by systemd (`metricshour-worker`)
- **Hetzner** (10.0.0.2 / 89.167.35.114) — secondary (Docker only)
  - Umami analytics, Directus CMS (connect to Netcup Postgres via WireGuard)
- **Cloudflare** — CDN proxy + R2 storage
  - `cdn.metricshour.com` = R2 custom domain

## Deploy procedure

1. Edit code locally → `git commit` → `git push origin main`
2. `ssh root@10.0.0.1 "cd metricshour && git pull"`
3. Restart relevant service:
   - `systemctl restart metricshour-api` (backend changes)
   - `systemctl restart metricshour-worker` (worker changes)
   - `cd frontend && npm run build && systemctl restart metricshour-frontend` (frontend)

---

## HOW TO GENERATE SOCIAL CARD IMAGES ("Did you know?" reels)

**When a user asks you to generate a social card, reel, or "Did you know?" image for any country, stock, or trade pair — use these exact commands.**

### Card format
- Size: **720×1280 portrait (9:16)** — for Instagram Reels, TikTok, Stories
- Layout: category pill → "Did you know?" headline → entity row (flag + name + year) → hero stat card (green left border) → KEY FACTS bullets → source → CTA button → MetricsHour brand bar
- Stored in R2 at: `social/countries/{code}.png`, `social/stocks/{ticker}.png`, `social/trade/{exp}-{imp}.png`
- Public URL: `https://cdn.metricshour.com/social/countries/us.png`

### Generate ALL social cards (all countries + stocks + trade pairs)

```bash
source /root/metricshour/workers/venv/bin/activate
cd /root/metricshour/workers
celery -A celery_app call tasks.og_images.generate_social_cards
```

Or run as a Python script directly (faster feedback):

```bash
source /root/metricshour/workers/venv/bin/activate
cd /root/metricshour/workers
python3 -c "
import sys, os
sys.path.insert(0, '/root/metricshour/backend')
sys.path.insert(0, '/root/metricshour/workers')
from dotenv import load_dotenv
load_dotenv('/root/metricshour/backend/.env')
from tasks.og_images import generate_social_cards
result = generate_social_cards()
print(result)
"
```

### Generate ONE social card (single country/stock/trade)

```bash
source /root/metricshour/workers/venv/bin/activate
cd /root/metricshour/workers
python3 << 'EOF'
import sys, os
sys.path.insert(0, '/root/metricshour/backend')
sys.path.insert(0, '/root/metricshour/workers')
from dotenv import load_dotenv
load_dotenv('/root/metricshour/backend/.env')

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from tasks.og_images import _country_social_card, _stock_social_card, _trade_social_card, _upload

engine = create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True)

with Session(engine) as db:
    from app.models.country import Country

    # EXAMPLE: generate card for United States
    c = db.execute(select(Country).where(Country.code == 'US')).scalar_one()
    img_bytes = _country_social_card(c, db)
    _upload(f'social/countries/us.png', img_bytes)
    print('Uploaded: https://cdn.metricshour.com/social/countries/us.png')

    # For a stock (e.g. AAPL):
    # from app.models.asset import Asset
    # a = db.execute(select(Asset).where(Asset.symbol == 'AAPL')).scalar_one()
    # img_bytes = _stock_social_card(a, db)
    # _upload('social/stocks/aapl.png', img_bytes)
    # print('Uploaded: https://cdn.metricshour.com/social/stocks/aapl.png')
EOF
```

### View generated images

After generation, images are at:
- `https://cdn.metricshour.com/social/countries/{code_lowercase}.png` — e.g. `us`, `gb`, `de`, `cn`
- `https://cdn.metricshour.com/social/stocks/{ticker_lowercase}.png` — e.g. `aapl`, `msft`, `tsla`
- `https://cdn.metricshour.com/social/trade/{exp}-{imp}.png` — e.g. `us-cn`, `de-fr`

### Generate OG images (landscape 1200×630 for social link previews)

```bash
source /root/metricshour/workers/venv/bin/activate
cd /root/metricshour/workers
celery -A celery_app call tasks.og_images.generate_og_images
```

### Generate feed event images

```bash
source /root/metricshour/workers/venv/bin/activate
cd /root/metricshour/workers
celery -A celery_app call tasks.og_images.generate_feed_og_images
```

---

## Social copy generation (Twitter / LinkedIn / Facebook / Reddit)

When asked to generate social media post copy (text, not images):

```bash
source /root/metricshour/workers/venv/bin/activate
cd /root/metricshour/workers
celery -A celery_app call tasks.social_content.generate_social_drafts
```

This generates 3 drafts (country spotlight + stock exposure + trade insight) and sends them to Telegram for approval. The user taps [LinkedIn] / [Facebook] / [Reddit] / [All] buttons to publish.

---

## Critical rules

1. **Never reference Bloomberg, Yahoo Finance, or Tiingo as a data source** — use "World Bank", "UN Comtrade", "SEC EDGAR", "FRED", "ECB" (public government/institutional sources only)
2. **Never show stale data as current** — display N/A before wrong data
3. **Never edit production files directly** — always `git pull` after push
4. **Never commit .env files or API keys**
5. **Wait for confirmation before destructive DB operations**
6. **Tailwind via direct PostCSS config** — do NOT install `@nuxtjs/tailwindcss`
7. **Redis is plain TCP** (`redis://10.0.0.1:6379/0`) — no SSL on DragonflyDB
8. **Never open new firewall ports** — check with user first; all management ports are already blocked
9. **Always activate venv before Python work**: `source /root/metricshour/workers/venv/bin/activate`

## Security posture

- UFW: 22/80/443 open; Docker ports blocked via DOCKER-USER chain (interface: `ens3`)
- DOCKER-USER uses `conntrack --ctorigdstport` for DNAT-remapped ports (8090, 8999)
- fail2ban: SSH maxretry=3, bantime=24h
- Prometheus: localhost-only (127.0.0.1:9090)
- TLS: 1.2 + 1.3 only
- Security headers: nginx only (FastAPI does NOT set them)

## Celery Beat schedule (key tasks)

| Cron | Task | Purpose |
|------|------|---------|
| Every 1 min | crypto prices | CoinGecko OHLCV |
| Every 15 min (weekdays) | stocks, FX, commodities | yfinance / ECB |
| Every 5 min | feed events | Market-moving events |
| 2:00 AM | summaries | AI page summaries (Gemini) |
| 3:00 AM | DB backup | pg_dump → R2 |
| 3:30 AM | og_images | Landscape OG cards (1200×630) |
| 4:15 AM | feed og_images | Feed event OG cards |
| 4:45 AM | social_cards | Portrait 9:16 social cards (720×1280) |
| 7:00 AM | r2_snapshots | JSON snapshots → R2 |

## Environment variables (names only — values in backend/.env)

DATABASE_URL, REDIS_URL, GEMINI_API_KEY, DEEPSEEK_API_KEY, JWT_SECRET,
R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME,
CF_ACCOUNT_ID, CF_API_TOKEN, CF_CACHE_PURGE_TOKEN, CF_ZONE_ID,
TELEGRAM_BOT_TOKEN, RESEND_API_KEY, FACEBOOK_PAGE_ID, FACEBOOK_PAGE_ACCESS_TOKEN,
SENTRY_DSN, INDEXNOW_KEY, FRONTEND_URL, ALLOWED_ORIGINS

## Data coverage

- Countries: 196 (World Bank indicators 2015–2024)
- Assets: 130 (stocks, crypto, commodities, FX pairs)
- Trade pairs: 3,042 (UN Comtrade / WITS)
- Feed events: continuous ingestion
- R2 snapshots: countries, stocks, trade pairs (daily at 7am UTC)
