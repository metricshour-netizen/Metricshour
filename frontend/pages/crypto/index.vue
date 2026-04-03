<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Crypto Markets</h1>
      <p class="text-gray-500 text-sm mt-1">Top cryptocurrencies by market cap — live prices 24/7</p>
    </div>

    <!-- Search -->
    <div class="relative mb-6">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search — Bitcoin, Ethereum, Solana, XRP..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-orange-500 transition-colors"
      />
      <button v-if="search" @click="search = ''" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 p-1.5">✕</button>
    </div>

    <div v-if="pending" class="space-y-2">
      <div v-for="i in 10" :key="i" class="h-16 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
    </div>

    <template v-else>
      <p v-if="search" class="text-xs text-gray-600 mb-4">{{ filtered.length }} result{{ filtered.length !== 1 ? 's' : '' }} for "{{ search }}"</p>

      <!-- Table header -->
      <div class="hidden sm:grid grid-cols-[2fr_1fr_1fr_1fr_1fr] gap-4 px-4 mb-2 text-[11px] text-gray-600 uppercase tracking-widest font-semibold">
        <span>Asset</span>
        <span class="text-right">Price</span>
        <span class="text-right">24h Change</span>
        <span class="text-right">Market Cap</span>
        <span class="text-right">24h Volume</span>
      </div>

      <div class="space-y-1.5">
        <NuxtLink
          v-for="(coin, idx) in filtered"
          :key="coin.symbol"
          :to="`/crypto/${coin.symbol.toLowerCase()}/`"
          class="grid grid-cols-[2fr_1fr_1fr] sm:grid-cols-[2fr_1fr_1fr_1fr_1fr] gap-4 items-center bg-[#111827] border border-[#1f2937] hover:border-orange-500/50 rounded-xl px-4 py-3.5 transition-all hover:bg-[#131d2e] group"
        >
          <!-- Rank + Name -->
          <div class="flex items-center gap-3">
            <span class="text-[11px] text-gray-700 tabular-nums w-5 text-right shrink-0">{{ idx + 1 }}</span>
            <span class="text-xl shrink-0">{{ COIN_META[coin.symbol]?.icon ?? '🪙' }}</span>
            <div>
              <div class="text-sm font-bold text-white group-hover:text-orange-300 transition-colors">{{ coin.name }}</div>
              <div class="text-[11px] text-gray-600 font-mono">{{ coin.symbol }}</div>
            </div>
          </div>

          <!-- Price -->
          <div class="text-right">
            <div class="text-sm font-bold text-white tabular-nums">
              {{ coin.price?.close != null ? fmtPrice(coin.price.close) : '—' }}
            </div>
            <div class="text-[10px] text-gray-700 sm:hidden">Price</div>
          </div>

          <!-- 24h Change -->
          <div class="text-right">
            <template v-if="coin.price?.change_pct != null">
              <span
                class="text-sm font-bold tabular-nums"
                :class="coin.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'"
              >{{ coin.price.change_pct >= 0 ? '+' : '' }}{{ coin.price.change_pct.toFixed(2) }}%</span>
            </template>
            <span v-else class="text-sm text-gray-700">—</span>
          </div>

          <!-- Market Cap (desktop only) -->
          <div class="hidden sm:block text-right text-sm text-gray-300 tabular-nums">
            {{ coin.market_cap_usd ? fmtCap(coin.market_cap_usd) : '—' }}
          </div>

          <!-- 24h Volume (desktop only) -->
          <div class="hidden sm:block text-right text-sm text-gray-500 tabular-nums">
            {{ coin.price?.volume ? fmtCap(coin.price.volume) : '—' }}
          </div>
        </NuxtLink>
      </div>

      <div v-if="filtered.length === 0 && search" class="text-center py-16 text-gray-600 text-sm">
        No cryptocurrencies match "{{ search }}"
      </div>

      <p class="text-xs text-gray-700 mt-6">Prices update every 2 minutes</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const { r2ListFetch } = useR2Fetch()
const search = ref('')

const COIN_META: Record<string, { icon: string }> = {
  BTC:  { icon: '₿' },
  ETH:  { icon: '🔷' },
  BNB:  { icon: '🟡' },
  SOL:  { icon: '🌅' },
  XRP:  { icon: '⚡' },
  DOGE: { icon: '🐕' },
  ADA:  { icon: '🔵' },
  AVAX: { icon: '🔺' },
  DOT:  { icon: '🟣' },
  LINK: { icon: '⛓️' },
}

const { data: coins, pending } = useAsyncData('crypto',
  () => r2ListFetch<any>('snapshots/lists/assets.json', '/api/assets?type=crypto')
    .then((list: any[]) => list
      .filter(a => a.asset_type === 'crypto')
      .sort((a, b) => (b.market_cap_usd ?? 0) - (a.market_cap_usd ?? 0))
    )
    .catch(() => []),
)

const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  if (!q) return coins.value ?? []
  return (coins.value ?? []).filter((c: any) =>
    c.name.toLowerCase().includes(q) || c.symbol.toLowerCase().includes(q)
  )
})

function fmtPrice(v: number): string {
  if (v >= 10_000) return '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1)      return '$' + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  if (v >= 0.01)   return '$' + v.toFixed(4)
  return '$' + v.toFixed(6)
}

function fmtCap(v: number): string {
  if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T'
  if (v >= 1e9)  return '$' + (v / 1e9).toFixed(1) + 'B'
  if (v >= 1e6)  return '$' + (v / 1e6).toFixed(0) + 'M'
  return '$' + v.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

useSeoMeta({
  title: 'Crypto Prices: Bitcoin, Ethereum & Top Coins — MetricsHour',
  description: 'Live cryptocurrency prices, market caps, and 24h changes for Bitcoin, Ethereum, Solana, XRP and top coins. Updated every 2 minutes.',
  ogTitle: 'Crypto Prices: Bitcoin, Ethereum & Top Coins — MetricsHour',
  ogDescription: 'Live cryptocurrency prices, market caps, and 24h changes for Bitcoin, Ethereum, Solana, XRP and top coins.',
  ogUrl: 'https://metricshour.com/crypto/',
  ogType: 'website',
  ogImage: 'https://cdn.metricshour.com/og/section/crypto.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterImage: 'https://cdn.metricshour.com/og/section/crypto.png',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/crypto/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Cryptocurrency Prices — MetricsHour',
      url: 'https://metricshour.com/crypto/',
      description: 'Live cryptocurrency prices, 24h changes, and market caps. BTC, ETH, SOL and 50+ coins.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
      mainEntity: {
        '@type': 'ItemList',
        itemListElement: (coins.value ?? []).slice(0, 50).map((c: any, i: number) => ({
          '@type': 'ListItem',
          position: i + 1,
          name: c.name || c.symbol,
          item: `https://metricshour.com/crypto/${c.symbol.toLowerCase()}/`,
        })),
      },
    }),
  }],
})))
</script>
