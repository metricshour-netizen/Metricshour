<template>
  <div class="embed-root">
    <div v-if="pending" class="loading"><div class="spinner"/></div>
    <div v-else-if="!stock" class="error">Stock not found.</div>
    <template v-else>
      <div class="header">
        <div>
          <div class="ticker">{{ stock.symbol }}</div>
          <div class="name">{{ stock.name }}</div>
          <div class="meta">{{ stock.exchange }} · {{ stock.currency || 'USD' }}</div>
        </div>
        <div class="price-block">
          <div class="price">{{ stock.price ? `$${stock.price.close?.toFixed(2)}` : '—' }}</div>
          <div v-if="stock.price?.change_pct != null" class="change" :class="stock.price.change_pct >= 0 ? 'pos' : 'neg'">
            {{ stock.price.change_pct >= 0 ? '▲' : '▼' }} {{ Math.abs(stock.price.change_pct).toFixed(2) }}%
          </div>
        </div>
      </div>

      <div ref="chartEl" class="chart"/>

      <div v-if="stock.country_revenues?.length" class="revenues">
        <div class="rev-title">Geographic Revenue</div>
        <div v-for="r in stock.country_revenues.slice(0, 4)" :key="r.country?.code" class="rev-row">
          <span class="rev-flag">{{ r.country?.flag }}</span>
          <span class="rev-name">{{ r.country?.name }}</span>
          <div class="rev-bar-wrap">
            <div class="rev-bar" :style="{ width: `${Math.min(r.revenue_pct, 100)}%` }"/>
          </div>
          <span class="rev-pct">{{ r.revenue_pct?.toFixed(1) }}%</span>
        </div>
      </div>
    </template>

    <a class="watermark" href="https://metricshour.com" target="_blank" rel="noopener">MetricsHour</a>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

definePageMeta({ layout: false })
useHead({ meta: [{ name: 'robots', content: 'noindex' }] })

const route = useRoute()
const ticker = computed(() => String(route.params.ticker).toUpperCase())
const { get } = useApi()

const { data: stock, pending } = useAsyncData(
  `embed-stock-${ticker.value}`,
  () => get<any>(`/api/assets/${ticker.value}`).catch(() => null),
)

const { data: pricesRaw } = useAsyncData(
  `embed-stock-prices-${ticker.value}`,
  () => get<any[]>(`/api/assets/${ticker.value}/prices`, { interval: '1d', limit: 180 }).catch(() => []),
  { server: false },
)

const chartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const chartData = computed(() => (pricesRaw.value ?? []).filter((p: any) => p.c != null))

watch([chartData, chartEl], () => {
  if (!chartEl.value || !chartData.value.length) return
  if (!chart) chart = echarts.init(chartEl.value, 'dark')
  const prices = chartData.value
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 10, right: 10, top: 10, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      formatter: (p: any) => `${p[0].axisValue}<br/>$${p[0].value?.toFixed(2)}`,
    },
    xAxis: { type: 'category', data: prices.map((p: any) => p.t.slice(0, 10)), axisLabel: { color: '#6b7280', fontSize: 10 }, axisLine: { lineStyle: { color: '#1f2937' } } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => `$${v.toFixed(0)}` }, splitLine: { lineStyle: { color: '#1a2030' } } },
    series: [{ type: 'line', data: prices.map((p: any) => p.c), smooth: true, symbol: 'none', lineStyle: { color: '#10b981', width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(16,185,129,0.2)' }, { offset: 1, color: 'rgba(16,185,129,0)' }] } } }],
  })
}, { immediate: true })

onUnmounted(() => chart?.dispose())
</script>

<style scoped>
.embed-root { background: #0a0e1a; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 16px; min-height: 100vh; position: relative; font-size: 13px; }
.loading { display: flex; align-items: center; justify-content: center; height: 200px; }
.spinner { width: 24px; height: 24px; border: 2px solid #10b981; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error { color: #6b7280; text-align: center; padding: 40px; }
.header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.ticker { font-size: 18px; font-weight: 800; color: #10b981; font-family: monospace; }
.name { font-size: 13px; font-weight: 600; color: #fff; margin-top: 1px; }
.meta { font-size: 10px; color: #4b5563; margin-top: 2px; }
.price-block { text-align: right; }
.price { font-size: 20px; font-weight: 800; color: #fff; font-variant-numeric: tabular-nums; }
.change { font-size: 12px; font-weight: 700; margin-top: 2px; font-variant-numeric: tabular-nums; }
.pos { color: #10b981; }
.neg { color: #ef4444; }
.chart { height: 160px; width: 100%; margin-bottom: 12px; }
.revenues { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 10px; margin-bottom: 28px; }
.rev-title { font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; margin-bottom: 8px; }
.rev-row { display: flex; align-items: center; gap: 6px; padding: 3px 0; }
.rev-flag { font-size: 14px; width: 20px; }
.rev-name { font-size: 11px; color: #d1d5db; width: 100px; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rev-bar-wrap { flex: 1; background: #1f2937; border-radius: 2px; height: 4px; }
.rev-bar { background: #10b981; height: 4px; border-radius: 2px; }
.rev-pct { font-size: 11px; color: #10b981; font-variant-numeric: tabular-nums; width: 36px; text-align: right; }
.watermark { position: fixed; bottom: 8px; right: 10px; font-size: 10px; color: #374151; text-decoration: none; font-weight: 600; letter-spacing: 0.05em; transition: color 0.2s; }
.watermark:hover { color: #10b981; }
</style>
