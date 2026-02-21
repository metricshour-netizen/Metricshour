<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Stocks</h1>
      <p class="text-gray-500 text-sm mt-1">Top global stocks · Geographic revenue exposure · SEC EDGAR filings</p>
    </div>

    <!-- Search -->
    <div class="relative mb-4">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search ticker, company, sector..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
      />
      <button v-if="search" @click="search = ''" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs">✕</button>
    </div>

    <!-- Sector filter -->
    <div v-if="sectors.length" class="flex gap-2 flex-wrap mb-6">
      <button
        @click="activeSector = null"
        class="px-3 py-1.5 rounded text-xs font-medium border transition-colors"
        :class="!activeSector ? 'bg-emerald-500 border-emerald-500 text-black' : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >All</button>
      <button
        v-for="s in sectors"
        :key="s"
        @click="activeSector = activeSector === s ? null : s"
        class="px-3 py-1.5 rounded text-xs font-medium border transition-colors"
        :class="activeSector === s ? 'bg-emerald-500 border-emerald-500 text-black' : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >{{ s }}</button>
    </div>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>

    <template v-else>
      <p v-if="search" class="text-xs text-gray-600 mb-4">{{ filtered.length }} result{{ filtered.length !== 1 ? 's' : '' }} for "{{ search }}"</p>

      <div v-if="filtered.length" class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
        <!-- Desktop header -->
        <div class="hidden sm:grid grid-cols-12 px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide">
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
            class="block hover:bg-[#1a2235] transition-colors"
          >
            <!-- Mobile row -->
            <div class="flex items-center justify-between px-4 py-3 sm:hidden">
              <div class="flex items-center gap-2.5 min-w-0">
                <span v-if="s.country" class="text-base leading-none shrink-0">{{ s.country.flag }}</span>
                <div class="min-w-0">
                  <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
                  <div class="text-xs text-gray-500 truncate max-w-[160px]">{{ s.name }}</div>
                  <div class="text-[10px] text-gray-600 mt-0.5">{{ s.sector || '—' }}</div>
                </div>
              </div>
              <div class="text-right shrink-0 ml-2">
                <div class="text-sm text-white tabular-nums font-medium">{{ fmtCap(s.market_cap_usd) }}</div>
                <div class="text-emerald-500 text-xs mt-0.5">→</div>
              </div>
            </div>
            <!-- Desktop row -->
            <div class="hidden sm:grid grid-cols-12 px-4 py-3 items-center">
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
            </div>
          </NuxtLink>
        </div>
      </div>

      <div v-else-if="search" class="text-center py-16 text-gray-600 text-sm">
        No stocks match "{{ search }}"
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()
const activeSector = ref<string | null>(null)
const search = ref('')

const { data: stocks, pending } = await useAsyncData('stocks',
  () => get<any[]>('/api/assets?type=stock').catch(() => []),
)

const sectors = computed(() => {
  if (!stocks.value?.length) return []
  return [...new Set(stocks.value.map((s: any) => s.sector).filter(Boolean))].sort()
})

const filtered = computed(() => {
  if (!stocks.value) return []
  let list = stocks.value as any[]

  if (activeSector.value) {
    list = list.filter((s: any) => s.sector === activeSector.value)
  }

  if (search.value.trim()) {
    const q = search.value.toLowerCase().trim()
    list = list.filter((s: any) =>
      s.symbol?.toLowerCase().includes(q) ||
      s.name?.toLowerCase().includes(q) ||
      s.sector?.toLowerCase().includes(q) ||
      s.country?.name?.toLowerCase().includes(q)
    )
  }

  return list
})

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

useSeoMeta({
  title: 'Stocks — MetricsHour',
  description: 'Top global stocks with geographic revenue exposure from SEC EDGAR. See which countries each stock earns from and how trade flows affect your portfolio.',
})
</script>
