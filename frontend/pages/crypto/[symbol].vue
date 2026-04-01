<template>
  <div>
    <!-- Hero band -->
    <div class="bg-gradient-to-b from-[#130a00] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/crypto/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Crypto
        </NuxtLink>

        <div v-if="pending" class="h-20 flex items-center">
          <div class="space-y-2">
            <div class="h-8 w-40 bg-[#1f2937] rounded animate-pulse"/>
            <div class="h-4 w-64 bg-[#1f2937] rounded animate-pulse"/>
          </div>
        </div>
        <div v-else-if="error || !asset" class="text-red-400 text-sm py-6">Asset not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 rounded-xl bg-orange-900/30 border border-orange-800/40 flex items-center justify-center text-2xl shrink-0">
                {{ COIN_META[asset.symbol]?.icon ?? '🪙' }}
              </div>
              <div>
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h1 class="text-3xl font-extrabold text-white tracking-tight">{{ asset.name }}</h1>
                  <span class="text-[10px] font-bold text-orange-400/80 bg-orange-400/10 border border-orange-800/40 px-2 py-1 rounded-md">{{ asset.symbol }}</span>
                </div>
                <p class="text-gray-500 text-xs">Cryptocurrency · Global Markets · 24/7</p>
              </div>
            </div>
            <div class="text-right">
              <div class="text-4xl font-extrabold text-white tabular-nums tracking-tight">
                {{ asset.price ? fmtPrice(asset.price.close) : '—' }}
              </div>
              <div v-if="asset.price?.change_pct != null" class="text-sm mt-1 tabular-nums"
                   :class="asset.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ asset.price.change_pct >= 0 ? '▲' : '▼' }}
                {{ Math.abs(asset.price.change_pct).toFixed(2) }}%
                <span class="text-gray-600 font-normal ml-1">24h</span>
              </div>
              <div class="text-xs text-gray-600 mt-1">
                {{ asset.price?.timestamp ? 'Updated ' + fmtTs(asset.price.timestamp) : 'Awaiting price feed' }}
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-8" v-if="asset">

      <!-- Stats -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Market Cap</div>
          <div class="text-white font-bold text-lg">{{ asset.market_cap_usd ? fmtCap(asset.market_cap_usd) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Day Open</div>
          <div class="text-white font-bold text-lg">{{ asset.price?.open ? fmtPrice(asset.price.open) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">24h Volume</div>
          <div class="text-white font-bold text-lg">{{ latestVolume ? fmtCap(latestVolume) : '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Exchange</div>
          <div class="text-white font-bold text-lg">{{ asset.exchange || '—' }}</div>
        </div>
      </div>

      <!-- Summary -->
      <div v-if="pageSummary?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-4 text-sm text-gray-400 leading-relaxed page-summary">
        {{ pageSummary.summary }}
      </div>

      <!-- Insights (rotating) -->
      <div v-if="pageInsights?.length" class="mb-4">
        <div class="relative border rounded-lg p-4 overflow-hidden bg-[#0d1520] border-orange-900/50 page-insight-latest">
          <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-orange-500/40 to-transparent"/>
          <div class="flex items-start gap-3">
            <span class="text-base mt-0.5 shrink-0 text-orange-400">◆</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1 flex-wrap">
                <span class="text-[10px] font-bold uppercase tracking-widest text-orange-400">MetricsHour Intelligence</span>
                <span class="text-[10px] text-gray-700 ml-auto">{{ fmtInsightDate(pageInsights[featuredIdx].generated_at) }}</span>
              </div>
              <p class="text-sm text-gray-300 leading-relaxed">{{ pageInsights[featuredIdx].summary }}</p>
            </div>
          </div>
        </div>
        <div v-if="pageInsights.length > 1" class="mt-1.5 border border-[#1a2030] rounded-lg overflow-hidden">
          <div class="divide-y divide-[#131b27]">
            <div
              v-for="(insight, i) in otherInsights"
              v-show="showAllInsights || i < 2"
              :key="insight.generated_at"
              class="flex items-start gap-3 px-3 py-2 bg-[#0a0d14] cursor-pointer"
              @click="toggleInsight(insight.generated_at)"
            >
              <span class="text-[10px] text-gray-600 shrink-0 mt-0.5 w-16">{{ new Date(insight.generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }}</span>
              <p class="text-xs text-gray-500 leading-relaxed" :class="expandedInsights.has(insight.generated_at) ? '' : 'line-clamp-2'">{{ insight.summary }}</p>
            </div>
          </div>
          <button
            v-if="pageInsights.length > 3"
            class="w-full px-3 py-2 text-[10px] text-gray-600 hover:text-orange-400 bg-[#0a0d14] border-t border-[#1a2030] transition-colors text-left"
            @click="showAllInsights = !showAllInsights"
          >
            {{ showAllInsights ? '↑ Show less' : `↓ Read more (${pageInsights.length - 3} more insights)` }}
          </button>
        </div>
      </div>

      <!-- Price chart -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4 mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-base font-bold text-white">Price History</h2>
          <div class="flex gap-1">
            <button
              v-for="r in RANGES"
              :key="r.label"
              @click="activeRange = r.days"
              class="text-xs px-2 py-0.5 rounded transition-colors"
              :class="activeRange === r.days ? 'bg-orange-600 text-white' : 'text-gray-500 hover:text-gray-300'"
            >{{ r.label }}</button>
          </div>
        </div>
        <EChartLine v-if="chartOption" :option="chartOption" height="260px" />
        <div v-else class="h-[260px] flex items-center justify-center text-gray-600 text-sm">
          No price history yet.
        </div>
      </div>

      <!-- About -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-3">About {{ asset.name }}</h2>
        <p class="text-gray-400 text-sm leading-relaxed">{{ cryptoDescription(asset.symbol, asset.name) }}</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <NuxtLink to="/crypto/" class="text-xs text-orange-400 hover:text-orange-300 border border-orange-800/40 px-3 py-1.5 rounded-lg transition-colors">
            ← All Crypto
          </NuxtLink>
          <NuxtLink to="/markets/" class="text-xs text-gray-400 hover:text-gray-300 border border-[#1f2937] px-3 py-1.5 rounded-lg transition-colors">
            Browse Markets →
          </NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center mb-8">Data: CoinGecko · Marketstack</p>

      <!-- Newsletter -->
      <div class="border border-gray-800 rounded-xl p-6 bg-gray-900/40">
        <p class="text-xs font-mono text-orange-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">Crypto + macro context, every week.</p>
        <p class="text-xs text-gray-500 mb-4">Market moves, on-chain data, economic shifts — free.</p>
        <NewsletterCapture :source="`crypto_page_${symbol}`" button-text="Subscribe free" />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()
const symbol = (route.params.symbol as string).toUpperCase()

const { data: asset, pending, error } = useAsyncData(
  `crypto-${symbol}`,
  () => get<any>(`/api/assets/${symbol}`).catch(() => null),
)

const { data: pageSummary } = useAsyncData(
  `summary-crypto-${symbol}`,
  () => get<any>(`/api/summaries/crypto/${symbol}`).catch(() => null),
  { server: false },
)

const { data: pageInsights } = useAsyncData(
  `insights-crypto-${symbol}`,
  () => get<any[]>(`/api/insights/crypto/${symbol}`).catch(() => []),
  { server: false },
)

const { data: pricesRaw } = useAsyncData(
  `crypto-prices-${symbol}`,
  () => get<any[]>(`/api/assets/${symbol}/prices?interval=1d&limit=365`).catch(() => []),
  { server: false },
)

// ── Insight rotation — cycles through most recent 3 over consecutive days ─────
const featuredIdx = computed(() => {
  const ins = pageInsights.value
  if (!ins?.length) return 0
  const day = Math.floor(Date.now() / 86400000)
  return day % Math.min(ins.length, 3)
})

const otherInsights = computed(() => {
  const ins = pageInsights.value ?? []
  return ins.filter((_: any, i: number) => i !== featuredIdx.value)
})

const expandedInsights = ref<Set<string>>(new Set())
const showAllInsights = ref(false)
const toggleInsight = (key: string) => {
  const s = new Set(expandedInsights.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedInsights.value = s
}

// ── Chart ─────────────────────────────────────────────────────────────────────
const RANGES = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
]
const activeRange = ref(90)

const latestVolume = computed(() => {
  const p = pricesRaw.value
  if (!p?.length) return null
  return p[p.length - 1]?.v ?? null
})

const chartOption = computed(() => {
  const p = pricesRaw.value
  if (!p?.length) return null
  const slice = p.slice(-activeRange.value)
  const dates  = slice.map((x: any) => x.t?.slice(0, 10))
  const closes = slice.map((x: any) => x.c)
  const isUp   = closes[closes.length - 1] >= closes[0]
  const color  = isUp ? '#f97316' : '#f87171'
  return {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 8, bottom: 40, containLabel: true },
    tooltip: { trigger: 'axis', backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#fff', fontSize: 11 }, formatter: (p: any) => `${p[0].axisValue}<br/>${fmtPrice(p[0].value)}` },
    xAxis: { type: 'category', data: dates, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, interval: Math.floor(slice.length / 5) } },
    yAxis: { type: 'value', scale: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => fmtPrice(v) }, splitLine: { lineStyle: { color: '#1f2937' } } },
    series: [{ type: 'line', data: closes, smooth: true, symbol: 'none', lineStyle: { color, width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '33' }, { offset: 1, color: color + '00' }] } } }],
  }
})

// ── Helpers ───────────────────────────────────────────────────────────────────
const COIN_META: Record<string, { icon: string }> = {
  BTC:  { icon: '₿' },
  ETH:  { icon: '⟠' },
  BNB:  { icon: '🟡' },
  SOL:  { icon: '🌅' },
  XRP:  { icon: '⚡' },
  DOGE: { icon: '🐕' },
  ADA:  { icon: '🔵' },
  AVAX: { icon: '🔺' },
  DOT:  { icon: '🟣' },
  LINK: { icon: '⛓️' },
}

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

function fmtTs(ts: string): string {
  if (!ts) return ''
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function fmtInsightDate(ts: string): string {
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const CRYPTO_DESCRIPTIONS: Record<string, string> = {
  BTC:  'Bitcoin (BTC) is the first and largest cryptocurrency by market capitalisation. Created in 2009 by the pseudonymous Satoshi Nakamoto, it operates on a decentralised proof-of-work blockchain. Bitcoin is widely regarded as a store of value and a hedge against inflation.',
  ETH:  'Ethereum (ETH) is a programmable blockchain platform enabling smart contracts and decentralised applications (dApps). Its native token Ether powers transactions and computations. Ethereum transitioned to proof-of-stake in 2022, significantly reducing its energy consumption.',
  BNB:  'BNB (formerly Binance Coin) is the native token of the BNB Chain ecosystem and Binance exchange. It is used for trading fee discounts, token launches, and powering transactions on BNB Smart Chain.',
  SOL:  'Solana (SOL) is a high-performance blockchain known for fast transaction speeds and low fees. It uses a hybrid proof-of-history and proof-of-stake consensus and hosts a large ecosystem of DeFi and NFT applications.',
  XRP:  'XRP is the native digital asset of the XRP Ledger, designed for fast, low-cost cross-border payments. Ripple Labs developed the protocol and uses XRP for liquidity provisioning in its payment network.',
  DOGE: 'Dogecoin (DOGE) began as a meme cryptocurrency in 2013 but gained mainstream attention and a large community. It uses a proof-of-work consensus and is frequently cited for its fast transaction times and low fees.',
  ADA:  'Cardano (ADA) is a proof-of-stake blockchain platform developed by IOHK, founded by Ethereum co-founder Charles Hoskinson. It focuses on peer-reviewed research and formal verification for smart contract security.',
  AVAX: 'Avalanche (AVAX) is a smart contract platform designed for high throughput and low latency. It achieves fast finality through its novel consensus mechanism and supports multiple interoperable blockchains (subnets).',
  DOT:  'Polkadot (DOT) is a multi-chain network connecting multiple specialised blockchains (parachains) into a single ecosystem. It enables cross-chain communication and was developed by Ethereum co-founder Gavin Wood.',
  LINK: 'Chainlink (LINK) is a decentralised oracle network that connects smart contracts with real-world data, APIs, and payment systems. It is the most widely used oracle solution across DeFi protocols.',
}

function cryptoDescription(sym: string, name: string): string {
  return CRYPTO_DESCRIPTIONS[sym] ??
    `${name} (${sym}) is a cryptocurrency tracked on global digital asset markets. Price history and market data are updated continuously on MetricsHour.`
}

// ── SEO ───────────────────────────────────────────────────────────────────────
const _change = computed(() => asset.value?.price?.change_pct ?? null)

const _seoTitle = computed(() => {
  if (!asset.value) return `${symbol} Price — MetricsHour`
  const name  = asset.value.name
  const price = asset.value.price?.close
  const chg   = _change.value
  if (price != null && chg != null) {
    return `${name} Price Today: ${fmtPrice(price)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%) — MetricsHour`
  }
  return `${name} (${symbol}) Price & Data — MetricsHour`
})

const _seoDesc = computed(() => {
  if (!asset.value) return ''
  const name  = asset.value.name
  const price = asset.value.price?.close
  const chg   = _change.value
  if (price != null && chg != null) {
    return `${name} (${symbol}) is trading at ${fmtPrice(price)} (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}% today). Live crypto price, market cap, and chart on MetricsHour.`
  }
  return `${name} (${symbol}) live price, market cap, and price history. Updated in real time on MetricsHour.`
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: `https://metricshour.com/crypto/${symbol.toLowerCase()}/`,
  ogType: 'website',
  twitterCard: 'summary_large_image',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/crypto/${symbol.toLowerCase()}/` }],
})))
</script>
