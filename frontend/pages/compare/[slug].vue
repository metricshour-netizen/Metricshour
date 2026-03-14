<template>
  <div>
    <!-- Hero -->
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/countries" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Countries
        </NuxtLink>

        <div v-if="pending && !countryA && !countryB" class="flex items-center gap-6 h-20">
          <div class="w-16 h-16 bg-[#1f2937] rounded-xl animate-pulse"/>
          <div class="w-12 h-8 bg-[#1f2937] rounded animate-pulse"/>
          <div class="w-16 h-16 bg-[#1f2937] rounded-xl animate-pulse"/>
        </div>

        <template v-if="!pending && error && !countryA && !countryB">
          <div class="text-red-400 text-sm py-4">
            Invalid comparison. Try <code class="text-gray-400">/compare/us-vs-cn</code>
          </div>
        </template>

        <template v-else>
          <h1 class="text-xl sm:text-2xl font-extrabold text-white mb-4">
            {{ nameA }} vs {{ nameB }} Economy
          </h1>
          <div class="flex items-center gap-6 flex-wrap">
            <div class="flex items-center gap-3">
              <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-3xl">
                {{ countryA?.flag || '🏳' }}
              </div>
              <div>
                <div class="text-base font-bold text-white">{{ countryA?.name || codeA.toUpperCase() }}</div>
                <div class="text-xs text-emerald-400 font-mono">{{ codeA.toUpperCase() }}</div>
              </div>
            </div>
            <div class="text-2xl text-gray-500">vs</div>
            <div class="flex items-center gap-3">
              <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-3xl">
                {{ countryB?.flag || '🏳' }}
              </div>
              <div>
                <div class="text-base font-bold text-white">{{ countryB?.name || codeB.toUpperCase() }}</div>
                <div class="text-xs text-emerald-400 font-mono">{{ codeB.toUpperCase() }}</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main v-if="!pending && countryA && countryB" class="max-w-7xl mx-auto px-4 py-8 space-y-8">

      <!-- Country summaries side-by-side -->
      <section v-if="summaryA?.summary || summaryB?.summary" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div v-if="summaryA?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-emerald-400 font-bold mb-2">{{ countryA.name }}</div>
          <p class="text-sm text-gray-400 leading-relaxed">{{ summaryA.summary }}</p>
        </div>
        <div v-if="summaryB?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-blue-400 font-bold mb-2">{{ countryB.name }}</div>
          <p class="text-sm text-gray-400 leading-relaxed">{{ summaryB.summary }}</p>
        </div>
      </section>

      <!-- Key Indicators Comparison Table -->
      <section>
        <h2 class="text-sm font-extrabold text-white uppercase tracking-widest mb-4">Key Economic Indicators</h2>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#1f2937]">
                <th class="text-left text-gray-500 font-medium py-2 pr-4 w-1/3">Indicator</th>
                <th class="text-right text-emerald-400 font-bold py-2 px-4">{{ countryA.name }}</th>
                <th class="text-right text-blue-400 font-bold py-2 pl-4">{{ countryB.name }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="row in indicatorRows" :key="row.key">
                <tr v-if="row.isSection" class="border-b border-[#1f2937]">
                  <td colspan="3" class="pt-4 pb-1 text-[10px] font-bold text-gray-600 uppercase tracking-widest">{{ row.label }}</td>
                </tr>
                <tr v-else class="border-b border-[#1f2937]/50 hover:bg-[#111827]/60 transition-colors">
                <td class="py-3 pr-4 text-gray-400">{{ row.label }}</td>
                <td class="py-3 px-4 text-right font-mono">
                  <span :class="row.winnerA ? 'text-white font-bold' : 'text-gray-400'">
                    {{ row.fmtA }}
                  </span>
                  <span v-if="row.winnerA" class="ml-1 text-[10px] text-emerald-500">▲</span>
                </td>
                <td class="py-3 pl-4 text-right font-mono">
                  <span :class="row.winnerB ? 'text-white font-bold' : 'text-gray-400'">
                    {{ row.fmtB }}
                  </span>
                  <span v-if="row.winnerB" class="ml-1 text-[10px] text-blue-400">▲</span>
                </td>
              </tr>
              </template>
            </tbody>
          </table>
        </div>
        <p class="text-[11px] text-gray-700 mt-2">Source: World Bank. ▲ = higher value. For inflation/unemployment/debt, lower may be preferable.</p>
      </section>

      <!-- Bilateral Trade (if data exists) -->
      <section v-if="trade">
        <h2 class="text-sm font-extrabold text-white uppercase tracking-widest mb-4">Bilateral Trade</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-[10px] text-gray-600 uppercase tracking-wider mb-1">Total Trade</div>
            <div class="text-lg font-extrabold text-white tabular-nums">{{ fmtUsd(trade.trade_value_usd) }}</div>
            <div class="text-[10px] text-gray-600 mt-1">{{ trade.year }}</div>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-[10px] text-gray-600 uppercase tracking-wider mb-1">{{ countryA.name }} Exports</div>
            <div class="text-lg font-extrabold text-white tabular-nums">{{ fmtUsd(trade.exports_usd) }}</div>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-[10px] text-gray-600 uppercase tracking-wider mb-1">{{ countryA.name }} Imports</div>
            <div class="text-lg font-extrabold text-white tabular-nums">{{ fmtUsd(trade.imports_usd) }}</div>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-[10px] text-gray-600 uppercase tracking-wider mb-1">Trade Balance</div>
            <div class="text-lg font-extrabold tabular-nums"
              :class="(trade.exports_usd || 0) >= (trade.imports_usd || 0) ? 'text-emerald-400' : 'text-red-400'">
              {{ fmtBalance(trade) }}
            </div>
          </div>
        </div>
        <!-- Top products -->
        <div v-if="trade.top_export_products?.length || trade.top_import_products?.length" class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
          <div v-if="trade.top_export_products?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-[10px] text-emerald-500 font-bold uppercase tracking-wider mb-2">{{ countryA.name }} Top Exports</div>
            <div v-for="p in trade.top_export_products" :key="p.name" class="flex justify-between items-center py-1 border-b border-[#1f2937]/40 last:border-0">
              <span class="text-xs text-gray-400 capitalize">{{ p.name }}</span>
              <span class="text-xs text-white font-mono">{{ fmtUsd(p.value_usd) }}</span>
            </div>
          </div>
          <div v-if="trade.top_import_products?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-[10px] text-blue-400 font-bold uppercase tracking-wider mb-2">{{ countryA.name }} Top Imports</div>
            <div v-for="p in trade.top_import_products" :key="p.name" class="flex justify-between items-center py-1 border-b border-[#1f2937]/40 last:border-0">
              <span class="text-xs text-gray-400 capitalize">{{ p.name }}</span>
              <span class="text-xs text-white font-mono">{{ fmtUsd(p.value_usd) }}</span>
            </div>
          </div>
        </div>

        <NuxtLink
          :to="`/trade/${countryA?.slug ?? codeA}--${countryB?.slug ?? codeB}`"
          class="inline-flex items-center gap-1 text-xs text-emerald-500 hover:text-emerald-300 mt-3 transition-colors"
        >
          Full trade analysis →
        </NuxtLink>
      </section>

      <!-- Groupings & Credit Ratings -->
      <section>
        <h2 class="text-sm font-extrabold text-white uppercase tracking-widest mb-4">Groupings & Ratings</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-xs text-emerald-400 font-bold mb-3">{{ countryA.name }}</div>
            <div class="flex flex-wrap gap-1.5 mb-3">
              <span v-for="g in countryA.groupings" :key="g"
                class="text-[10px] bg-[#1f2937] text-gray-400 px-2 py-0.5 rounded-full">{{ g }}</span>
              <span v-if="!countryA.groupings?.length" class="text-[11px] text-gray-600">—</span>
            </div>
            <div class="text-[11px] text-gray-500">
              S&amp;P: <span class="text-white">{{ countryA.credit_rating_sp || 'N/A' }}</span>
              &nbsp;·&nbsp;
              Moody's: <span class="text-white">{{ countryA.credit_rating_moodys || 'N/A' }}</span>
            </div>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-xs text-blue-400 font-bold mb-3">{{ countryB.name }}</div>
            <div class="flex flex-wrap gap-1.5 mb-3">
              <span v-for="g in countryB.groupings" :key="g"
                class="text-[10px] bg-[#1f2937] text-gray-400 px-2 py-0.5 rounded-full">{{ g }}</span>
              <span v-if="!countryB.groupings?.length" class="text-[11px] text-gray-600">—</span>
            </div>
            <div class="text-[11px] text-gray-500">
              S&amp;P: <span class="text-white">{{ countryB.credit_rating_sp || 'N/A' }}</span>
              &nbsp;·&nbsp;
              Moody's: <span class="text-white">{{ countryB.credit_rating_moodys || 'N/A' }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Related links -->
      <section>
        <h2 class="text-sm font-extrabold text-white uppercase tracking-widest mb-4">Related</h2>
        <div class="flex flex-wrap gap-3 text-xs">
          <NuxtLink :to="`/countries/${codeA}`" class="text-emerald-500 hover:text-emerald-300 transition-colors">
            {{ countryA.name }} Economy →
          </NuxtLink>
          <NuxtLink :to="`/countries/${codeB}`" class="text-blue-400 hover:text-blue-300 transition-colors">
            {{ countryB.name }} Economy →
          </NuxtLink>
          <NuxtLink v-if="trade" :to="`/trade/${countryA?.slug ?? codeA}--${countryB?.slug ?? codeB}`" class="text-gray-400 hover:text-white transition-colors">
            {{ countryA.name }}–{{ countryB.name }} Trade →
          </NuxtLink>
          <NuxtLink to="/countries" class="text-gray-500 hover:text-gray-300 transition-colors">
            All Countries →
          </NuxtLink>
        </div>
      </section>

      <!-- Newsletter -->
      <div class="mt-8 border border-gray-800 rounded-xl p-6 bg-gray-900/40">
        <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">Country comparisons + macro intelligence, every week.</p>
        <p class="text-xs text-gray-500 mb-4">GDP, trade, economic divergence — free.</p>
        <NewsletterCapture :source="`compare_page_${slug}`" button-text="Subscribe free" />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()

// Parse slug: "us-vs-cn" → codeA="us", codeB="cn"
const slug = (route.params.slug as string).toLowerCase()
const vsParts = slug.split('-vs-')

// Canonical redirect: ensure alphabetically sorted (cn-vs-us → cn-vs-us is fine, us-vs-cn stays)
// Actually canonical is: sort the two codes alphabetically
const rawA = (vsParts[0] || '').toUpperCase()
const rawB = (vsParts[1] || '').toUpperCase()
const [canonA, canonB] = [rawA, rawB].sort()
const codeA = canonA.toLowerCase()
const codeB = canonB.toLowerCase()

// Redirect non-canonical URLs
if (rawA !== canonA || rawB !== canonB) {
  await navigateTo(`/compare/${codeA}-vs-${codeB}`, { replace: true })
}

const [{ data: dataA, pending: pA, error: errA }, { data: dataB, pending: pB, error: errB }] = await Promise.all([
  useAsyncData(`compare-${codeA}`, () => get<any>(`/api/countries/${codeA}`).catch(() => null)),
  useAsyncData(`compare-${codeB}`, () => get<any>(`/api/countries/${codeB}`).catch(() => null)),
])

const pending = computed(() => pA.value || pB.value)
const error   = computed(() => errA.value || errB.value)
const countryA = computed(() => dataA.value)
const countryB = computed(() => dataB.value)

const { data: tradeRaw } = useAsyncData(
  `compare-trade-${codeA}-${codeB}`,
  () => get<any>(`/api/trade/${codeA}/${codeB}`).catch(() => null),
)
const { data: summaryA } = useAsyncData(
  `summary-country-compare-${codeA}`,
  () => get<any>(`/api/summaries/country/${canonA}`).catch(() => null),
  { server: false },
)
const { data: summaryB } = useAsyncData(
  `summary-country-compare-${codeB}`,
  () => get<any>(`/api/summaries/country/${canonB}`).catch(() => null),
  { server: false },
)

// Normalise trade direction — always show from A's perspective
const trade = computed(() => {
  const raw = tradeRaw.value
  if (!raw) return null
  // API returns { exporter, importer, trade_data, canonical_pair }
  const td = raw.trade_data || raw
  if (!td || (!td.trade_value_usd && !td.exports_usd && !td.imports_usd)) return null
  const expCode = (raw.exporter?.code || td.exporter?.code || '').toUpperCase()
  if (expCode === canonA) return td
  // Flip direction so A is always the exporter perspective
  return {
    ...td,
    exports_usd: td.imports_usd,
    imports_usd: td.exports_usd,
  }
})

// Indicator rows
type IndicatorDef = { section?: string; key: string; label: string; fmt: (v: number) => string; higher: boolean }

const INDICATORS: IndicatorDef[] = [
  { section: 'Economy',   key: 'gdp_usd',                     label: 'GDP',                      fmt: (v) => fmtUsd(v),                                  higher: true  },
  {                        key: 'gdp_per_capita_usd',          label: 'GDP per Capita',           fmt: (v) => '$' + fmtNum(v, 0),                         higher: true  },
  {                        key: 'gdp_per_capita_ppp',          label: 'GDP per Capita (PPP)',     fmt: (v) => '$' + fmtNum(v, 0),                         higher: true  },
  {                        key: 'gdp_growth_pct',              label: 'GDP Growth (%)',           fmt: (v) => v.toFixed(1) + '%',                         higher: true  },
  { section: 'Macro',     key: 'inflation_pct',               label: 'Inflation (%)',            fmt: (v) => v.toFixed(1) + '%',                         higher: false },
  {                        key: 'interest_rate_pct',           label: 'Interest Rate (%)',        fmt: (v) => v.toFixed(2) + '%',                         higher: false },
  {                        key: 'unemployment_pct',            label: 'Unemployment (%)',         fmt: (v) => v.toFixed(1) + '%',                         higher: false },
  {                        key: 'youth_unemployment_pct',      label: 'Youth Unemployment (%)',   fmt: (v) => v.toFixed(1) + '%',                         higher: false },
  { section: 'Fiscal',    key: 'government_debt_gdp_pct',     label: 'Govt Debt (% GDP)',        fmt: (v) => v.toFixed(1) + '%',                         higher: false },
  {                        key: 'budget_balance_gdp_pct',      label: 'Budget Balance (% GDP)',   fmt: (v) => (v >= 0 ? '+' : '') + v.toFixed(1) + '%',   higher: true  },
  {                        key: 'tax_revenue_gdp_pct',         label: 'Tax Revenue (% GDP)',      fmt: (v) => v.toFixed(1) + '%',                         higher: false },
  { section: 'External',  key: 'current_account_gdp_pct',     label: 'Current Account (% GDP)',  fmt: (v) => (v >= 0 ? '+' : '') + v.toFixed(1) + '%',   higher: true  },
  {                        key: 'exports_usd',                 label: 'Exports',                  fmt: (v) => fmtUsd(v),                                  higher: true  },
  {                        key: 'imports_usd',                 label: 'Imports',                  fmt: (v) => fmtUsd(v),                                  higher: false },
  {                        key: 'fdi_inflows_usd',             label: 'FDI Inflows',              fmt: (v) => fmtUsd(v),                                  higher: true  },
  {                        key: 'foreign_reserves_usd',        label: 'Foreign Reserves',         fmt: (v) => fmtUsd(v),                                  higher: true  },
  { section: 'Society',   key: 'population',                  label: 'Population',               fmt: (v) => fmtPop(v),                                  higher: false },
  {                        key: 'life_expectancy',             label: 'Life Expectancy (yrs)',    fmt: (v) => v.toFixed(1),                               higher: true  },
  {                        key: 'gini_coefficient',            label: 'Gini Inequality',          fmt: (v) => v.toFixed(1),                               higher: false },
  {                        key: 'healthcare_spending_gdp_pct', label: 'Healthcare (% GDP)',       fmt: (v) => v.toFixed(1) + '%',                         higher: true  },
  {                        key: 'education_spending_gdp_pct',  label: 'Education (% GDP)',        fmt: (v) => v.toFixed(1) + '%',                         higher: true  },
  {                        key: 'internet_penetration_pct',    label: 'Internet Penetration',     fmt: (v) => v.toFixed(1) + '%',                         higher: true  },
  {                        key: 'military_spending_gdp_pct',   label: 'Military (% GDP)',         fmt: (v) => v.toFixed(2) + '%',                         higher: false },
  {                        key: 'renewable_energy_pct',        label: 'Renewable Energy (%)',     fmt: (v) => v.toFixed(1) + '%',                         higher: true  },
]

const indicatorRows = computed(() => {
  const indA = countryA.value?.indicators || {}
  const indB = countryB.value?.indicators || {}
  const rows: any[] = []
  let lastSection = ''
  for (const ind of INDICATORS) {
    const vA = indA[ind.key] as number | undefined
    const vB = indB[ind.key] as number | undefined
    if (vA == null && vB == null) continue
    if (ind.section && ind.section !== lastSection) {
      rows.push({ isSection: true, key: `section-${ind.section}`, label: ind.section })
      lastSection = ind.section
    }
    const fmtA = vA != null ? ind.fmt(vA) : '—'
    const fmtB = vB != null ? ind.fmt(vB) : '—'
    let winnerA = false, winnerB = false
    if (vA != null && vB != null) {
      const aWins = ind.higher ? vA > vB : vA < vB
      winnerA = aWins
      winnerB = !aWins
    }
    rows.push({ isSection: false, key: ind.key, label: ind.label, fmtA, fmtB, winnerA, winnerB })
  }
  return rows
})

// ── Formatters ───────────────────────────────────────────────────────────────
function fmtUsd(v: number | null | undefined): string {
  if (v == null) return '—'
  if (Math.abs(v) >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (Math.abs(v) >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  if (Math.abs(v) >= 1e6)  return `$${(v / 1e6).toFixed(0)}M`
  return `$${v.toLocaleString()}`
}

function fmtNum(v: number, decimals = 0): string {
  return v.toLocaleString(undefined, { maximumFractionDigits: decimals })
}

function fmtPop(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(0)}M`
  return v.toLocaleString()
}

function fmtBalance(t: any): string {
  const bal = (t.exports_usd || 0) - (t.imports_usd || 0)
  return (bal >= 0 ? '+' : '') + fmtUsd(Math.abs(bal)).replace('$', '') + (bal >= 0 ? ' surplus' : ' deficit')
}

// ── SEO ──────────────────────────────────────────────────────────────────────
const nameA = computed(() => countryA.value?.name || canonA)
const nameB = computed(() => countryB.value?.name || canonB)

const _seoTitle = computed(() => {
  const gdpA = countryA.value?.indicators?.gdp_usd
  const gdpB = countryB.value?.indicators?.gdp_usd
  if (gdpA && gdpB) {
    return `${nameA.value} vs ${nameB.value} GDP: ${fmtUsd(gdpA)} vs ${fmtUsd(gdpB)} — MetricsHour`
  }
  return `${nameA.value} vs ${nameB.value} Economy Comparison — MetricsHour`
})

const _seoDesc = computed(() => {
  const gdpA = countryA.value?.indicators?.gdp_usd
  const gdpB = countryB.value?.indicators?.gdp_usd
  const gA   = countryA.value?.indicators?.gdp_growth_pct
  const gB   = countryB.value?.indicators?.gdp_growth_pct
  const parts: string[] = []
  if (gdpA && gdpB) parts.push(`GDP: ${fmtUsd(gdpA)} vs ${fmtUsd(gdpB)}`)
  if (gA != null && gB != null) parts.push(`growth: ${gA.toFixed(1)}% vs ${gB.toFixed(1)}%`)
  const base = `${nameA.value} vs ${nameB.value} economy comparison.`
  return parts.length ? `${base} ${parts.join(', ')}. Inflation, interest rates, unemployment and trade data.` : base
})

const _canonUrl = computed(() => `https://metricshour.com/compare/${codeA}-vs-${codeB}/`)
const { public: { r2PublicUrl: _r2 } } = useRuntimeConfig()
const _ogImage  = `${_r2}/og/section/countries.png`

useSeoMeta({
  title:            _seoTitle,
  description:      _seoDesc,
  ogTitle:          _seoTitle,
  ogDescription:    _seoDesc,
  ogUrl:            _canonUrl,
  ogType:           'website',
  ogImage:          _ogImage,
  ogImageWidth:     '1200',
  ogImageHeight:    '630',
  twitterTitle:     _seoTitle,
  twitterDescription: _seoDesc,
  twitterImage:     _ogImage,
  twitterCard:      'summary_large_image',
  robots:           computed(() => (codeA.length === 2 && codeB.length === 2) ? 'index, follow' : 'noindex, follow'),
})

useHead(computed(() => {
  const a = countryA.value
  const b = countryB.value
  const ind = (c: any) => c?.indicators || {}

  const schemaItem = (c: any, code: string) => ({
    '@type': 'Country',
    name: c?.name || code.toUpperCase(),
    identifier: (c?.code || code).toUpperCase(),
  })

  const variableMeasured: any[] = []
  const SCHEMA_INDS: [string, string, string][] = [
    ['gdp_usd', 'GDP', 'USD'],
    ['gdp_growth_pct', 'GDP Growth Rate', '%'],
    ['inflation_pct', 'Inflation Rate', '%'],
    ['unemployment_pct', 'Unemployment Rate', '%'],
    ['govt_debt_pct_gdp', 'Government Debt (% GDP)', '% GDP'],
  ]
  for (const [key, label, unit] of SCHEMA_INDS) {
    const vA = ind(a)[key], vB = ind(b)[key]
    if (vA != null) variableMeasured.push({ '@type': 'PropertyValue', name: `${a?.name || canonA} ${label}`, value: vA, unitText: unit })
    if (vB != null) variableMeasured.push({ '@type': 'PropertyValue', name: `${b?.name || canonB} ${label}`, value: vB, unitText: unit })
  }

  return {
    link: [{ rel: 'canonical', href: _canonUrl.value }],
    script: [
      {
        type: 'application/ld+json',
        innerHTML: JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'WebPage',
          name: _seoTitle.value,
          url: _canonUrl.value,
          description: _seoDesc.value,
          about: [schemaItem(a, canonA), schemaItem(b, canonB)],
        }),
      },
      {
        type: 'application/ld+json',
        innerHTML: JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'Dataset',
          name: `${a?.name || canonA} vs ${b?.name || canonB} Economic Indicators`,
          description: `Side-by-side comparison of economic indicators for ${a?.name || canonA} and ${b?.name || canonB}. Includes GDP, inflation, interest rates, unemployment and more. Source: World Bank, IMF.`,
          url: _canonUrl.value,
          creator: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com' },
          license: 'https://metricshour.com/terms/',
          keywords: [`${a?.name || canonA} vs ${b?.name || canonB}`, `${canonA} ${canonB} comparison`, `${a?.name || canonA} economy`, `${b?.name || canonB} economy`],
          mainEntity: {
            '@type': 'ItemList',
            itemListElement: [
              { '@type': 'ListItem', position: 1, item: { '@type': 'Country', name: a?.name || canonA } },
              { '@type': 'ListItem', position: 2, item: { '@type': 'Country', name: b?.name || canonB } },
            ],
          },
          variableMeasured,
        }),
      },
      {
        type: 'application/ld+json',
        innerHTML: JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home',      item: 'https://metricshour.com/' },
            { '@type': 'ListItem', position: 2, name: 'Countries', item: 'https://metricshour.com/countries/' },
            { '@type': 'ListItem', position: 3, name: `${a?.name || canonA} vs ${b?.name || canonB}`, item: _canonUrl.value },
          ],
        }),
      },
      ...(a && b ? [{
        type: 'application/ld+json',
        innerHTML: JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'FAQPage',
          mainEntity: [
            {
              '@type': 'Question',
              name: `What is the GDP difference between ${a.name} and ${b.name}?`,
              acceptedAnswer: {
                '@type': 'Answer',
                text: (() => {
                  const gA = ind(a).gdp_usd, gB = ind(b).gdp_usd
                  if (!gA || !gB) return `GDP data for ${a.name} and ${b.name} is available on MetricsHour with World Bank sourced indicators.`
                  const larger = gA > gB ? a.name : b.name
                  const diff = Math.abs(gA - gB)
                  return `${a.name} GDP is ${fmtUsd(gA)} and ${b.name} GDP is ${fmtUsd(gB)}. ${larger} has the larger economy by ${fmtUsd(diff)}.`
                })(),
              },
            },
            {
              '@type': 'Question',
              name: `Which has a lower inflation rate, ${a.name} or ${b.name}?`,
              acceptedAnswer: {
                '@type': 'Answer',
                text: (() => {
                  const iA = ind(a).inflation_pct, iB = ind(b).inflation_pct
                  if (iA == null || iB == null) return `Inflation data is tracked on MetricsHour for both countries.`
                  const lower = iA < iB ? a.name : b.name
                  return `${a.name} inflation is ${iA.toFixed(1)}% and ${b.name} inflation is ${iB.toFixed(1)}%. ${lower} has the lower inflation rate.`
                })(),
              },
            },
            {
              '@type': 'Question',
              name: `How much bilateral trade happens between ${a.name} and ${b.name}?`,
              acceptedAnswer: {
                '@type': 'Answer',
                text: trade.value
                  ? `Bilateral trade between ${a.name} and ${b.name} totalled ${fmtUsd(trade.value.trade_value_usd)} in ${trade.value.year}, with ${a.name} exporting ${fmtUsd(trade.value.exports_usd)} and importing ${fmtUsd(trade.value.imports_usd)}.`
                  : `Detailed bilateral trade data between ${a.name} and ${b.name} is available on the MetricsHour trade page.`,
              },
            },
          ],
        }),
      }] : []),
    ],
  }
}))
</script>
