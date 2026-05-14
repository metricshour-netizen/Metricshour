<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <!-- Header -->
    <div class="mb-8">
      <div class="text-[10px] font-mono font-bold text-emerald-500 uppercase tracking-widest mb-2">MetricsHour Tools</div>
      <h1 class="text-2xl sm:text-3xl font-extrabold text-white mb-2">{{ $t('smartMoney.title') }}</h1>
      <p class="text-gray-400 text-sm max-w-2xl">{{ $t('smartMoney.subtitle') }}</p>
    </div>

    <!-- Stats bar -->
    <div class="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-gray-500 mb-8 font-mono">
      <span v-if="investors"><span class="text-white font-bold">{{ investors.length }}</span> {{ $t('smartMoney.statsBar.tracked') }}</span>
      <span class="text-[#1f2937]">·</span>
      <span>{{ $t('smartMoney.statsBar.updated') }}</span>
    </div>

    <!-- Loading skeleton -->
    <div v-if="pending" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="h-48 bg-[#111827] rounded-2xl animate-pulse"/>
    </div>

    <template v-else-if="investors?.length">
      <!-- Tier 1 — Featured Individuals -->
      <div class="mb-10">
        <h2 class="text-sm font-bold text-white uppercase tracking-widest mb-4">{{ $t('smartMoney.featuredTitle') }}</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <NuxtLink
            v-for="inv in tier1"
            :key="inv.slug"
            :to="`/smart-money/${inv.slug}/`"
            class="group bg-[#111827] border border-[#1f2937] hover:border-emerald-500/50 rounded-2xl p-5 transition-all hover:bg-[#131d2e]"
          >
            <div class="flex items-start justify-between mb-3">
              <div>
                <div class="text-sm font-bold text-white group-hover:text-emerald-400 transition-colors">{{ inv.name }}</div>
                <div class="text-[11px] text-gray-500 mt-0.5">{{ inv.fund_name }}</div>
              </div>
              <span v-if="inv.total_value_usd" class="text-[10px] font-mono text-emerald-400 bg-emerald-900/20 border border-emerald-900/50 px-2 py-0.5 rounded-full shrink-0">
                ${{ fmtB(inv.total_value_usd) }}
              </span>
            </div>

            <!-- Top holdings tickers -->
            <div v-if="inv.top_holdings?.length" class="flex gap-1.5 mb-3 flex-wrap">
              <span v-for="ticker in inv.top_holdings" :key="ticker"
                class="text-[10px] font-mono font-bold text-emerald-600 bg-[#0d1520] border border-[#1f2937] px-2 py-0.5 rounded">
                {{ ticker }}
              </span>
            </div>
            <!-- Placeholder tickers when no data yet -->
            <div v-else class="flex gap-1.5 mb-3">
              <span v-for="i in 3" :key="i" class="h-4 w-10 bg-[#1f2937] rounded animate-pulse"/>
            </div>

            <div class="flex items-center justify-between text-[10px] text-gray-600 mt-auto">
              <span v-if="inv.holding_count">{{ $t('smartMoney.holdingsCount', { count: inv.holding_count }) }}</span>
              <span v-else class="text-gray-700">{{ $t('smartMoney.noData') }}</span>
              <span v-if="inv.latest_quarter" class="font-mono">{{ inv.latest_quarter }}</span>
            </div>
            <div class="mt-3 text-xs text-emerald-600 group-hover:text-emerald-400 transition-colors font-medium flex items-center gap-1">
              {{ $t('smartMoney.portfolio.viewPortfolio') }} →
            </div>
          </NuxtLink>
        </div>
      </div>

      <!-- Tier 2 — Featured Funds -->
      <div class="mb-10">
        <h2 class="text-sm font-bold text-white uppercase tracking-widest mb-4">{{ $t('smartMoney.featuredFunds') }}</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <NuxtLink
            v-for="inv in tier2"
            :key="inv.slug"
            :to="`/smart-money/${inv.slug}/`"
            class="group bg-[#0d1520] border border-[#1f2937] hover:border-emerald-500/40 rounded-xl p-4 transition-all hover:bg-[#111827]"
          >
            <div class="flex items-start justify-between mb-2">
              <div>
                <div class="text-sm font-bold text-white group-hover:text-emerald-400 transition-colors">{{ inv.fund_name || inv.name }}</div>
                <div class="text-[10px] text-gray-600 mt-0.5">{{ inv.name }}</div>
              </div>
              <span v-if="inv.total_value_usd" class="text-[10px] font-mono text-gray-500 shrink-0">
                ${{ fmtB(inv.total_value_usd) }}
              </span>
            </div>
            <div v-if="inv.top_holdings?.length" class="flex gap-1 flex-wrap mb-2">
              <span v-for="ticker in inv.top_holdings" :key="ticker"
                class="text-[10px] font-mono text-emerald-700 bg-emerald-900/10 px-1.5 py-0.5 rounded">
                {{ ticker }}
              </span>
            </div>
            <div v-else class="flex gap-1 mb-2">
              <span v-for="i in 3" :key="i" class="h-3.5 w-9 bg-[#1f2937] rounded animate-pulse"/>
            </div>
            <div class="text-[10px] text-emerald-700 group-hover:text-emerald-500 transition-colors font-medium mt-1">
              {{ $t('smartMoney.portfolio.viewPortfolio') }} →
            </div>
          </NuxtLink>
        </div>
      </div>

      <!-- About 13F filings -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl p-5 mt-6">
        <div class="text-[10px] font-mono font-bold text-gray-600 uppercase tracking-widest mb-2">{{ $t('smartMoney.about.title') }}</div>
        <p class="text-xs text-gray-500 leading-relaxed max-w-2xl">
          {{ $t('smartMoney.about.body') }}
          {{ $t('smartMoney.statsBar.updated') }}.
          <span>{{ $t('smartMoney.about.source') }}:
            <a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F" target="_blank" rel="noopener noreferrer" class="text-emerald-700 hover:text-emerald-500 underline">SEC EDGAR</a>.
          </span>
        </p>
      </div>
    </template>

    <div v-else-if="!pending" class="text-center py-16 text-gray-600">
      <p class="text-sm">{{ $t('smartMoney.noData') }}</p>
      <p class="text-xs mt-2 text-gray-700">{{ $t('smartMoney.about.noFilingData') }}</p>
    </div>
  </main>
</template>

<script setup lang="ts">
const { t } = useI18n()
const { get } = useApi()

const { data: investors, pending } = await useAsyncData(
  'sm-investors',
  () => get<any[]>('/api/smartmoney/investors').catch(() => []),
)

const tier1 = computed(() => investors.value?.filter((i: any) => i.tier === 1) ?? [])
const tier2 = computed(() => investors.value?.filter((i: any) => i.tier === 2) ?? [])

function fmtB(v: number): string {
  if (v >= 1e12) return `${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `${(v / 1e9).toFixed(0)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(0)}M`
  return `${(v / 1e3).toFixed(0)}K`
}

useSeoMeta({
  title: 'Smart Money Tracker — What Buffett, Burry & Top Funds Are Buying | MetricsHour',
  description: 'Track institutional investor 13F filings. See what Warren Buffett, Michael Burry, and top hedge funds are buying and selling — with geographic risk context.',
  ogTitle: 'Smart Money Tracker — MetricsHour',
  ogDescription: 'What Buffett, Burry, and top institutional investors are buying this quarter — with geographic revenue risk analysis.',
  robots: 'index, follow',
})
useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/smart-money/' }],
})
</script>
