<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-xl sm:text-2xl font-bold text-white">{{ $t('calendar.title') }}</h1>
      <p class="text-gray-500 text-sm mt-1">{{ $t('calendar.subtitle') }}</p>
    </div>

    <!-- Filter bar -->
    <div class="flex flex-wrap gap-2 mb-6">
      <!-- Date range tabs -->
      <div class="flex gap-1.5 flex-wrap">
        <button v-for="r in DATE_RANGES" :key="r.key"
          @click="dateRange = r.key"
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
          :class="dateRange === r.key ? 'bg-emerald-600 text-white' : 'bg-[#111827] border border-[#1f2937] text-gray-400 hover:text-white'">
          {{ r.label }}
        </button>
      </div>

      <!-- Impact toggle -->
      <button @click="highImpactOnly = !highImpactOnly"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border"
        :class="highImpactOnly ? 'bg-red-950 border-red-800 text-red-300' : 'bg-[#111827] border-[#1f2937] text-gray-400 hover:text-white'">
        🔴 {{ $t('calendar.filters.highImpact') }}
      </button>

      <!-- Region filter -->
      <select v-model="regionFilter"
        class="bg-[#111827] border border-[#1f2937] rounded-lg text-xs text-gray-400 px-2 py-1.5 focus:outline-none focus:border-emerald-700">
        <option value="">{{ $t('calendar.filters.allRegions') }}</option>
        <option value="US">🇺🇸 United States</option>
        <option value="EU">🇪🇺 Eurozone</option>
        <option value="GB">🇬🇧 United Kingdom</option>
        <option value="JP">🇯🇵 Japan</option>
        <option value="CA">🇨🇦 Canada</option>
        <option value="AU">🇦🇺 Australia</option>
        <option value="CN">🇨🇳 China</option>
      </select>

      <!-- Event type filter -->
      <select v-model="typeFilter"
        class="bg-[#111827] border border-[#1f2937] rounded-lg text-xs text-gray-400 px-2 py-1.5 focus:outline-none focus:border-emerald-700">
        <option value="">{{ $t('calendar.filters.allTypes') }}</option>
        <option value="rate_decision">Rate Decision</option>
        <option value="cpi">CPI / Inflation</option>
        <option value="gdp">GDP</option>
        <option value="nfp">Employment / NFP</option>
        <option value="pmi">PMI</option>
        <option value="trade">Trade Balance</option>
        <option value="retail">Retail Sales</option>
        <option value="pce">PCE</option>
        <option value="opec">OPEC Meeting</option>
        <option value="g7">G7 / G20</option>
      </select>
    </div>

    <!-- Loading -->
    <div v-if="pending" class="space-y-6">
      <div v-for="i in 3" :key="i" class="mb-8">
        <div class="h-4 w-40 bg-[#111827] rounded animate-pulse mb-4"/>
        <div class="space-y-2">
          <div v-for="j in 3" :key="j" class="h-16 bg-[#111827] border border-[#1f2937] rounded-xl animate-pulse"/>
        </div>
      </div>
    </div>

    <!-- Events grouped by day -->
    <template v-else-if="calendarData?.days?.length">
      <div v-for="day in calendarData.days" :key="day.date" class="mb-8">
        <!-- Day header -->
        <div class="flex items-center gap-3 mb-3">
          <h2 class="text-sm font-extrabold uppercase tracking-widest"
              :class="day.is_today ? 'text-emerald-400' : 'text-white'">
            {{ fmtDayLabel(day.date) }}
            <span v-if="day.is_today" class="text-[10px] text-emerald-500 bg-emerald-950 border border-emerald-800 px-1.5 py-0.5 rounded-full ml-1">TODAY</span>
          </h2>
          <span class="text-[10px] text-gray-600 bg-[#1f2937] px-2 py-0.5 rounded-full">{{ day.events.length }}</span>
          <div class="flex-1 h-px bg-[#1f2937]"/>
        </div>

        <!-- Desktop table -->
        <div class="hidden sm:block bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-[#111827] text-[10px] text-gray-500 uppercase tracking-widest">
              <tr>
                <th class="px-4 py-2.5 text-left">Country</th>
                <th class="px-4 py-2.5 text-left">Event</th>
                <th class="px-4 py-2.5 text-right">Time (UTC)</th>
                <th class="px-4 py-2.5 text-center">Impact</th>
                <th v-if="hasPrevFcst" class="px-4 py-2.5 text-right">Previous</th>
                <th v-if="hasPrevFcst" class="px-4 py-2.5 text-right">Forecast</th>
                <th class="px-4 py-2.5 text-right">Actual</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="evt in day.events" :key="evt.id"
                  class="border-t border-[#1f2937] hover:bg-[#111827]/60 transition-colors"
                  :class="day.is_today && !evt.actual_value ? 'bg-emerald-950/10' : ''">
                <td class="px-4 py-3 text-gray-300 font-mono text-xs">
                  <span class="mr-1">{{ countryFlag(evt.country_code) }}</span>
                  {{ evt.country_code }}
                </td>
                <td class="px-4 py-3 text-white text-sm font-medium">{{ evt.event_name }}</td>
                <td class="px-4 py-3 text-right text-gray-500 font-mono text-xs">{{ fmtTime(evt.event_date) }}</td>
                <td class="px-4 py-3 text-center">
                  <span class="text-xs px-2 py-0.5 rounded-full font-semibold"
                    :class="impactClass(evt.impact)">
                    {{ impactDot(evt.impact) }} {{ $t(`calendar.impact.${evt.impact}`) }}
                  </span>
                </td>
                <td v-if="hasPrevFcst" class="px-4 py-3 text-right text-gray-500 font-mono text-xs">{{ evt.previous_value ?? '' }}</td>
                <td v-if="hasPrevFcst" class="px-4 py-3 text-right text-gray-400 font-mono text-xs">{{ evt.forecast_value ?? '' }}</td>
                <td class="px-4 py-3 text-right font-mono text-xs font-bold"
                  :class="evt.actual_value ? 'text-emerald-400' : 'text-gray-700'">
                  {{ evt.actual_value || '—' }}
                </td>
                <td class="px-4 py-3 text-right">
                  <button @click="openAlert(evt)"
                    class="text-[10px] text-gray-600 hover:text-emerald-400 transition-colors px-2 py-1 rounded border border-transparent hover:border-emerald-900">
                    🔔
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile cards -->
        <div class="sm:hidden space-y-2">
          <div v-for="evt in day.events" :key="evt.id"
               class="bg-[#0d1520] border border-[#1f2937] rounded-xl px-4 py-3"
               :class="day.is_today && !evt.actual_value ? 'border-emerald-900/50' : ''">
            <div class="flex items-start justify-between gap-2 mb-1.5">
              <div>
                <div class="flex items-center gap-1.5 mb-0.5">
                  <span class="text-xs font-mono text-gray-400">{{ countryFlag(evt.country_code) }} {{ evt.country_code }}</span>
                  <span class="text-[10px] font-mono text-gray-600">{{ fmtTime(evt.event_date) }}</span>
                </div>
                <div class="text-sm font-semibold text-white leading-tight">{{ evt.event_name }}</div>
              </div>
              <span class="text-xs px-2 py-0.5 rounded-full font-semibold shrink-0"
                :class="impactClass(evt.impact)">
                {{ impactDot(evt.impact) }} {{ $t(`calendar.impact.${evt.impact}`) }}
              </span>
            </div>
            <div class="flex gap-4 text-xs font-mono text-gray-600 mt-2">
              <span v-if="evt.previous_value">Prev: <span class="text-gray-400">{{ evt.previous_value }}</span></span>
              <span v-if="evt.forecast_value">Fcst: <span class="text-gray-400">{{ evt.forecast_value }}</span></span>
              <span v-if="evt.actual_value">Act: <span class="text-emerald-400 font-bold">{{ evt.actual_value }}</span></span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Empty state -->
    <div v-else-if="!pending" class="text-center py-12 text-gray-600">
      <div class="text-4xl mb-3">📅</div>
      <p class="text-sm">{{ $t('calendar.noEvents') }}</p>
    </div>

  <EmailAlertModal
    v-model="showEmailAlert"
    :asset-symbol="alertAsset.symbol"
    :asset-name="alertAsset.name"
    asset-type="macro_event"
  />
  </main>
</template>

<script setup lang="ts">
const { t } = useI18n()
const { get } = useApi()
const route = useRoute()

const DATE_RANGES = [
  { key: 'week',  label: t('calendar.filters.thisWeek') },
  { key: 'next',  label: 'Next Week' },
  { key: 'month', label: t('calendar.filters.thisMonth') },
]

const dateRange    = ref<'week' | 'next' | 'month'>('week')
const highImpactOnly = ref(false)
const regionFilter   = ref('')
const typeFilter     = ref('')

function getDateRange() {
  const now = new Date()
  if (dateRange.value === 'week') {
    // Rolling 7 days from today
    const start = new Date(now)
    start.setHours(0, 0, 0, 0)
    const end = new Date(start)
    end.setDate(end.getDate() + 7)
    return { start: start.toISOString(), end: end.toISOString() }
  }
  if (dateRange.value === 'next') {
    // Days 7–14 from today
    const start = new Date(now)
    start.setDate(start.getDate() + 7)
    start.setHours(0, 0, 0, 0)
    const end = new Date(start)
    end.setDate(end.getDate() + 7)
    return { start: start.toISOString(), end: end.toISOString() }
  }
  // month: rolling 30 days from today
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  const end = new Date(start)
  end.setDate(end.getDate() + 30)
  return { start: start.toISOString(), end: end.toISOString() }
}

const queryParams = computed(() => {
  const { start, end } = getDateRange()
  const params: Record<string, string> = { start, end, limit: '200' }
  if (highImpactOnly.value) params.impact = 'high'
  if (regionFilter.value) params.country = regionFilter.value
  if (typeFilter.value) params.event_type = typeFilter.value
  return params
})

const { data: calendarData, pending, refresh } = useAsyncData(
  'calendar-events',
  () => {
    const p = queryParams.value
    const qs = new URLSearchParams(p).toString()
    return get<any>(`/api/calendar?${qs}`).catch(() => null)
  },
  { watch: [queryParams] },
)

// Only show Prev/Fcst columns when at least one event has data
const hasPrevFcst = computed(() =>
  calendarData.value?.days?.some((d: any) =>
    d.events?.some((e: any) => e.previous_value != null || e.forecast_value != null)
  ) ?? false
)

function fmtDayLabel(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00Z')
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' })
}

function fmtTime(isoStr: string | null): string {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC'
}

const FLAG_MAP: Record<string, string> = {
  US: '🇺🇸', EU: '🇪🇺', GB: '🇬🇧', JP: '🇯🇵', CA: '🇨🇦', AU: '🇦🇺', CN: '🇨🇳',
  DE: '🇩🇪', FR: '🇫🇷', IT: '🇮🇹', ES: '🇪🇸', CH: '🇨🇭', SE: '🇸🇪', NZ: '🇳🇿',
  KR: '🇰🇷', IN: '🇮🇳', BR: '🇧🇷', MX: '🇲🇽', AE: '🇦🇪',
}
function countryFlag(code: string): string {
  return FLAG_MAP[code] || '🌐'
}

function impactClass(impact: string): string {
  if (impact === 'high')   return 'bg-red-950 text-red-300 border border-red-800'
  if (impact === 'medium') return 'bg-amber-950 text-amber-300 border border-amber-800'
  return 'bg-gray-900 text-gray-400 border border-gray-800'
}

function impactDot(impact: string): string {
  if (impact === 'high')   return '🔴'
  if (impact === 'medium') return '🟡'
  return '🟢'
}

// Alert integration
const showEmailAlert = ref(false)
const alertAsset = ref({ symbol: '', name: '' })

function openAlert(evt: any) {
  alertAsset.value = {
    symbol: `${evt.country_code}:${evt.event_type}`,
    name: `${evt.event_name} (${evt.country_code})`,
  }
  showEmailAlert.value = true
}

useSeoMeta({
  title: `${t('calendar.title')} — MetricsHour`,
  description: `${t('calendar.subtitle')} Fed, ECB, BOE rate decisions, CPI, GDP, NFP and more.`,
  robots: 'index, follow',
})
useHead({ link: [{ rel: 'canonical', href: 'https://metricshour.com/calendar/' }] })
</script>
