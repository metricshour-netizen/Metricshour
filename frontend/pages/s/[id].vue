<template>
  <div style="font-family:sans-serif;color:#ccc;background:#050505;padding:2rem">
    <p>Redirecting to <a href="/feed" style="color:#10b981">MetricsHour Feed</a>…</p>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()

const eventId = route.params.id as string
const canonical = `https://metricshour.com/feed/${eventId}`

const { data: event } = await useAsyncData(
  `s-event-${eventId}`,
  () => get<any>(`/api/feed/events/${eventId}`).catch(() => null),
)

const ogImage = event.value?.image_url || `https://cdn.metricshour.com/og/feed/${eventId}.png`
const title = event.value?.title ? `${event.value.title} — MetricsHour` : 'Market Insight — MetricsHour'
const desc = event.value?.body?.slice(0, 200) || 'Real-time global market intelligence on MetricsHour.'

useSeoMeta({
  title,
  robots: 'noindex',
  ogType: 'article',
  ogSiteName: 'MetricsHour',
  ogUrl: canonical,
  ogTitle: title,
  ogDescription: desc,
  ogImage,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterSite: '@metricshour',
  twitterTitle: title,
  twitterDescription: desc,
  twitterImage: ogImage,
})

// Redirect real browsers; crawlers don't run JS so they see the meta tags above
onMounted(() => {
  navigateTo(canonical, { external: true, replace: true })
})
</script>
