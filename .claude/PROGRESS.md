# MetricsHour - Build Progress

## TODO — Must Not Skip (check these every session) ⚠️
These were agreed on 2026-02-21. Do not let the user move on until all are done.

### High Priority (do before next feature)
- [ ] **Restore script** — write + test a pg_dump restore from R2. Backup is useless until tested.
- [ ] **Sentry** — add to FastAPI (one line). Zero prod error visibility right now.
- [ ] **Rate limiting** — add slowapi to /api/auth/register + /api/auth/login. Currently wide open.
- [ ] **UptimeRobot** — set up free monitor on /health endpoint. Currently blind to outages.

### Medium Priority (do this sprint)
- [ ] **Celery failure alerting** — on_failure handler → log to file or post to Discord/Slack webhook.
- [ ] **Wire KV cache into hot routes** — /api/countries and /api/assets should read from KV first (storage.py is ready, just needs integration in routers).
- [ ] **Enable PgBouncer on Aiven** — connection pooler, prevents connection exhaustion under load.

### Later (before scaling)
- [ ] **Cloudflare Turnstile** — free CAPTCHA on /register.
- [ ] **R2 public domain** — attach custom domain to bucket if ever serving public URLs.
- [ ] **Axiom** — replace /var/log/metricshour/ with searchable log explorer (free 50GB/month, CF native).

---

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
1. Deploy frontend to Cloudflare Pages (see below — needs Pages API token)
2. Add custom domain in Cloudflare Pages dashboard (metricshour.com + www)

## Pending Deploy ⚡
Frontend is built (dist/ ready). Git pushed to GitHub. CF Pages deploy needs a token with Pages:Edit permission:
- dash.cloudflare.com → Profile → API Tokens → Create Token → "Edit Cloudflare Pages" template
- Then: `CLOUDFLARE_API_TOKEN=<token> npx wrangler pages deploy dist --project-name=metricshour`
- Run from: /root/metricshour/frontend/

## Known Issues 🐛
- Cloudflare Pages deploy token (CF_API_TOKEN in .env) is R2-only — lacks Pages:Edit permission
- After next CF Pages deploy, add ALLOWED_ORIGINS update to include www.metricshour.com

## Recent Decisions
- 2026-02-21: Full platform built — all 3 detail pages dynamic, homepage upgraded with live search + top stocks + trade pairs
- 2026-02-21: Backend restarted — search endpoint (/api/search) now live
- 2026-02-21: Frontend build ready (dist/), git pushed to GitHub
- 2026-02-20: Created memory system
- 2026-02-20: Confirmed tech stack: Nuxt 3 + FastAPI + PostgreSQL + Cloudflare
- 2026-02-20: Infrastructure: Hetzner CX23 + Aiven PostgreSQL + Upstash Redis
- 2026-02-20: Frontend pages all built; Tailwind fixed for Nuxt 3.17/Vite 6
- 2026-02-20: Asset seeder + API routes built; frontend wired to backend
- 2026-02-20: Auth router built (JWT + Argon2); DB fully seeded and connected
- 2026-02-20: Celery workers complete; Upstash SSL fix applied (broker_use_ssl + redis_backend_use_ssl with CERT_NONE)
- 2026-02-20: Trade seeder run → 252 trade_pairs rows; EDGAR seeder run → 742 stock_country_revenues rows
- 2026-02-20: DNS live (api.metricshour.com → 89.167.35.114), SSL issued via Let's Encrypt, https://api.metricshour.com returning 200
- 2026-02-21: Frontend deployed to Cloudflare Pages (https://2c93f583.metricshour.pages.dev); Node upgraded to v20; wrangler deployed with CLOUDFLARE_ACCOUNT_ID env var

## Priority Order (always follow this)
1. Celery price workers — live prices
2. UN Comtrade seeder — trade_pairs data
3. SEC EDGAR seeder — stock geo revenue (core differentiator)
4. Deploy
