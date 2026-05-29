<template>
  <main class="max-w-3xl mx-auto px-4 py-8">
    <Breadcrumb :crumbs="[
      { label: $t('breadcrumb.home'), href: '/' },
      { label: $t('breadcrumb.tools'), href: '/tools/' },
      { label: $t('breadcrumb.lens'), href: '/lens/' },
      { label: ticker }
    ]" />

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

      <!-- SECTION 1B: Mini pill row — key signals at a glance (mobile-first) -->
      <div v-if="lensData.geo_risk?.length || lensData.risk?.level || earningsPill"
           class="flex flex-wrap gap-1.5 mb-4">
        <!-- Top 3 country pills -->
        <span
          v-for="g in lensData.geo_risk?.slice(0, 3)"
          :key="g.country_code"
          class="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-full border"
          :class="pillColorClass(g.risk_icon)"
        >
          {{ g.flag }} {{ g.country_code }}: {{ g.revenue_pct?.toFixed(0) }}%
        </span>
        <!-- Risk level pill -->
        <span v-if="lensData.risk?.level"
          class="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-1 rounded-full border"
          :class="riskPillClass(lensData.risk.level)">
          {{ riskIcon(lensData.risk.level) }} {{ lensData.risk.level }}
        </span>
        <!-- Earnings pill (only within 30 days) -->
        <span v-if="earningsPill"
          class="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-full border border-sky-800 bg-sky-950/50 text-sky-300">
          📅 Earnings: {{ earningsPill }}
        </span>
      </div>

      <!-- SECTION 2: Risk Tearsheet -->
      <div v-if="lensData.geo_risk?.length || lensData.insight" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="flex items-center justify-between mb-2">
          <div class="text-xs font-bold text-emerald-500 uppercase tracking-wider">Risk Tearsheet — {{ lensData.ticker || ticker }}</div>
          <div class="text-[10px] text-gray-700">{{ fmtTs(lensData.last_updated) }}</div>
        </div>
        <div class="border-t border-[#2d3748] mb-3" />

        <!-- Revenue Concentration -->
        <div v-if="lensData.geo_risk?.length" class="mb-3">
          <div class="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">Revenue Concentration</div>
          <div class="space-y-0.5 text-xs text-gray-300 font-mono">
            <div v-if="tearsheetDomesticPct !== null">● Domestic: {{ tearsheetDomesticPct.toFixed(0) }}% — {{ tearsheetDomesticLabel }}</div>
            <div v-if="tearsheetIntlPct !== null">● International: {{ tearsheetIntlPct }}% · {{ lensData.geo_risk.length }} markets</div>
            <div v-if="lensData.geo_risk[0]">● Largest: {{ lensData.geo_risk[0].flag }} {{ lensData.geo_risk[0].country_name }} {{ lensData.geo_risk[0].revenue_pct?.toFixed(0) }}%</div>
          </div>
        </div>

        <!-- Geo Risk Factors (LLM insight split into bullets) -->
        <div v-if="tearsheetInsightBullets.length" class="mb-3">
          <div class="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">Geo Risk Factors</div>
          <div class="space-y-1 text-xs text-gray-300 font-mono">
            <div v-for="bullet in tearsheetInsightBullets" :key="bullet">● {{ bullet }}</div>
          </div>
        </div>

        <!-- Macro Sensitivity -->
        <div v-if="tearsheetMacroLines.length" class="mb-3">
          <div class="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">Macro Sensitivity</div>
          <div class="space-y-0.5 text-xs text-gray-300 font-mono">
            <div v-for="line in tearsheetMacroLines" :key="line">● {{ line }}</div>
          </div>
        </div>

        <!-- EPS Sensitivity -->
        <div v-if="lensData.stress_test" class="mb-3">
          <div class="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">EPS Sensitivity</div>
          <div class="text-xs text-gray-300 font-mono">
            ● {{ lensData.stress_test.scenario }}: EPS {{ lensData.stress_test.eps_impact >= 0 ? '+' : '' }}{{ lensData.stress_test.eps_impact?.toFixed(2) }}
            <span v-if="lensData.stress_test.price_impact_pct"> · price {{ lensData.stress_test.price_impact_pct?.toFixed(1) }}%</span>
          </div>
        </div>

        <!-- Footer -->
        <div class="border-t border-[#2d3748] pt-2 mt-1 flex items-center justify-between">
          <span class="text-[10px] font-bold text-gray-500 uppercase tracking-wider">
            Concentration Risk:
            <span :class="riskTextClass(lensData.risk?.level)">{{ tearsheetRiskLabel }}</span>
          </span>
          <span class="text-[10px] text-gray-700">{{ $t('lens.intelligence') }}</span>
        </div>
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

      <!-- SECTION 7: Smart Money — who holds this stock -->
      <div v-if="holders?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="flex items-center justify-between mb-3">
          <div class="text-xs font-bold text-white uppercase tracking-wider">{{ $t('smartMoney.holders.title', { ticker }) }}</div>
          <NuxtLink :to="`/smart-money/`" class="text-[10px] text-emerald-600 hover:text-emerald-400 transition-colors">View all →</NuxtLink>
        </div>
        <div class="space-y-2">
          <NuxtLink v-for="h in holders.slice(0, 5)" :key="h.investor_slug"
            :to="`/smart-money/${h.investor_slug}/`"
            class="flex items-center justify-between bg-[#0d1520] border border-[#1f2937] hover:border-emerald-900/60 rounded-lg px-3 py-2 transition-colors group">
            <div class="min-w-0">
              <div class="text-xs font-semibold text-white group-hover:text-emerald-400 transition-colors">{{ h.investor_name }}</div>
              <div class="text-[10px] text-gray-600">{{ h.fund_name }}</div>
            </div>
            <div class="text-right ml-3 shrink-0">
              <div class="text-xs font-mono text-gray-400">{{ h.portfolio_pct != null ? `${h.portfolio_pct}% portfolio` : '' }}</div>
              <div class="text-[10px] font-bold mt-0.5"
                :class="h.change_type === 'new' || h.change_type === 'increased' ? 'text-emerald-500' : h.change_type === 'decreased' || h.change_type === 'sold' ? 'text-red-500' : 'text-gray-600'">
                {{ changeLabel(h.change_type) }} · {{ h.quarter_label }}
              </div>
            </div>
          </NuxtLink>
        </div>
        <div class="mt-2 text-[10px] text-gray-700">Source: SEC EDGAR 13F filings</div>
      </div>

      <!-- SECTION 9: Lower Risk Alternatives -->
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

      <!-- SECTION 7B: Contextual CTA -->
      <ContextualCTA
        context-type="lens"
        :asset-symbol="lensData.ticker || ticker"
        :asset-name="lensData.name || ticker"
        class="mb-4"
      />

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

// Smart Money: who holds this stock
const { data: holders } = useAsyncData(
  `sm-holders-${ticker}`,
  () => get<any[]>(`/api/smartmoney/holders/${ticker}?limit=5`).catch(() => []),
  { server: false },
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

function changeLabel(type: string): string {
  const { t } = useI18n()
  const map: Record<string, string> = {
    new: t('smartMoney.change.new'),
    increased: t('smartMoney.change.increased'),
    decreased: t('smartMoney.change.decreased'),
    sold: t('smartMoney.change.sold'),
    unchanged: t('smartMoney.change.unchanged'),
  }
  return map[type] || type
}

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

function pillColorClass(riskIcon: string): string {
  if (riskIcon === '🔴') return 'border-red-800 bg-red-950/50 text-red-300'
  if (riskIcon === '🟡') return 'border-amber-800 bg-amber-950/50 text-amber-300'
  return 'border-emerald-900 bg-emerald-950/30 text-emerald-400'
}

function riskPillClass(level: string): string {
  if (level === 'ELEVATED') return 'border-red-800 bg-red-950/50 text-red-300'
  if (level === 'MODERATE') return 'border-amber-800 bg-amber-950/50 text-amber-300'
  return 'border-emerald-900 bg-emerald-950/30 text-emerald-400'
}

// Earnings pill — show if earnings within 30 days
const earningsPill = computed((): string | null => {
  const w = lensData.value?.what_to_watch
  if (!w?.length) return null
  const earningsEvent = w.find((e: any) => e.event?.toLowerCase().includes('earning'))
  if (!earningsEvent) return null
  const eventDate = new Date(earningsEvent.date)
  const now = new Date()
  const daysAway = (eventDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
  if (daysAway < 0 || daysAway > 30) return null
  return eventDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
})

// ── Tearsheet computed values ─────────────────────────────────────────────────
const tearsheetDomesticPct = computed((): number | null => {
  const geo = lensData.value?.geo_risk
  if (!geo?.length) return null
  const us = geo.find((g: any) => g.country_code === 'US')
  return us ? us.revenue_pct : geo[0].revenue_pct
})

const tearsheetDomesticLabel = computed((): string => {
  const pct = tearsheetDomesticPct.value
  if (pct === null) return ''
  if (pct >= 70) return 'highly domestic'
  if (pct >= 50) return 'majority domestic'
  if (pct >= 30) return 'significant exposure'
  return 'minor exposure'
})

const tearsheetIntlPct = computed((): number | null => {
  if (tearsheetDomesticPct.value === null) return null
  return Math.round(100 - tearsheetDomesticPct.value)
})

const tearsheetInsightBullets = computed((): string[] => {
  const text = lensData.value?.insight
  if (!text) return []
  return text
    .split(/\.\s+/)
    .map((s: string) => s.replace(/\.$/, '').trim())
    .filter((s: string) => s.length > 12)
    .slice(0, 3)
})

const tearsheetMacroLines = computed((): string[] => {
  const geo = lensData.value?.geo_risk
  if (!geo?.length) return []
  const lines: string[] = []
  for (const g of geo.slice(0, 2)) {
    if (g.risk_level === 'high' && g.context) {
      lines.push(`${g.country_name}: ${g.context}`)
    } else if (g.inflation_pct != null && g.inflation_pct > 4) {
      lines.push(`${g.country_name}: ${g.revenue_pct?.toFixed(0)}% revenue · inflation ${g.inflation_pct?.toFixed(1)}%`)
    } else if (g.context && g.context !== 'No active macro threat identified') {
      lines.push(`${g.country_name}: ${g.context}`)
    }
  }
  return lines.slice(0, 2)
})

const tearsheetRiskLabel = computed((): string => {
  const level = lensData.value?.risk?.level
  if (level === 'ELEVATED') return 'HIGH'
  if (level === 'MODERATE') return 'MOD'
  return 'LOW'
})

function riskTextClass(level: string | undefined): string {
  if (level === 'ELEVATED') return 'text-red-400'
  if (level === 'MODERATE') return 'text-amber-400'
  return 'text-emerald-400'
}
// ─────────────────────────────────────────────────────────────────────────────

const _name = lensData.value?.name || ticker
const _hasLensContent = computed(() =>
  (lensData.value?.geo_risk?.length ?? 0) > 0 || (lensData.value?.stress_test != null)
)
useSeoMeta({
  title: `${ticker} Pre-Trade Analysis — MetricsHour Lens`,
  description: `Lens analysis for ${_name}: geographic risk, macro drivers, cost estimate. Risk level: ${lensData.value?.risk?.level || 'loading'}.`,
  robots: computed(() => _hasLensContent.value ? 'index, follow' : 'noindex, follow'),
})
useHead({
  link: [{ rel: 'canonical', href: `https://metricshour.com/lens/stocks/${ticker.toLowerCase()}/` }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@graph': [
        {
          '@type': 'WebPage',
          '@id': `https://metricshour.com/lens/stocks/${ticker.toLowerCase()}/`,
          url: `https://metricshour.com/lens/stocks/${ticker.toLowerCase()}/`,
          name: `${ticker} Pre-Trade Risk Analysis — MetricsHour Lens`,
          description: `Geographic revenue exposure, macro risk drivers and trade sensitivity for ${_name}. Risk level: ${lensData.value?.risk?.level || 'see page'}.`,
          isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
          about: {
            '@type': 'Corporation',
            name: _name,
            tickerSymbol: ticker,
            url: `https://metricshour.com/stocks/${ticker.toLowerCase()}/`,
          },
        },
        {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'Lens', item: 'https://metricshour.com/lens/' },
            { '@type': 'ListItem', position: 3, name: ticker, item: `https://metricshour.com/lens/stocks/${ticker.toLowerCase()}/` },
          ],
        },
      ],
    }),
  }],
})
</script>
