<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">ETFs</h1>
      <p class="text-gray-500 text-sm mt-1">Exchange-traded funds — broad market, sector, international, bonds & commodities</p>
    </div>

    <!-- Search -->
    <div class="relative mb-6">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search — SPY, QQQ, GLD, TLT, EEM..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-sky-500 transition-colors"
      />
      <button v-if="search" @click="search = ''" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 p-1.5">✕</button>
    </div>

    <div v-if="pending" class="space-y-2">
      <div v-for="i in 8" :key="i" class="h-16 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
    </div>

    <template v-else>
      <p v-if="search" class="text-xs text-gray-600 mb-4">{{ matchCount }} result{{ matchCount !== 1 ? 's' : '' }} for "{{ search }}"</p>

      <template v-for="group in filteredGroups" :key="group.name">
        <div v-if="group.items.length" class="mb-10">
          <div class="flex items-center gap-3 mb-4">
            <span class="text-lg">{{ group.icon }}</span>
            <h2 class="text-sm font-extrabold text-white uppercase tracking-widest">{{ group.name }}</h2>
            <span class="text-[10px] text-gray-600 bg-[#1f2937] px-2 py-0.5 rounded-full">{{ group.items.length }}</span>
            <div class="flex-1 h-px bg-[#1f2937]"/>
          </div>

          <!-- Table header -->
          <div class="hidden sm:grid grid-cols-[2fr_1fr_1fr_1fr] gap-4 px-4 mb-2 text-[11px] text-gray-600 uppercase tracking-widest font-semibold">
            <span>Fund</span>
            <span class="text-right">Price</span>
            <span class="text-right">24h Change</span>
            <span class="text-right">AUM</span>
          </div>

          <div class="space-y-1.5">
            <NuxtLink
              v-for="etf in group.items"
              :key="etf.symbol"
              :to="`/etfs/${etf.symbol.toLowerCase()}/`"
              class="grid grid-cols-[2fr_1fr_1fr] sm:grid-cols-[2fr_1fr_1fr_1fr] gap-4 items-center bg-[#111827] border border-[#1f2937] hover:border-sky-500/50 rounded-xl px-4 py-3.5 transition-all hover:bg-[#131d2e] group"
            >
              <!-- Name + symbol -->
              <div class="flex items-center gap-3">
                <span class="text-xl shrink-0">{{ etf.icon }}</span>
                <div>
                  <div class="text-sm font-bold text-white group-hover:text-sky-300 transition-colors">{{ apiMap[etf.symbol]?.name ?? etf.name }}</div>
                  <div class="text-[11px] text-gray-600 font-mono">{{ etf.symbol }}</div>
                </div>
              </div>

              <!-- Price -->
              <div class="text-right">
                <div class="text-sm font-bold text-white tabular-nums">
                  {{ apiMap[etf.symbol]?.price?.close != null ? fmtPrice(apiMap[etf.symbol].price.close) : '—' }}
                </div>
                <div class="text-[10px] text-gray-700 sm:hidden">Price</div>
              </div>

              <!-- 24h Change -->
              <div class="text-right">
                <template v-if="apiMap[etf.symbol]?.price?.change_pct != null">
                  <span
                    class="text-sm font-bold tabular-nums"
                    :class="apiMap[etf.symbol].price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'"
                  >{{ apiMap[etf.symbol].price.change_pct >= 0 ? '+' : '' }}{{ apiMap[etf.symbol].price.change_pct.toFixed(2) }}%</span>
                </template>
                <span v-else class="text-sm text-gray-700">—</span>
              </div>

              <!-- AUM (desktop) -->
              <div class="hidden sm:block text-right text-sm text-gray-400 tabular-nums">
                {{ apiMap[etf.symbol]?.market_cap_usd ? fmtCap(apiMap[etf.symbol].market_cap_usd) : '—' }}
              </div>
            </NuxtLink>
          </div>
        </div>
      </template>

      <div v-if="matchCount === 0 && search" class="text-center py-16 text-gray-600 text-sm">
        No ETFs match "{{ search }}"
      </div>

      <p class="text-xs text-gray-700 mt-4">Source: NYSE · NASDAQ · Prices update every 15 minutes during market hours</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const { r2ListFetch } = useR2Fetch()
const search = ref('')

const { data: etfs, pending } = useAsyncData('etfs',
  () => r2ListFetch<any>('snapshots/lists/assets.json', '/api/assets?type=etf')
    .then((list: any[]) => list.filter(a => a.asset_type === 'etf'))
    .catch(() => []),
)

const apiMap = computed(() => {
  const m: Record<string, any> = {}
  for (const e of (etfs.value ?? [])) m[e.symbol] = e
  return m
})

const ALL_GROUPS = [
  {
    name: 'US Broad Market', icon: '🇺🇸',
    items: [
      { symbol: 'SPY', name: 'SPDR S&P 500 ETF',            icon: '📊' },
      { symbol: 'VOO', name: 'Vanguard S&P 500 ETF',         icon: '📊' },
      { symbol: 'VTI', name: 'Vanguard Total Stock Market',  icon: '📊' },
      { symbol: 'QQQ', name: 'Invesco QQQ (Nasdaq-100)',     icon: '💻' },
      { symbol: 'IWM', name: 'iShares Russell 2000',         icon: '📈' },
    ],
  },
  {
    name: 'Sector', icon: '🏭',
    items: [
      { symbol: 'XLK', name: 'Technology SPDR',    icon: '💻' },
      { symbol: 'XLF', name: 'Financials SPDR',    icon: '🏦' },
      { symbol: 'XLV', name: 'Health Care SPDR',   icon: '🏥' },
      { symbol: 'XLE', name: 'Energy SPDR',         icon: '⚡' },
      { symbol: 'XLI', name: 'Industrials SPDR',   icon: '🏗️' },
    ],
  },
  {
    name: 'International', icon: '🌍',
    items: [
      { symbol: 'EFA', name: 'iShares MSCI EAFE',             icon: '🌐' },
      { symbol: 'VEA', name: 'Vanguard FTSE Developed',       icon: '🌐' },
      { symbol: 'EEM', name: 'iShares MSCI Emerging Markets', icon: '🌏' },
      { symbol: 'EWJ', name: 'iShares MSCI Japan',            icon: '🇯🇵' },
      { symbol: 'FXI', name: 'iShares China Large-Cap',       icon: '🇨🇳' },
    ],
  },
  {
    name: 'Fixed Income', icon: '📉',
    items: [
      { symbol: 'AGG', name: 'iShares Core US Aggregate Bond', icon: '💵' },
      { symbol: 'BND', name: 'Vanguard Total Bond Market',     icon: '💵' },
      { symbol: 'TLT', name: 'iShares 20+ Year Treasury',      icon: '🏛️' },
    ],
  },
  {
    name: 'Commodities', icon: '🛢️',
    items: [
      { symbol: 'GLD', name: 'SPDR Gold Shares',       icon: '🥇' },
      { symbol: 'SLV', name: 'iShares Silver Trust',   icon: '🥈' },
      { symbol: 'USO', name: 'United States Oil Fund', icon: '🛢️' },
    ],
  },
]

const filteredGroups = computed(() => {
  if (!search.value.trim()) return ALL_GROUPS
  const q = search.value.toLowerCase().trim()
  return ALL_GROUPS.map(group => ({
    ...group,
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
  if (v >= 1000) return '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  return '$' + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtCap(v: number): string {
  if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T'
  if (v >= 1e9)  return '$' + (v / 1e9).toFixed(1) + 'B'
  if (v >= 1e6)  return '$' + (v / 1e6).toFixed(0) + 'M'
  return '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

useSeoMeta({
  title: 'ETF Prices: SPY, QQQ, GLD & Top Funds — MetricsHour',
  description: 'Live ETF prices and 24h changes for S&P 500, Nasdaq, international, bond and commodity funds. Updated every 15 minutes.',
  ogTitle: 'ETF Prices: SPY, QQQ, GLD & Top Funds — MetricsHour',
  ogDescription: 'Live ETF prices and 24h changes for S&P 500, Nasdaq, international, bond and commodity funds.',
  ogUrl: 'https://metricshour.com/etfs/',
  ogType: 'website',
  ogImage: 'https://cdn.metricshour.com/og/section/etfs.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterImage: 'https://cdn.metricshour.com/og/section/etfs.png',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/etfs/' }],
})
</script>
