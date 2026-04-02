<template>
  <div>
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-10">
        <NuxtLink to="/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">← Home</NuxtLink>
        <div class="flex items-center gap-4 mb-3">
          <span class="text-4xl" aria-hidden="true">🇨🇳</span>
          <div>
            <h1 class="text-3xl font-extrabold text-white tracking-tight">China A-Shares</h1>
            <p class="text-gray-400 text-sm mt-1">Shanghai (SHG) &amp; Shenzhen (SHE) listed stocks — priced in CNY</p>
          </div>
        </div>
        <p class="text-gray-500 text-xs max-w-2xl">
          China A-shares are mainland Chinese stocks traded on the Shanghai and Shenzhen exchanges.
          Prices are denominated in Chinese Yuan (CNY). Data sourced from Tiingo.
        </p>
      </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-8">
      <!-- Stats row -->
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Listed Stocks</div>
          <div class="text-white font-bold text-xl">{{ stocks?.length || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Exchanges</div>
          <div class="text-white font-bold text-xl">SHG · SHE</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Currency</div>
          <div class="text-white font-bold text-xl">CNY ¥</div>
        </div>
      </div>

      <!-- Search -->
      <div class="mb-5">
        <input
          v-model="search"
          type="text"
          placeholder="Search by name or ticker..."
          class="w-full sm:w-80 bg-[#111827] border border-[#1f2937] text-white text-sm px-4 py-2 rounded-lg placeholder-gray-600 focus:outline-none focus:border-emerald-700"
        />
      </div>

      <!-- Table -->
      <div v-if="pending" class="space-y-2">
        <div v-for="i in 20" :key="i" class="h-12 bg-[#111827] rounded-lg animate-pulse" />
      </div>

      <div v-else-if="!filtered?.length" class="text-center py-16 text-gray-600">
        <div class="text-3xl mb-3">📊</div>
        <p class="text-sm">{{ search ? 'No stocks match your search.' : 'No China A-share data yet — check back soon.' }}</p>
      </div>

      <div v-else class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#1f2937]">
              <th class="text-left text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3">Ticker</th>
              <th class="text-left text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3">Name</th>
              <th class="text-right text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3">Price (CNY)</th>
              <th class="text-right text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3 hidden sm:table-cell">Change</th>
              <th class="text-right text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3 hidden md:table-cell">Exchange</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in paginated"
              :key="s.id"
              class="border-b border-[#1a2030] hover:bg-[#0d1117] transition-colors cursor-pointer"
              @click="navigateTo(`/stocks/${s.symbol}`)"
            >
              <td class="px-4 py-3 font-mono text-xs text-emerald-400">{{ s.symbol }}</td>
              <td class="px-4 py-3 text-gray-200 truncate max-w-[200px]">{{ s.name }}</td>
              <td class="px-4 py-3 text-right font-bold text-white tabular-nums">
                {{ s.price ? `¥${s.price.close?.toFixed(2)}` : '—' }}
              </td>
              <td class="px-4 py-3 text-right tabular-nums hidden sm:table-cell"
                :class="s.price?.change_pct != null ? (s.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400') : 'text-gray-600'">
                {{ s.price?.change_pct != null ? `${s.price.change_pct >= 0 ? '+' : ''}${s.price.change_pct.toFixed(2)}%` : '—' }}
              </td>
              <td class="px-4 py-3 text-right text-gray-500 text-xs hidden md:table-cell">{{ s.exchange }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between px-4 py-3 border-t border-[#1f2937]">
          <button
            @click="page = Math.max(1, page - 1)"
            :disabled="page === 1"
            class="text-xs px-3 py-1.5 rounded border border-[#1f2937] text-gray-400 disabled:opacity-30 hover:border-emerald-700 hover:text-emerald-400 transition-colors"
          >← Prev</button>
          <span class="text-xs text-gray-600">Page {{ page }} / {{ totalPages }}</span>
          <button
            @click="page = Math.min(totalPages, page + 1)"
            :disabled="page === totalPages"
            class="text-xs px-3 py-1.5 rounded border border-[#1f2937] text-gray-400 disabled:opacity-30 hover:border-emerald-700 hover:text-emerald-400 transition-colors"
          >Next →</button>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center mt-6">Data: Tiingo · Prices in CNY · Updated daily after market close</p>
    </main>
  </div>
</template>

<script setup lang="ts">
const { get } = useApi()

const { data: stocks, pending } = await useAsyncData(
  'china-stocks',
  () => get<any[]>('/api/assets', { type: 'stock', exchange: 'SHG', limit: 500 })
    .then(async (shg) => {
      const she = await get<any[]>('/api/assets', { type: 'stock', exchange: 'SHE', limit: 500 }).catch(() => [])
      return [...(shg || []), ...(she || [])]
    })
    .catch(() => []),
)

const search = ref('')
const page = ref(1)
const PAGE_SIZE = 50

const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  const all = stocks.value ?? []
  if (!q) return all
  return all.filter(s =>
    s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
  )
})

watch(search, () => { page.value = 1 })

const totalPages = computed(() => Math.max(1, Math.ceil((filtered.value?.length || 0) / PAGE_SIZE)))
const paginated = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filtered.value?.slice(start, start + PAGE_SIZE) ?? []
})

useSeoMeta({
  title: 'China A-Shares — Shanghai & Shenzhen Stocks | MetricsHour',
  description: 'Browse China A-share stocks listed on the Shanghai (SHG) and Shenzhen (SHE) exchanges with live CNY prices. Powered by Tiingo.',
  ogTitle: 'China A-Shares | MetricsHour',
  ogDescription: 'Shanghai and Shenzhen listed stocks with live CNY prices.',
})
</script>
