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
        <div class="flex gap-2 flex-wrap mt-3">
          <span
            v-for="g in country.groupings"
            :key="g"
            class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded"
          >{{ g }}</span>
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
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-6">
        <h2 class="text-sm font-bold text-white mb-4">GDP History</h2>
        <div v-if="!gdpHistory?.length" class="h-32 flex items-center justify-center text-gray-600 text-xs">
          No GDP history data available
        </div>
        <div v-else class="relative">
          <svg :viewBox="`0 0 400 120`" class="w-full h-36" preserveAspectRatio="none">
            <defs>
              <linearGradient id="gdpGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#10b981" stop-opacity="0.35"/>
                <stop offset="100%" stop-color="#10b981" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <!-- Horizontal grid -->
            <line v-for="i in 4" :key="i" x1="0" :y1="i * 24" x2="400" :y2="i * 24" stroke="#1f2937" stroke-width="0.5"/>
            <!-- Area fill -->
            <polygon :points="gdpAreaPoints" fill="url(#gdpGrad)"/>
            <!-- Line -->
            <polyline :points="gdpLinePoints" fill="none" stroke="#10b981" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
          </svg>
          <!-- X-axis labels -->
          <div class="flex justify-between mt-1 px-0.5">
            <span
              v-for="(d, i) in gdpLabelYears"
              :key="i"
              class="text-xs text-gray-600"
            >{{ d }}</span>
          </div>
          <!-- Y-axis (last value) -->
          <div class="absolute top-0 right-0 text-xs text-emerald-400 font-medium">
            {{ gdpHistory ? fmt('gdp_usd', gdpHistory[gdpHistory.length - 1]?.gdp) : '' }}
          </div>
        </div>
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
                  <NuxtLink
                    :to="`/trade/${code.toUpperCase()}-${p.partner.code}`"
                    class="flex items-center gap-2 hover:text-emerald-400 transition-colors"
                  >
                    <span>{{ p.partner.flag }}</span>
                    <span class="text-white">{{ p.partner.name }}</span>
                  </NuxtLink>
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

      <!-- Stocks Exposed -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-6">
        <h2 class="text-sm font-bold text-white mb-1">Stocks Exposed to {{ country.name }}</h2>
        <p class="text-xs text-gray-500 mb-4">Companies with meaningful revenue from this country — SEC EDGAR 10-K data</p>
        <div v-if="stocksLoading" class="space-y-2">
          <div v-for="i in 5" :key="i" class="h-6 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="!exposedStocks?.length" class="text-gray-600 text-xs">No stock exposure data available</div>
        <div v-else class="space-y-3">
          <div
            v-for="s in exposedStocks"
            :key="s.symbol"
            class="flex items-center gap-3"
          >
            <NuxtLink
              :to="`/stocks/${s.symbol}`"
              class="w-16 text-xs font-mono font-bold text-emerald-400 hover:text-emerald-300 shrink-0"
            >{{ s.symbol }}</NuxtLink>
            <span class="text-xs text-gray-400 flex-1 truncate">{{ s.name }}</span>
            <div class="w-24 bg-[#1f2937] rounded-full h-1.5 shrink-0">
              <div class="bg-emerald-500 h-full rounded-full" :style="{ width: `${Math.min(s.revenue_pct, 100)}%` }"/>
            </div>
            <span class="text-xs text-white tabular-nums w-10 text-right shrink-0">{{ s.revenue_pct.toFixed(1) }}%</span>
          </div>
          <p class="text-xs text-gray-600 mt-2">Source: SEC EDGAR 10-K · FY{{ exposedStocks[0]?.fiscal_year }}</p>
        </div>
      </div>

      <!-- Exports & resources -->
      <div
        v-if="country.major_exports?.length || country.natural_resources?.length"
        class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8"
      >
        <div v-if="country.major_exports?.length" class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Major Exports</h2>
          <div class="flex gap-2 flex-wrap">
            <span
              v-for="e in country.major_exports"
              :key="e"
              class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded capitalize"
            >{{ e }}</span>
          </div>
        </div>
        <div v-if="country.natural_resources?.length" class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Natural Resources</h2>
          <div class="flex gap-2 flex-wrap">
            <span
              v-for="r in country.natural_resources"
              :key="r"
              class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded capitalize"
            >{{ r }}</span>
          </div>
        </div>
      </div>

      <p class="text-xs text-gray-600">Data: World Bank · REST Countries · IMF · UN Comtrade · SEC EDGAR</p>
    </template>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()

const code = route.params.code as string

const { data: country, pending, error } = await useAsyncData(
  `country-${code}`,
  () => get<any>(`/api/countries/${code}`),
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
})

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
  if (key.endsWith('_index')) return val.toFixed(1)

  return val.toFixed(1)
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
])

const monetaryRows = computed(() => [
  row('Inflation', 'inflation_pct'),
  row('Interest rate', 'interest_rate_pct'),
  row('Real interest rate', 'real_interest_rate_pct'),
  row('Foreign reserves', 'foreign_reserves_usd'),
  row('M2 money supply', 'money_supply_m2_usd'),
])

const tradeRows = computed(() => [
  row('Exports', 'exports_usd'),
  row('Imports', 'imports_usd'),
  row('Trade balance', 'trade_balance_usd'),
  row('Trade openness', 'trade_openness_pct'),
  row('Current account (% GDP)', 'current_account_gdp_pct'),
  row('FDI inflows', 'fdi_inflows_usd'),
])

const fiscalRows = computed(() => [
  row('Govt debt (% GDP)', 'government_debt_gdp_pct'),
  row('Budget balance (% GDP)', 'budget_balance_gdp_pct'),
  row('Tax revenue (% GDP)', 'tax_revenue_gdp_pct'),
  row('Military spending (% GDP)', 'military_spending_gdp_pct'),
])

const socialRows = computed(() => [
  row('HDI', 'hdi'),
  row('Unemployment', 'unemployment_pct'),
  row('Gini coefficient', 'gini_coefficient'),
  row('Internet penetration', 'internet_penetration_pct'),
  row('Literacy rate', 'literacy_rate_pct'),
  row('Poverty rate', 'poverty_rate_pct'),
])

const governanceRows = computed(() => [
  row('Corruption perception', 'corruption_perception_index'),
  row('Rule of law', 'rule_of_law_index'),
  row('Political stability', 'political_stability_index'),
  row('Democracy index', 'democracy_index'),
  row('Economic freedom', 'economic_freedom_index'),
])

// ─── GDP chart (SVG) ──────────────────────────────────────────────────────────

const W = 400
const H = 110
const PAD = 10

const gdpLinePoints = computed(() => {
  const data = gdpHistory.value
  if (!data?.length) return ''
  const vals = data.map(d => d.gdp)
  const minV = Math.min(...vals)
  const maxV = Math.max(...vals)
  const range = maxV - minV || 1
  return data.map((d, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2)
    const y = (H - PAD) - ((d.gdp - minV) / range) * (H - PAD * 2)
    return `${x},${y}`
  }).join(' ')
})

const gdpAreaPoints = computed(() => {
  const data = gdpHistory.value
  if (!data?.length) return ''
  const vals = data.map(d => d.gdp)
  const minV = Math.min(...vals)
  const maxV = Math.max(...vals)
  const range = maxV - minV || 1
  const pts = data.map((d, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2)
    const y = (H - PAD) - ((d.gdp - minV) / range) * (H - PAD * 2)
    return `${x},${y}`
  })
  const firstX = PAD
  const lastX = PAD + (W - PAD * 2)
  return `${firstX},${H - PAD} ${pts.join(' ')} ${lastX},${H - PAD}`
})

const gdpLabelYears = computed(() => {
  const data = gdpHistory.value
  if (!data?.length) return []
  const n = data.length
  // Show ~5 evenly-spaced labels
  const step = Math.max(1, Math.floor(n / 4))
  const indices = [0]
  for (let i = step; i < n - 1; i += step) indices.push(i)
  indices.push(n - 1)
  return [...new Set(indices)].map(i => data[i].year)
})
</script>
