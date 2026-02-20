<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white">Stocks</h1>
      <p class="text-gray-500 text-sm mt-1">
        Top global stocks · Geographic revenue exposure · SEC EDGAR filings
      </p>
    </div>

    <!-- Value props (shown when no data yet) -->
    <div v-if="!stocks?.length && !pending" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
      <div v-for="item in features" :key="item.title" class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
        <div class="text-xl mb-2">{{ item.icon }}</div>
        <h3 class="font-bold text-white text-sm mb-1">{{ item.title }}</h3>
        <p class="text-gray-500 text-xs">{{ item.desc }}</p>
      </div>
    </div>

    <!-- Sector filter (shown when data exists) -->
    <div v-if="sectors.length" class="flex gap-2 flex-wrap mb-6">
      <button
        @click="activeSector = null"
        class="px-3 py-1 rounded text-xs font-medium border transition-colors"
        :class="!activeSector ? 'bg-emerald-500 border-emerald-500 text-black' : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >All</button>
      <button
        v-for="s in sectors"
        :key="s"
        @click="activeSector = activeSector === s ? null : s"
        class="px-3 py-1 rounded text-xs font-medium border transition-colors"
        :class="activeSector === s ? 'bg-emerald-500 border-emerald-500 text-black' : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >{{ s }}</button>
    </div>

    <!-- Loading -->
    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>

    <!-- Stock table -->
    <div v-else-if="filtered.length" class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
      <div class="grid grid-cols-12 px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide">
        <span class="col-span-1">#</span>
        <span class="col-span-5">Company</span>
        <span class="col-span-3">Sector</span>
        <span class="col-span-2 text-right">Market Cap</span>
        <span class="col-span-1"></span>
      </div>
      <div class="divide-y divide-[#1f2937]">
        <NuxtLink
          v-for="(s, i) in filtered"
          :key="s.symbol"
          :to="`/stocks/${s.symbol}`"
          class="grid grid-cols-12 px-4 py-3 hover:bg-[#1a2235] transition-colors items-center"
        >
          <span class="col-span-1 text-xs text-gray-600">{{ i + 1 }}</span>
          <div class="col-span-5 flex items-center gap-2">
            <span v-if="s.country" class="text-base leading-none">{{ s.country.flag }}</span>
            <div>
              <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
              <div class="text-xs text-gray-500 truncate">{{ s.name }}</div>
            </div>
          </div>
          <span class="col-span-3 text-xs text-gray-500">{{ s.sector || '—' }}</span>
          <span class="col-span-2 text-xs text-right text-white tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
          <span class="col-span-1 text-right text-emerald-500 text-xs">→</span>
        </NuxtLink>
      </div>
    </div>

    <!-- Coming soon skeleton (no data yet) -->
    <div v-else-if="!pending" class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
      <div class="px-5 py-3 border-b border-[#1f2937] flex items-center justify-between">
        <span class="text-sm font-medium text-white">Top Stocks</span>
        <span class="text-xs text-yellow-400">Run asset seeder to populate</span>
      </div>
      <div class="divide-y divide-[#1f2937]">
        <div v-for="i in 8" :key="i" class="px-4 py-3 flex items-center gap-4">
          <div class="w-6 h-3 bg-[#1f2937] rounded animate-pulse shrink-0" />
          <div class="flex-1 space-y-1.5">
            <div class="h-3 bg-[#1f2937] rounded animate-pulse w-20" />
            <div class="h-2.5 bg-[#1f2937] rounded animate-pulse w-32" />
          </div>
          <div class="h-3 bg-[#1f2937] rounded animate-pulse w-16" />
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()
const activeSector = ref<string | null>(null)

const { data: stocks, pending } = await useAsyncData('stocks',
  () => get<any[]>('/api/assets?type=stock').catch(() => []),
)

const sectors = computed(() => {
  if (!stocks.value?.length) return []
  return [...new Set(stocks.value.map((s: any) => s.sector).filter(Boolean))].sort()
})

const filtered = computed(() => {
  if (!stocks.value) return []
  if (!activeSector.value) return stocks.value
  return stocks.value.filter((s: any) => s.sector === activeSector.value)
})

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

const features = [
  {
    icon: '🗺️',
    title: 'Geographic Revenue Exposure',
    desc: 'See exactly which countries each stock earns from — straight from SEC 10-K filings, not analyst estimates.',
  },
  {
    icon: '🔗',
    title: 'Connected to Trade Data',
    desc: 'When US-China trade tension spikes, instantly see which stocks have China revenue exposure.',
  },
  {
    icon: '📊',
    title: 'Real-Time Prices',
    desc: 'Live quotes for Pro subscribers. 15-minute delayed prices free for everyone.',
  },
]

useSeoMeta({
  title: 'Stocks — MetricsHour',
  description: 'Top global stocks with geographic revenue exposure from SEC EDGAR. See which countries each stock earns from and how trade flows affect your portfolio.',
})
</script>
