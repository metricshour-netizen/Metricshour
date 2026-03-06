<template>
  <div>
    <!-- Hero band -->
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/stocks" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Stocks
        </NuxtLink>

        <div v-if="pending" class="h-20 flex items-center">
          <div class="space-y-2">
            <div class="h-8 w-40 bg-[#1f2937] rounded animate-pulse"/>
            <div class="h-4 w-64 bg-[#1f2937] rounded animate-pulse"/>
          </div>
        </div>
        <div v-else-if="error || !stock" class="text-red-400 text-sm py-6">Stock not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <!-- Left: identity -->
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-2xl shrink-0">
                {{ stock.country?.flag || '🏢' }}
              </div>
              <div>
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h1 class="text-3xl font-extrabold text-white tracking-tight">{{ stock.symbol }}</h1>
                  <span class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded-md">{{ stock.exchange }}</span>
                  <span v-if="stock.sector" class="text-xs border border-emerald-800 text-emerald-400 px-2 py-1 rounded-md">{{ stock.sector }}</span>
                  <span v-if="geoRisk" class="text-xs font-bold px-2 py-1 rounded-md"
                    :class="{
                      'bg-red-900/40 text-red-400 border border-red-800': geoRisk === 'HIGH',
                      'bg-yellow-900/40 text-yellow-400 border border-yellow-800': geoRisk === 'MEDIUM',
                      'bg-emerald-900/40 text-emerald-400 border border-emerald-800': geoRisk === 'LOW',
                    }">{{ geoRisk }} GEO RISK</span>
                </div>
                <p class="text-gray-300 font-medium">{{ stock.name }}</p>
                <p v-if="stock.country" class="text-gray-600 text-xs mt-0.5">{{ stock.country.name }} · {{ stock.industry || stock.sector }}</p>
              </div>
            </div>

            <!-- Right: price + follow -->
            <div class="flex items-start gap-4">
              <div class="text-right">
                <div class="text-4xl font-extrabold text-white tabular-nums tracking-tight">
                  {{ stock.price ? `$${stock.price.close.toFixed(2)}` : '—' }}
                </div>
                <div class="text-xs text-gray-600 mt-1">
                  <template v-if="stock.price">Last close · <span class="font-mono text-emerald-700">{{ fmtPriceTs(stock.price.timestamp) }}</span></template>
                  <template v-else>Awaiting price feed</template>
                </div>
                <div class="text-sm font-semibold text-gray-400 mt-1">{{ fmtCap(stock.market_cap_usd) }} market cap</div>
              </div>
              <button
                class="mt-1 flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-lg border transition-colors"
                :class="isFollowing
                  ? 'border-emerald-700 text-emerald-400 bg-emerald-900/20 hover:bg-red-900/20 hover:text-red-400 hover:border-red-700'
                  : 'border-[#374151] text-gray-400 hover:border-emerald-600 hover:text-emerald-400'"
                @click="toggleFollow"
              >{{ isFollowing ? '★ Following' : '☆ Follow' }}</button>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-8" v-if="stock">

      <!-- Stats row -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Market Cap</div>
          <div class="text-white font-bold text-lg">{{ fmtCap(stock.market_cap_usd) }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Exchange</div>
          <div class="text-white font-bold text-lg">{{ stock.exchange || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Sector</div>
          <div class="text-white font-bold text-sm leading-snug mt-1">{{ stock.sector || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Geo Markets</div>
          <div class="text-white font-bold text-lg">{{ stock.country_revenues?.length || '—' }}</div>
          <div class="text-[10px] text-gray-600 mt-0.5">countries tracked</div>
        </div>
      </div>

      <!-- Page Summary -->
      <div v-if="pageSummary?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-6 text-sm text-gray-300 leading-relaxed">
        {{ pageSummary.summary }}
      </div>

      <!-- Geographic Revenue — core differentiator -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <div class="flex items-start justify-between mb-5 flex-wrap gap-3">
          <div>
            <h2 class="text-base font-bold text-white mb-1">Geographic Revenue Exposure</h2>
            <p class="text-xs text-gray-500">Where {{ stock.symbol }} earns its revenue — SEC EDGAR 10-K filings</p>
          </div>
          <div v-if="geoRisk" class="text-right">
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Concentration Risk</div>
            <span class="text-sm font-bold px-3 py-1.5 rounded-lg"
              :class="{
                'bg-red-900/40 text-red-400 border border-red-800': geoRisk === 'HIGH',
                'bg-yellow-900/40 text-yellow-400 border border-yellow-800': geoRisk === 'MEDIUM',
                'bg-emerald-900/40 text-emerald-400 border border-emerald-800': geoRisk === 'LOW',
              }">{{ geoRisk }}</span>
            <div class="text-[10px] text-gray-600 mt-1">{{ topCountryPct }}% in largest market</div>
          </div>
        </div>

        <div v-if="stock.country_revenues?.length" class="space-y-3.5">
          <div v-for="(r, i) in stock.country_revenues" :key="r.country.code" class="flex items-center gap-3">
            <NuxtLink
              :to="`/countries/${r.country.code.toLowerCase()}`"
              class="w-32 sm:w-44 flex items-center gap-2 shrink-0 min-w-0 group"
            >
              <span class="text-base shrink-0">{{ r.country.flag }}</span>
              <span class="text-xs text-gray-300 group-hover:text-emerald-400 truncate flex-1 transition-colors">{{ r.country.name }}</span>
            </NuxtLink>
            <div class="flex-1 bg-[#1f2937] rounded-full h-3 overflow-hidden">
              <div
                class="h-full rounded-full transition-all"
                :class="i === 0 ? 'bg-emerald-400' : i === 1 ? 'bg-emerald-500' : i === 2 ? 'bg-emerald-600' : 'bg-[#374151]'"
                :style="{ width: `${r.revenue_pct}%` }"
              />
            </div>
            <span class="text-sm font-bold text-white tabular-nums w-12 text-right shrink-0">
              {{ r.revenue_pct.toFixed(1) }}%
            </span>
            <NuxtLink
              :to="`/countries/${r.country.code.toLowerCase()}`"
              class="shrink-0 text-[10px] font-semibold text-emerald-600 hover:text-emerald-400 border border-emerald-900 hover:border-emerald-600 px-2 py-1 rounded transition-colors whitespace-nowrap hidden sm:inline-flex items-center gap-0.5"
            >
              View country →
            </NuxtLink>
          </div>
          <!-- Mobile: tap country name to go to dashboard -->
          <p class="text-[10px] text-gray-600 sm:hidden mt-1">Tap a country name to view its macro dashboard</p>
          <p class="text-xs text-gray-600 mt-3 pt-3 border-t border-[#1f2937]">
            Source: SEC EDGAR 10-K · FY{{ stock.country_revenues[0]?.fiscal_year }}
          </p>
        </div>

        <div v-else class="space-y-3.5">
          <div v-for="(w, i) in [55, 22, 12, 6, 5]" :key="i" class="flex items-center gap-3">
            <div class="w-32 sm:w-40 h-4 bg-[#1f2937] rounded animate-pulse shrink-0" />
            <div class="flex-1 bg-[#1f2937] rounded-full h-3 overflow-hidden">
              <div class="bg-[#374151] h-full rounded-full" :style="{ width: `${w}%` }" />
            </div>
            <div class="w-12 h-4 bg-[#1f2937] rounded animate-pulse shrink-0" />
          </div>
          <p class="text-xs text-gray-600 mt-3">SEC EDGAR data pending for this stock</p>
        </div>
      </div>

      <!-- Price Chart — full width above the 2-col grid -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6">
        <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 class="text-base font-bold text-white">Price Chart</h2>
          <div class="flex items-center gap-1.5">
            <button
              v-for="p in pricePeriods"
              :key="p.key"
              @click="activePeriod = p.key"
              class="text-xs px-2.5 py-1 rounded transition-colors font-medium"
              :class="activePeriod === p.key
                ? 'bg-emerald-600 text-white'
                : 'text-gray-500 hover:text-gray-300'"
            >{{ p.label }}</button>
          </div>
        </div>

        <div v-if="pricesPending" class="h-48 bg-[#0d1117] rounded-lg animate-pulse" />
        <div v-else-if="!visiblePrices.length" class="h-48 rounded-lg bg-[#0d1117] flex flex-col items-center justify-center gap-2">
          <span class="text-gray-700 text-2xl">📈</span>
          <span class="text-gray-600 text-xs">Price feed warming up — check back shortly</span>
        </div>
        <EChartLine v-else :option="priceChartOption" height="200px" />

        <div v-if="visiblePrices.length" class="flex items-center justify-between mt-2">
          <span class="text-[10px] text-gray-600">{{ priceRangeLabel }}</span>
          <span class="text-[10px] text-gray-600">{{ visiblePrices.length }} candles · 15m interval</span>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Country Context -->
        <div v-if="stock.country" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6">
          <h2 class="text-base font-bold text-white mb-4">HQ Country Context</h2>
          <div class="flex items-center gap-3 mb-4 p-3 rounded-lg bg-[#0d1117] border border-[#1f2937]">
            <span class="text-3xl">{{ stock.country.flag }}</span>
            <div>
              <div class="text-white font-semibold">{{ stock.country.name }}</div>
              <div class="text-xs text-gray-500">Headquarters country</div>
            </div>
            <NuxtLink
              :to="`/countries/${stock.country.code.toLowerCase()}`"
              class="ml-auto text-xs text-emerald-500 hover:text-emerald-400 transition-colors font-semibold"
            >View macro →</NuxtLink>
          </div>
          <div v-if="stock.country.indicators" class="grid grid-cols-2 gap-3">
            <div class="bg-[#0d1117] rounded-lg p-3">
              <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">GDP</div>
              <div class="text-sm font-bold text-white">{{ fmtGdp(stock.country.indicators?.gdp_usd) }}</div>
            </div>
            <div class="bg-[#0d1117] rounded-lg p-3">
              <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">GDP Growth</div>
              <div class="text-sm font-bold" :class="(stock.country.indicators?.gdp_growth_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ stock.country.indicators?.gdp_growth_pct?.toFixed(1) ?? '—' }}%
              </div>
            </div>
            <div class="bg-[#0d1117] rounded-lg p-3">
              <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Inflation</div>
              <div class="text-sm font-bold text-white">{{ stock.country.indicators?.inflation_pct?.toFixed(1) ?? '—' }}%</div>
            </div>
            <div class="bg-[#0d1117] rounded-lg p-3">
              <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Interest Rate</div>
              <div class="text-sm font-bold text-white">{{ stock.country.indicators?.interest_rate_pct?.toFixed(2) ?? '—' }}%</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Related Trade Flows — internal linking moat -->
      <div v-if="tradeFlowLinks.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-1">Trade Flows Impacting {{ stock.symbol }}</h2>
        <p class="text-xs text-gray-500 mb-4">
          Bilateral trade between {{ stock.country?.name }} and {{ stock.symbol }}'s key revenue markets
        </p>
        <div class="flex flex-wrap gap-2">
          <NuxtLink
            v-for="r in tradeFlowLinks"
            :key="r.pair"
            :to="`/trade/${r.pair}`"
            class="flex items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-700 rounded-lg px-3 py-2 transition-colors group"
          >
            <span class="text-base leading-none">{{ stock.country?.flag }}</span>
            <span class="text-[10px] text-gray-600 font-mono">↔</span>
            <span class="text-base leading-none">{{ r.flag }}</span>
            <div>
              <div class="text-xs font-semibold text-white group-hover:text-emerald-400 transition-colors">
                {{ stock.country?.code }} – {{ r.code }}
              </div>
              <div class="text-[9px] text-gray-600">{{ r.revPct.toFixed(0) }}% revenue</div>
            </div>
            <span class="text-emerald-800 text-xs ml-1 group-hover:text-emerald-500 transition-colors">→</span>
          </NuxtLink>
        </div>
      </div>

      <!-- Related Stocks -->
      <div v-if="stock.sector" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-bold text-white">Related Stocks</h2>
          <span class="text-xs text-gray-500 bg-[#1f2937] px-2 py-1 rounded">{{ stock.sector }}</span>
        </div>
        <div v-if="relatedLoading" class="space-y-2">
          <div v-for="i in 4" :key="i" class="h-10 bg-[#1f2937] rounded-lg animate-pulse"/>
        </div>
        <div v-else-if="!relatedStocks?.length" class="text-gray-600 text-xs">No related stocks found</div>
        <div v-else class="divide-y divide-[#1f2937]">
          <NuxtLink
            v-for="s in relatedStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol}`"
            class="flex items-center justify-between py-3 hover:bg-[#1f2937] -mx-2 px-2 rounded-lg transition-colors"
          >
            <div class="flex items-center gap-3">
              <span class="text-lg leading-none">{{ s.country?.flag || '🏢' }}</span>
              <div>
                <div class="text-sm font-bold text-emerald-400">{{ s.symbol }}</div>
                <div class="text-xs text-gray-500 truncate max-w-[180px]">{{ s.name }}</div>
              </div>
            </div>
            <span class="text-sm font-semibold text-white tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
          </NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center">Data: SEC EDGAR · World Bank · REST Countries</p>
    </main>
  </div>
  <AuthModal v-model="showAuthModal" />
</template>

<script setup lang="ts">
const route = useRoute()
const { get, post, del } = useApi()
const { isLoggedIn } = useAuth()

const ticker = (route.params.ticker as string).toUpperCase()

const { data: stock, pending, error } = useAsyncData(
  `stock-${ticker}`,
  () => get<any>(`/api/assets/${ticker}`).catch(() => null),
)

const { data: pageSummary } = useAsyncData(
  `summary-stock-${ticker}`,
  () => get<any>(`/api/summaries/stock/${ticker}`).catch(() => null),
  { server: false },
)

// ─── Price chart ──────────────────────────────────────────────────────────────

const pricePeriods = [
  { key: '1D', label: '1D', hours: 8 },
  { key: '3D', label: '3D', hours: 72 },
  { key: 'ALL', label: 'All', hours: 0 },
]
const activePeriod = ref('ALL')

const { data: pricesRaw, pending: pricesPending } = useAsyncData(
  `prices-${ticker}`,
  () => get<any[]>(`/api/assets/${ticker}/prices`, { interval: '15m', limit: 500 }).catch(() => []),
  { server: false },
)

const visiblePrices = computed(() => {
  const all = pricesRaw.value ?? []
  const period = pricePeriods.find(p => p.key === activePeriod.value)
  if (!period || period.hours === 0) return all
  const cutoff = Date.now() - period.hours * 3600 * 1000
  return all.filter((p: any) => new Date(p.t).getTime() >= cutoff)
})

const priceChartOption = computed(() => {
  const data = visiblePrices.value
  if (!data.length) return {}

  const times = data.map((p: any) => {
    const d = new Date(p.t)
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  })
  const closes = data.map((p: any) => p.c)
  const first = closes[0]
  const last = closes[closes.length - 1]
  const isUp = last >= first
  const lineColor = isUp ? '#10b981' : '#f87171'
  const areaColor = isUp ? 'rgba(16,185,129,0.08)' : 'rgba(248,113,113,0.08)'

  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 12, bottom: 28, left: 52, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1117',
      borderColor: '#1f2937',
      borderWidth: 1,
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      formatter: (params: any[]) => {
        const p = params[0]
        const raw = data[p.dataIndex]
        const lines = [`<b>${p.name}</b>`]
        lines.push(`Close: <b style="color:${lineColor}">$${raw.c?.toFixed(2)}</b>`)
        if (raw.o != null) lines.push(`Open: $${raw.o?.toFixed(2)}`)
        if (raw.h != null) lines.push(`High: $${raw.h?.toFixed(2)} · Low: $${raw.l?.toFixed(2)}`)
        return lines.join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLine: { lineStyle: { color: '#1f2937' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#4b5563',
        fontSize: 10,
        interval: Math.max(0, Math.floor(times.length / 6) - 1),
      },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: {
        color: '#4b5563',
        fontSize: 10,
        formatter: (v: number) => `$${v.toFixed(0)}`,
      },
    },
    series: [{
      type: 'line',
      data: closes,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: lineColor, width: 2 },
      areaStyle: { color: areaColor },
    }],
  }
})

const priceRangeLabel = computed(() => {
  const data = visiblePrices.value
  if (!data.length) return ''
  const from = new Date(data[0].t)
  const to = new Date(data[data.length - 1].t)
  return `${from.toLocaleDateString()} → ${to.toLocaleDateString()}`
})

const { data: sectorStocks, pending: relatedLoading } = useAsyncData(
  `related-${ticker}`,
  async () => {
    if (!stock.value?.sector) return []
    return get<any[]>('/api/assets', { type: 'stock', sector: stock.value.sector })
  },
  { watch: [() => stock.value?.sector] },
)

const relatedStocks = computed(() =>
  (sectorStocks.value ?? []).filter((s: any) => s.symbol !== ticker).slice(0, 6),
)

// Trade flow links — link to bilateral trade pages for top revenue countries
const tradeFlowLinks = computed(() => {
  if (!stock.value?.country || !stock.value.country_revenues?.length) return []
  const hqCode = stock.value.country.code.toLowerCase()
  return (stock.value.country_revenues as any[])
    .filter((r: any) => r.country.code.toLowerCase() !== hqCode)
    .slice(0, 5)
    .map((r: any) => ({
      pair: `${hqCode}-${r.country.code.toLowerCase()}`,
      code: r.country.code,
      flag: r.country.flag,
      name: r.country.name,
      revPct: r.revenue_pct,
    }))
})

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

function fmtPriceTs(ts: string | undefined): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
    + ' · ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC'
}

function fmtGdp(v: number | null | undefined): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

const showAuthModal = ref(false)
const isFollowing = ref(false)

onMounted(async () => {
  if (!isLoggedIn.value || !stock.value?.id) return
  try {
    const follows = await get<any[]>('/api/feed/follows')
    isFollowing.value = follows.some((f: any) => f.entity_type === 'asset' && f.entity_id === stock.value!.id)
  } catch { /* ignore */ }
})

async function toggleFollow() {
  if (!isLoggedIn.value) { showAuthModal.value = true; return }
  if (!stock.value?.id) return
  try {
    if (isFollowing.value) {
      await del(`/api/feed/follows/asset/${stock.value.id}`)
      isFollowing.value = false
    } else {
      await post('/api/feed/follows', { entity_type: 'asset', entity_id: stock.value.id })
      isFollowing.value = true
    }
  } catch { /* ignore */ }
}

const { public: { r2PublicUrl } } = useRuntimeConfig()
const ogImageUrl = computed(() =>
  r2PublicUrl
    ? `${r2PublicUrl}/og/stocks/${ticker.toLowerCase()}.png`
    : 'https://metricshour.com/og-image.png',
)

useSeoMeta({
  title: computed(() => stock.value ? `${stock.value.symbol} — ${stock.value.name} — MetricsHour` : `${ticker} Stock — MetricsHour`),
  description: computed(() => stock.value ? `${stock.value.name} (${stock.value.symbol}) geographic revenue breakdown from SEC EDGAR. See which countries drive ${stock.value.symbol} earnings.` : ''),
  ogTitle: computed(() => stock.value ? `${stock.value.symbol} — ${stock.value.name} — MetricsHour` : `${ticker} Stock — MetricsHour`),
  ogDescription: computed(() => stock.value ? `${stock.value.name} (${stock.value.symbol}) geographic revenue breakdown from SEC EDGAR. See which countries drive ${stock.value.symbol} earnings.` : ''),
  ogUrl: `https://metricshour.com/stocks/${ticker}`,
  ogType: 'website',
  ogImage: ogImageUrl,
  twitterTitle: computed(() => stock.value ? `${stock.value.symbol} — ${stock.value.name} — MetricsHour` : `${ticker} Stock — MetricsHour`),
  twitterDescription: computed(() => stock.value ? `${stock.value.name} (${stock.value.symbol}) geographic revenue breakdown from SEC EDGAR. See which countries drive ${stock.value.symbol} earnings.` : ''),
  twitterImage: ogImageUrl,
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/stocks/${ticker}` }],
  script: stock.value ? [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: `${stock.value.symbol} — ${stock.value.name} — MetricsHour`,
      url: `https://metricshour.com/stocks/${ticker}`,
      description: `${stock.value.name} (${stock.value.symbol}) geographic revenue breakdown from SEC EDGAR.`,
      breadcrumb: {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
          { '@type': 'ListItem', position: 2, name: 'Stocks', item: 'https://metricshour.com/stocks' },
          { '@type': 'ListItem', position: 3, name: stock.value.symbol, item: `https://metricshour.com/stocks/${ticker}` },
        ],
      },
    }),
  }] : [],
})))
</script>
