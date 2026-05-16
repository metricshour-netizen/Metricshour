<template>
  <div class="flex items-center justify-center gap-1 mt-8 flex-wrap">
    <NuxtLink
      v-if="currentPage > 1"
      :to="pageUrl(currentPage - 1)"
      class="px-3 py-1.5 text-sm rounded border border-[#1f2937] text-gray-400 hover:border-gray-500 transition-colors"
    >←</NuxtLink>

    <template v-for="p in pages" :key="String(p)">
      <span v-if="p === '...'" class="px-2 text-gray-600 text-sm select-none">…</span>
      <NuxtLink
        v-else
        :to="pageUrl(p as number)"
        class="px-3 py-1.5 text-sm rounded border transition-colors"
        :class="p === currentPage
          ? 'bg-emerald-500 border-emerald-500 text-black font-bold'
          : 'border-[#1f2937] text-gray-400 hover:border-gray-500'"
      >{{ p }}</NuxtLink>
    </template>

    <NuxtLink
      v-if="currentPage < totalPages"
      :to="pageUrl(currentPage + 1)"
      class="px-3 py-1.5 text-sm rounded border border-[#1f2937] text-gray-400 hover:border-gray-500 transition-colors"
    >→</NuxtLink>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  currentPage: number
  totalPages: number
  baseUrl: string
}>()

function pageUrl(p: number): string {
  return p === 1 ? props.baseUrl : `${props.baseUrl}?page=${p}`
}

const pages = computed((): (number | string)[] => {
  const { totalPages: total, currentPage: cur } = props
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const result: (number | string)[] = [1]
  if (cur > 3) result.push('...')
  for (let p = Math.max(2, cur - 1); p <= Math.min(total - 1, cur + 1); p++) result.push(p)
  if (cur < total - 2) result.push('...')
  result.push(total)
  return result
})
</script>
