<template>
  <div>
    <!-- Hero -->
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/china/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">← China A-Shares</NuxtLink>

        <div v-if="pending" class="h-20 flex items-center">
          <div class="space-y-2">
            <div class="h-8 w-40 bg-[#1f2937] rounded animate-pulse"/>
            <div class="h-4 w-64 bg-[#1f2937] rounded animate-pulse"/>
          </div>
        </div>
        <div v-else-if="error || !stock" class="text-red-400 text-sm py-6">Stock not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-2xl shrink-0" aria-hidden="true">🇨🇳</div>
              <div>
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h1 class="text-3xl font-extrabold text-white tracking-tight">{{ stock.name }}</h1>
                  <span class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded-md">{{ stock.exchange }}</span>
                </div>
                <p class="text-gray-300 font-medium font-mono">{{ stock.symbol }}</p>
                <p class="text-xs text-gray-500 mt-1">China A-share · Priced in CNY ¥ · {{ stock.exchange === 'SHG' ? 'Shanghai Stock Exchange' : 'Shenzhen Stock Exchange' }}</p>
              </div>
            </div>

            <div class="text-right">
              <div class="text-4xl font-extrabold text-white tabular-nums tracking-tight">
                {{ stock.price ? `¥${stock.price.close.toFixed(2)}` : '—' }}
              </div>
              <div v-if="stock.price?.change_pct != null" class="text-sm font-bold tabular-nums mt-1"
                   :class="stock.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ stock.price.change_pct >= 0 ? '▲' : '▼' }} {{ Math.abs(stock.price.change_pct).toFixed(2) }}% today
              </div>
              <div class="text-xs text-gray-600 mt-1 flex items-center gap-2 flex-wrap">
                <template v-if="stock.price">Updated · <span class="font-mono text-emerald-700">{{ fmtTs(stock.price.fetched_at || stock.price.timestamp) }}</span></template>
                <template v-else>Awaiting price data</template>
                <span v-if="stock.market_open === true" class="inline-flex items-center gap-1 text-[10px] font-mono font-semibold text-emerald-400">
                  <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block"></span>Open
                </span>
                <span v-else-if="stock.market_open === false" class="inline-flex items-center gap-1 text-[10px] font-mono text-gray-600">
                  <span class="w-1.5 h-1.5 rounded-full bg-gray-600 inline-block"></span>Closed
                </span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main v-if="stock" class="max-w-7xl mx-auto px-4 py-8">
      <!-- Stats -->
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Exchange</div>
          <div class="text-white font-bold">{{ stock.exchange }}</div>
          <div class="text-[10px] text-gray-600 mt-0.5">{{ stock.exchange === 'SHG' ? 'Shanghai' : 'Shenzhen' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Currency</div>
          <div class="text-white font-bold">CNY ¥</div>
          <div class="text-[10px] text-gray-600 mt-0.5">Chinese Yuan</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Today's Range</div>
          <div v-if="stock.price?.high && stock.price?.low" class="text-white font-bold text-sm">
            ¥{{ stock.price.low.toFixed(2) }} – ¥{{ stock.price.high.toFixed(2) }}
          </div>
          <div v-else class="text-gray-600 font-bold">—</div>
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

      <!-- Price chart -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6">
        <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h2 class="text-sm font-bold text-white">Price History</h2>
          <div class="flex gap-2">
            <button
              v-for="iv in ['1d', '15m']" :key="iv"
              @click="interval = iv"
              class="text-xs px-3 py-1.5 rounded border transition-colors"
              :class="interval === iv ? 'border-emerald-600 text-emerald-400 bg-emerald-900/20' : 'border-[#1f2937] text-gray-500 hover:text-gray-300'"
            >{{ iv }}</button>
          </div>
        </div>
        <div v-if="pricesPending" class="h-64 flex items-center justify-center">
          <div class="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"/>
        </div>
        <div v-else-if="!chartData.length" class="h-32 flex items-center justify-center text-gray-600 text-sm">No price history yet</div>
        <div v-else ref="chartEl" class="h-64 w-full"/>
      </div>

      <!-- News -->
      <div v-if="newsItems?.length" class="mb-6">
        <h2 class="text-sm font-bold text-white mb-3">Latest News</h2>
        <div class="space-y-2">
          <a
            v-for="item in newsItems"
            :key="item.id"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="block bg-[#111827] border border-[#1f2937] hover:border-[#374151] rounded-lg p-4 transition-colors group"
          >
            <div class="flex items-start gap-3">
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-white group-hover:text-emerald-300 transition-colors leading-snug line-clamp-2">{{ item.title }}</p>
                <p class="text-xs text-gray-500 mt-1 line-clamp-2">{{ item.description }}</p>
                <div class="flex items-center gap-2 mt-2">
                  <span class="text-[10px] text-gray-600 font-medium uppercase tracking-wide">{{ item.source }}</span>
                  <span class="text-gray-700">·</span>
                  <span class="text-[10px] text-gray-700">{{ fmtNewsDate(item.published_at) }}</span>
                </div>
              </div>
              <span class="text-gray-700 group-hover:text-emerald-500 transition-colors shrink-0">↗</span>
            </div>
          </a>
        </div>
      </div>

      <!-- Related China A-Shares -->
      <div v-if="relatedChina?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-3">More China A-Shares</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <NuxtLink
            v-for="s in relatedChina"
            :key="s.symbol"
            :to="`/china/${s.symbol.toLowerCase()}/`"
            class="flex items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-800/40 rounded-lg px-3 py-2.5 transition-colors group"
          >
            <span class="text-base">🇨🇳</span>
            <div class="min-w-0">
              <div class="text-xs font-bold text-white group-hover:text-emerald-400 transition-colors truncate">{{ s.name }}</div>
              <div class="text-[10px] text-gray-600 font-mono">{{ s.symbol }} · {{ s.exchange }}</div>
            </div>
          </NuxtLink>
        </div>
        <div class="mt-3 flex gap-3">
          <NuxtLink to="/china/" class="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">View all China A-Shares →</NuxtLink>
          <NuxtLink to="/countries/cn/" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">🇨🇳 China macro data →</NuxtLink>
          <NuxtLink to="/markets/" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">Markets →</NuxtLink>
        </div>
      </div>

      <!-- FAQ -->
      <div class="mb-6">
        <h2 class="text-sm font-bold text-white mb-3">Frequently Asked Questions</h2>
        <div class="space-y-2">
          <div class="bg-[#111827] border border-[#1f2937] rounded-lg px-4 py-3">
            <p class="text-sm font-medium text-gray-300 mb-1">What exchange is {{ stock.name }} listed on?</p>
            <p class="text-sm text-gray-500 leading-relaxed">{{ stock.name }} ({{ stock.symbol }}) is listed on the {{ stock.exchange === 'SHG' ? 'Shanghai Stock Exchange (SSE)' : 'Shenzhen Stock Exchange (SZSE)' }}, one of mainland China's two major stock exchanges.</p>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-lg px-4 py-3">
            <p class="text-sm font-medium text-gray-300 mb-1">What currency are {{ stock.name }} shares traded in?</p>
            <p class="text-sm text-gray-500 leading-relaxed">{{ stock.name }} shares are denominated in Chinese Yuan (CNY ¥). All prices shown on this page are in CNY.</p>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-lg px-4 py-3">
            <p class="text-sm font-medium text-gray-300 mb-1">What is a China A-share stock?</p>
            <p class="text-sm text-gray-500 leading-relaxed">China A-shares are renminbi-denominated shares of mainland Chinese companies listed on the Shanghai or Shenzhen Stock Exchange. They are accessible to domestic investors and qualified foreign investors via the Stock Connect programme.</p>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-lg px-4 py-3">
            <p class="text-sm font-medium text-gray-300 mb-1">Where can I find {{ stock.name }} price history and market analysis?</p>
            <p class="text-sm text-gray-500 leading-relaxed">MetricsHour provides daily price data, interactive charts, and AI-generated market insights for {{ stock.name }} and 300+ China A-share stocks. Prices update daily after the Shanghai and Shenzhen markets close.</p>
          </div>
        </div>
      </div>

      <p class="text-xs text-gray-700 mt-4">Data: SSE · SZSE · Prices in CNY · Updated daily after Shanghai/Shenzhen market close (07:00 UTC)</p>
    </main>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const route = useRoute()
const symbol = computed(() => String(route.params.symbol).toUpperCase())
const { get } = useApi()
const { r2Fetch } = useR2Fetch()

const { data: stock, pending, error } = await useAsyncData(
  `china-${symbol.value}`,
  () => r2Fetch<any>(`snapshots/stocks/${symbol.value.toLowerCase()}.json`, `/api/assets/${symbol.value}`).catch(() => null),
)
if (!stock.value) throw createError({ statusCode: 404, statusMessage: 'China A-share not found' })

// ── Related China stocks (must be before server:false calls for SSR) ─────────
const { public: { apiBase: _apiBase } } = useRuntimeConfig()
const { data: relatedChina } = await useAsyncData(
  `related-china-${symbol.value}`,
  async () => {
    const all = await $fetch<any[]>('/api/assets', { baseURL: _apiBase, params: { type: 'stock', exchange: 'SHG', limit: 12 } }).catch(() => [])
    return (all || []).filter((a: any) => a.symbol !== symbol.value).slice(0, 6)
  },
)

const interval = ref('1d')

const { data: pricesRaw, pending: pricesPending } = useAsyncData(
  `china-prices-${symbol.value}`,
  () => get<any[]>(`/api/assets/${symbol.value}/prices`, { interval: interval.value, limit: 200 }).catch(() => []),
  { watch: [interval], server: false },
)

const { data: newsItems } = useAsyncData(
  `china-news-${symbol.value}`,
  () => get<any[]>(`/api/news/${symbol.value}`).catch(() => []),
  { server: false },
)

const { data: pageSummary } = useAsyncData(
  `summary-stock-${symbol.value}`,
  () => get<any>(`/api/summaries/stock/${symbol.value}`).catch(() => null),
  { server: false },
)

const { data: pageInsights } = useAsyncData(
  `insights-stock-${symbol.value}`,
  () => get<any[]>(`/api/insights/stock/${symbol.value}`).catch(() => []),
  { server: false },
)

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

function fmtInsightDate(ts: string): string {
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const chartData = computed(() => (pricesRaw.value ?? []).filter((p: any) => p.c != null))

const chartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

watch([chartData, chartEl], () => {
  if (!chartEl.value || !chartData.value.length) return
  if (!chart) chart = echarts.init(chartEl.value, 'dark')
  const prices = chartData.value
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 55, right: 15, top: 10, bottom: 30 },
    xAxis: { type: 'category', data: prices.map((p: any) => p.t.slice(0, 16).replace('T', ' ')), axisLabel: { color: '#4b5563', fontSize: 10 }, axisLine: { lineStyle: { color: '#1f2937' } } },
    yAxis: { type: 'value', axisLabel: { color: '#4b5563', fontSize: 10, formatter: (v: number) => `¥${v.toFixed(2)}` }, splitLine: { lineStyle: { color: '#1a2030' } } },
    tooltip: { trigger: 'axis', backgroundColor: '#111827', borderColor: '#1f2937', textStyle: { color: '#e5e7eb', fontSize: 12 }, formatter: (params: any) => `${params[0].axisValue}<br/>¥${params[0].value?.toFixed(2)}` },
    series: [{ type: 'line', data: prices.map((p: any) => p.c), smooth: true, symbol: 'none', lineStyle: { color: '#10b981', width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(16,185,129,0.2)' }, { offset: 1, color: 'rgba(16,185,129,0)' }] } } }],
  })
}, { immediate: true })

onUnmounted(() => chart?.dispose())

function fmtTs(ts: string): string {
  return new Date(ts).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short' })
}

function fmtNewsDate(ts: string): string {
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const ogImageUrl = computed(() => `https://cdn.metricshour.com/og/china/${symbol.value.toLowerCase()}.png`)

function _exchangeName(exch: string): string {
  return exch === 'SHG' ? 'Shanghai Stock Exchange' : 'Shenzhen Stock Exchange'
}

const _chinaTitle = computed(() => {
  if (!stock.value) return `${symbol.value} — China A-Share | MetricsHour`
  const s = stock.value
  const price = s.price?.close
  if (price != null) {
    return `${s.name} (${s.symbol}) Stock Price ¥${price.toFixed(2)} — MetricsHour`
  }
  return `${s.name} (${s.symbol}) — China A-Share Stock | MetricsHour`
})

const _chinaDesc = computed(() => {
  if (!stock.value) return ''
  const s = stock.value
  const exch = _exchangeName(s.exchange)
  const parts: string[] = [`${s.name} (${s.symbol}) is a China A-share stock listed on the ${exch}`]
  if (s.price?.close != null) {
    const chg = s.price.change_pct
    const chgStr = chg != null ? ` (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}% today)` : ''
    parts.push(`current price ¥${s.price.close.toFixed(2)}${chgStr}`)
  }
  parts.push('Live price chart, history, and AI insights on MetricsHour')
  return parts.join('. ') + '.'
})

const _hasContent = computed(() => !pending.value && !!stock.value)

useSeoMeta({
  title: _chinaTitle,
  description: _chinaDesc,
  ogTitle: _chinaTitle,
  ogDescription: _chinaDesc,
  ogUrl: computed(() => `https://metricshour.com/china/${symbol.value.toLowerCase()}/`),
  ogType: 'website',
  ogImage: ogImageUrl,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterTitle: _chinaTitle,
  twitterDescription: _chinaDesc,
  twitterImage: ogImageUrl,
  robots: computed(() => _hasContent.value
    ? 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1'
    : 'noindex, follow'),
})
useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/china/${symbol.value.toLowerCase()}/` }],
  script: stock.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: [
          {
            '@type': 'Question',
            name: `What exchange is ${stock.value.name} listed on?`,
            acceptedAnswer: { '@type': 'Answer', text: `${stock.value.name} (${stock.value.symbol}) is listed on the ${stock.value.exchange === 'SHG' ? 'Shanghai Stock Exchange (SSE)' : 'Shenzhen Stock Exchange (SZSE)'}, one of mainland China's two major stock exchanges.` },
          },
          {
            '@type': 'Question',
            name: `What currency are ${stock.value.name} shares traded in?`,
            acceptedAnswer: { '@type': 'Answer', text: `${stock.value.name} shares are denominated in Chinese Yuan (CNY ¥). All prices are quoted in CNY.` },
          },
          {
            '@type': 'Question',
            name: 'What is a China A-share stock?',
            acceptedAnswer: { '@type': 'Answer', text: "China A-shares are renminbi-denominated shares of mainland Chinese companies listed on the Shanghai or Shenzhen Stock Exchange. They are accessible to domestic investors and qualified foreign investors via the Stock Connect programme." },
          },
          {
            '@type': 'Question',
            name: `Where can I find ${stock.value.name} price history and market analysis?`,
            acceptedAnswer: { '@type': 'Answer', text: `MetricsHour provides daily price data, interactive charts, and AI-generated market insights for ${stock.value.name} and 300+ China A-share stocks at metricshour.com/china/${symbol.value.toLowerCase()}/.` },
          },
        ],
      }),
    },
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: _chinaTitle.value,
        url: `https://metricshour.com/china/${symbol.value.toLowerCase()}/`,
        description: _chinaDesc.value,
        datePublished: '2026-04-03',
        dateModified: stock.value.price?.timestamp ? stock.value.price.timestamp.slice(0, 10) : new Date().toISOString().slice(0, 10),
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'China A-Shares', item: 'https://metricshour.com/china/' },
            { '@type': 'ListItem', position: 3, name: stock.value.name, item: `https://metricshour.com/china/${symbol.value.toLowerCase()}/` },
          ],
        },
        mainEntity: {
          '@type': 'Corporation',
          name: stock.value.name,
          tickerSymbol: stock.value.symbol,
          description: `${stock.value.name} is a China A-share stock listed on the ${_exchangeName(stock.value.exchange)} (${stock.value.exchange}). Priced in CNY.`,
        },
      }),
    },
  ] : [],
})))
</script>
