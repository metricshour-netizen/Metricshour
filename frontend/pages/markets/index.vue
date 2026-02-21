<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-white">Markets</h1>
      <p class="text-gray-500 text-sm mt-1">Crypto, stocks, and commodities — search across all markets</p>
    </div>

    <!-- Search -->
    <div class="relative mb-5">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search any asset — BTC, Apple, Gold, Palm Oil..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
        autofocus
      />
      <button v-if="search" @click="search = ''" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs">✕</button>
    </div>

    <!-- Tab filter -->
    <div class="flex gap-2 flex-wrap mb-6">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        class="px-4 py-1.5 rounded-lg text-xs font-semibold border transition-colors"
        :class="activeTab === tab.key
          ? 'bg-emerald-500 border-emerald-500 text-black'
          : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >
        {{ tab.label }}
        <span class="ml-1 opacity-60">{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="pending" class="text-gray-500 text-sm">Loading markets...</div>

    <template v-else>
      <p v-if="search" class="text-xs text-gray-600 mb-4">
        {{ filtered.length }} result{{ filtered.length !== 1 ? 's' : '' }} for "{{ search }}"
      </p>

      <!-- ── Crypto ─────────────────────────────────────────────────────── -->
      <template v-if="showSection('crypto') && cryptoFiltered.length">
        <h2 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-amber-400 inline-block"></span> Crypto
        </h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 mb-8">
          <NuxtLink
            v-for="a in cryptoFiltered"
            :key="a.symbol"
            :to="`/stocks/${a.symbol}`"
            class="bg-[#111827] border border-[#1f2937] hover:border-amber-500/50 rounded-lg p-4 transition-colors group"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="text-xl">{{ cryptoIcon(a.symbol) }}</span>
              <span class="text-[10px] font-bold text-amber-400/70 bg-amber-400/10 px-1.5 py-0.5 rounded">CRYPTO</span>
            </div>
            <div class="text-sm font-bold text-white group-hover:text-amber-300 transition-colors">{{ a.symbol }}</div>
            <div class="text-xs text-gray-500 truncate">{{ a.name }}</div>
            <div v-if="a.price" class="text-sm font-bold text-white mt-2 tabular-nums">${{ fmtPrice(a.price.close) }}</div>
            <div v-else class="text-xs text-gray-700 mt-2">——</div>
            <div v-if="a.market_cap_usd" class="text-[10px] text-gray-600 mt-0.5">Cap: {{ fmtCap(a.market_cap_usd) }}</div>
          </NuxtLink>
        </div>
      </template>

      <!-- ── Stocks ─────────────────────────────────────────────────────── -->
      <template v-if="showSection('stock') && stockFiltered.length">
        <h2 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span> Stocks
        </h2>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden mb-8">
          <div class="hidden sm:grid grid-cols-12 px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide">
            <span class="col-span-1">#</span>
            <span class="col-span-5">Company</span>
            <span class="col-span-3">Sector</span>
            <span class="col-span-2 text-right">Mkt Cap</span>
            <span class="col-span-1"></span>
          </div>
          <div class="divide-y divide-[#1f2937]">
            <NuxtLink
              v-for="(s, i) in stockFiltered"
              :key="s.symbol"
              :to="`/stocks/${s.symbol}`"
              class="block hover:bg-[#1a2235] transition-colors"
            >
              <!-- Mobile -->
              <div class="flex items-center justify-between px-4 py-3 sm:hidden">
                <div class="flex items-center gap-2.5 min-w-0">
                  <span v-if="s.country" class="text-base leading-none shrink-0">{{ s.country.flag }}</span>
                  <div class="min-w-0">
                    <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
                    <div class="text-xs text-gray-500 truncate max-w-[150px]">{{ s.name }}</div>
                  </div>
                </div>
                <div class="text-right shrink-0 ml-2">
                  <div class="text-sm text-white tabular-nums">{{ fmtCap(s.market_cap_usd) }}</div>
                  <div class="text-emerald-500 text-xs mt-0.5">→</div>
                </div>
              </div>
              <!-- Desktop -->
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
      </template>

      <!-- ── Commodities ────────────────────────────────────────────────── -->
      <template v-if="showSection('commodity') && commodityGroups.some(g => g.items.length)">
        <h2 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-blue-400 inline-block"></span> Commodities
        </h2>
        <div v-for="group in commodityGroups" :key="group.name" class="mb-6">
          <p v-if="group.items.length" class="text-[10px] text-gray-600 uppercase tracking-widest font-bold mb-2">{{ group.name }}</p>
          <div v-if="group.items.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            <div
              v-for="c in group.items"
              :key="c.symbol"
              class="bg-[#111827] border border-[#1f2937] hover:border-blue-500/40 rounded-lg p-4 transition-colors"
            >
              <div class="text-xl mb-2">{{ c.icon }}</div>
              <div class="text-sm font-medium text-white mb-0.5">{{ apiMap[c.symbol]?.name ?? c.name }}</div>
              <div class="text-xs text-gray-600 mb-2">{{ c.symbol }}</div>
              <div v-if="apiMap[c.symbol]?.price" class="text-sm font-bold text-white tabular-nums">
                ${{ fmtPrice(apiMap[c.symbol].price.close) }}
              </div>
              <div v-else class="text-xs text-gray-700">——</div>
            </div>
          </div>
        </div>
      </template>

      <!-- Empty state -->
      <div v-if="filtered.length === 0 && search" class="text-center py-20 text-gray-600 text-sm">
        No assets match "{{ search }}"
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()

const search = ref('')
const activeTab = ref('all')

const tabs = computed(() => [
  { key: 'all',       label: 'All',        count: allAssets.value.length },
  { key: 'crypto',    label: 'Crypto',     count: byType('crypto').length },
  { key: 'stock',     label: 'Stocks',     count: byType('stock').length },
  { key: 'commodity', label: 'Commodities',count: byType('commodity').length },
])

const { data: allAssets, pending } = await useAsyncData('markets-all',
  () => get<any[]>('/api/assets').catch(() => []),
)

function byType(type: string) {
  return (allAssets.value ?? []).filter((a: any) => a.asset_type === type)
}

function showSection(type: string) {
  return activeTab.value === 'all' || activeTab.value === type
}

// Single search across all assets
const filtered = computed(() => {
  if (!allAssets.value) return []
  let list = allAssets.value as any[]
  if (activeTab.value !== 'all') list = list.filter((a: any) => a.asset_type === activeTab.value)
  if (!search.value.trim()) return list
  const q = search.value.toLowerCase().trim()
  return list.filter((a: any) =>
    a.symbol?.toLowerCase().includes(q) ||
    a.name?.toLowerCase().includes(q) ||
    a.sector?.toLowerCase().includes(q)
  )
})

const cryptoFiltered = computed(() =>
  filtered.value.filter((a: any) => a.asset_type === 'crypto'),
)
const stockFiltered = computed(() =>
  filtered.value.filter((a: any) => a.asset_type === 'stock'),
)
const commodityFiltered = computed(() =>
  filtered.value.filter((a: any) => a.asset_type === 'commodity'),
)

// Build commodity groups respecting active search filter
const COMMODITY_GROUPS = [
  {
    name: 'Energy',
    items: [
      { symbol: 'WTI',      name: 'Crude Oil (WTI)',   icon: '🛢️' },
      { symbol: 'BRENT',    name: 'Crude Oil (Brent)', icon: '🛢️' },
      { symbol: 'NG',       name: 'Natural Gas',       icon: '🔥' },
      { symbol: 'GASOLINE', name: 'Gasoline',          icon: '⛽' },
      { symbol: 'COAL',     name: 'Coal',              icon: '⚫' },
    ],
  },
  {
    name: 'Metals',
    items: [
      { symbol: 'XAUUSD', name: 'Gold',      icon: '🥇' },
      { symbol: 'XAGUSD', name: 'Silver',    icon: '🥈' },
      { symbol: 'XPTUSD', name: 'Platinum',  icon: '⬜' },
      { symbol: 'HG',     name: 'Copper',    icon: '🟤' },
      { symbol: 'ALI',    name: 'Aluminum',  icon: '⬛' },
      { symbol: 'ZNC',    name: 'Zinc',      icon: '🔩' },
      { symbol: 'NI',     name: 'Nickel',    icon: '🔩' },
    ],
  },
  {
    name: 'Agriculture',
    items: [
      { symbol: 'ZW',   name: 'Wheat',     icon: '🌾' },
      { symbol: 'ZC',   name: 'Corn',      icon: '🌽' },
      { symbol: 'ZS',   name: 'Soybeans',  icon: '🟤' },
      { symbol: 'KC',   name: 'Coffee',    icon: '☕' },
      { symbol: 'SB',   name: 'Sugar',     icon: '🍬' },
      { symbol: 'CT',   name: 'Cotton',    icon: '🌿' },
      { symbol: 'CC',   name: 'Cocoa',     icon: '🍫' },
      { symbol: 'LE',   name: 'Live Cattle',icon: '🐄' },
      { symbol: 'PALM', name: 'Palm Oil',  icon: '🌴' },
    ],
  },
]

const apiMap = computed(() => {
  const m: Record<string, any> = {}
  for (const a of (allAssets.value ?? [])) m[a.symbol] = a
  return m
})

const commodityGroups = computed(() =>
  COMMODITY_GROUPS.map(group => ({
    name: group.name,
    items: group.items.filter(item =>
      commodityFiltered.value.some((a: any) => a.symbol === item.symbol)
    ),
  }))
)

// Icons for crypto
const CRYPTO_ICONS: Record<string, string> = {
  BTC: '₿', ETH: 'Ξ', BNB: '🟡', SOL: '◎', ADA: '₳',
  XRP: '✕', DOGE: '🐕', DOT: '●', AVAX: '🔺', LINK: '🔗',
}
function cryptoIcon(symbol: string) {
  return CRYPTO_ICONS[symbol] || '🪙'
}

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtPrice(v: number): string {
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1)    return v.toFixed(2)
  return v.toFixed(4)
}

useSeoMeta({
  title: 'Markets — MetricsHour',
  description: 'Search crypto, stocks, and commodities. Real-time prices and global market data.',
})
</script>
