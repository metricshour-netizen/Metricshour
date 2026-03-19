<template>
  <main class="max-w-4xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white">Watchlist</h1>
      <p class="text-gray-500 text-sm mt-1">Countries and assets you follow</p>
    </div>

    <!-- Not logged in -->
    <div v-if="!isLoggedIn" class="bg-[#111827] border border-[#1f2937] rounded-xl p-10 text-center">
      <div class="text-4xl mb-3">⭐</div>
      <p class="text-white font-semibold mb-1">Sign in to see your watchlist</p>
      <p class="text-gray-500 text-sm mb-4">Follow countries and stocks to track them here.</p>
      <button @click="showAuth = true" class="bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm px-6 py-2.5 rounded-lg transition-colors">Sign In / Register</button>
    </div>

    <template v-else>
      <div v-if="pending" class="space-y-3">
        <div v-for="i in 4" :key="i" class="h-16 bg-[#111827] rounded-lg animate-pulse" />
      </div>

      <div v-else-if="!watchlist?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-10 text-center">
        <div class="text-4xl mb-3">⭐</div>
        <p class="text-white font-semibold mb-1">Your watchlist is empty</p>
        <p class="text-gray-500 text-sm mb-4">Follow countries and stocks from their detail pages.</p>
        <div class="flex gap-3 justify-center">
          <NuxtLink to="/countries/" class="text-sm text-emerald-400 hover:text-emerald-300 transition-colors">Browse Countries →</NuxtLink>
          <NuxtLink to="/stocks/" class="text-sm text-emerald-400 hover:text-emerald-300 transition-colors">Browse Stocks →</NuxtLink>
        </div>
      </div>

      <template v-else>
        <!-- Stocks section -->
        <div v-if="stocks.length" class="mb-8">
          <h2 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Stocks & Assets</h2>
          <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
            <div class="hidden sm:grid px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide"
                 style="grid-template-columns: 1fr 7rem 6rem 6rem 1.5rem">
              <span>Asset</span>
              <span>Sector</span>
              <span class="text-right">Price</span>
              <span class="text-right">Mkt Cap</span>
              <span></span>
            </div>
            <div class="divide-y divide-[#1f2937]">
              <div v-for="item in stocks" :key="item.follow_id" class="flex items-center justify-between sm:grid px-4 py-3 hover:bg-[#1a2235] transition-colors"
                   style="grid-template-columns: 1fr 7rem 6rem 6rem 1.5rem">
                <NuxtLink :to="assetLink(item)" class="flex items-center gap-2 min-w-0 pr-2 group">
                  <div class="min-w-0">
                    <div class="text-sm font-bold text-white group-hover:text-emerald-400 transition-colors">{{ item.symbol }}</div>
                    <div class="text-xs text-gray-500 truncate">{{ item.name }}</div>
                  </div>
                </NuxtLink>
                <span class="text-xs text-gray-500 truncate hidden sm:block pr-2">{{ item.sector || '—' }}</span>
                <div class="text-right shrink-0 ml-2 sm:ml-0">
                  <div class="text-sm font-bold tabular-nums font-mono text-white">{{ item.price ? fmtPrice(item.price.close) : '—' }}</div>
                  <div v-if="item.price?.timestamp" class="text-[10px] text-emerald-500 tabular-nums font-mono mt-0.5">{{ fmtAge(item.price.timestamp) }}</div>
                </div>
                <span class="text-xs text-right text-gray-400 tabular-nums hidden sm:block">{{ fmtCap(item.market_cap_usd) }}</span>
                <button @click="unfollow('asset', item.entity_id)" class="text-gray-700 hover:text-red-400 transition-colors text-xs hidden sm:block" title="Unfollow">✕</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Countries section -->
        <div v-if="countries.length">
          <h2 class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3">Countries</h2>
          <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
            <div class="hidden sm:grid px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide"
                 style="grid-template-columns: 1fr 6rem 6rem 6rem 1.5rem">
              <span>Country</span>
              <span class="text-right">GDP</span>
              <span class="text-right">Growth</span>
              <span class="text-right">Inflation</span>
              <span></span>
            </div>
            <div class="divide-y divide-[#1f2937]">
              <div v-for="item in countries" :key="item.follow_id" class="flex items-center justify-between sm:grid px-4 py-3 hover:bg-[#1a2235] transition-colors"
                   style="grid-template-columns: 1fr 6rem 6rem 6rem 1.5rem">
                <NuxtLink :to="`/countries/${item.code.toLowerCase()}`" class="flex items-center gap-2.5 min-w-0 pr-2 group">
                  <span class="text-xl shrink-0" aria-hidden="true">{{ item.flag }}</span>
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-white group-hover:text-emerald-400 transition-colors">{{ item.name }}</div>
                    <div class="text-xs text-gray-600">{{ item.region }}</div>
                  </div>
                </NuxtLink>
                <span class="text-xs text-right text-gray-300 tabular-nums hidden sm:block">{{ fmtGdp(item.indicators?.gdp_usd) }}</span>
                <span class="text-xs text-right tabular-nums hidden sm:block"
                      :class="(item.indicators?.gdp_growth_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ item.indicators?.gdp_growth_pct != null ? `${item.indicators.gdp_growth_pct.toFixed(1)}%` : '—' }}
                </span>
                <span class="text-xs text-right text-gray-300 tabular-nums hidden sm:block">
                  {{ item.indicators?.inflation_pct != null ? `${item.indicators.inflation_pct.toFixed(1)}%` : '—' }}
                </span>
                <button @click="unfollow('country', item.entity_id)" class="text-gray-700 hover:text-red-400 transition-colors text-xs hidden sm:block" title="Unfollow">✕</button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <AuthModal v-model="showAuth" />
  </main>
</template>

<script setup lang="ts">
const { isLoggedIn } = useAuth()
const { get, del } = useApi()
const showAuth = ref(false)

const { data: watchlist, pending, refresh } = useAsyncData(
  'watchlist',
  () => isLoggedIn.value ? get<any[]>('/api/feed/watchlist').catch(() => []) : Promise.resolve([]),
  { server: false },
)

const stocks = computed(() => (watchlist.value ?? []).filter((i: any) => i.entity_type === 'asset'))
const countries = computed(() => (watchlist.value ?? []).filter((i: any) => i.entity_type === 'country'))

async function unfollow(type: string, id: number) {
  try {
    await del(`/api/feed/follows/${type}/${id}`)
    await refresh()
  } catch { /* ignore */ }
}

function assetLink(item: any): string {
  const sym = item.symbol?.toLowerCase()
  if (item.asset_type === 'commodity') return `/commodities/${sym}`
  if (item.asset_type === 'index') return `/indices/${sym}`
  return `/stocks/${sym}`
}

function fmtPrice(v: number): string {
  if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  if (v >= 1) return `$${v.toFixed(2)}`
  return `$${v.toFixed(4)}`
}

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtGdp(v: number | null | undefined): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  return `$${(v / 1e6).toFixed(0)}M`
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

useSeoMeta({
  title: 'Watchlist — MetricsHour',
  description: 'Your followed countries and assets — track prices and macro indicators in one place.',
  robots: 'noindex, nofollow',
})
useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/watchlist/' }],
})
</script>
