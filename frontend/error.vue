<template>
  <div class="min-h-screen bg-[#0a0e1a] flex items-center justify-center px-4">
    <div class="max-w-md w-full text-center">
      <div class="text-5xl mb-6 font-mono font-bold text-gray-700">{{ error?.statusCode || 404 }}</div>
      <h1 class="text-xl font-bold text-white mb-2">{{ title }}</h1>
      <p class="text-gray-500 text-sm mb-8">{{ message }}</p>

      <div v-if="redirectTarget" class="mb-6">
        <p class="text-xs text-gray-600 mb-3">Did you mean?</p>
        <NuxtLink
          :to="redirectTarget"
          class="inline-flex items-center gap-2 bg-emerald-900/30 border border-emerald-700 text-emerald-400 px-4 py-2 rounded-lg text-sm hover:bg-emerald-900/50 transition-colors"
        >
          {{ redirectTarget }}
        </NuxtLink>
      </div>

      <div class="flex items-center justify-center gap-4 text-sm">
        <NuxtLink to="/" class="text-emerald-500 hover:text-emerald-300 transition-colors">← Home</NuxtLink>
        <NuxtLink to="/markets" class="text-gray-500 hover:text-gray-300 transition-colors">Markets</NuxtLink>
        <NuxtLink to="/countries" class="text-gray-500 hover:text-gray-300 transition-colors">Countries</NuxtLink>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ error: { statusCode: number; statusMessage?: string; url?: string } | null }>()

const url = props.error?.url || ''

// Detect compare reverse URL pattern (e.g. /compare/us-vs-cn → /compare/cn-vs-us)
const compareMatch = url.match(/^\/compare\/([a-z]{2,3})-vs-([a-z]{2,3})\/?$/)
const redirectTarget = computed(() => {
  if (!compareMatch) return null
  const [, a, b] = compareMatch
  const [canonA, canonB] = [a, b].sort()
  if (a === canonA) return null // already canonical, no redirect suggestion
  return `/compare/${canonA}-vs-${canonB}/`
})

const title = computed(() => {
  if (props.error?.statusCode === 404) return 'Page not found'
  if (props.error?.statusCode === 500) return 'Server error'
  return 'Something went wrong'
})

const message = computed(() => {
  if (redirectTarget.value) return 'Country comparisons are sorted alphabetically.'
  if (props.error?.statusCode === 404) return 'This page does not exist or has moved.'
  return props.error?.statusMessage || 'An unexpected error occurred.'
})

useHead({ title: `${title.value} — MetricsHour` })
</script>
