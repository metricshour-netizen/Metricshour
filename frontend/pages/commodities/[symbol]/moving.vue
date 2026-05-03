<template>
  <main class="max-w-4xl mx-auto px-4 py-10">
    <NuxtLink :to="`/commodities/${symbol.toLowerCase()}/`" class="text-gray-500 text-xs hover:text-gray-300 transition-colors mb-6 inline-block">
      ← {{ symbol.toUpperCase() }}
    </NuxtLink>

    <div v-if="!data" class="text-center py-20">
      <p class="text-gray-500 text-sm">No significant move detected for {{ symbol.toUpperCase() }} today.</p>
      <NuxtLink :to="`/commodities/${symbol.toLowerCase()}/`" class="text-emerald-500 text-sm hover:text-emerald-400 mt-3 inline-block">View {{ symbol.toUpperCase() }} →</NuxtLink>
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
          <span class="text-[10px] text-gray-700">Updated daily</span>
        </div>

        <h1 class="text-2xl sm:text-3xl font-extrabold text-white leading-tight mb-3">
          Why is {{ data.name }}
          <span :class="data.direction === 'up' ? 'text-emerald-400' : 'text-red-400'">
            {{ data.direction === 'up' ? 'up' : 'down' }} {{ data.pct_change }}%
          </span>
          today?
        </h1>

        <div class="flex items-baseline gap-4 mb-2">
          <span class="text-4xl font-extrabold text-white tabular-nums">${{ fmtPrice(data.price_current) }}</span>
          <span class="text-lg font-bold tabular-nums" :class="data.direction === 'up' ? 'text-emerald-400' : 'text-red-400'">
            {{ data.direction === 'up' ? '+' : '-' }}{{ data.pct_change }}%
          </span>
          <span class="text-sm text-gray-600">Open: ${{ fmtPrice(data.price_open) }}</span>
        </div>
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

      <!-- CTA -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <p class="text-white font-semibold text-sm">Full analysis for {{ data.name }}</p>
          <p class="text-gray-500 text-xs mt-0.5">Price chart, key producers, trade flows</p>
        </div>
        <NuxtLink :to="`/commodities/${symbol.toLowerCase()}/`" class="shrink-0 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors">
          See full analysis →
        </NuxtLink>
      </div>

      <p class="text-[10px] text-gray-700 text-center">Auto-generated · not financial advice</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const { public: { apiBase } } = useRuntimeConfig()
const symbol = (route.params.symbol as string).toLowerCase()
const symUp = symbol.toUpperCase()

const { data } = await useAsyncData(
  `moving-commodity-${symUp}`,
  () => $fetch<any>(`${apiBase}/api/commodities/${symUp}/moving`).catch((e) => {
    if (e?.response?.status === 404) return null
    throw e
  }),
)

if (!data.value) {
  await navigateTo(`/commodities/${symbol}/`, { redirectCode: 302 })
}

function fmtPrice(v: number | null): string {
  if (v == null) return '—'
  if (v >= 1000) return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return v.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

const name = data.value?.name ?? symUp
const pct = data.value?.pct_change ?? 0
const dir = data.value?.direction ?? 'moving'

const metaTitle = dir === 'up'
  ? `Why is ${name} up ${pct}% today? — MetricsHour`
  : `Why is ${name} down ${pct}% today? — MetricsHour`
const metaDesc = `${name} is ${dir} ${pct}% today. Commodity market analysis and macro context from MetricsHour.`

useHead({
  title: metaTitle,
  meta: [
    { name: 'description', content: metaDesc },
    { property: 'og:title', content: metaTitle },
    { property: 'og:description', content: metaDesc },
    { property: 'og:url', content: `https://metricshour.com/commodities/${symbol}/moving/` },
    { name: 'robots', content: data.value ? 'index, follow' : 'noindex, follow' },
  ],
  link: [{ rel: 'canonical', href: `https://metricshour.com/commodities/${symbol}/moving/` }],
})
</script>
