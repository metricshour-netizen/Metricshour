<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Commodities</h1>
      <p class="text-gray-500 text-sm mt-1">Energy · Metals · Agriculture — 21 instruments tracked globally</p>
    </div>

    <!-- Search -->
    <div class="relative mb-6">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search — Gold, Oil, Palm Oil, Wheat, Copper..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
      />
      <button v-if="search" @click="search = ''" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 p-1.5">✕</button>
    </div>

    <div v-if="pending" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
      <div v-for="i in 10" :key="i" class="h-28 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
    </div>

    <template v-else>
      <p v-if="search" class="text-xs text-gray-600 mb-4">{{ matchCount }} result{{ matchCount !== 1 ? 's' : '' }} for "{{ search }}"</p>

      <template v-for="group in filteredGroups" :key="group.name">
        <div v-if="group.items.length" class="mb-10">
          <!-- Group header -->
          <div class="flex items-center gap-3 mb-4">
            <span class="text-lg">{{ group.icon }}</span>
            <h2 class="text-sm font-extrabold text-white uppercase tracking-widest">{{ group.name }}</h2>
            <span class="text-[10px] text-gray-600 bg-[#1f2937] px-2 py-0.5 rounded-full">{{ group.items.length }}</span>
            <div class="flex-1 h-px bg-[#1f2937]"/>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            <NuxtLink
              v-for="c in group.items"
              :key="c.symbol"
              :to="`/commodities/${c.symbol.toLowerCase()}`"
              class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500/60 rounded-xl p-4 transition-all hover:bg-[#131d2e] group"
            >
              <div class="flex items-start justify-between mb-3">
                <span class="text-2xl">{{ c.icon }}</span>
                <span class="text-[10px] text-gray-600 bg-[#1f2937] px-1.5 py-0.5 rounded font-mono">{{ c.symbol }}</span>
              </div>
              <div class="text-sm font-bold text-white mb-0.5 group-hover:text-emerald-300 transition-colors leading-tight">
                {{ apiMap[c.symbol]?.name ?? c.name }}
              </div>
              <div class="text-[10px] text-gray-600 mb-2">{{ group.name }}</div>
              <div class="mt-auto">
                <template v-if="apiMap[c.symbol]?.price?.close != null">
                  <div class="text-base font-extrabold text-white tabular-nums">${{ fmtPrice(apiMap[c.symbol].price.close) }}</div>
                  <div class="text-[10px] mt-0.5 flex items-center gap-1"
                    :class="apiMap[c.symbol].price.timestamp ? 'text-emerald-700' : 'text-gray-600'">
                    <span class="w-1 h-1 rounded-full inline-block"
                      :class="apiMap[c.symbol].price.timestamp ? 'bg-emerald-600' : 'bg-gray-600'"></span>
                    {{ fmtTs(apiMap[c.symbol].price.timestamp) }}
                  </div>
                </template>
                <div v-else class="text-base font-extrabold text-gray-700 tabular-nums">—</div>
              </div>
            </NuxtLink>
          </div>
        </div>
      </template>

      <div v-if="matchCount === 0 && search" class="text-center py-16 text-gray-600 text-sm">
        No commodities match "{{ search }}"
      </div>

      <p class="text-xs text-gray-700 mt-4">Data: Marketstack · CoinGecko · exchangerate.host</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()
const search = ref('')

const { data: commodities, pending } = useAsyncData('commodities',
  () => get<any[]>('/api/assets?type=commodity').catch(() => []),
)

const apiMap = computed(() => {
  const m: Record<string, any> = {}
  for (const c of (commodities.value ?? [])) m[c.symbol] = c
  return m
})

const ALL_GROUPS = [
  {
    name: 'Energy', icon: '⚡',
    items: [
      { symbol: 'WTI',      name: 'Crude Oil (WTI)',   icon: '🛢️' },
      { symbol: 'BRENT',    name: 'Crude Oil (Brent)', icon: '🛢️' },
      { symbol: 'NG',       name: 'Natural Gas',       icon: '🔥' },
      { symbol: 'GASOLINE', name: 'Gasoline',          icon: '⛽' },
      { symbol: 'COAL',     name: 'Coal',              icon: '⚫' },
    ],
  },
  {
    name: 'Metals', icon: '⚙️',
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
    name: 'Agriculture', icon: '🌾',
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
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1)    return v.toFixed(2)
  return v.toFixed(4)
}

function parseUTC(ts: string): Date {
  if (ts && !ts.endsWith('Z') && !ts.includes('+') && !/[+-]\d{2}:\d{2}$/.test(ts)) {
    return new Date(ts + 'Z')
  }
  return new Date(ts)
}

function fmtTs(iso: string | null | undefined): string {
  if (!iso) return 'No feed yet'
  const d = parseUTC(iso)
  const diff = Math.floor((Date.now() - d.getTime()) / 1000)
  if (diff < 60)   return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

useSeoMeta({
  title: 'Commodities: Oil, Gold, Wheat & 20+ Markets — MetricsHour',
  description: 'Real-time commodity prices: crude oil, gold, silver, copper, palm oil, wheat and 20+ instruments tracked globally.',
  ogTitle: 'Commodities: Oil, Gold, Wheat & 20+ Markets — MetricsHour',
  ogDescription: 'Real-time commodity prices: crude oil, gold, silver, copper, palm oil, wheat and 20+ instruments tracked globally.',
  ogUrl: 'https://metricshour.com/commodities/',
  ogType: 'website',
  ogImage: 'https://api.metricshour.com/og/section/commodities.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterTitle: 'Commodities: Oil, Gold, Wheat & 20+ Markets — MetricsHour',
  twitterDescription: 'Real-time commodity prices: crude oil, gold, silver, copper, palm oil, wheat and 20+ instruments tracked globally.',
  twitterImage: 'https://api.metricshour.com/og/section/commodities.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/commodities/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Commodities — MetricsHour',
      url: 'https://metricshour.com/commodities',
      description: 'Real-time commodity prices: crude oil, gold, silver, copper, wheat and 20+ instruments tracked globally.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
    }),
  }],
})
</script>
