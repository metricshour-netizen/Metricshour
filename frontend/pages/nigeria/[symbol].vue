<template>
  <div>
    <!-- Hero -->
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/nigeria/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">← Nigerian Stocks</NuxtLink>

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
              <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-2xl shrink-0" aria-hidden="true">🇳🇬</div>
              <div>
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h1 class="text-3xl font-extrabold text-white tracking-tight">{{ stock.name }}</h1>
                  <span class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded-md">{{ stock.exchange }}</span>
                  <span v-if="stock.sector" class="text-xs border border-emerald-800 text-emerald-400 px-2 py-1 rounded-md">{{ stock.sector }}</span>
                </div>
                <p class="text-gray-300 font-medium font-mono">{{ stock.symbol }}</p>
                <p class="text-xs text-gray-500 mt-1">
                  <template v-if="isLSE">LSE dual-listed · Priced in GBp (pence) · London Stock Exchange</template>
                  <template v-else>NGX-listed · Priced in NGN ₦ · Nigerian Exchange Group</template>
                </p>
              </div>
            </div>

            <div class="text-right">
              <div class="text-4xl font-extrabold text-white tabular-nums tracking-tight">
                <template v-if="stock.price">
                  {{ priceFmt(stock.price.close) }}
                </template>
                <template v-else>—</template>
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
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Exchange</div>
          <div class="text-white font-bold">{{ stock.exchange }}</div>
          <div class="text-[10px] text-gray-600 mt-0.5">{{ isLSE ? 'London Stock Exchange' : 'Nigerian Exchange' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Currency</div>
          <div class="text-white font-bold">{{ isLSE ? 'GBp' : 'NGN ₦' }}</div>
          <div class="text-[10px] text-gray-600 mt-0.5">{{ isLSE ? 'British pence' : 'Nigerian Naira' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Sector</div>
          <div class="text-white font-bold text-sm">{{ stock.sector || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Today's Range</div>
          <div v-if="stock.price?.high && stock.price?.low" class="text-white font-bold text-sm">
            {{ priceFmt(stock.price.low) }} – {{ priceFmt(stock.price.high) }}
          </div>
          <div v-else class="text-gray-600 font-bold">—</div>
        </div>
      </div>

      <!-- Summary -->
      <div v-if="pageSummary?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-4 text-sm text-gray-400 leading-relaxed page-summary">
        {{ pageSummary.summary }}
      </div>

      <!-- Insights -->
      <div v-if="pageInsights?.length" class="mb-6">
        <div class="relative border rounded-lg p-4 overflow-hidden bg-[#0d1520] border-emerald-900/50 page-insight-latest">
          <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"/>
          <div class="flex items-start gap-3">
            <span class="text-base mt-0.5 shrink-0 text-emerald-500" aria-hidden="true">◆</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                <span class="text-[10px] font-bold uppercase tracking-widest text-emerald-500">MetricsHour Intelligence</span>
                <span class="text-[10px] text-gray-700 ml-auto">{{ fmtDate(pageInsights[featuredIdx].generated_at) }}</span>
              </div>
              <p class="text-sm leading-relaxed text-gray-200">{{ pageInsights[featuredIdx].summary }}</p>
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

      <!-- Price Chart -->
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
      <div v-if="newsItems?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6">
        <h2 class="text-base font-bold text-white mb-4">Latest News</h2>
        <div class="space-y-3">
          <a
            v-for="item in newsItems"
            :key="item.id"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="block group"
          >
            <div class="flex items-start gap-3 p-3 rounded-lg hover:bg-[#0d1117] transition-colors">
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-200 group-hover:text-emerald-400 transition-colors leading-snug line-clamp-2">{{ item.title }}</p>
                <div class="flex items-center gap-2 mt-1">
                  <span class="text-[10px] text-gray-600 font-medium">{{ item.source }}</span>
                  <span class="text-[10px] text-gray-700">·</span>
                  <span class="text-[10px] text-gray-600">{{ fmtDate(item.published_at) }}</span>
                </div>
              </div>
              <span class="text-gray-700 group-hover:text-emerald-600 transition-colors text-xs shrink-0 mt-0.5">↗</span>
            </div>
          </a>
        </div>
      </div>

      <!-- Nigeria context -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-4">Nigeria Market Context</h2>
        <div class="grid sm:grid-cols-2 gap-4">
          <div class="bg-[#0d1117] rounded-lg p-4">
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">About the NGX</div>
            <p class="text-xs text-gray-500 leading-relaxed">
              The Nigerian Exchange Group (NGX) is sub-Saharan Africa's third-largest bourse by market cap.
              Nigeria's economy — Africa's largest by GDP — is driven by oil & gas, banking, telecoms, and FMCG.
            </p>
          </div>
          <div v-if="isLSE" class="bg-[#0d1117] rounded-lg p-4">
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Dual-Listed Company</div>
            <p class="text-xs text-gray-500 leading-relaxed">
              {{ stock.name }} is dual-listed on the London Stock Exchange (LSE) and the Nigerian Exchange (NGX).
              LSE prices are quoted in GBp (pence) — divide by 100 for GBP sterling.
            </p>
          </div>
          <div v-else class="bg-[#0d1117] rounded-lg p-4">
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">NGX Listed</div>
            <p class="text-xs text-gray-500 leading-relaxed">
              {{ stock.name }} is listed on the Nigerian Exchange Group (NGX).
              Prices are quoted in Nigerian Naira (NGN ₦). Live NGX price feeds are not available via free APIs.
            </p>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-3">
          <NuxtLink to="/nigeria/" class="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">All Nigerian stocks →</NuxtLink>
          <NuxtLink to="/countries/ng/" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">🇳🇬 Nigeria macro data →</NuxtLink>
          <NuxtLink to="/markets/" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">Markets →</NuxtLink>
        </div>
      </div>

      <!-- Related Nigerian stocks -->
      <div v-if="relatedNigeria?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-3">More Nigerian Stocks</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <NuxtLink
            v-for="s in relatedNigeria"
            :key="s.symbol"
            :to="`/nigeria/${s.symbol.toLowerCase()}/`"
            class="flex items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-800/40 rounded-lg px-3 py-2.5 transition-colors group"
          >
            <span class="text-base" aria-hidden="true">🇳🇬</span>
            <div class="min-w-0">
              <div class="text-xs font-bold text-white group-hover:text-emerald-400 transition-colors truncate">{{ s.name }}</div>
              <div class="text-[10px] text-gray-600 font-mono">{{ s.symbol }} · {{ s.exchange }}</div>
            </div>
          </NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center mt-4">
        <template v-if="isLSE">LSE prices (GBp) · Updated daily</template>
        <template v-else>NGX prices not available · Updated daily</template>
      </p>
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
const { public: { apiBase } } = useRuntimeConfig()

const { data: stock, pending, error } = await useAsyncData(
  `nigeria-stock-${symbol.value}`,
  () => get<any>(`/api/assets/${symbol.value}`).catch(() => null),
)
if (!stock.value) throw createError({ statusCode: 404, statusMessage: 'Stock not found' })

const isLSE = computed(() => stock.value?.exchange === 'LSE')

const currencyPrefix = computed(() => {
  if (!stock.value) return ''
  if (stock.value.currency === 'GBp') return 'p'
  if (stock.value.currency === 'NGN') return '₦'
  return stock.value.currency + ' '
})

function priceFmt(v: number | null | undefined): string {
  if (v == null) return '—'
  if (stock.value?.currency === 'GBp') return `${v.toFixed(2)}p`
  return `₦${v.toFixed(2)}`
}

// Related Nigerian stocks — SSR-safe (before server:false calls)
const { data: relatedNigeria } = await useAsyncData(
  `related-nigeria-${symbol.value}`,
  async () => {
    const [lse, ngx] = await Promise.all([
      $fetch<any[]>('/api/assets', { baseURL: apiBase, params: { type: 'stock', exchange: 'LSE', country_code: 'NG', limit: 10 } }).catch(() => []),
      $fetch<any[]>('/api/assets', { baseURL: apiBase, params: { type: 'stock', exchange: 'NGX', limit: 10 } }).catch(() => []),
    ])
    return [...(lse || []), ...(ngx || [])].filter((a: any) => a.symbol !== symbol.value).slice(0, 6)
  },
)

const interval = ref('1d')

const { data: pricesRaw, pending: pricesPending } = useAsyncData(
  `nigeria-prices-${symbol.value}`,
  () => get<any[]>(`/api/assets/${symbol.value}/prices`, { interval: interval.value, limit: 200 }).catch(() => []),
  { watch: [interval], server: false },
)

const { data: newsItems } = useAsyncData(
  `nigeria-news-${symbol.value}`,
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

const chartData = computed(() => (pricesRaw.value ?? []).filter((p: any) => p.c != null))

const chartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

watch([chartData, chartEl], () => {
  if (!chartEl.value || !chartData.value.length) return
  if (!chart) chart = echarts.init(chartEl.value, 'dark')
  const prices = chartData.value
  const prefix = currencyPrefix.value
  const dp = stock.value?.currency === 'GBp' ? 2 : 2
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 65, right: 15, top: 10, bottom: 30 },
    xAxis: {
      type: 'category',
      data: prices.map((p: any) => p.t.slice(0, 16).replace('T', ' ')),
      axisLabel: { color: '#4b5563', fontSize: 10 },
      axisLine: { lineStyle: { color: '#1f2937' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: {
        color: '#4b5563',
        fontSize: 10,
        formatter: (v: number) => stock.value?.currency === 'GBp' ? `${v.toFixed(0)}p` : `₦${v.toFixed(0)}`,
      },
      splitLine: { lineStyle: { color: '#1a2030' } },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#1f2937',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (params: any) => {
        const v = params[0].value
        const formatted = stock.value?.currency === 'GBp' ? `${Number(v).toFixed(dp)}p` : `₦${Number(v).toFixed(dp)}`
        return `${params[0].axisValue}<br/>${formatted}`
      },
    },
    series: [{
      type: 'line',
      data: prices.map((p: any) => p.c),
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#10b981', width: 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(16,185,129,0.2)' },
            { offset: 1, color: 'rgba(16,185,129,0)' },
          ],
        },
      },
    }],
  })
}, { immediate: true })

onUnmounted(() => chart?.dispose())

function fmtTs(ts: string): string {
  return new Date(ts).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short' })
}

function fmtDate(ts: string): string {
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── SEO ─────────────────────────────────────────────────────────────────────

const { public: { r2PublicUrl } } = useRuntimeConfig()
const ogImage = computed(() =>
  r2PublicUrl
    ? `${r2PublicUrl}/og/section/nigeria.png`
    : 'https://cdn.metricshour.com/og/section/nigeria.png',
)

const _seoTitle = computed(() => {
  if (!stock.value) return `${symbol.value} — Nigerian Stock | MetricsHour`
  const s = stock.value as any
  const exch = s.exchange === 'LSE' ? 'LSE' : 'NGX'
  const curr = s.currency === 'GBp' ? 'GBp' : 'NGN'
  return `${s.name} (${s.symbol}) Stock Price ${exch} — ${curr} | MetricsHour`
})

const _seoDesc = computed(() => {
  if (!stock.value) return ''
  const s = stock.value as any
  const exch = s.exchange === 'LSE' ? 'London Stock Exchange (LSE)' : 'Nigerian Exchange Group (NGX)'
  const curr = s.currency === 'GBp' ? 'GBp (pence)' : 'Nigerian Naira (NGN)'
  const price = s.price ? ` Current price: ${priceFmt(s.price.close)}.` : ''
  return `${s.name} (${s.symbol}) listed on the ${exch}. Priced in ${curr}.${price} ${s.sector ? `${s.sector} sector.` : ''} Nigerian equity data on MetricsHour.`
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: computed(() => `https://metricshour.com/nigeria/${symbol.value.toLowerCase()}/`),
  ogType: 'website',
  ogImage,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  ogImageType: 'image/png',
  twitterCard: 'summary_large_image',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  twitterImage: ogImage,
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/nigeria/${symbol.value.toLowerCase()}/` }],
  script: stock.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: _seoTitle.value,
        url: `https://metricshour.com/nigeria/${symbol.value.toLowerCase()}/`,
        description: _seoDesc.value,
        datePublished: '2026-04-17',
        dateModified: (stock.value as any).price?.timestamp
          ? (stock.value as any).price.timestamp.slice(0, 10)
          : new Date().toISOString().slice(0, 10),
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'Nigerian Stocks', item: 'https://metricshour.com/nigeria/' },
            { '@type': 'ListItem', position: 3, name: (stock.value as any).symbol, item: `https://metricshour.com/nigeria/${symbol.value.toLowerCase()}/` },
          ],
        },
        mainEntity: {
          '@type': 'Corporation',
          name: (stock.value as any).name,
          tickerSymbol: (stock.value as any).symbol,
          description: _seoDesc.value,
          foundingLocation: { '@type': 'Country', name: 'Nigeria' },
        },
      }),
    },
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: [
          {
            '@type': 'Question',
            name: `What exchange is ${(stock.value as any).symbol} listed on?`,
            acceptedAnswer: {
              '@type': 'Answer',
              text: `${(stock.value as any).name} (${(stock.value as any).symbol}) is listed on the ${(stock.value as any).exchange === 'LSE' ? 'London Stock Exchange (LSE) as a dual-listed Nigerian company' : 'Nigerian Exchange Group (NGX)'}.`,
            },
          },
          {
            '@type': 'Question',
            name: `What currency is ${(stock.value as any).symbol} priced in?`,
            acceptedAnswer: {
              '@type': 'Answer',
              text: `${(stock.value as any).symbol} is priced in ${(stock.value as any).currency === 'GBp' ? 'GBp (British pence). Divide by 100 to convert to GBP sterling.' : 'Nigerian Naira (NGN ₦).'}`,
            },
          },
          {
            '@type': 'Question',
            name: `What sector is ${(stock.value as any).symbol} in?`,
            acceptedAnswer: {
              '@type': 'Answer',
              text: `${(stock.value as any).name} operates in the ${(stock.value as any).sector || 'financial'} sector${(stock.value as any).industry ? `, specifically in ${(stock.value as any).industry}` : ''}.`,
            },
          },
        ],
      }),
    },
  ] : [],
})))
</script>
