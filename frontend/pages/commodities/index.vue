<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white">Commodities</h1>
      <p class="text-gray-500 text-sm mt-1">
        Energy, metals & agriculture · 20 instruments · Real-time prices for Pro subscribers
      </p>
    </div>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>

    <template v-else>
      <div v-for="group in groups" :key="group.name" class="mb-10">
        <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">{{ group.name }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          <div
            v-for="c in group.items"
            :key="c.symbol"
            class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg p-4 transition-colors"
          >
            <div class="text-xl mb-2">{{ c.icon }}</div>
            <div class="text-sm font-medium text-white mb-0.5">
              <!-- Show real name from API if available, fallback to static -->
              {{ apiMap[c.symbol]?.name ?? c.name }}
            </div>
            <div class="text-xs text-gray-600 mb-2">{{ c.symbol }}</div>
            <div v-if="apiMap[c.symbol]?.price" class="text-sm font-bold text-white tabular-nums">
              ${{ apiMap[c.symbol].price.close.toFixed(2) }}
            </div>
            <div v-else class="text-xs text-gray-700">——</div>
          </div>
        </div>
      </div>

      <p v-if="!hasPrices" class="text-xs text-yellow-400 mb-2">
        Prices coming soon — available once Marketstack feed is connected.
      </p>
      <p class="text-xs text-gray-600">Data: Marketstack · CoinGecko · exchangerate.host</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()

const { data: commodities, pending } = await useAsyncData('commodities',
  () => get<any[]>('/api/assets?type=commodity').catch(() => []),
)

// Map symbol → asset (with price when available)
const apiMap = computed(() => {
  const m: Record<string, any> = {}
  for (const c of (commodities.value ?? [])) {
    m[c.symbol] = c
  }
  return m
})

const hasPrices = computed(() =>
  Object.values(apiMap.value).some((c: any) => c?.price),
)

// Static display groups with icons (symbol must match seeded symbols)
const groups = [
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
      { symbol: 'ZW', name: 'Wheat',    icon: '🌾' },
      { symbol: 'ZC', name: 'Corn',     icon: '🌽' },
      { symbol: 'ZS', name: 'Soybeans', icon: '🟤' },
      { symbol: 'KC', name: 'Coffee',   icon: '☕' },
      { symbol: 'SB', name: 'Sugar',    icon: '🍬' },
      { symbol: 'CT', name: 'Cotton',   icon: '🌿' },
      { symbol: 'CC', name: 'Cocoa',    icon: '🍫' },
    ],
  },
]

useSeoMeta({
  title: 'Commodities — MetricsHour',
  description: 'Real-time commodity prices: crude oil, gold, silver, copper, wheat, and 20+ instruments. See how commodity moves ripple through global economies and trade flows.',
})
</script>
