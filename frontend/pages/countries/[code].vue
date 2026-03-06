<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <NuxtLink to="/countries" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
      ← Countries
    </NuxtLink>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>
    <div v-else-if="error" class="text-red-400 text-sm">Country not found.</div>

    <template v-else-if="country">
      <!-- Header -->
      <div class="mb-8">
        <div class="flex items-start gap-4 mb-3">
          <span class="text-5xl leading-none">{{ country.flag }}</span>
          <div>
            <h1 class="text-2xl font-bold text-white">{{ country.name }}</h1>
            <p class="text-gray-500 text-sm">{{ country.name_official }}</p>
            <p class="text-gray-500 text-sm">{{ country.region }} · {{ country.subregion }}</p>
          </div>
        </div>
        <!-- Hero stats -->
        <div class="flex gap-6 mt-4 flex-wrap">
          <div>
            <span class="text-xs text-gray-500 block">GDP</span>
            <span class="text-lg font-bold text-white">{{ fmt('gdp_usd', country.indicators?.gdp_usd) }}</span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block">Population</span>
            <span class="text-lg font-bold text-white">{{ fmt('population', country.indicators?.population) }}</span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block">GDP Growth</span>
            <span class="text-lg font-bold" :class="(country.indicators?.gdp_growth_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
              {{ fmt('gdp_growth_pct', country.indicators?.gdp_growth_pct) }}
            </span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block">Inflation</span>
            <span class="text-lg font-bold text-white">{{ fmt('inflation_pct', country.indicators?.inflation_pct) }}</span>
          </div>
        </div>
        <div class="flex items-center gap-3 mt-3 flex-wrap">
          <div class="flex gap-2 flex-wrap">
            <span
              v-for="g in country.groupings"
              :key="g"
              class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded"
            >{{ g }}</span>
          </div>
          <!-- Follow button -->
          <button
            class="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors"
            :class="isFollowing
              ? 'border-emerald-700 text-emerald-400 bg-emerald-900/20 hover:bg-red-900/20 hover:text-red-400 hover:border-red-700'
              : 'border-[#1f2937] text-gray-400 hover:border-emerald-700 hover:text-emerald-400'"
            @click="toggleFollow"
          >
            {{ isFollowing ? '★ Following' : '☆ Follow' }}
          </button>
        </div>
      </div>

      <!-- Page Summary -->
      <div v-if="pageSummary?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-3 text-sm text-gray-400 leading-relaxed">
        {{ pageSummary.summary }}
      </div>

      <!-- Daily Insight -->
      <div v-if="pageInsight?.summary" class="relative bg-[#0d1520] border border-emerald-900/50 rounded-lg p-4 mb-6 overflow-hidden">
        <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"/>
        <div class="flex items-start gap-3">
          <span class="text-emerald-500 text-base mt-0.5 shrink-0">◆</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1.5 flex-wrap">
              <span class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest">MetricsHour Intelligence</span>
              <span class="text-[10px] text-gray-600">· Daily analyst take</span>
              <span v-if="pageInsight.generated_at" class="text-[10px] text-gray-700 ml-auto">
                {{ new Date(pageInsight.generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}
              </span>
            </div>
            <p class="text-sm text-gray-200 leading-relaxed">{{ pageInsight.summary }}</p>
          </div>
        </div>
      </div>

      <!-- Quick facts -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Capital</div>
          <div class="text-white font-medium text-sm">{{ country.capital || 'N/A' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Currency</div>
          <div class="text-white font-medium text-sm">{{ country.currency_code }} {{ country.currency_symbol }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">S&P Rating</div>
          <div class="text-white font-medium text-sm">{{ country.credit_rating_sp || 'N/A' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Income Level</div>
          <div class="text-white font-medium text-sm capitalize">
            {{ country.income_level?.replace(/_/g, ' ') || 'N/A' }}
          </div>
        </div>
      </div>

      <!-- Key indicators — 6 card grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        <div v-for="kpi in keyIndicators" :key="kpi.label" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">{{ kpi.label }}</div>
          <div class="text-white font-semibold text-sm">{{ kpi.value }}</div>
        </div>
      </div>

      <!-- GDP Chart -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5 mb-4">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-bold text-white">GDP History</h2>
          <span v-if="gdpHistory?.length" class="text-xs text-emerald-400 font-medium tabular-nums">
            {{ fmt('gdp_usd', gdpHistory[gdpHistory.length - 1]?.gdp) }}
          </span>
        </div>
        <div v-if="!gdpHistory?.length" class="h-36 flex items-center justify-center text-gray-600 text-xs">
          No GDP history data available
        </div>
        <EChartLine v-else :option="gdpChartOption" height="160px" />
      </div>

      <!-- Macro indicators chart -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5 mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-bold text-white">Key Indicators Over Time</h2>
          <span class="text-[10px] text-gray-600">World Bank · 2015–2024</span>
        </div>
        <div v-if="timeseriesLoading" class="h-44 bg-[#0d1117] rounded-lg animate-pulse" />
        <div v-else-if="!hasTimeseries" class="h-44 flex items-center justify-center text-gray-600 text-xs">
          Indicator history not available
        </div>
        <EChartLine v-else :option="macroChartOption" height="176px" />
      </div>

      <!-- Macro indicators -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <IndicatorSection title="Economy" :rows="economyRows" />
        <IndicatorSection title="Monetary" :rows="monetaryRows" />
        <IndicatorSection title="Trade" :rows="tradeRows" />
        <IndicatorSection title="Fiscal" :rows="fiscalRows" />
        <IndicatorSection title="Social" :rows="socialRows" />
        <IndicatorSection title="Governance" :rows="governanceRows" />
      </div>

      <!-- Trade Partners -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-6">
        <h2 class="text-sm font-bold text-white mb-4">Top Trade Partners</h2>
        <div v-if="tradePartnersLoading" class="space-y-2">
          <div v-for="i in 5" :key="i" class="h-6 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="!tradePartners?.length" class="text-gray-600 text-xs">No trade data available</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-gray-500 border-b border-[#1f2937]">
                <th class="text-left py-2 font-medium">Partner</th>
                <th class="text-right py-2 font-medium">Exports</th>
                <th class="text-right py-2 font-medium">Imports</th>
                <th class="text-right py-2 font-medium">Balance</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in tradePartners"
                :key="p.partner.code"
                class="border-b border-[#1f2937] hover:bg-[#1f2937] transition-colors"
              >
                <td class="py-2.5">
                  <div class="flex items-center gap-2 flex-wrap">
                    <NuxtLink
                      :to="`/trade/${code.toUpperCase()}-${p.partner.code}`"
                      class="flex items-center gap-2 hover:text-emerald-400 transition-colors"
                    >
                      <span>{{ p.partner.flag }}</span>
                      <span class="text-white">{{ p.partner.name }}</span>
                    </NuxtLink>
                    <NuxtLink
                      :to="`/countries/${p.partner.code.toLowerCase()}`"
                      class="text-[10px] text-gray-600 hover:text-emerald-400 transition-colors whitespace-nowrap hidden sm:inline"
                    >macro →</NuxtLink>
                  </div>
                </td>
                <td class="text-right py-2.5 text-gray-300 tabular-nums">{{ fmtUsd(p.exports_usd) }}</td>
                <td class="text-right py-2.5 text-gray-300 tabular-nums">{{ fmtUsd(p.imports_usd) }}</td>
                <td class="text-right py-2.5 tabular-nums font-medium" :class="p.balance_usd >= 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ fmtUsd(p.balance_usd) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Global stocks exposed -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-4">
        <h2 class="text-sm font-bold text-white mb-1">Global stocks exposed to {{ country.name }}</h2>
        <p class="text-xs text-gray-500 mb-4">Companies worldwide with significant revenue from this country — SEC EDGAR 10-K</p>
        <div v-if="stocksLoading" class="space-y-2">
          <div v-for="i in 5" :key="i" class="h-6 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="!exposedStocks?.length" class="text-gray-600 text-xs">No stock exposure data available</div>
        <div v-else class="space-y-3">
          <NuxtLink
            v-for="s in exposedStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol}`"
            class="flex items-center gap-3 group hover:bg-[#1f2937] rounded-lg px-2 py-1 -mx-2 transition-colors"
          >
            <span class="w-16 text-xs font-mono font-bold text-emerald-400 group-hover:text-emerald-300 shrink-0">{{ s.symbol }}</span>
            <span class="text-xs text-gray-400 flex-1 truncate group-hover:text-gray-200 transition-colors">{{ s.name }}</span>
            <div class="w-24 bg-[#1f2937] rounded-full h-1.5 shrink-0">
              <div class="bg-emerald-500 h-full rounded-full" :style="{ width: `${Math.min(s.revenue_pct, 100)}%` }"/>
            </div>
            <span class="text-xs text-white tabular-nums w-10 text-right shrink-0">{{ s.revenue_pct.toFixed(1) }}%</span>
          </NuxtLink>
          <p class="text-xs text-gray-600 mt-2">Source: SEC EDGAR 10-K · FY{{ exposedStocks[0]?.fiscal_year }}</p>
        </div>
      </div>

      <!-- Top local entities by market cap -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-6">
        <h2 class="text-sm font-bold text-white mb-1">Top local entities by market cap</h2>
        <p class="text-xs text-gray-500 mb-4">Publicly traded companies headquartered in {{ country.name }}</p>
        <div v-if="localStocksLoading" class="space-y-2">
          <div v-for="i in 4" :key="i" class="h-10 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="!localStocks?.length" class="text-gray-600 text-xs">No local listed companies on record</div>
        <div v-else class="space-y-2">
          <NuxtLink
            v-for="(s, i) in localStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol}`"
            class="flex items-center gap-3 hover:bg-[#1f2937] rounded-lg px-2 py-2 -mx-2 transition-colors group"
          >
            <span class="text-xs text-gray-600 w-4 shrink-0">{{ i + 1 }}</span>
            <span class="text-xs font-mono font-bold text-emerald-400 w-14 shrink-0 group-hover:text-emerald-300">{{ s.symbol }}</span>
            <span class="text-xs text-gray-300 flex-1 truncate">{{ s.name }}</span>
            <span class="text-xs text-white tabular-nums font-semibold shrink-0">{{ fmtCap(s.market_cap_usd) }}</span>
            <span class="text-emerald-600 text-xs shrink-0">→</span>
          </NuxtLink>
        </div>
      </div>

      <!-- Exports & resources -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Major Exports</h2>
          <div v-if="country.major_exports?.length" class="flex gap-2 flex-wrap">
            <span
              v-for="e in country.major_exports"
              :key="e"
              class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded capitalize"
            >{{ e }}</span>
          </div>
          <div v-else class="text-xs text-gray-600">
            Export composition data pending —
            <NuxtLink :to="`/trade?country=${code.toUpperCase()}`" class="text-emerald-700 hover:text-emerald-500 transition-colors">see trade flows →</NuxtLink>
          </div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Natural Resources</h2>
          <div v-if="country.natural_resources?.length" class="flex gap-2 flex-wrap">
            <span
              v-for="r in country.natural_resources"
              :key="r"
              class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded capitalize"
            >{{ r }}</span>
          </div>
          <div v-else class="text-xs text-gray-600">Natural resource data pending</div>
        </div>
      </div>

      <p class="text-xs text-gray-600">Data: World Bank · REST Countries · IMF · UN Comtrade · SEC EDGAR</p>
    </template>
  </main>
  <AuthModal v-model="showAuthModal" />
</template>

<script setup lang="ts">
const route = useRoute()
const { get, post, del } = useApi()
const { isLoggedIn } = useAuth()

const code = route.params.code as string

const { data: country, pending, error } = useAsyncData(
  `country-${code}`,
  () => get<any>(`/api/countries/${code}`).catch(() => null),
)

// Lazy-load supplementary data (non-blocking)
const { data: gdpHistory, pending: gdpLoading } = useAsyncData(
  `gdp-history-${code}`,
  () => get<any[]>(`/api/countries/${code}/gdp-history`),
)

const { data: tradePartners, pending: tradePartnersLoading } = useAsyncData(
  `trade-partners-${code}`,
  () => get<any[]>(`/api/countries/${code}/trade-partners`),
)

const { data: exposedStocks, pending: stocksLoading } = useAsyncData(
  `stocks-${code}`,
  () => get<any[]>(`/api/countries/${code}/stocks`),
)

const { data: localStocks, pending: localStocksLoading } = useAsyncData(
  `local-stocks-${code}`,
  () => get<any[]>('/api/assets', { type: 'stock', country_code: code.toUpperCase() }).catch(() => []),
)

const { data: timeseries, pending: timeseriesLoading } = useAsyncData(
  `timeseries-${code}`,
  () => get<Record<string, any[]>>(`/api/countries/${code}/timeseries`, {
    keys: 'gdp_growth_pct,inflation_pct,interest_rate_pct,unemployment_pct',
  }).catch(() => ({})),
)

const { data: pageSummary } = useAsyncData(
  `summary-country-${code}`,
  () => get<any>(`/api/summaries/country/${code.toUpperCase()}`).catch(() => null),
  { server: false },
)

const { data: pageInsight } = useAsyncData(
  `insight-country-${code}`,
  () => get<any>(`/api/summaries/country_insight/${code.toUpperCase()}`).catch(() => null),
  { server: false },
)

// ── Follow ────────────────────────────────────────────────────────────────────
const showAuthModal = ref(false)
const isFollowing = ref(false)

onMounted(async () => {
  if (!isLoggedIn.value || !country.value?.id) return
  try {
    const follows = await get<any[]>('/api/feed/follows')
    isFollowing.value = follows.some(
      (f: any) => f.entity_type === 'country' && f.entity_id === country.value!.id,
    )
  } catch { /* ignore */ }
})

async function toggleFollow() {
  if (!isLoggedIn.value) { showAuthModal.value = true; return }
  if (!country.value?.id) return
  try {
    if (isFollowing.value) {
      await del(`/api/feed/follows/country/${country.value.id}`)
      isFollowing.value = false
    } else {
      await post('/api/feed/follows', { entity_type: 'country', entity_id: country.value.id })
      isFollowing.value = true
    }
  } catch { /* ignore */ }
}

const { public: { r2PublicUrl } } = useRuntimeConfig()
const ogImageUrl = computed(() =>
  r2PublicUrl
    ? `${r2PublicUrl}/og/countries/${code.toLowerCase()}.png`
    : 'https://metricshour.com/og-image.png',
)

useSeoMeta({
  title: computed(() =>
    country.value
      ? `${country.value.name} Economy & Macro Data — MetricsHour`
      : 'Country — MetricsHour',
  ),
  description: computed(() =>
    country.value
      ? `GDP, inflation, trade flows, and 80+ macro indicators for ${country.value.name}. Data from World Bank, IMF, and UN Comtrade.`
      : '',
  ),
  ogTitle: computed(() =>
    country.value ? `${country.value.name} Economy & Macro Data — MetricsHour` : 'Country — MetricsHour'
  ),
  ogDescription: computed(() =>
    country.value
      ? `GDP, inflation, trade flows, and 80+ macro indicators for ${country.value.name}. Data from World Bank, IMF, and UN Comtrade.`
      : ''
  ),
  ogUrl: `https://metricshour.com/countries/${code}`,
  ogType: 'website',
  ogImage: ogImageUrl,
  twitterImage: ogImageUrl,
  twitterTitle: computed(() =>
    country.value ? `${country.value.name} Economy & Macro Data — MetricsHour` : 'Country — MetricsHour'
  ),
  twitterDescription: computed(() =>
    country.value
      ? `GDP, inflation, trade flows, and 80+ macro indicators for ${country.value.name}. Data from World Bank, IMF, and UN Comtrade.`
      : ''
  ),
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/countries/${code}` }],
  script: country.value ? [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: `${country.value.name} Economy & Macro Data — MetricsHour`,
      url: `https://metricshour.com/countries/${code}`,
      description: `GDP, inflation, trade flows, and 80+ macro indicators for ${country.value.name}. Data from World Bank, IMF, and UN Comtrade.`,
      breadcrumb: {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
          { '@type': 'ListItem', position: 2, name: 'Countries', item: 'https://metricshour.com/countries' },
          { '@type': 'ListItem', position: 3, name: country.value.name, item: `https://metricshour.com/countries/${code}` },
        ],
      },
    }),
  }] : [],
})))

// ─── Formatting helpers ──────────────────────────────────────────────────────

function fmt(key: string, val: number | null | undefined): string {
  if (val === undefined || val === null) return 'N/A'

  if (key.endsWith('_usd')) {
    const abs = Math.abs(val)
    const sign = val < 0 ? '-' : ''
    if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`
    if (abs >= 1e9)  return `${sign}$${(abs / 1e9).toFixed(1)}B`
    if (abs >= 1e6)  return `${sign}$${(abs / 1e6).toFixed(1)}M`
    return `${sign}$${abs.toLocaleString()}`
  }

  if (key.endsWith('_pct')) return `${val.toFixed(1)}%`

  if (key === 'population') {
    if (val >= 1e9) return `${(val / 1e9).toFixed(2)}B`
    if (val >= 1e6) return `${(val / 1e6).toFixed(1)}M`
    return val.toLocaleString()
  }

  if (key === 'hdi') return val.toFixed(3)
  if (key === 'gini_coefficient') return val.toFixed(1)
  if (key === 'life_expectancy') return `${val.toFixed(1)} yrs`
  if (key === 'infant_mortality_per_1000') return `${val.toFixed(1)} / 1k`
  if (key.endsWith('_index')) return val.toFixed(2)

  return val.toFixed(1)
}

function fmtCap(v: number | null | undefined): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`
  if (abs >= 1e9)  return `${sign}$${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6)  return `${sign}$${(abs / 1e6).toFixed(0)}M`
  return `${sign}$${abs.toLocaleString()}`
}

function row(label: string, key: string) {
  const val = country.value?.indicators?.[key]
  return { label, value: fmt(key, val), raw: val ?? null }
}

// ─── Key indicator cards ─────────────────────────────────────────────────────

const keyIndicators = computed(() => {
  const ind = country.value?.indicators ?? {}
  return [
    { label: 'GDP', value: fmt('gdp_usd', ind.gdp_usd) },
    { label: 'GDP Growth', value: fmt('gdp_growth_pct', ind.gdp_growth_pct) },
    { label: 'Inflation', value: fmt('inflation_pct', ind.inflation_pct) },
    { label: 'Unemployment', value: fmt('unemployment_pct', ind.unemployment_pct) },
    { label: 'Interest Rate', value: fmt('interest_rate_pct', ind.interest_rate_pct) },
    { label: 'Debt / GDP', value: fmt('government_debt_gdp_pct', ind.government_debt_gdp_pct) },
  ]
})

// ─── Indicator sections ───────────────────────────────────────────────────────

const economyRows = computed(() => [
  row('GDP', 'gdp_usd'),
  row('GDP per capita', 'gdp_per_capita_usd'),
  row('GDP growth', 'gdp_growth_pct'),
  row('GDP (PPP)', 'gdp_ppp_usd'),
  row('GDP per capita (PPP)', 'gdp_per_capita_ppp_usd'),
  row('Population', 'population'),
].filter(r => r.raw !== null))

const monetaryRows = computed(() => [
  row('Inflation', 'inflation_pct'),
  row('Interest rate', 'interest_rate_pct'),
  row('Real interest rate', 'real_interest_rate_pct'),
  row('Foreign reserves', 'foreign_reserves_usd'),
  row('M2 Supply (% GDP)', 'money_supply_m2_gdp_pct'),
].filter(r => r.raw !== null))

const tradeRows = computed(() => {
  const ind = country.value?.indicators ?? {}
  const tradeBalance = (ind.exports_usd != null && ind.imports_usd != null)
    ? ind.exports_usd - ind.imports_usd
    : null
  const tradeOpenness = (ind.exports_usd != null && ind.imports_usd != null && ind.gdp_usd != null)
    ? ((ind.exports_usd + ind.imports_usd) / ind.gdp_usd) * 100
    : null
  return [
    row('Exports', 'exports_usd'),
    row('Imports', 'imports_usd'),
    { label: 'Trade balance', value: fmt('trade_balance_usd', tradeBalance), raw: tradeBalance },
    { label: 'Trade openness', value: fmt('trade_openness_pct', tradeOpenness), raw: tradeOpenness },
    row('Current account (% GDP)', 'current_account_gdp_pct'),
    row('FDI inflows', 'fdi_inflows_usd'),
  ].filter(r => r.raw !== null)
})

const fiscalRows = computed(() => [
  row('Govt debt (% GDP)', 'government_debt_gdp_pct'),
  row('Budget balance (% GDP)', 'budget_balance_gdp_pct'),
  row('Tax revenue (% GDP)', 'tax_revenue_gdp_pct'),
  row('Military spending (% GDP)', 'military_spending_gdp_pct'),
].filter(r => r.raw !== null))

const socialRows = computed(() => [
  row('Unemployment', 'unemployment_pct'),
  row('Life expectancy', 'life_expectancy'),
  row('Gini coefficient', 'gini_coefficient'),
  row('Internet penetration', 'internet_penetration_pct'),
  row('Literacy rate', 'literacy_rate_pct'),
  row('Poverty rate', 'poverty_rate_pct'),
  row('Urban population', 'urban_population_pct'),
  row('Infant mortality', 'infant_mortality_per_1000'),
].filter(r => r.raw !== null))

const governanceRows = computed(() => [
  row('Corruption control', 'control_of_corruption_index'),
  row('Rule of law', 'rule_of_law_index'),
  row('Political stability', 'political_stability_index'),
  row('Govt effectiveness', 'government_effectiveness_index'),
  row('Regulatory quality', 'regulatory_quality_index'),
  row('Voice & accountability', 'voice_accountability_index'),
].filter(r => r.raw !== null))

// ─── GDP chart (ECharts) ──────────────────────────────────────────────────────

const gdpChartOption = computed(() => {
  const data = gdpHistory.value ?? []
  if (!data.length) return {}
  const years = data.map((d: any) => String(d.year))
  const values = data.map((d: any) => d.gdp)

  function fmtGdpAxis(v: number) {
    if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
    if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
    return `$${(v / 1e6).toFixed(0)}M`
  }

  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 12, bottom: 28, left: 60, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1117',
      borderColor: '#1f2937',
      borderWidth: 1,
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      formatter: (params: any[]) => {
        const p = params[0]
        return `<b>${p.name}</b><br/>GDP: <b style="color:#10b981">${fmtGdpAxis(p.value)}</b>`
      },
    },
    xAxis: {
      type: 'category',
      data: years,
      axisLine: { lineStyle: { color: '#1f2937' } },
      axisTick: { show: false },
      axisLabel: { color: '#4b5563', fontSize: 10, interval: Math.max(0, Math.floor(years.length / 5) - 1) },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: { color: '#4b5563', fontSize: 10, formatter: fmtGdpAxis },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#10b981', width: 2 },
      areaStyle: { color: 'rgba(16,185,129,0.08)' },
    }],
  }
})

// ─── Macro timeseries chart (ECharts multi-line) ──────────────────────────────

const INDICATOR_META: Record<string, { label: string; color: string }> = {
  gdp_growth_pct:   { label: 'GDP Growth %',  color: '#10b981' },
  inflation_pct:    { label: 'Inflation %',    color: '#f59e0b' },
  interest_rate_pct:{ label: 'Interest Rate %',color: '#60a5fa' },
  unemployment_pct: { label: 'Unemployment %', color: '#a78bfa' },
}

const hasTimeseries = computed(() => {
  const ts = timeseries.value ?? {}
  return Object.values(ts).some((v: any) => v?.length > 0)
})

const macroChartOption = computed(() => {
  const ts = timeseries.value ?? {}
  const allYears = [...new Set(
    Object.values(ts).flatMap((arr: any) => arr.map((d: any) => d.year))
  )].sort() as number[]

  const series = Object.entries(ts)
    .filter(([, arr]) => (arr as any[]).length > 0)
    .map(([key, arr]) => {
      const meta = INDICATOR_META[key] ?? { label: key, color: '#6b7280' }
      const yearMap = Object.fromEntries((arr as any[]).map((d: any) => [d.year, d.value]))
      return {
        name: meta.label,
        type: 'line',
        data: allYears.map(y => yearMap[y] ?? null),
        connectNulls: false,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: meta.color, width: 1.5 },
        itemStyle: { color: meta.color },
      }
    })

  return {
    backgroundColor: 'transparent',
    legend: {
      top: 0,
      right: 0,
      textStyle: { color: '#9ca3af', fontSize: 10 },
      itemWidth: 12,
      itemHeight: 3,
    },
    grid: { top: 28, right: 12, bottom: 28, left: 48, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1117',
      borderColor: '#1f2937',
      borderWidth: 1,
      textStyle: { color: '#e5e7eb', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: allYears.map(String),
      axisLine: { lineStyle: { color: '#1f2937' } },
      axisTick: { show: false },
      axisLabel: { color: '#4b5563', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: {
        color: '#4b5563',
        fontSize: 10,
        formatter: (v: number) => `${v.toFixed(1)}%`,
      },
    },
    series,
  }
})
</script>
