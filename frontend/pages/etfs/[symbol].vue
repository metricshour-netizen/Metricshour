<template>
  <div>
    <!-- Hero band -->
    <div class="bg-gradient-to-b from-[#00091a] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/etfs/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← ETFs
        </NuxtLink>

        <div v-if="pending" class="h-20 flex items-center">
          <div class="space-y-2">
            <div class="h-8 w-40 bg-[#1f2937] rounded animate-pulse"/>
            <div class="h-4 w-64 bg-[#1f2937] rounded animate-pulse"/>
          </div>
        </div>
        <div v-else-if="error || !asset" class="text-red-400 text-sm py-6">ETF not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 rounded-xl bg-sky-900/30 border border-sky-800/40 flex items-center justify-center text-2xl shrink-0">
                {{ categoryIcon(asset.sector) }}
              </div>
              <div>
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h1 class="text-3xl font-extrabold text-white tracking-tight">{{ asset.name }}</h1>
                  <span class="text-[10px] font-bold text-sky-400/80 bg-sky-400/10 border border-sky-800/40 px-2 py-1 rounded-md">ETF</span>
                  <span v-if="asset.exchange" class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded-md">{{ asset.exchange }}</span>
                </div>
                <p class="text-gray-300 font-medium">{{ asset.symbol }}</p>
                <p class="text-gray-600 text-xs mt-0.5">{{ asset.sector || 'ETF' }} · Exchange-Traded Fund</p>
              </div>
            </div>
            <div class="text-right">
              <div class="text-4xl font-extrabold text-white tabular-nums tracking-tight">
                {{ asset.price ? fmtPrice(asset.price.close) : '—' }}
              </div>
              <div v-if="asset.price?.change_pct != null" class="text-sm mt-1 tabular-nums"
                   :class="asset.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ asset.price.change_pct >= 0 ? '▲' : '▼' }}
                {{ Math.abs(asset.price.change_pct).toFixed(2) }}%
                <span class="text-gray-600 font-normal ml-1">today</span>
              </div>
              <div class="text-xs text-gray-600 mt-1">
                {{ asset.price?.timestamp ? 'Updated ' + fmtTs(asset.price.fetched_at || asset.price.timestamp) : 'Awaiting price feed' }}
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-8" v-if="asset">

      <!-- Stats -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">AUM</div>
          <div class="text-white font-bold text-lg">{{ asset.market_cap_usd ? fmtCap(asset.market_cap_usd) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Category</div>
          <div class="text-white font-bold text-lg">{{ asset.sector || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Day Open</div>
          <div class="text-white font-bold text-lg">{{ asset.price?.open ? fmtPrice(asset.price.open) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Exchange</div>
          <div class="text-white font-bold text-lg">{{ asset.exchange || '—' }}</div>
        </div>
      </div>

      <!-- Summary -->
      <div v-if="pageSummary?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-4 text-sm text-gray-400 leading-relaxed page-summary">
        {{ pageSummary.summary }}
      </div>

      <!-- Insights (rotating) -->
      <div v-if="pageInsights?.length" class="mb-4">
        <div class="relative border rounded-lg p-4 overflow-hidden bg-[#0d1520] border-sky-900/50 page-insight-latest">
          <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-sky-500/40 to-transparent"/>
          <div class="flex items-start gap-3">
            <span class="text-base mt-0.5 shrink-0 text-sky-400">◆</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1 flex-wrap">
                <span class="text-[10px] font-bold uppercase tracking-widest text-sky-400">MetricsHour Intelligence</span>
                <span class="text-[10px] text-gray-700 ml-auto">{{ fmtInsightDate(pageInsights[featuredIdx].generated_at) }}</span>
              </div>
              <p class="text-sm text-gray-300 leading-relaxed">{{ pageInsights[featuredIdx].summary }}</p>
            </div>
          </div>
        </div>
        <div v-if="pageInsights.length > 1" class="mt-1.5 border border-[#1a2030] rounded-lg overflow-hidden">
          <div class="divide-y divide-[#131b27]">
            <div
              v-for="(insight, i) in otherInsights"
              v-show="showAllInsights || i < 2"
              :key="insight.generated_at"
              class="flex items-start gap-3 px-3 py-2 bg-[#0a0d14] cursor-pointer"
              @click="toggleInsight(insight.generated_at)"
            >
              <span class="text-[10px] text-gray-600 shrink-0 mt-0.5 w-16">{{ new Date(insight.generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }}</span>
              <p class="text-xs text-gray-500 leading-relaxed" :class="expandedInsights.has(insight.generated_at) ? '' : 'line-clamp-2'">{{ insight.summary }}</p>
            </div>
          </div>
          <button
            v-if="pageInsights.length > 3"
            class="w-full px-3 py-2 text-[10px] text-gray-600 hover:text-sky-400 bg-[#0a0d14] border-t border-[#1a2030] transition-colors text-left"
            @click="showAllInsights = !showAllInsights"
          >
            {{ showAllInsights ? '↑ Show less' : `↓ Read more (${pageInsights.length - 3} more insights)` }}
          </button>
        </div>
      </div>

      <!-- Price chart -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4 mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-base font-bold text-white">Price History</h2>
          <div class="flex gap-1">
            <button
              v-for="r in availableRanges"
              :key="r.label"
              @click="activeRange = r.days"
              class="text-xs px-2 py-0.5 rounded transition-colors"
              :class="activeRange === r.days ? 'bg-sky-600 text-white' : 'text-gray-500 hover:text-gray-300'"
            >{{ r.label }}</button>
          </div>
        </div>
        <EChartLine v-if="chartOption" :option="chartOption" height="260px" />
        <div v-else class="h-[260px] flex items-center justify-center text-gray-600 text-sm">
          {{ pricesRaw?.length ? 'Price history building — check back in a few days.' : 'No price data yet.' }}
        </div>
      </div>

      <!-- About -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-3">About {{ asset.symbol }}</h2>
        <p class="text-gray-400 text-sm leading-relaxed">{{ etfDescription(asset.symbol, asset.name, asset.sector) }}</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <NuxtLink to="/etfs/" class="text-xs text-sky-400 hover:text-sky-300 border border-sky-800/40 px-3 py-1.5 rounded-lg transition-colors">
            ← All ETFs
          </NuxtLink>
          <NuxtLink to="/markets/" class="text-xs text-gray-400 hover:text-gray-300 border border-[#1f2937] px-3 py-1.5 rounded-lg transition-colors">
            Browse Markets →
          </NuxtLink>
        </div>
      </div>

      <!-- Related ETFs -->
      <div v-if="relatedEtfs?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-3">More ETFs</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <NuxtLink
            v-for="e in relatedEtfs"
            :key="e.symbol"
            :to="`/etfs/${e.symbol.toLowerCase()}/`"
            class="flex items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-sky-800/40 rounded-lg px-3 py-2.5 transition-colors group"
          >
            <span class="text-lg">{{ categoryIcon(e.sector) }}</span>
            <div class="min-w-0">
              <div class="text-xs font-bold text-white group-hover:text-sky-400 transition-colors truncate">{{ e.name }}</div>
              <div class="text-[10px] text-gray-600 font-mono">{{ e.symbol }}</div>
            </div>
          </NuxtLink>
        </div>
        <div class="mt-3 flex gap-3">
          <NuxtLink to="/etfs/" class="text-xs text-sky-400 hover:text-sky-300 transition-colors">View all ETFs →</NuxtLink>
          <NuxtLink to="/stocks/" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">Stocks →</NuxtLink>
          <NuxtLink to="/indices/" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">Indices →</NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center mb-8">Data: NYSE · NASDAQ</p>

      <!-- Newsletter -->
      <div class="border border-gray-800 rounded-xl p-6 bg-gray-900/40">
        <p class="text-xs font-mono text-sky-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">ETF flows + macro context, every week.</p>
        <p class="text-xs text-gray-500 mb-4">Fund performance, rate moves, economic shifts — free.</p>
        <NewsletterCapture :source="`etf_page_${symbol}`" button-text="Subscribe free" />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()
const symbol = (route.params.symbol as string).toUpperCase()

const { data: asset, pending, error } = await useAsyncData(
  `etf-${symbol}`,
  () => get<any>(`/api/assets/${symbol}`).catch(() => null),
)
if (!asset.value) throw createError({ statusCode: 404, statusMessage: 'ETF not found' })

// ── Related ETFs (must be before server:false calls for SSR) ────────────────
const { public: { apiBase: _apiBase } } = useRuntimeConfig()
const { data: relatedEtfs } = await useAsyncData(
  `related-etf-${symbol}`,
  async () => {
    const all = await $fetch<any[]>('/api/assets', { baseURL: _apiBase, params: { type: 'etf', limit: 12 } }).catch(() => [])
    return (all || []).filter((a: any) => a.symbol !== symbol).slice(0, 6)
  },
)

const { data: pageSummary } = useAsyncData(
  `summary-etf-${symbol}`,
  () => get<any>(`/api/summaries/etf/${symbol}`).catch(() => null),
  { server: false },
)

const { data: pageInsights } = useAsyncData(
  `insights-etf-${symbol}`,
  () => get<any[]>(`/api/insights/etf/${symbol}`).catch(() => []),
  { server: false },
)

const { data: pricesRaw } = useAsyncData(
  `etf-prices-${symbol}`,
  () => get<any[]>(`/api/assets/${symbol}/prices?interval=1d&limit=365`).catch(() => []),
  { server: false },
)

// ── Insight rotation ──────────────────────────────────────────────────────────
const featuredIdx = computed(() => {
  const ins = pageInsights.value
  if (!ins?.length) return 0
  const day = Math.floor(Date.now() / 86400000)
  return day % Math.min(ins.length, 3)
})

const otherInsights = computed(() => {
  const ins = pageInsights.value ?? []
  return ins.filter((_: any, i: number) => i !== featuredIdx.value)
})

const expandedInsights = ref<Set<string>>(new Set())
const showAllInsights = ref(false)
const toggleInsight = (key: string) => {
  const s = new Set(expandedInsights.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedInsights.value = s
}

// ── Chart ─────────────────────────────────────────────────────────────────────
const RANGES = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
]
const activeRange = ref(90)

const availableRanges = computed(() => {
  const n = pricesRaw.value?.length ?? 0
  return RANGES.filter(r => n >= r.days || (r === RANGES[0] && n >= 5))
})

const chartOption = computed(() => {
  const p = pricesRaw.value
  if (!p?.length || p.length < 7) return null
  const slice = p.slice(-activeRange.value)
  const dates  = slice.map((x: any) => x.t?.slice(0, 10))
  const closes = slice.map((x: any) => x.c)
  const isUp   = closes[closes.length - 1] >= closes[0]
  const color  = isUp ? '#38bdf8' : '#f87171'
  return {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 8, bottom: 40, containLabel: true },
    tooltip: { trigger: 'axis', backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#fff', fontSize: 11 }, formatter: (p: any) => `${p[0].axisValue}<br/>$${p[0].value.toFixed(2)}` },
    xAxis: { type: 'category', data: dates, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, interval: Math.floor(slice.length / 5) } },
    yAxis: { type: 'value', scale: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => '$' + v.toFixed(0) }, splitLine: { lineStyle: { color: '#1f2937' } } },
    series: [{ type: 'line', data: closes, smooth: true, symbol: 'none', lineStyle: { color, width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '33' }, { offset: 1, color: color + '00' }] } } }],
  }
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function categoryIcon(sector: string | null): string {
  const map: Record<string, string> = {
    'Broad Market': '📊',
    'Sector': '🏭',
    'International': '🌍',
    'Bonds': '📜',
    'Commodities': '🪙',
    'Dividend': '💰',
  }
  return map[sector ?? ''] ?? '📈'
}

function fmtPrice(v: number): string {
  return '$' + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtCap(v: number): string {
  if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T'
  if (v >= 1e9)  return '$' + (v / 1e9).toFixed(1) + 'B'
  if (v >= 1e6)  return '$' + (v / 1e6).toFixed(0) + 'M'
  return '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

function fmtTs(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
  if (d.getUTCHours() === 0 && d.getUTCMinutes() === 0) return date
  return date + ' · ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC'
}

function fmtInsightDate(ts: string): string {
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const ETF_DESCRIPTIONS: Record<string, string> = {
  SPY:  'The SPDR S&P 500 ETF Trust (SPY) is the world\'s largest ETF by assets under management, tracking the S&P 500 index. Launched in 1993, it provides broad exposure to 500 large-cap US equities and is the most actively traded equity security in the world.',
  VOO:  'The Vanguard S&P 500 ETF (VOO) tracks the S&P 500 index with one of the lowest expense ratios available. Managed by Vanguard, it is the second-largest ETF globally and a core holding for long-term passive investors.',
  VTI:  'The Vanguard Total Stock Market ETF (VTI) provides exposure to the entire US equity market — large, mid, small, and micro-cap stocks. It tracks the CRSP US Total Market Index across more than 3,500 securities.',
  QQQ:  'The Invesco QQQ Trust (QQQ) tracks the Nasdaq-100 Index, comprising the 100 largest non-financial companies listed on the NASDAQ exchange. Heavily weighted toward technology, it is one of the most actively traded ETFs in the world.',
  IWM:  'The iShares Russell 2000 ETF (IWM) tracks the Russell 2000 Index of approximately 2,000 small-cap US companies. It is the most widely used benchmark for US small-cap equity performance.',
  GLD:  'The SPDR Gold Shares ETF (GLD) tracks the price of gold bullion and is one of the largest physically-backed gold ETFs. It provides investors with exposure to gold without needing to hold physical metal.',
  TLT:  'The iShares 20+ Year Treasury Bond ETF (TLT) tracks long-duration US Treasury bonds with maturities of 20 years or more. It is widely used as a proxy for long-term interest rate risk and as a safe-haven instrument.',
  EEM:  'The iShares MSCI Emerging Markets ETF (EEM) provides exposure to large and mid-cap equities in over 24 emerging market countries, including China, India, Brazil, and South Korea.',
  VWO:  'The Vanguard FTSE Emerging Markets ETF (VWO) tracks the FTSE Emerging Markets Index and provides low-cost exposure to stocks in developing economies across Asia, Latin America, Europe, and Africa.',
  XLF:  'The Financial Select Sector SPDR Fund (XLF) tracks the Financial Select Sector Index, providing concentrated exposure to US financial sector companies including banks, insurance firms, and diversified financials.',
}

function etfDescription(sym: string, name: string, sector: string | null): string {
  return ETF_DESCRIPTIONS[sym] ??
    `${name} (${sym}) is a${sector ? ' ' + sector.toLowerCase() : 'n'} exchange-traded fund providing investors with diversified market exposure. ETF price and performance data are tracked daily on MetricsHour.`
}

// ── SEO ───────────────────────────────────────────────────────────────────────
const _change = computed(() => asset.value?.price?.change_pct ?? null)

const _seoTitle = computed(() => {
  if (!asset.value) return `${symbol} ETF — MetricsHour`
  const name  = asset.value.name
  const price = asset.value.price?.close
  const chg   = _change.value
  if (price != null && chg != null) {
    return `${symbol} Today: $${price.toFixed(2)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%) — ${name} — MetricsHour`
  }
  return `${symbol} — ${name} Price & Data — MetricsHour`
})

const _seoDesc = computed(() => {
  if (!asset.value) return ''
  const name  = asset.value.name
  const price = asset.value.price?.close
  const chg   = _change.value
  if (price != null && chg != null) {
    return `${name} (${symbol}) at $${price.toFixed(2)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}% today). Live ETF price, AUM, and chart on MetricsHour.`
  }
  return `${name} (${symbol}) live price, assets under management, and performance history on MetricsHour.`
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: `https://metricshour.com/etfs/${symbol.toLowerCase()}/`,
  ogType: 'website',
  ogImage: 'https://cdn.metricshour.com/og/section/etfs.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterImage: 'https://cdn.metricshour.com/og/section/etfs.png',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/etfs/${symbol.toLowerCase()}/` }],
  script: asset.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: `${asset.value.name} (${asset.value.symbol}) ETF — MetricsHour`,
        url: `https://metricshour.com/etfs/${symbol.toLowerCase()}/`,
        description: `${asset.value.name} (${asset.value.symbol}) ETF price, performance, and data. Exchange-traded fund listed on ${asset.value.exchange || 'US exchanges'}.`,
        datePublished: '2026-04-01',
        dateModified: asset.value.price?.timestamp ? asset.value.price.timestamp.slice(0, 10) : new Date().toISOString().slice(0, 10),
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'ETFs', item: 'https://metricshour.com/etfs/' },
            { '@type': 'ListItem', position: 3, name: asset.value.symbol, item: `https://metricshour.com/etfs/${symbol.toLowerCase()}/` },
          ],
        },
        mainEntity: {
          '@type': 'FinancialProduct',
          name: asset.value.name,
          alternateName: asset.value.symbol,
          description: `${asset.value.name} is an exchange-traded fund (ETF)${asset.value.sector ? ` in the ${asset.value.sector} category` : ''}, traded under the ticker ${asset.value.symbol}.`,
          provider: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com' },
          ...(asset.value.price?.close != null ? {
            offers: {
              '@type': 'Offer',
              price: asset.value.price.close,
              priceCurrency: 'USD',
            },
          } : {}),
        },
      }),
    },
  ] : [],
})))
</script>
