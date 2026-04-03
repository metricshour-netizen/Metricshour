<template>
  <div class="embed-root">
    <div v-if="pending" class="loading">
      <div class="spinner"/>
    </div>
    <div v-else-if="!data" class="error">No data found.</div>
    <template v-else>
      <div class="header">
        <div class="flags">
          <span>{{ data.exporter.flag }}</span>
          <span class="arrow">→</span>
          <span>{{ data.importer.flag }}</span>
        </div>
        <div class="title">{{ data.exporter.name }} – {{ data.importer.name }} Trade</div>
        <div class="year">{{ data.trade_data?.year }} · UN Comtrade</div>
      </div>

      <div class="stats">
        <div class="stat">
          <div class="stat-label">Trade Value</div>
          <div class="stat-value">${{ fmt(data.trade_data?.trade_value_usd) }}</div>
        </div>
        <div class="stat">
          <div class="stat-label">{{ data.exporter.name }} Exports</div>
          <div class="stat-value">${{ fmt(data.trade_data?.exports_usd) }}</div>
        </div>
        <div class="stat">
          <div class="stat-label">{{ data.importer.name }} Exports</div>
          <div class="stat-value">${{ fmt(data.trade_data?.imports_usd) }}</div>
        </div>
        <div class="stat">
          <div class="stat-label">Balance</div>
          <div class="stat-value" :class="(data.trade_data?.balance_usd ?? 0) >= 0 ? 'pos' : 'neg'">
            {{ (data.trade_data?.balance_usd ?? 0) >= 0 ? '+' : '' }}${{ fmt(data.trade_data?.balance_usd) }}
          </div>
        </div>
      </div>

      <div ref="chartEl" class="chart"/>

      <div class="products" v-if="data.trade_data?.top_export_products?.length">
        <div class="products-title">Top {{ data.exporter.name }} Exports</div>
        <div v-for="p in data.trade_data.top_export_products.slice(0,3)" :key="p.name" class="product-row">
          <span class="product-name">{{ p.name }}</span>
          <span class="product-val">${{ fmt(p.value_usd) }}</span>
        </div>
      </div>
    </template>

    <a class="watermark" href="https://metricshour.com" target="_blank" rel="noopener">
      MetricsHour
    </a>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

definePageMeta({ layout: false })

useHead({
  meta: [{ name: 'robots', content: 'noindex' }],
})

const route = useRoute()
const pair = computed(() => String(route.params.pair))
const { get } = useApi()

const [exp, imp] = pair.value.split('-')
const { data, pending } = useAsyncData(
  `embed-trade-${pair.value}`,
  () => get<any>(`/api/trade/${exp}/${imp}`).catch(() => null),
)

const chartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

watch([data, chartEl], () => {
  if (!data.value?.trade_data || !chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value, 'dark')
  const td = data.value.trade_data
  const expName = data.value.exporter.name
  const impName = data.value.importer.name
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 10, right: 10, top: 10, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      formatter: (p: any) => `${p[0].name}<br/>${p[0].marker}$${fmtFull(p[0].value)}`,
    },
    xAxis: { type: 'category', data: [`${expName} Exports`, `${impName} Exports`], axisLabel: { color: '#6b7280', fontSize: 10 }, axisLine: { lineStyle: { color: '#1f2937' } } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => `$${fmt(v)}` }, splitLine: { lineStyle: { color: '#1a2030' } } },
    series: [{
      type: 'bar',
      data: [
        { value: td.exports_usd, itemStyle: { color: '#10b981' } },
        { value: td.imports_usd, itemStyle: { color: '#3b82f6' } },
      ],
      barMaxWidth: 60,
    }],
  })
}, { immediate: true })

onUnmounted(() => chart?.dispose())

function fmt(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e12) return (v / 1e12).toFixed(1) + 'T'
  if (abs >= 1e9) return (v / 1e9).toFixed(1) + 'B'
  if (abs >= 1e6) return (v / 1e6).toFixed(1) + 'M'
  return v.toLocaleString()
}
function fmtFull(v: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(v)
}
</script>

<style scoped>
.embed-root {
  background: #0a0e1a;
  color: #e5e7eb;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  padding: 16px;
  min-height: 100vh;
  position: relative;
  font-size: 13px;
}
.loading { display: flex; align-items: center; justify-content: center; height: 200px; }
.spinner { width: 24px; height: 24px; border: 2px solid #10b981; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error { color: #6b7280; text-align: center; padding: 40px; }
.header { margin-bottom: 12px; }
.flags { font-size: 20px; margin-bottom: 4px; }
.arrow { font-size: 14px; margin: 0 4px; color: #4b5563; }
.title { font-size: 15px; font-weight: 700; color: #fff; }
.year { font-size: 11px; color: #4b5563; margin-top: 2px; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.stat { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 8px 10px; }
.stat-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; margin-bottom: 2px; }
.stat-value { font-size: 14px; font-weight: 700; color: #fff; font-variant-numeric: tabular-nums; }
.pos { color: #10b981 !important; }
.neg { color: #ef4444 !important; }
.chart { height: 160px; width: 100%; margin-bottom: 12px; }
.products { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 10px; margin-bottom: 28px; }
.products-title { font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; margin-bottom: 6px; }
.product-row { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid #1a2030; }
.product-row:last-child { border-bottom: none; }
.product-name { color: #d1d5db; font-size: 12px; }
.product-val { color: #10b981; font-size: 12px; font-variant-numeric: tabular-nums; }
.watermark {
  position: fixed; bottom: 8px; right: 10px;
  font-size: 10px; color: #374151; text-decoration: none;
  font-weight: 600; letter-spacing: 0.05em;
  transition: color 0.2s;
}
.watermark:hover { color: #10b981; }
</style>
