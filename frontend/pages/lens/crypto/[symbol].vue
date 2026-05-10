<template>
  <main class="max-w-3xl mx-auto px-4 py-8">
    <NuxtLink to="/lens/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">← Lens</NuxtLink>
    <LensComingSoon
      asset-type="crypto"
      @analyze-stock="navigateTo('/lens/')"
      @analyze-forex="navigateTo('/lens/')"
    />
  </main>
</template>

<script setup lang="ts">
const { t } = useI18n()
const route = useRoute()
const symbol = (route.params.symbol as string).toUpperCase()

useSeoMeta({
  title: `${symbol} Lens — Coming Soon — MetricsHour`,
  description: 'Crypto analysis is coming to MetricsHour Lens. Get notified when it launches.',
  robots: 'index, follow',
})
</script>
