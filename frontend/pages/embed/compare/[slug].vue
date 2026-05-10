<template>
  <div class="embed-root">
    <div v-if="pending" class="loading"><div class="spinner"/></div>
    <div v-else-if="!countryA && !countryB" class="error">Countries not found.</div>
    <template v-else>
      <div class="header">
        <div class="country-pair">
          <div class="country-item">
            <span class="flag">{{ countryA?.flag_emoji || '🏳' }}</span>
            <div>
              <div class="country-name">{{ countryA?.name || codeA.toUpperCase() }}</div>
              <div class="country-code">{{ codeA.toUpperCase() }}</div>
            </div>
          </div>
          <div class="vs">vs</div>
          <div class="country-item">
            <span class="flag">{{ countryB?.flag_emoji || '🏳' }}</span>
            <div>
              <div class="country-name b">{{ countryB?.name || codeB.toUpperCase() }}</div>
              <div class="country-code b">{{ codeB.toUpperCase() }}</div>
            </div>
          </div>
        </div>
        <div class="subtitle">Economic Comparison · World Bank</div>
      </div>

      <div class="stats-grid">
        <div v-for="row in comparisonRows" :key="row.label" class="stat-row">
          <div class="stat-label">{{ row.label }}</div>
          <div class="stat-values">
            <span class="val-a" :class="{ winner: row.winnerA }">{{ row.fmtA }}</span>
            <span class="separator">·</span>
            <span class="val-b" :class="{ winner: row.winnerB }">{{ row.fmtB }}</span>
          </div>
        </div>
      </div>
    </template>

    <a class="watermark" href="https://metricshour.com" target="_blank" rel="noopener">MetricsHour</a>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false })
useHead({ meta: [{ name: 'robots', content: 'noindex' }] })

const route = useRoute()
const slug = (route.params.slug as string).toLowerCase()
const parts = slug.split('-vs-')
const rawA = (parts[0] || '').toUpperCase()
const rawB = (parts[1] || '').toUpperCase()
const [canonA, canonB] = [rawA, rawB].sort()
const codeA = canonA.toLowerCase()
const codeB = canonB.toLowerCase()

const { get } = useApi()

const [{ data: countryA, pending: pendingA }, { data: countryB, pending: pendingB }] = await Promise.all([
  useAsyncData(`embed-compare-a-${codeA}`, () => get<any>(`/api/countries/${codeA}`).catch(() => null)),
  useAsyncData(`embed-compare-b-${codeB}`, () => get<any>(`/api/countries/${codeB}`).catch(() => null)),
])

const pending = computed(() => pendingA.value || pendingB.value)

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return '—'
  if (v >= 1e12) return '$' + (v / 1e12).toFixed(1) + 'T'
  if (v >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B'
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M'
  return '$' + v.toLocaleString()
}
function fmtPct(v: number | null | undefined, dec = 1): string {
  return v != null ? v.toFixed(dec) + '%' : '—'
}

const comparisonRows = computed(() => {
  const indA = countryA.value?.indicators || {}
  const indB = countryB.value?.indicators || {}
  const rows = [
    { label: 'GDP',          fmtA: fmtUsd(indA.gdp_usd),            fmtB: fmtUsd(indB.gdp_usd),            higherBetter: true,  valA: indA.gdp_usd,          valB: indB.gdp_usd },
    { label: 'GDP Growth',   fmtA: fmtPct(indA.gdp_growth_pct),     fmtB: fmtPct(indB.gdp_growth_pct),     higherBetter: true,  valA: indA.gdp_growth_pct,   valB: indB.gdp_growth_pct },
    { label: 'Inflation',    fmtA: fmtPct(indA.inflation_pct),      fmtB: fmtPct(indB.inflation_pct),      higherBetter: false, valA: indA.inflation_pct,    valB: indB.inflation_pct },
    { label: 'Interest Rate',fmtA: fmtPct(indA.interest_rate_pct),  fmtB: fmtPct(indB.interest_rate_pct),  higherBetter: null,  valA: null,                  valB: null },
    { label: 'Unemployment', fmtA: fmtPct(indA.unemployment_pct),   fmtB: fmtPct(indB.unemployment_pct),   higherBetter: false, valA: indA.unemployment_pct, valB: indB.unemployment_pct },
    { label: 'Debt/GDP',     fmtA: fmtPct(indA.govt_debt_gdp_pct),  fmtB: fmtPct(indB.govt_debt_gdp_pct),  higherBetter: false, valA: indA.govt_debt_gdp_pct,valB: indB.govt_debt_gdp_pct },
  ]
  return rows.map(r => ({
    ...r,
    winnerA: r.higherBetter != null && r.valA != null && r.valB != null
      ? (r.higherBetter ? r.valA > r.valB : r.valA < r.valB)
      : false,
    winnerB: r.higherBetter != null && r.valA != null && r.valB != null
      ? (r.higherBetter ? r.valB > r.valA : r.valB < r.valA)
      : false,
  }))
})
</script>

<style scoped>
.embed-root { background: #0a0e1a; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 16px; min-height: 100vh; position: relative; font-size: 13px; }
.loading { display: flex; align-items: center; justify-content: center; height: 200px; }
.spinner { width: 24px; height: 24px; border: 2px solid #10b981; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error { color: #6b7280; text-align: center; padding: 40px; }

.header { margin-bottom: 16px; }
.country-pair { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.country-item { display: flex; align-items: center; gap: 8px; flex: 1; }
.flag { font-size: 28px; }
.country-name { font-size: 14px; font-weight: 700; color: #fff; }
.country-name.b { color: #93c5fd; }
.country-code { font-size: 10px; font-family: monospace; color: #10b981; margin-top: 1px; }
.country-code.b { color: #60a5fa; }
.vs { font-size: 14px; color: #4b5563; font-weight: 600; padding: 0 4px; }
.subtitle { font-size: 10px; color: #4b5563; text-transform: uppercase; letter-spacing: 0.05em; }

.stats-grid { display: flex; flex-direction: column; gap: 2px; margin-bottom: 28px; }
.stat-row { display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #1f2937; }
.stat-row:last-child { border-bottom: none; }
.stat-label { font-size: 11px; color: #6b7280; flex: 1; }
.stat-values { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }
.val-a { color: #9ca3af; min-width: 56px; text-align: right; }
.val-a.winner { color: #10b981; }
.val-b { color: #9ca3af; min-width: 56px; text-align: left; }
.val-b.winner { color: #60a5fa; }
.separator { color: #374151; font-size: 10px; }

.watermark { position: fixed; bottom: 8px; right: 10px; font-size: 10px; color: #374151; text-decoration: none; font-weight: 600; letter-spacing: 0.05em; transition: color 0.2s; }
.watermark:hover { color: #10b981; }
</style>
