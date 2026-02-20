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
        <div class="flex gap-2 flex-wrap mt-2">
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

      <!-- Macro indicators -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <IndicatorSection title="Economy" :rows="economyRows" />
        <IndicatorSection title="Monetary" :rows="monetaryRows" />
        <IndicatorSection title="Trade" :rows="tradeRows" />
        <IndicatorSection title="Fiscal" :rows="fiscalRows" />
        <IndicatorSection title="Social" :rows="socialRows" />
        <IndicatorSection title="Governance" :rows="governanceRows" />
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

      <p class="text-xs text-gray-600">Data: World Bank · REST Countries · IMF · UN Comtrade</p>
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

// Format indicator values based on key naming conventions
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

function row(label: string, key: string) {
  const val = country.value?.indicators?.[key]
  return { label, value: fmt(key, val), raw: val ?? null }
}

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
</script>
