<template>
  <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
    <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-4">{{ title }}</h2>
    <div class="space-y-2.5">
      <div
        v-for="r in rows"
        :key="r.label"
        class="flex items-center justify-between gap-4 text-sm"
      >
        <span class="text-gray-500 truncate">{{ r.label }}</span>
        <div class="text-right shrink-0">
          <span
            class="font-medium tabular-nums block"
            :class="r.raw == null ? 'text-gray-700' : 'text-white'"
          >{{ r.value }}</span>
          <span v-if="r.year" class="text-[10px] text-gray-600 leading-none">{{ r.year }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  rows: { label: string; value: string; raw?: number | null; year?: number | null }[]
}>()
</script>
