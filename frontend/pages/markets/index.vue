<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Markets</h1>
      <p class="text-gray-500 text-sm mt-1">Stocks · Crypto · ETFs · Indices · Bonds · Commodities · FX</p>
    </div>

    <!-- Search -->
    <div class="relative mb-5">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search any asset — SPY, BTC, Gold, S&P 500, US10Y..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
        autofocus
      />
      <button v-if="search" @click="search = ''" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs">✕</button>
    </div>

    <!-- Tab filter -->
    <div class="flex gap-2 flex-wrap mb-6 overflow-x-auto pb-1">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        class="px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors whitespace-nowrap shrink-0"
        :class="activeTab === tab.key
          ? `${tab.activeClass} text-black`
          : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >
        <span class="mr-1">{{ tab.icon }}</span>{{ tab.label }}
        <span class="ml-1 opacity-50 text-[10px]">{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="pending" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
      <div v-for="i in 12" :key="i" class="h-24 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
    </div>

    <template v-else>
      <p v-if="search" class="text-xs text-gray-600 mb-4">
        {{ filtered.length }} result{{ filtered.length !== 1 ? 's' : '' }} for "{{ search }}"
      </p>

      <!-- ── Indices ─────────────────────────────────────────────────────── -->
      <template v-if="showSection('index') && indexFiltered.length">
        <SectionHeader color="bg-purple-400" label="Indices" />
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 mb-8">
          <div
            v-for="a in indexFiltered"
            :key="a.symbol"
            class="bg-[#111827] border border-[#1f2937] hover:border-purple-500/50 rounded-xl p-4 transition-colors group"
          >
            <div class="flex items-start justify-between mb-2">
              <span class="text-lg">{{ regionIcon(a.sector) }}</span>
              <span class="text-[10px] font-bold text-purple-400/70 bg-purple-400/10 px-1.5 py-0.5 rounded">INDEX</span>
            </div>
            <div class="text-sm font-bold text-white group-hover:text-purple-300 transition-colors truncate">{{ a.symbol }}</div>
            <div class="text-xs text-gray-500 truncate leading-snug">{{ a.name }}</div>
            <div class="text-[10px] text-gray-600 mt-1">{{ a.sector }} · {{ a.exchange }}</div>
            <PriceBadge :asset="a" />
          </div>
        </div>
      </template>

      <!-- ── Crypto ─────────────────────────────────────────────────────── -->
      <template v-if="showSection('crypto') && cryptoFiltered.length">
        <SectionHeader color="bg-amber-400" label="Crypto" />
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 mb-8">
          <NuxtLink
            v-for="a in cryptoFiltered"
            :key="a.symbol"
            :to="`/stocks/${a.symbol}`"
            class="bg-[#111827] border border-[#1f2937] hover:border-amber-500/50 rounded-xl p-4 transition-colors group"
          >
            <div class="flex items-start justify-between mb-2">
              <span class="text-lg">{{ cryptoIcon(a.symbol) }}</span>
              <span class="text-[10px] font-bold text-amber-400/70 bg-amber-400/10 px-1.5 py-0.5 rounded">CRYPTO</span>
            </div>
            <div class="text-sm font-bold text-white group-hover:text-amber-300 transition-colors">{{ a.symbol }}</div>
            <div class="text-xs text-gray-500 truncate">{{ a.name }}</div>
            <PriceBadge :asset="a" />
            <div v-if="a.market_cap_usd" class="text-[10px] text-gray-600 mt-0.5">{{ fmtCap(a.market_cap_usd) }} cap</div>
          </NuxtLink>
        </div>
      </template>

      <!-- ── Stocks ─────────────────────────────────────────────────────── -->
      <template v-if="showSection('stock') && stockFiltered.length">
        <SectionHeader color="bg-emerald-400" label="Stocks" />
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden mb-8">
          <div class="hidden sm:grid grid-cols-12 px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide">
            <span class="col-span-1">#</span>
            <span class="col-span-5">Company</span>
            <span class="col-span-3">Sector</span>
            <span class="col-span-2 text-right">Mkt Cap</span>
            <span class="col-span-1"></span>
          </div>
          <div class="divide-y divide-[#1f2937]">
            <NuxtLink v-for="(s, i) in stockFiltered" :key="s.symbol" :to="`/stocks/${s.symbol}`" class="block hover:bg-[#1a2235] transition-colors">
              <!-- Mobile -->
              <div class="flex items-center justify-between px-4 py-3 sm:hidden">
                <div class="flex items-center gap-2 min-w-0">
                  <span v-if="s.country" class="text-base shrink-0">{{ s.country.flag }}</span>
                  <div class="min-w-0">
                    <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
                    <div class="text-xs text-gray-500 truncate max-w-[150px]">{{ s.name }}</div>
                  </div>
                </div>
                <div class="text-right shrink-0 ml-2">
                  <div class="text-sm font-bold text-white tabular-nums">{{ fmtCap(s.market_cap_usd) }}</div>
                  <div class="text-emerald-500 text-xs">→</div>
                </div>
              </div>
              <!-- Desktop -->
              <div class="hidden sm:grid grid-cols-12 px-4 py-3 items-center">
                <span class="col-span-1 text-xs text-gray-600">{{ i + 1 }}</span>
                <div class="col-span-5 flex items-center gap-2">
                  <span v-if="s.country" class="text-base leading-none">{{ s.country.flag }}</span>
                  <div><div class="text-sm font-bold text-white">{{ s.symbol }}</div><div class="text-xs text-gray-500 truncate">{{ s.name }}</div></div>
                </div>
                <span class="col-span-3 text-xs text-gray-500">{{ s.sector || '—' }}</span>
                <span class="col-span-2 text-xs text-right text-white tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
                <span class="col-span-1 text-right text-emerald-500 text-xs">→</span>
              </div>
            </NuxtLink>
          </div>
        </div>
      </template>

      <!-- ── ETFs ───────────────────────────────────────────────────────── -->
      <template v-if="showSection('etf') && etfFiltered.length">
        <SectionHeader color="bg-sky-400" label="ETFs" />
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden mb-8">
          <div class="hidden sm:grid grid-cols-12 px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide">
            <span class="col-span-4">Fund</span>
            <span class="col-span-4">Category</span>
            <span class="col-span-2 text-right">AUM</span>
            <span class="col-span-2 text-right">Exchange</span>
          </div>
          <div class="divide-y divide-[#1f2937]">
            <div v-for="a in etfFiltered" :key="a.symbol" class="block">
              <!-- Mobile -->
              <div class="flex items-center justify-between px-4 py-3 sm:hidden">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-bold text-sky-400">{{ a.symbol }}</span>
                    <span class="text-[10px] text-gray-600 bg-[#1f2937] px-1.5 py-0.5 rounded">{{ a.sector }}</span>
                  </div>
                  <div class="text-xs text-gray-500 truncate max-w-[200px] mt-0.5">{{ a.name }}</div>
                </div>
                <div class="text-right shrink-0 ml-2">
                  <div class="text-sm font-bold text-white tabular-nums">{{ fmtCap(a.market_cap_usd) }}</div>
                </div>
              </div>
              <!-- Desktop -->
              <div class="hidden sm:grid grid-cols-12 px-4 py-3 items-center hover:bg-[#1a2235] transition-colors">
                <div class="col-span-4">
                  <div class="text-sm font-bold text-sky-400">{{ a.symbol }}</div>
                  <div class="text-xs text-gray-500 truncate">{{ a.name }}</div>
                </div>
                <span class="col-span-4 text-xs text-gray-500">{{ a.sector }}</span>
                <span class="col-span-2 text-xs text-right text-white tabular-nums">{{ fmtCap(a.market_cap_usd) }}</span>
                <span class="col-span-2 text-xs text-right text-gray-600">{{ a.exchange }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ── Bonds ──────────────────────────────────────────────────────── -->
      <template v-if="showSection('bond') && bondFiltered.length">
        <SectionHeader color="bg-rose-400" label="Bonds" />
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 mb-8">
          <div
            v-for="a in bondFiltered"
            :key="a.symbol"
            class="bg-[#111827] border border-[#1f2937] hover:border-rose-500/40 rounded-xl p-4 transition-colors group"
          >
            <div class="flex items-start justify-between mb-2">
              <span class="text-lg">{{ bondIcon(a.symbol) }}</span>
              <span class="text-[10px] font-bold text-rose-400/70 bg-rose-400/10 px-1.5 py-0.5 rounded">{{ a.sector }}</span>
            </div>
            <div class="text-sm font-bold text-white group-hover:text-rose-300 transition-colors leading-tight">{{ a.symbol }}</div>
            <div class="text-xs text-gray-500 leading-snug mt-0.5 truncate">{{ a.name }}</div>
            <div class="text-[10px] text-gray-600 mt-1.5">{{ a.industry }} · {{ a.exchange }}</div>
            <PriceBadge :asset="a" />
          </div>
        </div>
      </template>

      <!-- ── Commodities ────────────────────────────────────────────────── -->
      <template v-if="showSection('commodity') && commodityGroups.some(g => g.items.length)">
        <SectionHeader color="bg-blue-400" label="Commodities" />
        <div v-for="group in commodityGroups" :key="group.name" class="mb-6">
          <p v-if="group.items.length" class="text-[10px] text-gray-600 uppercase tracking-widest font-bold mb-2">{{ group.name }}</p>
          <div v-if="group.items.length" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            <div v-for="c in group.items" :key="c.symbol" class="bg-[#111827] border border-[#1f2937] hover:border-blue-500/40 rounded-xl p-4 transition-colors group">
              <div class="text-xl mb-2">{{ c.icon }}</div>
              <div class="text-sm font-medium text-white group-hover:text-blue-300 transition-colors truncate mb-0.5">{{ apiMap[c.symbol]?.name ?? c.name }}</div>
              <div class="text-xs text-gray-600 mb-2">{{ c.symbol }}</div>
              <PriceBadge :asset="apiMap[c.symbol]" />
            </div>
          </div>
        </div>
        <div class="mb-8"/>
      </template>

      <!-- ── FX ─────────────────────────────────────────────────────────── -->
      <template v-if="showSection('fx') && fxFiltered.length">
        <SectionHeader color="bg-teal-400" label="FX / Currencies" />
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 mb-8">
          <div v-for="a in fxFiltered" :key="a.symbol" class="bg-[#111827] border border-[#1f2937] hover:border-teal-500/40 rounded-xl p-4 transition-colors group">
            <div class="flex items-start justify-between mb-2">
              <span class="text-lg">💱</span>
              <span class="text-[10px] font-bold text-teal-400/70 bg-teal-400/10 px-1.5 py-0.5 rounded">FX</span>
            </div>
            <div class="text-sm font-bold text-white group-hover:text-teal-300 transition-colors">{{ a.symbol }}</div>
            <div class="text-xs text-gray-500 truncate">{{ a.name }}</div>
            <PriceBadge :asset="a" />
          </div>
        </div>
      </template>

      <!-- Empty state -->
      <div v-if="filtered.length === 0 && search" class="text-center py-20 text-gray-600 text-sm">
        No assets match "{{ search }}"
      </div>

      <p class="text-xs text-gray-700 mt-2">Data: Marketstack · CoinGecko · exchangerate.host · Bloomberg · FRED</p>
    </template>
  </main>
</template>

<script setup lang="ts">
// ── Sub-components ────────────────────────────────────────────────────────────

const SectionHeader = defineComponent({
  props: { color: String, label: String },
  template: `<h2 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 flex items-center gap-2">
    <span class="w-2 h-2 rounded-full inline-block" :class="color"></span> {{ label }}
  </h2>`,
})

const PriceBadge = defineComponent({
  props: { asset: Object },
  setup() {
    function fmtPrice(v: number): string {
      if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
      if (v >= 1)    return `$${v.toFixed(2)}`
      return `$${v.toFixed(4)}`
    }
    return { fmtPrice }
  },
  template: `<div v-if="asset?.price" class="text-sm font-bold text-white mt-2 tabular-nums">{{ fmtPrice(asset.price.close) }}</div>
             <div v-else class="text-[10px] text-gray-700 mt-2 flex items-center gap-1"><span class="w-1 h-1 rounded-full bg-yellow-700 inline-block"></span> Pending</div>`,
})

// ── Data ──────────────────────────────────────────────────────────────────────

const { get } = useApi()
const search = ref('')
const activeTab = ref('all')

const { data: allAssets, pending } = await useAsyncData('markets-all',
  () => get<any[]>('/api/assets').catch(() => []),
)

function byType(type: string) {
  return (allAssets.value ?? []).filter((a: any) => a.asset_type === type)
}

const tabs = computed(() => [
  { key: 'all',       label: 'All',        icon: '◈', activeClass: 'bg-emerald-500 border-emerald-500', count: allAssets.value?.length ?? 0 },
  { key: 'index',     label: 'Indices',    icon: '📊', activeClass: 'bg-purple-500 border-purple-500',  count: byType('index').length },
  { key: 'crypto',    label: 'Crypto',     icon: '₿',  activeClass: 'bg-amber-500 border-amber-500',   count: byType('crypto').length },
  { key: 'stock',     label: 'Stocks',     icon: '📈', activeClass: 'bg-emerald-500 border-emerald-500', count: byType('stock').length },
  { key: 'etf',       label: 'ETFs',       icon: '🗂', activeClass: 'bg-sky-500 border-sky-500',       count: byType('etf').length },
  { key: 'bond',      label: 'Bonds',      icon: '🏛', activeClass: 'bg-rose-500 border-rose-500',     count: byType('bond').length },
  { key: 'commodity', label: 'Commodities',icon: '🛢', activeClass: 'bg-blue-500 border-blue-500',     count: byType('commodity').length },
  { key: 'fx',        label: 'FX',         icon: '💱', activeClass: 'bg-teal-500 border-teal-500',     count: byType('fx').length },
])

function showSection(type: string) {
  return activeTab.value === 'all' || activeTab.value === type
}

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

const indexFiltered     = computed(() => filtered.value.filter((a: any) => a.asset_type === 'index'))
const cryptoFiltered    = computed(() => filtered.value.filter((a: any) => a.asset_type === 'crypto'))
const stockFiltered     = computed(() => filtered.value.filter((a: any) => a.asset_type === 'stock'))
const etfFiltered       = computed(() => filtered.value.filter((a: any) => a.asset_type === 'etf'))
const bondFiltered      = computed(() => filtered.value.filter((a: any) => a.asset_type === 'bond'))
const commodityFiltered = computed(() => filtered.value.filter((a: any) => a.asset_type === 'commodity'))
const fxFiltered        = computed(() => filtered.value.filter((a: any) => a.asset_type === 'fx'))

const COMMODITY_GROUPS = [
  { name: 'Energy',      items: [
    { symbol: 'WTI', icon: '🛢️' }, { symbol: 'BRENT', icon: '🛢️' }, { symbol: 'NG', icon: '🔥' },
    { symbol: 'GASOLINE', icon: '⛽' }, { symbol: 'COAL', icon: '⚫' },
  ]},
  { name: 'Metals',      items: [
    { symbol: 'XAUUSD', icon: '🥇' }, { symbol: 'XAGUSD', icon: '🥈' }, { symbol: 'XPTUSD', icon: '⬜' },
    { symbol: 'HG', icon: '🟤' }, { symbol: 'ALI', icon: '⬛' }, { symbol: 'ZNC', icon: '🔩' }, { symbol: 'NI', icon: '🔩' },
  ]},
  { name: 'Agriculture', items: [
    { symbol: 'ZW', icon: '🌾' }, { symbol: 'ZC', icon: '🌽' }, { symbol: 'ZS', icon: '🟤' },
    { symbol: 'KC', icon: '☕' }, { symbol: 'SB', icon: '🍬' }, { symbol: 'CT', icon: '🌿' },
    { symbol: 'CC', icon: '🍫' }, { symbol: 'LE', icon: '🐄' }, { symbol: 'PALM', icon: '🌴' },
  ]},
]

const apiMap = computed(() => {
  const m: Record<string, any> = {}
  for (const a of (allAssets.value ?? [])) m[a.symbol] = a
  return m
})

const commodityGroups = computed(() =>
  COMMODITY_GROUPS.map(group => ({
    ...group,
    items: group.items.filter(item => commodityFiltered.value.some((a: any) => a.symbol === item.symbol)),
  }))
)

// ── Helpers ───────────────────────────────────────────────────────────────────

const CRYPTO_ICONS: Record<string, string> = {
  BTC: '₿', ETH: 'Ξ', BNB: '🟡', SOL: '◎', ADA: '₳',
  XRP: '✕', DOGE: '🐕', DOT: '●', AVAX: '🔺', LINK: '🔗',
}
function cryptoIcon(s: string) { return CRYPTO_ICONS[s] || '🪙' }

function regionIcon(region: string | null): string {
  const map: Record<string, string> = { US: '🇺🇸', Europe: '🇪🇺', Asia: '🌏', Global: '🌐' }
  return map[region ?? ''] ?? '📊'
}

function bondIcon(symbol: string): string {
  if (symbol.startsWith('US')) return '🇺🇸'
  if (symbol.startsWith('DE')) return '🇩🇪'
  if (symbol.startsWith('GB')) return '🇬🇧'
  if (symbol.startsWith('FR')) return '🇫🇷'
  if (symbol.startsWith('IT')) return '🇮🇹'
  if (symbol.startsWith('JP')) return '🇯🇵'
  return '🏛'
}

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

useSeoMeta({
  title: 'Markets — MetricsHour',
  description: 'Search crypto, stocks, ETFs, indices, bonds, commodities and FX. Real-time prices and global market data.',
})
</script>
