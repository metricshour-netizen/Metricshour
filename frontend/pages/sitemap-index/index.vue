<template>
  <main class="max-w-4xl mx-auto px-4 py-12">
    <h1 class="text-2xl font-bold text-white mb-2">Site Index</h1>
    <p class="text-gray-500 text-sm mb-10">All major sections of MetricsHour.com</p>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
      <div v-for="section in sections" :key="section.title" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
        <h2 class="text-sm font-bold text-white mb-1">{{ section.title }}</h2>
        <p class="text-xs text-gray-500 mb-3">{{ section.description }}</p>
        <NuxtLink :to="section.href" class="text-emerald-500 text-xs hover:text-emerald-400 transition-colors">
          {{ section.href }} →
        </NuxtLink>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
const sections = [
  { title: 'Stocks', href: '/stocks/', description: 'Geographic revenue exposure for 775+ global stocks from SEC EDGAR 10-K filings.' },
  { title: 'Countries', href: '/countries/', description: 'Macro data for 196 countries: GDP, inflation, trade, and 80+ economic indicators.' },
  { title: 'Trade', href: '/trade/', description: 'Bilateral trade flows between countries — 2,700+ corridors with UN Comtrade data.' },
  { title: 'Crypto', href: '/crypto/', description: 'Cryptocurrency prices and market data for 50+ assets.' },
  { title: 'ETFs', href: '/etfs/', description: 'Exchange-traded fund data and geographic exposure analysis.' },
  { title: 'FX', href: '/fx/', description: 'Foreign exchange rates for major and emerging market currency pairs.' },
  { title: 'Commodities', href: '/commodities/', description: 'Commodity prices: oil, gold, silver, natural gas, agricultural products.' },
  { title: 'Rates & Yield Curve', href: '/rates/', description: 'US Federal Reserve interest rates and FRED macro data series.' },
  { title: 'Earnings Calendar', href: '/earnings/', description: 'Upcoming and recent earnings events for major public companies.' },
  { title: 'Global Screener', href: '/screener/', description: 'Screen stocks by geographic revenue exposure — China, Europe, domestic-only, and more.' },
  { title: 'Smart Money', href: '/smart-money/', description: 'Track 13F filings from Buffett, Burry, Dalio, and top institutional funds.' },
  { title: 'Lens', href: '/lens/', description: 'Deep revenue lens pages showing exact country-level exposure per stock.' },
  { title: 'Blog', href: '/blog/', description: 'Analysis and insights on trade, macro, and global equity markets.' },
  { title: 'Markets', href: '/markets/', description: 'Real-time overview across stocks, crypto, FX, and commodities.' },
]

useSeoMeta({
  title: 'Site Index — MetricsHour',
  description: 'Complete index of all major sections on MetricsHour.com: stocks, countries, trade, crypto, ETFs, FX, commodities, rates, screener, smart money, and blog.',
  robots: 'index, follow',
})
useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/sitemap-index/' }],
})
</script>
