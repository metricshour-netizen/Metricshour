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

        <div v-if="data.data?.length >= 2" class="w-full overflow-x-auto">
          <svg :viewBox="`0 0 800 160`" class="w-full" style="height:160px">
            <!-- Grid -->
            <line v-for="y in svgGridYs" :key="y"
              :x1="48" :y1="toY(y, svgMinV, svgMaxV, 10, 130)"
              :x2="792" :y2="toY(y, svgMinV, svgMaxV, 10, 130)"
              stroke="#1f2937" stroke-width="1"/>
            <text v-for="y in svgGridYs" :key="'yl'+y"
              :x="44" :y="toY(y, svgMinV, svgMaxV, 10, 130) + 4"
              text-anchor="end" fill="#4b5563" font-size="10">
              {{ data.unit === '$B' ? '$'+fmtB(y) : y.toFixed(1) }}
            </text>
            <!-- Area fill -->
            <path :d="svgAreaPath" fill="url(#blueGrad2)" opacity="0.2"/>
            <!-- Line -->
            <polyline :points="svgLinePoints" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round"/>
            <defs>
              <linearGradient id="blueGrad2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#3b82f6"/>
                <stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
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

    <p class="text-xs text-gray-700 mt-4">Data: Federal Reserve Economic Data (FRED) · St. Louis Fed · Updated daily</p>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const seriesId = (route.params.series_id as string).toUpperCase()

const activeDays = ref(365)

const { data, pending, refresh } = await useAsyncData(
  `rates-${seriesId}-${activeDays.value}`,
  () => $fetch<any>(`/api/rates/${seriesId}?days=${activeDays.value}`).catch(() => null),
)

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

// SVG chart helpers
const SVG_PAD_L = 48, SVG_PAD_R = 8, SVG_PAD_T = 10, SVG_PAD_B = 30
const SVG_W = 800, SVG_H = 160

const svgMinV = computed(() => {
  const vals = (data.value?.data ?? []).map((r: any) => r.value as number)
  return Math.min(...vals) - 0.2
})
const svgMaxV = computed(() => {
  const vals = (data.value?.data ?? []).map((r: any) => r.value as number)
  return Math.max(...vals) + 0.2
})

const svgGridYs = computed(() => {
  const lo = Math.floor(svgMinV.value)
  const hi = Math.ceil(svgMaxV.value)
  const out = []
  for (let y = lo; y <= hi; y += 0.5) out.push(y)
  return out.slice(0, 8)
})

function toY(v: number, minV: number, maxV: number, padT: number, height: number): number {
  const range = maxV - minV || 1
  return padT + (1 - (v - minV) / range) * height
}

const svgLinePoints = computed(() => {
  const rows = data.value?.data ?? []
  if (!rows.length) return ''
  const W = SVG_W - SVG_PAD_L - SVG_PAD_R
  const H = SVG_H - SVG_PAD_T - SVG_PAD_B
  return rows.map((r: any, i: number) => {
    const x = SVG_PAD_L + (i / (rows.length - 1)) * W
    const y = toY(r.value, svgMinV.value, svgMaxV.value, SVG_PAD_T, H)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})

const svgAreaPath = computed(() => {
  const rows = data.value?.data ?? []
  if (rows.length < 2) return ''
  const W = SVG_W - SVG_PAD_L - SVG_PAD_R
  const H = SVG_H - SVG_PAD_T - SVG_PAD_B
  const bottom = SVG_PAD_T + H
  const pts = rows.map((r: any, i: number) => {
    const x = SVG_PAD_L + (i / (rows.length - 1)) * W
    const y = toY(r.value, svgMinV.value, svgMaxV.value, SVG_PAD_T, H)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const firstX = SVG_PAD_L
  const lastX = SVG_W - SVG_PAD_R
  return `M ${firstX},${bottom} L ${pts.join(' L ')} L ${lastX},${bottom} Z`
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

function fmtB(v: number): string {
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(0)}T`
  return `${v.toFixed(0)}B`
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
  ogImage: 'https://cdn.metricshour.com/og/section/home.png',
  robots: 'index, follow',
})
useHead({
  link: [{ rel: 'canonical', href: `https://metricshour.com/rates/${seriesId.toLowerCase()}/` }],
})
</script>
