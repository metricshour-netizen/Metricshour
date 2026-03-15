<template>
  <main class="max-w-3xl mx-auto px-4 py-10">
    <NuxtLink to="/feed" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
      ← Back to Feed
    </NuxtLink>

    <div v-if="pending" class="space-y-4">
      <div class="h-64 bg-[#111827] rounded-xl animate-pulse" />
      <div class="h-8 bg-[#111827] rounded animate-pulse" />
      <div class="h-4 bg-[#111827] rounded animate-pulse w-1/2" />
    </div>

    <div v-else-if="error || !post" class="text-red-400 text-sm">Article not found.</div>

    <template v-else>
      <!-- Cover image -->
      <div v-if="post.cover_image_url" class="mb-6 rounded-xl overflow-hidden">
        <img
          :src="post.cover_image_url"
          :alt="post.title"
          class="w-full h-64 sm:h-80 object-cover"
        />
      </div>

      <!-- Title block -->
      <div class="mb-6">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-xs bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full font-bold">ARTICLE</span>
          <span v-if="post.published_at" class="text-xs text-gray-500">{{ fmtDate(post.published_at) }}</span>
          <span class="text-xs text-gray-600">· {{ readingTime }} min read</span>
        </div>
        <h1 class="text-2xl sm:text-3xl font-bold text-white leading-tight mb-2">{{ post.title }}</h1>
        <p class="text-gray-500 text-sm">By {{ post.author_name }}</p>
      </div>

      <!-- Body -->
      <div class="prose prose-invert prose-sm max-w-none text-gray-300 leading-relaxed whitespace-pre-wrap mb-10">
        {{ post.body }}
      </div>

      <!-- Share buttons -->
      <div class="flex items-center gap-3 mb-8">
        <span class="text-xs text-gray-600 font-semibold uppercase tracking-wide">Share:</span>
        <a
          :href="`https://twitter.com/intent/tweet?url=${encodeURIComponent(articleUrl)}&text=${encodeURIComponent(post.title)}`"
          target="_blank" rel="noopener"
          class="flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 bg-[#111827] px-3 py-1.5 rounded-lg border border-[#1f2937] hover:border-sky-500/40 transition-colors"
        >𝕏 Tweet</a>
        <a
          :href="`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(articleUrl)}`"
          target="_blank" rel="noopener"
          class="flex items-center gap-1.5 text-xs text-sky-300 hover:text-sky-200 bg-[#111827] px-3 py-1.5 rounded-lg border border-[#1f2937] hover:border-sky-500/40 transition-colors"
        >in LinkedIn</a>
        <a
          :href="`https://wa.me/?text=${encodeURIComponent(post.title + ' ' + articleUrl)}`"
          target="_blank" rel="noopener"
          class="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 bg-[#111827] px-3 py-1.5 rounded-lg border border-[#1f2937] hover:border-emerald-500/40 transition-colors"
        >💬 WhatsApp</a>
      </div>

      <!-- Footer -->
      <div class="border-t border-[#1f2937] pt-6">
        <p class="text-xs text-gray-600">Published on MetricsHour · {{ fmtDate(post.published_at) }}</p>
      </div>

      <!-- Newsletter -->
      <div class="mt-8 border border-gray-800 rounded-xl p-6 bg-gray-900/40">
        <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">More macro intelligence, every week.</p>
        <p class="text-xs text-gray-500 mb-4">GDP, trade flows, market moves — free.</p>
        <NewsletterCapture source="blog_post" button-text="Subscribe free" />
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
interface BlogPost {
  id: number
  title: string
  slug: string
  body: string
  excerpt?: string
  cover_image_url?: string
  author_name: string
  published_at?: string
}

const route = useRoute()
const { get } = useApi()

const slug = route.params.slug as string
const articleUrl = `https://metricshour.com/blog/${slug}`

const { data: post, pending, error } = useAsyncData(
  `blog-${slug}`,
  () => get<BlogPost>(`/api/blog/${slug}`).catch(() => null),
)

const readingTime = computed(() => {
  if (!post.value?.body) return 1
  const words = post.value.body.split(/\s+/).length
  return Math.max(1, Math.ceil(words / 200))
})

function fmtDate(iso?: string): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  })
}

useSeoMeta({
  title: computed(() => post.value ? `${post.value.title} — MetricsHour` : 'Article — MetricsHour'),
  description: computed(() => post.value?.excerpt || ''),
  ogTitle: computed(() => post.value ? `${post.value.title} — MetricsHour` : 'Article — MetricsHour'),
  ogDescription: computed(() => post.value?.excerpt || ''),
  ogUrl: computed(() => `https://metricshour.com/blog/${slug}/`),
  ogType: 'article',
  ogImage: computed(() => post.value?.cover_image_url || 'https://cdn.metricshour.com/og/section/home.png'),
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterTitle: computed(() => post.value ? `${post.value.title} — MetricsHour` : 'Article — MetricsHour'),
  twitterDescription: computed(() => post.value?.excerpt || ''),
  twitterImage: computed(() => post.value?.cover_image_url || 'https://cdn.metricshour.com/og/section/home.png'),
  twitterCard: 'summary_large_image',
})

useHead({
  link: [{ rel: 'canonical', href: `https://metricshour.com/blog/${slug}/` }],
  script: [{
    type: 'application/ld+json',
    innerHTML: computed(() => post.value ? JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'Article',
      headline: post.value.title,
      description: post.value.excerpt || '',
      image: post.value.cover_image_url || 'https://metricshour.com/og-image.png',
      author: { '@type': 'Person', name: post.value.author_name },
      publisher: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com', logo: { '@type': 'ImageObject', url: 'https://metricshour.com/favicon.svg' } },
      datePublished: post.value.published_at || '',
      dateModified: post.value.published_at || '',
      mainEntityOfPage: { '@type': 'WebPage', '@id': `https://metricshour.com/blog/${slug}` },
      url: `https://metricshour.com/blog/${slug}`,
    }) : '{}'),
  }],
})
</script>
