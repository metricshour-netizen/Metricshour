<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">Earnings Calendar</h1>
      <p class="text-gray-500 text-sm mt-1">Upcoming earnings reports · S&P 500 companies · Next 30 days</p>
    </div>

    <!-- Tab toggle -->
    <div class="flex gap-2 mb-6">
      <button
        @click="tab = 'upcoming'"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
        :class="tab === 'upcoming' ? 'bg-emerald-600 text-white' : 'bg-[#111827] border border-[#1f2937] text-gray-400 hover:text-white'"
      >Upcoming</button>
      <button
        @click="tab = 'recent'"
        class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
        :class="tab === 'recent' ? 'bg-emerald-600 text-white' : 'bg-[#111827] border border-[#1f2937] text-gray-400 hover:text-white'"
      >Recent Results</button>
    </div>

    <!-- UPCOMING TAB -->
    <template v-if="tab === 'upcoming'">
      <div v-if="pendingUp" class="space-y-6">
        <div v-for="i in 3" :key="i" class="mb-8">
          <div class="h-4 w-40 bg-[#111827] rounded animate-pulse mb-4"/>
          <div class="space-y-2">
            <div v-for="j in 4" :key="j" class="h-14 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
          </div>
        </div>
      </div>

      <template v-else-if="upcomingData?.weeks?.length">
        <div v-for="week in upcomingData.weeks" :key="week.label" class="mb-8">
          <!-- Week header -->
          <div class="flex items-center gap-3 mb-3">
            <h2 class="text-sm font-extrabold text-white uppercase tracking-widest">{{ week.label }}</h2>
            <span class="text-[10px] text-gray-600 bg-[#1f2937] px-2 py-0.5 rounded-full">{{ week.events.length }}</span>
            <div class="flex-1 h-px bg-[#1f2937]"/>
          </div>

          <!-- Events table -->
          <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-hidden">
            <table class="w-full text-sm">
              <thead class="bg-[#111827] text-[10px] text-gray-500 uppercase tracking-widest">
                <tr>
                  <th class="px-4 py-2.5 text-left">Company</th>
                  <th class="px-4 py-2.5 text-left hidden sm:table-cell">Sector</th>
                  <th class="px-4 py-2.5 text-right">Report Date</th>
                  <th class="px-4 py-2.5 text-right hidden md:table-cell">EPS Est.</th>
                  <th class="px-4 py-2.5 text-right hidden lg:table-cell">Mkt Cap</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="ev in week.events" :key="ev.symbol + ev.report_date"
                  class="border-t border-[#1f2937] hover:bg-[#131d2e] transition-colors">
                  <td class="px-4 py-3">
                    <NuxtLink :to="`/stocks/${ev.symbol.toLowerCase()}/`" class="flex items-center gap-2">
                      <span class="font-mono text-xs text-emerald-400 font-bold w-12 flex-shrink-0">{{ ev.symbol }}</span>
                      <span class="text-white text-xs truncate max-w-[140px] sm:max-w-none">{{ ev.name }}</span>
                    </NuxtLink>
                  </td>
                  <td class="px-4 py-3 text-gray-500 text-xs hidden sm:table-cell">{{ ev.sector ?? '—' }}</td>
                  <td class="px-4 py-3 text-right text-gray-300 text-xs tabular-nums">{{ fmtDate(ev.report_date) }}</td>
                  <td class="px-4 py-3 text-right text-gray-400 text-xs tabular-nums hidden md:table-cell">
                    {{ ev.eps_estimate != null ? `$${ev.eps_estimate.toFixed(2)}` : '—' }}
                  </td>
                  <td class="px-4 py-3 text-right text-gray-600 text-xs tabular-nums hidden lg:table-cell">
                    {{ fmtMktCap(ev.market_cap_usd) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <div v-else class="text-center py-16">
        <p class="text-gray-600 text-sm mb-2">No upcoming earnings data yet.</p>
        <p class="text-gray-700 text-xs">Worker fetches daily at 7:30am UTC via yfinance.</p>
      </div>
    </template>

    <!-- RECENT TAB -->
    <template v-else>
      <div v-if="pendingRec" class="space-y-2">
        <div v-for="i in 8" :key="i" class="h-14 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
      </div>

      <template v-else-if="recentData?.events?.length">
        <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-hidden mb-4">
          <table class="w-full text-sm">
            <thead class="bg-[#111827] text-[10px] text-gray-500 uppercase tracking-widest">
              <tr>
                <th class="px-4 py-2.5 text-left">Company</th>
                <th class="px-4 py-2.5 text-right">Date</th>
                <th class="px-4 py-2.5 text-right hidden sm:table-cell">EPS Est.</th>
                <th class="px-4 py-2.5 text-right hidden sm:table-cell">EPS Actual</th>
                <th class="px-4 py-2.5 text-right">Surprise</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ev in recentData.events" :key="ev.symbol + ev.report_date"
                class="border-t border-[#1f2937] hover:bg-[#131d2e] transition-colors">
                <td class="px-4 py-3">
                  <NuxtLink :to="`/stocks/${ev.symbol.toLowerCase()}/`" class="flex items-center gap-2">
                    <span class="font-mono text-xs text-emerald-400 font-bold w-12 flex-shrink-0">{{ ev.symbol }}</span>
                    <span class="text-white text-xs truncate max-w-[120px] sm:max-w-none">{{ ev.name }}</span>
                  </NuxtLink>
                </td>
                <td class="px-4 py-3 text-right text-gray-400 text-xs tabular-nums">{{ fmtDate(ev.report_date) }}</td>
                <td class="px-4 py-3 text-right text-gray-500 text-xs tabular-nums hidden sm:table-cell">
                  {{ ev.eps_estimate != null ? `$${ev.eps_estimate.toFixed(2)}` : '—' }}
                </td>
                <td class="px-4 py-3 text-right text-white text-xs tabular-nums font-medium hidden sm:table-cell">
                  {{ ev.eps_actual != null ? `$${ev.eps_actual.toFixed(2)}` : '—' }}
                </td>
                <td class="px-4 py-3 text-right text-xs tabular-nums font-semibold"
                  :class="surpriseColor(ev.surprise_pct)">
                  {{ fmtSurprise(ev.surprise_pct) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-xs text-gray-700">Sorted by EPS surprise. Positive surprise = beat estimates.</p>
      </template>

      <div v-else class="text-center py-16">
        <p class="text-gray-600 text-sm">No recent earnings data yet.</p>
      </div>
    </template>

    <p class="text-xs text-gray-700 mt-6">Data: yfinance · SEC EDGAR · Updated daily</p>
  </main>
</template>

<script setup lang="ts">
const tab = ref<'upcoming' | 'recent'>('upcoming')

const { data: upcomingData, pending: pendingUp } = await useAsyncData('earnings-upcoming',
  () => $fetch<any>('/api/earnings/upcoming?days=30').catch(() => null),
)

const { data: recentData, pending: pendingRec } = await useAsyncData('earnings-recent',
  () => $fetch<any>('/api/earnings/recent?days=14').catch(() => null),
)

function fmtDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00Z')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

function fmtMktCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtSurprise(v: number | null): string {
  if (v == null) return '—'
  return (v >= 0 ? '+' : '') + v.toFixed(1) + '%'
}

function surpriseColor(v: number | null): string {
  if (v == null) return 'text-gray-600'
  if (v > 5) return 'text-emerald-400'
  if (v > 0) return 'text-emerald-600'
  if (v < -5) return 'text-red-400'
  return 'text-red-600'
}

useSeoMeta({
  title: 'Earnings Calendar — Upcoming & Recent S&P 500 Results — MetricsHour',
  description: 'Track upcoming earnings reports and recent results for S&P 500 companies. EPS estimates, actuals, and surprise percentages.',
  ogTitle: 'Earnings Calendar — MetricsHour',
  ogDescription: 'Upcoming earnings reports and recent EPS results for S&P 500 stocks.',
  ogUrl: 'https://metricshour.com/earnings/',
  ogImage: 'https://cdn.metricshour.com/og/section/home.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterImage: 'https://cdn.metricshour.com/og/section/home.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1',
})
useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/earnings/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'Earnings Calendar — MetricsHour',
      url: 'https://metricshour.com/earnings/',
      description: 'Upcoming earnings reports and recent EPS results for S&P 500 stocks.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
    }),
  }],
})
</script>
