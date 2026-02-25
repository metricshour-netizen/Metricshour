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
  - Steps: Aiven console → Connection pooling → Add pool (name=pgbouncer, db=defaultdb, mode=Transaction, size=25) → paste URI
  - Code: database.py pool_size=2, max_overflow=3 (PgBouncer handles real pooling)
  - Both services need restart after .env update

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

## Completed (2026-02-21) ✓
- **Adaptive Feed + Blog CRM** — FULLY DEPLOYED
  - BlogPost model + migration 0004 (blog_posts table live)
  - /api/admin/blogs (CRUD, publish→FeedEvent, R2 cover upload)
  - /api/blog/{slug} (public, no auth, for SEO)
  - /api/feed (public, anonymous = recency+importance, authed = personalised)
  - Feed seeder: 1048 indicator_release + 40 trade_update events in DB
  - useAuth composable (login/register/logout, localStorage)
  - useApi updated (post/put/del + auto Bearer token)
  - AuthModal, AppNav (Feed link + Sign In/Out)
  - FeedCard: TikTok full-screen snap scroll style
  - /feed page: snap-y mandatory, follows sidebar on desktop
  - /blog/[slug]: public article, SEO meta
  - /admin/blog: internal CRM panel
  - Follow buttons on stock + country detail pages
  - Git commit ea16c8b pushed → CF Pages auto-deploying
  - Feed API confirmed public (no paywall) ✓
  - Feed style = TikTok snap scroll (PERMANENT PREFERENCE — do not change)

## SPRINT — 2026-02-24 (agreed with user, do not skip) ⚠️

### PHASE 1 — Critical Bug Fixes ✅ COMPLETE (2026-02-24, commit d94871a)
- [x] **Fix pg_dump path** — /usr/bin/pg_dump hardcoded (systemd overrides PATH to venv only)
- [x] **Fix DB connection exhaustion** — pool_size=2, max_overflow=3 (was 10+20=30). Services restarted, health OK.
- [x] **Fix admin/CRM link in AppNav** — v-if="user?.is_admin" guard added
- [x] **Fix ECharts blank** — flush:'post' + nextTick + chart.resize() after init (SSG ClientOnly timing fix)
- [x] **Remove "Bloomberg" from data sources** — replaced with Marketstack · CoinGecko · exchangerate.host · FRED · SEC EDGAR
- Deployed to CF Pages: https://46865986.metricshour.pages.dev

### PHASE 2 — Data & Intelligence Layer ✅ COMPLETE (2026-02-25)
- [x] **Adaptive homepage intelligence** — GET /api/intelligence/spotlight, Redis TTL=3hr, rotates every 5s on homepage. Workers: refresh_spotlight Celery task every 3hr.
- [x] **Page summaries worker** — page_summaries table (migration applied), Celery task daily at 2am, templated summaries for all countries/stocks/trade pairs. GET /api/summaries/{entity_type}/{entity_code}.
- [x] **Trade page auto-summary** — wired to /trade/[pair].vue
- [x] **Country/stock/trade summary display** — all 3 detail pages fetch and display summary (server:false, graceful catch)
- [ ] **Country summary on gov announcements** — FeedEvent of type macro_release triggers country summary refresh (deferred, not blocking launch)
- [ ] **R2 JSON snapshots** — Celery task daily writes processed JSON to R2 (deferred)

### PHASE 3 — SEO & Structured Data ✅ COMPLETE (2026-02-25, commit 861315e)
- [x] **JSON-LD BreadcrumbList on all pages** — country, stock, trade pages via computed useHead
- [x] **Canonical tags** — all dynamic pages have <link rel="canonical">
- [x] **OG images in R2** — per-page og:image/twitterImage pointing to R2 paths. Celery task generates 1200x630 Pillow images daily at 3:30am. Set NUXT_PUBLIC_R2_URL after enabling R2 public access.
- [x] **Sitemap Celery cron** — sitemap-redeploy-daily-4am triggers CF Pages redeploy
- [ ] **Heading hierarchy audit** — deferred (low priority vs launch)
- [ ] **Alt text for SVGs/flags** — deferred

### PHASE 4 — UI/UX & Navigation
- [ ] **Light/dark mode toggle** — add toggle button in AppNav. Use CSS class on <html> + localStorage. Ensure WCAG 2.1 AA contrast on both modes.
- [ ] **Feed cards fully clickable** — wrap entire FeedCard in NuxtLink/router-push to /feed/{id} or source_url. Currently only action buttons are clickable.
- [ ] **Terminal View toggle** — Markets + Stocks pages. Toggle switches to monospaced table (JetBrains Mono), 50 rows, no whitespace, sparkline mini-chart per row.
- [ ] **Share buttons** — on FeedCard + blog articles: Twitter, WhatsApp, LinkedIn share URLs. Share the specific card/article URL with og:image.
- [ ] **Feedback button** — floating button on every page. Opens modal with textarea → POST /api/feedback. Simple table in DB.
- [ ] **Internal linking audit** — every country page links to its trade pairs and relevant stocks. Every stock page links to its revenue countries. Every trade page links to both country pages. Markets grid cards link to detail pages.
- [ ] **Indices clickable** — markets page indices (DJI, SPX etc) link to /indices/[symbol] detail page with price chart.
- [ ] **Logo always links to /** — audit all pages, ensure every METRICSHOUR text/logo is a NuxtLink to /.

### PHASE 5 — CRM & Admin
- [ ] **login_events migration** — new table: uuid PK, user_id FK, ip_address, user_agent, success bool, created_at. Index on user_id + created_at.
- [ ] **last_login_at on users** — add column, update in login route on success.
- [ ] **Login handler update** — on successful login: update last_login_at + insert login_event row.
- [ ] **Admin dashboard endpoint** — GET /api/admin/stats: total users, active last 7d, logins, page views (from events). Protected by get_admin_user dependency.
- [ ] **Activity tracking** — track country page views, stock page views, trade page views via POST /api/track (fire-and-forget, store in DB). Index aggressively.
- [ ] **Admin dashboard page** — /admin/dashboard.vue (currently only /admin/blog.vue exists). Shows user stats, recent logins, top pages.
- [ ] **Umami analytics** — self-hosted (defer to server upgrade) or Umami Cloud free tier for now.

### PHASE 6 — Monitoring
- [ ] **Create /root/monitoring/** — scripts: seo_monitor.py, competitor_monitor.py, content_checker.py, news_monitor.py, feedback_analyzer.py. All use Gemini API (free).
- [ ] **Prometheus/Grafana** — defer to server upgrade (needs more RAM). Add basic /metrics endpoint to FastAPI now (prometheus-fastapi-instrumentator).
- [ ] **Telegram alerts** — hook into existing Celery failure alerting, add Telegram bot notification for critical errors.

### PHASE 7 — Pricing Page Rebuild
- [ ] **Comparison table** — MetricsHour vs Bloomberg Terminal ($24K/yr) vs Trading Economics ($200/mo) vs Yahoo Finance (Free)
- [ ] **Tagline** — "Institutional-grade intelligence. Mobile-first design. $9.99/month."
- [ ] **14-day free trial CTA** — "No credit card required"
- [ ] **Guarantee copy** — "If MetricsHour doesn't save you 30 minutes of research in your first week, email me and I'll refund you personally."

---

## Known Issues 🐛
- pg_dump FileNotFoundError — backup task failing nightly (Sentry 03fdc8a6)
- DB connection exhaustion — psycopg2.OperationalError in fx worker (Sentry 1fc95c72)
- ECharts rendering blank — need to investigate EChartLine.vue
- Admin/CRM link visible to all logged-in users (should be admin-only)
- Cloudflare Pages deploy token (CF_API_TOKEN in .env) is R2-only — lacks Pages:Edit permission
- ALLOWED_ORIGINS: includes metricshour.com, www.metricshour.com, 2c93f583.metricshour.pages.dev, localhost:3000

## Recent Decisions
- 2026-02-24: Agreed full sprint plan — bugs → data depth → SEO → UI/UX → CRM → monitoring → pricing
- 2026-02-24: R2 as processed JSON CDN confirmed (not just backup storage)
- 2026-02-24: SWR pattern confirmed: Redis → DB → push update
- 2026-02-24: Server upgrade to 64GB/16CPU planned AFTER all fixes + SEO done. Full stack decided: Postgres 17+TimescaleDB, DragonflyDB (Redis replacement), Directus CMS, Umami analytics, Prometheus+Grafana, OpenClaw. All via Docker Compose except core app (systemd). Claude drives migration via SSH.
- 2026-02-24: Bloomberg removed from data sources (public/paid APIs only)
- 2026-02-24: Feed cards must be whole-card clickable
- 2026-02-24: Light mode + WCAG 2.1 AA required
- 2026-02-24: Terminal View toggle added to roadmap
- 2026-02-24: login_events table + admin dashboard added to roadmap
- 2026-02-21: Full platform built — all 3 detail pages dynamic, homepage upgraded with live search + top stocks + trade pairs
- 2026-02-21: Frontend deployed to Cloudflare Pages (https://2c93f583.metricshour.pages.dev)
- 2026-02-21: IMF + governance seeders complete; WGI indicators added; Sentry wired

## Priority Order (always follow this)
1. Phase 1 bugs (pg_dump, DB connections, admin visibility, ECharts)
2. Phase 2 data & intelligence (adaptive cards, page summaries, R2 snapshots)
3. Phase 3 SEO (JSON-LD, heading hierarchy, canonical)
4. Phase 4 UI/UX (light mode, feed cards, terminal view, share, feedback, internal links)
5. Phase 5 CRM (login events, admin dashboard, activity tracking)
6. Phase 6 Monitoring (Prometheus, Telegram, /root/monitoring/ scripts)
7. Phase 7 Pricing page rebuild
