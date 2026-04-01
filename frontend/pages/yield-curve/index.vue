<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-2">
      <NuxtLink to="/rates/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors">← Rates Dashboard</NuxtLink>
    </div>
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">US Treasury Yield Curve</h1>
      <p class="text-gray-500 text-sm mt-1">3M · 2Y · 5Y · 10Y · 30Y — current snapshot and historical comparison</p>
    </div>

    <!-- Loading -->
    <div v-if="pending" class="space-y-6">
      <div class="h-72 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
      <div class="grid grid-cols-5 gap-3">
        <div v-for="i in 5" :key="i" class="h-20 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
      </div>
    </div>

    <template v-else-if="data">
      <!-- Current snapshot cards -->
      <div class="grid grid-cols-3 sm:grid-cols-5 gap-3 mb-8">
        <div
          v-for="item in data.current"
          :key="item.series_id"
          class="bg-[#111827] border rounded-xl p-4 text-center transition-all"
          :class="item.value != null ? 'border-blue-900/50' : 'border-[#1f2937]'"
        >
          <div class="text-xs text-gray-500 font-mono mb-1">{{ item.maturity }}</div>
          <div v-if="item.value != null" class="text-lg font-extrabold tabular-nums" :class="yieldColor(item.value)">
            {{ item.value.toFixed(2) }}%
          </div>
          <div v-else class="text-lg font-extrabold text-gray-700">—</div>
          <div class="text-[10px] text-gray-600 mt-1">{{ item.period_date ? fmtDate(item.period_date) : '' }}</div>
        </div>
      </div>

      <!-- Inversion alert -->
      <div
        v-if="isInverted"
        class="mb-6 p-4 bg-red-900/20 border border-red-800/40 rounded-xl flex items-start gap-3"
      >
        <span class="text-red-400 text-lg flex-shrink-0">⚠</span>
        <div>
          <p class="text-red-300 text-sm font-semibold">Yield Curve Inverted</p>
          <p class="text-red-400/80 text-xs mt-0.5">
            The 2Y yield ({{ yld('DGS2')?.toFixed(2) }}%) exceeds the 10Y yield ({{ yld('DGS10')?.toFixed(2) }}%).
            Historically, sustained inversions have preceded economic slowdowns.
          </p>
        </div>
      </div>

      <!-- Spread callout -->
      <div v-if="spread != null" class="mb-8 p-4 bg-[#0d1520] border border-blue-900/40 rounded-xl flex flex-wrap gap-6">
        <div>
          <div class="text-[10px] text-gray-600 uppercase tracking-widest mb-1">10Y–2Y Spread</div>
          <div class="text-2xl font-extrabold tabular-nums" :class="spread >= 0 ? 'text-emerald-400' : 'text-red-400'">
            {{ spread >= 0 ? '+' : '' }}{{ spread.toFixed(2) }}%
          </div>
        </div>
        <div>
          <div class="text-[10px] text-gray-600 uppercase tracking-widest mb-1">Curve Shape</div>
          <div class="text-sm font-semibold" :class="spread >= 0.5 ? 'text-emerald-400' : spread >= 0 ? 'text-amber-400' : 'text-red-400'">
            {{ spread >= 0.5 ? 'Normal (steep)' : spread >= 0 ? 'Flat' : 'Inverted' }}
          </div>
        </div>
        <div>
          <div class="text-[10px] text-gray-600 uppercase tracking-widest mb-1">Fed Funds Rate</div>
          <div class="text-sm font-semibold text-blue-300">{{ dff != null ? dff.toFixed(2) + '%' : '—' }}</div>
        </div>
      </div>

      <!-- Yield curve chart -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl p-6 mb-8">
        <h2 class="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-widest">Current Yield Curve</h2>
        <EChartLine v-if="yieldCurveOption" :option="yieldCurveOption" height="220px" aria-label="US Treasury yield curve" />
        <div v-else class="py-10 text-center text-gray-600 text-sm">Chart data loading...</div>
      </div>

      <!-- 10Y historical chart -->
      <div v-if="data.history.DGS10?.length" class="bg-[#0d1520] border border-[#1f2937] rounded-xl p-6 mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-widest">10-Year Treasury — 2 Year History</h2>
          <div class="text-xs text-gray-600">{{ data.history.DGS10.length }} observations</div>
        </div>
        <EChartLine :option="dgs10HistoryOption" height="100px" aria-label="10-year Treasury yield 2-year history" />
      </div>

      <!-- Series comparison table -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-hidden mb-8">
        <table class="w-full text-sm">
          <thead class="bg-[#111827] text-[11px] text-gray-500 uppercase tracking-widest">
            <tr>
              <th class="px-4 py-3 text-left">Maturity</th>
              <th class="px-4 py-3 text-right">Current</th>
              <th class="px-4 py-3 text-right hidden sm:table-cell">1 Month Ago</th>
              <th class="px-4 py-3 text-right hidden md:table-cell">1 Year Ago</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in data.current" :key="item.series_id"
              class="border-t border-[#1f2937] hover:bg-[#131d2e] transition-colors">
              <td class="px-4 py-3 text-white font-medium">
                {{ item.maturity }}
                <span class="text-gray-600 text-xs ml-2">{{ item.series_id }}</span>
              </td>
              <td class="px-4 py-3 text-right font-extrabold tabular-nums" :class="item.value != null ? yieldColor(item.value) : 'text-gray-700'">
                {{ item.value != null ? item.value.toFixed(2) + '%' : '—' }}
              </td>
              <td class="px-4 py-3 text-right text-gray-400 tabular-nums hidden sm:table-cell">
                {{ getHistoricalValue(item.series_id, 30) }}
              </td>
              <td class="px-4 py-3 text-right text-gray-400 tabular-nums hidden md:table-cell">
                {{ getHistoricalValue(item.series_id, 365) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-else class="text-center py-16 text-gray-600 text-sm">
      No yield curve data yet — FRED worker runs daily at 6:30am UTC.
    </div>

    <p class="text-xs text-gray-700 mt-4">Data: Federal Reserve Economic Data (FRED) · St. Louis Fed · Updated daily</p>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()
const { data, pending } = await useAsyncData('yield-curve',
  () => get<any>('/api/rates/yield-curve?days=730').catch(() => null),
)

const yieldValues = computed<Record<string, number | null>>(() => {
  if (!data.value?.current) return {}
  return Object.fromEntries(data.value.current.map((c: any) => [c.series_id, c.value]))
})

const yld = (sid: string) => yieldValues.value[sid] ?? null

const spread = computed(() => {
  const t10 = yld('DGS10'), t2 = yld('DGS2')
  if (t10 == null || t2 == null) return null
  return +(t10 - t2).toFixed(3)
})

const isInverted = computed(() => spread.value != null && spread.value < 0)
const dff = computed(() => null) // DFF not in yield curve endpoint — shown on /rates/

const yieldCurveOption = computed(() => {
  if (!data.value?.current) return null
  const items = data.value.current.filter((c: any) => c.value != null)
  if (items.length < 2) return null
  const labels = items.map((c: any) => data.value.labels?.[c.series_id] ?? c.series_id)
  const values = items.map((c: any) => c.value)
  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 12, bottom: 28, left: 48, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1117',
      borderColor: '#1f2937',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (params: any[]) => {
        const p = params[0]
        return `<span style="color:#6b7280;font-size:11px">${p.axisValue}</span><br/><span style="color:#93c5fd;font-weight:600">${(p.value as number).toFixed(2)}%</span>`
      },
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#1f2937' } },
      axisTick: { show: false },
      axisLabel: { color: '#6b7280', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: { color: '#4b5563', fontSize: 10, formatter: (v: number) => `${v.toFixed(1)}%` },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: false,
      symbolSize: 8,
      symbol: 'circle',
      itemStyle: { color: '#3b82f6', borderColor: '#0d1520', borderWidth: 2 },
      lineStyle: { color: '#3b82f6', width: 2.5 },
      areaStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(59,130,246,0.25)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] },
      },
    }],
  }
})

const dgs10HistoryOption = computed(() => {
  const series: { date: string; value: number }[] = data.value?.history?.DGS10 ?? []
  if (!series.length) return {}
  return {
    backgroundColor: 'transparent',
    grid: { top: 4, right: 4, bottom: 4, left: 4 },
    tooltip: { show: false },
    xAxis: { type: 'category', data: series.map(r => r.date), show: false },
    yAxis: { type: 'value', scale: true, show: false },
    series: [{
      type: 'line',
      data: series.map(r => r.value),
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#3b82f6', width: 1.5 },
    }],
  }
})

function getHistoricalValue(seriesId: string, daysAgo: number): string {
  const hist = data.value?.history?.[seriesId]
  if (!hist?.length) return '—'
  const targetDate = new Date()
  targetDate.setDate(targetDate.getDate() - daysAgo)
  // Find closest observation to daysAgo
  let closest = hist[0]
  let minDiff = Infinity
  for (const row of hist) {
    const d = new Date(row.date + 'T00:00:00Z')
    const diff = Math.abs(d.getTime() - targetDate.getTime())
    if (diff < minDiff) { minDiff = diff; closest = row }
  }
  return closest ? closest.value.toFixed(2) + '%' : '—'
}

function yieldColor(v: number): string {
  if (v > 5.5) return 'text-red-400'
  if (v > 4.5) return 'text-amber-400'
  if (v < 1) return 'text-emerald-400'
  return 'text-blue-300'
}

function fmtDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

useSeoMeta({
  title: 'US Treasury Yield Curve — MetricsHour',
  description: 'Interactive US Treasury yield curve showing 3-month to 30-year yields. Track inversions, spreads, and historical comparisons.',
  ogTitle: 'US Treasury Yield Curve — MetricsHour',
  ogDescription: 'Interactive US yield curve: 3M, 2Y, 5Y, 10Y, 30Y Treasury yields with inversion alerts and historical charts.',
  ogUrl: 'https://metricshour.com/yield-curve/',
  ogImage: 'https://cdn.metricshour.com/og/section/home.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterImage: 'https://cdn.metricshour.com/og/section/home.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})
useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/yield-curve/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'US Treasury Yield Curve — MetricsHour',
      url: 'https://metricshour.com/yield-curve/',
      description: 'Interactive US Treasury yield curve with inversion detection and 2-year historical chart.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
    }),
  }],
})
</script>
