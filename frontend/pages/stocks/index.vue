<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl sm:text-2xl font-bold text-white">Stocks</h1>
        <p class="text-gray-500 text-sm mt-1">Top global stocks · Geographic revenue exposure · SEC EDGAR filings</p>
      </div>
      <!-- Terminal View toggle -->
      <button
        @click="terminalView = !terminalView"
        class="shrink-0 flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg border transition-all"
        :class="terminalView
          ? 'bg-emerald-950 border-emerald-700 text-emerald-400'
          : 'border-[#1f2937] text-gray-500 hover:border-gray-500 hover:text-gray-300'"
        title="Toggle Terminal View"
      >
        <span class="font-mono">⌨</span> Terminal
      </button>
    </div>

    <!-- Search -->
    <div class="relative mb-4">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search ticker, company, sector..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
      />
      <button v-if="search" @click="search = ''" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs">✕</button>
    </div>

    <!-- Sector filter (hidden in terminal view) -->
    <div v-if="sectors.length && !terminalView" class="flex gap-2 flex-wrap mb-6">
      <button
        @click="activeSector = null"
        class="px-3 py-2 rounded-lg text-xs font-medium border transition-colors"
        :class="!activeSector ? 'bg-emerald-500 border-emerald-500 text-black' : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >All</button>
      <button
        v-for="s in sectors"
        :key="s"
        @click="activeSector = activeSector === s ? null : s"
        class="px-3 py-2 rounded-lg text-xs font-medium border transition-colors"
        :class="activeSector === s ? 'bg-emerald-500 border-emerald-500 text-black' : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >{{ s }}</button>
    </div>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>

    <template v-else>
      <p v-if="search" class="text-xs text-gray-600 mb-4">{{ filtered.length }} result{{ filtered.length !== 1 ? 's' : '' }} for "{{ search }}"</p>

      <!-- ── Terminal View ──────────────────────────────────────────────────── -->
      <div v-if="terminalView" class="terminal-view rounded-lg overflow-hidden border border-emerald-900/60">
        <div class="bg-[#0a0a0a] px-3 py-1.5 border-b border-emerald-900/40 flex items-center justify-between">
          <span class="text-[10px] text-emerald-700 font-mono uppercase tracking-widest">METRICSHOUR TERMINAL · STOCKS · {{ filtered.length }} LISTED</span>
          <span class="text-[10px] text-emerald-800 font-mono">{{ nowStr }}</span>
        </div>
        <div class="bg-[#0a0a0a] overflow-x-auto">
          <!-- Header -->
          <div class="grid font-mono text-[11px] text-emerald-700 uppercase tracking-wider px-3 py-1.5 border-b border-emerald-900/30"
               style="grid-template-columns: 2rem 5rem 1fr 6rem 5rem 4rem">
            <span>#</span>
            <span>TICKER</span>
            <span>COMPANY</span>
            <span class="text-right">MKT CAP</span>
            <span class="text-right">COUNTRY</span>
            <span class="text-right">SECTOR</span>
          </div>
          <!-- Rows (max 50) -->
          <NuxtLink
            v-for="(s, i) in terminalRows"
            :key="s.symbol"
            :to="`/stocks/${s.symbol.toLowerCase()}`"
            class="grid font-mono text-[11px] px-3 py-[5px] border-b border-emerald-900/10 hover:bg-emerald-950/40 transition-colors"
            style="grid-template-columns: 2rem 5rem 1fr 6rem 5rem 4rem"
          >
            <span class="text-emerald-800">{{ i + 1 }}</span>
            <span class="text-emerald-400 font-bold">{{ s.symbol }}</span>
            <span class="text-emerald-300 truncate pr-2">{{ s.name }}</span>
            <span class="text-right text-emerald-500 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
            <span class="text-right text-emerald-700">{{ s.country?.code || '—' }}</span>
            <span class="text-right text-emerald-800 truncate">{{ s.sector ? s.sector.slice(0, 4).toUpperCase() : '—' }}</span>
          </NuxtLink>
        </div>
        <div v-if="filtered.length > 50" class="bg-[#0a0a0a] px-3 py-1.5 text-[10px] text-emerald-800 font-mono">
          ... {{ filtered.length - 50 }} more — use search to filter
        </div>
      </div>

      <!-- ── Card View (default) ───────────────────────────────────────────── -->
      <div v-else-if="filtered.length" class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
        <!-- Desktop header -->
        <div class="hidden sm:grid px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide"
             style="grid-template-columns: 2rem 1fr 7rem 6rem 7rem 1.5rem">
          <span>#</span>
          <span>Company</span>
          <span>Sector</span>
          <span class="text-right">Price · Updated</span>
          <span class="text-right">Mkt Cap</span>
          <span></span>
        </div>
        <div class="divide-y divide-[#1f2937]">
          <NuxtLink
            v-for="(s, i) in filtered"
            :key="s.symbol"
            :to="`/stocks/${s.symbol.toLowerCase()}`"
            class="block hover:bg-[#1a2235] transition-colors"
          >
            <!-- Mobile row -->
            <div class="flex items-center justify-between px-4 py-3 sm:hidden">
              <div class="flex items-center gap-2.5 min-w-0">
                <span v-if="s.country" class="text-base leading-none shrink-0" aria-hidden="true">{{ s.country.flag }}</span>
                <div class="min-w-0">
                  <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
                  <div class="text-xs text-gray-500 truncate max-w-[140px]">{{ s.name }}</div>
                  <div class="text-[10px] text-gray-600 mt-0.5">{{ s.sector || '—' }}</div>
                </div>
              </div>
              <div class="text-right shrink-0 ml-2">
                <div class="text-sm font-bold tabular-nums font-mono" :class="isStale(s.price?.timestamp) ? 'text-gray-400' : 'text-white'">{{ s.price ? fmtPrice(s.price.close) : '—' }}</div>
                <div class="text-[10px] text-gray-600 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</div>
                <div v-if="s.price?.timestamp" class="text-[11px] mt-1 tabular-nums font-mono font-semibold" :class="isStale(s.price.timestamp) ? 'text-amber-400' : 'text-emerald-400'">↻ {{ fmtCloseDate(s.price.timestamp) }}</div>
                <div v-else-if="s.price" class="text-[10px] mt-0.5 text-gray-600">no ts</div>
              </div>
            </div>
            <!-- Desktop row -->
            <div class="hidden sm:grid px-4 py-3 items-center"
                 style="grid-template-columns: 2rem 1fr 7rem 6rem 7rem 1.5rem">
              <span class="text-xs text-gray-600">{{ i + 1 }}</span>
              <div class="flex items-center gap-2 min-w-0 pr-2">
                <span v-if="s.country" class="text-base leading-none shrink-0" aria-hidden="true">{{ s.country.flag }}</span>
                <div class="min-w-0">
                  <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
                  <div class="text-xs text-gray-500 truncate">{{ s.name }}</div>
                </div>
              </div>
              <span class="text-xs text-gray-500 truncate pr-2">{{ s.sector || '—' }}</span>
              <div class="text-right">
                <div class="text-sm font-bold tabular-nums font-mono" :class="isStale(s.price?.timestamp) ? 'text-gray-400' : 'text-white'">{{ s.price ? fmtPrice(s.price.close) : '—' }}</div>
                <div v-if="s.price?.timestamp" class="text-xs tabular-nums font-mono mt-1 font-semibold" :class="isStale(s.price.timestamp) ? 'text-amber-400' : 'text-emerald-400'">
                  ↻ {{ fmtCloseDate(s.price.timestamp) }}
                </div>
                <div v-else-if="s.price" class="text-[10px] text-gray-600 mt-0.5">no timestamp</div>
                <div v-else class="text-[10px] text-gray-600">no data</div>
              </div>
              <span class="text-xs text-right text-gray-400 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
              <span class="text-right text-emerald-600 text-xs">→</span>
            </div>
          </NuxtLink>
        </div>
      </div>

      <div v-else-if="search" class="text-center py-16 text-gray-600 text-sm">
        No stocks match "{{ search }}"
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const { r2ListFetch } = useR2Fetch()
const activeSector = ref<string | null>(null)
const search = ref('')
const terminalView = ref(false)

const { data: stocks, pending } = useAsyncData('stocks',
  // R2 list has all asset types — filter to stocks client-side
  () => r2ListFetch<any>('snapshots/lists/assets.json', '/api/assets?type=stock')
    .then(list => list.filter((a: any) => a.asset_type === 'stock'))
    .catch(() => []),
)

const sectors = computed(() => {
  if (!stocks.value?.length) return []
  return [...new Set(stocks.value.map((s: any) => s.sector).filter(Boolean))].sort()
})

const filtered = computed(() => {
  if (!stocks.value) return []
  let list = stocks.value as any[]

  if (activeSector.value) {
    list = list.filter((s: any) => s.sector === activeSector.value)
  }

  if (search.value.trim()) {
    const q = search.value.toLowerCase().trim()
    list = list.filter((s: any) =>
      s.symbol?.toLowerCase().includes(q) ||
      s.name?.toLowerCase().includes(q) ||
      s.sector?.toLowerCase().includes(q) ||
      s.country?.name?.toLowerCase().includes(q)
    )
  }

  // Rank: stocks with price data first, then by market cap desc
  return [...list].sort((a, b) => {
    const aHasPrice = a.price ? 1 : 0
    const bHasPrice = b.price ? 1 : 0
    if (bHasPrice !== aHasPrice) return bHasPrice - aHasPrice
    return (b.market_cap_usd || 0) - (a.market_cap_usd || 0)
  })
})

// Terminal View: max 50 rows, densely packed
const terminalRows = computed(() => filtered.value.slice(0, 50))

// Live clock for terminal header
const nowStr = ref('')
onMounted(() => {
  const update = () => {
    nowStr.value = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
  }
  update()
  setInterval(update, 1000)

  // Restore terminal view preference
  terminalView.value = localStorage.getItem('stocks-terminal') === '1'
})
watch(terminalView, v => {
  localStorage.setItem('stocks-terminal', v ? '1' : '0')
})

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtPrice(v: number): string {
  if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  if (v >= 1)    return `$${v.toFixed(2)}`
  return `$${v.toFixed(4)}`
}

function fmtAge(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function parseUTC(ts: string): Date {
  // Ensure naive ISO strings (no timezone suffix) are parsed as UTC
  if (ts && !ts.endsWith('Z') && !ts.includes('+') && !/[+-]\d{2}:\d{2}$/.test(ts)) {
    return new Date(ts + 'Z')
  }
  return new Date(ts)
}

function isStale(ts: string | undefined): boolean {
  if (!ts) return false
  return Date.now() - parseUTC(ts).getTime() > 86_400_000 // >24h
}

function fmtCloseDate(ts: string): string {
  const d = parseUTC(ts)
  if (isNaN(d.getTime())) return '—'
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC'
  if (isToday) return time
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' · ' + time
}

useSeoMeta({
  title: 'Stock Geographic Revenue: Where Companies Earn — MetricsHour',
  description: 'Top global stocks with geographic revenue exposure from SEC EDGAR. See which countries each stock earns from and how trade flows affect your portfolio.',
  ogTitle: 'Stock Geographic Revenue: Where Companies Earn — MetricsHour',
  ogDescription: 'Top global stocks with geographic revenue exposure from SEC EDGAR. See which countries each stock earns from and how trade flows affect your portfolio.',
  ogUrl: 'https://metricshour.com/stocks/',
  ogType: 'website',
  ogImage: 'https://api.metricshour.com/og/section/stocks.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterTitle: 'Stock Geographic Revenue: Where Companies Earn — MetricsHour',
  twitterDescription: 'Top global stocks with geographic revenue exposure from SEC EDGAR. See which countries each stock earns from and how trade flows affect your portfolio.',
  twitterImage: 'https://api.metricshour.com/og/section/stocks.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/stocks/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Stocks — MetricsHour',
      url: 'https://metricshour.com/stocks/',
      description: 'Top global stocks with geographic revenue exposure from SEC EDGAR 10-K filings.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
      mainEntity: {
        '@type': 'ItemList',
        itemListElement: (stocks.value ?? []).slice(0, 50).map((s: any, i: number) => ({
          '@type': 'ListItem',
          position: i + 1,
          name: s.name || s.symbol,
          item: `https://metricshour.com/stocks/${s.symbol.toLowerCase()}/`,
        })),
      },
    }),
  }],
})))
</script>
