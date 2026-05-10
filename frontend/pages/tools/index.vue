<template>
  <main class="max-w-5xl mx-auto px-4 py-12">
    <div class="mb-10">
      <h1 class="text-2xl sm:text-3xl font-extrabold text-white">MetricsHour Tools</h1>
      <p class="text-gray-400 text-sm mt-2">Free tools for traders, investors, and researchers.</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      <NuxtLink
        v-for="tool in tools"
        :key="tool.to"
        :to="tool.to"
        class="group bg-[#111827] border border-[#1f2937] hover:border-emerald-500/50 rounded-2xl p-6 transition-all hover:bg-[#131d2e]"
      >
        <div class="flex items-start justify-between mb-4">
          <span class="text-3xl" aria-hidden="true">{{ tool.icon }}</span>
          <span
            class="text-[10px] font-bold px-2 py-1 rounded-full border"
            :class="tool.badge === 'Live' ? 'text-emerald-400 border-emerald-800 bg-emerald-900/20' : 'text-amber-400 border-amber-800 bg-amber-900/20'"
          >{{ tool.badge }}</span>
        </div>
        <h2 class="text-base font-bold text-white group-hover:text-emerald-400 transition-colors mb-1">{{ tool.name }}</h2>
        <p class="text-xs text-gray-500 leading-relaxed">{{ tool.desc }}</p>
        <div class="mt-4 flex items-center gap-1 text-xs text-emerald-600 group-hover:text-emerald-400 transition-colors font-medium">
          Open tool <span>→</span>
        </div>
      </NuxtLink>
    </div>

    <div class="mt-12 border border-[#1f2937] rounded-xl p-6 bg-[#0d1117]">
      <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-1">API Access</p>
      <p class="text-sm font-semibold text-white mb-1">Integrate MetricsHour data into your own applications.</p>
      <p class="text-xs text-gray-500 mb-4">RESTful API with JSON responses. Covers stocks, countries, trade, macro, FX, and more.</p>
      <NuxtLink to="/pricing/" class="text-xs text-emerald-400 hover:text-emerald-300 transition-colors font-medium">View API pricing →</NuxtLink>
    </div>
  </main>
</template>

<script setup lang="ts">
const tools = [
  {
    to: '/screener/',
    icon: '🔍',
    name: 'Global Risk Screener',
    desc: 'Filter stocks by China, EU, India, and emerging market revenue exposure. Built on SEC EDGAR data.',
    badge: 'Live',
  },
  {
    to: '/compare/',
    icon: '⚖️',
    name: 'Country Compare',
    desc: 'Compare any two economies side by side — GDP, inflation, interest rates, unemployment, and trade.',
    badge: 'Live',
  },
  {
    to: '/tools/fx-calculator',
    icon: '💱',
    name: 'FX Calculator',
    desc: 'Convert any currency using live rates. Supports 50+ world currencies with real-time data.',
    badge: 'Live',
  },
  {
    to: '/tools/embed',
    icon: '🖼',
    name: 'Embed Widget',
    desc: 'Embed MetricsHour charts and data on your website or blog with a single line of code.',
    badge: 'Live',
  },
  {
    to: '/yield-curve/',
    icon: '📈',
    name: 'Yield Curve',
    desc: 'US Treasury yield curve updated daily. Spot inversions and macro signals in real time.',
    badge: 'Live',
  },
  {
    to: '/earnings/',
    icon: '📅',
    name: 'Earnings Calendar',
    desc: 'Upcoming and recent earnings results with EPS beats, revenue, and geographic revenue context.',
    badge: 'Live',
  },
]

useSeoMeta({
  title: 'Free Financial Tools — MetricsHour',
  description: 'Free tools for traders, investors, and researchers. FX calculator, stock screener, country comparison, yield curve, earnings calendar, and embed widgets.',
  ogTitle: 'Free Financial Tools — MetricsHour',
  ogDescription: 'FX calculator, stock screener, country compare, yield curve, and more. All free.',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/tools/' }],
})
</script>
