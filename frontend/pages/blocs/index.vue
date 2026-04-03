<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-3xl font-extrabold text-white tracking-tight mb-2">Economic & Political Blocs</h1>
      <p class="text-gray-400 text-sm max-w-2xl">
        GDP, trade, and macro data aggregated across major international groupings — from the G7 to BRICS, ASEAN, NATO, and the EU.
      </p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <NuxtLink
        v-for="bloc in blocs"
        :key="bloc.slug"
        :to="`/blocs/${bloc.slug}/`"
        class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 hover:border-emerald-700 transition-colors group"
      >
        <div class="flex items-center gap-3 mb-3">
          <span class="text-3xl">{{ bloc.emoji }}</span>
          <div>
            <div class="text-white font-bold text-lg group-hover:text-emerald-400 transition-colors">{{ bloc.name }}</div>
            <div class="text-gray-500 text-xs">{{ bloc.full_name }}</div>
          </div>
        </div>
        <div class="text-gray-600 text-xs">Est. {{ bloc.founded }} · {{ bloc.hq }}</div>
      </NuxtLink>
    </div>
  </main>
</template>

<script setup lang="ts">
const { data: blocs } = await useFetch('/api/blocs', {
  baseURL: useRuntimeConfig().public.apiBase,
  default: () => [],
})

useSeoMeta({
  title: 'Economic & Political Blocs — G7, G20, EU, BRICS, NATO & More | MetricsHour',
  description: 'GDP, trade, and macro data for major international groupings: G7, G20, European Union, BRICS, NATO, ASEAN, OPEC, OECD, and more. Data from World Bank and IMF.',
  ogTitle: 'Economic & Political Blocs — MetricsHour',
  ogDescription: 'Aggregate GDP, trade and macro data for G7, G20, EU, BRICS, NATO, ASEAN, OPEC, OECD and Commonwealth.',
  ogUrl: 'https://metricshour.com/blocs/',
  ogType: 'website',
  twitterCard: 'summary_large_image',
  robots: 'index, follow',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/blocs/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Economic & Political Blocs — MetricsHour',
      url: 'https://metricshour.com/blocs/',
      description: 'GDP, trade, and macro data for major international groupings including G7, G20, EU, BRICS, NATO, ASEAN, OPEC, OECD, and Commonwealth.',
      breadcrumb: {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
          { '@type': 'ListItem', position: 2, name: 'Blocs', item: 'https://metricshour.com/blocs/' },
        ],
      },
    }),
  }],
})
</script>
