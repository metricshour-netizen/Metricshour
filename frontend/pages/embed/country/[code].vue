<template>
  <div class="embed-root">
    <div v-if="pending" class="loading"><div class="spinner"/></div>
    <div v-else-if="!country" class="error">Country not found.</div>
    <template v-else>
      <div class="header">
        <span class="flag">{{ country.flag_emoji }}</span>
        <div>
          <div class="title">{{ country.name }}</div>
          <div class="subtitle">Economic Indicators · World Bank</div>
        </div>
      </div>

      <div class="stats">
        <div v-for="s in keyStats" :key="s.label" class="stat">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
        </div>
      </div>

      <div v-if="gdpHistory.length" class="chart-wrap">
        <div class="chart-title">GDP (USD) — Historical</div>
        <div ref="chartEl" class="chart"/>
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
const code = computed(() => String(route.params.code).toUpperCase())
const { get } = useApi()

const { data: country, pending } = useAsyncData(
  `embed-country-${code.value}`,
  () => get<any>(`/api/countries/${code.value}`).catch(() => null),
)

const { data: gdpHistory } = useAsyncData(
  `embed-gdp-${code.value}`,
  () => get<any[]>(`/api/countries/${code.value}/gdp-history`).catch(() => []),
  { server: false },
)

const keyStats = computed(() => {
  const ind = country.value?.indicators || {}
  return [
    { label: 'GDP', value: fmtUsd(ind.gdp_usd) },
    { label: 'GDP Growth', value: ind.gdp_growth_pct != null ? `${ind.gdp_growth_pct?.toFixed(1)}%` : '—' },
    { label: 'Inflation', value: ind.inflation_pct != null ? `${ind.inflation_pct?.toFixed(1)}%` : '—' },
    { label: 'Population', value: fmtPop(ind.population) },
  ]
})

const chartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

watch([gdpHistory, chartEl], () => {
  if (!gdpHistory.value?.length || !chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value, 'dark')
  const data = gdpHistory.value
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 10, right: 10, top: 10, bottom: 24, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      formatter: (p: any) => `${p[0].axisValue}<br/>${fmtUsd(p[0].value)}`,
    },
    xAxis: { type: 'category', data: data.map((d: any) => d.year || d.period_date?.slice(0,4)), axisLabel: { color: '#6b7280', fontSize: 10 }, axisLine: { lineStyle: { color: '#1f2937' } } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => fmtUsd(v) }, splitLine: { lineStyle: { color: '#1a2030' } } },
    series: [{ type: 'line', data: data.map((d: any) => d.value ?? d.gdp_usd), smooth: true, symbol: 'none', lineStyle: { color: '#10b981', width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(16,185,129,0.2)' }, { offset: 1, color: 'rgba(16,185,129,0)' }] } } }],
  })
}, { immediate: true })

onUnmounted(() => chart?.dispose())

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return '—'
  if (v >= 1e12) return '$' + (v / 1e12).toFixed(1) + 'T'
  if (v >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B'
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M'
  return '$' + v.toLocaleString()
}
function fmtPop(v: number | null | undefined): string {
  if (v == null) return '—'
  if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B'
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M'
  return v.toLocaleString()
}
</script>

<style scoped>
.embed-root { background: #0a0e1a; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 16px; min-height: 100vh; position: relative; font-size: 13px; }
.loading { display: flex; align-items: center; justify-content: center; height: 200px; }
.spinner { width: 24px; height: 24px; border: 2px solid #10b981; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error { color: #6b7280; text-align: center; padding: 40px; }
.header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.flag { font-size: 28px; }
.title { font-size: 16px; font-weight: 700; color: #fff; }
.subtitle { font-size: 11px; color: #4b5563; margin-top: 1px; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.stat { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 8px 10px; }
.stat-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; margin-bottom: 2px; }
.stat-value { font-size: 14px; font-weight: 700; color: #fff; font-variant-numeric: tabular-nums; }
.chart-wrap { background: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 10px; margin-bottom: 28px; }
.chart-title { font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; margin-bottom: 6px; }
.chart { height: 160px; width: 100%; }
.watermark { position: fixed; bottom: 8px; right: 10px; font-size: 10px; color: #374151; text-decoration: none; font-weight: 600; letter-spacing: 0.05em; transition: color 0.2s; }
.watermark:hover { color: #10b981; }
</style>
