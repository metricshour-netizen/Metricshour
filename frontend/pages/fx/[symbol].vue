<template>
  <div>
    <!-- Hero band -->
    <div class="bg-gradient-to-b from-[#001209] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/fx/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Forex
        </NuxtLink>

        <div v-if="pending" class="h-20 flex items-center">
          <div class="space-y-2">
            <div class="h-8 w-40 bg-[#1f2937] rounded animate-pulse"/>
            <div class="h-4 w-64 bg-[#1f2937] rounded animate-pulse"/>
          </div>
        </div>
        <div v-else-if="error || !asset" class="text-red-400 text-sm py-6">Currency pair not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 rounded-xl bg-emerald-900/30 border border-emerald-800/40 flex items-center justify-center text-2xl shrink-0">
                {{ pairFlags(asset.symbol) }}
              </div>
              <div>
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h1 class="text-3xl font-extrabold text-white tracking-tight font-mono">{{ asset.symbol }}</h1>
                  <span class="text-[10px] font-bold text-emerald-400/80 bg-emerald-400/10 border border-emerald-800/40 px-2 py-1 rounded-md">FX</span>
                  <span class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded-md">FOREX</span>
                </div>
                <p class="text-gray-300 font-medium">{{ asset.name }}</p>
                <p class="text-gray-600 text-xs mt-0.5">Foreign Exchange · Updated every 15 minutes</p>
              </div>
            </div>
            <div class="text-right">
              <div class="text-4xl font-extrabold text-white tabular-nums tracking-tight font-mono">
                {{ asset.price ? fmtRate(asset.price.close) : '—' }}
              </div>
              <div v-if="asset.price?.change_pct != null" class="text-sm mt-1 tabular-nums"
                   :class="asset.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ asset.price.change_pct >= 0 ? '▲' : '▼' }}
                {{ Math.abs(asset.price.change_pct).toFixed(4) }}%
                <span class="text-gray-600 font-normal ml-1">today</span>
              </div>
              <div class="text-xs text-gray-600 mt-1">
                {{ asset.price?.timestamp ? 'Updated ' + fmtTs(asset.price.fetched_at || asset.price.timestamp) : 'Awaiting rate feed' }}
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
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Day Open</div>
          <div class="text-white font-bold text-lg font-mono">{{ asset.price?.open ? fmtRate(asset.price.open) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Day High</div>
          <div class="text-white font-bold text-lg font-mono">{{ asset.price?.high ? fmtRate(asset.price.high) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Day Low</div>
          <div class="text-white font-bold text-lg font-mono">{{ asset.price?.low ? fmtRate(asset.price.low) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Quote</div>
          <div class="text-white font-bold text-lg">{{ asset.currency || quoteCurrency(asset.symbol) }}</div>
        </div>
      </div>

      <!-- Summary -->
      <div v-if="pageSummary?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-4 text-sm text-gray-400 leading-relaxed page-summary">
        {{ pageSummary.summary }}
      </div>

      <!-- Insights (rotating) -->
      <div v-if="pageInsights?.length" class="mb-4">
        <div class="relative border rounded-lg p-4 overflow-hidden bg-[#0d1520] border-emerald-900/50 page-insight-latest">
          <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"/>
          <div class="flex items-start gap-3">
            <span class="text-base mt-0.5 shrink-0 text-emerald-400">◆</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1 flex-wrap">
                <span class="text-[10px] font-bold uppercase tracking-widest text-emerald-400">MetricsHour Intelligence</span>
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
            class="w-full px-3 py-2 text-[10px] text-gray-600 hover:text-emerald-400 bg-[#0a0d14] border-t border-[#1a2030] transition-colors text-left"
            @click="showAllInsights = !showAllInsights"
          >
            {{ showAllInsights ? '↑ Show less' : `↓ Read more (${pageInsights.length - 3} more insights)` }}
          </button>
        </div>
      </div>

      <!-- Rate chart -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4 mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-base font-bold text-white">Rate History</h2>
          <div class="flex gap-1">
            <button
              v-for="r in availableRanges"
              :key="r.label"
              @click="activeRange = r.days"
              class="text-xs px-2 py-0.5 rounded transition-colors"
              :class="activeRange === r.days ? 'bg-emerald-600 text-white' : 'text-gray-500 hover:text-gray-300'"
            >{{ r.label }}</button>
          </div>
        </div>
        <EChartLine v-if="chartOption" :option="chartOption" height="260px" />
        <div v-else class="h-[260px] flex items-center justify-center text-gray-600 text-sm">
          {{ pricesRaw?.length ? 'Rate history building — check back in a few days.' : 'No rate data yet.' }}
        </div>
      </div>

      <!-- About -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-3">About {{ asset.symbol }}</h2>
        <p class="text-gray-400 text-sm leading-relaxed">{{ fxDescription(asset.symbol, asset.name) }}</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <NuxtLink to="/fx/" class="text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-800/40 px-3 py-1.5 rounded-lg transition-colors">
            ← All Forex
          </NuxtLink>
          <NuxtLink v-if="baseCountry" :to="`/countries/${baseCountry.code}/`" class="text-xs text-gray-400 hover:text-gray-300 border border-[#1f2937] px-3 py-1.5 rounded-lg transition-colors">
            {{ FLAG_MAP[baseCcy] || '' }} {{ baseCountry.name }} →
          </NuxtLink>
          <NuxtLink v-if="quoteCountry" :to="`/countries/${quoteCountry.code}/`" class="text-xs text-gray-400 hover:text-gray-300 border border-[#1f2937] px-3 py-1.5 rounded-lg transition-colors">
            {{ FLAG_MAP[quoteCcy] || '' }} {{ quoteCountry.name }} →
          </NuxtLink>
          <NuxtLink to="/rates/" class="text-xs text-gray-400 hover:text-gray-300 border border-[#1f2937] px-3 py-1.5 rounded-lg transition-colors">
            Interest Rates →
          </NuxtLink>
        </div>
      </div>

      <!-- Related Currency Pairs -->
      <div v-if="relatedFx?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-3">More Currency Pairs</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <NuxtLink
            v-for="p in relatedFx"
            :key="p.symbol"
            :to="`/fx/${p.symbol.toLowerCase()}/`"
            class="flex items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-800/40 rounded-lg px-3 py-2.5 transition-colors group"
          >
            <span class="text-sm">{{ pairFlags(p.symbol) }}</span>
            <div class="min-w-0">
              <div class="text-xs font-bold text-white group-hover:text-emerald-400 transition-colors font-mono">{{ p.symbol }}</div>
              <div class="text-[10px] text-gray-600 truncate">{{ p.name }}</div>
            </div>
          </NuxtLink>
        </div>
        <div class="mt-3">
          <NuxtLink to="/fx/" class="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">View all forex pairs →</NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center mb-8">Data: Tiingo · FRED · ECB</p>

      <!-- Newsletter -->
      <div class="border border-gray-800 rounded-xl p-6 bg-gray-900/40">
        <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">FX moves + macro context, every week.</p>
        <p class="text-xs text-gray-500 mb-4">Currency trends, central bank policy, economic shifts — free.</p>
        <NewsletterCapture :source="`fx_page_${symbol}`" button-text="Subscribe free" />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()
const symbol = (route.params.symbol as string).toUpperCase()

const { data: asset, pending, error } = await useAsyncData(
  `fx-${symbol}`,
  () => get<any>(`/api/assets/${symbol}`).catch(() => null),
)
if (!asset.value) throw createError({ statusCode: 404, statusMessage: 'Currency pair not found' })

const { data: pageSummary } = useAsyncData(
  `summary-fx-${symbol}`,
  () => get<any>(`/api/summaries/fx/${symbol}`).catch(() => null),
  { server: false },
)

const { data: pageInsights } = useAsyncData(
  `insights-fx-${symbol}`,
  () => get<any[]>(`/api/insights/fx/${symbol}`).catch(() => []),
  { server: false },
)

const { data: pricesRaw } = useAsyncData(
  `fx-prices-${symbol}`,
  () => get<any[]>(`/api/assets/${symbol}/prices?interval=1d&limit=365`).catch(() => []),
  { server: false },
)

// ── Currency → country mapping ───────────────────────────────────────────────
const CURRENCY_COUNTRY: Record<string, { code: string; name: string }> = {
  USD: { code: 'us', name: 'United States' }, EUR: { code: 'de', name: 'Eurozone' },
  GBP: { code: 'gb', name: 'United Kingdom' }, JPY: { code: 'jp', name: 'Japan' },
  CHF: { code: 'ch', name: 'Switzerland' }, AUD: { code: 'au', name: 'Australia' },
  CAD: { code: 'ca', name: 'Canada' }, NZD: { code: 'nz', name: 'New Zealand' },
  CNY: { code: 'cn', name: 'China' }, HKD: { code: 'hk', name: 'Hong Kong' },
  SEK: { code: 'se', name: 'Sweden' }, NOK: { code: 'no', name: 'Norway' },
  DKK: { code: 'dk', name: 'Denmark' }, SGD: { code: 'sg', name: 'Singapore' },
  MXN: { code: 'mx', name: 'Mexico' }, BRL: { code: 'br', name: 'Brazil' },
  INR: { code: 'in', name: 'India' }, KRW: { code: 'kr', name: 'South Korea' },
  ZAR: { code: 'za', name: 'South Africa' }, TRY: { code: 'tr', name: 'Turkey' },
}
const baseCcy = symbol.slice(0, 3)
const quoteCcy = symbol.slice(3, 6)
const baseCountry = CURRENCY_COUNTRY[baseCcy] ?? null
const quoteCountry = CURRENCY_COUNTRY[quoteCcy] ?? null

// ── Related FX pairs ────────────────────────────────────────────────────────
const { public: { apiBase: _apiBase } } = useRuntimeConfig()
const { data: relatedFx } = await useAsyncData(
  `related-fx-${symbol}`,
  async () => {
    const all = await $fetch<any[]>('/api/assets', { baseURL: _apiBase, params: { type: 'fx', limit: 12 } }).catch(() => [])
    return (all || []).filter((a: any) => a.symbol !== symbol).slice(0, 6)
  },
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
  const color  = isUp ? '#34d399' : '#f87171'
  return {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 8, bottom: 40, containLabel: true },
    tooltip: { trigger: 'axis', backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#fff', fontSize: 11 }, formatter: (p: any) => `${p[0].axisValue}<br/>${fmtRate(p[0].value)}` },
    xAxis: { type: 'category', data: dates, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, interval: Math.floor(slice.length / 5) } },
    yAxis: { type: 'value', scale: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => fmtRate(v) }, splitLine: { lineStyle: { color: '#1f2937' } } },
    series: [{ type: 'line', data: closes, smooth: true, symbol: 'none', lineStyle: { color, width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '33' }, { offset: 1, color: color + '00' }] } } }],
  }
})

// ── Helpers ───────────────────────────────────────────────────────────────────
const FLAG_MAP: Record<string, string> = {
  USD: '🇺🇸', EUR: '🇪🇺', GBP: '🇬🇧', JPY: '🇯🇵', CHF: '🇨🇭',
  AUD: '🇦🇺', CAD: '🇨🇦', NZD: '🇳🇿', CNY: '🇨🇳', HKD: '🇭🇰',
  SEK: '🇸🇪', NOK: '🇳🇴', DKK: '🇩🇰', SGD: '🇸🇬', MXN: '🇲🇽',
  BRL: '🇧🇷', INR: '🇮🇳', KRW: '🇰🇷', ZAR: '🇿🇦', TRY: '🇹🇷',
}

function pairFlags(sym: string): string {
  const base  = sym.slice(0, 3)
  const quote = sym.slice(3, 6)
  return (FLAG_MAP[base] ?? '🏳️') + (FLAG_MAP[quote] ?? '🏳️')
}

function quoteCurrency(sym: string): string {
  return sym.slice(3, 6) || '—'
}

function fmtRate(v: number): string {
  if (v >= 100)  return v.toFixed(2)
  if (v >= 1)    return v.toFixed(4)
  return v.toFixed(6)
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

const FX_DESCRIPTIONS: Record<string, string> = {
  EURUSD: 'EUR/USD is the most traded currency pair in the world, representing the exchange rate between the Euro and the US Dollar. It reflects monetary policy divergence between the European Central Bank (ECB) and the US Federal Reserve.',
  GBPUSD: 'GBP/USD (Sterling / Dollar) is one of the oldest traded currency pairs, known as "Cable" — a reference to the transatlantic telegraph cable used for quotes in the 19th century. It is heavily influenced by Bank of England policy and UK economic data.',
  USDJPY: 'USD/JPY is the second most traded currency pair globally, reflecting the exchange rate between the US Dollar and the Japanese Yen. It is closely watched as a risk sentiment indicator, with JPY often strengthening during periods of global uncertainty.',
  USDCHF: 'USD/CHF (Dollar / Swiss Franc) reflects the exchange rate between the US Dollar and the Swiss Franc. The Swiss Franc is considered a safe-haven currency, often appreciating during geopolitical stress and global market volatility.',
  AUDUSD: 'AUD/USD (Aussie Dollar) is heavily influenced by commodity prices, particularly iron ore and coal, which are Australia\'s largest exports. It serves as a proxy for risk sentiment and exposure to the Chinese economy.',
  USDCAD: 'USD/CAD (Dollar / Loonie) reflects the relationship between the US Dollar and the Canadian Dollar. It is closely tied to crude oil prices, as Canada is one of the world\'s largest oil exporters.',
  NZDUSD: 'NZD/USD (Kiwi Dollar) tracks the exchange rate between the New Zealand Dollar and the US Dollar. It is influenced by dairy prices, the Reserve Bank of New Zealand\'s policy, and general risk sentiment.',
  EURGBP: 'EUR/GBP tracks the exchange rate between the Euro and the British Pound. It reflects economic and political dynamics between the Eurozone and the UK, and has been particularly volatile since Brexit.',
  USDBRL: 'USD/BRL tracks the exchange rate between the US Dollar and the Brazilian Real. The Brazilian Real is an emerging market currency sensitive to commodity prices, political stability, and global risk appetite.',
  USDMXN: 'USD/MXN tracks the exchange rate between the US Dollar and the Mexican Peso. The Peso is one of the most liquid emerging market currencies and is closely tied to US-Mexico trade relations and Federal Reserve policy.',
}

function fxDescription(sym: string, name: string): string {
  return FX_DESCRIPTIONS[sym] ??
    `${name} (${sym}) is a currency pair tracked on the global foreign exchange market. Exchange rates are updated every 15 minutes during weekday trading hours on MetricsHour.`
}

// ── SEO ───────────────────────────────────────────────────────────────────────
const _change = computed(() => asset.value?.price?.change_pct ?? null)

const _seoTitle = computed(() => {
  if (!asset.value) return `${symbol} Exchange Rate — MetricsHour`
  const name  = asset.value.name
  const price = asset.value.price?.close
  const chg   = _change.value
  if (price != null && chg != null) {
    return `${symbol} Rate Today: ${fmtRate(price)} (${chg >= 0 ? '+' : ''}${chg.toFixed(4)}%) — MetricsHour`
  }
  return `${symbol} — ${name} Live Rate — MetricsHour`
})

const _seoDesc = computed(() => {
  if (!asset.value) return ''
  const name  = asset.value.name
  const price = asset.value.price?.close
  const chg   = _change.value
  if (price != null && chg != null) {
    return `${name} (${symbol}) at ${fmtRate(price)} (${chg >= 0 ? '+' : ''}${chg.toFixed(4)}% today). Live forex rate, history chart, and macro context on MetricsHour.`
  }
  return `${name} (${symbol}) live exchange rate and history chart. Updated every 15 minutes on MetricsHour.`
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: `https://metricshour.com/fx/${symbol.toLowerCase()}/`,
  ogType: 'website',
  ogImage: 'https://cdn.metricshour.com/og/section/fx.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterImage: 'https://cdn.metricshour.com/og/section/fx.png',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/fx/${symbol.toLowerCase()}/` }],
})))
</script>
