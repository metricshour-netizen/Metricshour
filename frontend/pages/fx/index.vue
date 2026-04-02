<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Forex Markets</h1>
      <p class="text-gray-500 text-sm mt-1">Major currency pairs — live rates updated every 15 minutes</p>
    </div>

    <div v-if="pending" class="space-y-2">
      <div v-for="i in 10" :key="i" class="h-16 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
    </div>

    <template v-else>
      <template v-for="group in GROUPS" :key="group.name">
        <div class="mb-10">
          <div class="flex items-center gap-3 mb-4">
            <span class="text-lg">{{ group.icon }}</span>
            <h2 class="text-sm font-extrabold text-white uppercase tracking-widest">{{ group.name }}</h2>
            <span class="text-[10px] text-gray-600 bg-[#1f2937] px-2 py-0.5 rounded-full">{{ group.items.length }}</span>
            <div class="flex-1 h-px bg-[#1f2937]"/>
          </div>

          <!-- Table header -->
          <div class="hidden sm:grid grid-cols-[2fr_1fr_1fr_1fr] gap-4 px-4 mb-2 text-[11px] text-gray-600 uppercase tracking-widest font-semibold">
            <span>Pair</span>
            <span class="text-right">Rate</span>
            <span class="text-right">24h Change</span>
            <span class="text-right">Open</span>
          </div>

          <div class="space-y-1.5">
            <NuxtLink
              v-for="pair in group.items"
              :key="pair.symbol"
              :to="`/fx/${pair.symbol.toLowerCase()}/`"
              class="grid grid-cols-[2fr_1fr_1fr] sm:grid-cols-[2fr_1fr_1fr_1fr] gap-4 items-center bg-[#111827] border border-[#1f2937] hover:border-emerald-500/50 rounded-xl px-4 py-3.5 transition-all hover:bg-[#0d1a14] group"
            >
              <!-- Flags + name -->
              <div class="flex items-center gap-3">
                <span class="text-xl shrink-0 tabular-nums font-mono">{{ pair.flags }}</span>
                <div>
                  <div class="text-sm font-bold text-white">{{ pair.symbol }}</div>
                  <div class="text-[11px] text-gray-600">{{ pair.name }}</div>
                </div>
              </div>

              <!-- Rate -->
              <div class="text-right">
                <div class="text-sm font-bold text-white tabular-nums">
                  {{ apiMap[pair.symbol]?.price?.close != null ? fmtRate(pair.symbol, apiMap[pair.symbol].price.close) : '—' }}
                </div>
                <div class="text-[10px] text-gray-700 sm:hidden">Rate</div>
              </div>

              <!-- 24h Change -->
              <div class="text-right">
                <template v-if="apiMap[pair.symbol]?.price?.change_pct != null">
                  <span
                    class="text-sm font-bold tabular-nums"
                    :class="apiMap[pair.symbol].price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'"
                  >{{ apiMap[pair.symbol].price.change_pct >= 0 ? '+' : '' }}{{ apiMap[pair.symbol].price.change_pct.toFixed(3) }}%</span>
                </template>
                <span v-else class="text-sm text-gray-700">—</span>
              </div>

              <!-- Open (desktop) -->
              <div class="hidden sm:block text-right text-sm text-gray-500 tabular-nums">
                {{ apiMap[pair.symbol]?.price?.open != null ? fmtRate(pair.symbol, apiMap[pair.symbol].price.open) : '—' }}
              </div>
            </NuxtLink>
          </div>
        </div>
      </template>

      <p class="text-xs text-gray-700 mt-4">Source: Open Exchange Rates · Rates update every 15 minutes on weekdays</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const { r2ListFetch } = useR2Fetch()

const { data: fxData, pending } = useAsyncData('fx',
  () => r2ListFetch<any>('snapshots/lists/assets.json', '/api/assets?type=fx')
    .then((list: any[]) => list.filter(a => a.asset_type === 'fx'))
    .catch(() => []),
)

const apiMap = computed(() => {
  const m: Record<string, any> = {}
  for (const f of (fxData.value ?? [])) m[f.symbol] = f
  return m
})

const GROUPS = [
  {
    name: 'Majors', icon: '💱',
    items: [
      { symbol: 'EURUSD', name: 'Euro / US Dollar',          flags: '🇪🇺🇺🇸', decimals: 4 },
      { symbol: 'GBPUSD', name: 'British Pound / USD',       flags: '🇬🇧🇺🇸', decimals: 4 },
      { symbol: 'USDJPY', name: 'US Dollar / Japanese Yen',  flags: '🇺🇸🇯🇵', decimals: 2 },
      { symbol: 'USDCHF', name: 'US Dollar / Swiss Franc',   flags: '🇺🇸🇨🇭', decimals: 4 },
      { symbol: 'AUDUSD', name: 'Australian Dollar / USD',   flags: '🇦🇺🇺🇸', decimals: 4 },
      { symbol: 'USDCAD', name: 'US Dollar / Canadian Dollar',flags: '🇺🇸🇨🇦', decimals: 4 },
    ],
  },
  {
    name: 'Emerging Markets', icon: '🌏',
    items: [
      { symbol: 'USDCNY', name: 'US Dollar / Chinese Yuan',    flags: '🇺🇸🇨🇳', decimals: 4 },
      { symbol: 'USDMXN', name: 'US Dollar / Mexican Peso',   flags: '🇺🇸🇲🇽', decimals: 4 },
      { symbol: 'USDBRL', name: 'US Dollar / Brazilian Real',  flags: '🇺🇸🇧🇷', decimals: 4 },
      { symbol: 'USDINR', name: 'US Dollar / Indian Rupee',    flags: '🇺🇸🇮🇳', decimals: 2 },
    ],
  },
]

// Pairs that quote in the USD (e.g. EURUSD = how many dollars per euro)
const USD_QUOTE = new Set(['EURUSD', 'GBPUSD', 'AUDUSD'])

function fmtRate(symbol: string, v: number): string {
  // Find decimal precision from GROUPS
  for (const g of GROUPS) {
    const item = g.items.find(i => i.symbol === symbol)
    if (item) return v.toFixed(item.decimals)
  }
  return v.toFixed(4)
}

useSeoMeta({
  title: 'Forex Rates: EUR/USD, GBP/USD & Major Currency Pairs — MetricsHour',
  description: 'Live forex exchange rates for EUR/USD, GBP/USD, USD/JPY, USD/CNY and major currency pairs. Updated every 15 minutes on weekdays.',
  ogTitle: 'Forex Rates: EUR/USD, GBP/USD & Currency Pairs — MetricsHour',
  ogDescription: 'Live forex exchange rates for major and emerging market currency pairs. Updated every 15 minutes.',
  ogUrl: 'https://metricshour.com/fx/',
  ogType: 'website',
  ogImage: 'https://cdn.metricshour.com/og/section/fx.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/fx/' }],
})
</script>
