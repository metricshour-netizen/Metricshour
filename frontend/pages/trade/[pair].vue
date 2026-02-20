<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <NuxtLink to="/trade" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
      ← Trade
    </NuxtLink>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>
    <div v-else-if="error || !data" class="text-red-400 text-sm">
      Invalid country pair. Use two ISO codes separated by a dash, e.g.
      <code class="text-gray-400">/trade/us-cn</code>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="mb-8">
        <div class="flex items-center gap-5 mb-3 flex-wrap">
          <div class="flex items-center gap-2">
            <span class="text-5xl leading-none">{{ data.exporter.flag }}</span>
            <div>
              <div class="text-lg font-bold text-white">{{ data.exporter.name }}</div>
              <div class="text-xs text-gray-500">{{ codeA.toUpperCase() }}</div>
            </div>
          </div>
          <span class="text-2xl text-gray-600 font-light">↔</span>
          <div class="flex items-center gap-2">
            <span class="text-5xl leading-none">{{ data.importer.flag }}</span>
            <div>
              <div class="text-lg font-bold text-white">{{ data.importer.name }}</div>
              <div class="text-xs text-gray-500">{{ codeB.toUpperCase() }}</div>
            </div>
          </div>
        </div>
        <p class="text-sm text-gray-500">
          Bilateral trade relationship · UN Comtrade data
          <span v-if="td?.year"> · {{ td.year }}</span>
        </p>
      </div>

      <!-- Trade metrics -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Total Trade Value</div>
          <div class="font-medium text-sm" :class="td ? 'text-white' : 'text-gray-700 animate-pulse'">
            {{ td ? fmtUsd(td.trade_value_usd) : '——' }}
          </div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Trade Balance</div>
          <div
            class="font-medium text-sm"
            :class="td ? ((td.balance_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400') : 'text-gray-700 animate-pulse'"
          >{{ td ? fmtUsd(td.balance_usd) : '——' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">% of {{ codeA.toUpperCase() }} GDP</div>
          <div class="font-medium text-sm" :class="td ? 'text-white' : 'text-gray-700 animate-pulse'">
            {{ td?.exporter_gdp_share_pct != null ? `${td.exporter_gdp_share_pct.toFixed(1)}%` : '——' }}
          </div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">% of {{ codeB.toUpperCase() }} GDP</div>
          <div class="font-medium text-sm" :class="td ? 'text-white' : 'text-gray-700 animate-pulse'">
            {{ td?.importer_gdp_share_pct != null ? `${td.importer_gdp_share_pct.toFixed(1)}%` : '——' }}
          </div>
        </div>
      </div>

      <!-- Top products -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest">
              {{ data.exporter.name }} → {{ data.importer.name }}
            </h2>
            <span v-if="!td?.top_export_products?.length" class="text-xs text-yellow-400">Pending</span>
          </div>
          <div v-if="td?.top_export_products?.length" class="space-y-2.5">
            <div v-for="p in td.top_export_products" :key="p.name" class="flex items-center justify-between text-sm">
              <span class="text-gray-400 capitalize truncate mr-2">{{ p.name }}</span>
              <span class="text-white tabular-nums shrink-0">{{ fmtUsd(p.value_usd) }}</span>
            </div>
          </div>
          <div v-else class="space-y-2.5">
            <div v-for="i in 5" :key="i" class="flex items-center gap-3">
              <div class="flex-1 h-2.5 bg-[#1f2937] rounded animate-pulse" />
              <div class="w-12 h-2.5 bg-[#1f2937] rounded animate-pulse" />
            </div>
          </div>
        </div>

        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest">
              {{ data.importer.name }} → {{ data.exporter.name }}
            </h2>
            <span v-if="!td?.top_import_products?.length" class="text-xs text-yellow-400">Pending</span>
          </div>
          <div v-if="td?.top_import_products?.length" class="space-y-2.5">
            <div v-for="p in td.top_import_products" :key="p.name" class="flex items-center justify-between text-sm">
              <span class="text-gray-400 capitalize truncate mr-2">{{ p.name }}</span>
              <span class="text-white tabular-nums shrink-0">{{ fmtUsd(p.value_usd) }}</span>
            </div>
          </div>
          <div v-else class="space-y-2.5">
            <div v-for="i in 5" :key="i" class="flex items-center gap-3">
              <div class="flex-1 h-2.5 bg-[#1f2937] rounded animate-pulse" />
              <div class="w-12 h-2.5 bg-[#1f2937] rounded animate-pulse" />
            </div>
          </div>
        </div>
      </div>

      <!-- Country macro links -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div
          v-for="(c, code) in { [codeA]: data.exporter, [codeB]: data.importer }"
          :key="code"
          class="bg-[#111827] border border-[#1f2937] rounded-lg p-5"
        >
          <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">{{ c.name }}</h2>
          <NuxtLink
            :to="`/countries/${code}`"
            class="text-xs text-emerald-500 hover:text-emerald-400 transition-colors"
          >
            View macro data →
          </NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-600">Data: UN Comtrade · World Bank</p>
    </template>
  </main>
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

// Shorthand for the trade_data block
const td = computed(() => data.value?.trade_data ?? null)

function fmtUsd(v: number | null): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`
  if (abs >= 1e9)  return `${sign}$${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6)  return `${sign}$${(abs / 1e6).toFixed(0)}M`
  return `${sign}$${abs.toLocaleString()}`
}

useSeoMeta({
  title: computed(() =>
    data.value
      ? `${data.value.exporter.name}–${data.value.importer.name} Trade — MetricsHour`
      : 'Bilateral Trade — MetricsHour',
  ),
  description: computed(() =>
    data.value
      ? `${data.value.exporter.name} and ${data.value.importer.name} bilateral trade flows, top products, and GDP dependency. Source: UN Comtrade.`
      : '',
  ),
})
</script>
