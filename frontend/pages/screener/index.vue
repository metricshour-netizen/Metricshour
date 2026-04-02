<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Stock Screener</h1>
      <p class="text-gray-500 text-sm mt-1">Filter S&amp;P 500 stocks by geographic revenue exposure · SEC EDGAR data</p>
    </div>

    <!-- Filters -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-6">
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <!-- China Revenue Max -->
        <div>
          <label class="block text-[10px] text-gray-500 uppercase tracking-wide mb-1">China Rev Max %</label>
          <input
            v-model.number="filters.china_max"
            type="number" min="0" max="100" step="5"
            placeholder="e.g. 10"
            class="w-full bg-[#0f1623] border border-[#1f2937] rounded px-2.5 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <!-- US Revenue Min -->
        <div>
          <label class="block text-[10px] text-gray-500 uppercase tracking-wide mb-1">US Rev Min %</label>
          <input
            v-model.number="filters.us_min"
            type="number" min="0" max="100" step="5"
            placeholder="e.g. 50"
            class="w-full bg-[#0f1623] border border-[#1f2937] rounded px-2.5 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <!-- US Revenue Max -->
        <div>
          <label class="block text-[10px] text-gray-500 uppercase tracking-wide mb-1">US Rev Max %</label>
          <input
            v-model.number="filters.us_max"
            type="number" min="0" max="100" step="5"
            placeholder="e.g. 90"
            class="w-full bg-[#0f1623] border border-[#1f2937] rounded px-2.5 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <!-- Sector -->
        <div>
          <label class="block text-[10px] text-gray-500 uppercase tracking-wide mb-1">Sector</label>
          <select
            v-model="filters.sector"
            class="w-full bg-[#0f1623] border border-[#1f2937] rounded px-2.5 py-1.5 text-sm text-white focus:outline-none focus:border-emerald-500"
          >
            <option value="">All</option>
            <option v-for="s in sectors" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <!-- Market Cap Min -->
        <div>
          <label class="block text-[10px] text-gray-500 uppercase tracking-wide mb-1">Mkt Cap Min ($B)</label>
          <input
            v-model.number="filters.market_cap_min"
            type="number" min="0" step="10"
            placeholder="e.g. 10"
            class="w-full bg-[#0f1623] border border-[#1f2937] rounded px-2.5 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <!-- Country Exposure -->
        <div>
          <label class="block text-[10px] text-gray-500 uppercase tracking-wide mb-1">Country Exposure</label>
          <input
            v-model="filters.country_code"
            type="text" maxlength="2"
            placeholder="e.g. DE"
            class="w-full bg-[#0f1623] border border-[#1f2937] rounded px-2.5 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 uppercase"
            @input="filters.country_code = filters.country_code.toUpperCase()"
          />
        </div>
      </div>

      <!-- Preset buttons -->
      <div class="flex flex-wrap gap-2 mt-4 pt-3 border-t border-[#1f2937]">
        <span class="text-[10px] text-gray-600 uppercase tracking-wide self-center mr-1">Presets:</span>
        <button
          v-for="preset in PRESETS"
          :key="preset.label"
          @click="applyPreset(preset)"
          class="px-2.5 py-1 text-xs rounded border transition-colors border-[#1f2937] text-gray-400 hover:border-emerald-700 hover:text-emerald-400"
        >{{ preset.label }}</button>
        <button
          @click="resetFilters"
          class="ml-auto px-2.5 py-1 text-xs rounded border border-[#1f2937] text-gray-600 hover:border-gray-500 hover:text-gray-400 transition-colors"
        >Reset</button>
      </div>
    </div>

    <!-- Sort controls + result count -->
    <div class="flex items-center justify-between mb-3">
      <p class="text-xs text-gray-500">
        <span v-if="pending">Loading…</span>
        <span v-else><span class="text-white font-medium">{{ data?.total ?? 0 }}</span> stocks match</span>
      </p>
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-600">Sort:</span>
        <select
          v-model="sortBy"
          class="bg-[#111827] border border-[#1f2937] rounded px-2 py-1 text-xs text-gray-300 focus:outline-none focus:border-emerald-500"
        >
          <option value="market_cap">Market Cap</option>
          <option value="china_pct">China %</option>
          <option value="us_pct">US %</option>
          <option value="country_count">Countries</option>
          <option value="symbol">Ticker</option>
        </select>
        <button
          @click="sortDir = sortDir === 'desc' ? 'asc' : 'desc'"
          class="px-2 py-1 text-xs border border-[#1f2937] rounded text-gray-400 hover:border-gray-500 transition-colors"
        >{{ sortDir === 'desc' ? '↓' : '↑' }}</button>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
      <!-- Header -->
      <div class="hidden sm:grid px-4 py-2 border-b border-[#1f2937] text-[10px] text-gray-500 uppercase tracking-wide"
           style="grid-template-columns: 2rem 1fr 7rem 6rem 5rem 5rem 4rem 1.5rem">
        <span>#</span>
        <span>Company</span>
        <span>Sector</span>
        <span class="text-right cursor-pointer hover:text-gray-300" @click="setSortBy('market_cap')">
          Mkt Cap <span v-if="sortBy === 'market_cap'">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
        </span>
        <span class="text-right cursor-pointer hover:text-gray-300" @click="setSortBy('china_pct')">
          China % <span v-if="sortBy === 'china_pct'">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
        </span>
        <span class="text-right cursor-pointer hover:text-gray-300" @click="setSortBy('us_pct')">
          US % <span v-if="sortBy === 'us_pct'">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
        </span>
        <span class="text-right cursor-pointer hover:text-gray-300" @click="setSortBy('country_count')">
          Countries <span v-if="sortBy === 'country_count'">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
        </span>
        <span></span>
      </div>

      <!-- Loading skeleton -->
      <div v-if="pending" class="divide-y divide-[#1f2937]">
        <div v-for="i in 10" :key="i" class="px-4 py-3 flex gap-3 items-center">
          <div class="h-3 bg-[#1f2937] rounded w-8 animate-pulse"></div>
          <div class="h-3 bg-[#1f2937] rounded flex-1 animate-pulse"></div>
          <div class="h-3 bg-[#1f2937] rounded w-16 animate-pulse"></div>
        </div>
      </div>

      <!-- Results -->
      <div v-else-if="data?.results?.length" class="divide-y divide-[#1f2937]">
        <NuxtLink
          v-for="(s, i) in data.results"
          :key="s.symbol"
          :to="`/stocks/${s.symbol.toLowerCase()}`"
          class="block hover:bg-[#1a2235] transition-colors"
        >
          <!-- Mobile -->
          <div class="flex items-center justify-between px-4 py-3 sm:hidden">
            <div class="min-w-0">
              <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
              <div class="text-xs text-gray-500 truncate max-w-[160px]">{{ s.name }}</div>
              <div class="text-[10px] text-gray-600 mt-0.5">{{ s.sector || '—' }}</div>
            </div>
            <div class="text-right shrink-0 ml-2 space-y-0.5">
              <div class="text-xs text-gray-300 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</div>
              <div class="text-[10px] tabular-nums">
                <span class="text-red-400">CN {{ s.china_pct }}%</span>
                <span class="text-gray-600 mx-1">·</span>
                <span class="text-blue-400">US {{ s.us_pct }}%</span>
              </div>
              <div v-if="!s.has_revenue_data" class="text-[9px] text-gray-700">no EDGAR data</div>
            </div>
          </div>

          <!-- Desktop -->
          <div class="hidden sm:grid px-4 py-2.5 items-center"
               style="grid-template-columns: 2rem 1fr 7rem 6rem 5rem 5rem 4rem 1.5rem">
            <span class="text-xs text-gray-600">{{ offset + i + 1 }}</span>
            <div class="min-w-0 pr-2">
              <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
              <div class="text-xs text-gray-500 truncate">{{ s.name }}</div>
            </div>
            <span class="text-xs text-gray-500 truncate pr-2">{{ s.sector || '—' }}</span>
            <span class="text-xs text-right text-gray-400 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
            <div class="text-right">
              <span
                class="text-xs tabular-nums font-medium"
                :class="chinaPctClass(s.china_pct)"
              >{{ s.china_pct > 0 ? s.china_pct + '%' : (s.has_revenue_data ? '0%' : '—') }}</span>
            </div>
            <span class="text-xs text-right text-blue-400 tabular-nums">{{ s.us_pct > 0 ? s.us_pct + '%' : (s.has_revenue_data ? '0%' : '—') }}</span>
            <span class="text-xs text-right text-gray-500 tabular-nums">{{ s.country_count > 0 ? s.country_count : '—' }}</span>
            <span class="text-right text-emerald-600 text-xs">→</span>
          </div>
        </NuxtLink>
      </div>

      <div v-else class="text-center py-16 text-gray-600 text-sm">
        No stocks match these filters.
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="data && data.total > PAGE_SIZE" class="flex items-center justify-between mt-4">
      <button
        @click="offset = Math.max(0, offset - PAGE_SIZE)"
        :disabled="offset === 0"
        class="px-3 py-1.5 text-xs border border-[#1f2937] rounded text-gray-400 hover:border-gray-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >← Prev</button>
      <span class="text-xs text-gray-600">{{ offset + 1 }}–{{ Math.min(offset + PAGE_SIZE, data.total) }} of {{ data.total }}</span>
      <button
        @click="offset += PAGE_SIZE"
        :disabled="offset + PAGE_SIZE >= data.total"
        class="px-3 py-1.5 text-xs border border-[#1f2937] rounded text-gray-400 hover:border-gray-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      >Next →</button>
    </div>

    <!-- Data note -->
    <p class="text-[10px] text-gray-700 mt-6 text-center">
      Revenue data from SEC EDGAR 10-K/10-Q filings · {{ data?.results?.filter(r => r.has_revenue_data).length ?? 0 }} of {{ data?.results?.length ?? 0 }} shown stocks have EDGAR data
    </p>
  </main>
</template>

<script setup lang="ts">
const API = useRuntimeConfig().public.apiBase

const PAGE_SIZE = 50

const PRESETS = [
  { label: 'No China exposure',    filters: { china_max: 0 } },
  { label: 'Low China (<5%)',       filters: { china_max: 5 } },
  { label: 'High US (>70%)',        filters: { us_min: 70 } },
  { label: 'Tech sector',           filters: { sector: 'Information Technology' } },
  { label: 'Large cap (>$100B)',    filters: { market_cap_min: 100 } },
  { label: 'China exposed (>20%)',  filters: { china_min: 20 } },
]

const defaultFilters = () => ({
  china_max: null as number | null,
  china_min: null as number | null,
  us_min: null as number | null,
  us_max: null as number | null,
  sector: '',
  market_cap_min: null as number | null,
  country_code: '',
})

const filters = reactive(defaultFilters())
const sortBy = ref('market_cap')
const sortDir = ref<'asc' | 'desc'>('desc')
const offset = ref(0)

// Reset offset when filters/sort change
watch([filters, sortBy, sortDir], () => { offset.value = 0 }, { deep: true })

// Build query params
const queryParams = computed(() => {
  const p: Record<string, string | number> = {
    sort_by: sortBy.value,
    sort_dir: sortDir.value,
    limit: PAGE_SIZE,
    offset: offset.value,
  }
  if (filters.china_max !== null && filters.china_max !== undefined) p.china_max = filters.china_max
  if (filters.china_min !== null && filters.china_min !== undefined) p.china_min = filters.china_min
  if (filters.us_min !== null && filters.us_min !== undefined) p.us_min = filters.us_min
  if (filters.us_max !== null && filters.us_max !== undefined) p.us_max = filters.us_max
  if (filters.sector) p.sector = filters.sector
  if (filters.market_cap_min !== null && filters.market_cap_min !== undefined) p.market_cap_min = filters.market_cap_min
  if (filters.country_code) p.country_code = filters.country_code
  return p
})

const { data, pending, refresh } = await useAsyncData(
  'screener',
  () => $fetch(`${API}/api/screener`, { params: queryParams.value }),
  { watch: [queryParams] }
)

const { data: sectorsData } = await useAsyncData(
  'screener-sectors',
  () => $fetch<string[]>(`${API}/api/screener/sectors`)
)
const sectors = computed(() => sectorsData.value ?? [])

function applyPreset(preset: { label: string; filters: Record<string, any> }) {
  Object.assign(filters, defaultFilters())
  Object.assign(filters, preset.filters)
}

function resetFilters() {
  Object.assign(filters, defaultFilters())
  sortBy.value = 'market_cap'
  sortDir.value = 'desc'
  offset.value = 0
}

function setSortBy(col: string) {
  if (sortBy.value === col) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = col
    sortDir.value = 'desc'
  }
}

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  if (v >= 1e6)  return `$${(v / 1e6).toFixed(0)}M`
  return `$${v.toLocaleString()}`
}

function chinaPctClass(pct: number): string {
  if (pct === 0) return 'text-gray-600'
  if (pct < 5)  return 'text-yellow-600'
  if (pct < 15) return 'text-yellow-400'
  if (pct < 30) return 'text-orange-400'
  return 'text-red-400'
}

useHead({
  title: 'Stock Screener — Filter by China/US Revenue Exposure | MetricsHour',
  meta: [
    { name: 'description', content: 'Screen S&P 500 stocks by geographic revenue exposure. Find stocks with low China exposure, high US revenue, or specific sector focus.' },
    { property: 'og:title', content: 'Stock Screener — MetricsHour' },
    { property: 'og:description', content: 'Filter 465 S&P 500 stocks by China revenue %, US revenue %, sector, and market cap.' },
    { property: 'og:image', content: 'https://cdn.metricshour.com/og/section/home.png' },
    { property: 'og:type', content: 'website' },
  ],
  link: [{ rel: 'canonical', href: 'https://metricshour.com/screener/' }]
})
</script>
