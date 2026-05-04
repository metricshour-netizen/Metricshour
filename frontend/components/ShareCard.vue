<template>
  <!-- Mobile: share page URL -->
  <button
    v-if="canShare"
    class="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-[#1f2937] text-gray-400 hover:border-emerald-700 hover:text-emerald-400 transition-colors"
    @click="onShare"
  >↗ Share</button>

  <!-- Desktop: download pre-generated OG PNG from R2 -->
  <button
    v-else
    :disabled="downloading"
    class="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-[#1f2937] text-gray-400 hover:border-emerald-700 hover:text-emerald-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
    @click="onDownload"
  >{{ downloading ? 'Downloading…' : '↓ Share card' }}</button>
</template>

<script setup lang="ts">
const props = defineProps<{
  type: 'stock' | 'country' | 'crypto' | 'fx' | 'etf' | 'commodity' | 'trade'
  slug: string
  name: string
}>()

const { sharePage, downloadOgImage, downloading } = useShareCard()
const { public: { apiBase } } = useRuntimeConfig()

const canShare = ref(false)
onMounted(() => {
  canShare.value = typeof navigator.share === 'function'
})

const OG_PATH: Record<string, string> = {
  stock: 'stocks', country: 'countries', crypto: 'crypto',
  fx: 'fx', etf: 'etfs', commodity: 'commodities', trade: 'trade',
}

const ogImageUrl = computed(() =>
  `${apiBase}/og/${OG_PATH[props.type]}/${props.slug.toLowerCase()}.png`,
)

const TITLE_SUFFIX: Record<string, string> = {
  stock: '— Revenue by Country | MetricsHour',
  country: 'Economy — GDP & Macro Data | MetricsHour',
  crypto: '— Crypto Price & Data | MetricsHour',
  fx: '— Live Exchange Rate | MetricsHour',
  etf: '— ETF Price & Data | MetricsHour',
  commodity: '— Price & Market Data | MetricsHour',
  trade: '— Bilateral Trade Data | MetricsHour',
}

const shareTitle = computed(() =>
  `${props.name} ${TITLE_SUFFIX[props.type] ?? '| MetricsHour'}`,
)

function onShare() {
  sharePage(shareTitle.value)
}

function onDownload() {
  const filename = `metricshour-${props.name.replace(/\s+/g, '-').toLowerCase()}`
  downloadOgImage(ogImageUrl.value, filename)
}
</script>
