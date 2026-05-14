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
          <div class="w-10 h-10 rounded-xl bg-[#0d1520] border border-[#1f2937] flex items-center justify-center text-emerald-500 group-hover:border-emerald-800 transition-colors" aria-hidden="true">
            <svg v-if="tool.icon === 'screener'" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z"/></svg>
            <svg v-else-if="tool.icon === 'compare'" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
            <svg v-else-if="tool.icon === 'fx'" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/></svg>
            <svg v-else-if="tool.icon === 'embed'" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>
            <svg v-else-if="tool.icon === 'yield'" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/></svg>
            <svg v-else-if="tool.icon === 'calendar'" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
            <svg v-else-if="tool.icon === 'smartmoney'" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M17 14l2 2 4-4"/></svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
          </div>
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
    icon: 'screener',
    name: 'Global Risk Screener',
    desc: 'Filter stocks by China, EU, India, and emerging market revenue exposure. Built on SEC EDGAR data.',
    badge: 'Live',
  },
  {
    to: '/compare/',
    icon: 'compare',
    name: 'Country Compare',
    desc: 'Compare any two economies side by side — GDP, inflation, interest rates, unemployment, and trade.',
    badge: 'Live',
  },
  {
    to: '/tools/fx-calculator',
    icon: 'fx',
    name: 'FX Calculator',
    desc: 'Convert any currency using live rates. Supports 50+ world currencies with real-time data.',
    badge: 'Live',
  },
  {
    to: '/tools/embed',
    icon: 'embed',
    name: 'Embed Widget',
    desc: 'Embed MetricsHour charts and data on your website or blog with a single line of code.',
    badge: 'Live',
  },
  {
    to: '/yield-curve/',
    icon: 'yield',
    name: 'Yield Curve',
    desc: 'US Treasury yield curve updated daily. Spot inversions and macro signals in real time.',
    badge: 'Live',
  },
  {
    to: '/earnings/',
    icon: 'calendar',
    name: 'Earnings Calendar',
    desc: 'Upcoming and recent earnings results with EPS beats, revenue, and geographic revenue context.',
    badge: 'Live',
  },
  {
    to: '/smart-money/',
    icon: 'smartmoney',
    name: 'Smart Money Tracker',
    desc: 'Track what Buffett, Burry, and top funds are buying — with geographic risk context.',
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
