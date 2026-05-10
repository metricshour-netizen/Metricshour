<template>
  <div
    class="rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center overflow-hidden shrink-0"
    :style="{ width: `${size}px`, height: `${size}px` }"
    :class="sizeClass"
  >
    <img
      v-if="showImg"
      :src="logoUrl"
      :alt="symbol"
      :width="size"
      :height="size"
      class="object-contain p-1"
      @error="onError"
    />
    <span v-else class="font-bold text-gray-400 select-none" :style="{ fontSize: `${Math.round(size * 0.36)}px` }">
      {{ initials }}
    </span>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  symbol: string
  size?: number
}>()

const size = computed(() => props.size ?? 48)
const sizeClass = computed(() => size.value <= 32 ? 'text-xs' : size.value <= 48 ? 'text-sm' : 'text-base')

// Parqet logo service — works for most exchange-listed tickers without API key
const logoUrl = computed(() => `https://assets.parqet.com/logos/symbol/${props.symbol}?format=jpg`)

const showImg = ref(true)

function onError() {
  showImg.value = false
}

const initials = computed(() => {
  const s = props.symbol.replace(/[^A-Z]/g, '')
  return s.slice(0, 2) || props.symbol.slice(0, 2).toUpperCase()
})
</script>
