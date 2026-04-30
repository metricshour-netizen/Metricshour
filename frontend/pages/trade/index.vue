<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Bilateral Trade</h1>
      <p class="text-gray-500 text-sm mt-1">
        2,700+ trade corridors · Trade flows, top products, dependency ratios · UN Comtrade data
      </p>
    </div>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>

    <template v-else-if="pairs?.length">
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
        <!-- Desktop header -->
        <div class="hidden sm:grid grid-cols-12 px-4 py-2 border-b border-[#1f2937] text-xs text-gray-500 uppercase tracking-wide">
          <span class="col-span-5">Trade Relationship</span>
          <span class="col-span-2 text-right">Trade Value</span>
          <span class="col-span-2 text-right">Balance</span>
          <span class="col-span-2 text-right">Year</span>
          <span class="col-span-1"></span>
        </div>
        <div class="divide-y divide-[#1f2937]">
          <NuxtLink
            v-for="p in visiblePairs"
            :key="p.id"
            :to="`/trade/${p.exporter?.code?.toLowerCase()}-${p.importer?.code?.toLowerCase()}`"
            class="block hover:bg-[#1a2235] transition-colors"
          >
            <!-- Mobile row -->
            <div class="flex items-center justify-between px-4 py-3 sm:hidden">
              <div class="flex items-center gap-1.5">
                <span class="text-base" aria-hidden="true">{{ p.exporter?.flag }}</span>
                <span class="text-xs font-medium text-gray-300">{{ p.exporter?.code }}</span>
                <span class="text-gray-600 text-xs mx-0.5">→</span>
                <span class="text-base" aria-hidden="true">{{ p.importer?.flag }}</span>
                <span class="text-xs font-medium text-gray-300">{{ p.importer?.code }}</span>
              </div>
              <div class="text-right">
                <div class="text-sm text-white tabular-nums font-medium">{{ fmtUsd(p.trade_value_usd) }}</div>
                <div class="text-xs tabular-nums" :class="(p.balance_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ fmtUsd(p.balance_usd) }}
                </div>
              </div>
            </div>
            <!-- Desktop row -->
            <div class="hidden sm:grid grid-cols-12 px-4 py-3 items-center">
              <div class="col-span-5 flex items-center gap-1.5">
                <span class="text-base" aria-hidden="true">{{ p.exporter?.flag }}</span>
                <span class="text-xs text-gray-400">{{ p.exporter?.code }}</span>
                <span class="text-gray-600 text-xs mx-1">→</span>
                <span class="text-base" aria-hidden="true">{{ p.importer?.flag }}</span>
                <span class="text-xs text-gray-400">{{ p.importer?.code }}</span>
              </div>
              <span class="col-span-2 text-xs text-right text-white tabular-nums">{{ fmtUsd(p.trade_value_usd) }}</span>
              <span
                class="col-span-2 text-xs text-right tabular-nums"
                :class="(p.balance_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'"
              >{{ fmtUsd(p.balance_usd) }}</span>
              <span class="col-span-2 text-xs text-right text-gray-500">{{ p.year }}</span>
              <span class="col-span-1 text-right text-emerald-500 text-xs">→</span>
            </div>
          </NuxtLink>
        </div>
      </div>

      <div v-if="visibleCount < pairs.length" class="mt-6 text-center">
        <button
          @click="loadMore"
          class="px-6 py-2.5 bg-[#111827] border border-[#1f2937] hover:border-emerald-700 text-sm text-gray-300 hover:text-white rounded-lg transition-colors"
        >
          Show more ({{ pairs.length - visibleCount }} remaining)
        </button>
      </div>
      <p class="text-xs text-gray-600 text-center mt-3">Showing {{ visibleCount }} of {{ pairs.length }} corridors</p>
    </template>

    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
        <div v-for="item in features" :key="item.title" class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <div class="text-xl mb-2">{{ item.icon }}</div>
          <h3 class="font-bold text-white text-sm mb-1">{{ item.title }}</h3>
          <p class="text-gray-500 text-xs">{{ item.desc }}</p>
        </div>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()

// server: false — 2,700+ rows is too large to embed in SSR HTML; sitemap covers all ≥$1B pairs
const { data: pairs, pending } = useAsyncData('trade-pairs',
  () => get<any[]>('/api/trade').catch(() => []),
  { server: false },
)

const PAGE_SIZE = 100
const visibleCount = ref(PAGE_SIZE)
const visiblePairs = computed(() => (pairs.value ?? []).slice(0, visibleCount.value))

function loadMore() {
  visibleCount.value = Math.min(visibleCount.value + PAGE_SIZE, (pairs.value ?? []).length)
}

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
  { icon: '⚖️', title: 'Trade Balance', desc: 'Total trade value, exports, imports, and bilateral balance for 2,700+ trade corridors.' },
  { icon: '📦', title: 'Top Products', desc: 'What countries actually trade — the top export and import products, not just dollar totals.' },
  { icon: '📈', title: 'GDP Dependency', desc: "Trade value as a % of each country's GDP — reveals true economic dependency between partners." },
]

useSeoMeta({
  title: 'Bilateral Trade Flows: 2,700+ Trade Corridors — MetricsHour',
  description: 'Trade flows between 2,700+ country pairs. Exports, imports, top products, and GDP dependency ratios sourced from UN Comtrade.',
  ogTitle: 'Bilateral Trade Flows: 2,700+ Trade Corridors — MetricsHour',
  ogDescription: 'Trade flows between 2,700+ country pairs. Exports, imports, top products, and GDP dependency ratios sourced from UN Comtrade.',
  ogUrl: 'https://metricshour.com/trade/',
  ogType: 'website',
  ogImage: 'https://cdn.metricshour.com/og/section/trade.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterTitle: 'Bilateral Trade Flows: 2,700+ Trade Corridors — MetricsHour',
  twitterDescription: 'Trade flows between 2,700+ country pairs. Exports, imports, top products, and GDP dependency ratios sourced from UN Comtrade.',
  twitterImage: 'https://cdn.metricshour.com/og/section/trade.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/trade/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Bilateral Trade — MetricsHour',
      url: 'https://metricshour.com/trade/',
      description: 'Trade flows between 2,700+ country pairs. Exports, imports, top products, and GDP dependency ratios from UN Comtrade.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
      mainEntity: {
        '@type': 'ItemList',
        itemListElement: (pairs.value ?? []).slice(0, 50).map((p: any, i: number) => ({
          '@type': 'ListItem',
          position: i + 1,
          name: `${p.exporter?.name} – ${p.importer?.name}`,
          item: `https://metricshour.com/trade/${p.exporter?.code?.toLowerCase()}-${p.importer?.code?.toLowerCase()}/`,
        })),
      },
    }),
  }],
})))
</script>
