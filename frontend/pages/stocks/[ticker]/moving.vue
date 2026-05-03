<template>
  <main class="max-w-4xl mx-auto px-4 py-10">
    <NuxtLink :to="`/stocks/${ticker.toLowerCase()}/`" class="text-gray-500 text-xs hover:text-gray-300 transition-colors mb-6 inline-block">
      ← {{ ticker }}
    </NuxtLink>

    <div v-if="!data" class="text-center py-20">
      <p class="text-gray-500 text-sm">No significant move detected for {{ ticker }} today.</p>
      <NuxtLink :to="`/stocks/${ticker.toLowerCase()}/`" class="text-emerald-500 text-sm hover:text-emerald-400 mt-3 inline-block">View {{ ticker }} →</NuxtLink>
    </div>

    <template v-else>
      <!-- Hero -->
      <div class="mb-8">
        <div class="flex items-center gap-3 mb-3">
          <span
            class="text-xs font-bold uppercase tracking-widest px-3 py-1 rounded-full border"
            :class="data.direction === 'up'
              ? 'bg-emerald-900/40 text-emerald-400 border-emerald-800'
              : 'bg-red-900/40 text-red-400 border-red-800'"
          >{{ data.direction === 'up' ? '▲ Moving Up' : '▼ Moving Down' }}</span>
          <span class="text-[10px] text-gray-700">Updates every 15 min</span>
        </div>

        <h1 class="text-2xl sm:text-3xl font-extrabold text-white leading-tight mb-3">
          Why is {{ ticker }}
          <span :class="data.direction === 'up' ? 'text-emerald-400' : 'text-red-400'">
            {{ data.direction === 'up' ? 'up' : 'down' }} {{ data.pct_change }}%
          </span>
          today?
        </h1>

        <div class="flex items-baseline gap-4 mb-2">
          <span class="text-4xl font-extrabold text-white tabular-nums">${{ data.price_current?.toFixed(2) }}</span>
          <span class="text-lg font-bold tabular-nums" :class="data.direction === 'up' ? 'text-emerald-400' : 'text-red-400'">
            {{ data.direction === 'up' ? '+' : '-' }}{{ data.pct_change }}%
          </span>
          <span class="text-sm text-gray-600">Open: ${{ data.price_open?.toFixed(2) }}</span>
        </div>
        <p class="text-xs text-gray-600">{{ timeAgo(data.triggered_at) }}</p>
      </div>

      <!-- Intelligence insight -->
      <div v-if="data.insight?.summary" class="relative border rounded-lg p-5 bg-[#0d1520] border-emerald-900/50 mb-6">
        <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"/>
        <div class="flex items-start gap-3">
          <span class="text-emerald-500 shrink-0 mt-0.5">◆</span>
          <div>
            <span class="text-[10px] font-bold uppercase tracking-widest text-emerald-500 block mb-1.5">MetricsHour Intelligence</span>
            <p class="text-sm leading-relaxed text-gray-200">{{ data.insight.summary }}</p>
          </div>
        </div>
      </div>

      <!-- Revenue countries -->
      <div v-if="data.top_revenues?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-4">Geographic Revenue Exposure</h2>
        <div class="space-y-4">
          <div v-for="r in data.top_revenues" :key="r.code" class="flex flex-col sm:flex-row sm:items-center gap-3">
            <NuxtLink :to="`/countries/${r.code.toLowerCase()}/`" class="flex items-center gap-2 sm:w-44 shrink-0 group">
              <span class="text-xl">{{ r.flag }}</span>
              <div>
                <div class="text-sm font-semibold text-gray-200 group-hover:text-emerald-400 transition-colors">{{ r.name }}</div>
                <div class="text-[10px] text-gray-600">{{ r.revenue_pct }}% of revenue · FY{{ r.fiscal_year }}</div>
              </div>
            </NuxtLink>
            <div class="flex gap-3 flex-wrap">
              <div v-if="r.gdp_growth !== null" class="bg-[#0d1117] rounded px-3 py-1.5">
                <div class="text-[10px] text-gray-600">GDP Growth</div>
                <div class="text-sm font-bold" :class="(r.gdp_growth ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">{{ r.gdp_growth >= 0 ? '+' : '' }}{{ r.gdp_growth }}%</div>
              </div>
              <div v-if="r.inflation !== null" class="bg-[#0d1117] rounded px-3 py-1.5">
                <div class="text-[10px] text-gray-600">Inflation</div>
                <div class="text-sm font-bold text-white">{{ r.inflation }}%</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- CTA -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <p class="text-white font-semibold text-sm">Full analysis for {{ ticker }}</p>
          <p class="text-gray-500 text-xs mt-0.5">Revenue breakdown, price chart, trade flows</p>
        </div>
        <NuxtLink :to="`/stocks/${ticker.toLowerCase()}/`" class="shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors">
          See full analysis →
        </NuxtLink>
      </div>

      <p class="text-[10px] text-gray-700 text-center">Auto-generated · expires 48h after trigger · not financial advice</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const { public: { apiBase } } = useRuntimeConfig()
const ticker = (route.params.ticker as string).toUpperCase()

const { data, error } = await useAsyncData(
  `moving-${ticker}`,
  () => $fetch<any>(`${apiBase}/api/stocks/${ticker}/moving`).catch((e) => {
    if (e?.response?.status === 404) return null
    throw e
  }),
)

if (!data.value) {
  await navigateTo(`/stocks/${ticker.toLowerCase()}/`, { redirectCode: 302 })
}

function timeAgo(iso: string): string {
  if (!iso) return ''
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 60) return `${mins}m ago`
  return `${Math.floor(mins / 60)}h ago`
}

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

const direction = data.value?.direction ?? 'moving'
const pct = data.value?.pct_change ?? 0
const topCountry = data.value?.top_revenues?.[0]?.name ?? 'international markets'

const metaTitle = direction === 'up'
  ? `Why is ${ticker} up ${pct}% today? — MetricsHour`
  : `Why is ${ticker} down ${pct}% today? — MetricsHour`
const metaDesc = `${ticker} is ${direction} ${pct}% today. ${topCountry} revenue exposure and macro context from MetricsHour.`

useHead({
  title: metaTitle,
  meta: [
    { name: 'description', content: metaDesc },
    { property: 'og:title', content: metaTitle },
    { property: 'og:description', content: metaDesc },
    { property: 'og:url', content: `https://metricshour.com/stocks/${ticker.toLowerCase()}/moving/` },
    { name: 'robots', content: data.value ? 'index, follow' : 'noindex, follow' },
  ],
  link: [{ rel: 'canonical', href: `https://metricshour.com/stocks/${ticker.toLowerCase()}/moving/` }],
})
</script>
