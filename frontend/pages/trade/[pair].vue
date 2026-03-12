<template>
  <div>
    <!-- Hero band -->
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/trade" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Trade
        </NuxtLink>

        <div v-if="pending" class="flex items-center gap-6 h-20">
          <div class="w-16 h-16 bg-[#1f2937] rounded-xl animate-pulse"/>
          <div class="w-8 h-8 bg-[#1f2937] rounded animate-pulse"/>
          <div class="w-16 h-16 bg-[#1f2937] rounded-xl animate-pulse"/>
        </div>
        <div v-else-if="error || !data" class="text-red-400 text-sm py-4">
          Invalid country pair. Try <code class="text-gray-400">/trade/united-states--china</code>
        </div>

        <template v-else>
          <div class="flex flex-col gap-4">
            <!-- Countries -->
            <div class="flex items-center gap-4 flex-wrap">
              <h1 class="text-xl sm:text-2xl font-extrabold text-white leading-tight mb-1">
                {{ data.exporter.name }}–{{ data.importer.name }} Trade
              </h1>
              <div class="flex items-center gap-3">
                <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-3xl" aria-hidden="true">
                  {{ data.exporter.flag }}
                </div>
                <div>
                  <div class="text-lg font-extrabold text-white">{{ data.exporter.name }}</div>
                  <div class="text-xs text-emerald-400 font-mono font-bold">{{ codeA.toUpperCase() }}</div>
                </div>
              </div>
              <div class="flex flex-col items-center gap-1 px-2">
                <div class="text-2xl text-gray-500">↔</div>
                <div class="text-[10px] text-gray-600 uppercase tracking-wider">bilateral</div>
              </div>
              <div class="flex items-center gap-3">
                <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-3xl" aria-hidden="true">
                  {{ data.importer.flag }}
                </div>
                <div>
                  <div class="text-lg font-extrabold text-white">{{ data.importer.name }}</div>
                  <div class="text-xs text-emerald-400 font-mono font-bold">{{ codeB.toUpperCase() }}</div>
                </div>
              </div>
            </div>
            <!-- Balance callout -->
            <div v-if="td" class="sm:text-right">
              <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">Trade Balance</div>
              <div class="text-2xl sm:text-3xl font-extrabold tabular-nums" :class="(td.balance_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ fmtUsd(td.balance_usd) }}
              </div>
              <div class="text-xs text-gray-600 mt-1">
                {{ (td.balance_usd ?? 0) >= 0 ? `${codeA.toUpperCase()} surplus` : `${codeA.toUpperCase()} deficit` }}
                <span v-if="td.year"> · {{ td.year }}</span>
              </div>
              <div v-if="td.data_source" class="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded text-[10px] font-mono bg-[#111827] border border-[#1f2937] text-gray-500">
                <span class="text-emerald-700">◆</span> {{ td.data_source }}
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-8" v-if="data">

      <!-- Trade metrics -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">Total Trade</div>
          <div class="text-xl font-extrabold text-white tabular-nums">{{ td ? fmtUsd(td.trade_value_usd) : '—' }}</div>
          <div class="text-[10px] text-gray-600 mt-1">combined value</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">Balance</div>
          <div class="text-xl font-extrabold tabular-nums" :class="td ? ((td.balance_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400') : 'text-gray-700'">
            {{ td ? fmtUsd(td.balance_usd) : '—' }}
          </div>
          <div class="text-[10px] mt-1" :class="td ? ((td.balance_usd ?? 0) >= 0 ? 'text-emerald-700' : 'text-red-700') : 'text-gray-700'">
            {{ td ? ((td.balance_usd ?? 0) >= 0 ? `${codeA.toUpperCase()} surplus` : `${codeA.toUpperCase()} deficit`) : '' }}
          </div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">{{ codeA.toUpperCase() }} GDP share</div>
          <div class="text-xl font-extrabold text-white tabular-nums">
            {{ td?.exporter_gdp_share_pct != null ? `${td.exporter_gdp_share_pct.toFixed(1)}%` : '—' }}
          </div>
          <div class="text-[10px] text-gray-600 mt-1">of GDP</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wider mb-2">{{ codeB.toUpperCase() }} GDP share</div>
          <div class="text-xl font-extrabold text-white tabular-nums">
            {{ td?.importer_gdp_share_pct != null ? `${td.importer_gdp_share_pct.toFixed(1)}%` : '—' }}
          </div>
          <div class="text-[10px] text-gray-600 mt-1">of GDP</div>
        </div>
      </div>

      <!-- Page Summary -->
      <div v-if="pageSummary?.summary" class="page-summary bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-3 text-sm text-gray-300 leading-relaxed">
        {{ pageSummary.summary }}
      </div>

      <!-- Daily Trade Insights -->
      <div v-if="pageInsights?.length" class="mb-6">
        <!-- Latest: full card -->
        <div class="relative border rounded-lg p-4 overflow-hidden bg-[#0d1520] border-emerald-900/50 page-insight-latest">
          <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"/>
          <div class="flex items-start gap-3">
            <span class="text-base mt-0.5 shrink-0 text-emerald-500">◆</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                <span class="text-[10px] font-bold uppercase tracking-widest text-emerald-500">MetricsHour Intelligence</span>
                <span class="text-[10px] text-gray-600">· Daily trade take</span>
                <span class="text-[10px] text-gray-700 ml-auto">{{ new Date(pageInsights[0].generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</span>
              </div>
              <p class="text-sm leading-relaxed text-gray-200">{{ pageInsights[0].summary }}</p>
            </div>
          </div>
        </div>
        <!-- History: compact scrollable log -->
        <div v-if="pageInsights.length > 1" class="mt-1.5 border border-[#1a2030] rounded-lg overflow-hidden">
          <div class="divide-y divide-[#131b27]">
            <div
              v-for="(insight, i) in pageInsights.slice(1)"
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
            class="w-full px-3 py-2 text-[10px] text-gray-600 hover:text-emerald-400 bg-[#0a0d14] border-t border-[#1a2030] transition-colors text-left"
            @click="showAllInsights = !showAllInsights"
          >
            {{ showAllInsights ? '↑ Show less' : `↓ Read more (${pageInsights.length - 3} more insights)` }}
          </button>
        </div>
      </div>

      <!-- Trade flow visualiser -->
      <div v-if="td" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6">
        <h2 class="text-sm font-bold text-white mb-4">Trade Flow</h2>
        <div class="flex items-center gap-3">
          <span class="text-2xl shrink-0" aria-hidden="true">{{ data.exporter.flag }}</span>
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1.5">
              <div class="text-[10px] text-emerald-400 uppercase tracking-wider font-bold">Exports {{ fmtUsd(td.exports_usd) }}</div>
            </div>
            <div class="h-4 bg-[#1f2937] rounded-full overflow-hidden mb-1.5">
              <div class="h-full bg-emerald-500/70 rounded-full" :style="{ width: exportPct + '%' }"/>
            </div>
            <div class="h-4 bg-[#1f2937] rounded-full overflow-hidden">
              <div class="h-full bg-red-500/60 rounded-full" :style="{ width: importPct + '%' }"/>
            </div>
            <div class="flex items-center gap-2 mt-1.5">
              <div class="text-[10px] text-red-400 uppercase tracking-wider font-bold">Imports {{ fmtUsd(td.imports_usd) }}</div>
            </div>
          </div>
          <span class="text-2xl shrink-0" aria-hidden="true">{{ data.importer.flag }}</span>
        </div>
      </div>

      <!-- No bilateral data notice -->
      <div v-if="!td" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6 text-center">
        <div class="text-gray-500 text-sm mb-1">No bilateral trade data available for this corridor</div>
        <div class="text-gray-700 text-xs">Data coverage is limited to major trade flows reported via UN Comtrade. This pair may not report bilateral statistics.</div>
      </div>

      <!-- Top products side by side -->
      <div v-if="td" class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <span class="text-lg" aria-hidden="true">{{ data.exporter.flag }}</span>
            <div>
              <div class="text-xs font-bold text-white">{{ data.exporter.name }} exports to</div>
              <div class="text-[10px] text-gray-500">{{ data.importer.name }}</div>
            </div>
          </div>
          <div v-if="td.top_export_products?.length" class="space-y-3">
            <div v-for="(p, i) in td.top_export_products" :key="p.name">
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs text-gray-300 capitalize truncate mr-2">{{ p.name }}</span>
                <span class="text-xs font-bold text-white tabular-nums shrink-0">{{ fmtUsd(p.value_usd) }}</span>
              </div>
              <div class="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                <div class="h-full bg-emerald-500 rounded-full transition-all"
                  :style="{ width: `${productBarPct(td.top_export_products, p.value_usd)}%`, opacity: 1 - i * 0.12 }"/>
              </div>
            </div>
          </div>
          <div v-else class="text-xs text-gray-600 py-4 text-center">Product breakdown not available</div>
        </div>

        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <span class="text-lg" aria-hidden="true">{{ data.importer.flag }}</span>
            <div>
              <div class="text-xs font-bold text-white">{{ data.importer.name }} exports to</div>
              <div class="text-[10px] text-gray-500">{{ data.exporter.name }}</div>
            </div>
          </div>
          <div v-if="td.top_import_products?.length" class="space-y-3">
            <div v-for="(p, i) in td.top_import_products" :key="p.name">
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs text-gray-300 capitalize truncate mr-2">{{ p.name }}</span>
                <span class="text-xs font-bold text-white tabular-nums shrink-0">{{ fmtUsd(p.value_usd) }}</span>
              </div>
              <div class="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                <div class="h-full bg-blue-500 rounded-full transition-all"
                  :style="{ width: `${productBarPct(td.top_import_products, p.value_usd)}%`, opacity: 1 - i * 0.12 }"/>
              </div>
            </div>
          </div>
          <div v-else class="text-xs text-gray-600 py-4 text-center">Product breakdown not available</div>
        </div>
      </div>

      <!-- Country macro comparison -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-5">Country Comparison</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div v-for="c in [{ country: data.exporter, code: codeA }, { country: data.importer, code: codeB }]" :key="c.code">
            <div class="flex items-center gap-3 mb-3">
              <span class="text-2xl" aria-hidden="true">{{ c.country.flag }}</span>
              <div>
                <div class="text-sm font-bold text-white">{{ c.country.name }}</div>
                <NuxtLink :to="`/countries/${c.code}`" class="text-xs text-emerald-500 hover:text-emerald-400 transition-colors">Full macro data →</NuxtLink>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div class="bg-[#0d1117] rounded-lg p-3">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">GDP</div>
                <div class="text-sm font-bold text-white">{{ fmtGdp(c.country.indicators?.gdp_usd) }}</div>
              </div>
              <div class="bg-[#0d1117] rounded-lg p-3">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">GDP Growth</div>
                <div class="text-sm font-bold" :class="(c.country.indicators?.gdp_growth_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ c.country.indicators?.gdp_growth_pct?.toFixed(1) ?? '—' }}%
                </div>
              </div>
              <div class="bg-[#0d1117] rounded-lg p-3">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">Inflation</div>
                <div class="text-sm font-bold text-white">{{ c.country.indicators?.inflation_pct?.toFixed(1) ?? '—' }}%</div>
              </div>
              <div class="bg-[#0d1117] rounded-lg p-3">
                <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">Currency</div>
                <div class="text-sm font-bold text-white">{{ c.country.currency_code || '—' }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Stocks exposed to this trade corridor -->
      <div v-if="corridorStocks.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-1">Stocks exposed to this trade corridor</h2>
        <p class="text-xs text-gray-500 mb-4">
          Companies with revenue tied to {{ data.exporter.name }} or {{ data.importer.name }} — SEC EDGAR 10-K
        </p>
        <div class="flex flex-wrap gap-2">
          <NuxtLink
            v-for="s in corridorStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol.toLowerCase()}`"
            class="flex items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-700 rounded-lg px-3 py-2 transition-colors group"
          >
            <span class="text-xs font-mono font-bold text-emerald-400 group-hover:text-emerald-300">{{ s.symbol }}</span>
            <span class="text-[10px] text-gray-500 group-hover:text-gray-400 truncate max-w-[100px]">{{ s.name }}</span>
            <span class="text-[10px] text-emerald-700 tabular-nums shrink-0">{{ s.revenue_pct.toFixed(0) }}%</span>
          </NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center">
        Trade: {{ td?.data_source || 'UN Comtrade 2022' }} · Macro: World Bank · IMF
      </p>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { get, post } = useApi()
const { r2Fetch } = useR2Fetch()

const pair = route.params.pair as string
// Support both slug format (united-states--china) and ISO code format (us-cn)
const parts = pair.includes('--') ? pair.split('--') : pair.split('-')
const codeA = parts[0] ?? ''
const codeB = parts[parts.length - 1] ?? ''

const { data, pending, error } = useAsyncData(
  `trade-${pair}`,
  () => r2Fetch<any>(`snapshots/trade/${pair.toLowerCase()}.json`, `/api/trade/${codeA}/${codeB}`).catch(() => null),
)

const { data: pageSummary } = useAsyncData(
  `summary-trade-${codeA}-${codeB}`,
  () => get<any>(`/api/summaries/trade/${codeA.toUpperCase()}-${codeB.toUpperCase()}`).catch(() => null),
  { server: false },
)

const { data: pageInsights } = useAsyncData(
  `insights-trade-${codeA}-${codeB}`,
  () => get<any[]>(`/api/insights/trade/${codeA.toUpperCase()}-${codeB.toUpperCase()}`).catch(() => []),
  { server: false },
)

// Stocks exposed to this trade corridor (lazy, non-blocking)
const { data: stocksA } = useAsyncData(
  `corridor-stocks-a-${codeA}`,
  () => get<any[]>(`/api/countries/${codeA}/stocks`).catch(() => []),
  { server: false },
)
const { data: stocksB } = useAsyncData(
  `corridor-stocks-b-${codeB}`,
  () => get<any[]>(`/api/countries/${codeB}/stocks`).catch(() => []),
  { server: false },
)

const corridorStocks = computed(() => {
  const all = [...(stocksA.value || []), ...(stocksB.value || [])]
  const map = new Map<string, any>()
  for (const s of all) {
    if (!map.has(s.symbol) || s.revenue_pct > map.get(s.symbol).revenue_pct) {
      map.set(s.symbol, s)
    }
  }
  return [...map.values()].sort((a, b) => b.revenue_pct - a.revenue_pct).slice(0, 16)
})

const td = computed(() => data.value?.trade_data ?? null)

const totalFlow = computed(() => {
  if (!td.value) return 1
  return (td.value.exports_usd ?? 0) + (td.value.imports_usd ?? 0) || 1
})

const exportPct = computed(() => Math.round(((td.value?.exports_usd ?? 0) / totalFlow.value) * 100))
const importPct = computed(() => Math.round(((td.value?.imports_usd ?? 0) / totalFlow.value) * 100))

function productBarPct(products: any[], value: number): number {
  if (!products?.length) return 0
  const max = Math.max(...products.map((p: any) => p.value_usd ?? 0))
  return max ? Math.round((value / max) * 100) : 0
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

function fmtGdp(v: number | null | undefined): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

const { public: { r2PublicUrl } } = useRuntimeConfig()
const ogImageUrl = computed(() =>
  r2PublicUrl
    ? `${r2PublicUrl}/og/trade/${pair.toLowerCase()}.png`
    : `https://api.metricshour.com/og/trade/${pair.toLowerCase()}.png`,
)

// ── SEO helpers: inject real trade data for long-tail keyword ranking ─────────
const _seoTitle = computed(() => {
  if (!data.value) return 'Bilateral Trade — MetricsHour'
  const A = data.value.exporter.name
  const B = data.value.importer.name
  const vol = td.value?.trade_value_usd
  const year = td.value?.year
  if (vol && year) {
    const volStr = vol >= 1e12 ? `$${(vol / 1e12).toFixed(1)}T` : `$${(vol / 1e9).toFixed(0)}B`
    return `${A}–${B} Trade ${year}: ${volStr} Volume — MetricsHour`
  }
  return `${A}–${B} Bilateral Trade — MetricsHour`
})

const _seoDesc = computed(() => {
  if (!data.value) return ''
  const A = data.value.exporter.name
  const B = data.value.importer.name
  const vol    = td.value?.trade_value_usd
  const bal    = td.value?.balance_usd
  const year   = td.value?.year
  const source = td.value?.data_source ?? 'UN Comtrade'
  const prods  = (td.value?.top_export_products as any[] | undefined)
    ?.slice(0, 3).map((p: any) => p.name).join(', ')
  const parts: string[] = []
  if (vol && year) {
    const volStr = vol >= 1e12 ? `$${(vol / 1e12).toFixed(1)}T` : `$${(vol / 1e9).toFixed(0)}B`
    parts.push(`${A} and ${B} traded ${volStr} in ${year}`)
  } else {
    parts.push(`${A} and ${B} bilateral trade flows`)
  }
  if (bal != null) {
    const absB   = Math.abs(bal as number)
    const balStr = absB >= 1e9 ? `$${(absB / 1e9).toFixed(0)}B` : `$${(absB / 1e6).toFixed(0)}M`
    parts.push(`${A} ${(bal as number) >= 0 ? 'surplus' : 'deficit'} ${balStr}`)
  }
  if (prods) parts.push(`top exports: ${prods}`)
  parts.push(`Source: ${source}`)
  return parts.join('. ') + '.'
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: computed(() => `https://metricshour.com/trade/${data.value?.canonical_pair ?? pair}/`),
  ogType: 'website',
  ogImage: ogImageUrl,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  twitterImage: ogImageUrl,
  twitterCard: 'summary_large_image',
  // Prevent indexing of pages with no trade data — thin content
  // noindex only if the whole page failed to load — even without bilateral data, country context is valuable
  robots: computed(() => !data.value ? 'noindex, follow' : 'index, follow'),
})

function buildTradeFaqs(d: any, tdVal: any) {
  const faqs: { '@type': string; name: string; acceptedAnswer: { '@type': string; text: string } }[] = []
  const push = (q: string, a: string) => faqs.push({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })
  const A = d.exporter.name, B = d.importer.name

  if (tdVal?.trade_value_usd != null) {
    const v = tdVal.trade_value_usd
    const fv = v >= 1e12 ? `$${(v / 1e12).toFixed(1)} trillion` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)} billion` : `$${(v / 1e6).toFixed(0)} million`
    push(`How much trade is there between ${A} and ${B}?`, `Total bilateral trade between ${A} and ${B} is ${fv} (${tdVal.year ?? 'latest'}). Source: ${tdVal.data_source ?? 'UN Comtrade'}.`)
  }
  if (tdVal?.balance_usd != null) {
    const surplus = tdVal.balance_usd >= 0
    const abs = Math.abs(tdVal.balance_usd)
    const fv = abs >= 1e9 ? `$${(abs / 1e9).toFixed(1)} billion` : `$${(abs / 1e6).toFixed(0)} million`
    push(`What is the trade balance between ${A} and ${B}?`, `${A} runs a trade ${surplus ? 'surplus' : 'deficit'} of ${fv} with ${B} (${tdVal.year ?? 'latest'}). ${surplus ? `${A} exports more than it imports from ${B}.` : `${A} imports more than it exports to ${B}.`}`)
  }
  if (tdVal?.top_export_products?.length) {
    const products = tdVal.top_export_products.slice(0, 5).map((p: any) => p.name).join(', ')
    push(`What does ${A} export to ${B}?`, `${A}'s top exports to ${B} include: ${products}. Source: ${tdVal.data_source ?? 'UN Comtrade'}.`)
  }
  if (tdVal?.top_import_products?.length) {
    const products = tdVal.top_import_products.slice(0, 5).map((p: any) => p.name).join(', ')
    push(`What does ${B} export to ${A}?`, `${B}'s top exports to ${A} include: ${products}. Source: ${tdVal.data_source ?? 'UN Comtrade'}.`)
  }
  push(`Why is ${A}–${B} trade important?`, `${A} and ${B} bilateral trade reflects economic interdependence through goods, services, and supply chain links. MetricsHour tracks this corridor with GDP dependency ratios, product breakdowns, and balance data updated annually.`)
  return faqs
}

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/trade/${data.value?.canonical_pair ?? pair}/` }],
  script: data.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: `${data.value.exporter.name}–${data.value.importer.name} Trade — MetricsHour`,
        url: `https://metricshour.com/trade/${data.value?.canonical_pair ?? pair}/`,
        description: `${data.value.exporter.name} and ${data.value.importer.name} bilateral trade flows, top products, and GDP dependency. Source: UN Comtrade.`,
        speakable: {
          '@type': 'SpeakableSpecification',
          cssSelector: ['.page-summary', '.page-insight-latest'],
        },
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'Trade', item: 'https://metricshour.com/trade/' },
            { '@type': 'ListItem', position: 3, name: `${data.value.exporter.name}–${data.value.importer.name}`, item: `https://metricshour.com/trade/${data.value.canonical_pair}/` },
          ],
        },
      }),
    },
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: buildTradeFaqs(data.value, td.value),
      }),
    },
  ] : [],
})))

onMounted(() => {
  post('/api/track', { entity_type: 'trade', entity_code: pair.toUpperCase() }).catch(() => {})
})
const expandedInsights = ref<Set<string>>(new Set())
const showAllInsights = ref(false)
const toggleInsight = (key: string) => {
  const s = new Set(expandedInsights.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedInsights.value = s
}
</script>
