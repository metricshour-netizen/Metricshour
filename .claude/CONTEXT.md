# MetricsHour - Technical Context

## Infrastructure (Phase 1 - MVP)
- **Server:** Hetzner CX23 (current machine) — 3 vCPU, 4GB RAM, 80GB NVMe
- **Database:** Aiven PostgreSQL (pg-ea9f4fb-metricshour-a91a.k.aivencloud.com:16917)
- **Cache / Queue broker:** Upstash Redis — used for Celery tasks AND live feed pub/sub
- **Frontend:** Cloudflare Pages (FREE - unlimited bandwidth, 300+ edge locations)
- **Domain:** metricshour.com (~$12/year)
- **SSL:** Let's Encrypt (FREE, auto-renews every 90 days)

> Phase 2 upgrade: move to CX43 (8 vCPU, 16GB) once traffic justifies it.

## Database Options (choose one)
**Neon:**
- Free tier available (great for MVP)
- Connection string: `postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require`
- Has built-in connection pooling (PgBouncer)
- Serverless — scales to zero when idle

**Ubicloud:**
- Managed PostgreSQL, Germany region
- Internal network if co-located with Hetzner
- verify pricing at ubicloud.com

## Upstash Redis — Dual Role
1. **Celery broker** — background task queue (price ingestion, data fetching)
2. **Feed pub/sub** — live market event feed for dashboards (Redis Streams or Pub/Sub)
- FREE tier: 500K commands/month
- REST API — works from anywhere, no persistent connection needed
- Connection: `rediss://default:TOKEN@HOST:PORT`

## Tech Stack - Backend
**Framework:** FastAPI (Python 3.12)
**ASGI Server:** Uvicorn via Gunicorn (2 workers on CX23, bump to 4 on CX43)
**Reverse Proxy:** Nginx (SSL, static files, proxy to uvicorn)
**Process Manager:** systemd (keeps FastAPI + Celery running 24/7)
**Location:** Hetzner CX23 (this machine — /root/metricshour/)

## Tech Stack - Frontend
**Framework:** Nuxt 3 (Vue 3)
**Styling:** Tailwind CSS — Bloomberg Terminal dark aesthetic
**Rendering:** SSG (Static Site Generation) with SWR (Stale While Revalidate)
**Deployment:** Cloudflare Pages — auto-deploy on `git push` to main branch
**URLs:**
- Production: https://metricshour.com
- API: https://api.metricshour.com

## Database
**Engine:** PostgreSQL 15+ (Neon or Ubicloud managed)
**ORM:** SQLAlchemy 2.0+
**Migrations:** Alembic
**Backups:** Daily pg_dump at 3am UTC → Cloudflare R2 (zero egress fees)

## Background Tasks
**Queue:** Celery with Celery Beat scheduler
**Broker:** Upstash Redis
**Tasks:**
- Stock prices: Every 15 min during market hours
- Crypto prices: Every 1 min (24/7)
- FX rates: Every 15 min (weekdays)
- Commodity prices: Every 15 min during trading hours
- Feed events: Every 5 min → push to Redis Streams for live dashboard
- Country economic data: Monthly (1st day, 6am)
- Trade data: Annually (February, UN Comtrade release)
- SEO monitoring (Gemini): Daily at 6am

## AI Services
**Claude:** Insight generation for Pro subscribers
**Gemini 2.0 Flash:** SEO monitoring, content quality, competitor analysis (FREE — 2M tokens/day)

## Asset Classes
- **Stocks** — equities with geographic revenue exposure (SEC EDGAR)
- **Crypto** — BTC, ETH and major coins (24/7, CoinGecko free API)
- **Commodities** — oil, gold, metals, agriculture (80+ instruments)
- **FX** — currency pairs, tied to country macro and trade data
- **Country Macro** — GDP, inflation, interest rates, trade balances

## Data Sources
**FREE:**
- REST Countries API — 196 countries static data (no key)
- World Bank API — 58 indicators for all countries (no key)
- SEC EDGAR — stock geographic revenue (no key)
- UN Comtrade — bilateral trade flows (free registration)
- FRED API — US economic indicators 800K+ series (free key)
- IMF Data API — economic forecasts (no key)
- CoinGecko API — crypto prices (free tier)
- Central bank RSS feeds — interest rate decisions

**PAID:**
- Marketstack — stock prices ($10/mo delayed, $50/mo real-time)
- FX: exchangerate.host or Open Exchange Rates (check free tiers first)
- Note: Email FMP and Tiingo for startup pricing

## File Structure
- Development + Production: `/root/metricshour/` (same machine for now)
- Venv: `/root/metricshour/workers/venv/`
- Backend: `/root/metricshour/backend/`
- Logs: `/var/log/metricshour/`
