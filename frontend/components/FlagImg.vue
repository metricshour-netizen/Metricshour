<template>
  <span
    v-if="!showImg || !code"
    :class="emojiClass"
    aria-hidden="true"
  >{{ emoji || fallbackEmoji }}</span>
  <img
    v-else
    :src="`https://flagcdn.com/w${imgSize}/${code.toLowerCase()}.png`"
    :width="imgSize"
    :height="Math.round(imgSize * 0.75)"
    :alt="code"
    class="inline-block rounded-sm object-cover"
    :style="{ width: `${displaySize}px`, height: `${Math.round(displaySize * 0.75)}px` }"
    @error="showImg = false"
    loading="lazy"
  />
</template>

<script setup lang="ts">
const props = defineProps<{
  code?: string          // ISO 3166-1 alpha-2 e.g. 'US', 'GB'
  emoji?: string         // fallback emoji e.g. '🇺🇸'
  size?: number          // display size in px (default 20)
}>()

const displaySize = computed(() => props.size ?? 20)
// flagcdn.com supports w20, w40, w80, w160 — pick smallest that's >= displaySize
const imgSize = computed(() => {
  const s = displaySize.value
  if (s <= 20) return 20
  if (s <= 40) return 40
  if (s <= 80) return 80
  return 160
})

const showImg = ref(!!props.code)
const emojiClass = computed(() => {
  const s = displaySize.value
  if (s <= 14) return 'text-xs'
  if (s <= 20) return 'text-base'
  if (s <= 28) return 'text-xl'
  return 'text-2xl'
})

// Generic globe fallback when no code or emoji
const fallbackEmoji = '🌐'

watch(() => props.code, (val) => { showImg.value = !!val })
</script>
