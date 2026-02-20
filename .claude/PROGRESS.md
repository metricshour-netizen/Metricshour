# MetricsHour - Build Progress

## Completed ✓
- Memory system (PROJECT.md, CONTEXT.md, PREFERENCES.md, PROGRESS.md)
- Database schema — 9 tables (countries, country_indicators, trade_pairs, assets, prices, stock_country_revenues, users, price_alerts, feed_events)
- Alembic migrations — initial schema + currency symbol fix
- FastAPI skeleton — main.py, config.py, database.py
- Country seeder — REST Countries API → 250 countries seeded
- World Bank seeder — 88,496 indicator rows (2015-2024)
- Backend routers — health, countries (list + detail with indicators)
- Bug fix — is_nato added to countries _country_summary (NATO filter now works)
- Frontend — all 9 pages built and returning 200:
  - / (homepage with G20 grid)
  - /countries (listing with G20/G7/EU/NATO/OPEC/BRICS filters)
  - /countries/[code] (full macro detail: 6 indicator sections, exports, resources)
  - /stocks (listing skeleton)
  - /stocks/[ticker] (detail with geo revenue skeleton)
  - /trade (listing skeleton)
  - /trade/[pair] (bilateral detail, fetches real country data from API)
  - /commodities (19 instruments across Energy/Metals/Agriculture)
  - /pricing (static 4-tier page)
- Frontend components — AppNav, AppFooter, IndicatorSection
- Tailwind CSS — switched from @nuxtjs/tailwindcss to direct PostCSS config (fixed Vite 6 incompatibility)
- Asset seeder — 130 assets seeded (stocks, commodities, crypto, FX pairs)
- Backend routers — assets (list + detail + geo revenues), trade (list + pair detail)
- Frontend wired — stocks, commodities, trade pages now call real API endpoints
- User auth router — POST /api/auth/register, POST /api/auth/login, GET /api/auth/me (JWT via python-jose, Argon2 password hashing)
- Infrastructure provisioned — Aiven PostgreSQL + Upstash Redis (both connected, .env set)
- Migrations applied (alembic at head)
- Celery workers — all 4 tasks working (crypto, stocks, commodities, fx); fixed Upstash SSL (ssl_cert_reqs=CERT_NONE); tested end-to-end, prices flowing into DB
- Trade seeder — 252 rows (126 unique G20 pairs × 2 directions), 2022 WTO/IMF data, top products per pair
- EDGAR seeder — 371 rows across 24 stocks (742 total including reverse lookups), FY2023/2024 10-K data

## In Progress 🔨
- Nothing active right now

## Next Steps 📋
1. Deploy — Nginx + systemd on Hetzner, Cloudflare Pages for frontend
2. DNS — point metricshour.com and api.metricshour.com

## Known Issues 🐛
- None at this time. All core data tables populated.

## Recent Decisions
- 2026-02-20: Created memory system
- 2026-02-20: Confirmed tech stack: Nuxt 3 + FastAPI + PostgreSQL + Cloudflare
- 2026-02-20: Infrastructure: Hetzner CX23 + Aiven PostgreSQL + Upstash Redis
- 2026-02-20: Frontend pages all built; Tailwind fixed for Nuxt 3.17/Vite 6
- 2026-02-20: Asset seeder + API routes built; frontend wired to backend
- 2026-02-20: Auth router built (JWT + Argon2); DB fully seeded and connected
- 2026-02-20: Celery workers complete; Upstash SSL fix applied (broker_use_ssl + redis_backend_use_ssl with CERT_NONE)
- 2026-02-20: Trade seeder run → 252 trade_pairs rows; EDGAR seeder run → 742 stock_country_revenues rows

## Priority Order (always follow this)
1. Celery price workers — live prices
2. UN Comtrade seeder — trade_pairs data
3. SEC EDGAR seeder — stock geo revenue (core differentiator)
4. Deploy
