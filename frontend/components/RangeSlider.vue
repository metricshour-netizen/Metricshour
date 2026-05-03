<template>
  <div class="range-slider relative h-5 flex items-center">
    <!-- Track background -->
    <div class="absolute inset-x-0 h-1 bg-[#1f2937] rounded-full">
      <!-- Active range fill -->
      <div
        class="absolute h-full rounded-full opacity-60"
        :class="trackClass"
        :style="{ left: minPct + '%', width: (maxPct - minPct) + '%' }"
      ></div>
    </div>

    <!-- Min thumb -->
    <input
      type="range"
      :min="0" :max="100" :step="step"
      :value="minVal"
      class="range-thumb absolute inset-x-0 w-full appearance-none bg-transparent pointer-events-none"
      @input="onMinInput"
    />

    <!-- Max thumb -->
    <input
      type="range"
      :min="0" :max="100" :step="step"
      :value="maxVal"
      class="range-thumb absolute inset-x-0 w-full appearance-none bg-transparent pointer-events-none"
      @input="onMaxInput"
    />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  min?: number | null
  max?: number | null
  step?: number
  color?: string
}>()

const emit = defineEmits<{
  'update:min': [value: number | null]
  'update:max': [value: number | null]
}>()

const minVal = computed(() => props.min ?? 0)
const maxVal = computed(() => props.max ?? 100)

const minPct = computed(() => minVal.value)
const maxPct = computed(() => maxVal.value)

const colorMap: Record<string, string> = {
  red: 'bg-red-500',
  blue: 'bg-blue-500',
  purple: 'bg-purple-500',
  pink: 'bg-pink-500',
  orange: 'bg-orange-500',
  yellow: 'bg-yellow-500',
  emerald: 'bg-emerald-500',
}
const trackClass = computed(() => colorMap[props.color ?? 'emerald'] ?? 'bg-emerald-500')

function onMinInput(e: Event) {
  const val = Number((e.target as HTMLInputElement).value)
  emit('update:min', val === 0 ? null : val)
}

function onMaxInput(e: Event) {
  const val = Number((e.target as HTMLInputElement).value)
  emit('update:max', val === 100 ? null : val)
}
</script>

<style scoped>
.range-thumb::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #374151;
  cursor: pointer;
  pointer-events: all;
  position: relative;
  z-index: 1;
}
.range-thumb::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid #374151;
  cursor: pointer;
  pointer-events: all;
}
</style>
