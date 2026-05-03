<template>
  <!-- Capture target — hidden off-screen, rendered for html2canvas -->
  <div
    ref="cardEl"
    class="share-card-root"
    style="position:fixed;left:-9999px;top:0;width:600px;background:#0a0d14;padding:28px 28px 24px;font-family:'JetBrains Mono',monospace,sans-serif;box-sizing:border-box;"
    aria-hidden="true"
  >
    <!-- Header row -->
    <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px;">
      <div>
        <div v-if="type === 'stock'" style="display:flex;align-items:baseline;gap:10px;">
          <span style="color:#fff;font-size:22px;font-weight:700;letter-spacing:-0.5px;">{{ symbol }}</span>
          <span style="color:#6b7280;font-size:13px;font-weight:400;">{{ name }}</span>
        </div>
        <div v-else style="display:flex;align-items:center;gap:10px;">
          <span style="font-size:28px;line-height:1;">{{ flag }}</span>
          <span style="color:#fff;font-size:20px;font-weight:700;">{{ name }}</span>
        </div>
        <!-- Price row (stocks only) -->
        <div v-if="type === 'stock' && price" style="display:flex;align-items:baseline;gap:8px;margin-top:6px;">
          <span style="color:#fff;font-size:28px;font-weight:700;letter-spacing:-1px;">{{ fmtPrice(price) }}</span>
          <span
            style="font-size:14px;font-weight:600;padding:2px 8px;border-radius:4px;"
            :style="changeStyle"
          >{{ changePct > 0 ? '+' : '' }}{{ changePct?.toFixed(2) }}%</span>
        </div>
        <!-- GDP row (countries) -->
        <div v-if="type === 'country' && gdp" style="margin-top:6px;">
          <span style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1px;">{{ $t('shareCard.gdp') }}</span>
          <span style="color:#fff;font-size:24px;font-weight:700;margin-left:8px;">{{ gdp }}</span>
          <span v-if="gdpGrowth !== null" style="font-size:13px;font-weight:600;padding:2px 8px;border-radius:4px;margin-left:8px;" :style="gdpGrowthStyle">{{ gdpGrowth > 0 ? '+' : '' }}{{ gdpGrowth?.toFixed(1) }}%</span>
        </div>
      </div>
      <!-- GEO RISK badge (stocks) -->
      <div v-if="type === 'stock' && geoRisk" style="text-align:right;">
        <div style="background:#1f2937;border:1px solid #374151;border-radius:6px;padding:6px 10px;display:inline-block;">
          <div style="color:#9ca3af;font-size:9px;letter-spacing:1px;text-transform:uppercase;margin-bottom:2px;">{{ $t('shareCard.geoRisk') }}</div>
          <div style="color:#f59e0b;font-size:16px;font-weight:700;">{{ geoRisk }}</div>
        </div>
      </div>
    </div>

    <!-- Divider -->
    <div style="height:1px;background:linear-gradient(to right,#10b981,#1f2937);margin-bottom:16px;opacity:0.5;"></div>

    <!-- Revenue / Trade partners section -->
    <div v-if="type === 'stock' && topRevenue?.length" style="margin-bottom:20px;">
      <div style="color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">{{ $t('shareCard.topRevenue') }}</div>
      <div v-for="row in topRevenue" :key="row.code" style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
        <span style="font-size:18px;width:24px;text-align:center;">{{ row.flag }}</span>
        <span style="color:#d1d5db;font-size:13px;flex:1;">{{ row.name }}</span>
        <div style="background:#1f2937;border-radius:3px;height:6px;width:120px;overflow:hidden;flex-shrink:0;">
          <div :style="`width:${Math.min(row.pct, 100)}%;height:100%;background:${barColor(row.pct)};`"></div>
        </div>
        <span style="color:#fff;font-size:13px;font-weight:600;width:38px;text-align:right;">{{ row.pct }}%</span>
      </div>
    </div>

    <div v-if="type === 'country' && topPartners?.length" style="margin-bottom:20px;">
      <div style="color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">{{ $t('shareCard.topPartners') }}</div>
      <div v-for="row in topPartners" :key="row.code" style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
        <span style="font-size:18px;width:24px;text-align:center;">{{ row.flag }}</span>
        <span style="color:#d1d5db;font-size:13px;flex:1;">{{ row.name }}</span>
        <span style="color:#fff;font-size:13px;font-weight:600;">{{ row.value }}</span>
      </div>
    </div>

    <!-- Footer -->
    <div style="display:flex;align-items:center;justify-content:space-between;border-top:1px solid #1f2937;padding-top:12px;margin-top:4px;">
      <span style="color:#374151;font-size:10px;">SEC EDGAR · World Bank · UN Comtrade</span>
      <span style="color:#10b981;font-size:11px;font-weight:700;letter-spacing:0.5px;">{{ $t('shareCard.branding') }}</span>
    </div>
  </div>

  <!-- Trigger button (always visible) -->
  <button
    :disabled="generating"
    class="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-[#1f2937] text-gray-400 hover:border-emerald-700 hover:text-emerald-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    @click="capture"
  >
    <span>{{ generating ? $t('shareCard.generating') : $t('shareCard.share') }}</span>
    <span aria-hidden="true">↗</span>
  </button>
</template>

<script setup lang="ts">
const props = defineProps<{
  type: 'stock' | 'country'
  symbol?: string
  name: string
  flag?: string
  price?: number | null
  changePct?: number | null
  geoRisk?: string | null
  gdp?: string | null
  gdpGrowth?: number | null
  topRevenue?: Array<{ code: string; name: string; flag: string; pct: number }>
  topPartners?: Array<{ code: string; name: string; flag: string; value: string }>
}>()

const { captureElement, generating } = useShareCard()
const cardEl = ref<HTMLElement | null>(null)

const changeStyle = computed(() => {
  const pct = props.changePct ?? 0
  if (pct > 0) return 'background:#064e3b;color:#34d399;'
  if (pct < 0) return 'background:#450a0a;color:#f87171;'
  return 'background:#1f2937;color:#9ca3af;'
})

const gdpGrowthStyle = computed(() => {
  const g = props.gdpGrowth ?? 0
  if (g > 0) return 'background:#064e3b;color:#34d399;'
  if (g < 0) return 'background:#450a0a;color:#f87171;'
  return 'background:#1f2937;color:#9ca3af;'
})

function fmtPrice(v: number): string {
  if (v >= 1000) return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  return `$${v.toFixed(2)}`
}

function barColor(pct: number): string {
  if (pct >= 30) return '#ef4444'
  if (pct >= 15) return '#f59e0b'
  if (pct >= 5) return '#fcd34d'
  return '#10b981'
}

async function capture() {
  if (!cardEl.value) return
  const filename = `metricshour-${props.symbol || props.name?.replace(/\s+/g, '-').toLowerCase()}`
  await captureElement(cardEl.value, filename)
}
</script>
