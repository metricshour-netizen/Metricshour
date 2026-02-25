<template>
  <div>
    <!-- Hero band -->
    <div class="bg-gradient-to-b from-[#110a1f] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/markets" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
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
              <div class="text-xs text-gray-600 mt-1">{{ index.price ? 'Last close' : 'Awaiting price feed' }}</div>
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

      <!-- Price chart placeholder -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-4">Price History</h2>
        <div v-if="!index.price" class="text-gray-600 text-sm text-center py-10">
          No price data available yet — price ingestion runs every 15 minutes during market hours.
        </div>
        <div v-else id="index-chart" ref="chartEl" class="w-full" style="height:280px"/>
      </div>

      <!-- About -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-3">About {{ index.symbol }}</h2>
        <p class="text-gray-400 text-sm leading-relaxed">
          {{ indexDescription(index.symbol) }}
        </p>
        <div class="mt-4 flex flex-wrap gap-2">
          <NuxtLink to="/markets" class="text-xs text-purple-400 hover:text-purple-300 border border-purple-800/40 px-3 py-1.5 rounded-lg transition-colors">
            ← All Markets
          </NuxtLink>
          <NuxtLink to="/markets?tab=stock" class="text-xs text-gray-400 hover:text-gray-300 border border-[#1f2937] px-3 py-1.5 rounded-lg transition-colors">
            Browse Stocks →
          </NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center">Data: Marketstack · FRED · Yahoo Finance</p>
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
const { get } = useApi()
const symbol = (route.params.symbol as string).toUpperCase()

const { data: index, pending, error } = await useAsyncData(
  `index-${symbol}`,
  () => get<any>(`/api/assets/${symbol}`).catch(() => null),
)

// ── Chart ─────────────────────────────────────────────────────────────────────
const chartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

onMounted(async () => {
  await nextTick()
  if (!chartEl.value || !index.value?.price) return
  chart = echarts.init(chartEl.value)
  const p = index.value.price
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: [p.date], axisLine: { lineStyle: { color: '#374151' } }, axisLabel: { color: '#6b7280', fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => fmtPrice(v) }, splitLine: { lineStyle: { color: '#1f2937' } } },
    tooltip: { trigger: 'axis', backgroundColor: '#111827', borderColor: '#374151', textStyle: { color: '#fff', fontSize: 12 } },
    series: [{ type: 'line', data: [p.close], smooth: true, lineStyle: { color: '#a78bfa', width: 2 }, itemStyle: { color: '#a78bfa' }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(167,139,250,0.2)' }, { offset: 1, color: 'rgba(167,139,250,0)' }] } } }],
  })
})

onUnmounted(() => chart?.dispose())

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtPrice(v: number): string {
  if (v >= 10000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1000)  return v.toLocaleString(undefined, { maximumFractionDigits: 1 })
  if (v >= 1)     return v.toFixed(2)
  return v.toFixed(4)
}

function regionIcon(region: string | null): string {
  const map: Record<string, string> = { US: '🇺🇸', Europe: '🇪🇺', Asia: '🌏', Global: '🌐' }
  return map[region ?? ''] ?? '📊'
}

const INDEX_DESCRIPTIONS: Record<string, string> = {
  DJI:    'The Dow Jones Industrial Average (DJIA) tracks 30 large-cap US companies listed on the NYSE and NASDAQ. Founded in 1896, it is one of the oldest and most widely followed equity indices. Price-weighted.',
  GSPC:   'The S&P 500 tracks 500 of the largest US-listed companies by market capitalisation. Market-cap weighted, it covers approximately 80% of the US equity market and is widely used as a benchmark for US large-cap performance.',
  IXIC:   'The NASDAQ Composite Index tracks all common stocks listed on the NASDAQ exchange — over 3,000 companies. Heavily weighted toward technology, biotech, and consumer discretionary sectors.',
  FTSE:   'The FTSE 100 Index measures the performance of 100 companies listed on the London Stock Exchange with the highest market capitalisation. A key benchmark for UK equity performance.',
  DAX:    'The DAX (Deutscher Aktienindex) tracks 40 major German companies listed on the Frankfurt Stock Exchange. Performance index including dividends. Key benchmark for the German and European equity markets.',
  N225:   'The Nikkei 225 is a price-weighted index of 225 prominent stocks listed on the Tokyo Stock Exchange. Widely used as the main benchmark for the Japanese equity market.',
  HSI:    'The Hang Seng Index (HSI) tracks the largest companies on the Hong Kong Stock Exchange, covering approximately 65% of the exchange\'s total market capitalisation.',
  SSEC:   'The Shanghai Composite Index measures the performance of all stocks listed on the Shanghai Stock Exchange — A shares and B shares. Primary benchmark for mainland Chinese equities.',
  SENSEX: 'The BSE SENSEX (Sensitive Index) is a free-float market-weighted stock market index of 30 well-established and financially sound companies listed on the Bombay Stock Exchange.',
  SPX:    'The S&P 500 Index tracks 500 large-cap US-listed companies. Market-cap weighted benchmark representing approximately 80% of available US market capitalisation.',
}

function indexDescription(symbol: string): string {
  return INDEX_DESCRIPTIONS[symbol] ??
    `${symbol} is a market index tracking a basket of securities. Indices provide a statistical measure of market performance for a group of assets, region, or sector.`
}

useSeoMeta({
  title: computed(() => index.value ? `${index.value.symbol} — ${index.value.name} — MetricsHour` : 'Index — MetricsHour'),
  description: computed(() => index.value ? `${index.value.name} (${index.value.symbol}) live price, performance data, and market analysis. ${indexDescription(symbol).slice(0, 120)}` : ''),
  ogTitle: computed(() => index.value ? `${index.value.symbol} — ${index.value.name}` : 'Index — MetricsHour'),
  ogDescription: computed(() => index.value ? `${index.value.name} live price and market data on MetricsHour.` : ''),
  ogUrl: `https://metricshour.com/indices/${symbol}`,
  ogType: 'website',
  twitterTitle: computed(() => index.value ? `${index.value.symbol} — ${index.value.name}` : 'Index — MetricsHour'),
  twitterDescription: computed(() => index.value ? `${index.value.name} live price on MetricsHour.` : ''),
})

useHead({
  script: index.value ? [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      'itemListElement': [
        { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
        { '@type': 'ListItem', position: 2, name: 'Markets', item: 'https://metricshour.com/markets' },
        { '@type': 'ListItem', position: 3, name: index.value?.symbol, item: `https://metricshour.com/indices/${symbol}` },
      ],
    }),
  }] : [],
})
</script>
