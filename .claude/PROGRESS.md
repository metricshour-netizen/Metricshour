# MetricsHour — Progress & Session Log

## Current Status: LIVE ✅ (as of 2026-03-14)
- Site: metricshour.com — SSR Nuxt, all pages 200
- API: api.metricshour.com — FastAPI 8 workers
- Workers: 33 Celery beat tasks running (crypto 2min, prices 15min, feed 3min, etc.)
- CDN: cdn.metricshour.com — R2 snapshots live (countries, assets, trade)
- Analytics: analytics.metricshour.com — Umami self-hosted
- CMS: cms.metricshour.com — Directus

---

## Session 2026-03-14 (continued) — Bug Sweep, Security Hardening, Search Fix

### Fixed (commits 7f46dc2 → 91c6941)
- **`Query` import missing** — countries.py + assets.py crashed API on startup (502). Fixed.
- **Search broken** — `SearchModal.vue` called `$apiFetch` which doesn't exist anywhere. Replaced with `useApi().get()`. Search now works.
- **`flag_emoji` field mismatch** — search API returns `flag`, template used `flag_emoji`. Fixed.
- **`groupings` null crash** — `c.groupings.slice()` throws if null. Added `(c.groupings ?? [])` guard.
- **`tradePartners` null crash** — filtered out entries missing `partner.code` before render.
- **`/api/auth/me` no rate limit** — added `@limiter.limit("120/minute")` (token enumeration risk).
- **`/api/feed/events/{id}` no rate limit** — added `@limiter.limit("60/minute")`.
- **`track_page_view` wrong param order** — slowapi requires `request` first; `body` was first, rate limit silently ignored. Fixed.
- **Docker secrets** — Netcup + Hetzner docker-compose.yml moved hardcoded passwords to `.env` files.
- **db.query() migration 100% complete** — all 15 remaining worker batch tasks migrated to SQLAlchemy 2.0 `select()`.
- **Worker failure resilience** — Telegram alerts on final failure, Redis DLQ (last 100), watchdog heartbeat every 10min.

### SEO audit result: 95/100 ✓
- All 22 page types: useSeoMeta, og:image, canonical, JSON-LD, h1
- Sitemap: 2,791 URLs with dynamic lastmod
- robots.txt: AI scrapers blocked

### Security posture (post-session)
- All public endpoints rate-limited ✓
- `request` param order correct on all @limiter decorators ✓
- Docker secrets in .env files ✓
- No `$apiFetch` ghost references remaining ✓

### Smoke test (all 200)
- api.metricshour.com/health, /api/countries, /api/assets, /api/search, /api/feed, /api/trade, metricshour.com

---

## Session 2026-03-14 — Social Card Templates + Distribution

### Done
- **14 PNG background templates** — generated and uploaded to R2 at `templates/{name}.png`
- **`_social_card()` rebuilt pixel-accurate** — matches Telegram template exactly:
  - Left-aligned layout, PAD=40
  - Red 64px flag square, left-aligned entity row
  - Hero card: 70px number LEFT, description RIGHT-ALIGNED in right column
  - Gray `□` outline bullets (not arrows)
  - Fixed y-positions: source=1098, CTA=1128 (partial-width pill), divider=1207, brand bar=1215
  - M logo OUTLINED box (not filled), MetricsHour + metricshour.com stacked
- **TradePair attrs fixed** — `exports_usd`, `imports_usd`, `top_export_products`
- **`generate_social_cards` Celery task** — added to Beat at 4:45 AM UTC
- **AGENTS.md updated** — full on-demand generation instructions with Python scripts
- **All 3 image tasks ran on Netcup** — social cards (250 countries, 90 stocks, 3042 trade pairs), OG landscape cards, feed event cards
- **SearchModal.vue** — recreated after lost in Netcup git reset
- **Commits**: ccce612, 43b0ec5, 5df10e4, da2f132, 3068e32, 4a772f1, 8db93d3, de27791

### R2 image counts (post-run)
- `social/countries/`: 250 files
- `social/stocks/`: 90 files
- `social/trade/`: in progress (3042 total)
- `og/countries/`, `og/stocks/`: landscape 1200×630 generated

---

## Session 2026-03-13 — Security Hardening + Bug Fixes

### Fixed
- **celery_app.py corrupted by Moltis** — module docstring embedded entire beat_schedule body. Restored from git.
- **data-quality-monitor task** — properly added to beat schedule (9am UTC daily)
- **Coolify (8090) public exposure** — Docker bypasses UFW. Fixed via DOCKER-USER iptables chain.
- **Portainer (8999, 9443) + Coolify realtime (6001, 6002)** — also exposed via Docker bypass. Fixed in docker-ufw-fix.service.
- **docker-ufw-fix.service** — systemd service runs after Docker on every boot, re-applies DOCKER-USER rules. Enabled.
- **UFW accidentally removed** during iptables-persistent install conflict. Reinstalled and reconfigured.
- **boot.mount failed** — VPS has no /boot partition. Masked the unit.
- **unattended-upgrades not running** — was blocked by boot.mount failure. Now active.
- **24 security packages outdated** — applied (libgnutls, libpam, sudo, krb5, libxml2, etc.). 0 pending.
- **CSP header missing** — added Content-Security-Policy to nginx security-headers.conf snippet.
- **Nginx rate limiting** — added zones: api_general (120r/m, burst 30), api_auth (10r/m, burst 5), api_write (30r/m). Applied to all location blocks.
- **robots.txt corrupted** by Moltis (garbage prefix). Restored from git.
- **DOCKER-USER duplicate rules** — cleaned up, now 10 clean rules.
- **Moltis max_iterations=20** — raised to 50. agent_timeout 300→600s.
- **Moltis AGENTS.md** — updated with security posture, Coolify access method, beat task list, refuse-port-open directive.
- **Junk files from Moltis** removed: celery_app.py.backup, fix_celery.py, index.vue.bak, indexOG.vue.
- **data_quality_monitor.py** (new Celery task) committed to git.

### Security posture (current)
- UFW: active, default deny, 22/80/443/51820 only public
- DOCKER-USER: blocks 8090, 8999, 9443, 6001, 6002 publicly (Contabo IP allowed for management)
- Fail2ban: SSH, 1366 total banned
- HSTS, CSP, X-Frame, X-Content, Referrer, Permissions headers all live
- SSH: pubkey only, no passwords
- Unattended-upgrades: active
- SSL cert: expires 2026-05-21 (68 days) — auto-renews via certbot

### Infrastructure confirmed healthy
- All 7 Netcup services: active
- WireGuard tunnel Netcup↔Hetzner: up (39s last handshake)
- Postgres: 15 idle + 1 active connections, healthy
- DragonflyDB: running, 890 keys, password-protected
- Celery beat: separate systemd service (metricshour-beat), enabled, running since 17:50 UTC
- Hetzner Docker: Umami 200, Directus healthy, no errors
- CDN R2: lists/countries.json, lists/assets.json, countries/us.json all 200
- Sitemap: 2791 URLs with lastmod
- SEO: all pages pass (title, og:title, og:image, canonical, JSON-LD, h1)

---

## Session 2026-03-14 (continued) — Bug Fixes from Deep Investigation

### Fixed
- **N+1 alerts query** — `_alert_dict()` no longer calls `db.get(Asset)` per alert. Batch-loads all assets in one query before loop. (`routers/alerts.py`)
- **Commodities OG image** — was pointing to generic `og/section/commodities.png`. Now uses per-commodity `og/stocks/{symbol}.png`
- **Social card redesign** — clean full-height layout (no empty gaps), green badge, dot bullets, entity-specific CTA text, 55KB/card. All 250 countries + 90 stocks + 2708 trade pairs regenerated on R2.
- **Deep investigation completed** — 30 issues identified, prioritized (see report above)

---

## Session 2026-03-14 (continued) — Resilience, Security, db.query Migration

### Done
- **Worker failure resilience** — Telegram alerts on final failure, Redis dead-letter queue (last 100), worker watchdog (10min beat, 8 critical tasks, 30min throttle). Commits: `dce2e18`
- **Meilisearch** — Confirmed running at `127.0.0.1:7700`, both indexes (countries + assets) populated, search API working
- **Rate limiting** — `intelligence.py` (spotlight 30/min, summaries/insights 60/min), `newsletter.py` (10/min), OAuth callback (10/min)
- **OG error handling** — All 6 OG endpoints return branded fallback PNG on exception instead of 500
- **OAuth TTL** — State token 600s → 3600s
- **db.query() migration** — All 8 backend routers + summaries.py (73 calls) + feed_ranker.py + og.py fully on SQLAlchemy 2.0 `select()`. Commits: `7953168`, `aa99e61`
- **Insight fallbacks** — Rule-based fallback for all 5 insight generators when Gemini+Deepseek are down. Commit: `b6e5917`
- **24 remaining db.query()** — In 15 low-priority worker batch tasks (backfill, bond_yields, stocks, etc.) — deferred

### Known open items (carry forward)
- [ ] Facebook Page Access Token — FACEBOOK_PAGE_ACCESS_TOKEN empty in .env
- [ ] Cloudflare Turnstile — not implemented on /register
- [ ] Pricing page — needs comparison table + 14-day trial CTA
- [ ] Prometheus/Grafana Telegram alerts — alertmanager not configured
- [ ] SSL cert renewal — expires 2026-05-21, auto-renew should trigger at 30 days
- [ ] Nginx rate limiting — applied to / and auth locations. Consider adding to /api/* more granularly.
