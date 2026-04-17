<template>
  <div>
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-10">
        <NuxtLink to="/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">← Home</NuxtLink>
        <div class="flex items-center gap-4 mb-3">
          <span class="text-4xl" aria-hidden="true">🇳🇬</span>
          <div>
            <h1 class="text-3xl font-extrabold text-white tracking-tight">Nigerian Stocks</h1>
            <p class="text-gray-400 text-sm mt-1">NGX (Nigerian Exchange) and LSE-listed Nigerian companies</p>
          </div>
        </div>
        <p class="text-gray-500 text-xs max-w-2xl">
          Nigerian equities from the Nigerian Exchange Group (NGX) — Africa's largest economy by GDP.
          LSE dual-listings (Seplat Energy, Airtel Africa) show live prices in GBp. NGX-only stocks
          are listed for reference; live prices require a local data feed.
        </p>
      </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-8">
      <!-- Stats -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Listed Stocks</div>
          <div class="text-white font-bold text-xl">{{ allStocks?.length || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Live Prices</div>
          <div class="text-white font-bold text-xl">{{ liveCount }}</div>
          <div class="text-[10px] text-gray-600 mt-0.5">LSE dual-listings</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Exchange</div>
          <div class="text-white font-bold text-xl">NGX · LSE</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Currencies</div>
          <div class="text-white font-bold text-xl">NGN · GBp</div>
        </div>
      </div>

      <!-- Search + sector filter -->
      <div class="flex flex-wrap gap-3 mb-5">
        <input
          v-model="search"
          type="text"
          placeholder="Search by name or ticker..."
          class="w-full sm:w-80 bg-[#111827] border border-[#1f2937] text-white text-sm px-4 py-2 rounded-lg placeholder-gray-600 focus:outline-none focus:border-emerald-700"
        />
        <div class="flex flex-wrap gap-2">
          <button
            v-for="s in sectors"
            :key="s"
            @click="activeSector = activeSector === s ? '' : s"
            class="text-xs px-3 py-1.5 rounded-lg border transition-colors"
            :class="activeSector === s
              ? 'bg-emerald-900/40 border-emerald-700 text-emerald-400'
              : 'border-[#1f2937] text-gray-500 hover:border-emerald-800 hover:text-gray-300'"
          >{{ s }}</button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="pending" class="space-y-2">
        <div v-for="i in 15" :key="i" class="h-12 bg-[#111827] rounded-lg animate-pulse" />
      </div>

      <!-- Empty -->
      <div v-else-if="!filtered?.length" class="text-center py-16 text-gray-600">
        <div class="text-3xl mb-3">📊</div>
        <p class="text-sm">{{ search ? 'No stocks match your search.' : 'No Nigerian stocks found — seed the database first.' }}</p>
      </div>

      <!-- Table -->
      <div v-else class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#1f2937]">
              <th class="text-left text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3">Ticker</th>
              <th class="text-left text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3">Name</th>
              <th class="text-right text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3">Price</th>
              <th class="text-right text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3 hidden sm:table-cell">Change</th>
              <th class="text-left text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3 hidden md:table-cell">Sector</th>
              <th class="text-right text-[10px] text-gray-500 uppercase tracking-wider px-4 py-3 hidden md:table-cell">Exchange</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in paginated"
              :key="s.id"
              class="border-b border-[#1a2030] hover:bg-[#0d1117] transition-colors cursor-pointer"
              @click="navigateTo(stockUrl(s))"
            >
              <td class="px-4 py-3 font-mono text-xs text-emerald-400 whitespace-nowrap">{{ s.symbol }}</td>
              <td class="px-4 py-3 text-gray-200 truncate max-w-[180px]">{{ s.name }}</td>
              <td class="px-4 py-3 text-right font-bold text-white tabular-nums whitespace-nowrap">
                <template v-if="s.price">
                  <span class="text-[10px] text-gray-500 mr-0.5">{{ s.currency === 'GBp' ? 'p' : '₦' }}</span>{{ s.price.close?.toFixed(2) }}
                </template>
                <span v-else class="text-gray-600">—</span>
              </td>
              <td class="px-4 py-3 text-right tabular-nums hidden sm:table-cell"
                :class="s.price?.change_pct != null ? (s.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400') : 'text-gray-600'">
                {{ s.price?.change_pct != null ? `${s.price.change_pct >= 0 ? '+' : ''}${s.price.change_pct.toFixed(2)}%` : '—' }}
              </td>
              <td class="px-4 py-3 text-gray-500 text-xs hidden md:table-cell">{{ s.sector || '—' }}</td>
              <td class="px-4 py-3 text-right hidden md:table-cell">
                <span class="text-[10px] px-2 py-0.5 rounded border"
                  :class="s.exchange === 'LSE' ? 'border-blue-900 text-blue-400' : 'border-emerald-900 text-emerald-600'">
                  {{ s.exchange }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-between px-4 py-3 border-t border-[#1f2937]">
          <button
            @click="page = Math.max(1, page - 1)"
            :disabled="page === 1"
            class="text-xs px-3 py-1.5 rounded border border-[#1f2937] text-gray-400 disabled:opacity-30 hover:border-emerald-700 hover:text-emerald-400 transition-colors"
          >← Prev</button>
          <span class="text-xs text-gray-600">Page {{ page }} / {{ totalPages }}</span>
          <button
            @click="page = Math.min(totalPages, page + 1)"
            :disabled="page === totalPages"
            class="text-xs px-3 py-1.5 rounded border border-[#1f2937] text-gray-400 disabled:opacity-30 hover:border-emerald-700 hover:text-emerald-400 transition-colors"
          >Next →</button>
        </div>
      </div>

      <!-- Notes -->
      <div class="mt-6 grid sm:grid-cols-2 gap-4">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-xs font-semibold text-white mb-2">About Nigeria's Stock Market</div>
          <p class="text-xs text-gray-500 leading-relaxed">
            The Nigerian Exchange Group (NGX) is sub-Saharan Africa's third-largest bourse by market cap.
            Nigeria's economy — Africa's largest by GDP — is driven by oil & gas, banking, telecoms, and FMCG.
            The NGX All-Share Index tracks 150+ listed companies.
          </p>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-xs font-semibold text-white mb-2">Dual-Listed Companies</div>
          <p class="text-xs text-gray-500 leading-relaxed">
            Seplat Energy (SEPL.L) and Airtel Africa (AAF.L) are dual-listed on the London Stock Exchange
            and the NGX. LSE prices are in GBp (pence) — divide by 100 for GBP.
          </p>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center mt-6">
        LSE prices via Yahoo Finance · NGX prices not available via free APIs · Updated daily
      </p>
    </main>
  </div>
</template>

<script setup lang="ts">
const { get } = useApi()

const { data: allStocks, pending } = await useAsyncData(
  'nigeria-stocks',
  async () => {
    const [ngx, lse] = await Promise.all([
      get<any[]>('/api/assets', { type: 'stock', exchange: 'NGX', limit: 200 }).catch(() => []),
      get<any[]>('/api/assets', { type: 'stock', exchange: 'LSE', country_code: 'NG', limit: 50 }).catch(() => []),
    ])
    return [...(lse || []), ...(ngx || [])]
  },
)

const search = ref('')
const activeSector = ref('')
const page = ref(1)
const PER_PAGE = 30

const sectors = computed(() => {
  const s = new Set<string>()
  allStocks.value?.forEach(st => { if (st.sector) s.add(st.sector) })
  return [...s].sort()
})

const liveCount = computed(() =>
  allStocks.value?.filter(s => s.price != null).length ?? 0,
)

const filtered = computed(() => {
  let list = allStocks.value || []
  if (activeSector.value) list = list.filter(s => s.sector === activeSector.value)
  if (!search.value) return list
  const q = search.value.toLowerCase()
  return list.filter(s =>
    s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q),
  )
})

watch([search, activeSector], () => { page.value = 1 })

const totalPages = computed(() => Math.ceil(filtered.value.length / PER_PAGE))
const paginated  = computed(() => {
  const start = (page.value - 1) * PER_PAGE
  return filtered.value.slice(start, start + PER_PAGE)
})

function stockUrl(s: any) {
  return `/nigeria/${s.symbol.toLowerCase()}/`
}

const { public: { r2PublicUrl } } = useRuntimeConfig()
const ogImage = r2PublicUrl
  ? `${r2PublicUrl}/og/section/nigeria.png`
  : 'https://cdn.metricshour.com/og/section/nigeria.png'

useSeoMeta({
  title: 'Nigerian Stocks — NGX & LSE Listed Companies | MetricsHour',
  description: 'Nigerian Exchange (NGX) and LSE-listed stocks with live prices — Seplat Energy (SEPL.L), Airtel Africa (AAF.L), Dangote Cement, MTN Nigeria, Zenith Bank.',
  ogTitle: 'Nigerian Stocks — NGX & LSE | MetricsHour',
  ogDescription: 'Nigerian Exchange (NGX) equities and LSE dual-listed companies — Seplat Energy, Airtel Africa, Dangote Cement, MTN Nigeria, Zenith Bank — with live prices.',
  ogUrl: 'https://metricshour.com/nigeria/',
  ogType: 'website',
  ogImage,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  ogImageType: 'image/png',
  twitterCard: 'summary_large_image',
  twitterTitle: 'Nigerian Stocks | MetricsHour',
  twitterDescription: 'NGX & LSE-listed Nigerian equities with live prices — Seplat Energy, Airtel Africa, Dangote Cement and more.',
  twitterImage: ogImage,
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/nigeria/' }],
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: 'Nigerian Stocks — NGX & LSE Listed Companies',
        description: 'Nigerian Exchange (NGX) and LSE dual-listed Nigerian stocks including Seplat Energy, Airtel Africa, Dangote Cement, MTN Nigeria, and Zenith Bank.',
        url: 'https://metricshour.com/nigeria/',
        inLanguage: 'en',
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'Nigerian Stocks', item: 'https://metricshour.com/nigeria/' },
          ],
        },
      }),
    },
  ],
})
</script>
