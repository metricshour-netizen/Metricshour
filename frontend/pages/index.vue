<template>
  <!-- ── Market Ticker Strip ──────────────────────────────────────────────── -->
  <div v-if="tickerItems.length" class="w-full bg-[#060d14] border-b border-[#1a2332] overflow-hidden select-none" @mouseenter="tickerPaused = true" @mouseleave="tickerPaused = false">
    <div class="ticker-wrap">
      <div class="ticker-track" :class="{ paused: tickerPaused }">
        <span
          v-for="(item, i) in [...tickerItems, ...tickerItems]"
          :key="`tk-${i}`"
          class="inline-flex items-center gap-1.5 px-5 py-2 border-r border-[#1a2332] shrink-0"
        >
          <span class="text-[11px] font-mono font-bold" :class="item.typeColor">{{ item.symbol }}</span>
          <span class="text-[11px] text-white tabular-nums font-semibold">{{ item.priceStr }}</span>
          <span class="text-[10px] tabular-nums font-semibold" :class="item.dir >= 0 ? 'text-emerald-400' : 'text-red-400'">
            {{ item.dir >= 0 ? '▲' : '▼' }}{{ item.changePct }}
          </span>
        </span>
      </div>
    </div>
  </div>

  <main class="max-w-7xl mx-auto px-4 py-16">
    <!-- Hero -->
    <div class="text-center mb-16">
      <h1 class="text-3xl sm:text-4xl md:text-6xl font-bold text-white mb-4 leading-tight">
        Global financial intelligence.<br>
        <span class="text-emerald-400">One place.</span>
      </h1>
      <p class="text-gray-400 text-base sm:text-xl max-w-2xl mx-auto mb-10">
        Connect stock revenue, trade flows, and country macro data
        in seconds — not minutes across 4 websites.
      </p>

      <!-- Search bar -->
      <div class="relative max-w-xl mx-auto mb-10" ref="searchContainer">
        <div class="relative">
          <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm pointer-events-none">🔍</span>
          <input
            v-model="searchQuery"
            @input="onSearchInput"
            @keydown.escape="closeSearch"
            @keydown.down.prevent="moveFocus(1)"
            @keydown.up.prevent="moveFocus(-1)"
            @keydown.enter.prevent="selectFocused"
            @focus="searchQuery.length >= 2 && (searchOpen = true)"
            placeholder="Search countries, stocks, trade pairs..."
            class="w-full bg-[#111827] border border-[#1f2937] focus:border-emerald-500 text-white rounded-lg px-4 py-3.5 pl-9 text-sm focus:outline-none transition-colors"
            autocomplete="off"
            spellcheck="false"
          />
          <button
            v-if="searchQuery"
            @click="closeSearch"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 text-lg leading-none"
          >×</button>
        </div>

        <!-- Autocomplete dropdown -->
        <div
          v-if="searchOpen && (searchResults.countries.length || searchResults.assets.length)"
          class="absolute top-full left-0 right-0 mt-1 bg-[#0d1117] border border-[#1f2937] rounded-lg overflow-hidden z-50 text-left shadow-2xl"
        >
          <!-- Countries -->
          <template v-if="searchResults.countries.length">
            <div class="px-3 py-1.5 text-[10px] text-gray-600 uppercase tracking-widest font-bold border-b border-[#1f2937] bg-[#111827]">
              Countries
            </div>
            <NuxtLink
              v-for="(c, i) in searchResults.countries"
              :key="c.code"
              :to="`/countries/${c.code.toLowerCase()}`"
              @click="closeSearch"
              class="flex items-center gap-2.5 px-3 py-2.5 hover:bg-[#1f2937] transition-colors"
              :class="focusedIndex === i ? 'bg-[#1f2937]' : ''"
            >
              <span class="text-base">{{ c.flag }}</span>
              <span class="text-sm text-white flex-1">{{ c.name }}</span>
              <span class="text-xs text-gray-600 font-mono">{{ c.code }}</span>
            </NuxtLink>
          </template>

          <!-- Assets -->
          <template v-if="searchResults.assets.length">
            <div class="px-3 py-1.5 text-[10px] text-gray-600 uppercase tracking-widest font-bold border-b border-[#1f2937] bg-[#111827]" :class="searchResults.countries.length ? 'border-t' : ''">
              Stocks & Assets
            </div>
            <NuxtLink
              v-for="(a, i) in searchResults.assets"
              :key="a.symbol"
              :to="`/stocks/${a.symbol}`"
              @click="closeSearch"
              class="flex items-center gap-2.5 px-3 py-2.5 hover:bg-[#1f2937] transition-colors"
              :class="focusedIndex === (searchResults.countries.length + i) ? 'bg-[#1f2937]' : ''"
            >
              <span class="text-xs font-mono font-bold text-emerald-400 w-14 shrink-0">{{ a.symbol }}</span>
              <span class="text-sm text-gray-300 flex-1 truncate">{{ a.name }}</span>
              <span class="text-[10px] text-gray-600 capitalize shrink-0 bg-[#1f2937] px-1.5 py-0.5 rounded">
                {{ a.asset_type }}
              </span>
            </NuxtLink>
          </template>
        </div>

        <!-- No results -->
        <div
          v-else-if="searchOpen && searchQuery.length >= 2 && !searchLoading"
          class="absolute top-full left-0 right-0 mt-1 bg-[#0d1117] border border-[#1f2937] rounded-lg p-4 z-50 text-center"
        >
          <span class="text-sm text-gray-600">No results for "{{ searchQuery }}"</span>
        </div>
      </div>

      <div class="flex justify-center gap-3 flex-wrap">
        <NuxtLink to="/markets" class="bg-emerald-500 hover:bg-emerald-400 text-black font-bold px-5 py-3.5 rounded-lg transition-colors text-sm sm:text-base">
          Explore Markets →
        </NuxtLink>
        <NuxtLink to="/countries" class="border border-gray-600 hover:border-emerald-500 text-gray-300 hover:text-white px-5 py-3.5 rounded-lg transition-colors text-sm sm:text-base">
          Explore Countries
        </NuxtLink>
      </div>
    </div>

    <!-- What we connect -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-16">
      <div v-for="item in pillars" :key="item.title"
           class="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
        <div class="text-2xl mb-3">{{ item.icon }}</div>
        <h3 class="font-bold text-white mb-1">{{ item.title }}</h3>
        <p class="text-gray-500 text-sm">{{ item.desc }}</p>
      </div>
    </div>

    <!-- Live data: Top Stocks + G20 Countries side by side -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-10 mb-16">

      <!-- Top Stocks by Market Cap -->
      <div>
        <div class="flex items-center justify-between mb-5">
          <h2 class="text-lg font-bold text-white">Top Stocks</h2>
          <NuxtLink to="/stocks" class="text-xs text-emerald-500 hover:text-emerald-400 transition-colors">View all →</NuxtLink>
        </div>
        <div v-if="stocksPending" class="space-y-2">
          <div v-for="i in 5" :key="i" class="h-[60px] bg-[#111827] rounded-lg animate-pulse"/>
        </div>
        <div v-else-if="stocksError" class="text-red-400 text-sm">Failed to load stocks</div>
        <div v-else class="space-y-2">
          <NuxtLink
            v-for="s in topStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol}`"
            class="flex items-center gap-3 bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg px-4 py-3 transition-colors"
          >
            <span class="text-xl leading-none">{{ s.country?.flag || '🏢' }}</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 mb-0.5">
                <span class="text-sm font-mono font-bold text-emerald-400">{{ s.symbol }}</span>
                <span class="text-xs text-gray-500 truncate">{{ s.name }}</span>
              </div>
              <span class="text-[11px] text-gray-600">{{ s.sector }}</span>
            </div>
            <div class="text-right shrink-0">
              <div class="text-sm font-semibold text-white tabular-nums">{{ fmtCap(s.market_cap_usd) }}</div>
              <div class="text-[11px] text-gray-600">market cap</div>
            </div>
          </NuxtLink>
        </div>
      </div>

      <!-- G20 Countries -->
      <div>
        <div class="flex items-center justify-between mb-5">
          <h2 class="text-lg font-bold text-white">G20 Countries</h2>
          <NuxtLink to="/countries" class="text-xs text-emerald-500 hover:text-emerald-400 transition-colors">View all 196 →</NuxtLink>
        </div>
        <div v-if="countriesPending" class="text-gray-500 text-sm">Loading...</div>
        <div v-else-if="countriesError" class="text-red-400 text-sm">Failed to load countries</div>
        <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          <NuxtLink
            v-for="c in countries"
            :key="c.code"
            :to="`/countries/${c.code.toLowerCase()}`"
            class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg p-3 transition-colors"
          >
            <div class="text-xl mb-1">{{ c.flag }}</div>
            <div class="text-xs font-medium text-white leading-tight">{{ c.name }}</div>
            <div class="text-[10px] text-gray-600 mt-0.5">{{ c.code }}</div>
          </NuxtLink>
        </div>
      </div>
    </div>

    <!-- Sample trade pairs -->
    <div class="mb-16">
      <div class="flex items-center justify-between mb-5">
        <h2 class="text-lg font-bold text-white">Major Trade Relationships</h2>
        <NuxtLink to="/trade" class="text-xs text-emerald-500 hover:text-emerald-400 transition-colors">View all →</NuxtLink>
      </div>
      <div v-if="tradesPending" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div v-for="i in 6" :key="i" class="h-20 bg-[#111827] rounded-lg animate-pulse"/>
      </div>
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <NuxtLink
          v-for="t in topTrades"
          :key="`${t.exporter?.code}-${t.importer?.code}`"
          :to="`/trade/${t.exporter?.code}-${t.importer?.code}`"
          class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg p-4 transition-colors"
        >
          <div class="flex items-center gap-2 mb-2">
            <span class="text-lg">{{ t.exporter?.flag }}</span>
            <span class="text-xs text-gray-500">↔</span>
            <span class="text-lg">{{ t.importer?.flag }}</span>
            <span class="text-xs font-medium text-white ml-1 truncate">
              {{ t.exporter?.name }} – {{ t.importer?.name }}
            </span>
          </div>
          <div class="flex gap-4">
            <div>
              <div class="text-[10px] text-gray-600">Total Trade</div>
              <div class="text-sm font-semibold text-white">{{ fmtUsd(t.trade_value_usd) }}</div>
            </div>
            <div>
              <div class="text-[10px] text-gray-600">Balance</div>
              <div class="text-sm font-semibold" :class="(t.balance_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ fmtUsd(t.balance_usd) }}
              </div>
            </div>
          </div>
        </NuxtLink>
      </div>
    </div>

    <!-- Data sources footer note -->
    <p class="text-center text-xs text-gray-700">
      Data: World Bank · SEC EDGAR · UN Comtrade · REST Countries · IMF · CoinGecko
    </p>
  </main>
</template>

<script setup lang="ts">
const pillars = [
  { icon: '📈', title: 'Stock Revenue Exposure', desc: 'See which countries each stock earns from — straight from SEC filings.' },
  { icon: '🌍', title: 'Country Macro', desc: 'GDP, inflation, debt, trade balance, and 80+ indicators per country.' },
  { icon: '⚖️', title: 'Bilateral Trade', desc: 'US-China, EU-Russia — every major trade relationship with top products.' },
  { icon: '🛢️', title: 'Commodities', desc: 'Oil, gold, metals — see how commodity moves ripple through economies.' },
]

const { get } = useApi()

// G20 countries
const { data: countries, pending: countriesPending, error: countriesError } = await useAsyncData(
  'g20',
  () => get<any[]>('/api/countries', { is_g20: 'true' }),
)

// Top stocks by market cap
const { data: allStocks, pending: stocksPending, error: stocksError } = await useAsyncData(
  'top-stocks',
  () => get<any[]>('/api/assets', { type: 'stock' }),
)

// Top trade pairs
const { data: trades, pending: tradesPending } = await useAsyncData(
  'top-trades',
  () => get<any[]>('/api/trade'),
)

const topStocks = computed(() => (allStocks.value ?? []).slice(0, 5))
const topTrades = computed(() => (trades.value ?? []).slice(0, 6))

// ─── Search ───────────────────────────────────────────────────────────────────

const searchQuery = ref('')
const searchOpen = ref(false)
const searchLoading = ref(false)
const focusedIndex = ref(-1)
const searchResults = ref<{ countries: any[], assets: any[] }>({ countries: [], assets: [] })
let searchTimeout: ReturnType<typeof setTimeout> | null = null

function onSearchInput() {
  if (searchTimeout) clearTimeout(searchTimeout)
  const q = searchQuery.value.trim()
  focusedIndex.value = -1
  if (q.length < 2) {
    searchResults.value = { countries: [], assets: [] }
    searchOpen.value = false
    return
  }
  searchTimeout = setTimeout(async () => {
    searchLoading.value = true
    try {
      const res = await get<any>('/api/search', { q })
      searchResults.value = res
      searchOpen.value = true
    } catch {
      // silent fail
    } finally {
      searchLoading.value = false
    }
  }, 280)
}

function closeSearch() {
  searchOpen.value = false
  searchQuery.value = ''
  searchResults.value = { countries: [], assets: [] }
  focusedIndex.value = -1
}

const allResults = computed(() => [
  ...searchResults.value.countries.map((c: any) => ({ type: 'country', ...c })),
  ...searchResults.value.assets.map((a: any) => ({ type: 'asset', ...a })),
])

function moveFocus(dir: 1 | -1) {
  const max = allResults.value.length - 1
  if (max < 0) return
  focusedIndex.value = Math.max(-1, Math.min(max, focusedIndex.value + dir))
}

const router = useRouter()
function selectFocused() {
  if (focusedIndex.value < 0) return
  const item = allResults.value[focusedIndex.value]
  if (!item) return
  if (item.type === 'country') {
    router.push(`/countries/${item.code.toLowerCase()}`)
  } else {
    router.push(`/stocks/${item.symbol}`)
  }
  closeSearch()
}

// Close search on click outside
if (import.meta.client) {
  document.addEventListener('click', (e: MouseEvent) => {
    const container = document.querySelector('[data-search-container]')
    if (container && !container.contains(e.target as Node)) {
      searchOpen.value = false
    }
  })
}

// ─── Formatting ───────────────────────────────────────────────────────────────

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(0)}M`
  return `${sign}$${abs.toLocaleString()}`
}

// ─── Market Ticker ────────────────────────────────────────────────────────────

const TICKER_SYMBOLS = ['BTC', 'ETH', 'SOL', 'AAPL', 'NVDA', 'TSLA', 'MSFT', 'SPY', 'QQQ', 'XAUUSD', 'WTI', 'EURUSD', 'USDJPY', 'BNB', 'XAGUSD']
const tickerPaused = ref(false)

const { data: tickerRaw } = await useAsyncData('ticker',
  () => get<any[]>('/api/assets').catch(() => []),
  { server: false },
)

function tickerTypeColor(type: string): string {
  const map: Record<string, string> = {
    crypto: 'text-amber-400', stock: 'text-emerald-400', etf: 'text-sky-400',
    index: 'text-purple-400', commodity: 'text-blue-400', fx: 'text-teal-400', bond: 'text-rose-400',
  }
  return map[type] ?? 'text-gray-400'
}

function fmtTickerPrice(v: number): string {
  if (v >= 10000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  if (v >= 1)     return `$${v.toFixed(2)}`
  return `$${v.toFixed(4)}`
}

const tickerItems = computed(() => {
  const assets = tickerRaw.value ?? []
  return TICKER_SYMBOLS
    .map(sym => (assets as any[]).find(a => a.symbol === sym))
    .filter(Boolean)
    .map((a: any) => {
      const p = a.price
      if (!p?.close) return null
      const open = p.open || p.close
      const dir = p.close >= open ? 1 : -1
      const pct = open > 0 ? Math.abs((p.close - open) / open * 100) : 0
      return { symbol: a.symbol, priceStr: fmtTickerPrice(p.close), changePct: pct.toFixed(2) + '%', dir, typeColor: tickerTypeColor(a.asset_type) }
    })
    .filter(Boolean) as { symbol: string; priceStr: string; changePct: string; dir: number; typeColor: string }[]
})

useSeoMeta({
  title: 'MetricsHour — Global Financial Intelligence',
  description: 'Connect stock geographic revenue, bilateral trade flows, and country macro data. 196 countries, 5,000+ stocks, 38,000+ trade pairs. Free forever.',
})
</script>

<style scoped>
.ticker-wrap {
  overflow: hidden;
  width: 100%;
}
.ticker-track {
  display: inline-flex;
  animation: ticker-scroll 45s linear infinite;
}
.ticker-track.paused {
  animation-play-state: paused;
}
@keyframes ticker-scroll {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}
</style>
