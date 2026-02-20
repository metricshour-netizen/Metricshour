<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white">Bilateral Trade</h1>
      <p class="text-gray-500 text-sm mt-1">
        380 country pairs · Trade flows, top products, dependency ratios · UN Comtrade data
      </p>
    </div>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>

    <!-- Real data table -->
    <template v-else-if="pairs?.length">
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
        <div class="grid grid-cols-12 px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide">
          <span class="col-span-5">Trade Relationship</span>
          <span class="col-span-2 text-right">Trade Value</span>
          <span class="col-span-2 text-right">Balance</span>
          <span class="col-span-2 text-right">Year</span>
          <span class="col-span-1"></span>
        </div>
        <div class="divide-y divide-[#1f2937]">
          <NuxtLink
            v-for="p in pairs"
            :key="p.id"
            :to="`/trade/${p.exporter?.code?.toLowerCase()}-${p.importer?.code?.toLowerCase()}`"
            class="grid grid-cols-12 px-4 py-3 hover:bg-[#1a2235] transition-colors items-center"
          >
            <div class="col-span-5 flex items-center gap-1.5">
              <span class="text-base">{{ p.exporter?.flag }}</span>
              <span class="text-xs text-gray-400">{{ p.exporter?.code }}</span>
              <span class="text-gray-600 text-xs mx-1">→</span>
              <span class="text-base">{{ p.importer?.flag }}</span>
              <span class="text-xs text-gray-400">{{ p.importer?.code }}</span>
            </div>
            <span class="col-span-2 text-xs text-right text-white tabular-nums">{{ fmtUsd(p.trade_value_usd) }}</span>
            <span
              class="col-span-2 text-xs text-right tabular-nums"
              :class="(p.balance_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'"
            >{{ fmtUsd(p.balance_usd) }}</span>
            <span class="col-span-2 text-xs text-right text-gray-500">{{ p.year }}</span>
            <span class="col-span-1 text-right text-emerald-500 text-xs">→</span>
          </NuxtLink>
        </div>
      </div>
    </template>

    <!-- No data yet -->
    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
        <div v-for="item in features" :key="item.title" class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <div class="text-xl mb-2">{{ item.icon }}</div>
          <h3 class="font-bold text-white text-sm mb-1">{{ item.title }}</h3>
          <p class="text-gray-500 text-xs">{{ item.desc }}</p>
        </div>
      </div>

      <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
        <div class="px-5 py-3 border-b border-[#1f2937] flex items-center justify-between">
          <span class="text-sm font-medium text-white">Major Trade Relationships</span>
          <span class="text-xs text-yellow-400">Pending UN Comtrade seeder</span>
        </div>
        <div class="divide-y divide-[#1f2937]">
          <div v-for="i in 6" :key="i" class="px-4 py-3 flex items-center gap-4">
            <div class="flex gap-1 shrink-0">
              <div class="w-7 h-7 bg-[#1f2937] rounded animate-pulse" />
              <div class="w-7 h-7 bg-[#1f2937] rounded animate-pulse" />
            </div>
            <div class="flex-1 space-y-1.5">
              <div class="h-3 bg-[#1f2937] rounded animate-pulse w-40" />
              <div class="h-2.5 bg-[#1f2937] rounded animate-pulse w-24" />
            </div>
            <div class="h-3 bg-[#1f2937] rounded animate-pulse w-16 shrink-0" />
          </div>
        </div>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()

const { data: pairs, pending } = await useAsyncData('trade-pairs',
  () => get<any[]>('/api/trade').catch(() => []),
)

function fmtUsd(v: number | null): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`
  if (abs >= 1e9)  return `${sign}$${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6)  return `${sign}$${(abs / 1e6).toFixed(0)}M`
  return `${sign}$${abs.toLocaleString()}`
}

const features = [
  {
    icon: '⚖️',
    title: 'Trade Balance',
    desc: 'Total trade value, exports, imports, and bilateral balance for 380 country pairs.',
  },
  {
    icon: '📦',
    title: 'Top Products',
    desc: 'What countries actually trade — the top export and import products, not just dollar totals.',
  },
  {
    icon: '📈',
    title: 'GDP Dependency',
    desc: "Trade value as a % of each country's GDP — reveals true economic dependency between partners.",
  },
]

useSeoMeta({
  title: 'Bilateral Trade — MetricsHour',
  description: 'Trade flows between 380 country pairs. Exports, imports, top products, and GDP dependency ratios sourced from UN Comtrade.',
})
</script>
