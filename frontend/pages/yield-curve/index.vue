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

      <!-- SVG yield curve chart -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl p-6 mb-8">
        <h2 class="text-sm font-semibold text-gray-400 mb-4 uppercase tracking-widest">Current Yield Curve</h2>
        <div v-if="chartPoints.length >= 2" class="w-full overflow-x-auto">
          <svg :viewBox="`0 0 ${SVG_W} ${SVG_H}`" class="w-full" style="min-height:180px;max-height:260px">
            <!-- Grid lines -->
            <line v-for="y in gridYs" :key="y"
              :x1="MARGIN_L" :y1="toSvgY(y)" :x2="SVG_W - MARGIN_R" :y2="toSvgY(y)"
              stroke="#1f2937" stroke-width="1"/>
            <!-- Y labels -->
            <text v-for="y in gridYs" :key="'yl'+y"
              :x="MARGIN_L - 8" :y="toSvgY(y) + 4"
              text-anchor="end" fill="#4b5563" font-size="11">{{ y.toFixed(1) }}%</text>
            <!-- Curve fill -->
            <path :d="fillPath" fill="url(#blueGrad)" opacity="0.25"/>
            <!-- Curve line -->
            <polyline :points="svgPoints" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linejoin="round"/>
            <!-- Dots -->
            <circle v-for="(pt, i) in chartPoints" :key="i"
              :cx="pt.x" :cy="pt.y" r="5" fill="#3b82f6" stroke="#0d1520" stroke-width="2"/>
            <!-- X labels -->
            <text v-for="(pt, i) in chartPoints" :key="'xl'+i"
              :x="pt.x" :y="SVG_H - 8"
              text-anchor="middle" fill="#6b7280" font-size="12">{{ pt.label }}</text>
            <!-- Gradient def -->
            <defs>
              <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#3b82f6"/>
                <stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <div v-else class="py-10 text-center text-gray-600 text-sm">Chart data loading...</div>
      </div>

      <!-- 10Y historical sparkline -->
      <div v-if="data.history.DGS10?.length" class="bg-[#0d1520] border border-[#1f2937] rounded-xl p-6 mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-widest">10-Year Treasury — 2 Year History</h2>
          <div class="text-xs text-gray-600">{{ data.history.DGS10.length }} observations</div>
        </div>
        <svg :viewBox="`0 0 800 80`" class="w-full" style="height:80px">
          <polyline
            :points="sparklinePoints(data.history.DGS10)"
            fill="none" stroke="#3b82f6" stroke-width="1.5"/>
        </svg>
        <div class="flex justify-between text-[10px] text-gray-600 mt-1">
          <span>{{ data.history.DGS10[0]?.date }}</span>
          <span>{{ data.history.DGS10[data.history.DGS10.length - 1]?.date }}</span>
        </div>
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
const { data, pending } = await useAsyncData('yield-curve',
  () => $fetch<any>('/api/rates/yield-curve?days=730').catch(() => null),
)

const SVG_W = 600
const SVG_H = 200
const MARGIN_L = 44
const MARGIN_R = 16
const MARGIN_T = 10
const MARGIN_B = 28

// Yield curve maturities in order
const MATURITIES = ['DGS3MO', 'DGS2', 'DGS5', 'DGS10', 'DGS30']

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

// SVG chart points
const chartPoints = computed(() => {
  if (!data.value?.current) return []
  const items = data.value.current.filter((c: any) => c.value != null)
  if (items.length < 2) return []
  const vals = items.map((c: any) => c.value as number)
  const minV = Math.min(...vals) - 0.3
  const maxV = Math.max(...vals) + 0.3
  const innerW = SVG_W - MARGIN_L - MARGIN_R
  const innerH = SVG_H - MARGIN_T - MARGIN_B
  return items.map((c: any, i: number) => ({
    x: MARGIN_L + (i / (items.length - 1)) * innerW,
    y: MARGIN_T + (1 - (c.value - minV) / (maxV - minV)) * innerH,
    label: data.value.labels[c.series_id] ?? c.series_id,
    value: c.value,
  }))
})

const svgPoints = computed(() =>
  chartPoints.value.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
)

const fillPath = computed(() => {
  if (!chartPoints.value.length) return ''
  const pts = chartPoints.value
  const bottom = SVG_H - MARGIN_B
  const first = pts[0], last = pts[pts.length - 1]
  const line = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  return `M ${first.x},${bottom} L ${line.replace(/\d+\.\d+,\d+\.\d+/g, (m) => m)} L ${last.x},${bottom} Z`
    .replace('L L', 'L')
})

// Grid Y values
const gridYs = computed(() => {
  if (!data.value?.current) return []
  const vals = data.value.current.filter((c: any) => c.value != null).map((c: any) => c.value as number)
  if (!vals.length) return []
  const lo = Math.floor(Math.min(...vals) - 0.5)
  const hi = Math.ceil(Math.max(...vals) + 0.5)
  const out = []
  for (let y = lo; y <= hi; y += 0.5) out.push(y)
  return out
})

function toSvgY(v: number): number {
  if (!data.value?.current) return 0
  const vals = data.value.current.filter((c: any) => c.value != null).map((c: any) => c.value as number)
  const minV = Math.min(...vals) - 0.3
  const maxV = Math.max(...vals) + 0.3
  const innerH = SVG_H - MARGIN_T - MARGIN_B
  return MARGIN_T + (1 - (v - minV) / (maxV - minV)) * innerH
}

function sparklinePoints(series: { date: string; value: number }[]): string {
  if (!series.length) return ''
  const vals = series.map(r => r.value)
  const minV = Math.min(...vals)
  const maxV = Math.max(...vals)
  const range = maxV - minV || 1
  const W = 800, H = 80, PAD = 4
  return series.map((r, i) => {
    const x = (i / (series.length - 1)) * W
    const y = PAD + (1 - (r.value - minV) / range) * (H - PAD * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

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
