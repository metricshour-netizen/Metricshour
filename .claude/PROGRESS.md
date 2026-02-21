# MetricsHour - Build Progress

## TODO — Must Not Skip (check these every session) ⚠️
These were agreed on 2026-02-21. Do not let the user move on until all are done.

### High Priority (do before next feature)
- [x] **Restore script** — deploy/restore.py. Tested end-to-end: downloads from R2, psql restore, row count verification (250 countries, 103k indicators, all tables OK). Stops/starts services automatically.
- [x] **Sentry** — FastAPI (StarletteIntegration + FastApiIntegration) + Celery (CeleryIntegration). Live and active after restart 2026-02-21.
- [x] **Rate limiting** — slowapi + Upstash Redis; 5/min on /register, 10/min on /login. Redis-backed (shared across workers). Tested and confirmed 429.
- [ ] **UptimeRobot** — set up free monitor on /health endpoint. Currently blind to outages.

### Medium Priority (do this sprint)
- [x] **Celery failure alerting** — task_failure signal in celery_app.py; always logs to /var/log/metricshour/celery-failures.log; Discord embed alert if DISCORD_WEBHOOK_URL set. Covers all 5 tasks automatically. Tested.
- [x] **Wire KV cache into hot routes** — /api/countries (1hr TTL, filter-aware key) + /api/assets (5min TTL). Wired and live 2026-02-21.
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
- IMF seeder — 10,801 rows: govt debt, budget balance, current account, GDP growth, inflation, unemployment (IMF DataMapper WEO 2015-2024)
- Governance seeder — 1,836 rows: control_of_corruption_index (World Bank WGI CC.EST)
- World Bank WGI — 6 new governance indicators: rule_of_law, political_stability, government_effectiveness, regulatory_quality, voice_accountability, control_of_corruption (total WB rows: 99,485)
- Sentry — added to FastAPI (StarletteIntegration + FastApiIntegration) and Celery (CeleryIntegration); activated via SENTRY_DSN env var

## In Progress 🔨
- **Adaptive Feed + Blog CRM** — implementing 2026-02-21. Files being built:
  - ✅ BlogPost model added to backend/app/models/feed.py
  - ✅ Migration 0004 created: backend/migrations/versions/20260221_0004_blog_posts.py
  - ✅ backend/app/routers/admin.py (blog CRUD + publish + R2 cover upload + public /api/blog/{slug})
  - ✅ backend/app/main.py updated (admin + blog routers, PUT+DELETE in CORS)
  - ✅ backend/app/seeders/feed.py (price_moves, indicator_release, trade_update events)
  - ✅ backend/seed.py updated (--only feed)
  - ✅ frontend/composables/useAuth.ts (login/register/logout/restore, localStorage)
  - ✅ frontend/composables/useApi.ts (added post/put/del methods + auto Bearer token)
  - ✅ frontend/components/AuthModal.vue (login/register tabs)
  - ✅ frontend/components/AppNav.vue (Feed link + Sign In/Out)
  - ✅ frontend/components/FeedCard.vue (TikTok full-screen style)
  - ✅ frontend/pages/feed.vue (snap-y snap-mandatory scroll, loads /api/feed)
  - ✅ frontend/pages/blog/[slug].vue (public article view)
  - ✅ frontend/pages/admin/blog.vue (CRM admin panel)
  - ✅ frontend/pages/stocks/[ticker].vue (follow button added)
  - 🔨 frontend/pages/countries/[code].vue (follow button — IN PROGRESS)
  - Pending: alembic upgrade head, seed feed, restart API, deploy frontend

  IMPORTANT: Feed style = TikTok (full-screen snap scroll). User confirmed this. NOT Instagram style.

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
- ALLOWED_ORIGINS updated 2026-02-21: includes metricshour.com, www.metricshour.com, 2c93f583.metricshour.pages.dev, localhost:3000

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
- 2026-02-21: IMF + governance seeders complete; WGI indicators added; Sentry wired into FastAPI + Celery; DB now has 57 indicators per country live via API

## Priority Order (always follow this)
1. Celery price workers — live prices
2. UN Comtrade seeder — trade_pairs data
3. SEC EDGAR seeder — stock geo revenue (core differentiator)
4. Deploy
