<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <NuxtLink to="/screener/" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
      ← Screener
    </NuxtLink>

    <!-- SEO header -->
    <div class="mb-8">
      <h1 class="text-xl sm:text-2xl font-bold text-white mb-3">{{ config.h1 }}</h1>
      <p class="text-sm text-gray-400 leading-relaxed max-w-2xl">{{ config.intro }}</p>
    </div>

    <!-- Active filter badge -->
    <div class="flex flex-wrap gap-2 mb-6">
      <span
        v-for="badge in activeBadges"
        :key="badge"
        class="text-xs bg-emerald-900/30 border border-emerald-800/50 text-emerald-400 px-3 py-1 rounded-full"
      >{{ badge }}</span>
    </div>

    <!-- Screener table (reuse screener logic inline) -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden">
      <div class="hidden sm:grid px-4 py-2 border-b border-[#1f2937] text-[10px] text-gray-500 uppercase tracking-wide"
           style="grid-template-columns: 2rem 1fr 7rem 6rem 5rem 5rem 4rem 4rem 1.5rem">
        <span>#</span>
        <span>Company</span>
        <span>Sector</span>
        <span class="text-right">Mkt Cap</span>
        <span class="text-right">China %</span>
        <span class="text-right">US %</span>
        <span class="text-right">EU %</span>
        <span class="text-right">Countries</span>
        <span></span>
      </div>

      <div v-if="pending" class="divide-y divide-[#1f2937]">
        <div v-for="i in 10" :key="i" class="px-4 py-3 flex gap-3 items-center">
          <div class="h-3 bg-[#1f2937] rounded w-8 animate-pulse"></div>
          <div class="h-3 bg-[#1f2937] rounded flex-1 animate-pulse"></div>
          <div class="h-3 bg-[#1f2937] rounded w-16 animate-pulse"></div>
        </div>
      </div>

      <div v-else-if="data?.results?.length" class="divide-y divide-[#1f2937]">
        <NuxtLink
          v-for="(s, i) in data.results"
          :key="s.symbol"
          :to="`/stocks/${s.symbol.toLowerCase()}`"
          class="block hover:bg-[#1a2235] transition-colors"
        >
          <!-- Mobile -->
          <div class="flex items-center justify-between px-4 py-3 sm:hidden">
            <div class="min-w-0">
              <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
              <div class="text-xs text-gray-500 truncate max-w-[160px]">{{ s.name }}</div>
            </div>
            <div class="text-right shrink-0 ml-2 space-y-0.5">
              <div class="text-xs text-gray-300 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</div>
              <div class="text-[10px] tabular-nums">
                <span class="text-red-400">CN {{ s.china_pct }}%</span>
                <span class="text-gray-600 mx-1">·</span>
                <span class="text-blue-400">US {{ s.us_pct }}%</span>
              </div>
            </div>
          </div>
          <!-- Desktop -->
          <div class="hidden sm:grid px-4 py-2.5 items-center"
               style="grid-template-columns: 2rem 1fr 7rem 6rem 5rem 5rem 4rem 4rem 1.5rem">
            <span class="text-xs text-gray-600">{{ i + 1 }}</span>
            <div class="min-w-0 pr-2">
              <div class="text-sm font-bold text-white">{{ s.symbol }}</div>
              <div class="text-xs text-gray-500 truncate">{{ s.name }}</div>
            </div>
            <span class="text-xs text-gray-500 truncate pr-2">{{ s.sector || '—' }}</span>
            <span class="text-xs text-right text-gray-400 tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
            <span class="text-xs text-right tabular-nums font-medium" :class="chinaPctClass(s.china_pct)">
              {{ s.china_pct > 0 ? s.china_pct + '%' : (s.has_revenue_data ? '0%' : '—') }}
            </span>
            <span class="text-xs text-right text-blue-400 tabular-nums">
              {{ s.us_pct > 0 ? s.us_pct + '%' : (s.has_revenue_data ? '0%' : '—') }}
            </span>
            <span class="text-xs text-right text-purple-400 tabular-nums">
              {{ s.eu_pct > 0 ? s.eu_pct + '%' : (s.has_revenue_data ? '0%' : '—') }}
            </span>
            <span class="text-xs text-right text-gray-500 tabular-nums">{{ s.country_count > 0 ? s.country_count : '—' }}</span>
            <span class="text-right text-emerald-600 text-xs">→</span>
          </div>
        </NuxtLink>
      </div>

      <div v-else class="text-center py-16 text-gray-600 text-sm">No stocks match this filter.</div>
    </div>

    <!-- Load more -->
    <div v-if="data && data.total > data.results?.length" class="flex justify-center mt-4">
      <NuxtLink
        :to="`/screener/?${presetQueryString}`"
        class="px-4 py-2 text-sm border border-[#1f2937] rounded text-gray-400 hover:border-emerald-700 hover:text-emerald-400 transition-colors"
      >
        View all {{ data.total }} results in Screener →
      </NuxtLink>
    </div>

    <p class="text-[10px] text-gray-700 mt-6 text-center">
      Revenue data from SEC EDGAR 10-K/10-Q filings · Source: MetricsHour
    </p>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const API = useRuntimeConfig().public.apiBase
const { truncateAtSentence } = useTruncate()

type SlugConfig = {
  h1: string
  metaTitle: string
  metaDesc: string
  intro: string
  filters: Record<string, number | string>
  badges: string[]
}

const SLUG_MAP: Record<string, SlugConfig> = {
  'no-china-exposure': {
    h1: 'Stocks With No China Revenue Exposure',
    metaTitle: 'No China Exposure Stocks — MetricsHour Screener',
    metaDesc: 'Screen S&P 500 stocks with zero China revenue exposure. Filter by sector, market cap, and trade risk using SEC EDGAR data.',
    intro: 'These stocks report zero revenue from China in their most recent SEC 10-K or 10-Q filing. For investors concerned about US-China trade tensions, tariffs, or geopolitical risk, this list shows companies with no direct China revenue dependency. Data is sourced from SEC EDGAR geographic segment disclosures.',
    filters: { china_max: 0, sort_by: 'market_cap', limit: 100 },
    badges: ['China Revenue: 0%'],
  },
  'low-china-exposure': {
    h1: 'Stocks With Low China Revenue Exposure',
    metaTitle: 'Low China Exposure Stocks (Under 5%) — MetricsHour',
    metaDesc: 'Find S&P 500 stocks with under 5% China revenue exposure. Screened from SEC EDGAR 10-K geographic segment data.',
    intro: 'These S&P 500 stocks derive less than 5% of total revenue from China, based on the most recent SEC EDGAR filings. Low China exposure reduces direct sensitivity to US-China trade policy, tariff escalation, and RMB currency risk. Use this screen as a starting point for trade-resilient portfolio construction.',
    filters: { china_max: 5, sort_by: 'market_cap', limit: 100 },
    badges: ['China Revenue < 5%'],
  },
  'china-exposed-stocks': {
    h1: 'Stocks With High China Revenue Exposure',
    metaTitle: 'China-Exposed Stocks (Over 20%) — MetricsHour Screener',
    metaDesc: 'S&P 500 stocks with more than 20% China revenue exposure from SEC EDGAR filings. Track tariff and trade war risk.',
    intro: 'These companies generate more than 20% of total revenue from China, making them materially sensitive to US-China trade policy, tariffs, and Chinese consumer demand. Investors tracking trade war risk, export controls, or RMB depreciation should monitor these stocks closely.',
    filters: { china_min: 20, sort_by: 'china_pct', sort_dir: 'desc', limit: 100 },
    badges: ['China Revenue > 20%'],
  },
  'tariff-proof-stocks': {
    h1: 'Tariff-Proof Stocks: Low China and EU Exposure',
    metaTitle: 'Tariff-Proof Stocks — Low China & EU Revenue | MetricsHour',
    metaDesc: 'Stocks with under 5% China revenue and under 5% EU revenue. Screened for minimal tariff exposure using SEC EDGAR data.',
    intro: 'Tariff-proof stocks derive less than 5% of revenue from both China and the EU — the two largest targets of recent US trade policy. With tariffs on Chinese imports and potential EU trade friction, these companies have limited direct exposure to cross-border revenue risk from either region.',
    filters: { china_max: 5, eu_max: 5, sort_by: 'market_cap', limit: 100 },
    badges: ['China Revenue < 5%', 'EU Revenue < 5%'],
  },
  'europe-exposed-stocks': {
    h1: 'Stocks With High Europe Revenue Exposure',
    metaTitle: 'Europe-Exposed Stocks (Over 20% EU Revenue) — MetricsHour',
    metaDesc: 'S&P 500 stocks with more than 20% EU revenue exposure. Data from SEC EDGAR geographic segment filings.',
    intro: 'These stocks generate more than 20% of revenue from European Union countries, based on SEC EDGAR geographic disclosures. Europe exposure creates sensitivity to EUR/USD exchange rates, European Central Bank policy, EU regulatory changes, and any transatlantic trade friction.',
    filters: { eu_min: 20, sort_by: 'eu_pct', sort_dir: 'desc', limit: 100 },
    badges: ['EU Revenue > 20%'],
  },
  'high-us-revenue': {
    h1: 'Stocks With High US Domestic Revenue',
    metaTitle: 'High US Revenue Stocks (Over 70%) — MetricsHour Screener',
    metaDesc: 'S&P 500 stocks deriving over 70% of revenue from the United States. Screened from SEC EDGAR geographic segment data.',
    intro: 'These companies generate more than 70% of total revenue domestically within the United States. High US revenue concentration reduces exposure to foreign currency risk, international trade policy, and geopolitical disruption — making these stocks more insulated from global macro headwinds.',
    filters: { us_min: 70, sort_by: 'us_pct', sort_dir: 'desc', limit: 100 },
    badges: ['US Revenue > 70%'],
  },
  'india-growth-stocks': {
    h1: 'Stocks With India Revenue Exposure',
    metaTitle: 'India Growth Stocks (Over 10% India Revenue) — MetricsHour',
    metaDesc: 'Find S&P 500 stocks with over 10% India revenue exposure. Screened from SEC EDGAR geographic segment filings.',
    intro: 'India is one of the fastest-growing major economies, projected to be the world\'s third-largest GDP by 2030. These stocks derive more than 10% of revenue from India, giving them material exposure to Indian consumer spending, infrastructure growth, and the IT services sector.',
    filters: { india_min: 10, sort_by: 'india_pct', sort_dir: 'desc', limit: 100 },
    badges: ['India Revenue > 10%'],
  },
  'domestic-only-stocks': {
    h1: 'Domestic-Only Stocks: Over 80% US Revenue',
    metaTitle: 'Domestic-Only Stocks (Over 80% US Revenue) — MetricsHour',
    metaDesc: 'S&P 500 stocks with over 80% US domestic revenue. Minimal international exposure, screened from SEC EDGAR data.',
    intro: 'These companies derive more than 80% of revenue from the United States, with minimal international exposure. Domestic-only stocks are less affected by currency fluctuations, foreign trade policy, and global economic slowdowns — though they remain fully exposed to US economic cycles.',
    filters: { us_min: 80, sort_by: 'us_pct', sort_dir: 'desc', limit: 100 },
    badges: ['US Revenue > 80%'],
  },
  'large-cap-stocks': {
    h1: 'Large Cap Stocks by Geographic Revenue Exposure',
    metaTitle: 'Large Cap Stocks by Geographic Revenue — MetricsHour Screener',
    metaDesc: 'Screen large cap stocks (over $100B market cap) by China, US, and EU geographic revenue exposure from SEC EDGAR.',
    intro: 'Large cap stocks with market capitalizations exceeding $100 billion, screened by geographic revenue exposure from SEC EDGAR filings. Large caps dominate index weights and institutional portfolios — understanding their China, US, and international revenue mix is essential for assessing macro and trade risk at the portfolio level.',
    filters: { market_cap_min: 100, sort_by: 'market_cap', limit: 100 },
    badges: ['Market Cap > $100B'],
  },
  'tech-sector-exposure': {
    h1: 'Technology Sector Stocks by Geographic Revenue',
    metaTitle: 'Tech Stocks Geographic Revenue Exposure — MetricsHour',
    metaDesc: 'Screen technology sector stocks by China, US, and EU revenue exposure. Data from SEC EDGAR 10-K geographic filings.',
    intro: 'Technology sector stocks screened by geographic revenue exposure from SEC EDGAR filings. Tech companies often have significant international revenue — particularly from China — and are frequently subject to export controls, tariffs, and geopolitical restrictions. Use this screen to assess China revenue risk within the technology sector.',
    filters: { sector: 'Information Technology', sort_by: 'china_pct', sort_dir: 'desc', limit: 100 },
    badges: ['Sector: Technology'],
  },
}

const slug = route.params.slug as string
const config = SLUG_MAP[slug]

if (!config) {
  throw createError({ statusCode: 404, statusMessage: 'Screener preset not found' })
}

const activeBadges = config.badges

const { data, pending } = await useAsyncData(
  `screener-slug-${slug}`,
  () => $fetch<any>(`${API}/api/screener`, { params: config.filters }),
)

const presetQueryString = computed(() => {
  return Object.entries(config.filters)
    .map(([k, v]) => `${k}=${v}`)
    .join('&')
})

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  if (v >= 1e6)  return `$${(v / 1e6).toFixed(0)}M`
  return `$${v.toLocaleString()}`
}

function chinaPctClass(pct: number): string {
  if (pct === 0) return 'text-gray-600'
  if (pct < 5)  return 'text-yellow-600'
  if (pct < 15) return 'text-yellow-400'
  if (pct < 30) return 'text-orange-400'
  return 'text-red-400'
}

const canonicalUrl = `https://metricshour.com/screener/${slug}/`
const metaDesc = truncateAtSentence(config.metaDesc, 155)

useHead({
  title: config.metaTitle,
  meta: [
    { name: 'description', content: metaDesc },
    { property: 'og:title', content: config.metaTitle },
    { property: 'og:description', content: metaDesc },
    { property: 'og:url', content: canonicalUrl },
    { property: 'og:type', content: 'website' },
    { property: 'og:image', content: 'https://cdn.metricshour.com/og/section/home.png' },
  ],
  link: [{ rel: 'canonical', href: canonicalUrl }]
})
</script>
