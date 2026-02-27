<template>
  <main class="max-w-lg mx-auto px-4 py-10">
    <NuxtLink to="/feed" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
      ← Back to Feed
    </NuxtLink>

    <div v-if="pending" class="h-64 bg-[#111827] rounded-2xl animate-pulse" />
    <div v-else-if="error || !event" class="text-red-400 text-sm">Event not found.</div>

    <template v-else>
      <!-- Card preview -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-2xl overflow-hidden mb-6">
        <ClientOnly>
          <div class="h-72">
            <FeedCard :event="event" />
          </div>
        </ClientOnly>
      </div>

      <!-- Share section -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
        <h2 class="text-sm font-bold text-white mb-1">Share this insight</h2>
        <p class="text-xs text-gray-500 mb-4 leading-relaxed">{{ event.title }}</p>

        <div class="grid grid-cols-3 gap-3">
          <!-- Twitter -->
          <a
            :href="`https://twitter.com/intent/tweet?url=${encodeURIComponent(cardUrl)}&text=${encodeURIComponent(event.title)}`"
            target="_blank"
            rel="noopener"
            class="flex flex-col items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-sky-500/40 rounded-xl py-4 transition-colors group"
          >
            <svg class="w-5 h-5 text-sky-400 fill-current group-hover:scale-110 transition-transform" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
            <span class="text-[11px] text-gray-400 font-semibold">Tweet</span>
          </a>

          <!-- WhatsApp -->
          <a
            :href="`https://wa.me/?text=${encodeURIComponent(event.title + ' — ' + cardUrl)}`"
            target="_blank"
            rel="noopener"
            class="flex flex-col items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-500/40 rounded-xl py-4 transition-colors group"
          >
            <svg class="w-5 h-5 text-emerald-400 fill-current group-hover:scale-110 transition-transform" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
            </svg>
            <span class="text-[11px] text-gray-400 font-semibold">WhatsApp</span>
          </a>

          <!-- LinkedIn -->
          <a
            :href="`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(cardUrl)}`"
            target="_blank"
            rel="noopener"
            class="flex flex-col items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-sky-400/40 rounded-xl py-4 transition-colors group"
          >
            <svg class="w-5 h-5 text-sky-300 fill-current group-hover:scale-110 transition-transform" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
            <span class="text-[11px] text-gray-400 font-semibold">LinkedIn</span>
          </a>
        </div>

        <!-- Copy link -->
        <button
          class="w-full mt-3 flex items-center justify-between bg-[#0d1117] border border-[#1f2937] hover:border-gray-500 rounded-xl px-4 py-3 text-xs text-gray-400 transition-colors group"
          @click="copyLink"
        >
          <span class="font-mono truncate text-gray-600">{{ cardUrl }}</span>
          <span class="shrink-0 ml-2 font-semibold group-hover:text-white transition-colors">{{ copied ? '✓ Copied' : 'Copy' }}</span>
        </button>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const { get } = useApi()

const eventId = route.params.id as string
const cardUrl = `https://metricshour.com/feed/${eventId}`

// Fetch single event by ID — runs server-side for OG meta tags
const { data: feedData, pending, error } = useAsyncData(
  `feed-event-${eventId}`,
  () => get<any>(`/api/feed/events/${eventId}`).catch(() => null),
)

const event = computed(() => feedData.value ?? null)

const copied = ref(false)
function copyLink() {
  if (import.meta.client) {
    navigator.clipboard.writeText(cardUrl).then(() => {
      copied.value = true
      setTimeout(() => { copied.value = false }, 2000)
    })
  }
}

// SEO meta for social sharing
const ogImage = computed(() =>
  event.value?.image_url || 'https://metricshour.com/og-image.png'
)

useSeoMeta({
  title: computed(() => event.value ? `${event.value.title} — MetricsHour` : 'Market Insight — MetricsHour'),
  description: computed(() => event.value?.body || 'Real-time global market intelligence on MetricsHour.'),
  ogTitle: computed(() => event.value ? `${event.value.title} — MetricsHour` : 'Market Insight — MetricsHour'),
  ogDescription: computed(() => event.value?.body || 'Real-time global market intelligence on MetricsHour.'),
  ogUrl: cardUrl,
  ogType: 'article',
  ogImage,
  twitterCard: 'summary_large_image',
  twitterTitle: computed(() => event.value ? `${event.value.title} — MetricsHour` : 'Market Insight — MetricsHour'),
  twitterDescription: computed(() => event.value?.body || 'Real-time global market intelligence on MetricsHour.'),
  twitterImage: ogImage,
})

useHead({
  link: [{ rel: 'canonical', href: cardUrl }],
})
</script>
