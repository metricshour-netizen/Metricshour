# MetricsHour — Progress & Session Log

## Session 2026-05-03 — Feature sprint: i18n infra, screener overhaul, share cards, email alerts, comparable stocks, SEO pages ✅

### Phase 0 — Full codebase audit
- Mapped all 60 frontend pages, 10 components, 3 composables, 70+ backend endpoints
- Identified 11 feature gaps across 3 categories: partial, missing, complete
- Output structured audit report before writing any code

### Phase 1 — Foundation
- **@nuxtjs/i18n v10 installed** — `strategy: prefix_except_default`, English default (no URL change), `i18n/locales/en.json` with 82 keys
- **`useTruncate` composable** — `truncateAtSentence()` + `truncateAtWord()`, sentence-boundary safe
- **`useShareCard` composable** — html2canvas lazy-load wrapper, mobile native share sheet + desktop download fallback
- **`TranslationService`** — `backend/app/services/translation.py`: Gemini 2.0 Flash + Redis cache (`translation:{lang}:{hash}`, TTL 30d/24h/7d). Batch mode for cost efficiency.

### Phase 2 — High priority features
- **Email-only alert capture (F9)**: `email_alerts` DB table (migration 0021), `POST /api/email-alerts`, `GET /api/email-alerts/unsubscribe`, `EmailAlertModal.vue` — no auth required, dedup, rate-limited
- **ShareCard component (F2)**: `ShareCard.vue` — stock card (ticker/price/change/geo-revenue/GEO RISK badge) + country card (flag/GDP/partners). html2canvas at 2x scale. Added to stock + country page headers.
- **Comparable stocks (F3)**: Replaced "Related Stocks" with "Lower China Exposure" panel — uses `/api/screener` with sector + `china_max` + market cap 0.5x–2x range. Shows CN%/US% per peer. Links to filtered screener.

### Phase 3 — Screener
- **EU/JP/IN/EM filters (F4b)**: Backend SQL extended with `SUM(CASE WHEN c.is_eu=true)` for EU, single-code pivots for JP/IN, 32-country list for EM. 4 new filter params in `/api/screener`.
- **Range sliders (F4a)**: `RangeSlider.vue` dual-handle component (6 colour variants). All 8 filter pairs now sliders.
- **CSV export (F4d)**: `GET /api/screener/export` streaming CSV endpoint. Frontend export button with auto-dated filename.
- **5 new presets (F4e)**: Tariff-proof (CN<5%+EU<5%), Europe exposed (EU>20%), India growth (IN>10%), Domestic only (US>80%). Active preset highlighted.
- **EU% sort column**: Added to sort dropdown + results table.
- **10 screener SEO pages (F5)**: `pages/screener/[slug].vue` — each slug has unique H1, meta title (≤60c), meta desc (≤155c), intro paragraph, pre-filtered results. All 10 slugs in sitemap.

### Phase 4 — Depth features
- **Revenue history endpoint**: `GET /api/screener/revenue-history/{symbol}` — multi-year fiscal data, 6h cache.
- **Earnings impact (F7)**: Section on stock page — `(top_country_pct / 100) × abs(eps_actual) × 0.20`. Hidden if no EPS data. Labelled "Estimated — not financial advice".
- **Macro risk timeline (F8)**: ECharts line chart on stock page — China rev % by year. Renders only if ≥3 years data.

### Verified live
- `https://api.metricshour.com/api/screener` → EU/JP/IN/EM fields present ✅
- `https://api.metricshour.com/api/screener/export?china_max=5` → CSV streaming ✅
- `https://metricshour.com/screener/tariff-proof-stocks/` → 200, correct title/desc/canonical ✅
- `https://api.metricshour.com/sitemap.xml` → all 10 screener slugs present ✅
- `POST /api/email-alerts` → `{"status":"created"}` ✅
- Migration 0021 applied on Netcup ✅

### Deferred (not started)
- **F6: Why is X moving pages** — requires Celery price-change trigger (>3%), dynamic sitemap mutation, 48h page expiration. Scoped but not implemented.

---

## Session 2026-05-01 — 15 blog batch: craft, clean, schedule ✅

### 15 keyword-targeted blog posts — all drafted and scheduled

**Pipeline:** craft_blog.py (Gemini 2.5 Pro → Grok → Claude editorial) run for all 15 topics from keyword research session.

**Issue encountered:** Two `nohup` processes ran in parallel → 21 posts published with 9 duplicates.
- Fix: `DELETE /api/admin/blogs/{id}?force=true` on 9 lower-ID duplicates
- Reverted remaining 13 to draft via SQL: `UPDATE blog_posts SET status='draft' WHERE id IN (...)`
- Note: `BlogUpdate` has no `status` field — SQL is the only way to revert published→draft

**Word counts:** Gemini 2.5 Pro returned 503 errors during morning peak → Flash fallback → short drafts. Re-ran short posts with `--draft-id` flag + `--topic` context injection until all cleared 1000w.

**Fluff audit:** Regex scan across all 15 — 14 clean, 1 fixed (ID=164 "comprehensive").

**Scheduled:** 15 cron entries added to Contabo crontab, 03:00 UTC daily May 2–16. `scheduled_publish.py` self-removes each line after firing + sends Telegram notify.

| Date | ID | Title | Words |
|------|----|-------|-------|
| May 2 | 148 | Microsoft Revenue by Country | 1,091 |
| May 3 | 150 | Amazon Revenue by Country | 1,002 |
| May 4 | 152 | Google Alphabet Revenue by Country | 1,063 |
| May 5 | 154 | Meta Revenue by Country | 1,129 |
| May 6 | 156 | How the US-China Trade War Affects Your 401k | 1,164 |
| May 7 | 158 | US-Mexico Trade Relationship 2026 | 1,052 |
| May 8 | 160 | BOJ Rate Hike: Yen Headwind Stocks | 1,146 |
| May 9 | 163 | Germany vs France Economy 2026 | 1,157 |
| May 10 | 164 | India vs Vietnam Manufacturing 2026 | 1,065 |
| May 11 | 165 | Japan vs South Korea Economy 2026 | 1,381 |
| May 12 | 166 | What Is Geographic Revenue Exposure? | 1,197 |
| May 13 | 167 | 15 S&P 500 Stocks Highest Foreign Revenue | 1,227 |
| May 14 | 168 | How Currency Exchange Rates Affect Earnings | 1,246 |
| May 15 | 169 | What Is a Trade Deficit? | 1,419 |
| May 16 | 170 | Disney Revenue by Country | 1,006 |

---

## Session 2026-04-30 — Homepage UX, markets fix, about page, SEO, blog drafts ✅

### Markets page — Indices/FX/Bonds showing 0 (FIXED)
- Root cause: API `limit=500`, assets ordered by `market_cap DESC NULLS LAST`. 789 stocks with market caps filled all 500 slots; indices/FX/bonds have NULL market_cap → fell beyond position 500
- Backend: raised `limit` max 500→2000 in `assets.py`
- Frontend: `markets/index.vue` now requests `limit=2000`
- Result: index=18, fx=10, bond=3, crypto=50, etf=99, stock=789, commodity=17 all visible in tabs
- Commit: 8361ab4, deployed ✅

### Homepage copy refresh (commit 8361ab4)
- Search placeholder: "Search countries, stocks, trade pairs..." → "Search Gold, NVDA, China, Oil…"
- Secondary CTA: plain text "Get Daily Brief →" → outlined button with live emerald pulse dot + "What's Moving Today"
- Newsletter section: "Weekly Briefing" → "Daily Brief"; headline "Markets don't wait. Neither should you."; subtext updated; button "Get the daily brief"

### About page data consistency (commit 8361ab4)
- "100+ stocks" → "775+ stocks", "380+ corridors" → "1,400+ corridors", "20 commodities" → "21 commodities"
- Replaced stale "REST Countries + Marketstack" data source block with "REST Countries + Tiingo" (Tiingo IEX primary, yfinance fallback; correct update frequencies)

### SEO — conditional noindex on asset detail pages (commit 8361ab4)
- `etfs/[symbol].vue`, `crypto/[symbol].vue`, `fx/[symbol].vue` — all hardcoded `robots: 'index, follow'`
- Now: `robots: computed(() => asset.value ? 'index, follow...' : 'noindex, follow')` — matches what stocks already had
- Addresses Google Search Console soft 404 + noindex validation failures

### Feedback bubble UX (commit 8361ab4)
- Added scroll-triggered visibility: hidden on initial load, appears after 300px scroll
- Prevents overlap with hero CTAs on mobile

### Blog drafts — published
- **ID 141 (BOJ)** — FLAGGED: entire post is based on watcher parsing failure ("BOJ published corrupted file"). Awaiting user confirmation to delete.
- **ID 142 (KO)** — "Coca-Cola Q1 2026: How 60% International Revenue Creates Currency Risk". Expanded to 995w, title fixed from ALL-CAPS, slug cleaned. Published ✅ `/blog/coca-cola-q1-2026-international-revenue-currency-risk/`
- **ID 143 (FOMC)** — "Fed Holds at 3.75% as Four Members Dissent: What a Divided FOMC Means for Markets". Expanded to 1,018w, title fixed, slug cleaned. Published ✅ `/blog/fed-holds-3-75-percent-four-members-dissent-fomc-april-2026/`
- All 3 pipelines confirmed: Gemini 2.5 Pro → Grok 4.1 Fast → Claude Sonnet 4.6

### Sitemap / Search Console
- Sitemap: 2,621 URLs, auto-rebuilt daily at 07:00 UTC — no manual action needed
- GSC action needed: click "Validate Fix" on soft 404 + noindex coverage issues (fixes now deployed)

---

## Session 2026-04-25 — Source attribution purge + blog drafts fixed + Apple CEO post ✅

### Source attribution (commit 9e76e4e)
- Removed Yahoo Finance and Tiingo from ALL user-visible text across 9 frontend pages
- `stocks/[ticker].vue`, `crypto/[symbol].vue`, `nigeria/[symbol].vue` — removed "Source: Tiingo News" labels
- `nigeria/index.vue` — removed "via Yahoo Finance"
- `earnings/index.vue` — "Data: yfinance · SEC EDGAR" → "Data: SEC EDGAR"
- `china/[symbol].vue` — "Data: Tiingo" → "Data: SSE · SZSE"
- `etfs/[symbol].vue` — "Data: Tiingo · NYSE · NASDAQ" → "Data: NYSE · NASDAQ"
- `indices/[symbol].vue` — "Data: Tiingo · FRED · NYSE…" → "Data: FRED · NYSE…"
- `fx/[symbol].vue` — "Data: Tiingo · FRED · ECB" → "Data: FRED · ECB"
- `og_images.py` — "Yahoo Finance / MetricsHour" → "MetricsHour"
- AGENTS.md rule updated: Yahoo Finance and Tiingo now explicitly banned alongside Bloomberg
- Deployed + CF purged ✅

### Blog drafts — fixed and published
- **ID 136** (UnitedHealth earnings) — 919w, published. Title fixed from ALL-CAPS to "UnitedHealth Earnings: The Latin America Revenue Bet Wall Street Misses"
- **ID 137** (ECB digital euro) — 984w, published. Title fixed to "Digital Euro: ECB Sets Open Standards to Challenge Visa and Mastercard"
- **ID 138** (Apple CEO) — was 88-word stub (announcement_watcher auto-draft, NOT through pipeline). Ran craft_blog.py (Gemini→Grok→Claude) to rebuild. Category set to "markets". Published after pipeline complete.

---

## Session 2026-04-24 — SEO speed fix, FAQ schema, sitemap audit ✅

### Speed
- Removed render-blocking Google Fonts from nuxt.config.ts
- Self-hosted JetBrains Mono at `/public/fonts/jetbrains-mono.woff2` (31KB woff2 latin variable)
- @font-face in `assets/css/main.css` with font-display:swap
- Commits: e6213c1, deployed + CF purged

### Canonical / redirects
- `/register/` and `/signup/` fixed: was double-hop → `/join` → `/join/`; now single 301 → `/join/`
- All canonical tags verified clean across all page types

### China A-shares FAQ schema (94090a6)
- FAQPage JSON-LD + visible FAQ section on all 289 `/china/[symbol]/` pages
- 4 Q&As: exchange, currency, A-share definition, where to track
- Server-side rendered from stock data — Googlebot gets it in initial HTML

### Sitemap (2b4af0a)
- Audited: 2,619 URLs; all trailing slashes, lowercase, HTTPS; no private pages; all lastmod fresh
- Added blog author pages: /blog/authors/metricshour-team/ + /blog/authors/metricshour-research/

### GitHub PAT
- Old PAT expired; new PAT set on both local repo and Netcup 2026-04-24

### Footer
- Regrouped into 4 columns: Markets / Economy / Tools / Resources
- @tailwindcss/typography added (used by blog prose classes)

---

## Session 2026-04-03 — Tiingo integration complete + China A-shares full rollout ✅

### Blog audit (all 57 posts)
- 57/57 clean; 13 fixed via Gemini 2.5 Pro; no temporal fluff, no banned phrases, all 700w+

### Tiingo API (key in backend/.env, field in config.py)
- **Crypto** (`workers/tasks/crypto.py`): `GET /tiingo/crypto/prices` no startDate = real OHLC; batches 5/req across 10 calls; 40/50 coins; running `Crypto (Tiingo): upserted 40 1m + 40 1d prices` every minute
- **News** (`backend/app/routers/news.py`): `GET /api/news/{symbol}`; Redis 900s; ≤8 articles; shown on /stocks/[ticker] + /crypto/[symbol]
- **IEX intraday** (`workers/tasks/iex_intraday.py`): 1m quotes US stocks, market hours only, batch 100
- **China A-shares** (`workers/tasks/china_stocks.py`): 300 stocks daily EOD; SHG=6xxxxx, SHE=0xxxxx/3xxxxx; 220 names backfilled from Tiingo

### China A-shares pages (all live, all 200)
- `/china/index.vue` — listing (search, 50/page, CNY prices)
- `/china/[symbol].vue` — detail (price chart, news, stats, ogImage, canonical)
- `/markets/` — China tab added (all stocks w/prices when active; top 10 on All tab)
- Footer — China A-Shares link added (between Commodities and Rates)
- NOT in nav (too crowded — discoverable via markets + footer)

### SEO + CDN
- Sitemap: `/china/` + 289 `/china/{symbol}/` URLs (price-gated); total 2,577 URLs
- OG: `GET /og/china/{symbol}.png` endpoint; `og/section/china.png` on R2 CDN ✅
- Cache-Control: `/og/china/*` = 24h edge
- CF cache purged; all verified 200

### Marketstack removed — all-in on Tiingo
- `workers/tasks/stocks.py` rewritten: Tiingo IEX replaces Marketstack
- `GET /iex/?tickers=...` batch 100; returns tngoLast/open/high/low/volume
- yfinance kept as fallback; no more Marketstack references anywhere
- Log format: `Stocks: upserted X/Y prices (tiingo_iex=X, yfinance=Y)`

### Health check (2026-04-03) ✅
- All services active: api, worker, frontend
- Pages: /, /markets/, /china/, /china/600000, /stocks/, /crypto/, /rates/, /screener/, /earnings/ — all 200
- API: health OK, AAPL $255.92, BTC open/close real OHLC, 600000 = Shanghai Pudong Dev Bank, news 8 articles
- Crypto (Tiingo): upserted 42 1m + 42 1d prices — running every minute
- Sitemap: 2,577 URLs

## Session 2026-04-01 — S&P 500 expansion + Marketstack caching + new asset pages ✅

### Marketstack API key updated + smart caching
- New key: `e91123b9111c0e39fbdeedade073bc51` set in `/root/metricshour/backend/.env`
- `workers/tasks/stocks.py`: Redis day-cache (`marketstack:eod:fetched:YYYY-MM-DD`, 6h TTL) — calls Marketstack once/day not 12×/day
- Full OHLCV from Marketstack (open/high/low/close/volume via adj_* fields); yfinance fallback handles intraday
- `_upsert_prices()` now handles 3 formats: dict (Marketstack), tuple (yfinance), float (legacy)

### S&P 500 expansion: 90 → 465 active stocks
- `backend/app/seeders/assets.py`: ~375 new stocks added across all 11 GICS sectors
- `NI` symbol collision fixed: CME Nickel deactivated by `(symbol, exchange)` tuple, NiSource NYSE preserved
- `backend/app/seeders/edgar.py`: 147 new EDGAR entries (24 → 171 companies), 3,283 rows in `stock_country_revenues`
- 453/465 stocks have live price data; 12 will fill on next yfinance run

### New frontend pages (all live, all 200)
- `/crypto/` — ranked by market cap, orange accent, table with price/24h-change/market-cap/volume
- `/etfs/` — grouped by category (Broad Market/Sector/International/Fixed Income/Commodities), sky accent
- `/fx/` — grouped Majors/Emerging Markets, correct decimal precision per pair
- AppNav: Crypto, ETFs, FX links added to desktop + mobile menus
- nuxt.config.ts: cache rules added (`/crypto` 2min, `/etfs`+`/fx` 15min edge)
- stocks/index.vue: subtitle → "S&P 500"; sector filter auto-generates from data (all 11 GICS)

### AI summaries triggered for new stocks
- 308 stocks had no summary, 367 had no insights
- `generate_page_summaries` + `generate_daily_insights` triggered manually at 17:38 UTC
- Both run daily automatically (2am + 5am UTC) — all 465 stocks covered going forward

## Session 2026-03-21 — Full security hardening + Moltis aggression mode + blog from screenshots ✅

### Security hardening — ALL 3 SERVERS

**Critical bug found & fixed:**
- Netcup DOCKER-USER rule used `-i eth0` but interface is `ens3` — Coolify (8090) + Traefik dashboard (8080) were publicly exposed. Fixed to interface-agnostic rule covering 8080,8090,8999,9443,6001,6002,9100.

**Subnet blocks (permanent, persisted):**
- Netcup: `34.91.0.0/24` (Google Cloud), `45.148.10.0/24` — iptables + netfilter-persistent
- Hetzner: above + `52.168.141.0/24` (Azure), `2.57.121.0/24`, `2.57.122.0/24` — iptables + netfilter-persistent
- Contabo: same 4 subnets — UFW insert (auto-persistent)
- Attack confirmed: `34.91.0.68` = Google Cloud NL VM doing SSH credential stuffing Mar 19–21 (usernames: central, test_user, hduser, ashok). `52.168.141.47` = Azure.

**Port 3000 locked:**
- Netcup: `iptables -I INPUT -i ens3 -p tcp --dport 3000 -j DROP` — Docker bridge unaffected, Traefik still routes fine
- Hetzner: same with `-i eth0` — nginx still routes fine
- Both persisted via netfilter-persistent

**fail2ban hardened (all 3 servers):**
- `bantime 24h → 7d`, `findtime 10m → 5m`
- New `[recidive]` jail: 2nd offense within 7d = **180-day full port ban**
- Both `sshd` + `recidive` jails confirmed active on all 3

**Morning crons fixed (SSH timeout root cause):**
- `morning_pulse.py`: 9 SSH calls → 1 batched SQL. timeout 30s → 60s
- `morning_crypto.py`: 2 SSH calls → 1 combined query. timeout 30s → 60s
- Both tested live, Telegram cards sent successfully

**Moltis BOOT.md — security aggression mode:**
- R18b rewritten: cloud provider IPs (34.x Google, 52.168.x Azure) = CRITICAL, block /24 immediately. Severity scale: 1-5=LOW, 6-20=MEDIUM, 21-50=HIGH, 51+=CRITICAL
- R18c added: SUBNET AUTO-BLOCK PROTOCOL — executes iptables/ufw block without waiting when ≥3 IPs from same /24 or any cloud provider IP banned
- Incident table updated: SSH brute-force now AUTO not ASK; cloud IP = AUTO; subnet pattern = AUTO

**security_watcher.py upgraded:**
- New `classify_ips()` detects cloud provider IPs (34.x, 35.x, 52.x, 104.x, 13.x, 18.x, 20.x, 40.x) and subnet concentrations
- Cloud IP banned → CRITICAL alert + subnet to block
- ≥3 IPs from same /24 → HIGH alert + hot subnets listed
- SSH brute-force severity now scales: ≥500/h=CRITICAL, ≥200/h=HIGH
- Overall severity now includes CRITICAL tier

### Blog from Telegram screenshots (id=52, published)

**New workflow established:**
- User sends screenshots to Moltis Telegram → downloaded to `/tmp/image_for_blog.jpg` + `/tmp/image_2.jpg` on Contabo (NOT `/tmp/moltis_images/`)
- Pull to Hetzner with scp, pass to Gemini 2.5 Pro with inline_data (jpeg)
- Gemini returns JSON: title, slug, excerpt, body with [IMAGE_1]/[IMAGE_2] placeholders
- Script on Netcup: upload to R2, replace placeholders, create draft, upload cover, publish
- Admin token: `METRICSHOUR_ADMIN_TOKEN` in Contabo `/root/.config/moltis/.env`

**Blog post id=52:**
- Title: "UK Backs £746M Nigerian Port Overhaul, Cementing £8.1B Trade Tie"
- Slug: `uk-backs-746m-nigerian-port-overhaul-cementing-81b-trade-tie`
- Source: UK Export Finance + Chris Bryant MP tweets on UK-Nigeria port deal
- Cover: UKEF deal tweet card (R2 CDN) → OG image working ✓
- Body images: both embedded with figcaptions ✓
- Internal links: /trade/gb-ng, /countries/ng, /countries/gb ✓
- Live 200 ✓, all CDN assets 200 ✓

**Blog count: 52 posts total (drafts 43–50 still pending publish)**

### Current DB snapshot (2026-03-21)
- Users: 40
- Blog posts: 52 total (published: ~43, drafts: 43–50 + any others)
- Page views 7d: 3,314

## Session 2026-03-19e — Blog SEO deep fix + security_watcher critical fix + Moltis learning ✅

### Blog SEO fixes (commits 5f8fb2e + 5ea7708)
- **Blog slug SSR**: related entities + otherPosts moved from `watch()` to single `useAsyncData` — now SSR-rendered, crawlers see all internal links
- **dateModified**: now uses real `updated_at` (was always same as `datePublished`)
- **BlogPublicOut**: exposes `updated_at` field
- **Blog index**: post links now have trailing slash; added `ogImageAlt`, `twitterTitle`, `twitterDescription`
- **JSON-LD**: Article `image` fallback fixed to cdn.metricshour.com
- **`_auto_excerpt`**: now strips markdown headings/bold/italic/links before slicing
- **FeedEvent `source_url`**: now has trailing slash (`/blog/{slug}/`)
- **Sitemap**: blog `lastmod` = `max(published_at, updated_at)`; priority 0.8, changefreq weekly
- **delete_blog**: synced local Netcup patch (force param + FeedEvent cascade cleanup)

### security_watcher.py — CRITICAL BUG FIXED
- **Root cause**: script runs ON Contabo but SSH'd to itself (10.0.0.3) to check moltis/tg-bridge → "Too many authentication failures" → both always appeared DOWN → HIGH alert every single hour
- **Fix**: replaced `ssh(CONTABO, ...)` with `local()` subprocess calls for Contabo checks
- **State file**: moved from `/tmp/` (cleared on reboot) to `/root/.moltis/security_watcher_state.json`
- **Same bug in security_daily.py** — fixed identically
- **Verified**: next run shows "All clear" ✅

### Moltis improvements
- **moltis_context.json seeded**: `/root/openclaw/style_guides/moltis_context.json` — initial learnings about content tone, reel style, data sources
- **R20 added to BOOT.md**: ACTIVE LEARNING rule — Moltis must call `update_system_context` immediately when user gives performance feedback
- **update_system_context read**: now called at session start (not just on demand)
- **Moltis state verified**: 100+ active sessions, regular Telegram interactions, all 8 social slots fired correctly today

### Orphaned files on Netcup (not cleaned up)
- `workers/celery_app.py.backup`
- `workers/tasks/social_content.py.bak_20260319_1855`
- Root: `\ncount = len(...)` (Python fragment accidentally created as file)

## Session 2026-03-19d — Deep investigation + 2 critical fixes ✅

### Fix 1: Redis idempotency lock on all 8 social content slots (commit 759f676)
- **Root cause**: Celery "Restoring 4 unacknowledged messages" caused same task to run 4× concurrently → 4 duplicate posts sent to Telegram
- **Fix**: `_acquire_slot_lock(slot)` at start of each task — Redis NX key `social:lock:{slot}:{date}` TTL 2h
- All 8 tasks protected: social_drafts, market_open, evening_wrap, viral_hook, morning_reel × 2, evening_reel × 2

### Fix 2: content_log SQL bug — ALL post logging was silently failing (commit 9704045)
- **Root cause**: `::jsonb` cast on SQLAlchemy named parameter → `psycopg2.SyntaxError` on every `_log_content()` call
- **Impact**: content_log was always empty → dedup check (`recent_set`) was always empty → same country/stock/trade pair could repeat every single day
- **Fix**: Removed `::jsonb` (PostgreSQL auto-coerces json string to jsonb column)
- Both fixes deployed, worker restarted ✅

### Deep investigation findings (2026-03-19)
**Infrastructure: all green** — API ✅ Frontend ✅ DragonflyDB ✅ Moltis ✅ tg-bridge ✅
**DB counts**: 40 users, 151K price rows, 9024 feed events, 11 blog_posts
**Prices fresh**: latest timestamp 18:36 UTC same day

**Social pipeline status today**:
- 08:00 market_open ✅ / 08:30 reel ✅ / 09:00 social_drafts ✅ (3 retries) / 09:30 reel ✅
- 17:00 evening_wrap ✅ / 17:30 reel ✅ / 18:00 viral_hook ✅ / 18:30 reel ✅
- morning_social.py (Contabo cron): 4 image cards sent ✅

**Known remaining issues** (not yet fixed):
- `FACEBOOK_PAGE_ACCESS_TOKEN` still empty — no Facebook/Instagram posting possible
- Evening crypto reel hardcoded to Bitcoin (no data-driven subject selection)
- Reel confirmation gap: Celery marks success when tg-bridge returns 200, but has no feedback if video was actually generated by Moltis
- MarketStack API key invalid (falls back to yfinance — not critical)

## Session 2026-03-19c — Blog pipeline + Moltis craft_blog fully verified ✅

### Blog status (verified live)
- **6 published posts, 0 drafts**
- All 6 have: clean excerpts (no # headings), feed_event_id, entity tags
- TSLA post (id=12) published today — 1,126 words, 3 links, no banned phrases ✅

| id | title (short) | words | links | issues |
|----|---------------|-------|-------|--------|
| 12 | Tesla $21.3B China Revenue | 1,126 | 3 | none — NEW |
| 6 | Apple $72B China Revenue | 669 | 3 | pre-fix word count |
| 7 | NVIDIA China Revenue | 645 | 3 | pre-fix word count |
| 8 | US-China Tariffs S&P500 | 767 | 3 | pre-fix word count |
| 5 | Portfolio Blind Spot | 1,015 | 0 | no internal links (old) |
| 2 | Geographic Blind Spot | 1,900 | 4 | "landscape" banned word (oldest) |

Posts 6/7/8 short word count is a legacy issue (pre-fix). All new posts from craft_blog will be 900-1100+ words.

### craft_blog bug fixed (Contabo mcp_server.py)
- **Root cause**: bare `import os` in video tool branches (lines 2961/2988/3006) made Python treat `os` as a local variable throughout `call_tool` → `UnboundLocalError` when craft_blog hit `os.environ.get()` before any local import
- **Fix**: added `import os` as first line inside `craft_blog` (line 2331) and `publish_blog` (line 2255) branches
- **Verified**: direct Python test on Contabo + live Gemini Pro call succeeded

### Word count fix (mcp_server.py)
- Changed `800-1000 words` → `900-1100 words minimum` in both tool description (line 784) and prompt (line 2477)
- Verified: live run returned 1,126 words ✅

### Moltis session reset
- Old session `e947955d` had 529 messages of stale context — Moltis was hallucinating old `NameError` without calling tool
- Deleted old session from moltis.db, fresh session `d3068d73` created (533 system context messages, archived=0)
- First response on fresh session: 1,127 chars in ~19s (normal BOOT.md load time) ✅

### Moltis craft_blog confirmed working end-to-end
- tg-bridge injection → Moltis calls craft_blog → Gemini Pro writes post → admin API creates draft → publish endpoint fires → FeedEvent auto-created
- TSLA post: id=12, feed_event_id=22709, slug=teslas-213-billion-china-revenue...

## Session 2026-03-19b — Content quality + data fix ✅

### Root causes of poor content quality — ALL FIXED

**Fix 1: stock_country_revenues duplicates (wrong data source)**
- Every (asset, country) row was doubled — BABA showed 194% intl revenue, AAPL 116%, NVDA 112%
- Root cause: seeder ran twice, no unique constraint enforced
- Fix: `DELETE` 371 duplicate rows (kept latest fiscal_year per pair) — now 371 clean rows
- AAPL=58.2% intl ✓, NVDA=56% ✓, BABA=96.8% ✓
- Safeguard added: `_hook_stock_exposure` HAVING now `BETWEEN 20 AND 100` (not just `> 20`)

**Fix 2: Trade pair selection always same mega-corridors**
- Was: random from top 15 by volume (always US-China, US-EU, US-Germany)
- Fix: expanded to top 60, skip first 3, pick from index 3-35 — first run returned Vietnam-China $198B ✓

**Fix 3: AUDIENCE_PERSONA too soft**
- Added: "skip obvious posts", "only share 'I didn't know that' moments", MANDATORY counterintuitive angle

**Fix 4: craft_blog + smart_reel → Gemini 2.5 Pro (mcp_server.py)**
- craft_blog (line 2504): Flash → Pro (better long-form writing)
- smart_reel script step (line 3387): Flash → Pro, timeout 20s → 45s
- Reel script prompt: added forbidden phrases, "tell story BEHIND numbers", exact 5-frame requirement
- social_content.py stays on Flash (8×/day automated — Flash + better prompts = right tradeoff)

**Fix 5: Gemini response parsing fragile (KeyError: 'parts')**
- All callers used `["candidates"][0]["content"]["parts"][0]["text"]` — crashes when parts empty (happens on 503, thinking mode, or safety blocks)
- Fixed in: `social_content.py` `_call_gemini_with_key` + `mcp_server.py` `craft_blog` + `smart_reel` script step
- All now use safe `.get()` with fallback to empty string + explicit None return if text empty

**Fix 6: maxOutputTokens 2048 → 4096 in social_content.py**
- 5-platform prompt (Twitter+LinkedIn+Facebook+Instagram+Reddit) requires ~3000 tokens output
- 2048 limit caused JSON truncation after twitter → linkedin/facebook/instagram always empty
- Raised to 4096 — all platforms now populate on every run

**Fix 7: craft_blog + smart_reel: Pro → Flash fallback (mcp_server.py)**
- Gemini 2.5 Pro returns 503 intermittently ("high demand")
- Both tools now try Pro key1 → Pro key2 → Flash key1 → Flash key2 → DeepSeek

**Verified working (final state):**
- country_spotlight: US $910B | tw✓ li✓ fb✓ ig✓
- stock_exposure: BABA 97% intl | tw✓ li✓ fb✓ ig✓
- trade_insight: Netherlands-Germany $288B | tw✓ li✓ fb✓ ig✓
- viral_stat: BABA 88% China $114.7B ✓
- Workers active, syntax OK both servers, commits e5dc577 + 2e1918d pushed

**LIVE VERIFIED — 09:00 UTC POST 2 slot fired cleanly:**
- Quality gate caught "nuanced" on attempt 1 → auto-retried → clean output
- `ok: 1 draft sent` — US Foreign Reserves post delivered to Telegram ✓
- Total runtime: ~18s including quality gate retry

**Model routing (confirmed unchanged):**
- Moltis default: DeepSeek V3 (unchanged)
- `gemini` alias: still Gemini 2.5 Flash (unchanged)
- Pro ONLY used in: craft_blog tool + smart_reel script step (targeted, not global)

**End of session state:**
- All 8 daily slots expected to fire correctly going forward
- 09:30 REEL 2 (Moltis smart_reel) not yet observed — check Telegram for quality
- No outstanding issues

## Session 2026-03-19a — SEO canonical fix deployed ✅

### Google Search Console: "Duplicate, Google chose different canonical than user" — FIXED

**Root cause identified:**
Every `NuxtLink` across the entire site (AppNav, AppFooter, 16 page components) used
non-trailing-slash hrefs (`/countries`, `/stocks`, `/trade`, etc.) while all canonical
tags and the sitemap use trailing-slash versions (`/countries/`, `/stocks/`, etc.).
Google uses internal link volume as a canonical signal — thousands of links to `/countries`
overrode the declared canonical `/countries/`.

**Files changed (commit 7f4b18b):**
- `components/AppNav.vue` — all listing links updated to trailing slash
- `components/AppFooter.vue` — all listing links updated to trailing slash
- `pages/index.vue`, `countries/[code].vue`, `stocks/[ticker].vue`, `trade/[pair].vue`,
  `commodities/[symbol].vue`, `indices/[symbol].vue`, `compare/[slug].vue`,
  `watchlist/index.vue`, `alerts/index.vue`, `blog/[slug].vue`, `feed/[id].vue`,
  `join.vue`, `login.vue`, `error.vue` — all internal links fixed
- `pages/join.vue` — added missing `canonical` tag (`/join/`)
- `pages/markets/index.vue` — `ogUrl` and JSON-LD `url` aligned with canonical `/markets/`
- `pages/auth/callback.vue` — added `robots: noindex, nofollow`

**Verified in production:**
- SSR HTML on homepage shows `/countries/`, `/stocks/`, `/markets/`, `/feed/`, `/join/`,
  `/login/`, `/trade/`, `/commodities/` — all trailing slash ✓
- `/countries` 301 → `/countries/` still working (trailing-slash middleware intact) ✓
- Cloudflare cache purged post-deploy ✓

**Next step:** GSC will clear the issue after Google recrawls (days–weeks).
Use GSC URL Inspection on affected pages and request re-indexing to accelerate.

## Session 2026-03-18h — Social pipeline bugs fixed + Moltis hardened ✅

### 3 bugs causing 0/8 social tasks to fail today — ALL FIXED

**Bug 1: smart_reel NameError (Contabo mcp_server.py)**
- Root cause: new AI script step used `os.environ.get()` but smart_reel imports os as `_os`
- Fix: `os.environ` → `_os.environ` on both GEMINI_API_KEY lines (~line 3335)

**Bug 2: smart_reel Gemini JSON truncated (Contabo mcp_server.py)**
- Root cause: `maxOutputTokens: 1024` — Gemini filled up before closing JSON brackets
- Fix: bumped to `2048` at line 3360
- Verified end-to-end with real GEMINI_API_KEY: Gemini returns valid parsed JSON ✓

**Bug 3: POST 1 SQL error (Netcup social_content.py)**
- Root cause: `_hook_market_movers` used `p.symbol` — column doesn't exist on prices table
- Fix: already in commit `9dea4d4` (pushed 08:18 UTC, 8 min after the task failed)
- Worker restarted 18:13 UTC — tomorrow 08:00 will use fixed code ✓

### Moltis hallucination: "still broken" without calling tool
- Moltis reported "still broken" 3x without tool_calls=0 — just parroting old context
- Added BOOT.md R7: "Never assume a tool is broken from prior context — always call it"
- Added BOOT.md R8: "Report EXACT error text verbatim, never paraphrase"

### BOOT.md SQL patterns corrected (critical)
- `p.change_pct` → doesn't exist; must compute: `(p.close-p.open)/NULLIF(p.open,0)*100`
- `ci.indicator_code` → column is `ci.indicator`; `c.iso2` → column is `c.code`
- All 3 SQL examples now use correct column names (prevents Moltis writing broken queries)
- BOOT.md now 311 lines, Moltis restarted to load updates

### Verified state (end of session)
- Contabo: moltis ✓ tg-bridge ✓ mcp_server.py syntax OK ✓
- Netcup: no p.symbol in social_content.py ✓ worker last restarted 18:13 UTC ✓
- Tomorrow's 8 slots should all fire: POST1 ✓ REEL1-4 ✓ POST2-4 already worked ✓

## Session 2026-03-18g — Services verified + blog feed fix ✅

### All services confirmed active
- Netcup: metricshour-api, metricshour-worker, metricshour-beat, metricshour-frontend
- Contabo: moltis, tg-bridge
- API health: ok

### Blog posts missing from feed — FIXED
- Root cause: posts id=5,6,7,8 were inserted via raw SQL, bypassing /api/admin/blogs/{id}/publish
- That endpoint auto-creates a FeedEvent row — raw SQL inserts skip it → posts invisible in feed
- Fix: inserted feed_events rows 22078–22081 directly (CAST AS jsonb for related_*_ids)
- Set feed_event_id on each blog_post row
- Deleted stale test feed events (id=21232 "Test Blog", id=22040 "test post from contabo")
- Verified: /api/feed now returns 4 blog events with correct slugs + entity IDs

### Content quality changes verified — 36/36 checks passed
- social_content.py: all helpers, all hooks, all 4 new viral types confirmed on Netcup
- mcp_server.py: craft_blog prompt, smart_reel script step confirmed on Contabo
- BOOT.md: reel quality section confirmed (296 lines)

## Session 2026-03-18f — Content quality overhaul ✅

### social_content.py (Netcup workers) — commit 5ceb5b4
- Added `AUDIENCE_PERSONA`: retail investor 30-45, share-worthy tone, injected into every prompt
- Added `_fetch_news_context()`: Google News RSS headlines injected per-prompt (live context)
- Added `_compute_angle()`: flags multi-year highs/lows, YoY deltas, consecutive trends
- Added `_pick_best_country_indicator()`: picks G20 country with biggest YoY indicator change (vs random)
- `_hook_stock_exposure`: now picks most-moved stock this week with intl exposure (vs random)
- `_hook_trade_insight`: news context injected, instructed to frame live geopolitical angle
- market_movers + day_wrap: instructed to explain WHY, not just list numbers
- 4 new viral stat types: `china_exposure`, `big_price_mover`, `commodity_extreme`, `debt_yoy_surge`

### smart_reel (Contabo mcp_server.py)
- Added AI script-writing step: Gemini writes narrative (hook→facts→implication) from live_data before building slides
- `title_hook` from script replaces generic title card subtitle
- Per-frame AI voiceovers override auto-generated fallbacks
- AI Telegram caption used instead of generic "{style} · MetricsHour"

### craft_blog prompt (Contabo mcp_server.py)
- Lead with surprising/counterintuitive fact
- Connect data to NOW (tariffs, rate cycles, elections)
- Concrete "what to watch" with thresholds instead of generic forward-looking paragraph
- Added audience persona and banned word "nuanced"

### Moltis BOOT.md (Contabo)
- Added REEL QUALITY — SCRIPT-FIRST PROTOCOL section (296 lines total)
- Teaches manual reel creation: data → script → matched slides → create_voiced_reel

## Session 2026-03-18e — Final verification ✅
- craft_blog: 14/14 checks passed (verified via local Python script reading mcp_server.py from Contabo)
- publish_blog: `import re,` + entity extraction confirmed
- Live API confirmed: apple post → asset_ids=[1], country_ids=[189]; tariffs post → 7 assets, 1 country
- Sitemap: 2794 URLs (blog index + 5 posts)
- Confirmed non-bugs: R2 DYNAMIC (expected), duplicate Cache-Control (CF Free), CF Pages builds (no traffic)

## Session 2026-03-18d — Moltis craft_blog fix + blog entity linking ✅

### Moltis craft_blog — FULLY FIXED (Contabo /root/openclaw/mcp_server.py)
- Root cause: `_run_psql` was called 5× but never defined anywhere → silent NameError → all DB queries failed → AI wrote generic posts with no real data
- Also: DB query column names were all wrong (c.iso2, ci.indicator_code, p.change_pct — none exist)
- Fix: replaced entire data-fetching block with calls to MetricsHour public API:
  - `stock:SYM` → GET /api/assets/{sym} → real price + geographic revenue breakdown
  - `country:CC` → GET /api/countries/{code} → indicators, credit rating, exposed stocks
  - `trade:EXP-IMP` → GET /api/trade?exporter=X&importer=Y → bilateral trade values
  - `commodity:NAME` → GET /api/assets?asset_type=commodity
- Added entity extraction: regex scan of generated content for `/stocks/XX` and `/countries/xx` → API lookup → set related_asset_ids + related_country_ids
- Added excerpt auto-extraction from first non-heading paragraph
- payload now includes: related_asset_ids, related_country_ids, excerpt

### publish_blog — also patched
- Was not setting related_asset_ids / related_country_ids at all
- Now: same regex extraction from content before POSTing
- Added `import re,` to handler

### Blog entity backfill
- All 5 existing posts updated with related_asset_ids + related_country_ids from their body content
- Key IDs: AAPL=1, NVDA=2, TSLA=7, ASML=77, PG=44, TM=78; US=144, CN=189, TW=86, DE=47

### Frontend: "Explore in MetricsHour" section on blog posts
- Added after share buttons, before footer in pages/blog/[slug].vue
- Shows related stocks (emerald chips) + countries (blue chips) from related_* IDs
- Fetches /api/assets?limit=200 and /api/countries?limit=300 client-side, filters by ID
- Commit: 3b81614

### Verified live
- Public API returns related_asset_ids + related_country_ids correctly ✓
- Sitemap: 2794 URLs, 6 blog (index + 5 posts) ✓
- Moltis active ✓
- craft_blog syntax valid ✓ (ast.parse passes)
- test-blog deleted ✓

## Session 2026-03-18c — Blog content push ✅

### Blog cleanup + 3 new posts published
- Deleted junk "test-blog" (id=3, 25 chars, published) — removed from sitemap
- Published draft id=5 "Why Most Stock Portfolios Hide a $2 Trillion Geographic Blind Spot"
- Wrote and published 3 new data-driven posts using real DB data (EDGAR + Comtrade):
  1. `apple-china-revenue-geographic-exposure-aapl-investors` — AAPL 18.9% China ($72.4B), full geographic breakdown, tariff transmission, 2025 context
  2. `nvidia-china-revenue-chip-export-controls-nvda` — NVDA 17% China ($10.4B), FY2024 breakdown, export control timeline, Huawei Ascend wildcard
  3. `us-china-tariffs-sp500-stocks-geographic-revenue-exposure` — China exposure table (BABA/TSLA/AAPL/NVDA/PG/ASML/TM/NVO), tariff transmission mechanisms, portfolio strategy
- Blog now: 5 published posts (was 3 including junk, now 5 real)
- CF cache purged; 4 new URLs submitted to IndexNow

### Content strategy — next 10 posts (priority order)
1. "Tesla's 22% China Revenue: Gigafactory Shanghai and the Geopolitical Bet" (TSLA $21.3B)
2. "ASML: The Semiconductor Equipment Maker Caught Between Two Superpowers" (10% CN)
3. "Procter & Gamble in China: $8.2 Billion at Stake in an Unlikely Trade War Target"
4. "Germany GDP Slowdown 2025: How It Affects US Stocks with European Revenue"
5. "Japan's Interest Rate Hike: Impact on US Stocks with Japanese Revenue Exposure"
6. "India's Rising Economy: The Next Frontier for S&P 500 Revenue Growth"
7. "How to Build a Trade-War-Resilient Portfolio Using Geographic Revenue Data"
8. "The Complete Guide to Geographic Revenue Risk for Individual Investors"
9. "Oil Price Volatility 2025: Which Companies Have Middle East Revenue Exposure"
10. "US-EU Trade Tensions: Which US Stocks Have the Most European Revenue at Risk"

## Session 2026-03-18b — SEO/caching/edge audit + Moltis blog fix ✅

### Moltis craft_blog — FIXED (Contabo /root/openclaw/mcp_server.py)
- Bug: `craft_blog` handler imported `requests` and `json` but NOT `os`, then called `os.environ.get(...)` → `NameError: name 'os' is not defined`
- Fix: added `import os` to the `elif name == "craft_blog":` imports line
- Moltis restarted — blog publishing now works

### social_content.py — SQL query fix (root cause confirmed)
- 08:00 `generate_market_open_drafts` failed: `psycopg2.errors.UndefinedColumn: column p.symbol does not exist`
- `prices` table has no `symbol` column; query must JOIN via `asset_id` not `a.symbol = p.symbol`
- Added `DISTINCT ON (a.id) ORDER BY a.id, p.timestamp DESC` to prevent duplicate rows per asset
- Same fix applied to both `_hook_market_movers` and `_hook_day_wrap`
- Reel trigger message upgraded: adds UTC timestamp + explicit tool call instruction
- Committed: `4c8ce5d`

### Sitemap investigation — 2791 URLs
- Breakdown: trade 2232, countries 251, compare 172, stocks 91, indices 18, commodities 17, blog 3
- `sitemap.xml` generates dynamically from DB (FastAPI); `robots.txt` both served from `api.metricshour.com`
- `metricshour.com/sitemap.xml` → 301 → `api.metricshour.com/sitemap.xml` (Google follows this fine)

### Bug: Nginx `no-store, no-cache` poisoning sitemap — FIXED
- Nginx for `api.metricshour.com location /` added `Cache-Control: no-store, no-cache, no-transform` to ALL responses
- FastAPI sets `s-maxage=3600` for sitemap but Nginx overrode it → CF showed `DYNAMIC` on every Googlebot request
- Fix: added `location = /sitemap.xml` and `location = /robots.txt` exact-match blocks BEFORE `location /`
  - These blocks have no `add_header Cache-Control` → FastAPI headers pass through clean
  - `location /` retains `no-store, no-transform` for API data endpoints
- Nginx reloaded on Hetzner (10.0.0.2)

### Bug: CF cache rule `browser_ttl=0, override_origin` — FIXED
- CF injected a second `Cache-Control: public, max-age=0, s-maxage=60` header alongside Nuxt's header
- This killed browser caching (browsers always revalidated) and created ambiguous duplicate headers
- Root cause: CF Cache Rule `http_request_cache_settings` had `browser_ttl: {default: 0, mode: override_origin}`
- Fix via CF API: updated both `browser_ttl` and `edge_ttl` to `mode: respect_origin`
  - CF now defers to Nuxt's `max-age=300` (5min browser) and `s-maxage=1800/3600` (edge)
- Note: CF still adds `max-age=0, s-maxage=60` second header on Free plan (CF behaviour for edge-managed HTML) — CF IS caching (verified `cf-cache-status: HIT`)

### Bug: Missing `/compare/**` routeRule — FIXED
- 172 compare pages had no `Cache-Control` header → CF defaulted to 60s edge, 0 browser cache
- Fix: added `'/compare/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } }` to `nuxt.config.ts`
- Frontend rebuilt + deployed on Netcup; CF cache purged
- Committed: `28e0aea`

### New CF cache rule: sitemap + robots caching
- `api.metricshour.com` had no CF cache rule → treated as DYNAMIC even with `s-maxage=3600`
- Added rule: `http.host eq "api.metricshour.com" and (path eq "/sitemap.xml" or path eq "/robots.txt")`
  - `edge_ttl: 3600, override_origin` + `browser_ttl: 0, override_origin` (browsers shouldn't cache sitemap)
- Verified: first hit MISS, second hit HIT ✅

### CF Cache Rules final state (3 rules total)
1. `metricshour.com` HTML pages: `cache: true, browser_ttl: respect_origin, edge_ttl: respect_origin`
2. `cdn.metricshour.com` R2 CDN: `cache: true, browser_ttl: 3600 override, edge_ttl: 3600 override`
3. `api.metricshour.com` sitemap+robots: `cache: true, browser_ttl: 0 override, edge_ttl: 3600 override`

### R2 status — healthy, DYNAMIC expected
- R2 custom domain (`cdn.metricshour.com`) always shows `cf-cache-status: DYNAMIC`
- This is expected: R2 IS on CF infrastructure, not a separate origin to CDN-cache
- Browser `max-age` still applies (86400 for OG images, 3600 for snapshots)
- Object counts: snapshots/countries/ 750, snapshots/trade/ 5416, og/countries/ 250, og/stocks/ 90, og/trade/ 2708, og/feed/ 10741

### All commits today
- `9dea4d4` fix: social_content SQL DISTINCT ON + p.symbol → a.symbol (EARLIER SESSION)
- `28e0aea` fix: /compare/** routeRule (Hetzner → pushed to origin)
- `56a93c9` fix: reel trigger tool call message (Netcup local, rebased)
- `f082332` fix: expires=3600 social beat tasks (Netcup local, rebased)
- `4c8ce5d` fix: social_content SQL + reel trigger UTC timestamp (final push)

## Session 2026-03-18 — Full system audit + Celery Beat fix ✅

### Celery Beat crash-loop fixed (CRITICAL)
- Beat was crash-looping since 12:50 UTC (46 min down) — restart counter hit 211+
- Error: `No such option: --timezone` — Celery 5.6.2 dropped this CLI flag
- Fix: removed `--timezone=UTC` from ExecStart in `/etc/systemd/system/metricshour-beat.service`
- Timezone already set correctly in `celery_app.py` line 105: `timezone='UTC'`
- Beat restored at 13:36 UTC, immediately started firing all due tasks

### System audit findings (all 3 servers)
- Netcup: ✅ healthy — all services up, disk 2%, RAM 4.8/31G
- Hetzner: ⚠️ RAM 773M free / 3.7G, NO swap — monitor, consider swapfile
- Contabo: ✅ Moltis + tg-bridge running clean
- Gemini model causes smart_reel failures (confirmed 09:30 reel today — tool_turns=0)
- fail2ban: 116 banned (Netcup), 135 banned (Hetzner)

### Moltis model behavior confirmed
- On Gemini: smart_reel fails (chatted instead of calling MCP tool, tool_turns=0)
- On DeepSeek: fires tool immediately, tool_turns>0, reels succeed
- Other tasks (monitoring, chat, server checks) work fine on both models

## Session 2026-03-17f — Moltis smart_reel full audit & fix ✅

### All 6 reel types now verified working (frame-inspected, sent to Telegram)
market_recap, crypto_update, commodities, country_deep_dive, trade_spotlight, stock_analysis

### Bugs found and fixed (all in `/root/openclaw/mcp_server.py`)

**Bug 1: Duplicate assets in market_recap / crypto / commodities**
- Queries used `WHERE timestamp >= NOW() - INTERVAL '3 days'` with no deduplication
- Same asset appeared multiple times (e.g. CT/Cotton twice with different day prices)
- Fix: wrapped all three queries in `WITH latest AS (SELECT DISTINCT ON (a.id) ... ORDER BY a.id, p.timestamp DESC)` subquery

**Bug 2: Trade products showing raw JSON**
- `tp.top_export_products` stored as JSON array — was rendering as `[{"name":"petroleum",...}]`
- Fix: replaced with `jsonb_array_elements` subquery → now renders as `petroleum products, machinery, aircraft`

**Bug 3: Trade value `$0.65T` instead of `$649B`**
- Threshold `val_f > 1e11` (>$100B → show as T) was wrong — $649B was formatting as `$0.65T`
- Fix: threshold → `1e12` (>$1T → show as T); also switched to `.0f` for cleaner B formatting

**Bug 4: `scr.year` column doesn't exist → AAPL gets zero geographic revenue cards**
- Column is `fiscal_year` not `year` — psql error swallowed by `2>/dev/null`
- Fix: `scr.year` → `scr.fiscal_year`

**Bug 5: Duplicate country rows in geographic revenue (AAPL showing US twice, CN twice)**
- DB has duplicate entries per country per ticker
- Fix: `DISTINCT ON (scr.country_id) ... ORDER BY scr.country_id, scr.fiscal_year DESC` + pipe through `sort -k3 -rn | head -8`

### Verified ✅ (all frame-inspected)
- AAPL: $254.53 +0.57% → Revenue 38.1% US, 18.9% China, 6.3% Japan, 4.9% UK, 4.9% Germany
- US-CN trade: $649B (2023) · petroleum, machinery, aircraft, electronics, vehicles
- GB country: GDP Growth 1.1%, GDP $3.69T, Inflation 3.3%, Unemployment 4.7%
- market_recap: unique assets only, correct prices
- All 6 reel styles: no header garbage cards, no duplicate rows, correct value formatting

---

## Session 2026-03-17e — Moltis reel data bug fixes ✅

### Root causes found and fixed (all in `/root/openclaw/mcp_server.py`)

**Bug 1: `c.iso2` → `c.code` (schema mismatch)**
- All country, trade, and stock geo revenue queries used `c.iso2` but the column is `c.code`
- Queries failed silently (psql error swallowed by `2>/dev/null`) → `live_data` contained only the column header line
- Affected: `country_deep_dive`, `macro_alert`, `trade_spotlight`, `stock_analysis`

**Bug 2: `tp.top_products` → `tp.top_export_products` (wrong column name)**
- Trade pair query used non-existent column name

**Bug 3: Header row parsed as data card ("value" showing on screen)**
- `get_reel_data` wraps results as `"COUNTRY DATA GB (indicator|value|year):\n..."` — header contains `|`
- Parser read header line as a data row → rendered card with value=**"value"**, label="Country Data Gb (Indicator"
- Fix for `country_deep_dive`: added `if ind_raw not in IND_MAP: continue`
- Fix for `trade_spotlight`: changed `except Exception: val_fmt = cols[2]` → `except Exception: continue`

**Bug 4: market_recap corrupt data (carried from prior session)**
- Added `AND a.asset_type != 'index'` + `AND ABS(change) < 0.5` to market_recap query
- Added `if abs(chg_f) > 50: continue` sanity check in stat card parser

### Verified ✅
- country:GB query returns: GDP Growth 1.1%, GDP $3.69T, Inflation 3.3%, Unemployment 4.7% (2024/2025)
- country:US query returns: GDP Growth 2.8%, GDP $28.75T, Inflation 2.9%, Unemployment 4.2%
- trade:US-CN returns: $649B (2023), top products petroleum/machinery/aircraft
- market_recap: SSNLF (60.62%) correctly excluded by filter
- Frame inspection confirmed: no more "value" garbage cards on GB reel
- All files pass `ast.parse()` ✅, moltis active ✅

---

## Session 2026-03-17d — tg-bridge multi-turn fix + reel delivery fix ✅

### tg-bridge multi-turn collection — FIXED ✅
- **Root cause:** `inject_to_moltis` returned `True` on first `thinking_done` with text. Model says "Creating reels..." → bridge exits → smart_reel runs silently → user sees intro text + silent videos with no context.
- **Fix:** `/root/openclaw/telegram_webhook_bridge.py` — `thinking_done` with text now sends the text but CONTINUES listening. Exits only on idle timeout (8s silence after tool turns complete). Final summary after tool calls is now delivered.
- `reply_chunks` reset between turns so multi-turn text accumulates correctly.

### BOOT.md strict tool-first rule — ADDED ✅
- Rule 1: "Call tools FIRST. Zero text before a tool call." with Good/Wrong examples
- Topic→style reference table with example hooks
- Hook quality rules: factual, punchy, < 60 chars, no fabricated numbers
- Tool usage guide: which tool for which job

### Verification ✅
- Both files pass `ast.parse()` syntax check
- `moltis` + `tg-bridge` active after restart
- Webhook registered
- Session cleared (DeepSeek default, message_count=0)
- Confirmed reel file sizes post-patch: market_recap 1.9MB (was 0.4MB), trade_spotlight 1.0MB (was 0.5MB) — ElevenLabs voice confirmed active

---

## Session 2026-03-17c — Moltis reel quality overhaul ✅

### Reel quality — FIXED (all styles now produce real data cards + voice + captions)

**Root causes found and fixed:**
1. `market_recap` data has 5 cols (sym|name|**type**|close|chg%) — old parser read col[2] (type) as price → no data cards generated. Fixed: now reads col[3] for price, col[4] for change.
2. `trade_spotlight` and `stock_analysis` had **zero card-generation code** — both styles produced only title + outro with no data. Added full parsers for both.
3. Voiceover was `""` for all data frames → ElevenLabs API error (empty string). Fixed: every frame now has contextual voice text ("Bitcoin is surging — plus 3.2% in the last 24 hours").
4. `create_voiced_reel` now generates ffmpeg silence for any frame that has empty voiceover text (no API error).
5. Captions and subcaptions are now passed per-frame into `moviepy_frames` dict so they're burned onto the video.

**Files changed:**
- `/root/openclaw/mcp_server.py` — smart_reel handler: replaced stat card parsing with style-specific parsers + `frame_meta` list (caption, subcap, voiceover, accent per data frame); replaced voiceover loop with rich per-frame metadata builder
- `/root/openclaw/image_gen.py` — `create_voiced_reel`: non-empty voiceover texts only go to ElevenLabs; empty frames get ffmpeg silence
- `/root/.moltis/BOOT.md` — production quality rules, hook quality guide, topic→style table, tool usage guide

**Verified:**
- Both files pass `ast.parse()` syntax check ✅
- `moltis` + `tg-bridge` services active ✅
- Session cleared (4 lines, message_count=0, DeepSeek default) ✅

**Styles now fully supported with data cards:**
- `market_recap` → top movers (5-col format fixed)
- `crypto_update` → crypto prices (4-col)
- `commodities` → commodity prices / specific symbol (4-col)
- `country_deep_dive` → GDP, inflation, unemployment, growth (3-col)
- `trade_spotlight` → bilateral trade value + top products (5-col) ← was broken
- `stock_analysis` → price + geographic revenue breakdown (5-col + 4-col) ← was broken

---

## Session 2026-03-17b — Moltis reliability + video production + ElevenLabs voice ✅

### Bot reliability — FIXED ✅
- **Root cause:** 64 MCP tool schemas sent ~25K tokens to DeepSeek → intermittent empty responses
- **Fix:** Added `EXPOSED_TOOLS` filter in `/root/openclaw/mcp_server.py` — only 18 tools exposed to LLM (all 64 still callable). Token count dropped from 25K → 18.8K → DeepSeek reliable
- DeepSeek set as permanent default in `moltis.toml` + session DB (Gemini was failing at 25K tokens)
- tg-bridge v2 already in place: persistent WS, 30s keepalive, reconnects automatically

### Video production — FIXED ✅
- **Bug 1:** `@font-face{font-family:...}` unescaped inside Python f-strings → `NameError: name 'font'`. Fixed 20 occurrences in `/root/openclaw/image_gen.py` (→ `@font-face{{font-family:...}}`)
- **Bug 2:** Header row `symbol|name|price|24h_chg%` from `get_reel_data` was parsed as a data row → `float("price")` crash. Fixed with `try: price_f = float(price) except: continue`
- **Bug 3:** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` missing from `/root/.config/moltis/.env` — were only in tg-bridge.service. Added to moltis env. Videos now send successfully.
- Verified: `smart_reel` returns `Video sent: /tmp/smart_reel_crypto_update_btc.mp4 (0.4MB)` ✅

### ElevenLabs voice — CONFIGURED ✅
- `ELEVENLABS_API_KEY=4f409...` added to `/root/.config/moltis/.env`
- `smart_reel` now calls `create_voiced_reel` when key is set (title + outro spoken by Adam voice)
- Falls back to `create_moviepy_reel` (silent) if key missing

### Commodity reels — FIXED ✅
- Added `commodity:SYMBOL` topic to `get_reel_data` for specific lookups (gold=XAUUSD, oil=WTI etc.)
- Added commodity subject→symbol mapping in `smart_reel` (gold→XAUUSD, silver→XAGUSD, oil→WTI etc.)
- Added `commodities` to `smart_reel` style enum and `title_map`
- Gold reel test confirmed: `Video sent: /tmp/smart_reel_commodities_gold.mp4 (0.4MB)` ✅

### SQL fixes
- `ROUND(float, 2)` → `ROUND(CAST(... AS numeric), 2)` fixed in 5 places in `mcp_server.py`
- BOOT.md updated with correct PostgreSQL rules and price column names

### BOOT.md optimised
- `smart_reel` is now ONE-STEP (model calls it directly, no pre-call to `get_reel_data`)
- Topic→style mapping guide added for all asset types
- Removed `generate_visual` and `generate_chart` from EXPOSED_TOOLS to prevent fallback to static images

---

## Session 2026-03-17 — Moltis/Telegram audit + website health check ✅

### Moltis/Telegram bot on Contabo — ALL HEALTHY ✅
- `[channels.telegram.openclaw]` block confirmed present in moltis.toml (token + chat_id set)
- `telegram_webhook_bridge.py` watchdog loop confirmed implemented (60s loop, re-registers webhook if URL drifts)
- `tg-bridge.service`: active, PID 345913, listening on 10.0.0.3:8767 (WireGuard-only ✅)
- `moltis.service`: active, EnvironmentFile=/root/.config/moltis/.env present ✅
- Webhook: `api.metricshour.com/tg-webhook/` registered, 0 pending updates
- Test message delivered: msg_id 1280 ✅
- Minor: duplicate `RestartSec=` lines in moltis.service (5 and 10) — harmless, uses last value
- Watchdog logs confirmed correct behaviour: re-registered after moltis restart at 01:14-01:17, then stable

### Website health check — see next session update when agent 2 completes

---

## Session 2026-03-16c — Moltis blog hallucination fix + first blog post published ✅

### Moltis publish_blog was hallucinating — FIXED
- Root cause: Moltis LLM was routing blog publishes to Directus CMS (wrong system) instead of calling the `publish_blog` MCP tool which uses `api.metricshour.com/api/admin/blogs`
- Evidence: session JSONL showed Moltis fabricating "Directus CMS Link: cms.metricshour.com/..." URLs that never existed
- Fix: Updated `publish_blog` tool description in `/root/openclaw/mcp_server.py` — explicit warning: "NOT Directus CMS, do NOT call cms.metricshour.com, do NOT use SSH to write files"
- Deployed to Contabo; mcp_server restarts on-demand so fix is live immediately

### First blog post published ✅
- Article: "The Great Geographic Blind Spot: Why Your Portfolio Is Riskier Than You Think"
- Source: medium_article_final.pdf (940.5 KB) sent via Telegram today
- URL: https://metricshour.com/blog/the-great-geographic-blind-spot-why-your-portfolio-is-riskier-than-you-think
- Status: Published (ID: 2, feed event auto-created)
- CF cache purged (used zone ID 6af28d1007b6f8de70ced8653822e49a + VLogFrQw... token)

### Bridge stability issues diagnosed
- Old `telegram_doc_bridge.py` was being run manually, conflicting with webhook bridge during 19:06-20:19
- Since 20:19 webhook bridge is stable (tg-bridge.service running, no cron/service for old script)
- Moltis still has `[channels.telegram.openclaw]` in moltis.toml → spams getUpdates errors but is harmless (can still send replies)

---

## Session 2026-03-16b — Contabo WireGuard + Moltis private routing ✅

### Contabo added to WireGuard mesh
- Installed WireGuard on Contabo (158.220.92.254), assigned IP **10.0.0.3/24**
- Contabo pubkey: `B8P7R1d77LLcD0Wyu5KDAoMSVBSjnI2+DlioMhXHsxE=`
- Added as peer on Netcup (10.0.0.1) + Hetzner (10.0.0.2) — live `wg set` + conf file
- All 3 servers can ping each other via private IPs. Latency: Contabo↔Netcup ~20ms, Contabo↔Hetzner ~38ms
- wg-quick@wg0 enabled on boot on Contabo

### Moltis routes updated to WireGuard IPs
- `publish_blog` / `list_blog_posts`: `https://cms.metricshour.com` → `http://10.0.0.2:8055`
- `NETCUP` constant in all crons: `159.195.29.136` → `10.0.0.1`
- SSH targets in story_finder.py: public IP → `10.0.0.1`
- Moltis restarted (PID 248010)
- Verified: `curl http://10.0.0.2:8055/server/health` → `{"status":"ok"}` from Contabo ✅

---

## Session 2026-03-16 — Price change % fix + Moltis PDF/blog — commit 0ae6514

### Price change % — FIXED EVERYWHERE ✅
Root cause: all workers stored `open=None`, stocks/commodities used minute-precision timestamps for `interval='1d'` creating 167k duplicate rows. Result: `change_pct` was always 0.0% or null.

**DB cleanup:**
- Deleted 167,424 duplicate 1d rows (kept best row per asset-day — open preferred)
- Fixed timestamps to midnight UTC for all 1d records
- Backfilled open prices for 166 assets over last 30 days via yfinance

**Workers fixed:**
- `stocks.py`: day-truncate 1d timestamp; `_fetch_yfinance` now returns `(open, close)` tuples; `_upsert_prices` stores actual open; `_fetch_marketstack` stays bare float
- `commodities.py`: same day-truncation + open from yfinance
- `crypto.py`: `include_24hr_change=true` from CoinGecko → computes `open = close/(1+pct/100)`; writes both `1m` (minute-precise) AND `1d` (day-truncated with open) records
- `fx.py`: fetches daily open separately; writes both `15m` AND `1d` records

**API (`assets.py`):** Added `_price_dict()` helper — all price responses now include `change_pct = (close-open)/open*100`

**Frontend (all pages showing 0.0% now fixed):**
- `index.vue`: ticker skips assets with no change data (no more 0.0% in scrolling ticker)
- `markets/index.vue`: `PriceBadge` component now shows `▲/▼ X.XX%`
- `stocks/index.vue`: change_pct on mobile + desktop rows
- `stocks/[ticker].vue`: change_pct below price hero
- `commodities/[symbol].vue`: uses API `change_pct`, fallback to consecutive closes
- `indices/index.vue`: uses `change_pct` (was open/close which was always null)

**Verified live:** AAPL +0.55%, BTC +3.06%, NVDA +0.88%, WTI -5.79%, XAUUSD -0.22%, EURUSD +0.83% ✅

### Moltis PDF/blog capability — IMPLEMENTED ✅

**New MCP tools on Contabo:**
- `read_pdf(file_id, name)`: downloads PDF from Telegram, extracts text via pypdf, saves to `/root/openclaw/pdf_library/`, returns full text
- `publish_blog(title, content, ...)`: publishes blog to Directus CMS (cms.metricshour.com) as draft or published, with tags/slug/status
- `list_blog_posts(status, limit)`: lists recent blog posts

**Directus setup:**
- `blog_posts` table created in Directus DB (id, title, slug, content, summary, status, tags, source_type, source_file, date_created, date_updated)
- Accessible at cms.metricshour.com/admin/content/blog_posts
- API endpoint: `http://10.0.0.2:8055/items/blog_posts` via WireGuard

**AGENTS.md updated:**
- `## PDF WORKFLOW` section: full step-by-step flow (extract → analyse → blog → card)
- Blog quality rules, learn_from_sample integration with PDFs

**Moltis image fixes (previous session completing):**
- `generate_macro_alert` KeyError fixed: impacts dict normalised to accept `{label/area, value/effect, direction}` in any format
- All tools now verified: `generate_card` ✅ `generate_macro_alert` ✅ `generate_stat_spotlight` ✅ `generate_custom` ✅
- `learn_from_sample` tool added: saves HTML templates with style notes, permanently reusable

### Open items (carry forward)
- [ ] Facebook Page Access Token — still empty
- [ ] Cloudflare Turnstile on /register
- [ ] Pricing page comparison table
- [ ] Prometheus alertmanager
- [ ] SSL cert renewal — expires 2026-05-21
- [ ] Google Indexing API service account setup (one-time user task)

---

## Session 2026-03-16 (auth links) — footer + homepage CTA, commit e5120db

### Completed ✅
- **AppFooter.vue**: Added `Sign In` + `Join Free` links to footer nav row (visible on every page)
- **pages/index.vue**: Added `Create Free Account` button + `Sign In →` link below hero search bar, conditional on `!isLoggedIn`. Added `useAuth()` import to script setup.
- Deployed + verified: both links appear in rendered HTML on homepage ✅

---

## Session 2026-03-16 (auth pages) — dedicated /login + /join pages, commit 0a4a50a

### Completed ✅
- **pages/login.vue**: Full-page Sign In — email/password form + Google OAuth + forgot password link. `robots: noindex`. Redirects to `/` if already logged in.
- **pages/join.vue**: Full-page Register/Join — two-column desktop layout (value props left, form right), 5 features, email/password + Google OAuth + terms/privacy links. `robots: index, follow`.
- **AppNav.vue**: Nav CTAs changed from modal trigger → `NuxtLink to="/login"` (Sign In) + `NuxtLink to="/join"` (Join Free). Both desktop + mobile menus updated.
- **nuxt.config.ts**: Removed `/login` → `/` redirect (now real page). Added `/signup` → `/join` redirect. `/register` → `/join` already existed.
- Deployed to Netcup: `git push`, `git pull`, `npm run build`, `systemctl restart metricshour-frontend`, CF cache purged.
- Verified: `/login` 200, `/join` 200 ✅

### Deploy lesson (IMPORTANT)
- Always verify `git push` completed before SSHing to Netcup to pull. "Already up to date" on Netcup means the push hadn't happened yet — built from stale code.

---

## Session 2026-03-16 (worker bug fixes) — 4 recurring errors eliminated, commit be61e01

### Fixed ✅ (all deployed + verified on Netcup)
- **stocks.py**: `logging.getLogger("yfinance").setLevel(logging.CRITICAL)` — yfinance was logging per-ticker TypeError internally before our except ran. Now silent. 90/90 prices confirmed post-fix.
- **fx.py**: Same yfinance logger suppression + added `TypeError` to primary 15m loop's `except (KeyError, IndexError)` → `except (KeyError, IndexError, TypeError)` (fallback loop already had it)
- **world_bank_update.py**: `NE.IMP.GNFS.CD` HTTP 400 now `log.warning` (1 line) instead of `log.exception` (full traceback). All WB fetch errors downgraded from exception to warning.
- **DOCKER-USER iptables**: `systemctl restart docker-ufw-fix.service` — flushed + reapplied clean. 16 rules → 14 rules. Duplicate DROP rules for ports 6001/6002 removed.

### Verification
- Stocks task at 14:18 UTC: 90/90 prices, zero TypeErrors (was 89/90 + error before fix)
- Worker started clean 14:20 UTC, no errors in log since

---

## Session 2026-03-16 (deep investigation) — Security cleanup + full infra audit

### Security monitoring cleanup ✅
- **Moltis Telegram chat analysed** — identified Moltis hallucinated card delivery in previous session
- **Netcup `/usr/local/bin/security_monitor.sh` cron REMOVED** — buggy bash script running every 15min, spamming text alerts, had variable leak bug (`$severity` from fail2ban block infected disk check → disk "warning" at 2%)
- **Contabo `security_watcher.py` SyntaxWarning fixed** — line 100: `"| grep -v 'SRC=10\.'..."` → raw string `r"..."`. Confirmed `Syntax OK`
- **Canonical monitoring**: Contabo security_watcher.py (hourly PIL image cards, state-aware) + security_daily.py (9am report) — these are the real monitors

### Full infrastructure audit findings (2026-03-16 14:00 UTC)
- All 6 Netcup services: active ✅
- Beat (metricshour-beat.service): running 1d 5h, all schedules firing ✅
- Worker (metricshour-worker): running 14h, 38 tasks registered, no failures since Mar 15 01:10 ✅
- Redis: 3,907 keys ✅ | DB: 24 idle + 1 active ✅ | Disk: 2% ✅
- Contabo Moltis: 3 days uptime ✅
- **Facebook paid ads live** — fbclid + utm_medium=paid traffic seen in nginx logs ✅
- Worker logs → `/var/log/metricshour/celery.log` (not journald — StandardOutput=append)

### Known recurring non-critical errors (not fixed yet)
- `stocks.py`/`fx.py`: `TypeError('NoneType' not subscriptable)` on 1 ticker/batch — yfinance returns None on market close. Task still succeeds 89/90. Needs None guard.
- `world_bank_update.py`: `NE.IMP.GNFS.CD` → HTTP 400 from WB API daily
- `fx.py`: USDCNY=X, USDINR=X, USDBRL=X "possibly delisted" — fallback recovers

### Open items (carry forward)
- [x] Fix yfinance None guard in stocks.py / fx.py — DONE commit be61e01
- [x] Remove or skip NE.IMP.GNFS.CD in world_bank_update.py — DONE commit be61e01
- [ ] Facebook Page Access Token — still empty
- [ ] Cloudflare Turnstile on /register
- [ ] Pricing page comparison table
- [ ] Prometheus alertmanager
- [ ] SSL cert renewal — expires 2026-05-21
- [ ] Google Indexing API service account setup (one-time user task)

---

## Session 2026-03-16 (late) — Moltis intelligence overhaul + Google Indexing API

### Moltis — smart model routing + false alert fix + model switching fix ✅

#### False security alerts — FIXED ✅
- Root cause: Coolify containers (10.0.2.x) doing SSH auth = counted as "attacks"
- `/root/openclaw/crons/security_watcher.py`: UFW block count now excludes internal IPs (`10.`, `172.`, `158.220.92.`, `127.`)
- Threshold raised 100→200 (external-only now). `ufw_top_ips` shows actual attacker IPs in alert
- `AGENTS.md`: added infrastructure table of known-legitimate traffic so agent never false-alerts on internal IPs

#### Moltis model switching — FIXED ✅
- Root cause 1: `[tools.exec.sandbox] mode = "all"` → bash/exec in container, no systemctl → `switch_model.sh` unreachable
- Root cause 2: MCP subprocess lacked `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` → systemctl --user failed silently
- Root cause 3: AGENTS.md warning "NEVER use bash switch_model.sh — sandboxed" → model concluded ALL tools were sandboxed → 0 tool calls
- **Fix**: Added 3 MCP tools to `/root/openclaw/mcp_server.py`:
  - `switch_model(model)`: updates moltis.toml + SQLite DB session + detached restart with correct env vars
  - `current_model()`: reads active model from SQLite sessions table
  - `recall_chat(limit)`: reads recent Telegram messages from message_log
- **BOOT.md**: updated to explicitly state all 3 MCP tools are available and work (exec sandbox does NOT affect MCP tools)
- **AGENTS.md**: reworded — "The switch_model tool is available and works. It is an MCP tool, not a bash command."
- 4 valid models: `deepseek`, `gemini`, `haiku`, `sonnet`

#### Moltis smart routing — ADDED ✅
- AGENTS.md: `## AUTOMATIC TASK ROUTING` — routes by task type without user prompting
  - Doc/file analysis → switch to gemini (best for large context, free tier)
  - Heavy analysis → deepseek (cost-optimised)
  - Complex code/logic → sonnet (manual only, offer revert)
- AGENTS.md: `## MODEL AWARENESS` — calls `current_model` tool when user asks which model is active
- AGENTS.md: `## USER-TRIGGERED MODEL SWITCHING` — maps natural language ("switch to gemini", "use cheaper model") to switch_model MCP tool
- AGENTS.md: `## DOCUMENT / FILE ANALYSIS PROTOCOL` — size-check, focused extraction, no full-file dumps
- AGENTS.md: `⚠️ DATA WARNING` before all templates — volatile data replaced with `{{QUERY}}` placeholders

### Google Indexing API — IMPLEMENTED ✅ (commit in progress)
- New file: `workers/tasks/google_indexing.py`
  - `submit_daily_batch()`: daily Celery task, Redis cursor rotation through ~2800 URLs, 200 URL/day quota
  - `notify_url(url)`: on-demand single URL notify (for newly published content)
  - `notify_urls(urls)`: batch notify up to 200 URLs
  - Priority URL ordering: homepage → /countries → /stocks → /commodities → /trade
- `celery_app.py`: `tasks.google_indexing` added to includes + beat schedule `crontab(hour=4, minute=5)`
- `backend/app/config.py`: `google_indexing_key_file` setting added

### Google Indexing one-time setup (user TODO)
1. Google Cloud Console → Service Accounts → create → JSON key download
2. Google Search Console → Users → add service account email as Owner
3. `scp key.json root@10.0.0.1:/root/metricshour/backend/google_service_account.json`
4. Add to Netcup `.env`: `GOOGLE_INDEXING_KEY_FILE=/root/metricshour/backend/google_service_account.json`
5. `systemctl restart metricshour-api metricshour-worker`

### Open items (carry forward)
- [ ] Test model switching: send `/reset` in Telegram then "switch to gemini" → confirm tool fires
- [ ] Google Indexing API: complete one-time service account setup (see steps above)
- [ ] Facebook Page Access Token — still empty
- [ ] Cloudflare Turnstile on /register
- [ ] Pricing page comparison table
- [ ] Prometheus alertmanager
- [ ] SSL cert renewal — expires 2026-05-21 (auto-renews at 30 days)

---

## Current Status: LIVE ✅ (as of 2026-03-16)

---

## Session 2026-03-16 (latest) — JSON-LD mainEntity SEO fix + full verification

### JSON-LD mainEntity — ALL PAGES FIXED ✅ (commit 6bc5077)
- `countries/[code].vue`: `mainEntity: Country` on WebPage ✅
- `stocks/[ticker].vue`: `mainEntity: Corporation` on WebPage ✅
- `trade/[pair].vue`: `mainEntity: ItemList` (exporter + importer countries) on WebPage ✅
- `blog/index.vue`: CollectionPage + BreadcrumbList JSON-LD added ✅
- `blog/[slug].vue`: BreadcrumbList JSON-LD block added ✅
- `privacy.vue`: WebPage JSON-LD added ✅
- `terms.vue`: WebPage JSON-LD added ✅

### Live verification (2026-03-16) ✅
- `/countries/us`: WebPage + FAQPage + Dataset — all `mainEntity` present ✅
- `/stocks/aapl`: WebPage + FAQPage + Dataset — all `mainEntity` present ✅
- `/trade/united-states--china`: WebPage + FAQPage + Dataset — all `mainEntity` present ✅
- `/blog`: CollectionPage + BreadcrumbList live ✅
- `/privacy` + `/terms`: WebPage JSON-LD live ✅

### Sitemap: 2,791 URLs ✅ (confirmed via curl grep count)
- Redirects: metricshour.com/sitemap.xml → 301 → api.metricshour.com/sitemap.xml ✅
- robots.txt: AI bots blocked, Sitemap directive present ✅

### Edge / CDN delivery ✅
- `cdn.metricshour.com/snapshots/lists/countries.json`: 250 countries, `cache-control: public, s-maxage=3600, stale-while-revalidate=86400` ✅
- `cdn.metricshour.com/og/section/home.png`: PNG serving, `cache-control: public, max-age=86400` ✅
- CF cache purged post-deploy ✅

### Meta tags on /countries/us (SSR verified) ✅
- title: "United States Economy: GDP $28.8T, +2.8% Growth — MetricsHour"
- meta description: present ✅
- robots: `index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1` ✅
- og:image: `https://cdn.metricshour.com/og/countries/us.png` ✅
- canonical: `https://metricshour.com/countries/us/` ✅

---

## Session 2026-03-16 (night) — OG image full fix + SEO audit + security hardening

### OG image system — COMPLETE ✅ (commits 2877215, 8130a47, f1e75c9)
- **Root cause**: compare pages used `og/section/countries.png` which didn't exist in R2 (only `home.png` existed)
- **Fixed compare page** → `og/countries/{codeA}.png` (commit 2877215)
- **Section images**: added `_section_image()` + `generate_section_images()` Celery task — 9 images generated (home, countries, stocks, trade, commodities, markets, indices, feed, pricing) — all 200 on CDN ✅
- **Commodity OG**: worker only generated stocks; added commodity loop → `og/commodities/{symbol}.png` (18 images). Fixed `commodities/[symbol].vue` path: `og/stocks/` → `og/commodities/`
- **Index OG**: `og/indices/` was empty; added index loop → 18 images generated
- **Final R2 state**: 250 countries + 90 stocks + 2708 trade + 18 commodities + 18 indices + 9 section = **3,093 OG images, 0 errors**
- All pages verified live: og:image → cdn.metricshour.com for every page type ✅

### SEO audit — FULLY VERIFIED (31 pages)
- `og:site_name` + `og:locale` confirmed set globally in `nuxt.config.ts` (lines 33-34) — NOT per-page, don't add per-page
- `privacy.vue`: added missing `ogDescription` (commit f1e75c9)
- All H1, canonical, JSON-LD, twitter:card, robots confirmed correct on all page types
- Sitemap: 2,791 URLs — trade 2232, countries 251, compare 172, stocks 91, commodities 19, indices 18, static 8

### Security hardening — COMPLETE ✅
- **Ports 6001/6002 (coolify-realtime) were publicly exposed** — blocked via DOCKER-USER chain (live immediately)
- **`docker-ufw-fix.service` updated** — now has ordered ACCEPT (WireGuard/Contabo) before DROP for 6001/6002 on reboot
- **ALLOWED_ORIGINS tightened** — removed stale CF Pages preview URLs (`2c93f583`, `d41eaf8c`). Now: `localhost:3000, metricshour.com, www.metricshour.com` only
- API restarted to apply new ALLOWED_ORIGINS
- Telegram webhook: confirmed validated via `X-Telegram-Bot-Api-Secret-Token` header (was not missing — audit false alarm)
- fail2ban: 1,564 total banned ✅
- All security headers live: HSTS, CSP, X-Frame DENY, nosniff, Referrer, Permissions ✅
- Evil-origin CORS test confirmed: no `Access-Control-Allow-Origin` returned for `evil.com` ✅
- CF cache purged after all changes ✅

### Open items (carry forward)
- [ ] Facebook Page Access Token — still empty
- [ ] Cloudflare Turnstile on /register
- [ ] Pricing page comparison table
- [ ] Prometheus alertmanager
- [ ] SSL cert renewal — expires 2026-05-21

---

## Session 2026-03-16 (continued) — Verification + importance score fix + deploy

### All previous fixes verified ✅
- `useApi.ts`: `_fetchWithTimeout()` + AbortController ✅
- `useAuth.ts`: `console.warn` in `restore()` ✅
- `telegram_webhook.py`: `_tg_post()` helper ✅
- `security_monitor.py`: DDoS detection (10k/hr threshold) ✅
- `og_images.py`: sys.path = `/root/metricshour/backend` ✅
- `storage.py` + `celery_app.py`: SSL only for `rediss://` ✅
- `social_content.py`: Gemini truncation recovery + `re.DOTALL` ✅
- `feed.py /watchlist`: batch subquery joins ✅
- `summaries.py`: `scalars().first()` for PageInsight/PageSummary + `asset_type` filters ✅
- `meilisearch` package installed in venv ✅

### Fixed (commits 5a9147e, 04fba85 — pushed + deployed)
- `frontend/pages/feed/[id].vue` + `s/[id].vue`: normalize legacy `api.metricshour.com` image_url → `cdn.metricshour.com` (old DB records still have api.metricshour.com URLs)
- `workers/tasks/summaries.py` `_insight_importance()`: lower tiers now granular — stock $1B/$100M splits, trade $1B/$100M splits → 4.5/5.0/5.5 instead of flat 5.5 for all small entities
- Frontend built + deployed, worker restarted, CF cache purged ✅

### Open items (carry forward)
- [ ] Facebook Page Access Token — still empty
- [ ] Cloudflare Turnstile on /register
- [ ] Pricing page comparison table
- [ ] Prometheus alertmanager
- [ ] Old social shares: manual re-scrape on Facebook/LinkedIn debug tools
- [ ] Test reel generation: OpenClaw fire 7+ images on "generate reel"

---

## Session 2026-03-16 — AI flow audit + critical worker crash fix

### Critical: worker had been down (unknown duration)
- `tasks/search_index.py` imports `meilisearch` which was not installed → worker crashed on startup every 15s
- **Fix**: `pip install meilisearch` on both Hetzner + Netcup venvs ✅
- **Zero tasks were running** until this was fixed

### AI model fixes (commits b7140b0, ca4b5bc — pushed + deployed to Netcup)
- `social_content.py`: `gemini-2.5-flash-lite` → `gemini-2.5-flash` (better quality for daily post drafts)
- `summaries.py`: added 1024-token thinking buffer to `maxOutputTokens` for flash model (thinking model consumes tokens before output — G20 summaries were being silently truncated)
- `test_ai.py`: rewritten — real prompt, tests both Gemini (flash + flash-lite) + DeepSeek, exits non-zero on failure

### Keys
- `GEMINI_API_KEY_2` added to both Hetzner + Netcup `.env` (sourced from Contabo secrets.env)
- All 4 keys confirmed live on Netcup: Gemini key1 ✅ Gemini key2 ✅ DeepSeek ✅

### Infrastructure clarification (IMPORTANT)
- **We run Claude Code on Hetzner (89.167.35.114 / 10.0.0.2)**
- **Production is on Netcup (10.0.0.1)** — always SSH there to verify production state
- Hetzner also runs a copy of worker+API but Redis is unreachable (10.0.0.1:6379) → degraded, not production
- Deploy flow: commit on Hetzner → git push → ssh Netcup git pull → systemctl restart

### Full AI model map (production, Netcup — verified 2026-03-16)
| Flow | Model | Fallback |
|------|-------|---------|
| `social_content` (9am drafts) | gemini-2.5-flash | gemini-2.5-flash (key2) → DeepSeek |
| `summaries` bulk | DeepSeek primary | gemini-2.5-flash-lite |
| `summaries` G20 | gemini-2.5-flash | DeepSeek |
| `macro_alert_checker` | gemini-2.5-flash-lite | gemini-2.5-flash-lite (key2) |
| `seo_monitor` | gemini-2.5-flash-lite | (key2 fallback) |
| OpenClaw (Contabo) | deepseek-chat | gemini-2.5-flash |

### Production health (Netcup, confirmed)
- API: `{"status":"ok","database":"connected","redis":"connected"}` ✅
- Services: metricshour-api ✅ metricshour-worker ✅ metricshour-frontend ✅
- No tracebacks in worker logs ✅
- All 28+ Celery tasks loaded ✅

### SEO/OG fix (commit 0caf311 — deployed)
- Added `og:image:type: 'image/png'` to all 5 entity pages (countries, stocks, trade, commodities, indices)
- Facebook/WhatsApp/LinkedIn require this for reliable image previews in social shares
- CF cache purged — crawlers now get fresh HTML with correct tags
- ROOT CAUSE of social blocking: platforms had cached OLD `api.metricshour.com/og/...` URLs (changed to cdn in commit 3ad0b8a). With cache purge + og:image:type, new scrapes will work. Old cached shares on platforms (Facebook/LinkedIn) need manual re-scrape via their debug tools:
  - Facebook: https://developers.facebook.com/tools/debug/
  - LinkedIn: https://www.linkedin.com/post-inspector/

### OG image brand bar removal (commit 712fd14 — deployed + live on CDN ✅)
- **Root issue**: prominent green "M" box + bold "MetricsHour" bar at bottom of every OG/feed image was dominating visually over data
- **Fix**: replaced brand bar entirely with a single tiny gray `metricshour.com` watermark at bottom-right only
- Also fixed trade image: had 40% empty black space at top; redesigned to header + total volume card + exports/imports side-by-side cards
- Feed event images: same brand bar removal applied
- All 250 country + 90 stock + 2708 trade OG images regenerated and live at cdn.metricshour.com ✅
- Feed OG images (8390) regeneration dispatched, still running
- CF cache purged after regeneration ✅
- Verified live on CDN: Germany, TSLA, US-China trade all confirmed correct

### OG image redesign (commit 02aa569 — deployed + regeneration running)
- **Root issue**: `_country_image` / `_stock_image` only showed 2 metrics, right half of 1200×630 completely empty. Green MetricsHour branding dominated.
- **Fix**: Complete redesign to 2×2 metric grid layout filling full canvas.
  - Country: GDP + GDP Growth + Inflation + Interest Rate (4 cards). Inflation color-coded amber/red/green.
  - Stock: Price + Day Change% + Market Cap + Sector (4 cards). Change% color-coded.
  - Added `_metric_card()` helper.
  - `generate_og_images()` now queries `inflation_pct` and `interest_rate` for countries; computes `change_pct` from open/close for stocks; passes `sector` to stock image.
  - Branding reduced to bottom bar only.
- **Regeneration task dispatched** at 13:28 UTC on Netcup (task ID: 99a42d12-...) — still running (3000+ trade pairs)
- After task completes: all OG images at cdn.metricshour.com/og/{type}/{code}.png will be updated

### OG image session (2026-03-15 continued) — commits 321a854, 6a94bf3
- Fix: trade OG "UNI → UNI" label bug — uses ISO codes now (GB/US not UNI/UNI) — commit 321a854
- Fix: feed event OG title repositioned to fill space freed by brand bar removal — commit 6a94bf3
- Countries 250/250 ✅ Stocks 90/90 ✅ Trade 2708/2708 ✅ — all COMPLETE
- Feed OG: 6494/8441 as of ~15:40 UTC — task b25c149f running, finishes automatically
- All pages 200: / /countries /stocks /trade /commodities /indices ✅
- OG meta tags verified live: correct cdn.metricshour.com URLs on all page types ✅
- Snapshots current: 2026-03-15 07:00 UTC (daily 7am schedule) ✅
- Sitemap: 2791 URLs, redirects working ✅
- Security: DOCKER-USER 5 DROP rules active, fail2ban 1518 bans, internal ports locked ✅
- CF cache purged multiple times ✅

### Open items (carry forward)
- [ ] ANTHROPIC_API_KEY not set on Netcup (not needed — no code uses it)
- [ ] Hetzner worker Redis broken (10.0.0.1:6379 unreachable from Hetzner) — investigate or disable
- [ ] Facebook Page Access Token — still empty
- [ ] Cloudflare Turnstile on /register
- [ ] Pricing page comparison table
- [ ] Prometheus alertmanager
- [ ] Old social shares (pre-cdn migration) need manual re-scrape on Facebook/LinkedIn debug tools

---

## Session 2026-03-15 (evening) — Social share + edge caching

### Social share fixes (commits 3ad0b8a, f09548b)
- **og:image URLs** — all 19 frontend pages had hardcoded `api.metricshour.com/og/...`. Fixed to `cdn.metricshour.com/og/...` across every page.
- **Share URL** — `FeedCard.vue` share link was `api.metricshour.com/s/{id}`. Moved to `metricshour.com/s/{id}`.
- **New SSR share page** — `pages/s/[id].vue` created. Fetches event data, renders OG meta server-side for crawlers, client-side redirects real users to `/feed/{id}`.

### Edge caching (commit 229c5ec)
Added `Cache-Control` headers via Nuxt `routeRules` so Cloudflare caches SSR HTML at the edge:
- `/s/**` — 5 min (share previews)
- `/` + listing pages — 1 h
- Entity pages (`/countries/**`, `/stocks/**`, `/trade/**`, etc.) — 30 min + 24 h stale-while-revalidate
- Markets/Feed — 5 min (live data)
- Static pages (about/privacy/terms) — 24 h
CF cache purged after deploy. Pages now served from Cloudflare PoPs on cache hit.

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

## Session 2026-03-15 (night) — Celery failure elimination + AI key hardening

### Celery failures — ALL ELIMINATED ✅

| Task | Error | Fix | Commit |
|------|-------|-----|--------|
| `oecd_update` | CardinalityViolation (weekly, recurring) | try/except around bulk upsert → row-by-row fallback | `2071a0a` |
| `summaries.run_insight_batch` | MultipleResultsFound | `scalar_one_or_none()` → `scalars().first()` on PageInsight, PageSummary; added `asset_type` filter to all Asset symbol lookups; `.limit(1)` on TradePair query | `2071a0a` |
| `social_content` (9am) | Gemini instant timeout, 0 drafts sent | DeepSeek V3 fallback added; verified 3/3 drafts sent at 09:17 UTC | `bad3e82` |

**celery-failures.log**: last entry 2026-03-15T01:10 (OECD). All subsequent tasks clean.

### 9am social media posts — WORKING ✅
- `generate_social_drafts` fires at 9am UTC via Celery Beat
- Chain: Gemini primary key → Gemini secondary key → DeepSeek V3
- 3 drafts sent to Telegram (Brazil country, SAP SE stock, Netherlands–Germany trade) at 09:17 UTC
- Verified: `DEEPSEEK_API_KEY` set in Netcup `.env` ✓

### Morning visual cards (Contabo cron) — 4/4 WORKING ✅
- `morning_social.py` runs at 09:05 UTC on Contabo
- **Root cause of 2/4**: `_find_best_growth_corridor()` required 2022+2023 corridor overlap — zero rows exist (each year uses different data source, no pairs appear in both years)
- **Fix**: replaced with `_find_top_corridor()` — picks biggest 2023 corridor by volume, fetches any available prior-year data for sparkline
- **Test run**: Netherlands ↔ Germany = $288B → 4/4 cards sent ✓

### AI key safety hardening ✅
- `GEMINI_API_KEY_2` support added everywhere Gemini is called:
  - `social_content.py`: full try-key-1 → try-key-2 → DeepSeek chain
  - `macro_alert_checker.py`: `active_key = GEMINI_API_KEY or GEMINI_API_KEY_2`
  - `seo_monitor.py`: `_GEMINI_KEY = GEMINI_API_KEY or GEMINI_API_KEY_2`
  - `test_ai.py`: safe `.get()` instead of `['key']` (was crashing on missing key)
- **Zero hardcoded keys anywhere** — full audit confirmed
- **Commit**: `b9325c1`, deployed to Netcup, worker restarted

### Key security rules (enforced going forward)
- Never paste API keys into chat — set them on server: `nano /root/metricshour/backend/.env`
- Test keys via SSH: `cd /root/metricshour/workers && python3 test_ai.py`
- To add `GEMINI_API_KEY_2`: `echo 'GEMINI_API_KEY_2=<key>' >> /root/metricshour/backend/.env` then `systemctl restart metricshour-api metricshour-worker`

### Full AI model map (as of 2026-03-15 night)
| Layer | Primary | Fallback 1 | Fallback 2 |
|-------|---------|-----------|-----------|
| `social_content` (9am drafts) | `GEMINI_API_KEY` | `GEMINI_API_KEY_2` | DeepSeek V3 |
| `summaries` bulk | DeepSeek V3 | gemini-2.5-flash | — |
| `summaries` G20 | gemini-2.5-flash | DeepSeek V3 | — |
| `macro_alert_checker` | `GEMINI_API_KEY` || `GEMINI_API_KEY_2` | — | — |
| `seo_monitor` | `_GEMINI_KEY` (key1 or key2) | — | — |
| OpenClaw (Telegram) | deepseek-chat | gemini-2.5-flash | — |
| Anthropic/Claude | NOT USED anywhere | — | — |

### Open items (carry forward)
- [ ] Set `GEMINI_API_KEY_2` in Netcup `.env` (user to do via SSH — never paste in chat)
- [ ] Facebook Page Access Token — `FACEBOOK_PAGE_ACCESS_TOKEN` still empty
- [ ] Cloudflare Turnstile on /register
- [ ] Pricing page comparison table
- [ ] Prometheus/Grafana Telegram alertmanager
- [ ] SSL cert expires 2026-05-21 (auto-renews at 30 days)

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

---

## Session 2026-03-16d — Blog rendering fix deployed to Netcup ✅

### Root cause identified: changes were applied to Hetzner (wrong server) not Netcup
- Claude Code sessions run on Hetzner (89.167.35.114). All previous session's code changes were on Hetzner.
- Production server is Netcup (10.0.0.1). Changes need to be committed → pushed → pulled on Netcup.
- Git pull on SSH requires Already up to date. (SSH starts in /root, not in repo directory)

### Frontend fixes now live on Netcup ✅
- Commits 91cf3cc + 7ad7082 pulled and built on Netcup
- :  library renders markdown → HTML server-side via 
- : SSR calls  directly — bypasses Cloudflare JSON body transform
- :  private config added for SSR bypass
- : converted  →  — article links now SSR-rendered (Google-crawlable)

### Netcup nginx fixed
- Added  location block with  + 
- Added  to  block — eliminates duplicate header
- Note: CF Cache Rule () still adds its own  header — dual header from CF rule not from nginx, non-critical

### CF cache purge
- Purged twice (once mid-session on Hetzner, once after Netcup deploy)
- Used CF purge token  and zone  (hardcoded — NOT in Netcup .env)

### Health check — ALL PASS ✅
- 20/20 frontend routes: 200 OK
- 4/4 API endpoints: 200 OK
- 4/4 Systemd services: active
- Celery clean: stocks (90/90), FX, crypto all succeeding
- Blog article: 7 H2 headers, rendered HTML, 5 CDN images, 10 min read

### Moltis hallucination fix (from session c, confirmed)
-  MCP tool description updated with explicit NOT Directus warning
- Previous blog posts using Directus: 0 real posts existed (all were hallucinated)
- Current real posts: ID=2 (the Geographic Blind Spot article, published 2026-03-16)



---

## Session 2026-03-16d — Blog rendering fix deployed to Netcup

### Root cause: changes were on Hetzner (wrong server), not Netcup
- Claude Code runs on Hetzner (89.167.35.114). All previous session code changes were local.
- Production = Netcup (10.0.0.1). Must commit + push + SSH pull + build + restart.
- Git via SSH requires: git -C /root/metricshour pull (SSH starts in /root, not repo dir)

### Frontend fixes live on Netcup (commits 91cf3cc + 7ad7082)
- blog/[slug].vue: marked library renders markdown to HTML server-side (v-html=renderedBody)
- blog/[slug].vue: SSR calls 127.0.0.1:8000 directly, bypasses Cloudflare JSON body transform
- nuxt.config.ts: apiBaseServer private config added for SSR bypass
- blog/index.vue: converted onMounted to useAsyncData — article links SSR-rendered (Google-crawlable)

### Netcup nginx fixed
- Added /blog/ location block with proxy_hide_header + s-maxage=1800
- Added proxy_hide_header to location / block — eliminates duplicate header
- CF Cache Rule still adds s-maxage=60 alongside — known, non-critical

### Health check ALL PASS
- 20/20 frontend routes: 200 OK
- 4/4 API endpoints: 200 OK
- 4/4 Systemd services: active
- Celery clean: stocks, FX, crypto all succeeding
- Blog article: 7 H2 headers, rendered HTML, 5 CDN images, 10 min read

### CF purge token (NOT in Netcup .env — hardcoded in sessions)
- Token: VLogFrQwgY5RvzkCbmhDvSJbcDsA1_vYNSfZzrYs
- Zone: 6af28d1007b6f8de70ced8653822e49a

## Session 2026-03-17g — Moltis smart_reel production quality overhaul

### Files changed (Contabo 10.0.0.3)
- /root/openclaw/mcp_server.py — smart_reel + get_reel_data complete rewrite
- /root/openclaw/image_gen.py — video engine + list card template overhaul

### Data fixes
- Market recap SQL: stocks/crypto sorted before commodities
- DISTINCT ON queries, scr.fiscal_year fix, GDP threshold 1e12, _fmt_price helper

### Card architecture
- generate_reel_list_card upgraded: METRICSHOUR tag, accent bar, colored badges, date footer
- All 6 reel types: list cards for multi-item views, stat cards for spotlights
- List card captions suppressed (self-contained)

### Video engine
- Ken Burns: 4 center-anchored patterns (max 1.15x zoom, no clipping)
- xfade transitions: fade/wiperight/smoothleft/fadeblack cycling
- Variable durations: title=3.5s data=5.0s outro=3.0s

### Status: all 6 reel types verified clean. Moltis restarted.

## Session 2026-03-17g — Moltis full upgrade + infra hardening ✅

### Moltis disconnection — ROOT CAUSE FIXED
- moltis.service was missing  → OS assigned random port each restart
- tg-bridge hardcoded to 13131 → Connection refused on every moltis restart
- Fix: added  to ExecStart in moltis.service
- tg-bridge.service: added ExecStartPre=/bin/sleep 8 + StartLimitIntervalSec=0
- Result: stable connection, handshake confirmed in logs

### Moltis MCP tools: 30 → 64 exposed
- Added all image, video, template, content, and publishing tools to EXPOSED_TOOLS
- 71 tools defined total; 7 kept hidden (admin/destructive: execute_sql, manage_user, etc.)
- TOML soul string fixed (invalid \' escapes → plain ') — MCP was showing 0 configured

### BOOT.md rewritten (2084 → 7591 chars)
- Full server infrastructure map (all 3 servers with IPs, ports, services)
- All 64 tools catalogued with descriptions and categories
- All 10 custom templates with variables listed
- Content formulas, SQL patterns, deploy procedure

### Infrastructure hardening — all 3 servers (2026-03-17)
- **Hetzner**: UFW was INACTIVE → enabled (22/80/443/51820); fail2ban installed; node_exporter 9100 WireGuard-only
- **Contabo**: added 51820/udp to UFW; 3389 BLOCKED; xrdp MASKED + process killed
- **All servers**: fail2ban ignoreip = 127.0.0.0/8 + 10.0.0.0/24 → no more WireGuard false-positive bans

### All flows verified healthy (2026-03-17)
- Celery: crypto (every 2min), price_alerts (every 1min), feed_generator (every 3min), indices, watchdog — all succeeding ✅
- Alertmanager: 5 rules (APIDown/HighCPU/HighMem/DiskFull/HighLatency), Telegram channel configured ✅
- Prometheus: healthy (127.0.0.1:9090) ✅
- AI APIs: Gemini×2 + Anthropic on Netcup backend; DeepSeek + Gemini×2 + Anthropic + ElevenLabs on Contabo ✅
- API: {status:ok,database:connected,redis:connected} ✅
- Moltis port 13131 + tg-bridge connected ✅
- xrdp: masked + dead + port 3389 closed ✅

### Note: Hetzner runs secondary MetricsHour stack
- Nginx on Hetzner proxies api.metricshour.com AND metricshour.com (not just Docker)
- FastAPI gunicorn + Nuxt SSR also running on Hetzner (secondary/dev)
- Docker: Umami (8080) + Directus (8055) on Hetzner

## Session 2026-03-17g — Moltis full upgrade + infra hardening

### Moltis disconnection ROOT CAUSE FIXED
- moltis.service was missing --port 13131 → OS assigned random port each restart
- tg-bridge hardcoded to 13131 → Connection refused on every moltis restart
- Fix: added --port 13131 to ExecStart in moltis.service
- tg-bridge.service: ExecStartPre=/bin/sleep 8 + StartLimitIntervalSec=0

### Moltis MCP tools: 30 → 64 exposed
- Added all image, video, template, content, publishing tools to EXPOSED_TOOLS
- 71 tools defined total; 7 kept hidden (admin/destructive)
- TOML soul string fixed (invalid backslash-quote escapes) — MCP was showing 0 configured

### BOOT.md rewritten (2084 → 7591 chars)
- Full 3-server infrastructure map with IPs, ports, WireGuard addresses
- All 64 tools catalogued with categories
- 10 custom templates with variables, content formulas, SQL patterns

### Infrastructure hardening — all 3 servers
- Hetzner: UFW was INACTIVE → enabled; fail2ban installed; node_exporter 9100 WireGuard-only
- Contabo: added 51820/udp; 3389 BLOCKED; xrdp MASKED + killed
- All servers: fail2ban ignoreip = 127.0.0.0/8 + 10.0.0.0/24 (WireGuard false-positive fix)

### All flows verified healthy
- Celery: crypto/price_alerts/feed_generator/indices/watchdog all succeeding
- Alertmanager: 5 rules, Telegram configured, 0 active alerts
- Prometheus healthy, API healthy (db+redis connected)
- All AI APIs present: Gemini x2, Anthropic, DeepSeek, ElevenLabs
- Moltis port 13131 stable, tg-bridge connected
- xrdp: masked + dead + 3389 closed

## Session 2026-03-17h — Social media pipeline + blog publishing

### Social media schedule — 4 slots (was 1)
- 8:00 UTC: generate_market_open_drafts — top movers since yesterday
- 9:00 UTC: generate_social_drafts — country/stock/trade insight (existing, upgraded)
- 17:00 UTC: generate_evening_wrap_drafts — day wrap, biggest gainer/loser
- 18:00 UTC: generate_viral_hook_drafts — shocking stat / did-you-know

### Platforms: LinkedIn + Facebook + Instagram + Twitter (was just LI+FB+Reddit)
- Instagram: 2-step Graph API (media container → publish), R2 OG image as visual
- Telegram buttons: [LI][FB] / [Instagram][Twitter] / [All 4][Skip]
- post_approved_draft() dispatches all 4 with Make.com fallback
- og_image_url added to all drafts (R2 CDN: /og/countries/, /og/stocks/, /og/trade/, /og/section/)
- 3 new hooks: _hook_market_movers, _hook_day_wrap, _hook_viral_stat

### Missing env vars (must add to Netcup .env):
- FACEBOOK_PAGE_ACCESS_TOKEN (needed for Facebook + Instagram direct API)
- INSTAGRAM_BUSINESS_ACCOUNT_ID
- TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
- Until set: all posting falls back to Make.com webhook

### Blog publishing via Moltis — new craft_blog tool (tool #65)
Two modes:
1. craft_blog(title, topic, data_hook) → AI (Gemini→DeepSeek) queries DB, writes 800-1000 words SEO post → publishes → returns URL
2. craft_blog(title, raw_content) → user-provided text → publish as-is (no AI)
- data_hook: 'country:IN', 'stock:AAPL', 'trade:US-CN', 'commodity:gold'
- BOOT.md updated with blog flows (8352 chars)
- Moltis now at 65 tools exposed

## Session 2026-03-17i — Social media posts manual flow + reel scheduling

### Architecture change: manual publishing (no API automation)
- All posts delivered to Telegram as copy-ready text — user posts manually
- 5 messages per slot: photo (OG image from R2) + Twitter + LinkedIn + Facebook + Instagram
- Each platform message is separate so user can long-press copy in Telegram
- Removed: Redis draft storage, inline keyboards, approval buttons, API posting code

### 6 daily schedule slots (UTC)
- 08:00 — Market open: top movers text posts
- 08:30 — Morning reel (Moltis generates market_recap reel via tg-bridge injection)
- 09:00 — Insight post: country/stock/trade (3 hooks rotate)
- 17:00 — Evening wrap: day summary biggest mover/loser
- 17:30 — Evening reel (Moltis generates crypto_update reel via tg-bridge)
- 18:00 — Viral hook: shocking stat / did-you-know

### Reel trigger flow
- Celery task POSTs fake Telegram update to http://10.0.0.3:8767/webhook (WireGuard)
- Header: X-Telegram-Bot-Api-Secret-Token validates the request
- tg-bridge forwards command to Moltis → Moltis generates reel → sends video to Telegram
- User downloads video from Telegram and posts to Instagram/TikTok manually

## Session 2026-03-18i — Moltis hardening + robust content pipeline ✅

### social_content.py (Netcup) — commit 1b4841c
- Added `_send_failure_alert(slot_name, error_msg)` — sends Telegram message when any slot fails permanently after all retries
- Fixed `_trigger_reel_via_moltis` return type: `None → bool` — silent failures were masked (task said "reel triggered" even when tg-bridge unreachable)
- All 4 reel tasks upgraded from bare functions to `bind=True, max_retries=2` with try/except + failure alerts
- All 4 POST tasks: `MaxRetriesExceededError` now calls `_send_failure_alert` (was silent log-only)

### mcp_server.py (Contabo)
- Added 3 new model aliases: `deepseek-r1` (DeepSeek Reasoner), `gemini-pro` (Gemini 2.5 Pro), `gemini-pro-exp` (Gemini 2.5 Pro Exp 03-25)
- `switch_model` inputSchema enum updated to include all 8 models
- Tool description updated: "ALWAYS ask user for confirmation before calling"

### BOOT.md (Contabo) — now 330 lines
- R9: smart_reel failure → send exact error to user + retry once. If retry fails → stop and report.
- R10: NEVER call switch_model without user's explicit YES (show model name + label first)
- New section: AVAILABLE MODELS table (8 models, aliases, when to use each)

### Services restarted
- Netcup: metricshour-worker + metricshour-beat ✓
- Contabo: moltis ✓
- Telegram update sent to user ✓

### Additional fixes (Session 2026-03-18i continued)
- social_content.py quality gate (commit b783001): `_quality_check()` + `_BANNED_PHRASES` (23 phrases), auto-retry once if bad output
- BOOT.md: CONTINUOUS IMPROVEMENT PROTOCOL section added (update_system_context usage guide)
- BOOT.md R11: API down = auto-switch fallback, no permission needed
- BOOT.md Smart routing table: which model for which task type
- BOOT.md now 371 lines
- Final state: all 8 slots have failure alerts + retry, quality gate, smart model routing, 8 models available

## Session 2026-03-18j — Full verification ✅

### Verified live (all checks passing)

**Netcup services:** metricshour-api ✓ metricshour-worker ✓ metricshour-beat ✓ metricshour-frontend ✓
**Contabo services:** moltis ✓ tg-bridge ✓
**API health:** ok ✓
**Commits:** b783001 (quality gate) + 1b4841c (failure alerts) both pushed to main ✓

**social_content.py (Netcup) — verified:**
- 22 matches: `_send_failure_alert` (×9), `_quality_check` (×2), `_BANNED_PHRASES` (×2), `max_retries=2` (×8), `-> bool` (×1)
- All 8 slot names confirmed: POST 1-4 + REEL 1-4
- Syntax: OK

**mcp_server.py (Contabo) — verified:**
- New models: `deepseek-r1`, `gemini-pro`, `gemini-pro-exp` + `deepseek-reasoner` ✓
- 5 matches in file
- Syntax: OK

**BOOT.md (Contabo) — verified:**
- R9, R10, R11 all present
- 9 matches: deepseek-r1(×2), gemini-pro(×3), R9(×1), R10(×1), R11(×1), CONTINUOUS IMPROVEMENT(×1)
- 367 lines total
