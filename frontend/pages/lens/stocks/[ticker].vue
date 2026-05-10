<template>
  <main class="max-w-3xl mx-auto px-4 py-8">
    <!-- Back -->
    <NuxtLink to="/lens/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">← Lens</NuxtLink>

    <!-- Loading -->
    <div v-if="pending" class="space-y-4">
      <div class="h-24 bg-[#111827] rounded-xl animate-pulse"/>
      <div class="h-32 bg-[#111827] rounded-xl animate-pulse"/>
      <div class="h-48 bg-[#111827] rounded-xl animate-pulse"/>
    </div>

    <!-- Error / not found -->
    <div v-else-if="error || !lensData" class="text-center py-16">
      <div class="text-4xl mb-3">🔭</div>
      <p class="text-gray-500 text-sm mb-4">{{ lensData === null ? 'Stock not found.' : 'Unable to load analysis.' }}</p>
      <NuxtLink to="/lens/" class="text-emerald-500 hover:text-emerald-400 text-sm">← Back to Lens</NuxtLink>
    </div>

    <template v-else>
      <!-- SECTION 1: Header -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-2xl p-5 mb-4">
        <div class="text-[10px] font-mono font-bold text-emerald-500 uppercase tracking-widest mb-2">MetricsHour Lens · Stocks</div>
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <span class="text-xl font-extrabold text-white font-mono">{{ lensData.ticker }}</span>
              <span class="text-gray-500 text-sm">{{ lensData.name }}</span>
              <span v-if="direction !== 'long'" class="text-xs px-2 py-0.5 rounded-full bg-red-950 text-red-400 border border-red-900">Short</span>
              <span v-else class="text-xs px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-900">Long</span>
              <span v-if="sizeUsd" class="text-xs text-gray-600">${{ Number(sizeUsd).toLocaleString() }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-lg font-extrabold font-mono text-white tabular-nums">
                {{ lensData.currency === 'GBp' ? (lensData.price / 100).toFixed(2) + '£' : '$' + (lensData.price ?? '—') }}
              </span>
              <span v-if="lensData.change_pct != null" class="text-sm font-semibold font-mono"
                :class="lensData.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ lensData.change_pct >= 0 ? '▲' : '▼' }} {{ Math.abs(lensData.change_pct).toFixed(2) }}%
              </span>
            </div>
            <div class="text-[10px] text-gray-600 mt-1">{{ lensData.exchange }} · {{ lensData.sector }}</div>
          </div>
          <div class="flex flex-col items-end gap-1">
            <span class="text-sm font-extrabold px-3 py-1.5 rounded-full border"
              :class="riskClass(lensData.risk?.level)">
              {{ riskIcon(lensData.risk?.level) }} {{ lensData.risk?.level }}
            </span>
            <span class="text-[10px] text-gray-600">Risk: {{ lensData.risk?.score }}/{{ lensData.risk?.level === 'ELEVATED' ? '10+' : '10' }}</span>
          </div>
        </div>
        <div class="text-[10px] text-gray-700 mt-2">{{ $t('lens.lastUpdated') }}: {{ fmtTs(lensData.last_updated) }}</div>
      </div>

      <!-- SECTION 2: What's Driving It (LLM insight) -->
      <div v-if="lensData.insight" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-emerald-500 uppercase tracking-wider mb-2">{{ $t('lens.sections.driving') }}</div>
        <p class="text-sm text-gray-200 leading-relaxed">{{ lensData.insight }}</p>
        <div class="text-[10px] text-gray-700 mt-2">{{ $t('lens.intelligence') }} · {{ fmtTs(lensData.last_updated) }}</div>
      </div>

      <!-- SECTION 3: Geographic Risk -->
      <div v-if="lensData.geo_risk?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.geoRisk') }}</div>
        <div class="space-y-3">
          <div v-for="g in lensData.geo_risk" :key="g.country_code" class="flex items-start gap-3">
            <span class="text-base shrink-0 mt-0.5">{{ g.risk_icon }}</span>
            <div class="flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm font-bold text-white">{{ g.flag }} {{ g.country_name }}</span>
                <span class="text-xs text-gray-500 font-mono">{{ g.revenue_pct?.toFixed(0) }}% of revenue</span>
              </div>
              <div class="text-xs text-gray-500 mt-0.5">{{ g.context }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- SECTION 4: Real Cost Estimate (only with size) -->
      <div v-if="lensData.cost" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.cost') }}</div>
        <div class="space-y-1.5 text-sm font-mono">
          <div class="flex justify-between">
            <span class="text-gray-500">{{ $t('lens.cost.entryPrice') }}</span>
            <span class="text-white">${{ lensData.cost.entry_price }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">{{ $t('lens.cost.slippage') }}</span>
            <span class="text-yellow-400">+${{ lensData.cost.slippage_usd }} ({{ lensData.cost.slippage_pct }}%)</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">{{ $t('lens.cost.fee') }}</span>
            <span class="text-yellow-400">+${{ lensData.cost.fee_usd }} ({{ lensData.cost.fee_pct }}%)</span>
          </div>
          <div class="border-t border-[#1f2937] pt-1.5 flex justify-between">
            <span class="text-gray-400 font-semibold">{{ $t('lens.cost.effectivePrice') }}</span>
            <span class="text-white font-bold">${{ lensData.cost.effective_price }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">{{ $t('lens.cost.breakEven') }}</span>
            <span class="text-gray-400">+{{ lensData.cost.break_even_pct }}%</span>
          </div>
        </div>
        <div class="text-[10px] text-gray-700 mt-2">{{ $t('lens.cost.disclaimer') }}</div>
      </div>

      <!-- SECTION 5: Stress Test (only if EPS data + size) -->
      <div v-if="lensData.stress_test" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.stress') }}</div>
        <div class="text-xs text-gray-400 mb-3">
          {{ $t('lens.stress.scenario', { country: lensData.stress_test.country_code }) }}
        </div>
        <div class="space-y-1.5 text-sm font-mono">
          <div class="flex justify-between">
            <span class="text-gray-500">{{ $t('lens.stress.epsImpact') }}</span>
            <span class="text-red-400">-${{ lensData.stress_test.eps_impact }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">{{ $t('lens.stress.priceImpact') }}</span>
            <span class="text-red-400">-${{ lensData.stress_test.price_impact_usd }} (-{{ lensData.stress_test.price_impact_pct }}%)</span>
          </div>
          <div v-if="lensData.stress_test.position_impact_usd" class="flex justify-between">
            <span class="text-gray-500">{{ $t('lens.stress.positionImpact') }}</span>
            <span class="text-red-400">-${{ Math.abs(lensData.stress_test.position_impact_usd).toLocaleString() }}</span>
          </div>
        </div>
        <div class="text-[10px] text-gray-700 mt-2">{{ $t('lens.stress.disclaimer') }}</div>
      </div>

      <!-- SECTION 6: What to Watch -->
      <div v-if="lensData.what_to_watch?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.watch') }}</div>
        <div class="space-y-1.5">
          <div v-for="w in lensData.what_to_watch" :key="w.event" class="flex items-center gap-2 text-sm">
            <span class="text-emerald-600">→</span>
            <span class="text-gray-300">{{ w.event }}</span>
            <span class="text-gray-600 text-xs">— {{ w.date }}</span>
            <span v-if="w.country_code" class="text-[10px] text-gray-700 font-mono">{{ w.country_code }}</span>
          </div>
        </div>
      </div>

      <!-- SECTION 7: Lower Risk Alternatives -->
      <div v-if="alternatives?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.alternatives') }}</div>
        <div class="space-y-2">
          <NuxtLink v-for="s in alternatives" :key="s.symbol"
            :to="`/lens/stocks/${s.symbol.toLowerCase()}/`"
            class="flex items-center gap-3 bg-[#0d1520] border border-[#1f2937] hover:border-emerald-700 rounded-lg px-3 py-2 transition-colors">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="text-xs font-mono font-bold text-emerald-400">{{ s.symbol }}</span>
                <span class="text-xs text-gray-500 truncate">{{ s.name }}</span>
              </div>
              <div class="text-[10px] text-gray-600">{{ s.sector }} · {{ s.china_pct != null ? `CN ${s.china_pct.toFixed(0)}%` : 'Low CN' }}</div>
            </div>
            <span class="text-[10px] text-emerald-600">Analyze →</span>
          </NuxtLink>
        </div>
      </div>

      <!-- About Lens -->
      <div class="bg-[#0a0f1a] border border-[#1a2435] rounded-xl p-4 mb-4 text-xs text-gray-500 leading-relaxed">
        <strong class="text-gray-400">How Lens works:</strong> Lens scores geopolitical and macro risk for {{ lensData.ticker }} using SEC EDGAR geographic revenue data, bilateral trade exposure, upcoming earnings, and FRED macro series.
        A high risk score indicates significant revenue concentration in trade-sensitive or politically volatile markets.
        Use it to compare entry timing, size your position, or understand which macro events matter most for this stock.
      </div>

      <!-- SECTION 8: Actions -->
      <div class="flex flex-wrap gap-3">
        <EmailAlertModal v-model="showAlert" :asset-symbol="lensData.ticker" :asset-name="lensData.name" asset-type="stock" />
        <button @click="showAlert = true"
          class="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold bg-[#111827] border border-[#1f2937] text-gray-300 hover:border-emerald-700 hover:text-emerald-400 transition-all">
          🔔 Set Alert
        </button>
        <NuxtLink to="/lens/" class="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold bg-[#111827] border border-[#1f2937] text-gray-400 hover:text-white transition-all">
          ← Analyze Another
        </NuxtLink>
        <ShareCard type="stock" :entity-code="lensData.ticker" />
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const { t } = useI18n()
const route  = useRoute()
const ticker = (route.params.ticker as string).toUpperCase()

const direction = computed(() => String(route.query.direction || 'long'))
const sizeUsd   = computed(() => route.query.size ? Number(route.query.size) : null)

const { get } = useApi()

const queryStr = computed(() => {
  const p: Record<string, string> = { direction: direction.value }
  if (sizeUsd.value) p.size = String(sizeUsd.value)
  return new URLSearchParams(p).toString()
})

const { public: { apiBase } } = useRuntimeConfig()

const { data: lensData, pending, error } = await useAsyncData(
  `lens-stock-${ticker}-${direction.value}-${sizeUsd.value || 'none'}`,
  () => get<any>(`/api/lens/stocks/${ticker}?${queryStr.value}`).catch(() => null),
)

// Lower risk alternatives — same sector, less China exposure
const { data: alternatives } = useAsyncData(
  `lens-alternatives-${ticker}`,
  async () => {
    if (!lensData.value?.sector) return []
    const chinaCap = Math.max(0, (lensData.value.geo_risk?.find((g: any) => g.country_code === 'CN')?.revenue_pct || 1) - 1)
    const data = await $fetch<any>(`${apiBase}/api/screener`, {
      params: { sector: lensData.value.sector, china_max: chinaCap, sort_by: 'market_cap', limit: 6 },
    }).catch(() => null)
    return ((data?.results || []) as any[]).filter((s: any) => s.symbol !== ticker).slice(0, 3)
  },
  { server: false, watch: [() => lensData.value?.sector] },
)

const showAlert = ref(false)

function riskClass(level: string | undefined): string {
  if (level === 'ELEVATED')  return 'bg-red-950 text-red-300 border-red-800'
  if (level === 'MODERATE')  return 'bg-amber-950 text-amber-300 border-amber-800'
  return 'bg-emerald-950 text-emerald-300 border-emerald-800'
}
function riskIcon(level: string | undefined): string {
  if (level === 'ELEVATED') return '🔴'
  if (level === 'MODERATE') return '🟡'
  return '🟢'
}
function fmtTs(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC'
}

const _name = lensData.value?.name || ticker
const _hasLensContent = computed(() =>
  (lensData.value?.geo_risk?.length ?? 0) > 0 || (lensData.value?.stress_test != null)
)
useSeoMeta({
  title: `${ticker} Pre-Trade Analysis — MetricsHour Lens`,
  description: `Lens analysis for ${_name}: geographic risk, macro drivers, cost estimate. Risk level: ${lensData.value?.risk?.level || 'loading'}.`,
  robots: computed(() => _hasLensContent.value ? 'index, follow' : 'noindex, follow'),
})
useHead({ link: [{ rel: 'canonical', href: `https://metricshour.com/lens/stocks/${ticker.toLowerCase()}/` }] })
</script>
