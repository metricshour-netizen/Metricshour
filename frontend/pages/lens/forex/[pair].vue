<template>
  <main class="max-w-3xl mx-auto px-4 py-8">
    <NuxtLink to="/lens/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">← Lens</NuxtLink>

    <div v-if="pending" class="space-y-4">
      <div class="h-24 bg-[#111827] rounded-xl animate-pulse"/>
      <div class="h-32 bg-[#111827] rounded-xl animate-pulse"/>
      <div class="h-48 bg-[#111827] rounded-xl animate-pulse"/>
    </div>

    <div v-else-if="error || !lensData" class="text-center py-16">
      <div class="text-4xl mb-3">💱</div>
      <p class="text-gray-500 text-sm mb-4">Pair not found or analysis unavailable.</p>
      <NuxtLink to="/lens/" class="text-emerald-500 hover:text-emerald-400 text-sm">← Back to Lens</NuxtLink>
    </div>

    <template v-else>
      <!-- SECTION 1: Header -->
      <div class="bg-[#0d1520] border border-[#1f2937] rounded-2xl p-5 mb-4">
        <div class="text-[10px] font-mono font-bold text-emerald-500 uppercase tracking-widest mb-2">MetricsHour Lens · Forex</div>
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <span class="text-xl font-extrabold text-white font-mono">{{ lensData.pair }}</span>
              <span class="text-gray-500 text-sm">{{ lensData.comparison?.base_name }} / {{ lensData.comparison?.quote_name }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full"
                :class="direction === 'long' ? 'bg-emerald-950 text-emerald-400 border border-emerald-900' : 'bg-red-950 text-red-400 border border-red-900'">
                {{ direction === 'long' ? $t('lens.direction.long') : $t('lens.direction.short') }}
              </span>
              <span v-if="sizeUsd" class="text-xs text-gray-600">${{ Number(sizeUsd).toLocaleString() }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-lg font-extrabold font-mono text-white tabular-nums">{{ lensData.rate?.toFixed(5) || '—' }}</span>
              <span v-if="lensData.change_pct != null" class="text-sm font-semibold font-mono"
                :class="lensData.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ lensData.change_pct >= 0 ? '▲' : '▼' }} {{ Math.abs(lensData.change_pct).toFixed(4) }}%
              </span>
            </div>
          </div>
          <div class="flex flex-col items-end gap-1">
            <span class="text-sm font-extrabold px-3 py-1.5 rounded-full border"
              :class="riskClass(lensData.risk?.level)">
              {{ riskIcon(lensData.risk?.level) }} {{ lensData.risk?.level }}
            </span>
            <span class="text-[10px] text-gray-600">Volatility Risk: {{ lensData.risk?.score }}/12</span>
          </div>
        </div>
        <div class="text-[10px] text-gray-700 mt-2">{{ $t('lens.lastUpdated') }}: {{ fmtTs(lensData.last_updated) }}</div>
      </div>

      <!-- SECTION 2: Driving Forces (LLM) -->
      <div v-if="lensData.insight" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-emerald-500 uppercase tracking-wider mb-2">{{ $t('lens.sections.driving') }}</div>
        <p class="text-sm text-gray-200 leading-relaxed">{{ lensData.insight }}</p>
        <div class="text-[10px] text-gray-700 mt-2">{{ $t('lens.intelligence') }} · {{ fmtTs(lensData.last_updated) }}</div>
      </div>

      <!-- SECTION 3: Country Comparison -->
      <div v-if="lensData.comparison" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.countryComparison') }}</div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#1f2937]">
                <th class="text-left text-gray-600 text-xs py-2 pr-4">Indicator</th>
                <th class="text-right text-emerald-400 text-xs py-2 px-2">{{ lensData.comparison.base_flag }} {{ lensData.comparison.base_code }}</th>
                <th class="text-right text-blue-400 text-xs py-2 pl-2">{{ lensData.comparison.quote_flag }} {{ lensData.comparison.quote_code }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in lensData.comparison.rows" :key="row.label" class="border-b border-[#1f2937]/40">
                <td class="py-2 pr-4 text-gray-500 text-xs">{{ row.label }}</td>
                <td class="py-2 px-2 text-right font-mono text-xs text-emerald-300">{{ row.base }}</td>
                <td class="py-2 pl-2 text-right font-mono text-xs text-blue-300">{{ row.quote }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="lensData.comparison.rate_differential != null" class="mt-3 text-xs text-gray-500">
          Rate differential: <span class="text-white font-mono">{{ Math.abs(lensData.comparison.rate_differential).toFixed(2) }}%</span>
          in favour of {{ lensData.comparison.rate_differential > 0 ? lensData.comparison.base_code : lensData.comparison.quote_code }}
        </div>
      </div>

      <!-- SECTION 4: Macro Pressure (rule-based) -->
      <div v-if="lensData.macro_pressure?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.macroPressure') }}</div>
        <div class="space-y-2">
          <div v-for="tag in lensData.macro_pressure" :key="tag.text" class="flex items-start gap-2 text-sm">
            <span class="shrink-0 mt-0.5">{{ tag.signal === 'green' ? '🟢' : tag.signal === 'red' ? '🔴' : '🟡' }}</span>
            <span class="text-gray-400">{{ tag.text }}</span>
          </div>
        </div>
      </div>

      <!-- SECTION 5: Real Cost Estimate (only with size) -->
      <div v-if="lensData.cost" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.cost') }}</div>
        <div class="space-y-1.5 text-sm font-mono">
          <div class="flex justify-between">
            <span class="text-gray-500">Entry rate</span>
            <span class="text-white">{{ lensData.cost.entry_rate }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Spread ({{ lensData.cost.pair_type }})</span>
            <span class="text-yellow-400">+${{ lensData.cost.spread_usd }} ({{ lensData.cost.spread_pct }}%)</span>
          </div>
          <div class="border-t border-[#1f2937] pt-1.5 flex justify-between">
            <span class="text-gray-400 font-semibold">Effective rate</span>
            <span class="text-white font-bold">{{ lensData.cost.effective_rate }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Break-even</span>
            <span class="text-gray-400">{{ lensData.cost.break_even_pips }} pips</span>
          </div>
        </div>
        <div class="text-[10px] text-gray-700 mt-2">{{ $t('lens.cost.disclaimer') }}</div>
      </div>

      <!-- SECTION 6: What to Watch -->
      <div v-if="lensData.what_to_watch?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.watch') }}</div>
        <div class="space-y-1.5">
          <div v-for="w in lensData.what_to_watch" :key="w.event" class="flex items-center gap-2 text-sm">
            <span class="text-emerald-600">→</span>
            <span class="text-gray-300">{{ w.event }}</span>
            <span class="text-gray-600 text-xs">— {{ w.date }}</span>
            <span class="text-[10px] text-gray-700 font-mono">{{ w.country_code }}</span>
          </div>
        </div>
      </div>

      <!-- SECTION 7: Related Pairs -->
      <div v-if="lensData.related_pairs?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-4">
        <div class="text-xs font-bold text-white uppercase tracking-wider mb-3">{{ $t('lens.sections.relatedPairs') }}</div>
        <div class="flex flex-wrap gap-2">
          <NuxtLink v-for="p in lensData.related_pairs" :key="p"
            :to="`/lens/forex/${p.toLowerCase()}/`"
            class="px-3 py-1.5 rounded-lg text-xs font-mono font-bold text-emerald-400 bg-[#0d1520] border border-[#1f2937] hover:border-emerald-700 transition-colors">
            {{ p }}
          </NuxtLink>
        </div>
      </div>

      <!-- About Lens Forex -->
      <div class="bg-[#0a0f1a] border border-[#1a2435] rounded-xl p-4 mb-4 text-xs text-gray-500 leading-relaxed">
        <strong class="text-gray-400">How Lens works for forex:</strong> Lens analyses {{ pair }} by comparing the macroeconomic conditions of both countries — interest rate differentials, GDP growth divergence, inflation gap, and current account balance.
        The risk score reflects how exposed your trade is to central bank surprises, geopolitical shifts, or macro releases in either economy.
        Rates are updated every 15 minutes during weekday trading hours.
      </div>

      <!-- SECTION 8: Actions -->
      <div class="flex flex-wrap gap-3">
        <NuxtLink to="/lens/" class="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold bg-[#111827] border border-[#1f2937] text-gray-400 hover:text-white transition-all">
          ← Analyze Another
        </NuxtLink>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const { t } = useI18n()
const route = useRoute()
const pair  = (route.params.pair as string).toUpperCase()

const direction = computed(() => String(route.query.direction || 'long'))
const sizeUsd   = computed(() => route.query.size ? Number(route.query.size) : null)

const { get } = useApi()

const queryStr = computed(() => {
  const p: Record<string, string> = { direction: direction.value }
  if (sizeUsd.value) p.size = String(sizeUsd.value)
  return new URLSearchParams(p).toString()
})

const { data: lensData, pending, error } = await useAsyncData(
  `lens-forex-${pair}-${direction.value}-${sizeUsd.value || 'none'}`,
  () => get<any>(`/api/lens/forex/${pair}?${queryStr.value}`).catch(() => null),
)

function riskClass(level: string | undefined): string {
  if (level === 'HIGH VOLATILITY') return 'bg-red-950 text-red-300 border-red-800'
  if (level === 'MODERATE')        return 'bg-amber-950 text-amber-300 border-amber-800'
  return 'bg-emerald-950 text-emerald-300 border-emerald-800'
}
function riskIcon(level: string | undefined): string {
  if (level === 'HIGH VOLATILITY') return '🔴'
  if (level === 'MODERATE') return '🟡'
  return '🟢'
}
function fmtTs(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC'
}

useSeoMeta({
  title: `${pair} Pre-Trade Analysis — MetricsHour Lens`,
  description: `Lens forex analysis for ${pair}: macro drivers, rate differential, cost estimate. Risk: ${lensData.value?.risk?.level || 'loading'}.`,
  robots: 'index, follow',
})
useHead({ link: [{ rel: 'canonical', href: `https://metricshour.com/lens/forex/${pair.toLowerCase()}/` }] })
</script>
