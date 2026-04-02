<template>
  <div>
    <!-- Hero band -->
    <div class="bg-gradient-to-b from-[#110a1f] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/markets/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Markets
        </NuxtLink>

        <div v-if="pending" class="h-20 flex items-center">
          <div class="space-y-2">
            <div class="h-8 w-40 bg-[#1f2937] rounded animate-pulse"/>
            <div class="h-4 w-64 bg-[#1f2937] rounded animate-pulse"/>
          </div>
        </div>
        <div v-else-if="error || !index" class="text-red-400 text-sm py-6">Index not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <!-- Left: identity -->
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 rounded-xl bg-purple-900/30 border border-purple-800/40 flex items-center justify-center text-2xl shrink-0">
                {{ regionIcon(index.sector) }}
              </div>
              <div>
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h1 class="text-3xl font-extrabold text-white tracking-tight">{{ index.symbol }}</h1>
                  <span class="text-[10px] font-bold text-purple-400/80 bg-purple-400/10 border border-purple-800/40 px-2 py-1 rounded-md">INDEX</span>
                  <span v-if="index.exchange" class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded-md">{{ index.exchange }}</span>
                </div>
                <p class="text-gray-300 font-medium">{{ index.name }}</p>
                <p class="text-gray-600 text-xs mt-0.5">{{ index.sector }} · Global Markets Index</p>
              </div>
            </div>

            <!-- Right: price -->
            <div class="text-right">
              <div class="text-4xl font-extrabold text-white tabular-nums tracking-tight">
                {{ index.price ? fmtPrice(index.price.close) : '—' }}
              </div>
              <div v-if="index.price?.open" class="text-sm mt-1 tabular-nums"
                   :class="index.price.close >= index.price.open ? 'text-emerald-400' : 'text-red-400'">
                {{ index.price.close >= index.price.open ? '▲' : '▼' }}
                {{ Math.abs(((index.price.close - index.price.open) / index.price.open) * 100).toFixed(2) }}%
              </div>
              <div class="text-xs text-gray-600 mt-1">
                {{ index.price?.timestamp ? 'Updated ' + fmtTs(index.price.fetched_at || index.price.timestamp) : 'Awaiting price feed' }}
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-8" v-if="index">

      <!-- Stats row -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Exchange</div>
          <div class="text-white font-bold text-lg">{{ index.exchange || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Region</div>
          <div class="text-white font-bold text-lg">{{ index.sector || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Day Open</div>
          <div class="text-white font-bold text-lg">{{ index.price?.open ? fmtPrice(index.price.open) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Day Range</div>
          <div class="text-white font-bold text-sm leading-snug mt-1">
            {{ index.price?.low && index.price?.high ? `${fmtPrice(index.price.low)} — ${fmtPrice(index.price.high)}` : '—' }}
          </div>
        </div>
      </div>

      <!-- Summary + Insights -->
      <div v-if="pageSummary?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-4 text-sm text-gray-400 leading-relaxed">
        {{ pageSummary.summary }}
      </div>
      <!-- Daily Insights -->
      <div v-if="pageInsights?.length" class="mb-4">
        <!-- Latest: full card -->
        <div class="relative border rounded-lg p-4 overflow-hidden bg-[#0d1520] border-purple-900/50 page-insight-latest">
          <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-purple-500/40 to-transparent"/>
          <div class="flex items-start gap-3">
            <span class="text-base mt-0.5 shrink-0 text-purple-400">◆</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1 flex-wrap">
                <span class="text-[10px] font-bold uppercase tracking-widest text-purple-400">MetricsHour Intelligence</span>
                <span class="text-[10px] text-gray-700 ml-auto">{{ new Date(pageInsights[0].generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</span>
              </div>
              <p class="text-sm text-gray-300 leading-relaxed">{{ pageInsights[0].summary }}</p>
            </div>
          </div>
        </div>
        <!-- History: compact scrollable log -->
        <div v-if="pageInsights.length > 1" class="mt-1.5 border border-[#1a2030] rounded-lg overflow-hidden">
          <div class="divide-y divide-[#131b27]">
            <div
              v-for="(insight, i) in pageInsights.slice(1)"
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
            class="w-full px-3 py-2 text-[10px] text-gray-600 hover:text-purple-400 bg-[#0a0d14] border-t border-[#1a2030] transition-colors text-left"
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
              :class="activeRange === r.days ? 'bg-purple-600 text-white' : 'text-gray-500 hover:text-gray-300'"
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
        <h2 class="text-base font-bold text-white mb-3">About {{ index.symbol }}</h2>
        <p class="text-gray-400 text-sm leading-relaxed">
          {{ indexDescription(index.symbol) }}
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <NuxtLink to="/markets/" class="text-xs text-purple-400 hover:text-purple-300 border border-purple-800/40 px-3 py-1.5 rounded-lg transition-colors">
            ← All Markets
          </NuxtLink>
          <NuxtLink to="/markets?tab=stock" class="text-xs text-gray-400 hover:text-gray-300 border border-[#1f2937] px-3 py-1.5 rounded-lg transition-colors">
            Browse Stocks →
          </NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center">Data: Marketstack · FRED · NYSE · NASDAQ · CME</p>

      <!-- Newsletter -->
      <div class="mt-8 border border-gray-800 rounded-xl p-6 bg-gray-900/40">
        <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">Market moves + macro context, every week.</p>
        <p class="text-xs text-gray-500 mb-4">Index performance, trade flows, economic shifts — free.</p>
        <NewsletterCapture :source="`index_page_${symbol}`" button-text="Subscribe free" />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()
const symbol = (route.params.symbol as string).toUpperCase()

const { data: index, pending, error } = await useAsyncData(
  `index-${symbol}`,
  () => get<any>(`/api/assets/${symbol}`).catch(() => null),
)
if (!index.value) throw createError({ statusCode: 404, statusMessage: 'Index not found' })

const { data: pageSummary } = useAsyncData(
  `summary-index-${symbol}`,
  () => get<any>(`/api/summaries/index/${symbol}`).catch(() => null),
  { server: false },
)

const { data: pageInsights } = useAsyncData(
  `insights-index-${symbol}`,
  () => get<any[]>(`/api/insights/index/${symbol}`).catch(() => []),
  { server: false },
)

const { data: pricesRaw } = useAsyncData(
  `index-prices-${symbol}`,
  () => get<any[]>(`/api/assets/${symbol}/prices?interval=1d&limit=365`).catch(() => []),
  { server: false },
)

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
  const color  = isUp ? '#a78bfa' : '#f87171'
  return {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 8, bottom: 40, containLabel: true },
    tooltip: { trigger: 'axis', backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#fff', fontSize: 11 }, formatter: (p: any) => `${p[0].axisValue}<br/>${fmtPrice(p[0].value)}` },
    xAxis: { type: 'category', data: dates, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, interval: Math.floor(slice.length / 5) } },
    yAxis: { type: 'value', scale: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => fmtPrice(v) }, splitLine: { lineStyle: { color: '#1f2937' } } },
    series: [{ type: 'line', data: closes, smooth: true, symbol: 'none', lineStyle: { color, width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '33' }, { offset: 1, color: color + '00' }] } } }],
  }
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtPrice(v: number): string {
  if (v >= 10000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1000)  return v.toLocaleString(undefined, { maximumFractionDigits: 1 })
  if (v >= 1)     return v.toFixed(2)
  return v.toFixed(4)
}

function fmtTs(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
  if (d.getUTCHours() === 0 && d.getUTCMinutes() === 0) return date
  return date + ' · ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC'
}

function regionIcon(region: string | null): string {
  const map: Record<string, string> = { US: '🇺🇸', Europe: '🇪🇺', Asia: '🌏', Global: '🌐' }
  return map[region ?? ''] ?? '📊'
}

const INDEX_DESCRIPTIONS: Record<string, string> = {
  DJI:    'The Dow Jones Industrial Average (DJIA) tracks 30 large-cap US companies listed on the NYSE and NASDAQ. Founded in 1896, it is one of the oldest and most widely followed equity indices. Price-weighted.',
  SPX:    'The S&P 500 tracks 500 of the largest US-listed companies by market capitalisation. Market-cap weighted, it covers approximately 80% of the US equity market and is widely used as a benchmark for US large-cap performance.',
  NDX:    'The Nasdaq 100 tracks the 100 largest non-financial companies listed on the NASDAQ exchange. Heavily weighted toward technology, biotech, and consumer discretionary sectors.',
  RUT:    'The Russell 2000 Index measures the performance of approximately 2,000 small-cap US companies. It is the most widely quoted index for small-cap US equities.',
  VIX:    'The CBOE Volatility Index (VIX) measures the market\'s expectation of near-term volatility in the S&P 500. Often called the "fear gauge", it rises during market uncertainty and falls in calm conditions.',
  UKX:    'The FTSE 100 Index measures the performance of 100 companies listed on the London Stock Exchange with the highest market capitalisation. A key benchmark for UK equity performance.',
  DAX:    'The DAX (Deutscher Aktienindex) tracks 40 major German companies listed on the Frankfurt Stock Exchange. Performance index including dividends. Key benchmark for the German and European equity markets.',
  CAC:    'The CAC 40 is a benchmark French stock market index that tracks 40 of the largest publicly traded companies on Euronext Paris, measured by market capitalisation.',
  IBEX:   'The IBEX 35 is the benchmark stock market index of the Bolsa de Madrid, Spain\'s principal stock exchange, tracking the 35 most liquid Spanish stocks.',
  SMI:    'The Swiss Market Index (SMI) is Switzerland\'s blue-chip stock market index, comprising the 20 largest and most liquid stocks listed on the SIX Swiss Exchange.',
  NKY:    'The Nikkei 225 is a price-weighted index of 225 prominent stocks listed on the Tokyo Stock Exchange. Widely used as the main benchmark for the Japanese equity market.',
  HSI:    'The Hang Seng Index (HSI) tracks the largest companies on the Hong Kong Stock Exchange, covering approximately 65% of the exchange\'s total market capitalisation.',
  SHCOMP: 'The Shanghai Composite Index measures the performance of all stocks listed on the Shanghai Stock Exchange — A shares and B shares. Primary benchmark for mainland Chinese equities.',
  KOSPI:  'The KOSPI (Korea Composite Stock Price Index) is the primary benchmark for the Korea Exchange, tracking all common stocks listed on the market.',
  SENSEX: 'The BSE SENSEX (Sensitive Index) is a free-float market-weighted stock market index of 30 well-established and financially sound companies listed on the Bombay Stock Exchange.',
  ASX200: 'The ASX 200 is the benchmark Australian stock market index, tracking the 200 largest companies by market capitalisation listed on the Australian Securities Exchange.',
  MSCIW:  'The MSCI World Index tracks large and mid-cap equity performance across 23 developed market countries. Tracked here via the Vanguard Total World ETF (VT) as a proxy.',
  MSCIEM: 'The MSCI Emerging Markets Index captures large and mid-cap representation across 24 emerging market countries. Tracked here via the Vanguard FTSE Emerging Markets ETF (VWO) as a proxy.',
}

function indexDescription(symbol: string): string {
  return INDEX_DESCRIPTIONS[symbol] ??
    `${symbol} is a market index tracking a basket of securities. Indices provide a statistical measure of market performance for a group of assets, region, or sector.`
}

const config = useRuntimeConfig()
const r2PublicUrl = config.public.r2PublicUrl || 'https://cdn.metricshour.com'
const ogImageUrl = `${r2PublicUrl}/og/indices/${symbol.toLowerCase()}.png`

// ── SEO helpers — inject live price + change ──────────────────────────────────
const _change = computed(() => {
  const p = index.value?.price
  if (!p?.open || !p?.close) return null
  return ((p.close - p.open) / p.open) * 100
})

const _seoTitle = computed(() => {
  if (!index.value) return `${symbol} Index — MetricsHour`
  const name  = index.value.name
  const price = index.value.price?.close
  const chg   = _change.value
  if (price != null && chg != null) {
    return `${symbol} Today: ${fmtPrice(price)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%) — ${name} — MetricsHour`
  }
  return `${symbol} — ${name} Price & Data — MetricsHour`
})

const _seoDesc = computed(() => {
  if (!index.value) return ''
  const name  = index.value.name
  const price = index.value.price?.close
  const chg   = _change.value
  const base  = indexDescription(symbol).slice(0, 100)
  if (price != null && chg != null) {
    return `${name} (${symbol}) at ${fmtPrice(price)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}% today). ${base}`
  }
  return `${name} (${symbol}) price, chart, and market data. ${base}`
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: `https://metricshour.com/indices/${symbol.toLowerCase()}/`,
  ogType: 'website',
  ogImage: ogImageUrl,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  ogImageType: 'image/png',
  twitterCard: 'summary_large_image',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  twitterImage: ogImageUrl,
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/indices/${symbol.toLowerCase()}/` }],
  script: index.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: _seoTitle.value,
        url: `https://metricshour.com/indices/${symbol.toLowerCase()}/`,
        description: _seoDesc.value,
        speakable: {
          '@type': 'SpeakableSpecification',
          cssSelector: ['.page-summary', '.page-insight-latest'],
        },
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home',    item: 'https://metricshour.com/' },
            { '@type': 'ListItem', position: 2, name: 'Markets', item: 'https://metricshour.com/markets/' },
            { '@type': 'ListItem', position: 3, name: symbol,    item: `https://metricshour.com/indices/${symbol.toLowerCase()}/` },
          ],
        },
      }),
    },
    ...(index.value.price?.close ? [{
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Dataset',
        name: `${index.value.name} (${symbol}) Price Data`,
        description: `Current and historical price data for ${index.value.name}. Source: Marketstack.`,
        url: `https://metricshour.com/indices/${symbol.toLowerCase()}/`,
        creator: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com' },
        license: 'https://metricshour.com/terms/',
        keywords: [`${symbol} price today`, `${index.value.name} price`, `${symbol} index value`, `${index.value.name} performance`],
        mainEntity: { '@type': 'FinancialProduct', name: index.value.name, tickerSymbol: symbol },
        variableMeasured: [
          { '@type': 'PropertyValue', name: `${symbol} Price`,   value: String(index.value.price.close) },
          { '@type': 'PropertyValue', name: `${symbol} Day Open`, value: String(index.value.price.open) },
          { '@type': 'PropertyValue', name: `${symbol} Day High`, value: String(index.value.price.high) },
          { '@type': 'PropertyValue', name: `${symbol} Day Low`,  value: String(index.value.price.low) },
        ].filter(v => v.value !== 'undefined' && v.value !== 'null'),
      }),
    }] : []),
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: [
          {
            '@type': 'Question',
            name: `What is the ${index.value.name}?`,
            acceptedAnswer: { '@type': 'Answer', text: indexDescription(symbol) },
          },
          {
            '@type': 'Question',
            name: `What is ${symbol}'s current value?`,
            acceptedAnswer: {
              '@type': 'Answer',
              text: index.value.price?.close
                ? `${index.value.name} (${symbol}) is currently at ${fmtPrice(index.value.price.close)}${_change.value != null ? `, ${_change.value >= 0 ? 'up' : 'down'} ${Math.abs(_change.value).toFixed(2)}% today` : ''}. Prices are updated daily on MetricsHour.`
                : `${index.value.name} (${symbol}) price data is updated daily on MetricsHour.`,
            },
          },
          {
            '@type': 'Question',
            name: `What exchange is ${symbol} listed on?`,
            acceptedAnswer: {
              '@type': 'Answer',
              text: index.value.exchange
                ? `${index.value.name} is traded on ${index.value.exchange}.`
                : `${index.value.name} (${symbol}) is a market index tracking a basket of securities.`,
            },
          },
          {
            '@type': 'Question',
            name: `How does ${symbol} affect global markets?`,
            acceptedAnswer: {
              '@type': 'Answer',
              text: `${index.value.name} is a benchmark for ${index.value.sector ?? 'regional'} equities. Movements in ${symbol} are closely watched by investors globally as a barometer of economic health and market sentiment.`,
            },
          },
        ],
      }),
    },
  ] : [],
})))
const expandedInsights = ref<Set<string>>(new Set())
const showAllInsights = ref(false)
const toggleInsight = (key: string) => {
  const s = new Set(expandedInsights.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedInsights.value = s
}
</script>
