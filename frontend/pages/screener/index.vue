<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Stock Screener</h1>
      <p class="text-gray-500 text-sm mt-1">Filter S&amp;P 500 stocks by geographic revenue exposure · SEC EDGAR data</p>
    </div>

    <!-- Filters -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-6">
      <!-- Sliders grid -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-4 mb-4">

        <!-- China % range -->
        <div>
          <div class="flex justify-between items-center mb-1">
            <label class="text-[10px] text-gray-500 uppercase tracking-wide">China Rev %</label>
            <span class="text-[10px] text-red-400 tabular-nums">{{ filters.china_min ?? 0 }}–{{ filters.china_max ?? 100 }}</span>
          </div>
          <RangeSlider v-model:min="filters.china_min" v-model:max="filters.china_max" :step="5" color="red" />
        </div>

        <!-- US % range -->
        <div>
          <div class="flex justify-between items-center mb-1">
            <label class="text-[10px] text-gray-500 uppercase tracking-wide">US Rev %</label>
            <span class="text-[10px] text-blue-400 tabular-nums">{{ filters.us_min ?? 0 }}–{{ filters.us_max ?? 100 }}</span>
          </div>
          <RangeSlider v-model:min="filters.us_min" v-model:max="filters.us_max" :step="5" color="blue" />
        </div>

        <!-- EU % range -->
        <div>
          <div class="flex justify-between items-center mb-1">
            <label class="text-[10px] text-gray-500 uppercase tracking-wide">{{ $t('screener.filters.eu') }}</label>
            <span class="text-[10px] text-purple-400 tabular-nums">{{ filters.eu_min ?? 0 }}–{{ filters.eu_max ?? 100 }}</span>
          </div>
          <RangeSlider v-model:min="filters.eu_min" v-model:max="filters.eu_max" :step="5" color="purple" />
        </div>

        <!-- Japan % range -->
        <div>
          <div class="flex justify-between items-center mb-1">
            <label class="text-[10px] text-gray-500 uppercase tracking-wide">{{ $t('screener.filters.japan') }}</label>
            <span class="text-[10px] text-pink-400 tabular-nums">{{ filters.japan_min ?? 0 }}–{{ filters.japan_max ?? 100 }}</span>
          </div>
          <RangeSlider v-model:min="filters.japan_min" v-model:max="filters.japan_max" :step="5" color="pink" />
        </div>

        <!-- India % range -->
        <div>
          <div class="flex justify-between items-center mb-1">
            <label class="text-[10px] text-gray-500 uppercase tracking-wide">{{ $t('screener.filters.india') }}</label>
            <span class="text-[10px] text-orange-400 tabular-nums">{{ filters.india_min ?? 0 }}–{{ filters.india_max ?? 100 }}</span>
          </div>
          <RangeSlider v-model:min="filters.india_min" v-model:max="filters.india_max" :step="5" color="orange" />
        </div>

        <!-- EM % range -->
        <div>
          <div class="flex justify-between items-center mb-1">
            <label class="text-[10px] text-gray-500 uppercase tracking-wide">{{ $t('screener.filters.em') }}</label>
            <span class="text-[10px] text-yellow-400 tabular-nums">{{ filters.em_min ?? 0 }}–{{ filters.em_max ?? 100 }}</span>
          </div>
          <RangeSlider v-model:min="filters.em_min" v-model:max="filters.em_max" :step="5" color="yellow" />
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

        <!-- Sector + Country -->
        <div class="flex gap-2">
          <div class="flex-1">
            <label class="block text-[10px] text-gray-500 uppercase tracking-wide mb-1">Sector</label>
            <select
              v-model="filters.sector"
              class="w-full bg-[#0f1623] border border-[#1f2937] rounded px-2.5 py-1.5 text-sm text-white focus:outline-none focus:border-emerald-500"
            >
              <option value="">All</option>
              <option v-for="s in sectors" :key="s" :value="s">{{ s }}</option>
            </select>
          </div>
          <div class="w-20">
            <label class="block text-[10px] text-gray-500 uppercase tracking-wide mb-1">Country</label>
            <input
              v-model="filters.country_code"
              type="text" maxlength="2"
              placeholder="DE"
              class="w-full bg-[#0f1623] border border-[#1f2937] rounded px-2.5 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 uppercase"
              @input="filters.country_code = filters.country_code.toUpperCase()"
            />
          </div>
        </div>
      </div>

      <!-- Preset buttons -->
      <div class="flex flex-wrap gap-2 pt-3 border-t border-[#1f2937]">
        <span class="text-[10px] text-gray-600 uppercase tracking-wide self-center mr-1">Presets:</span>
        <button
          v-for="preset in PRESETS"
          :key="preset.key"
          @click="applyPreset(preset)"
          class="px-2.5 py-1 text-xs rounded border transition-colors"
          :class="activePresetKey === preset.key
            ? 'border-emerald-600 text-emerald-400 bg-emerald-900/20'
            : 'border-[#1f2937] text-gray-400 hover:border-emerald-700 hover:text-emerald-400'"
        >{{ $t(`screener.presets.${preset.key}`) }}</button>
        <button
          @click="resetFilters"
          class="ml-auto px-2.5 py-1 text-xs rounded border border-[#1f2937] text-gray-600 hover:border-gray-500 hover:text-gray-400 transition-colors"
        >Reset</button>
      </div>
    </div>

    <!-- Sort controls + result count + export -->
    <div class="flex items-center justify-between mb-3 gap-3 flex-wrap">
      <p class="text-xs text-gray-500">
        <span v-if="pending">Loading…</span>
        <span v-else><span class="text-white font-medium">{{ data?.total ?? 0 }}</span> stocks match</span>
      </p>
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-xs text-gray-600">Sort:</span>
        <select
          v-model="sortBy"
          class="bg-[#111827] border border-[#1f2937] rounded px-2 py-1 text-xs text-gray-300 focus:outline-none focus:border-emerald-500"
        >
          <option value="market_cap">Market Cap</option>
          <option value="china_pct">China %</option>
          <option value="us_pct">US %</option>
          <option value="eu_pct">{{ $t('screener.sort.eu_pct') }}</option>
          <option value="japan_pct">{{ $t('screener.sort.japan_pct') }}</option>
          <option value="india_pct">{{ $t('screener.sort.india_pct') }}</option>
          <option value="em_pct">{{ $t('screener.sort.em_pct') }}</option>
          <option value="country_count">Countries</option>
          <option value="symbol">Ticker</option>
        </select>
        <button
          @click="sortDir = sortDir === 'desc' ? 'asc' : 'desc'"
          class="px-2 py-1 text-xs border border-[#1f2937] rounded text-gray-400 hover:border-gray-500 transition-colors"
        >{{ sortDir === 'desc' ? '↓' : '↑' }}</button>
        <!-- CSV Export -->
        <a
          :href="exportUrl"
          :download="`metricshour-screener-${today}.csv`"
          class="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-[#1f2937] text-gray-400 hover:border-emerald-700 hover:text-emerald-400 transition-colors"
        >
          <span>↓</span>
          <span>{{ $t('screener.export') }}</span>
        </a>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
      <!-- Header -->
      <div class="hidden sm:grid px-4 py-2 border-b border-[#1f2937] text-[10px] text-gray-500 uppercase tracking-wide"
           style="grid-template-columns: 2rem 1fr 7rem 6rem 5rem 5rem 4rem 4rem 1.5rem">
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
        <span class="text-right cursor-pointer hover:text-gray-300" @click="setSortBy('eu_pct')">
          EU % <span v-if="sortBy === 'eu_pct'">{{ sortDir === 'desc' ? '↓' : '↑' }}</span>
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
                <span v-if="s.eu_pct > 0" class="text-gray-600 mx-1">·</span>
                <span v-if="s.eu_pct > 0" class="text-purple-400">EU {{ s.eu_pct }}%</span>
              </div>
              <div v-if="!s.has_revenue_data" class="text-[9px] text-gray-700">no EDGAR data</div>
            </div>
          </div>

          <!-- Desktop -->
          <div class="hidden sm:grid px-4 py-2.5 items-center"
               style="grid-template-columns: 2rem 1fr 7rem 6rem 5rem 5rem 4rem 4rem 1.5rem">
            <span class="text-xs text-gray-600">{{ offset + i + 1 }}</span>
            <div class="min-w-0 pr-2">
              <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
              <div class="text-xs text-gray-500 truncate">{{ s.name }}</div>
            </div>
            <span class="text-xs text-gray-500 truncate pr-2">{{ s.sector || '—' }}</span>
            <span class="text-xs text-right text-gray-400 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
            <div class="text-right">
              <span class="text-xs tabular-nums font-medium" :class="chinaPctClass(s.china_pct)">
                {{ s.china_pct > 0 ? s.china_pct + '%' : (s.has_revenue_data ? '0%' : '—') }}
              </span>
            </div>
            <span class="text-xs text-right text-blue-400 tabular-nums">
              {{ s.us_pct > 0 ? s.us_pct + '%' : (s.has_revenue_data ? '0%' : '—') }}
            </span>
            <span class="text-xs text-right text-purple-400 tabular-nums">
              {{ s.eu_pct > 0 ? s.eu_pct + '%' : (s.has_revenue_data ? '0%' : '—') }}
            </span>
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

    <p class="text-[10px] text-gray-700 mt-6 text-center">
      Revenue data from SEC EDGAR 10-K/10-Q filings · {{ data?.results?.filter(r => r.has_revenue_data).length ?? 0 }} of {{ data?.results?.length ?? 0 }} shown stocks have EDGAR data
    </p>
  </main>
</template>

<script setup lang="ts">
const API = useRuntimeConfig().public.apiBase

const PAGE_SIZE = 50

const PRESETS = [
  { key: 'noChinaExposure',   filters: { china_max: 0 } },
  { key: 'lowChina',          filters: { china_max: 5 } },
  { key: 'highUs',            filters: { us_min: 70 } },
  { key: 'techSector',        filters: { sector: 'Information Technology' } },
  { key: 'largeCap',          filters: { market_cap_min: 100 } },
  { key: 'chinaExposed',      filters: { china_min: 20 } },
  { key: 'tariffProof',       filters: { china_max: 5, eu_max: 5 } },
  { key: 'chinaPlays',        filters: { china_min: 20 } },
  { key: 'europeExposed',     filters: { eu_min: 20 } },
  { key: 'indiaGrowth',       filters: { india_min: 10 } },
  { key: 'domesticOnly',      filters: { us_min: 80 } },
]

const defaultFilters = () => ({
  china_max: null as number | null,
  china_min: null as number | null,
  us_min: null as number | null,
  us_max: null as number | null,
  eu_min: null as number | null,
  eu_max: null as number | null,
  japan_min: null as number | null,
  japan_max: null as number | null,
  india_min: null as number | null,
  india_max: null as number | null,
  em_min: null as number | null,
  em_max: null as number | null,
  sector: '',
  market_cap_min: null as number | null,
  country_code: '',
})

const filters = reactive(defaultFilters())
const sortBy = ref('market_cap')
const sortDir = ref<'asc' | 'desc'>('desc')
const offset = ref(0)
const activePresetKey = ref<string | null>(null)

watch([filters, sortBy, sortDir], () => { offset.value = 0 }, { deep: true })

const queryParams = computed(() => {
  const p: Record<string, string | number> = {
    sort_by: sortBy.value,
    sort_dir: sortDir.value,
    limit: PAGE_SIZE,
    offset: offset.value,
  }
  const f = filters
  if (f.china_max !== null)    p.china_max = f.china_max
  if (f.china_min !== null)    p.china_min = f.china_min
  if (f.us_min !== null)       p.us_min = f.us_min
  if (f.us_max !== null)       p.us_max = f.us_max
  if (f.eu_min !== null)       p.eu_min = f.eu_min
  if (f.eu_max !== null)       p.eu_max = f.eu_max
  if (f.japan_min !== null)    p.japan_min = f.japan_min
  if (f.japan_max !== null)    p.japan_max = f.japan_max
  if (f.india_min !== null)    p.india_min = f.india_min
  if (f.india_max !== null)    p.india_max = f.india_max
  if (f.em_min !== null)       p.em_min = f.em_min
  if (f.em_max !== null)       p.em_max = f.em_max
  if (f.sector)                p.sector = f.sector
  if (f.market_cap_min !== null) p.market_cap_min = f.market_cap_min
  if (f.country_code)          p.country_code = f.country_code
  return p
})

const exportParams = computed(() => {
  const p = { ...queryParams.value }
  delete p.limit
  delete p.offset
  return new URLSearchParams(Object.entries(p).map(([k, v]) => [k, String(v)])).toString()
})

const exportUrl = computed(() => `${API}/api/screener/export?${exportParams.value}`)
const today = new Date().toISOString().split('T')[0]

const { data, pending } = await useAsyncData(
  'screener',
  () => $fetch(`${API}/api/screener`, { params: queryParams.value }),
  { watch: [queryParams] }
)

const { data: sectorsData } = await useAsyncData(
  'screener-sectors',
  () => $fetch<string[]>(`${API}/api/screener/sectors`)
)
const sectors = computed(() => sectorsData.value ?? [])

function applyPreset(preset: { key: string; filters: Record<string, any> }) {
  activePresetKey.value = preset.key
  Object.assign(filters, defaultFilters())
  Object.assign(filters, preset.filters)
}

function resetFilters() {
  activePresetKey.value = null
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
  title: 'Stock Screener — Filter by China/US/EU Revenue Exposure | MetricsHour',
  meta: [
    { name: 'description', content: 'Screen S&P 500 stocks by geographic revenue exposure. Find stocks with low China exposure, high US revenue, EU exposure, or specific sector focus. Data from SEC EDGAR.' },
    { property: 'og:title', content: 'Stock Screener — MetricsHour' },
    { property: 'og:description', content: 'Filter 775+ stocks by China, US, EU, Japan, India revenue %, sector, and market cap.' },
    { property: 'og:image', content: 'https://cdn.metricshour.com/og/section/home.png' },
    { property: 'og:type', content: 'website' },
  ],
  link: [{ rel: 'canonical', href: 'https://metricshour.com/screener/' }]
})
</script>
