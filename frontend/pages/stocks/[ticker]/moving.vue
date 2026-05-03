<template>
  <main class="max-w-4xl mx-auto px-4 py-10">
    <NuxtLink :to="`/stocks/${ticker.toLowerCase()}/`" class="text-gray-500 text-xs hover:text-gray-300 transition-colors mb-6 inline-block">
      ← {{ ticker }}
    </NuxtLink>

    <!-- Not moving — redirect handled server-side, this is a fallback -->
    <div v-if="!data" class="text-center py-20">
      <p class="text-gray-500 text-sm">No significant move detected for {{ ticker }} right now.</p>
      <NuxtLink :to="`/stocks/${ticker.toLowerCase()}/`" class="text-emerald-500 text-sm hover:text-emerald-400 mt-3 inline-block">
        View {{ ticker }} full analysis →
      </NuxtLink>
    </div>

    <template v-else>
      <!-- Hero -->
      <div class="mb-8">
        <!-- Direction badge -->
        <div class="flex items-center gap-3 mb-3">
          <span
            class="text-xs font-bold uppercase tracking-widest px-3 py-1.5 rounded-full"
            :class="data.direction === 'up'
              ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800'
              : 'bg-red-900/40 text-red-400 border border-red-800'"
          >{{ data.direction === 'up' ? '▲ Moving Up' : '▼ Moving Down' }}</span>
          <span class="text-[10px] text-gray-600">Auto-expires within 48 hours · Data updates every 15 min</span>
        </div>

        <h1 class="text-2xl sm:text-3xl font-extrabold text-white leading-tight mb-2">
          Why is {{ ticker }}
          <span :class="data.direction === 'up' ? 'text-emerald-400' : 'text-red-400'">
            {{ data.direction === 'up' ? 'up' : 'down' }} {{ data.pct_change }}%
          </span>
          today?
        </h1>

        <!-- Price row -->
        <div class="flex items-baseline gap-4 mb-4">
          <span class="text-4xl font-extrabold text-white tabular-nums">${{ data.price_current?.toFixed(2) }}</span>
          <span class="text-lg font-bold tabular-nums" :class="data.direction === 'up' ? 'text-emerald-400' : 'text-red-400'">
            {{ data.direction === 'up' ? '+' : '-' }}{{ data.pct_change }}%
          </span>
          <span class="text-sm text-gray-500">Open: ${{ data.price_open?.toFixed(2) }}</span>
        </div>

        <p class="text-xs text-gray-600">
          Triggered {{ timeAgo(data.triggered_at) }} ·
          <NuxtLink :to="`/stocks/${ticker.toLowerCase()}/`" class="text-emerald-700 hover:text-emerald-500">
            {{ data.name }}
          </NuxtLink>
        </p>
      </div>

      <!-- Intelligence insight -->
      <div v-if="data.insight?.summary" class="relative border rounded-lg p-5 overflow-hidden bg-[#0d1520] border-emerald-900/50 mb-6">
        <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"/>
        <div class="flex items-start gap-3">
          <span class="text-emerald-500 text-base mt-0.5 shrink-0">◆</span>
          <div>
            <div class="flex items-center gap-2 mb-2">
              <span class="text-[10px] font-bold uppercase tracking-widest text-emerald-500">MetricsHour Intelligence</span>
              <span class="text-[10px] text-gray-600">· Latest analyst take</span>
            </div>
            <p class="text-sm leading-relaxed text-gray-200">{{ data.insight.summary }}</p>
          </div>
        </div>
      </div>

      <!-- Revenue countries + macro context -->
      <div v-if="data.top_revenues?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-1">Geographic Revenue Exposure</h2>
        <p class="text-xs text-gray-500 mb-5">
          These markets represent {{ ticker }}'s largest revenue sources — moves in these economies directly affect earnings.
        </p>
        <div class="space-y-5">
          <div v-for="r in data.top_revenues" :key="r.code" class="flex flex-col sm:flex-row sm:items-center gap-3">
            <NuxtLink
              :to="`/countries/${r.code.toLowerCase()}/`"
              class="flex items-center gap-2 w-full sm:w-44 shrink-0 group"
            >
              <span class="text-xl">{{ r.flag }}</span>
              <div>
                <div class="text-sm font-semibold text-gray-200 group-hover:text-emerald-400 transition-colors">{{ r.name }}</div>
                <div class="text-[10px] text-gray-600">{{ r.revenue_pct }}% of revenue · FY{{ r.fiscal_year }}</div>
              </div>
            </NuxtLink>
            <div class="flex gap-4 flex-wrap">
              <div v-if="r.gdp_growth !== null" class="bg-[#0d1117] rounded-lg px-3 py-2">
                <div class="text-[10px] text-gray-600 mb-0.5">GDP Growth</div>
                <div class="text-sm font-bold" :class="(r.gdp_growth ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ r.gdp_growth >= 0 ? '+' : '' }}{{ r.gdp_growth }}%
                </div>
              </div>
              <div v-if="r.inflation !== null" class="bg-[#0d1117] rounded-lg px-3 py-2">
                <div class="text-[10px] text-gray-600 mb-0.5">Inflation</div>
                <div class="text-sm font-bold text-white">{{ r.inflation }}%</div>
              </div>
              <NuxtLink
                :to="`/countries/${r.code.toLowerCase()}/`"
                class="self-center text-xs text-emerald-700 hover:text-emerald-400 transition-colors"
              >View macro dashboard →</NuxtLink>
            </div>
          </div>
        </div>
      </div>

      <!-- CTA to full analysis -->
      <div class="bg-[#111827] border border-emerald-900/50 rounded-xl p-6 mb-6 text-center">
        <p class="text-white font-semibold mb-1">See the full picture</p>
        <p class="text-gray-500 text-sm mb-4">Geographic revenue breakdown, price chart, trade flows, and all macro data for {{ ticker }}.</p>
        <NuxtLink
          :to="`/stocks/${ticker.toLowerCase()}/`"
          class="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold px-6 py-2.5 rounded-lg transition-colors"
        >
          See full analysis for {{ ticker }} →
        </NuxtLink>
      </div>

      <!-- Comparable stocks (lower CN exposure) -->
      <div v-if="comparableStocks?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-1">Lower China Exposure Alternatives</h2>
        <p class="text-xs text-gray-500 mb-4">Same sector, less China revenue dependency.</p>
        <div class="divide-y divide-[#1f2937]">
          <NuxtLink
            v-for="s in comparableStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol.toLowerCase()}/`"
            class="flex items-center justify-between py-3 hover:bg-[#1f2937] -mx-2 px-2 rounded-lg transition-colors"
          >
            <div>
              <div class="text-sm font-bold text-emerald-400">{{ s.symbol }}</div>
              <div class="text-xs text-gray-500">{{ s.name }}</div>
            </div>
            <div class="flex items-center gap-4 text-right">
              <div>
                <div class="text-[10px] text-gray-600">CN%</div>
                <div class="text-xs font-semibold" :class="s.china_pct > 0 ? 'text-red-400' : 'text-gray-600'">{{ s.china_pct }}%</div>
              </div>
              <span class="text-sm font-semibold text-white tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
            </div>
          </NuxtLink>
        </div>
      </div>

      <p class="text-[10px] text-gray-700 text-center">
        This page is auto-generated and expires within 48 hours of the move triggering.
        Data updates every 15 minutes during US market hours. Not financial advice.
      </p>
    </template>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const { public: { apiBase } } = useRuntimeConfig()

const ticker = (route.params.ticker as string).toUpperCase()

// Fetch moving data — throws 404 if stock is not moving
const { data, error } = await useAsyncData(
  `moving-${ticker}`,
  () => $fetch<any>(`${apiBase}/api/stocks/${ticker}/moving`).catch((e) => {
    if (e?.response?.status === 404) return null
    throw e
  }),
)

// If clearly not moving, redirect to stock page
if (!data.value && !error.value) {
  await navigateTo(`/stocks/${ticker.toLowerCase()}/`, { redirectCode: 302 })
}

// Comparable stocks (lower China exposure, same sector not known here — use screener)
const { data: comparableData } = useAsyncData(
  `moving-comparable-${ticker}`,
  async () => {
    if (!data.value) return { results: [] }
    // Get current china pct from move data — we don't have sector here so just filter by china_max
    return $fetch<any>(`${apiBase}/api/screener`, {
      params: { china_max: 5, sort_by: 'market_cap', limit: 5 },
    }).catch(() => ({ results: [] }))
  },
  { server: false },
)

const comparableStocks = computed(() =>
  (comparableData.value?.results ?? [])
    .filter((s: any) => s.symbol !== ticker)
    .slice(0, 3),
)

function timeAgo(iso: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

// Dynamic SEO
const direction = data.value?.direction ?? 'moving'
const pct = data.value?.pct_change ?? 0
const metaTitle = direction === 'up'
  ? `Why is ${ticker} up ${pct}% today? — MetricsHour`
  : `Why is ${ticker} down ${pct}% today? — MetricsHour`
const topCountry = data.value?.top_revenues?.[0]?.name ?? 'international markets'
const metaDesc = direction === 'up'
  ? `${ticker} is up ${pct}%. ${topCountry} exposure and macro data from MetricsHour.`
  : `${ticker} is down ${pct}%. ${topCountry} exposure and macro data from MetricsHour.`

useHead({
  title: metaTitle,
  meta: [
    { name: 'description', content: metaDesc },
    { property: 'og:title', content: metaTitle },
    { property: 'og:description', content: metaDesc },
    { property: 'og:url', content: `https://metricshour.com/stocks/${ticker.toLowerCase()}/moving/` },
    { property: 'og:type', content: 'website' },
    // Noindex when not moving (safety net — redirect should handle this first)
    { name: 'robots', content: data.value ? 'index, follow' : 'noindex, follow' },
  ],
  link: [{ rel: 'canonical', href: `https://metricshour.com/stocks/${ticker.toLowerCase()}/moving/` }],
})
</script>
