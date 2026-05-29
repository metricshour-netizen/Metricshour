<template>
  <main class="max-w-7xl mx-auto px-4 py-8">
    <Breadcrumb :crumbs="[
      { label: $t('breadcrumb.home'), href: '/' },
      { label: $t('breadcrumb.smartMoney'), href: '/smart-money/' },
      { label: data?.name || slug }
    ]" />

    <!-- Loading -->
    <div v-if="pending" class="space-y-4">
      <div class="h-32 bg-[#111827] rounded-2xl animate-pulse"/>
      <div class="h-12 bg-[#111827] rounded-xl animate-pulse"/>
      <div class="h-64 bg-[#111827] rounded-xl animate-pulse"/>
    </div>

    <div v-else-if="!data" class="text-center py-16 text-gray-600">
      <p class="text-sm">{{ $t('smartMoney.notFound') }}</p>
      <NuxtLink to="/smart-money/" class="text-emerald-500 text-xs mt-2 inline-block">{{ $t('smartMoney.backLink') }}</NuxtLink>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-2xl p-6 mb-5">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div class="text-[10px] font-mono font-bold text-emerald-500 uppercase tracking-widest mb-1">{{ $t('smartMoney.badge') }}</div>
            <h1 class="text-xl sm:text-2xl font-extrabold text-white mb-1">{{ data.name }}</h1>
            <div class="text-sm text-gray-500 mb-3">{{ data.fund_name }}</div>
            <p v-if="data.description" class="text-xs text-gray-600 max-w-xl">{{ data.description }}</p>
          </div>
          <div class="text-right">
            <div v-if="data.total_value_usd" class="text-2xl font-extrabold font-mono text-white tabular-nums">${{ fmtB(data.total_value_usd) }}</div>
            <div v-if="data.total_value_usd" class="text-[10px] text-gray-600 uppercase tracking-wider">{{ $t('smartMoney.portfolio.value') }}</div>
            <div v-if="data.holding_count" class="text-sm text-gray-400 mt-1">{{ $t('smartMoney.holdingsCount', { count: data.holding_count }) }}</div>
          </div>
        </div>

        <!-- Quarter selector -->
        <div v-if="data.quarters?.length > 1" class="flex gap-2 mt-4 flex-wrap">
          <button
            v-for="q in data.quarters"
            :key="q"
            @click="selectedQuarter = q"
            class="px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all border"
            :class="selectedQuarter === q
              ? 'bg-emerald-600 border-emerald-500 text-white'
              : 'bg-[#111827] border-[#1f2937] text-gray-500 hover:text-white'">
            {{ q }}
          </button>
        </div>
        <div v-else-if="data.latest_quarter" class="mt-3 text-xs font-mono text-gray-600">
          {{ $t('smartMoney.portfolio.latest', { quarter: data.latest_quarter }) }}
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex gap-1 mb-5 flex-wrap border-b border-[#1f2937] pb-0">
        <button v-for="tab in TABS" :key="tab.key"
          @click="activeTab = tab.key"
          class="px-4 py-2.5 text-xs font-semibold transition-all border-b-2 -mb-px"
          :class="activeTab === tab.key
            ? 'border-emerald-500 text-emerald-400'
            : 'border-transparent text-gray-500 hover:text-gray-300'">
          {{ tab.label }}
          <span v-if="tab.count != null" class="ml-1.5 text-[10px] bg-[#1f2937] text-gray-600 px-1.5 py-0.5 rounded-full">{{ tab.count }}</span>
        </button>
      </div>

      <!-- TAB: Holdings -->
      <template v-if="activeTab === 'holdings'">
        <div v-if="!data.holdings?.length" class="max-w-md mx-auto py-10 text-center">
          <p class="text-sm text-gray-300 mb-1 font-medium">{{ data.name }}</p>
          <p class="text-xs text-gray-500 mb-5">{{ $t('smartMoneyAlert.heading', { name: data.name }) }}</p>
          <p class="text-xs text-gray-400 mb-3">{{ $t('smartMoneyAlert.subheading') }}</p>
          <div class="flex gap-2 max-w-sm mx-auto mb-2">
            <input
              v-model="alertEmail"
              type="email"
              :placeholder="$t('smartMoneyAlert.placeholder')"
              class="flex-1 bg-[#0d1520] border border-[#1f2937] text-white text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-emerald-600"
              @keydown.enter="submitDetailAlert"
            />
            <button @click="submitDetailAlert"
              :disabled="alertSubmitting"
              class="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white text-sm font-semibold transition-colors shrink-0 disabled:opacity-50">
              {{ alertSubmitting ? $t('smartMoneyAlert.submitting') : $t('smartMoneyAlert.submit') }}
            </button>
          </div>
          <p v-if="alertSuccess" class="text-xs text-emerald-400">{{ alertSuccess }}</p>
          <p v-else class="text-[10px] text-gray-700">{{ $t('smartMoneyAlert.disclaimer') }}</p>
        </div>

        <template v-else>
        <!-- Cap notice for large quant funds (200+ positions capped) -->
        <p v-if="data.holdings_total > data.holdings_shown" class="text-xs text-amber-500/70 mb-3">
          Showing top {{ data.holdings_shown }} of {{ data.holdings_total?.toLocaleString() }} positions by value
        </p>

        <!-- Desktop table -->
        <div class="hidden sm:block bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-x-auto">
          <table class="w-full min-w-[640px] text-sm">
            <thead class="bg-[#111827] text-[10px] text-gray-500 uppercase tracking-widest sticky top-12 z-10">
              <tr>
                <th class="px-4 py-2.5 text-left w-8">{{ $t('smartMoney.table.rank') }}</th>
                <th class="px-4 py-2.5 text-left">{{ $t('smartMoney.table.ticker') }}</th>
                <th class="px-4 py-2.5 text-left hidden md:table-cell">{{ $t('smartMoney.table.company') }}</th>
                <th class="px-4 py-2.5 text-right">{{ $t('smartMoney.table.shares') }}</th>
                <th class="px-4 py-2.5 text-right">{{ $t('smartMoney.table.value') }}</th>
                <th class="px-4 py-2.5 text-right">{{ $t('smartMoney.table.portfolioPct') }}</th>
                <th class="px-4 py-2.5 text-right">{{ $t('smartMoney.table.change') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(h, i) in data.holdings" :key="h.symbol + i"
                class="border-t border-[#1f2937] hover:bg-[#111827]/60 transition-colors">
                <td class="px-4 py-3 text-gray-700 text-xs font-mono">{{ i + 1 }}</td>
                <td class="px-4 py-3">
                  <NuxtLink v-if="h.symbol" :to="`/lens/stocks/${h.symbol.toLowerCase()}/`"
                    class="font-mono text-xs font-bold text-emerald-400 hover:text-emerald-300">{{ h.symbol }}</NuxtLink>
                  <span v-else class="font-mono text-xs text-gray-600">—</span>
                </td>
                <td class="px-4 py-3 text-gray-400 text-xs hidden md:table-cell truncate max-w-[200px]">{{ h.company_name }}</td>
                <td class="px-4 py-3 text-right text-gray-400 text-xs tabular-nums font-mono">{{ fmtShares(h.shares) }}</td>
                <td class="px-4 py-3 text-right text-white text-xs tabular-nums font-mono">${{ fmtB(h.value_usd) }}</td>
                <td class="px-4 py-3 text-right text-xs tabular-nums">
                  <span v-if="h.portfolio_pct" class="text-gray-300 font-mono">{{ h.portfolio_pct.toFixed(1) }}%</span>
                  <div v-if="h.portfolio_pct" class="mt-1 h-0.5 bg-[#1f2937] rounded-full overflow-hidden">
                    <div class="h-full bg-emerald-500/60 rounded-full" :style="{ width: `${Math.min(h.portfolio_pct * 5, 100)}%` }"/>
                  </div>
                </td>
                <td class="px-4 py-3 text-right">
                  <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                    :class="changeClass(h.change_type)">
                    {{ changeLabel(h.change_type) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile cards -->
        <div class="sm:hidden space-y-2">
          <NuxtLink v-for="(h, i) in data.holdings" :key="h.symbol + i"
            :to="h.symbol ? `/stocks/${h.symbol.toLowerCase()}/` : ''"
            class="block bg-[#0d1520] border border-[#1f2937] rounded-xl px-4 py-3"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-mono text-xs font-bold text-emerald-400">{{ h.symbol || '—' }}</span>
                  <span class="text-[10px] text-gray-500 truncate">{{ h.company_name }}</span>
                </div>
                <div class="flex items-center gap-3 mt-1 text-[10px] font-mono text-gray-500">
                  <span v-if="h.value_usd">${{ fmtB(h.value_usd) }}</span>
                  <span v-if="h.portfolio_pct">{{ h.portfolio_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full shrink-0"
                :class="changeClass(h.change_type)">
                {{ changeLabel(h.change_type) }}
              </span>
            </div>
          </NuxtLink>
        </div>
        </template><!-- end v-else (has holdings) -->
      </template>

      <!-- TAB: Changes -->
      <template v-else-if="activeTab === 'changes'">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div v-for="section in CHANGE_SECTIONS" :key="section.key">
            <h3 class="text-xs font-bold uppercase tracking-widest mb-3"
              :class="section.color">{{ section.label }}</h3>
            <div v-if="data.changes?.[section.key]?.length" class="space-y-1.5">
              <NuxtLink v-for="h in data.changes[section.key]" :key="h.symbol"
                :to="h.symbol ? `/stocks/${h.symbol.toLowerCase()}/` : ''"
                class="flex items-center justify-between bg-[#0d1520] border border-[#1f2937] rounded-lg px-3 py-2 hover:border-emerald-900/60 transition-colors group">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="font-mono text-xs font-bold text-emerald-400 w-14 shrink-0">{{ h.symbol || '—' }}</span>
                  <span class="text-[10px] text-gray-500 truncate">{{ h.company_name }}</span>
                </div>
                <span class="text-xs font-mono text-gray-400 shrink-0 ml-2">${{ fmtB(h.value_usd) }}</span>
              </NuxtLink>
            </div>
            <p v-else class="text-xs text-gray-700 py-2">
              {{ $t('smartMoney.noChanges', { type: section.label.toLowerCase() }) }}
            </p>
          </div>
        </div>
      </template>

      <!-- TAB: Geo Risk View -->
      <template v-else-if="activeTab === 'georisk'">
        <div class="bg-[#0d1520] border border-[#1f2937] rounded-xl p-5 mb-4">
          <div class="text-xs font-bold text-emerald-500 uppercase tracking-wider mb-1">{{ $t('smartMoney.geoRisk.title') }}</div>
          <p class="text-[11px] text-gray-500 mb-5">{{ $t('smartMoney.geoRisk.subtitle') }}</p>

          <div v-if="geoExposure.length" class="space-y-3">
            <div v-for="g in geoExposure" :key="g.code" class="flex items-center gap-3">
              <div class="w-6 text-center shrink-0">{{ g.flag }}</div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between mb-0.5">
                  <span class="text-xs text-white font-medium">{{ g.name }}</span>
                  <span class="text-xs font-mono text-gray-400 tabular-nums">{{ g.pct.toFixed(1) }}%</span>
                </div>
                <div class="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                  <div class="h-full rounded-full transition-all"
                    :class="riskBarColor(g)"
                    :style="{ width: `${Math.min(g.pct * 2, 100)}%` }"/>
                </div>
                <div v-if="g.risk_note" class="text-[10px] text-gray-600 mt-0.5">{{ g.risk_note }}</div>
              </div>
            </div>
          </div>
          <p v-else class="text-xs text-gray-600">{{ $t('smartMoney.geoRisk.noData') }}</p>
        </div>
      </template>

      <!-- TAB: Sectors / History — placeholder until more data -->
      <template v-else>
        <div class="text-center py-12 text-gray-600 text-sm">
          {{ $t('smartMoney.noHolderData') }}
        </div>
      </template>
    </template>
  </main>
</template>

<script setup lang="ts">
const { t } = useI18n()
const { get } = useApi()
const route = useRoute()
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const slug = route.params.slug as string
const selectedQuarter = ref<string | null>(null)
const activeTab = ref('holdings')

const { data, pending } = await useAsyncData(
  `sm-investor-${slug}`,
  () => {
    const q = selectedQuarter.value ? `?quarter=${encodeURIComponent(selectedQuarter.value)}` : ''
    return get<any>(`/api/smartmoney/investors/${slug}${q}`).catch(() => null)
  },
  { watch: [selectedQuarter] },
)

watchEffect(() => {
  if (data.value?.latest_quarter && !selectedQuarter.value) {
    selectedQuarter.value = data.value.latest_quarter
  }
})

const TABS = computed(() => [
  { key: 'holdings', label: t('smartMoney.tabs.overview'),  count: data.value?.holdings?.length ?? null },
  { key: 'changes',  label: t('smartMoney.tabs.changes'),   count: null },
  { key: 'georisk',  label: t('smartMoney.tabs.geoRisk'),   count: null },
])

const CHANGE_SECTIONS = computed(() => [
  { key: 'new',       label: t('smartMoney.changes.new'),       color: 'text-emerald-400' },
  { key: 'increased', label: t('smartMoney.changes.increased'),  color: 'text-emerald-600' },
  { key: 'decreased', label: t('smartMoney.changes.decreased'),  color: 'text-amber-500' },
  { key: 'sold',      label: t('smartMoney.changes.sold'),       color: 'text-red-500' },
])

const { data: geoExposure } = await useAsyncData(
  () => `sm-geo-${slug}-${selectedQuarter.value || 'latest'}`,
  () => {
    const q = selectedQuarter.value ? `?quarter=${encodeURIComponent(selectedQuarter.value)}` : ''
    return $fetch<any[]>(`/api/smartmoney/investors/${slug}/geo${q}`, { baseURL: apiBase }).catch(() => [])
  },
  { watch: [selectedQuarter], default: () => [] },
)

const { post } = useApi()
const alertEmail = ref('')
const alertSubmitting = ref(false)
const alertSuccess = ref('')

async function submitDetailAlert() {
  const email = alertEmail.value.trim()
  if (!email || !email.includes('@')) return
  alertSubmitting.value = true
  try {
    await post('/api/smartmoney/alerts', { email, investor_slug: slug })
    alertSuccess.value = t('smartMoneyAlert.success', { name: data.value?.name || slug })
    alertEmail.value = ''
  } catch {
    alertSuccess.value = t('emailAlert.error')
  } finally {
    alertSubmitting.value = false
  }
}

function changeLabel(type: string): string {
  const map: Record<string, string> = {
    new: t('smartMoney.change.new'),
    increased: t('smartMoney.change.increased'),
    decreased: t('smartMoney.change.decreased'),
    sold: t('smartMoney.change.sold'),
    unchanged: t('smartMoney.change.unchanged'),
  }
  return map[type] || type
}

function changeClass(type: string): string {
  if (type === 'new') return 'bg-emerald-900/50 text-emerald-400 border border-emerald-800/50'
  if (type === 'increased') return 'bg-emerald-950/80 text-emerald-600 border border-emerald-900/30'
  if (type === 'decreased') return 'bg-amber-950/50 text-amber-500 border border-amber-900/30'
  if (type === 'sold') return 'bg-red-950/50 text-red-400 border border-red-900/30'
  return 'bg-[#1f2937] text-gray-500 border border-[#374151]'
}

function riskBarColor(g: any): string {
  if (g.risk_level === 'high') return 'bg-red-500'
  if (g.risk_level === 'medium') return 'bg-amber-500'
  return 'bg-emerald-500'
}

function fmtB(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(0)}M`
  return `${(v / 1e3).toFixed(0)}K`
}

function fmtShares(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`
  return String(v)
}

const investorName = computed(() => data.value?.name || slug)
const fundName = computed(() => data.value?.fund_name || '')

useSeoMeta({
  title: () => `${investorName.value} Portfolio — ${fundName.value} 13F Holdings | MetricsHour`,
  description: () => `Track ${investorName.value}'s latest 13F filing. See what ${fundName.value} is buying and selling this quarter with geographic risk analysis.`,
  ogTitle: () => `${investorName.value} Portfolio — ${fundName.value} 13F Holdings | MetricsHour`,
  ogDescription: () => `Track ${investorName.value}'s latest 13F filing. See what ${fundName.value} is buying and selling this quarter with geographic risk analysis.`,
  ogImage: 'https://cdn.metricshour.com/og/section/stocks.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  ogType: 'website',
  twitterTitle: () => `${investorName.value} Portfolio — ${fundName.value} 13F Holdings | MetricsHour`,
  twitterDescription: () => `Track ${investorName.value}'s latest 13F filing. See what ${fundName.value} is buying and selling this quarter with geographic risk analysis.`,
  twitterImage: 'https://cdn.metricshour.com/og/section/stocks.png',
  twitterCard: 'summary_large_image',
  robots: 'index, follow',
})
useHead({
  link: [{ rel: 'canonical', href: `https://metricshour.com/smart-money/${slug}/` }],
})
</script>
