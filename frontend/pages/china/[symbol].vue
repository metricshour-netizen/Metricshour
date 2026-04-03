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
              <div class="text-xs text-gray-600 mt-1">
                <template v-if="stock.price">Updated · <span class="font-mono text-emerald-700">{{ fmtTs(stock.price.fetched_at || stock.price.timestamp) }}</span></template>
                <template v-else>Awaiting price data</template>
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

      <p class="text-xs text-gray-700 mt-4">Data: Tiingo · Prices in CNY · Updated daily after Shanghai/Shenzhen market close (07:00 UTC)</p>
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

const { data: stock, pending, error } = useAsyncData(
  `china-${symbol.value}`,
  () => get<any>(`/api/assets/${symbol.value}`).catch(() => null),
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

useSeoMeta({
  title: computed(() => stock.value ? `${stock.value.name} (${stock.value.symbol}) — China A-Share | MetricsHour` : 'China A-Share | MetricsHour'),
  description: computed(() => stock.value ? `${stock.value.name} stock price and data. Listed on ${stock.value.exchange}. Priced in CNY.` : ''),
  ogImage: ogImageUrl,
  twitterCard: 'summary_large_image',
  twitterImage: ogImageUrl,
})
useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/china/${symbol.value.toLowerCase()}/` }],
  script: stock.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: `${stock.value.name} (${stock.value.symbol}) — China A-Share | MetricsHour`,
        url: `https://metricshour.com/china/${symbol.value.toLowerCase()}/`,
        description: `${stock.value.name} stock price and data. Listed on the ${stock.value.exchange === 'SHG' ? 'Shanghai Stock Exchange' : 'Shenzhen Stock Exchange'} (${stock.value.exchange}). Priced in CNY.`,
        datePublished: '2026-04-03',
        dateModified: stock.value.price?.timestamp ? stock.value.price.timestamp.slice(0, 10) : new Date().toISOString().slice(0, 10),
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'China A-Shares', item: 'https://metricshour.com/china/' },
            { '@type': 'ListItem', position: 3, name: stock.value.symbol, item: `https://metricshour.com/china/${symbol.value.toLowerCase()}/` },
          ],
        },
        mainEntity: {
          '@type': 'Corporation',
          name: stock.value.name,
          tickerSymbol: stock.value.symbol,
          description: `${stock.value.name} is a China A-share stock listed on the ${stock.value.exchange === 'SHG' ? 'Shanghai Stock Exchange' : 'Shenzhen Stock Exchange'}.`,
        },
      }),
    },
  ] : [],
})))
</script>
