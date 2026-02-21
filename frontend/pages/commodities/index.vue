<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-white">Commodities</h1>
      <p class="text-gray-500 text-sm mt-1">Energy, metals & agriculture · 21 instruments</p>
    </div>

    <!-- Search -->
    <div class="relative mb-6">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search commodities — Gold, Oil, Palm Oil, Wheat..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
      />
      <button v-if="search" @click="search = ''" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs">✕</button>
    </div>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>

    <template v-else>
      <p v-if="search" class="text-xs text-gray-600 mb-4">{{ matchCount }} result{{ matchCount !== 1 ? 's' : '' }} for "{{ search }}"</p>

      <template v-for="group in filteredGroups" :key="group.name">
        <div v-if="group.items.length" class="mb-10">
          <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">{{ group.name }}</h2>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            <div
              v-for="c in group.items"
              :key="c.symbol"
              class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg p-4 transition-colors"
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

      <div v-if="matchCount === 0 && search" class="text-center py-16 text-gray-600 text-sm">
        No commodities match "{{ search }}"
      </div>

      <p class="text-xs text-gray-600 mt-2">Data: Marketstack · CoinGecko · exchangerate.host</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()
const search = ref('')

const { data: commodities, pending } = await useAsyncData('commodities',
  () => get<any[]>('/api/assets?type=commodity').catch(() => []),
)

const apiMap = computed(() => {
  const m: Record<string, any> = {}
  for (const c of (commodities.value ?? [])) m[c.symbol] = c
  return m
})

const ALL_GROUPS = [
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
      { symbol: 'ZW',   name: 'Wheat',      icon: '🌾' },
      { symbol: 'ZC',   name: 'Corn',       icon: '🌽' },
      { symbol: 'ZS',   name: 'Soybeans',   icon: '🟤' },
      { symbol: 'KC',   name: 'Coffee',     icon: '☕' },
      { symbol: 'SB',   name: 'Sugar',      icon: '🍬' },
      { symbol: 'CT',   name: 'Cotton',     icon: '🌿' },
      { symbol: 'CC',   name: 'Cocoa',      icon: '🍫' },
      { symbol: 'LE',   name: 'Live Cattle',icon: '🐄' },
      { symbol: 'PALM', name: 'Palm Oil',   icon: '🌴' },
    ],
  },
]

const filteredGroups = computed(() => {
  if (!search.value.trim()) return ALL_GROUPS
  const q = search.value.toLowerCase().trim()
  return ALL_GROUPS.map(group => ({
    name: group.name,
    items: group.items.filter(item =>
      item.name.toLowerCase().includes(q) ||
      item.symbol.toLowerCase().includes(q) ||
      group.name.toLowerCase().includes(q)
    ),
  }))
})

const matchCount = computed(() =>
  filteredGroups.value.reduce((sum, g) => sum + g.items.length, 0)
)

function fmtPrice(v: number): string {
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1)    return v.toFixed(2)
  return v.toFixed(4)
}

useSeoMeta({
  title: 'Commodities — MetricsHour',
  description: 'Real-time commodity prices: crude oil, gold, silver, copper, palm oil, wheat and 20+ instruments.',
})
</script>
