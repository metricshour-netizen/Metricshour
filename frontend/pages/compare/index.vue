<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Country Economy Comparisons</h1>
      <p class="text-gray-500 text-sm mt-1">Side-by-side GDP, inflation, interest rates, unemployment and trade data for G20 economies.</p>
    </div>

    <!-- Search -->
    <div class="relative mb-6">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search country — US, China, Germany, Brazil..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
      />
      <button v-if="search" @click="search = ''" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 p-1.5">✕</button>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
      <NuxtLink
        v-for="pair in filteredPairs"
        :key="pair.slug"
        :to="`/compare/${pair.slug}`"
        class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500/60 rounded-xl p-4 transition-all hover:bg-[#131d2e] group flex items-center gap-3"
      >
        <span class="text-2xl">{{ pair.flagA }}</span>
        <span class="text-gray-600 text-sm">vs</span>
        <span class="text-2xl">{{ pair.flagB }}</span>
        <div class="ml-1 min-w-0">
          <div class="text-sm font-bold text-white group-hover:text-emerald-300 transition-colors truncate">{{ pair.nameA }} vs {{ pair.nameB }}</div>
          <div class="text-[10px] text-gray-600 font-mono">{{ pair.codeA.toUpperCase() }}–{{ pair.codeB.toUpperCase() }}</div>
        </div>
      </NuxtLink>
    </div>

    <div v-if="filteredPairs.length === 0" class="text-center py-16 text-gray-600 text-sm">
      No comparisons match "{{ search }}"
    </div>

    <p class="text-xs text-gray-700 mt-8">Data: World Bank. G20 economies only.</p>
  </main>
</template>

<script setup lang="ts">
const search = ref('')

// Featured G20 comparison pairs — enough to be useful, not spam
const PAIRS = [
  { codeA: 'us', codeB: 'cn', nameA: 'United States', nameB: 'China',         flagA: '🇺🇸', flagB: '🇨🇳' },
  { codeA: 'us', codeB: 'de', nameA: 'United States', nameB: 'Germany',       flagA: '🇺🇸', flagB: '🇩🇪' },
  { codeA: 'us', codeB: 'jp', nameA: 'United States', nameB: 'Japan',         flagA: '🇺🇸', flagB: '🇯🇵' },
  { codeA: 'us', codeB: 'gb', nameA: 'United States', nameB: 'United Kingdom',flagA: '🇺🇸', flagB: '🇬🇧' },
  { codeA: 'us', codeB: 'in', nameA: 'United States', nameB: 'India',         flagA: '🇺🇸', flagB: '🇮🇳' },
  { codeA: 'cn', codeB: 'in', nameA: 'China',         nameB: 'India',         flagA: '🇨🇳', flagB: '🇮🇳' },
  { codeA: 'cn', codeB: 'jp', nameA: 'China',         nameB: 'Japan',         flagA: '🇨🇳', flagB: '🇯🇵' },
  { codeA: 'cn', codeB: 'de', nameA: 'China',         nameB: 'Germany',       flagA: '🇨🇳', flagB: '🇩🇪' },
  { codeA: 'de', codeB: 'fr', nameA: 'Germany',       nameB: 'France',        flagA: '🇩🇪', flagB: '🇫🇷' },
  { codeA: 'de', codeB: 'gb', nameA: 'Germany',       nameB: 'United Kingdom',flagA: '🇩🇪', flagB: '🇬🇧' },
  { codeA: 'in', codeB: 'br', nameA: 'India',         nameB: 'Brazil',        flagA: '🇮🇳', flagB: '🇧🇷' },
  { codeA: 'jp', codeB: 'kr', nameA: 'Japan',         nameB: 'South Korea',   flagA: '🇯🇵', flagB: '🇰🇷' },
  { codeA: 'au', codeB: 'ca', nameA: 'Australia',     nameB: 'Canada',        flagA: '🇦🇺', flagB: '🇨🇦' },
  { codeA: 'fr', codeB: 'it', nameA: 'France',        nameB: 'Italy',         flagA: '🇫🇷', flagB: '🇮🇹' },
  { codeA: 'br', codeB: 'ru', nameA: 'Brazil',        nameB: 'Russia',        flagA: '🇧🇷', flagB: '🇷🇺' },
  { codeA: 'sa', codeB: 'ae', nameA: 'Saudi Arabia',  nameB: 'UAE',           flagA: '🇸🇦', flagB: '🇦🇪' },
  { codeA: 'mx', codeB: 'ca', nameA: 'Mexico',        nameB: 'Canada',        flagA: '🇲🇽', flagB: '🇨🇦' },
  { codeA: 'tr', codeB: 'ru', nameA: 'Turkey',        nameB: 'Russia',        flagA: '🇹🇷', flagB: '🇷🇺' },
  { codeA: 'id', codeB: 'au', nameA: 'Indonesia',     nameB: 'Australia',     flagA: '🇮🇩', flagB: '🇦🇺' },
  { codeA: 'za', codeB: 'ng', nameA: 'South Africa',  nameB: 'Nigeria',       flagA: '🇿🇦', flagB: '🇳🇬' },
].map(p => ({ ...p, slug: [p.codeA, p.codeB].sort().join('-vs-') }))

const filteredPairs = computed(() => {
  if (!search.value.trim()) return PAIRS
  const q = search.value.toLowerCase()
  return PAIRS.filter(p =>
    p.nameA.toLowerCase().includes(q) ||
    p.nameB.toLowerCase().includes(q) ||
    p.codeA.includes(q) ||
    p.codeB.includes(q)
  )
})

useSeoMeta({
  title: 'Country Economy Comparisons — MetricsHour',
  description: 'Compare G20 economies side-by-side: GDP, inflation, interest rates, unemployment, and bilateral trade. United States vs China, Germany vs France, and more.',
  ogTitle: 'Country Economy Comparisons — MetricsHour',
  ogDescription: 'Compare G20 economies side-by-side: GDP, inflation, interest rates, unemployment, and bilateral trade. United States vs China, Germany vs France, and more.',
  ogUrl: 'https://metricshour.com/compare/',
  ogType: 'website',
  ogImage: 'https://api.metricshour.com/og/section/countries.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterTitle: 'Country Economy Comparisons — MetricsHour',
  twitterDescription: 'Compare G20 economies side-by-side: GDP, inflation, interest rates, unemployment, and bilateral trade.',
  twitterImage: 'https://api.metricshour.com/og/section/countries.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/compare/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Country Economy Comparisons — MetricsHour',
      url: 'https://metricshour.com/compare/',
      description: 'Side-by-side comparison of G20 country economies: GDP, inflation, trade, and macro indicators.',
    }),
  }],
})
</script>
