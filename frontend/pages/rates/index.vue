<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">US Interest Rates & Macro Dashboard</h1>
      <p class="text-gray-500 text-sm mt-1">Fed funds rate · Treasury yields · CPI · M2 · Unemployment — sourced daily from FRED</p>
    </div>

    <!-- Quick links -->
    <div class="flex flex-wrap gap-2 mb-8">
      <NuxtLink to="/yield-curve/" class="text-xs bg-[#111827] border border-[#1f2937] hover:border-blue-500/60 text-gray-400 hover:text-blue-300 px-3 py-1.5 rounded-lg transition-all">
        📈 Yield Curve
      </NuxtLink>
      <NuxtLink to="/markets/" class="text-xs bg-[#111827] border border-[#1f2937] hover:border-emerald-500/60 text-gray-400 hover:text-emerald-300 px-3 py-1.5 rounded-lg transition-all">
        Markets Overview
      </NuxtLink>
      <NuxtLink to="/countries/us/" class="text-xs bg-[#111827] border border-[#1f2937] hover:border-emerald-500/60 text-gray-400 hover:text-emerald-300 px-3 py-1.5 rounded-lg transition-all">
        🇺🇸 US Economy
      </NuxtLink>
    </div>

    <!-- Loading -->
    <div v-if="pending" class="space-y-8">
      <div v-for="i in 3" :key="i" class="mb-8">
        <div class="h-4 w-32 bg-[#111827] rounded animate-pulse mb-4"/>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          <div v-for="j in 4" :key="j" class="h-24 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
        </div>
      </div>
    </div>

    <template v-else-if="data">
      <!-- Category sections -->
      <template v-for="(catLabel, catKey) in CATEGORY_META" :key="catKey">
        <div v-if="data.categories[catKey]?.length" class="mb-10">
          <!-- Header -->
          <div class="flex items-center gap-3 mb-4">
            <span class="text-lg">{{ catLabel.icon }}</span>
            <h2 class="text-sm font-extrabold text-white uppercase tracking-widest">{{ catLabel.label }}</h2>
            <div class="flex-1 h-px bg-[#1f2937]"/>
          </div>

          <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            <NuxtLink
              v-for="item in data.categories[catKey]"
              :key="item.series_id"
              :to="`/rates/${item.series_id.toLowerCase()}/`"
              class="bg-[#111827] border border-[#1f2937] hover:border-blue-500/60 rounded-xl p-4 transition-all hover:bg-[#131d2e] group"
            >
              <div class="text-[10px] text-gray-600 font-mono mb-2">{{ item.series_id }}</div>
              <div class="text-sm font-bold text-white mb-2 group-hover:text-blue-300 transition-colors leading-tight">
                {{ item.label }}
              </div>
              <div v-if="item.value != null" class="text-xl font-extrabold tabular-nums" :class="valueColor(item.series_id, item.value)">
                {{ fmtValue(item) }}
              </div>
              <div v-else class="text-xl font-extrabold text-gray-700">—</div>
              <div class="text-[10px] text-gray-600 mt-1">
                {{ item.period_date ? fmtDate(item.period_date) : 'No data' }}
                <span v-if="item.period_type" class="ml-1 text-gray-700">· {{ item.period_type }}</span>
              </div>
            </NuxtLink>
          </div>
        </div>
      </template>
    </template>

    <div v-else class="text-center py-16 text-gray-600 text-sm">
      No rates data yet — worker will populate on next run (daily 6:30am UTC).
    </div>

    <!-- Yield curve CTA -->
    <div class="mt-8 p-5 bg-[#0d1520] border border-blue-900/40 rounded-xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div>
        <h3 class="text-white font-semibold mb-1">Interactive Yield Curve</h3>
        <p class="text-gray-500 text-sm">Visualize the US Treasury yield curve across all maturities and track inversions over time.</p>
      </div>
      <NuxtLink to="/yield-curve/" class="flex-shrink-0 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold px-5 py-2.5 rounded-lg transition-colors">
        View Yield Curve →
      </NuxtLink>
    </div>

    <p class="text-xs text-gray-700 mt-6">Data: Federal Reserve Economic Data (FRED) · St. Louis Fed · Updated daily</p>
  </main>
</template>

<script setup lang="ts">
const { data, pending } = await useAsyncData('rates-dashboard',
  () => $fetch<any>('/api/rates/').catch(() => null),
)

const CATEGORY_META: Record<string, { label: string; icon: string }> = {
  rates:       { label: 'Interest Rates',   icon: '🏦' },
  yield_curve: { label: 'Treasury Yields',  icon: '📈' },
  inflation:   { label: 'Inflation',        icon: '📊' },
  money:       { label: 'Money Supply',     icon: '💵' },
  labor:       { label: 'Labor Market',     icon: '👷' },
}

function fmtValue(item: any): string {
  if (item.value == null) return '—'
  const v = item.value
  if (item.unit === '$B') {
    if (v >= 1000) return `$${(v / 1000).toFixed(1)}T`
    return `$${v.toFixed(0)}B`
  }
  if (item.unit === 'K') return `${(v / 1000).toFixed(0)}K`
  if (item.unit === 'index') return v.toFixed(1)
  return `${v.toFixed(2)}%`
}

function valueColor(seriesId: string, v: number): string {
  // Spread: negative = inverted = red; positive = green
  if (seriesId === 'T10Y2Y') return v < 0 ? 'text-red-400' : 'text-emerald-400'
  // High rates/inflation = warning amber
  if (['CPIAUCSL', 'CPILFESL'].includes(seriesId)) {
    if (v > 4) return 'text-red-400'
    if (v > 2.5) return 'text-amber-400'
    return 'text-emerald-400'
  }
  return 'text-blue-300'
}

function fmtDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

useSeoMeta({
  title: 'US Interest Rates & Macro Dashboard — MetricsHour',
  description: 'Track Fed funds rate, Treasury yields, CPI inflation, M2 money supply, and unemployment in one dashboard. Data updated daily from FRED.',
  ogTitle: 'US Interest Rates & Macro Dashboard — MetricsHour',
  ogDescription: 'Fed funds rate, Treasury yields, CPI, M2, jobless claims — updated daily from FRED.',
  ogUrl: 'https://metricshour.com/rates/',
  ogImage: 'https://cdn.metricshour.com/og/section/home.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterImage: 'https://cdn.metricshour.com/og/section/home.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})
useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/rates/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'US Interest Rates & Macro Dashboard — MetricsHour',
      url: 'https://metricshour.com/rates/',
      description: 'Federal Reserve rates, Treasury yields, CPI, M2, and unemployment data from FRED.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
    }),
  }],
})
</script>
