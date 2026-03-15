# MetricsHour — Progress & Session Log

## Current Status: LIVE ✅ (as of 2026-03-15)

---

## Session 2026-03-15 — OpenClaw fixes, worker bug fixes, security audit

### OpenClaw (Contabo 158.220.92.254)
- **Model**: DeepSeek V3 (`deepseek::deepseek-chat`) primary, Gemini 2.5 Flash fallback. No Claude anywhere.
- **All 17 image templates migrated to PIL** — `_html_to_png` fully removed from all generate_* functions in `/root/openclaw/image_gen.py`. All cards now use brand-consistent PIL design.
- **Moltis timeout fixed** — `agent_timeout_secs` 120→300, `agent_max_iterations` 15→25
- **Session cleared** — fresh context, no hallucination history

### Worker bug fixes (commit 295e524)
- **`summaries.py` MultipleResultsFound** — `scalar_one_or_none()` → `scalars().first()` for all 5 Asset symbol lookups. Commodity insight batch was crashing every 3 min.
- **`og_images.py` sys.path** — fixed `/var/www/metricshour/backend` → `/root/metricshour/backend`. Trade pair social cards (2708) will generate correctly at 4:45am UTC.

### Security audit (all clean)
- UFW, docker-ufw-fix, fail2ban, Prometheus localhost-only all confirmed ✓
- All security headers present (HSTS, CSP, X-Frame DENY, nosniff) ✓
- SSL cert valid until 2026-05-21 (auto-renews at 30 days) ✓
- No exposed ports beyond 22/80/443/51820 ✓

### AI model map (confirmed from source)
| Layer | Primary | Fallback |
|-------|---------|---------|
| OpenClaw (Telegram) | deepseek-chat (V3) | gemini-2.5-flash |
| Worker summaries (bulk) | deepseek-chat | gemini-2.5-flash |
| Worker summaries (G20) | gemini-2.5-flash | deepseek-chat |
| Anthropic/Claude | NOT USED | — |

### Open items (carry forward)
- [ ] Facebook Page Access Token — still empty in .env
- [ ] Cloudflare Turnstile on /register
- [ ] Pricing page comparison table
- [ ] Prometheus/Grafana Telegram alertmanager setup
- [ ] SSL cert renewal monitor (due ~2026-04-21)

---

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

---

## Session 2026-03-15 (evening) — Security + Worker Audit + OpenClaw Content Strategy

### Security audit: CLEAN ✅
- All services active: api, worker, frontend, postgresql, dragonfly, nginx
- UFW correct, Prometheus on 127.0.0.1:9090, DragonflyDB on 127.0.0.1:6379, fail2ban 0 bans
- Beat firing correctly: price alerts/crypto/commodities/fx/feed/watchdog all running
- Redis: 3,262 keys — spotlight current (v2:2026031501, 6 items), api cache 152 keys

### Worker bugs fixed
- **`oecd_update` CardinalityViolation** — OECD API returns duplicate (country, indicator, period) rows in same batch → `ON CONFLICT DO UPDATE` fails. Fixed by deduplicating with dict keyed on `(country_id, indicator, period_date)` before INSERT. Commit `f99c1ad`, deployed via scp.
- **NOTE: Netcup git diverged** — commit `295e524` (worker fixes Mar 15 00:39) exists only on Netcup. Hetzner/origin at `f99c1ad`. Reconcile needed: push 295e524 from Netcup → origin, then merge.

### OpenClaw AGENTS.md — content strategy upgrade
- **6 reel angle templates** added: Country Macro, Trade Corridor Shock, Surprising #1, Did You Know, Stock×Country Exposure, Macro Alert
- **Source attribution fixed** — `body_lines` must show actual data source (IMF/WB/UN Comtrade/EDGAR), NOT "metricshour.com" (that's already in the image footer)
- **Decision flow**: run SQL first → find surprising fact → pick angle → pick template
- **SOUL.md rewritten** — editorial judgment, proactive behavior, real voice, no filler words

### OpenClaw vision / image support — UNRESOLVED ⚠️
- **Problem**: DeepSeek V3 rejects `image_url` (HTTP 400) — can't see photos sent to Telegram
- **Gemini tried** → rate limited immediately
- **Haiku tried** → hallucinated tool calls (said "Generated X" but tool_calls=0, nothing sent)
- **Sonnet tried** → user rejected (too expensive), disabled
- **Current state**: back on DeepSeek V3, Anthropic provider disabled (`enabled = false`)
- **Image support = broken until Gemini quota resets or paid tier used**
- **To re-enable vision**: `bash /root/openclaw/switch_model.sh gemini` (try off-peak hours)

### OpenClaw content generation — AGENTS.md reel issue
- Moltis generates only 1 image then stops / asks for confirmation instead of firing 7+
- AGENTS.md updated with explicit "minimum 7 images, no asking, no listing" rule
- Root cause was Haiku hallucinating + DeepSeek not following multi-tool instructions reliably
- **TODO next session**: test reel generation with DeepSeek — confirm it fires 7+ images on "generate reel"
- `switch_model.sh` has no `deepseek` option — add it for easy revert

### Current OpenClaw state (end of session)
- Model: `deepseek::deepseek-chat` primary, `gemini::models/gemini-2.5-flash` fallback
- Anthropic: `enabled = false`
- AGENTS.md: 10 angles, reel auto-execute rule, source attribution fixed
- SOUL.md: rewritten with editorial voice
- Vision: broken (DeepSeek can't see images)

---

## Session 2026-03-15 (late) — DeepSeek V3 fix + AGENTS.md overhaul

### DeepSeek V3 — FIXED ✅
- **Root cause confirmed**: 7 `image_url` base64 blocks in session JSONL (lines 53-57, 60, 76) caused HTTP 400 on every request since DeepSeek rejects `image_url` content type
- **Fix**: stripped all `image_url` blocks from `/root/.moltis/sessions/telegram_openclaw_7884960961.jsonl`, replaced with `[user sent a photo]` text
- **Verified working**: logs show `model="deepseek::deepseek-chat"`, responses firing, no HTTP 400
- `switch_model.sh` updated to include `deepseek` case (was missing)
- Moltis running stable on DeepSeek V3 + Gemini 2.5 Flash fallback

### AGENTS.md — complete overhaul ✅
- **606 lines** (up from 315) — full distribution playbook
- **SQL queries fixed** — all now use correct schema (`trade_value_usd`, JOINs with countries, `country_id`, `period_date`, actual indicator names like `gdp_usd`, `gdp_growth_pct`)
- **17 tool templates** — each with complete JSON example, correct field names, when-to-use guidance
- **6 viral triggers** defined — contradiction, scale shock, velocity, David vs Goliath, timely peg, reversal
- **Caption formula** added — hook + context + data point + CTA, with platform-specific variants (Twitter, Instagram, LinkedIn, WhatsApp)
- **Reel protocol hardened** — minimum 7 templates, exact execution sequence defined, no asking/listing allowed
- **Distribution priority order** — templates ranked by viral ceiling (did_you_know → stat_spotlight → macro_alert → trade_shift → ranking → commodity → export_breakdown → quote → rest)
- **TOOLS.md schema fixed** — `country_indicators`, `trade_pairs`, `stock_country_revenues` now have correct column names

### Token cost optimization
- DeepSeek V3 = $0.27/M input, $1.10/M output — primary for all ops + content
- Gemini 2.5 Flash = free tier fallback (auto-triggered when DeepSeek has issues)
- Claude (Haiku/Sonnet) = manual switch only for complex analysis — always offer revert to DeepSeek after
- Worker summaries (bulk) = DeepSeek primary, Gemini fallback
- Worker summaries (G20) = Gemini primary, DeepSeek fallback

### Open items carried forward
- [ ] Reel generation: verify OpenClaw fires 7+ images on "generate reel" command (test via Telegram)
- [ ] Vision: DeepSeek can't see photos — switch to Gemini for any image-analysis request
- [ ] Facebook Page Access Token — still empty in .env
- [ ] Cloudflare Turnstile on /register
- [ ] Prometheus alertmanager
- [ ] SSL cert expires 2026-05-21 (auto-renew at 30 days)
