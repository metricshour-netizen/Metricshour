<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Global Indices</h1>
      <p class="text-gray-500 text-sm mt-1">US · Europe · Asia · Global — 18 major indices tracked live</p>
    </div>

    <div class="relative mb-6">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search — S&amp;P 500, DAX, Nikkei, FTSE..."
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
          <div class="flex items-center gap-3 mb-4">
            <span class="text-lg">{{ group.icon }}</span>
            <h2 class="text-sm font-extrabold text-white uppercase tracking-widest">{{ group.name }}</h2>
            <span class="text-[10px] text-gray-600 bg-[#1f2937] px-2 py-0.5 rounded-full">{{ group.items.length }}</span>
            <div class="flex-1 h-px bg-[#1f2937]"/>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            <NuxtLink
              v-for="idx in group.items"
              :key="idx.symbol"
              :to="`/indices/${idx.symbol.toLowerCase()}`"
              class="bg-[#111827] border border-[#1f2937] hover:border-purple-500/60 rounded-xl p-4 transition-all hover:bg-[#131d2e] group"
            >
              <div class="flex items-start justify-between mb-3">
                <span class="text-2xl">{{ group.icon }}</span>
                <span class="text-[10px] text-gray-600 bg-[#1f2937] px-1.5 py-0.5 rounded font-mono">{{ idx.symbol }}</span>
              </div>
              <div class="text-sm font-bold text-white mb-0.5 group-hover:text-purple-300 transition-colors leading-tight">
                {{ apiMap[idx.symbol]?.name ?? idx.name }}
              </div>
              <div class="text-[10px] text-gray-600 mb-2">{{ idx.exchange }}</div>
              <div class="mt-auto">
                <template v-if="apiMap[idx.symbol]?.price?.close != null">
                  <div class="text-base font-extrabold text-white tabular-nums">{{ fmtPrice(apiMap[idx.symbol].price.close) }}</div>
                  <div v-if="apiMap[idx.symbol].price.change_pct != null" class="text-[10px] mt-0.5 tabular-nums"
                    :class="apiMap[idx.symbol].price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                    {{ apiMap[idx.symbol].price.change_pct >= 0 ? '▲' : '▼' }}
                    {{ Math.abs(apiMap[idx.symbol].price.change_pct).toFixed(2) }}%
                  </div>
                </template>
                <div v-else class="text-base font-extrabold text-gray-700 tabular-nums">—</div>
              </div>
            </NuxtLink>
          </div>
        </div>
      </template>

      <div v-if="matchCount === 0 && search" class="text-center py-16 text-gray-600 text-sm">
        No indices match "{{ search }}"
      </div>

      <p class="text-xs text-gray-700 mt-4">Data: Marketstack · CBOE · Exchange feeds</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const { r2ListFetch } = useR2Fetch()
const search = ref('')

const { data: indices, pending } = useAsyncData('indices',
  () => r2ListFetch<any>('snapshots/lists/assets.json', '/api/assets?type=index')
    .then((list: any[]) => list.filter((a: any) => a.asset_type === 'index'))
    .catch(() => []),
)

const apiMap = computed(() => {
  const m: Record<string, any> = {}
  for (const i of (indices.value ?? [])) m[i.symbol] = i
  return m
})

const ALL_GROUPS = [
  {
    name: 'United States', icon: '🇺🇸', region: 'US',
    items: [
      { symbol: 'SPX',  name: 'S&P 500',                     exchange: 'NYSE'   },
      { symbol: 'DJI',  name: 'Dow Jones Industrial Average', exchange: 'NYSE'   },
      { symbol: 'NDX',  name: 'Nasdaq 100',                   exchange: 'NASDAQ' },
      { symbol: 'RUT',  name: 'Russell 2000',                 exchange: 'NYSE'   },
      { symbol: 'VIX',  name: 'CBOE Volatility Index',        exchange: 'CBOE'   },
    ],
  },
  {
    name: 'Europe', icon: '🇪🇺', region: 'Europe',
    items: [
      { symbol: 'UKX',  name: 'FTSE 100',          exchange: 'LSE'      },
      { symbol: 'DAX',  name: 'DAX 40',             exchange: 'XETRA'   },
      { symbol: 'CAC',  name: 'CAC 40',             exchange: 'EURONEXT' },
      { symbol: 'IBEX', name: 'IBEX 35',            exchange: 'BME'      },
      { symbol: 'SMI',  name: 'Swiss Market Index', exchange: 'SIX'      },
    ],
  },
  {
    name: 'Asia Pacific', icon: '🌏', region: 'Asia',
    items: [
      { symbol: 'NKY',    name: 'Nikkei 225',        exchange: 'TSE'  },
      { symbol: 'HSI',    name: 'Hang Seng Index',   exchange: 'HKEX' },
      { symbol: 'SHCOMP', name: 'Shanghai Composite',exchange: 'SSE'  },
      { symbol: 'SENSEX', name: 'BSE Sensex',        exchange: 'BSE'  },
      { symbol: 'KOSPI',  name: 'KOSPI',             exchange: 'KRX'  },
      { symbol: 'ASX200', name: 'ASX 200',           exchange: 'ASX'  },
    ],
  },
  {
    name: 'Global', icon: '🌐', region: 'Global',
    items: [
      { symbol: 'MSCIW',  name: 'MSCI World',            exchange: 'MSCI' },
      { symbol: 'MSCIEM', name: 'MSCI Emerging Markets', exchange: 'MSCI' },
    ],
  },
]

const filteredGroups = computed(() =>
  ALL_GROUPS.map(g => ({
    ...g,
    items: g.items.filter(i =>
      !search.value ||
      i.name.toLowerCase().includes(search.value.toLowerCase()) ||
      i.symbol.toLowerCase().includes(search.value.toLowerCase())
    ),
  }))
)

const matchCount = computed(() => filteredGroups.value.reduce((s, g) => s + g.items.length, 0))

function fmtPrice(v: number) {
  if (v >= 1000) return v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  return v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

useSeoMeta({
  title: 'Global Stock Market Indices — MetricsHour',
  description: 'Live prices for 18 major global stock indices: S&P 500, Dow Jones, Nasdaq 100, FTSE 100, DAX, Nikkei 225, and more.',
  ogTitle: 'Global Stock Market Indices — MetricsHour',
  ogDescription: 'Live prices for 18 major global stock indices: S&P 500, Dow Jones, Nasdaq 100, FTSE 100, DAX, Nikkei 225.',
  ogUrl: 'https://metricshour.com/indices/',
  ogType: 'website',
  ogImage: 'https://cdn.metricshour.com/og/section/indices.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/indices/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Global Stock Market Indices — MetricsHour',
      url: 'https://metricshour.com/indices/',
      description: 'Live prices for 18 major global stock indices.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
      mainEntity: {
        '@type': 'ItemList',
        itemListElement: (indices.value ?? []).slice(0, 30).map((idx: any, i: number) => ({
          '@type': 'ListItem',
          position: i + 1,
          name: idx.name,
          item: `https://metricshour.com/indices/${idx.symbol.toLowerCase()}/`,
        })),
      },
    }),
  }],
})))
</script>
