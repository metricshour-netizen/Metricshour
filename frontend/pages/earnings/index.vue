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

          <!-- Desktop table -->
          <div class="hidden sm:block bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-hidden">
            <table class="w-full text-sm">
              <thead class="bg-[#111827] text-[10px] text-gray-500 uppercase tracking-widest">
                <tr>
                  <th class="px-4 py-2.5 text-left">Company</th>
                  <th class="px-4 py-2.5 text-left">Sector</th>
                  <th class="px-4 py-2.5 text-right">Date</th>
                  <th class="px-4 py-2.5 text-right">EPS Est.</th>
                  <th class="px-4 py-2.5 text-right">Rev. Est.</th>
                  <th class="px-4 py-2.5 text-right hidden md:table-cell">Mkt Cap</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="ev in week.events" :key="ev.symbol + ev.report_date"
                  class="border-t border-[#1f2937] hover:bg-[#131d2e] transition-colors">
                  <td class="px-4 py-3">
                    <NuxtLink :to="`/stocks/${ev.symbol.toLowerCase()}/`" class="flex items-center gap-2">
                      <span class="font-mono text-xs text-emerald-400 font-bold w-12 flex-shrink-0">{{ ev.symbol }}</span>
                      <div class="min-w-0">
                        <span class="text-white text-xs truncate block">{{ ev.name }}</span>
                        <span v-if="ev.period" class="text-[10px] text-gray-600 font-mono">{{ ev.period }}</span>
                      </div>
                    </NuxtLink>
                  </td>
                  <td class="px-4 py-3 text-gray-500 text-xs">{{ ev.sector ?? '—' }}</td>
                  <td class="px-4 py-3 text-right text-gray-300 text-xs tabular-nums whitespace-nowrap">{{ fmtDate(ev.report_date) }}</td>
                  <td class="px-4 py-3 text-right text-gray-400 text-xs tabular-nums">
                    {{ ev.eps_estimate != null ? `$${ev.eps_estimate.toFixed(2)}` : '—' }}
                  </td>
                  <td class="px-4 py-3 text-right text-xs tabular-nums">
                    <span v-if="ev.revenue_estimate != null" class="text-gray-400">{{ fmtRevenue(ev.revenue_estimate) }}</span>
                    <span v-else class="text-gray-700 text-[10px]">{{ ev.period ?? 'N/A' }}</span>
                  </td>
                  <td class="px-4 py-3 text-right text-gray-600 text-xs tabular-nums hidden md:table-cell">
                    {{ fmtMktCap(ev.market_cap_usd) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Mobile cards -->
          <div class="sm:hidden space-y-2">
            <NuxtLink
              v-for="ev in week.events"
              :key="ev.symbol + ev.report_date"
              :to="`/stocks/${ev.symbol.toLowerCase()}/`"
              class="block bg-[#0d1520] border border-[#1f2937] rounded-xl p-3 hover:border-emerald-500/40 transition-colors"
            >
              <div class="flex items-start justify-between gap-2 mb-2">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="font-mono text-xs text-emerald-400 font-bold shrink-0">{{ ev.symbol }}</span>
                  <span class="text-white text-xs truncate">{{ ev.name }}</span>
                </div>
                <span class="text-gray-300 text-xs tabular-nums whitespace-nowrap shrink-0">{{ fmtDate(ev.report_date) }}</span>
              </div>
              <div class="flex items-center gap-2 mb-2">
                <span v-if="ev.period" class="text-[10px] font-mono text-emerald-700 bg-emerald-900/20 px-1.5 py-0.5 rounded">{{ ev.period }}</span>
                <span v-if="ev.sector" class="text-[10px] text-gray-600">{{ ev.sector }}</span>
                <span v-if="ev.market_cap_usd" class="text-[10px] text-gray-700 ml-auto">{{ fmtMktCap(ev.market_cap_usd) }}</span>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <div class="bg-[#111827] rounded-lg px-2.5 py-1.5">
                  <div class="text-[10px] text-gray-600 uppercase tracking-wide mb-0.5">EPS Est.</div>
                  <div class="text-sm font-bold tabular-nums" :class="ev.eps_estimate != null ? 'text-white' : 'text-gray-700'">
                    {{ ev.eps_estimate != null ? `$${ev.eps_estimate.toFixed(2)}` : '—' }}
                  </div>
                </div>
                <div class="bg-[#111827] rounded-lg px-2.5 py-1.5">
                  <div class="text-[10px] text-gray-600 uppercase tracking-wide mb-0.5">Rev. Est.</div>
                  <div class="text-sm font-bold tabular-nums" :class="ev.revenue_estimate != null ? 'text-white' : 'text-gray-700'">
                    {{ ev.revenue_estimate != null ? fmtRevenue(ev.revenue_estimate) : '—' }}
                  </div>
                </div>
              </div>
            </NuxtLink>
          </div>
        </div>
      </template>

      <div v-else class="text-center py-16">
        <p class="text-gray-600 text-sm mb-2">No upcoming earnings data yet.</p>
        <p class="text-gray-700 text-xs">Worker fetches daily at 7:30am UTC.</p>
      </div>
    </template>

    <!-- RECENT TAB -->
    <template v-else>
      <div v-if="pendingRec" class="space-y-2">
        <div v-for="i in 8" :key="i" class="h-14 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
      </div>

      <template v-else-if="recentData?.events?.length">
        <!-- Desktop table -->
        <div class="hidden sm:block bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-hidden mb-4">
          <table class="w-full text-sm">
            <thead class="bg-[#111827] text-[10px] text-gray-500 uppercase tracking-widest">
              <tr>
                <th class="px-4 py-2.5 text-left">Company</th>
                <th class="px-4 py-2.5 text-right">Prev EPS</th>
                <th class="px-4 py-2.5 text-right">EPS Est.</th>
                <th class="px-4 py-2.5 text-right">EPS Actual</th>
                <th class="px-4 py-2.5 text-right hidden md:table-cell">Revenue</th>
                <th class="px-4 py-2.5 text-right hidden lg:table-cell">Mkt Cap</th>
                <th class="px-4 py-2.5 text-right">Surprise</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ev in recentData.events" :key="ev.symbol + ev.report_date"
                class="border-t border-[#1f2937] hover:bg-[#131d2e] transition-colors">
                <td class="px-4 py-3">
                  <NuxtLink :to="`/stocks/${ev.symbol.toLowerCase()}/`" class="flex items-center gap-2">
                    <span class="font-mono text-xs text-emerald-400 font-bold w-12 flex-shrink-0">{{ ev.symbol }}</span>
                    <div class="min-w-0">
                      <span class="text-white text-xs truncate block">{{ ev.name }}</span>
                      <span v-if="ev.period" class="text-[10px] text-gray-600 font-mono">{{ ev.period }} · {{ fmtDate(ev.report_date) }}</span>
                    </div>
                  </NuxtLink>
                </td>
                <td class="px-4 py-3 text-right text-gray-600 text-xs tabular-nums">
                  {{ ev.prev_eps != null ? `$${ev.prev_eps.toFixed(2)}` : '—' }}
                </td>
                <td class="px-4 py-3 text-right text-gray-500 text-xs tabular-nums">
                  {{ ev.eps_estimate != null ? `$${ev.eps_estimate.toFixed(2)}` : '—' }}
                </td>
                <td class="px-4 py-3 text-right text-xs tabular-nums font-medium">
                  <span v-if="ev.eps_actual != null" class="flex items-center justify-end gap-1">
                    <span :class="epsVsPrevColor(ev.eps_actual, ev.prev_eps)" class="text-[10px]">{{ epsDirection(ev.eps_actual, ev.prev_eps) }}</span>
                    <span class="text-white">${{ ev.eps_actual.toFixed(2) }}</span>
                  </span>
                  <span v-else class="text-gray-600">—</span>
                </td>
                <td class="px-4 py-3 text-right text-xs tabular-nums hidden md:table-cell">
                  <span v-if="ev.revenue_actual != null" class="text-gray-400">{{ fmtRevenue(ev.revenue_actual) }}</span>
                  <span v-else-if="ev.revenue_estimate != null" class="text-gray-600">{{ fmtRevenue(ev.revenue_estimate) }}<span class="text-[10px] ml-0.5">E</span></span>
                  <span v-else class="text-gray-700 text-[10px]">no data</span>
                </td>
                <td class="px-4 py-3 text-right text-gray-600 text-xs tabular-nums hidden lg:table-cell">
                  {{ fmtMktCap(ev.market_cap_usd) }}
                </td>
                <td class="px-4 py-3 text-right text-xs tabular-nums">
                  <div class="flex items-center justify-end gap-1.5">
                    <span class="font-semibold" :class="surpriseColor(ev.surprise_pct)">{{ fmtSurprise(ev.surprise_pct) }}</span>
                    <span v-if="ev.surprise_pct != null" class="text-[10px] font-bold px-1 py-0.5 rounded"
                      :class="ev.surprise_pct > 0 ? 'bg-emerald-900/50 text-emerald-400' : 'bg-red-900/50 text-red-400'">
                      {{ ev.surprise_pct > 0 ? 'BEAT' : 'MISS' }}
                    </span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile cards -->
        <div class="sm:hidden space-y-2 mb-4">
          <NuxtLink
            v-for="ev in recentData.events"
            :key="ev.symbol + ev.report_date"
            :to="`/stocks/${ev.symbol.toLowerCase()}/`"
            class="block bg-[#0d1520] border rounded-xl p-3 hover:border-emerald-500/40 transition-colors"
            :class="ev.surprise_pct != null && ev.surprise_pct > 0 ? 'border-emerald-900/60' : ev.surprise_pct != null && ev.surprise_pct < 0 ? 'border-red-900/60' : 'border-[#1f2937]'"
          >
            <!-- Header row: ticker + name + beat/miss badge -->
            <div class="flex items-start justify-between gap-2 mb-1.5">
              <div class="flex items-center gap-2 min-w-0">
                <span class="font-mono text-xs text-emerald-400 font-bold shrink-0">{{ ev.symbol }}</span>
                <span class="text-white text-xs truncate">{{ ev.name }}</span>
              </div>
              <div class="flex items-center gap-1 shrink-0">
                <span class="font-semibold text-xs tabular-nums" :class="surpriseColor(ev.surprise_pct)">{{ fmtSurprise(ev.surprise_pct) }}</span>
                <span v-if="ev.surprise_pct != null" class="text-[10px] font-bold px-1.5 py-0.5 rounded"
                  :class="ev.surprise_pct > 0 ? 'bg-emerald-900/50 text-emerald-400' : 'bg-red-900/50 text-red-400'">
                  {{ ev.surprise_pct > 0 ? 'BEAT' : 'MISS' }}
                </span>
              </div>
            </div>

            <!-- Period + date -->
            <div class="flex items-center gap-2 mb-2">
              <span v-if="ev.period" class="text-[10px] font-mono text-emerald-700 bg-emerald-900/20 px-1.5 py-0.5 rounded">{{ ev.period }}</span>
              <span class="text-[10px] text-gray-600">{{ fmtDate(ev.report_date) }}</span>
              <span v-if="ev.market_cap_usd" class="text-[10px] text-gray-700 ml-auto">{{ fmtMktCap(ev.market_cap_usd) }}</span>
            </div>

            <!-- EPS row -->
            <div class="grid grid-cols-3 gap-2 mb-2">
              <div class="bg-[#111827] rounded-lg px-2 py-1.5">
                <div class="text-[10px] text-gray-600 uppercase tracking-wide mb-0.5">Prev EPS</div>
                <div class="text-xs tabular-nums text-gray-500">{{ ev.prev_eps != null ? `$${ev.prev_eps.toFixed(2)}` : '—' }}</div>
              </div>
              <div class="bg-[#111827] rounded-lg px-2 py-1.5">
                <div class="text-[10px] text-gray-600 uppercase tracking-wide mb-0.5">Est.</div>
                <div class="text-xs tabular-nums text-gray-400">{{ ev.eps_estimate != null ? `$${ev.eps_estimate.toFixed(2)}` : '—' }}</div>
              </div>
              <div class="bg-[#111827] rounded-lg px-2 py-1.5">
                <div class="text-[10px] text-gray-600 uppercase tracking-wide mb-0.5">Actual</div>
                <div v-if="ev.eps_actual != null" class="flex items-center gap-0.5">
                  <span :class="epsVsPrevColor(ev.eps_actual, ev.prev_eps)" class="text-[10px]">{{ epsDirection(ev.eps_actual, ev.prev_eps) }}</span>
                  <span class="text-xs font-bold tabular-nums text-white">${{ ev.eps_actual.toFixed(2) }}</span>
                </div>
                <div v-else class="text-xs text-gray-700">—</div>
              </div>
            </div>

            <!-- Revenue row -->
            <div class="bg-[#111827] rounded-lg px-2.5 py-1.5">
              <div class="text-[10px] text-gray-600 uppercase tracking-wide mb-0.5">Revenue</div>
              <div class="text-xs tabular-nums">
                <span v-if="ev.revenue_actual != null" class="text-gray-300 font-medium">{{ fmtRevenue(ev.revenue_actual) }}</span>
                <span v-else-if="ev.revenue_estimate != null" class="text-gray-500">{{ fmtRevenue(ev.revenue_estimate) }} <span class="text-[10px] text-gray-600">est.</span></span>
                <span v-else class="text-gray-700 text-[10px]">No revenue data</span>
              </div>
            </div>
          </NuxtLink>
        </div>
        <p class="text-xs text-gray-700">Sorted by EPS surprise. Positive = beat estimates.</p>
      </template>

      <div v-else class="text-center py-16">
        <p class="text-gray-600 text-sm">No recent earnings data yet.</p>
      </div>
    </template>

    <p class="text-xs text-gray-700 mt-6">Data: SEC EDGAR · Updated daily</p>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()
const tab = ref<'upcoming' | 'recent'>('upcoming')

const { data: upcomingData, pending: pendingUp } = await useAsyncData('earnings-upcoming',
  () => get<any>('/api/earnings/upcoming?days=30').catch(() => null),
)

const { data: recentData, pending: pendingRec } = await useAsyncData('earnings-recent',
  () => get<any>('/api/earnings/recent?days=14').catch(() => null),
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

function fmtRevenue(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(1)}B`
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

function epsDirection(actual: number | null, prev: number | null): string {
  if (actual == null || prev == null) return ''
  return actual > prev ? '▲' : actual < prev ? '▼' : '='
}

function epsVsPrevColor(actual: number | null, prev: number | null): string {
  if (actual == null || prev == null) return 'text-gray-600'
  return actual > prev ? 'text-emerald-400' : actual < prev ? 'text-red-400' : 'text-gray-600'
}

useSeoMeta({
  title: 'Earnings Calendar — Upcoming & Recent S&P 500 Results — MetricsHour',
  description: 'Track upcoming earnings reports and recent results for S&P 500 companies. EPS estimates, actuals, revenue, and surprise percentages.',
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
