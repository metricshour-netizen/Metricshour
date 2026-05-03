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
  /** 'stock' or 'country' — determines OG image URL path */
  type: 'stock' | 'country'
  /** Ticker symbol (stocks) or ISO2 country code (countries) — lowercase */
  slug: string
  /** Display name for share title and filename */
  name: string
}>()

const { sharePage, downloadOgImage, downloading } = useShareCard()
// Use API base (has CORS headers for metricshour.com) — not R2 CDN (no CORS headers)
const { public: { apiBase } } = useRuntimeConfig()

const canShare = ref(false)
onMounted(() => {
  canShare.value = typeof navigator.share === 'function'
})

const ogImageUrl = computed(() => {
  if (props.type === 'stock') return `${apiBase}/og/stocks/${props.slug.toLowerCase()}.png`
  return `${apiBase}/og/countries/${props.slug.toLowerCase()}.png`
})

const shareTitle = computed(() =>
  props.type === 'stock'
    ? `${props.name} — Revenue by Country | MetricsHour`
    : `${props.name} Economy — GDP & Macro Data | MetricsHour`,
)

function onShare() {
  sharePage(shareTitle.value)
}

function onDownload() {
  const filename = `metricshour-${props.name.replace(/\s+/g, '-').toLowerCase()}`
  downloadOgImage(ogImageUrl.value, filename)
}
</script>
