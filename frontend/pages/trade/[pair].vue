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
          Invalid country pair. Try <code class="text-gray-400">/trade/us-cn</code>
        </div>

        <template v-else>
          <div class="flex flex-col gap-4">
            <!-- Countries -->
            <div class="flex items-center gap-4 flex-wrap">
              <div class="flex items-center gap-3">
                <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-3xl">
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
                <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-3xl">
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
            {{ td ? ((td.balance_usd ?? 0) >= 0 ? 'surplus' : 'deficit') : '' }}
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

      <!-- Trade flow visualiser -->
      <div v-if="td" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6">
        <h2 class="text-sm font-bold text-white mb-4">Trade Flow</h2>
        <div class="flex items-center gap-3">
          <span class="text-2xl shrink-0">{{ data.exporter.flag }}</span>
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
          <span class="text-2xl shrink-0">{{ data.importer.flag }}</span>
        </div>
      </div>

      <!-- Top products side by side -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <span class="text-lg">{{ data.exporter.flag }}</span>
            <div>
              <div class="text-xs font-bold text-white">{{ data.exporter.name }} exports to</div>
              <div class="text-[10px] text-gray-500">{{ data.importer.name }}</div>
            </div>
            <span v-if="!td?.top_export_products?.length" class="ml-auto text-[10px] text-yellow-400 bg-yellow-900/20 border border-yellow-900 px-2 py-0.5 rounded">Pending</span>
          </div>
          <div v-if="td?.top_export_products?.length" class="space-y-3">
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
          <div v-else class="space-y-3">
            <div v-for="i in 5" :key="i" class="space-y-1">
              <div class="flex gap-2">
                <div class="flex-1 h-3 bg-[#1f2937] rounded animate-pulse" />
                <div class="w-14 h-3 bg-[#1f2937] rounded animate-pulse" />
              </div>
              <div class="h-1.5 bg-[#1f2937] rounded-full animate-pulse" :style="{ width: `${80 - i * 12}%` }"/>
            </div>
          </div>
        </div>

        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <div class="flex items-center gap-2 mb-4">
            <span class="text-lg">{{ data.importer.flag }}</span>
            <div>
              <div class="text-xs font-bold text-white">{{ data.importer.name }} exports to</div>
              <div class="text-[10px] text-gray-500">{{ data.exporter.name }}</div>
            </div>
            <span v-if="!td?.top_import_products?.length" class="ml-auto text-[10px] text-yellow-400 bg-yellow-900/20 border border-yellow-900 px-2 py-0.5 rounded">Pending</span>
          </div>
          <div v-if="td?.top_import_products?.length" class="space-y-3">
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
          <div v-else class="space-y-3">
            <div v-for="i in 5" :key="i" class="space-y-1">
              <div class="flex gap-2">
                <div class="flex-1 h-3 bg-[#1f2937] rounded animate-pulse" />
                <div class="w-14 h-3 bg-[#1f2937] rounded animate-pulse" />
              </div>
              <div class="h-1.5 bg-[#1f2937] rounded-full animate-pulse" :style="{ width: `${80 - i * 12}%` }"/>
            </div>
          </div>
        </div>
      </div>

      <!-- Country macro comparison -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-5">Country Comparison</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div v-for="c in [{ country: data.exporter, code: codeA }, { country: data.importer, code: codeB }]" :key="c.code">
            <div class="flex items-center gap-3 mb-3">
              <span class="text-2xl">{{ c.country.flag }}</span>
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

      <p class="text-xs text-gray-700 text-center">Data: UN Comtrade · World Bank · IMF</p>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()

const pair = route.params.pair as string
const parts = pair.split('-')
const codeA = parts[0] ?? ''
const codeB = parts[1] ?? ''

const { data, pending, error } = await useAsyncData(
  `trade-${pair}`,
  () => get<any>(`/api/trade/${codeA}/${codeB}`),
)

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

useSeoMeta({
  title: computed(() => data.value ? `${data.value.exporter.name}–${data.value.importer.name} Trade — MetricsHour` : 'Bilateral Trade — MetricsHour'),
  description: computed(() => data.value ? `${data.value.exporter.name} and ${data.value.importer.name} bilateral trade flows, top products, and GDP dependency.` : ''),
})
</script>
