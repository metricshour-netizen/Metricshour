<template>
  <main class="max-w-7xl mx-auto px-4 py-16">
    <!-- Hero -->
    <div class="text-center mb-20">
      <h1 class="text-4xl md:text-6xl font-bold text-white mb-4 leading-tight">
        Global financial intelligence.<br>
        <span class="text-emerald-400">One place.</span>
      </h1>
      <p class="text-gray-400 text-xl max-w-2xl mx-auto mb-8">
        Connect stock geographic revenue, bilateral trade flows, and country macro data
        in 30 seconds — not 30 minutes across 4 websites.
      </p>
      <div class="flex justify-center gap-4 flex-wrap">
        <NuxtLink to="/countries" class="bg-emerald-500 hover:bg-emerald-400 text-black font-bold px-6 py-3 rounded transition-colors">
          Explore Countries →
        </NuxtLink>
        <NuxtLink to="/pricing" class="border border-gray-600 hover:border-gray-400 text-gray-300 px-6 py-3 rounded transition-colors">
          See Pricing
        </NuxtLink>
      </div>
    </div>

    <!-- What we connect -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-20">
      <div v-for="item in pillars" :key="item.title"
           class="bg-[#111827] border border-[#1f2937] rounded-lg p-6">
        <div class="text-2xl mb-3">{{ item.icon }}</div>
        <h3 class="font-bold text-white mb-1">{{ item.title }}</h3>
        <p class="text-gray-500 text-sm">{{ item.desc }}</p>
      </div>
    </div>

    <!-- G20 countries preview -->
    <div>
      <h2 class="text-xl font-bold text-white mb-4">G20 Countries</h2>
      <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>
      <div v-else-if="error" class="text-red-400 text-sm">Failed to load countries</div>
      <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        <NuxtLink
          v-for="c in countries"
          :key="c.code"
          :to="`/countries/${c.code.toLowerCase()}`"
          class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg p-3 transition-colors"
        >
          <div class="text-2xl mb-1">{{ c.flag }}</div>
          <div class="text-sm font-medium text-white">{{ c.name }}</div>
          <div class="text-xs text-gray-500">{{ c.currency_code }}</div>
        </NuxtLink>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
const pillars = [
  { icon: '📈', title: 'Stock Revenue Exposure', desc: 'See which countries each stock earns from — straight from SEC filings.' },
  { icon: '🌍', title: 'Country Macro', desc: 'GDP, inflation, debt, trade balance, and 80+ indicators per country.' },
  { icon: '⚖️', title: 'Bilateral Trade', desc: 'US-China, EU-Russia — every major trade relationship with top products.' },
  { icon: '🛢️', title: 'Commodities', desc: 'Oil, gold, metals — see how commodity moves ripple through economies.' },
]

const { get } = useApi()
const { data: countries, pending, error } = await useAsyncData('g20',
  () => get('/api/countries', { is_g20: 'true' })
)
</script>
