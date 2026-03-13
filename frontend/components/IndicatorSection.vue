<template>
  <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
    <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-4">{{ title }}</h2>
    <div class="space-y-2.5">
      <div
        v-for="r in rows"
        :key="r.label"
        class="flex items-center justify-between gap-4 text-sm group"
      >
        <span class="text-gray-500 truncate">{{ r.label }}</span>
        <div class="flex items-center gap-2 shrink-0">
          <button
            v-if="alertable && r.indicatorKey && r.raw != null"
            class="opacity-0 group-hover:opacity-100 transition-opacity text-gray-600 hover:text-emerald-400"
            :title="`Set alert for ${r.label}`"
            :aria-label="`Set macro alert for ${r.label} (current: ${r.raw})`"
            @click="$emit('set-alert', { indicatorKey: r.indicatorKey, label: r.label, currentValue: r.raw })"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
          </button>
          <div class="text-right">
            <span
              class="font-medium tabular-nums block"
              :class="r.raw == null ? 'text-gray-700' : 'text-white'"
            >{{ r.value }}</span>
            <span v-if="r.year" class="text-[10px] text-gray-600 leading-none">{{ r.year }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  rows: { label: string; value: string; raw?: number | null; year?: number | null; indicatorKey?: string }[]
  alertable?: boolean
}>()

defineEmits<{
  'set-alert': [payload: { indicatorKey: string; label: string; currentValue: number }]
}>()
</script>
