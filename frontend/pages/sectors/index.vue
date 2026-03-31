<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white">Market Sectors</h1>
      <p class="text-gray-500 text-sm mt-1">Browse stocks by GICS sector · Geographic revenue exposure · SEC EDGAR data</p>
    </div>

    <div v-if="pending" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 9" :key="i" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 animate-pulse">
        <div class="h-10 w-10 bg-[#1f2937] rounded-lg mb-3"/>
        <div class="h-5 w-32 bg-[#1f2937] rounded mb-2"/>
        <div class="h-3 w-full bg-[#1f2937] rounded mb-1"/>
        <div class="h-3 w-3/4 bg-[#1f2937] rounded"/>
      </div>
    </div>

    <div v-else-if="error" class="text-red-400 text-sm">Failed to load sectors.</div>

    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <NuxtLink
        v-for="s in sectors"
        :key="s.slug"
        :to="`/sectors/${s.slug}`"
        class="bg-[#111827] border border-[#1f2937] hover:border-violet-500 rounded-xl p-5 transition-all group"
      >
        <div class="flex items-start justify-between mb-3">
          <span class="text-3xl" aria-hidden="true">{{ s.icon }}</span>
          <span class="text-[10px] font-mono text-gray-600 bg-[#1f2937] px-2 py-1 rounded">
            {{ s.stock_count }} stocks
          </span>
        </div>
        <h2 class="text-white font-bold text-base mb-1 group-hover:text-violet-400 transition-colors">{{ s.name }}</h2>
        <p class="text-gray-500 text-xs leading-relaxed mb-3">{{ s.description }}</p>
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-600 tabular-nums">
            <span class="text-gray-400 font-semibold">{{ fmtCap(s.total_market_cap_usd) }}</span> total cap
          </span>
          <span class="text-violet-600 text-xs group-hover:text-violet-400 transition-colors">Explore →</span>
        </div>
      </NuxtLink>
    </div>

    <!-- Legend -->
    <div class="mt-12 border-t border-[#1f2937] pt-8">
      <h2 class="text-sm font-semibold text-gray-400 mb-4">Entity link color guide</h2>
      <div class="flex flex-wrap gap-4 text-xs">
        <span><a class="link-stock">Stock</a> — blue</span>
        <span><a class="link-country">Country</a> — green</span>
        <span><a class="link-corridor">Trade corridor</a> — amber</span>
        <span><a class="link-sector">Sector</a> — violet</span>
        <span><a class="link-index">Index</a> — cyan</span>
        <span><a class="link-commodity">Commodity</a> — orange</span>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
const { data: sectors, pending, error } = useFetch<any[]>('/api/assets/sectors', {
  baseURL: useRuntimeConfig().public.apiBase,
  default: () => [],
})

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

useSeoMeta({
  title: 'Market Sectors — MetricsHour',
  description: 'Browse stocks by GICS sector. Technology, Healthcare, Financials, Energy, and more — with geographic revenue data from SEC EDGAR.',
  ogTitle: 'Market Sectors — MetricsHour',
  ogDescription: 'Browse stocks by GICS sector with geographic revenue exposure from SEC EDGAR 10-K filings.',
  ogUrl: 'https://metricshour.com/sectors/',
  ogType: 'website',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/sectors/' }],
})
</script>
