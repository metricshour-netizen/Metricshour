# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Memory System

At the start of every session, read all 4 files in `.claude/`:
- `PROJECT.md` — business model, revenue goals, competitive strategy
- `CONTEXT.md` — full tech stack and infrastructure details
- `PREFERENCES.md` — code style, git workflow, security rules
- `PROGRESS.md` — current build status and what's been completed

After reading, say **"Memory loaded ✓"** then ask what we're working on today. Update `PROGRESS.md` at the end of each session.

## Commands

All Python work uses the venv at `workers/venv/`. Activate it first:

```bash
source /root/metricshour/workers/venv/bin/activate
```

**Database migrations:**
```bash
cd /root/metricshour/backend
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "description"  # create new migration
```

**Seed database (idempotent — safe to re-run):**
```bash
cd /root/metricshour/backend
python seed.py                     # run all seeders in order
python seed.py --only countries    # REST Countries API → 196 countries
python seed.py --only world_bank   # World Bank → 60+ indicators (2015-2024)
```

**Run FastAPI backend:**
```bash
cd /root/metricshour/backend
uvicorn app.main:app --reload      # development
gunicorn app.main:app -w 2 --worker-class uvicorn.workers.UvicornWorker  # production
```

**Run Nuxt 3 frontend:**
```bash
cd /root/metricshour/frontend
npm run dev      # development server (port 3000, or 3001 if 3000 is taken)
npm run build    # build for production
npm run generate # static site generation (SSG)
```

**Run Celery workers:**
```bash
source /root/metricshour/workers/venv/bin/activate
cd /root/metricshour/workers
celery -A celery_app worker --beat --loglevel=info   # combined worker + scheduler
celery -A celery_app worker --loglevel=info          # worker only (no beat)
```

**Test Gemini connectivity:**
```bash
cd /root/metricshour/workers && python3 test_ai.py
```

No test suite exists yet. No linter is configured yet (black + ruff are planned).

## Architecture

**Data flow:**
```
Free/Paid APIs → Celery workers (background ingestion)
              → PostgreSQL (SQLAlchemy 2.0 + Alembic)
              → FastAPI (Python 3.12, Uvicorn behind Nginx)
              → Nuxt 3 frontend (SSG + SWR, Cloudflare Pages)
```

**Backend layout** (`backend/`):
- `app/main.py` — FastAPI app + CORS middleware (GET-only for now)
- `app/config.py` — Settings loaded from `.env` (DATABASE_URL, REDIS_URL, API keys)
- `app/database.py` — SQLAlchemy engine (pool size 10, pre-ping), `get_db()` dependency
- `app/models/` — 9 tables across 4 files (country.py, asset.py, user.py, base.py)
- `app/routers/` — `health.py` (GET /health), `countries.py` (GET /api/countries, /api/countries/{code}), `assets.py` (GET /api/assets, /api/assets/{ticker}), `trade.py` (GET /api/trade, /api/trade/{pair}), `auth.py` (POST /api/auth/register, POST /api/auth/login, GET /api/auth/me — JWT via python-jose, Argon2 hashing, `get_current_user` dependency for protected routes)
- `app/seeders/` — `countries.py`, `world_bank.py`, `groupings.py`
- `seed.py` — orchestrates seeders with `--only` flag support
- `migrations/versions/` — Alembic migration files

**Database schema — 9 tables:**

| Table | Purpose |
|-------|---------|
| `countries` | 196 countries, 96 columns (identity, geography, currency, groupings, credit ratings) |
| `country_indicators` | Time-series for 80+ economic indicators (GDP, inflation, governance, environment, etc.) |
| `trade_pairs` | Bilateral trade flows (UN Comtrade): exporter, importer, year, value, top products |
| `assets` | All instruments: stocks, crypto, commodities, FX pairs |
| `prices` | OHLCV price history — all asset types, multiple intervals |
| `stock_country_revenues` | **Core differentiator** — links stocks to geographic revenue % (from SEC EDGAR 10-K/10-Q) |
| `users` | Accounts with Argon2 password hashing, tier enum (free/pro/analyst/enterprise) |
| `price_alerts` | User-configured above/below price triggers |
| `feed_events` | Market-moving events (rate decisions, earnings, GDP releases, etc.) |

`stock_country_revenues` is the unique data model: it connects assets → countries via revenue percentage, enabling the core product feature — "how does US-China trade tension affect Apple stock?"

**Country grouping flags** (boolean columns on `countries`): `is_g7`, `is_g20`, `is_eu`, `is_eurozone`, `is_nato`, `is_opec`, `is_brics`, `is_asean`, `is_oecd`, `is_commonwealth`

**Frontend layout** (`frontend/`):
- Nuxt 3 (Vue 3 Composition API), Tailwind CSS (Bloomberg Terminal dark theme)
- **Tailwind is configured via direct PostCSS config — do NOT install `@nuxtjs/tailwindcss` module** (incompatible with Vite 6)
- SSG rendering with SWR; deployed on Cloudflare Pages
- `pages/` — `index.vue`, `countries/index.vue`, `countries/[code].vue`, `stocks/index.vue`, `stocks/[ticker].vue`, `trade/index.vue`, `trade/[pair].vue`, `commodities/index.vue`, `pricing/index.vue`
- `components/` — `AppNav.vue`, `AppFooter.vue`, `IndicatorSection.vue`
- `composables/useApi.ts` — API client helper

**Background tasks (Celery + Celery Beat, Upstash Redis as broker):**
- Stock prices: every 15 min during market hours
- Crypto prices: every 1 min (24/7)
- FX rates: every 15 min (weekdays)
- Feed events: every 5 min → Redis Streams for live dashboard
- Country data: monthly; Trade data: annually (UN Comtrade)

**Environment variables** — copy from `backend/.env.example`:
```
DATABASE_URL=postgresql://user:pass@host:5432/metricshour
REDIS_URL=rediss://default:TOKEN@HOST:PORT
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
MARKETSTACK_API_KEY=
JWT_SECRET=
JWT_EXPIRE_DAYS=30
JWT_ALGORITHM=HS256
```

**Deploy / process management:**
- FastAPI runs under systemd, proxied by Nginx (SSL via Let's Encrypt)
- Celery + Celery Beat also managed by systemd
- Logs: `/var/log/metricshour/`
- Production path: `/var/www/metricshour/` — never edit directly; use `git pull`
- Backup: daily `pg_dump` at 3am UTC → Cloudflare R2

## Code Style

**Python:** PEP 8, type hints on all function signatures, max line length 100 chars. Docstrings only for complex functions.

**Vue/JS:** Composition API only (never Options API), single quotes, trailing commas, `const`/`let` only.

**Comments:** Explain WHY not WHAT — only for non-obvious logic.

## Git Workflow

Semantic commit messages: `feat:`, `fix:`, `docs:`, `style:`, `refactor:`. Always run `git status` before committing. Never commit `.env` files or API keys.

## Don't Do

- Over-engineer — simple > complex always
- Add npm packages when vanilla works
- Redesign working features without asking first
- Write 500-line functions (break them up)
- Use string concatenation for SQL — always use the ORM

## Key Constraints

- **14-day launch rule** — MVP only: G20 countries, top 100 stocks, top 380 trade pairs, top 20 commodities. No scope creep.
- Never show stale data as current — display N/A before wrong data
- Show data sources on every page
- Never build features without 3 users requesting first
- Wait for confirmation before destructive operations (database drops, deletes, migrations on production)
