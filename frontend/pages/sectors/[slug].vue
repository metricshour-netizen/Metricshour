<template>
  <div>
    <!-- Hero -->
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/sectors/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Sectors
        </NuxtLink>

        <div v-if="pending" class="space-y-2">
          <div class="h-8 w-48 bg-[#1f2937] rounded animate-pulse"/>
          <div class="h-4 w-80 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="error || !sector" class="text-red-400 text-sm py-6">Sector not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-3xl shrink-0">
                {{ sector.icon }}
              </div>
              <div>
                <h1 class="text-3xl font-extrabold text-white tracking-tight mb-1">{{ sector.name }}</h1>
                <p class="text-gray-400 text-sm max-w-xl leading-relaxed">{{ sector.description }}</p>
                <p class="text-gray-600 text-xs mt-2">GICS Sector · Source: SEC EDGAR 10-K/10-Q filings</p>
              </div>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-1 gap-2 shrink-0 text-right">
              <div>
                <div class="text-2xl font-extrabold text-white tabular-nums">{{ fmtCap(sector.total_market_cap_usd) }}</div>
                <div class="text-xs text-gray-600">combined market cap</div>
              </div>
              <div>
                <div class="text-2xl font-extrabold text-white tabular-nums">{{ sector.stock_count }}</div>
                <div class="text-xs text-gray-600">tracked companies</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main v-if="sector" class="max-w-7xl mx-auto px-4 py-8">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">

        <!-- Left: stock table -->
        <div class="lg:col-span-2">
          <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Companies</h2>
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
            <!-- Header -->
            <div class="hidden sm:grid px-4 py-2 border-b border-[#1f2937] text-[10px] text-gray-600 uppercase tracking-wider"
                 style="grid-template-columns: 2rem 1fr 6rem 6rem 1.5rem">
              <span>#</span>
              <span>Company</span>
              <span class="text-right">Price</span>
              <span class="text-right">Mkt Cap</span>
              <span></span>
            </div>
            <div class="divide-y divide-[#1f2937]">
              <NuxtLink
                v-for="(s, i) in sector.stocks"
                :key="s.symbol"
                :to="`/stocks/${s.symbol.toLowerCase()}`"
                class="block hover:bg-[#1a2235] transition-colors"
              >
                <!-- Mobile -->
                <div class="flex items-center justify-between px-4 py-3 sm:hidden">
                  <div class="flex items-center gap-2.5 min-w-0">
                    <span v-if="s.country" class="text-base leading-none shrink-0">{{ s.country.flag }}</span>
                    <div class="min-w-0">
                      <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
                      <div class="text-xs text-gray-500 truncate max-w-[150px]">{{ s.name }}</div>
                    </div>
                  </div>
                  <div class="text-right shrink-0 ml-2">
                    <div class="text-sm font-bold tabular-nums font-mono text-white">{{ s.price ? fmtPrice(s.price.close) : '—' }}</div>
                    <div v-if="s.price?.change_pct != null" class="text-[10px] tabular-nums mt-0.5"
                         :class="s.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                      {{ s.price.change_pct >= 0 ? '▲' : '▼' }} {{ Math.abs(s.price.change_pct).toFixed(2) }}%
                    </div>
                  </div>
                </div>
                <!-- Desktop -->
                <div class="hidden sm:grid px-4 py-3 items-center"
                     style="grid-template-columns: 2rem 1fr 6rem 6rem 1.5rem">
                  <span class="text-xs text-gray-600">{{ i + 1 }}</span>
                  <div class="flex items-center gap-2 min-w-0 pr-2">
                    <span v-if="s.country" class="text-base leading-none shrink-0">{{ s.country.flag }}</span>
                    <div class="min-w-0">
                      <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
                      <div class="text-xs text-gray-500 truncate">{{ s.name }}</div>
                    </div>
                  </div>
                  <div class="text-right">
                    <div class="text-sm font-bold tabular-nums font-mono text-white">{{ s.price ? fmtPrice(s.price.close) : '—' }}</div>
                    <div v-if="s.price?.change_pct != null" class="text-[10px] tabular-nums mt-0.5"
                         :class="s.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                      {{ s.price.change_pct >= 0 ? '▲' : '▼' }} {{ Math.abs(s.price.change_pct).toFixed(2) }}%
                    </div>
                  </div>
                  <span class="text-xs text-right text-gray-400 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
                  <span class="text-right text-violet-700 text-xs">→</span>
                </div>
              </NuxtLink>
            </div>
          </div>
        </div>

        <!-- Right: geographic exposure + related links -->
        <div class="space-y-6">

          <!-- Top countries exposed -->
          <div v-if="sector.top_countries?.length">
            <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Geographic Revenue Exposure</h2>
            <div class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
              <div class="divide-y divide-[#1f2937]">
                <NuxtLink
                  v-for="c in sector.top_countries"
                  :key="c.code"
                  :to="`/countries/${c.code.toLowerCase()}`"
                  class="flex items-center justify-between px-4 py-3 hover:bg-[#1a2235] transition-colors"
                >
                  <div class="flex items-center gap-2">
                    <span class="text-base leading-none">{{ c.flag }}</span>
                    <div>
                      <div class="text-sm text-white font-medium">{{ c.name }}</div>
                      <div class="text-[10px] text-gray-600">{{ c.stock_count }} stock{{ c.stock_count > 1 ? 's' : '' }} exposed</div>
                    </div>
                  </div>
                  <div class="text-right">
                    <div class="text-sm font-bold tabular-nums text-emerald-400">{{ c.total_pct.toFixed(0) }}%</div>
                    <div class="text-[10px] text-gray-600">total pct</div>
                  </div>
                </NuxtLink>
              </div>
            </div>
          </div>

          <!-- Browse other sectors -->
          <div>
            <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Other Sectors</h2>
            <div class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
              <div class="divide-y divide-[#1f2937]">
                <NuxtLink
                  v-for="other in otherSectors"
                  :key="other.slug"
                  :to="`/sectors/${other.slug}`"
                  class="flex items-center justify-between px-4 py-2.5 hover:bg-[#1a2235] transition-colors"
                >
                  <span class="flex items-center gap-2 text-sm text-gray-300">
                    <span>{{ other.icon }}</span> {{ other.name }}
                  </span>
                  <span class="text-xs text-gray-600">{{ other.stock_count }}</span>
                </NuxtLink>
              </div>
            </div>
          </div>

          <!-- Data source note -->
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4 text-xs text-gray-600 leading-relaxed">
            Geographic revenue data sourced from SEC EDGAR 10-K and 10-Q filings.
            Market cap and prices updated every 15 minutes during market hours.
          </div>
        </div>

      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const slug = computed(() => route.params.slug as string)

const { data: sector, pending, error } = await useFetch<any>(() => `/api/assets/sectors/${slug.value}`, {
  baseURL: useRuntimeConfig().public.apiBase,
})
if (!sector.value) throw createError({ statusCode: 404, statusMessage: 'Sector not found' })

const { data: allSectors } = useFetch<any[]>('/api/assets/sectors', {
  key: 'sectors-list',
  baseURL: useRuntimeConfig().public.apiBase,
  default: () => [],
})

const otherSectors = computed(() =>
  (allSectors.value ?? []).filter((s: any) => s.slug !== slug.value).slice(0, 8)
)

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtPrice(v: number): string {
  if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  if (v >= 1)    return `$${v.toFixed(2)}`
  return `$${v.toFixed(4)}`
}

useSeoMeta(computed(() => ({
  title: sector.value ? `${sector.value.name} Sector Stocks — MetricsHour` : 'Sector — MetricsHour',
  description: sector.value
    ? `${sector.value.name} sector: ${sector.value.stock_count} companies tracked with geographic revenue exposure from SEC EDGAR. ${sector.value.description}`
    : '',
  ogTitle: sector.value ? `${sector.value.name} Sector — MetricsHour` : 'Sector',
  ogUrl: `https://metricshour.com/sectors/${slug.value}/`,
  ogType: 'website',
})))

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/sectors/${slug.value}/` }],
  script: sector.value ? [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: `${sector.value.name} Sector — MetricsHour`,
      url: `https://metricshour.com/sectors/${slug.value}/`,
      description: sector.value.description,
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
      mainEntity: {
        '@type': 'ItemList',
        itemListElement: (sector.value.stocks ?? []).map((s: any, i: number) => ({
          '@type': 'ListItem',
          position: i + 1,
          name: s.name || s.symbol,
          item: `https://metricshour.com/stocks/${s.symbol.toLowerCase()}/`,
        })),
      },
    }),
  }] : [],
})))
</script>
