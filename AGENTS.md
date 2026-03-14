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
- **Cloudflare** — CDN proxy + R2 storage + Pages (builds only, no traffic)
  - `cdn.metricshour.com` = R2 custom domain

## Deploy procedure

1. Edit code locally → `git commit` → `git push origin main`
2. `ssh root@10.0.0.1`
3. `cd metricshour && git pull`
4. Restart relevant service:
   - `systemctl restart metricshour-api` (backend changes)
   - `systemctl restart metricshour-worker` (worker changes)
   - `cd frontend && npm run build && systemctl restart metricshour-frontend` (frontend)

## Image generation (og_images.py)

Two card formats generated daily and uploaded to R2:

### Landscape OG images (1200×630) — `og/{type}/{code}.png`
Used as `og:image` meta tags for social link previews.
- `_country_image()` — flag + name + GDP card with growth %
- `_stock_image()` — ticker + name + price/cap card
- `_trade_image()` — bilateral pair + trade volume card

### Portrait social cards (720×1280) — `social/{type}/{code}.png`
"Did you know?" format for reels, TikTok, Instagram Stories.
- `_social_card()` — base renderer with: category pill, headline, entity row, hero stat card (green left border), KEY FACTS bullets, source attribution, CTA button, brand bar
- `_country_social_card()` — pulls GDP + growth + inflation + population
- `_stock_social_card()` — pulls latest price + market cap + sector
- `_trade_social_card()` — pulls trade value + top products

Beat tasks:
- `og-images-daily-330am` → `generate_og_images` (1200×630 for all)
- `feed-og-images-daily-4am` → `generate_feed_og_images` (feed events)
- `social-cards-daily-445am` → `generate_social_cards` (720×1280 for all)

Fonts: DejaVu (`/usr/share/fonts/truetype/dejavu/`). Pillow is in `workers/venv/`.

## Critical rules

1. **Never reference Bloomberg as a data source** — use "World Bank", "UN Comtrade", "Yahoo Finance", etc.
2. **Never show stale data as current** — display N/A before wrong data
3. **Never edit production files directly** — always `git pull` after push
4. **Never commit .env files or API keys**
5. **Wait for confirmation before destructive DB operations**
6. **Tailwind via direct PostCSS config** — do NOT install `@nuxtjs/tailwindcss`
7. **Redis is plain TCP** (`redis://10.0.0.1:6379/0`) — no SSL on DragonflyDB

## Security posture

- UFW: 22/80/443 open; Docker ports blocked via DOCKER-USER chain (interface: `ens3`)
- DOCKER-USER uses `conntrack --ctorigdstport` for DNAT-remapped ports (8090, 8999)
- fail2ban: SSH maxretry=3, bantime=24h
- Prometheus: localhost-only (127.0.0.1:9090)
- TLS: 1.2 + 1.3 only (1.0/1.1 removed)
- Security headers: nginx only (FastAPI does NOT duplicate them)
- Celery hourly scan: `tasks.security_monitor.run_security_checks`

## Celery Beat schedule (key tasks)

| Cron | Task | Purpose |
|------|------|---------|
| Every 1 min | crypto prices | CoinGecko OHLCV |
| Every 15 min (weekdays) | stocks, FX, commodities | yfinance / ECB |
| Every 5 min | feed events | Market-moving events |
| 2:00 AM | summaries | AI page summaries (Gemini) |
| 3:00 AM | DB backup | pg_dump → R2 |
| 3:30 AM | og_images | Landscape OG cards |
| 4:15 AM | feed og_images | Feed event OG cards |
| 4:45 AM | social_cards | Portrait 9:16 social cards |
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
- R2 snapshots: countries, stocks, trade pairs (daily)
