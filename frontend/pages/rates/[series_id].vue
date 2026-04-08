<template>
  <main class="max-w-5xl mx-auto px-4 py-10">
    <div class="mb-2">
      <NuxtLink to="/rates/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors">← Rates Dashboard</NuxtLink>
    </div>

    <div v-if="pending" class="space-y-4">
      <div class="h-8 w-64 bg-[#111827] rounded animate-pulse"/>
      <div class="h-48 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
    </div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="mb-6">
        <div class="flex items-center gap-3 mb-1">
          <span class="text-[11px] font-mono text-gray-600 bg-[#1f2937] px-2 py-0.5 rounded">{{ data.series_id }}</span>
          <span class="text-[11px] text-gray-600">{{ data.category?.replace('_', ' ') }}</span>
        </div>
        <h1 class="text-xl sm:text-2xl font-bold text-white">{{ data.label }}</h1>
      </div>

      <!-- Latest value hero -->
      <div class="bg-[#0d1520] border border-blue-900/40 rounded-xl p-6 mb-6 flex flex-wrap gap-8 items-end">
        <div>
          <div class="text-[11px] text-gray-600 uppercase tracking-widest mb-1">Latest</div>
          <div class="text-4xl font-extrabold tabular-nums text-blue-300">
            {{ fmtValue(data.latest?.value, data.unit) }}
          </div>
          <div class="text-xs text-gray-600 mt-1">{{ data.latest?.date ? fmtDate(data.latest.date) : '—' }}</div>
        </div>
        <div v-if="change1m != null">
          <div class="text-[11px] text-gray-600 uppercase tracking-widest mb-1">1M Change</div>
          <div class="text-lg font-bold tabular-nums" :class="change1m >= 0 ? 'text-amber-400' : 'text-emerald-400'">
            {{ change1m >= 0 ? '+' : '' }}{{ change1m.toFixed(2) }}{{ data.unit === '%' ? 'pp' : '' }}
          </div>
        </div>
        <div v-if="change1y != null">
          <div class="text-[11px] text-gray-600 uppercase tracking-widest mb-1">1Y Change</div>
          <div class="text-lg font-bold tabular-nums" :class="change1y >= 0 ? 'text-amber-400' : 'text-emerald-400'">
            {{ change1y >= 0 ? '+' : '' }}{{ change1y.toFixed(2) }}{{ data.unit === '%' ? 'pp' : '' }}
          </div>
        </div>
      </div>

      <!-- Chart -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-widest">{{ data.days }}-Day History</h2>
          <div class="flex gap-2">
            <button v-for="d in [90, 365, 730]" :key="d"
              @click="setDays(d)"
              class="text-[11px] px-2.5 py-1 rounded-md transition-all"
              :class="activeDays === d ? 'bg-blue-600 text-white' : 'bg-[#1f2937] text-gray-500 hover:text-gray-300'">
              {{ d === 90 ? '3M' : d === 365 ? '1Y' : '2Y' }}
            </button>
          </div>
        </div>

        <EChartLine v-if="data.data?.length >= 2" :option="ratesChartOption" height="200px" :aria-label="`${data.label} chart`" />
        <div v-else class="py-8 text-center text-gray-600 text-sm">Not enough data for chart</div>
      </div>

      <!-- Recent data table -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-hidden mb-6">
        <div class="px-4 py-3 bg-[#111827] text-[11px] text-gray-500 uppercase tracking-widest font-semibold">
          Recent Observations (last 20)
        </div>
        <table class="w-full text-sm">
          <tbody>
            <tr v-for="(row, i) in recentRows" :key="row.date"
              class="border-t border-[#1f2937]"
              :class="i === 0 ? 'bg-blue-950/20' : 'hover:bg-[#131d2e]'">
              <td class="px-4 py-2.5 text-gray-400 text-xs tabular-nums w-36">{{ fmtDate(row.date) }}</td>
              <td class="px-4 py-2.5 text-right font-semibold tabular-nums" :class="i === 0 ? 'text-blue-300' : 'text-white'">
                {{ fmtValue(row.value, data.unit) }}
              </td>
              <td v-if="i > 0" class="px-4 py-2.5 text-right text-xs tabular-nums"
                :class="rowChange(row.value, recentRows[i-1]?.value) >= 0 ? 'text-amber-500' : 'text-emerald-500'">
                {{ fmtChange(rowChange(row.value, recentRows[i-1]?.value), data.unit) }}
              </td>
              <td v-else class="px-4 py-2.5 text-right text-gray-700 text-xs">latest</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-else class="text-center py-16 text-gray-600 text-sm">
      Series not found or no data yet.
    </div>

    <!-- Related Rate Series -->
    <div v-if="relatedRates?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mt-6 mb-4">
      <h2 class="text-base font-bold text-white mb-3">Related Rate Series</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <NuxtLink
          v-for="r in relatedRates"
          :key="r.series_id"
          :to="`/rates/${r.series_id.toLowerCase()}/`"
          class="flex items-center justify-between bg-[#0d1117] border border-[#1f2937] hover:border-blue-800/40 rounded-lg px-4 py-3 transition-colors group"
        >
          <div class="min-w-0">
            <div class="text-xs font-bold text-white group-hover:text-blue-400 transition-colors truncate">{{ r.label }}</div>
            <div class="text-[10px] text-gray-600 font-mono">{{ r.series_id }}</div>
          </div>
          <div v-if="r.value != null" class="text-sm font-bold text-blue-300 tabular-nums shrink-0 ml-3">
            {{ fmtValue(r.value, r.unit || '%') }}
          </div>
        </NuxtLink>
      </div>
      <div class="mt-3 flex gap-3">
        <NuxtLink to="/rates/" class="text-xs text-blue-400 hover:text-blue-300 transition-colors">All rates →</NuxtLink>
        <NuxtLink to="/yield-curve/" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">Yield curve →</NuxtLink>
        <NuxtLink to="/fx/" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">Forex →</NuxtLink>
      </div>
    </div>

    <p class="text-xs text-gray-700 mt-4">Data: Federal Reserve Economic Data (FRED) · St. Louis Fed · Updated daily</p>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const seriesId = (route.params.series_id as string).toUpperCase()
const { get } = useApi()

// ── Related rate series ──────────────────────────────────────────────────────
const { data: relatedRates } = useAsyncData(
  `related-rates-${seriesId}`,
  async () => {
    const dashboard = await get<any>('/api/rates/').catch(() => null)
    if (!dashboard) return []
    const all: any[] = []
    for (const items of Object.values(dashboard as Record<string, any[]>)) {
      if (Array.isArray(items)) all.push(...items)
    }
    return all.filter((s: any) => s.series_id !== seriesId).slice(0, 6)
  },
  { server: false },
)

const activeDays = ref(365)

const { data, pending, refresh } = await useAsyncData(
  `rates-${seriesId}-${activeDays.value}`,
  () => get<any>(`/api/rates/${seriesId}?days=${activeDays.value}`).catch(() => null),
)
if (!data.value) throw createError({ statusCode: 404, statusMessage: 'Series not found' })

async function setDays(d: number) {
  activeDays.value = d
  await refresh()
}

const recentRows = computed(() => {
  if (!data.value?.data?.length) return []
  return [...data.value.data].reverse().slice(0, 20)
})

const change1m = computed(() => {
  const rows = data.value?.data
  if (!rows?.length) return null
  const latest = rows[rows.length - 1]?.value
  const target = new Date(rows[rows.length - 1]?.date)
  target.setDate(target.getDate() - 30)
  const past = rows.find((r: any) => new Date(r.date) <= target)
  if (!past) return null
  return +(latest - past.value).toFixed(3)
})

const change1y = computed(() => {
  const rows = data.value?.data
  if (!rows?.length) return null
  const latest = rows[rows.length - 1]?.value
  const target = new Date(rows[rows.length - 1]?.date)
  target.setFullYear(target.getFullYear() - 1)
  const past = rows.find((r: any) => new Date(r.date) <= target)
  if (!past) return null
  return +(latest - past.value).toFixed(3)
})

const ratesChartOption = computed(() => {
  const rows: any[] = data.value?.data ?? []
  const unit: string = data.value?.unit ?? '%'
  const dates = rows.map((r: any) => r.date)
  const values = rows.map((r: any) => r.value)
  const yFmt = (v: number) => {
    if (unit === '$B') return v >= 1000 ? `$${(v / 1000).toFixed(0)}T` : `$${v.toFixed(0)}B`
    if (unit === 'K') return `${(v / 1000).toFixed(0)}K`
    if (unit === 'index') return v.toFixed(1)
    return `${v.toFixed(2)}%`
  }
  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 12, bottom: 28, left: 56, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1117',
      borderColor: '#1f2937',
      textStyle: { color: '#e5e7eb', fontSize: 12 },
      formatter: (params: any[]) => {
        const p = params[0]
        return `<span style="color:#6b7280;font-size:11px">${p.axisValue}</span><br/><span style="color:#93c5fd;font-weight:600">${yFmt(p.value)}</span>`
      },
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#1f2937' } },
      axisTick: { show: false },
      axisLabel: { color: '#4b5563', fontSize: 10, interval: 'auto' },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: { color: '#4b5563', fontSize: 10, formatter: yFmt },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#3b82f6', width: 2 },
      areaStyle: {
        color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(59,130,246,0.25)' }, { offset: 1, color: 'rgba(59,130,246,0)' }] },
      },
    }],
  }
})

function fmtValue(v: number | null | undefined, unit: string): string {
  if (v == null) return '—'
  if (unit === '$B') {
    if (v >= 1000) return `$${(v / 1000).toFixed(1)}T`
    return `$${v.toFixed(0)}B`
  }
  if (unit === 'K') return `${(v / 1000).toFixed(0)}K`
  if (unit === 'index') return v.toFixed(1)
  return `${v.toFixed(2)}%`
}

function fmtDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

function rowChange(current: number, prev: number | undefined): number {
  if (prev == null) return 0
  return current - prev
}

function fmtChange(diff: number, unit: string): string {
  const sign = diff >= 0 ? '+' : ''
  if (unit === '%') return `${sign}${diff.toFixed(2)}pp`
  if (unit === '$B') return `${sign}${(diff / 1000).toFixed(1)}T`
  return `${sign}${diff.toFixed(2)}`
}

const pageTitle = computed(() => data.value ? `${data.value.label} — MetricsHour` : `${seriesId} — MetricsHour`)

useSeoMeta({
  title: pageTitle,
  description: `Historical data and chart for FRED series ${seriesId}. Updated daily from Federal Reserve Economic Data.`,
  ogUrl: `https://metricshour.com/rates/${seriesId.toLowerCase()}/`,
  ogTitle: pageTitle,
  ogDescription: `Historical data and chart for FRED series ${seriesId}. Updated daily from Federal Reserve Economic Data.`,
  ogImage: 'https://cdn.metricshour.com/og/section/rates.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterImage: 'https://cdn.metricshour.com/og/section/rates.png',
  robots: 'index, follow',
})
useHead({
  link: [{ rel: 'canonical', href: `https://metricshour.com/rates/${seriesId.toLowerCase()}/` }],
})
</script>
