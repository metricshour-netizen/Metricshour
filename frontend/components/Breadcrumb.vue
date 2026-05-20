<template>
  <nav aria-label="Breadcrumb" class="mb-4">
    <ol class="flex items-center flex-wrap gap-1 text-xs text-gray-600">
      <li v-for="(crumb, i) in crumbs" :key="crumb.href || crumb.label" class="flex items-center gap-1">
        <span v-if="i > 0" class="text-gray-700" aria-hidden="true">›</span>
        <NuxtLink
          v-if="crumb.href"
          :to="crumb.href"
          class="hover:text-gray-400 transition-colors"
        >{{ crumb.label }}</NuxtLink>
        <span v-else class="text-gray-400 font-medium">{{ crumb.label }}</span>
      </li>
    </ol>
  </nav>
</template>

<script setup lang="ts">
defineProps<{
  crumbs: Array<{ label: string; href?: string }>
}>()
</script>
