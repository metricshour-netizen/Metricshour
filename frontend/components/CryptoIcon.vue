<template>
  <div
    class="rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center overflow-hidden shrink-0"
    :style="{ width: `${size}px`, height: `${size}px` }"
  >
    <img
      v-if="showImg"
      :src="`https://assets.coingecko.com/coins/images/${coingeckoId}/small/${symbol.toLowerCase()}.png`"
      :alt="symbol"
      :width="size - 8"
      :height="size - 8"
      class="object-contain"
      @error="onError"
      loading="lazy"
    />
    <span v-else class="font-bold text-amber-400 select-none" :style="{ fontSize: `${Math.round(size * 0.4)}px` }">
      {{ EMOJI[symbol] || '🪙' }}
    </span>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  symbol: string
  size?: number
}>()

const size = computed(() => props.size ?? 40)
const showImg = ref(true)

const EMOJI: Record<string, string> = {
  BTC: '₿', ETH: 'Ξ', BNB: '🟡', SOL: '◎', XRP: '✕',
  ADA: '₳', DOGE: '🐕', DOT: '●', AVAX: '🔺', LINK: '🔗',
  LTC: 'Ł', BCH: '₿', MATIC: '⬡', UNI: '🦄', ATOM: '⚛',
}

// CoinGecko image IDs for major coins
const COINGECKO_IDS: Record<string, string> = {
  BTC: '1', ETH: '279', BNB: '825', SOL: '4128', XRP: '44',
  ADA: '2010', DOGE: '5', DOT: '12171', AVAX: '12559', LINK: '877',
  LTC: '2', BCH: '780', MATIC: '4713', UNI: '12504', ATOM: '3794',
}

const coingeckoId = computed(() => COINGECKO_IDS[props.symbol] ?? '')

function onError() {
  showImg.value = false
}
</script>
