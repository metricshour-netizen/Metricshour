<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <NuxtLink to="/stocks" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
      ← Stocks
    </NuxtLink>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>
    <div v-else-if="error || !stock" class="text-red-400 text-sm">Stock not found.</div>

    <template v-else>
      <!-- Header -->
      <div class="flex items-start justify-between gap-4 mb-8 flex-wrap">
        <div class="flex items-start gap-3">
          <span v-if="stock.country" class="text-4xl leading-none mt-1">{{ stock.country.flag }}</span>
          <div>
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <h1 class="text-2xl font-bold text-white">{{ stock.symbol }}</h1>
              <span class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded">{{ stock.exchange }}</span>
              <span v-if="stock.sector" class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded">{{ stock.sector }}</span>
              <!-- Geographic Risk badge -->
              <span
                v-if="geoRisk"
                class="text-xs font-bold px-2 py-1 rounded"
                :class="{
                  'bg-red-900/50 text-red-400': geoRisk === 'HIGH',
                  'bg-yellow-900/50 text-yellow-400': geoRisk === 'MEDIUM',
                  'bg-emerald-900/50 text-emerald-400': geoRisk === 'LOW',
                }"
              >{{ geoRisk }} GEO RISK</span>
            </div>
            <p class="text-gray-400 text-sm">{{ stock.name }}</p>
            <p v-if="stock.country" class="text-gray-600 text-xs mt-0.5">
              HQ: {{ stock.country.name }}
            </p>
          </div>
        </div>

        <!-- Price block -->
        <div class="text-right">
          <div v-if="stock.price" class="text-2xl font-bold text-white tabular-nums">
            ${{ stock.price.close.toFixed(2) }}
          </div>
          <div v-else class="text-2xl font-bold text-gray-700">—</div>
          <div class="text-xs text-gray-600 mt-1">
            {{ stock.price ? 'Last close' : 'Price pending market connection' }}
          </div>
        </div>
      </div>

      <!-- Stats row -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Market Cap</div>
          <div class="text-white font-medium text-sm">{{ fmtCap(stock.market_cap_usd) }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Exchange</div>
          <div class="text-white font-medium text-sm">{{ stock.exchange || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Sector</div>
          <div class="text-white font-medium text-sm">{{ stock.sector || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Industry</div>
          <div class="text-white font-medium text-sm">{{ stock.industry || '—' }}</div>
        </div>
      </div>

      <!-- Geographic revenue — the core differentiator -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-6">
        <div class="flex items-start justify-between mb-4">
          <div>
            <h2 class="text-sm font-bold text-white mb-1">Geographic Revenue Exposure</h2>
            <p class="text-xs text-gray-500">
              Which countries {{ stock.symbol }} earns revenue from — sourced from SEC EDGAR 10-K filings.
            </p>
          </div>
          <div v-if="geoRisk" class="text-right shrink-0 ml-4">
            <div class="text-xs text-gray-500 mb-0.5">Concentration Risk</div>
            <span
              class="text-sm font-bold px-2 py-1 rounded"
              :class="{
                'bg-red-900/50 text-red-400': geoRisk === 'HIGH',
                'bg-yellow-900/50 text-yellow-400': geoRisk === 'MEDIUM',
                'bg-emerald-900/50 text-emerald-400': geoRisk === 'LOW',
              }"
            >{{ geoRisk }}</span>
            <div class="text-xs text-gray-600 mt-0.5">largest: {{ topCountryPct }}% in one market</div>
          </div>
        </div>

        <!-- Real revenue data -->
        <div v-if="stock.country_revenues?.length" class="space-y-3">
          <div
            v-for="r in stock.country_revenues"
            :key="r.country.code"
            class="flex items-center gap-3"
          >
            <NuxtLink
              :to="`/countries/${r.country.code.toLowerCase()}`"
              class="w-28 flex items-center gap-1.5 shrink-0 hover:text-emerald-400 transition-colors"
            >
              <span class="text-sm">{{ r.country.flag }}</span>
              <span class="text-xs text-gray-400 truncate">{{ r.country.name }}</span>
            </NuxtLink>
            <div class="flex-1 bg-[#1f2937] rounded-full h-2 overflow-hidden">
              <div
                class="bg-emerald-500 h-full rounded-full transition-all"
                :style="{ width: `${r.revenue_pct}%` }"
              />
            </div>
            <span class="text-xs text-white tabular-nums w-10 text-right shrink-0">
              {{ r.revenue_pct.toFixed(1) }}%
            </span>
          </div>
          <p class="text-xs text-gray-600 mt-2">
            Source: SEC EDGAR 10-K · FY{{ stock.country_revenues[0]?.fiscal_year }}
          </p>
        </div>

        <!-- Skeleton when no revenue data -->
        <div v-else class="space-y-3">
          <div v-for="(w, i) in [55, 22, 12, 6, 5]" :key="i" class="flex items-center gap-3">
            <div class="w-28 h-3 bg-[#1f2937] rounded animate-pulse shrink-0" />
            <div class="flex-1 bg-[#1f2937] rounded-full h-2 overflow-hidden">
              <div class="bg-[#374151] h-full rounded-full" :style="{ width: `${w}%` }" />
            </div>
            <div class="w-10 h-3 bg-[#1f2937] rounded animate-pulse shrink-0" />
          </div>
          <p class="text-xs text-gray-600 mt-2">SEC EDGAR data not yet available for this stock</p>
        </div>
      </div>

      <!-- HQ country macro link -->
      <div v-if="stock.country" class="bg-[#111827] border border-[#1f2937] rounded-lg p-5 mb-6">
        <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Country Context</h2>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-2xl">{{ stock.country.flag }}</span>
            <span class="text-sm text-white">{{ stock.country.name }}</span>
          </div>
          <NuxtLink
            :to="`/countries/${stock.country.code.toLowerCase()}`"
            class="text-xs text-emerald-500 hover:text-emerald-400 transition-colors"
          >
            View macro data →
          </NuxtLink>
        </div>
      </div>

      <!-- Related Stocks (same sector) -->
      <div v-if="stock.sector" class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-6">
        <h2 class="text-sm font-bold text-white mb-1">Related Stocks</h2>
        <p class="text-xs text-gray-500 mb-4">{{ stock.sector }} · sorted by market cap</p>
        <div v-if="relatedLoading" class="space-y-2">
          <div v-for="i in 4" :key="i" class="h-6 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="!relatedStocks?.length" class="text-gray-600 text-xs">No related stocks found</div>
        <div v-else class="space-y-2">
          <NuxtLink
            v-for="s in relatedStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol}`"
            class="flex items-center justify-between py-2 px-3 rounded hover:bg-[#1f2937] transition-colors"
          >
            <div class="flex items-center gap-2">
              <span class="text-sm">{{ s.country?.flag }}</span>
              <span class="text-xs font-mono font-bold text-emerald-400">{{ s.symbol }}</span>
              <span class="text-xs text-gray-400 truncate">{{ s.name }}</span>
            </div>
            <span class="text-xs text-gray-500 shrink-0">{{ fmtCap(s.market_cap_usd) }}</span>
          </NuxtLink>
        </div>
      </div>

      <!-- Price history placeholder -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-bold text-white">Price History</h2>
          <span v-if="!stock.price" class="text-xs text-yellow-400">Pending market data connection</span>
        </div>
        <div class="h-40 border border-[#1f2937] rounded flex items-center justify-center">
          <span class="text-gray-700 text-xs">Chart available once price feed is connected</span>
        </div>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()

const ticker = (route.params.ticker as string).toUpperCase()

const { data: stock, pending, error } = await useAsyncData(
  `stock-${ticker}`,
  () => get<any>(`/api/assets/${ticker}`),
)

// Related stocks (same sector, lazy)
const { data: sectorStocks, pending: relatedLoading } = useAsyncData(
  `related-${ticker}`,
  async () => {
    if (!stock.value?.sector) return []
    return get<any[]>('/api/assets', { type: 'stock', sector: stock.value.sector })
  },
  { watch: [() => stock.value?.sector] },
)

const relatedStocks = computed(() =>
  (sectorStocks.value ?? [])
    .filter((s: any) => s.symbol !== ticker)
    .slice(0, 6),
)

// Geographic risk: HIGH if any single market > 40%, MEDIUM if > 20%, else LOW
const topCountryPct = computed(() => {
  const revs = stock.value?.country_revenues ?? []
  if (!revs.length) return 0
  return Math.max(...revs.map((r: any) => r.revenue_pct))
})

const geoRisk = computed(() => {
  if (!stock.value?.country_revenues?.length) return null
  const top = topCountryPct.value
  if (top > 40) return 'HIGH'
  if (top > 20) return 'MEDIUM'
  return 'LOW'
})

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

useSeoMeta({
  title: computed(() =>
    stock.value
      ? `${stock.value.symbol} — ${stock.value.name} — MetricsHour`
      : `${ticker} Stock — MetricsHour`,
  ),
  description: computed(() =>
    stock.value
      ? `${stock.value.name} (${stock.value.symbol}) geographic revenue breakdown from SEC EDGAR. See which countries drive ${stock.value.symbol} earnings.`
      : '',
  ),
})
</script>
