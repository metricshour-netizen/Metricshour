<template>
  <div class="min-h-screen bg-[#030303] text-white">
    <div class="max-w-3xl mx-auto px-4 py-16">

      <h1 class="text-3xl font-black tracking-tight text-white mb-2">MetricsHour Intelligence</h1>
      <p class="text-white/40 text-sm mb-8">Analysis, data insights, and market commentary.</p>

      <!-- Category filter pills -->
      <div class="flex flex-wrap gap-2 mb-8">
        <button
          class="px-3 py-1 rounded-full text-xs font-semibold border transition-all"
          :class="activeCategory === null
            ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300'
            : 'border-white/10 text-white/40 hover:border-white/30 hover:text-white/70'"
          @click="activeCategory = null"
        >All</button>
        <button
          v-for="cat in CATEGORIES"
          :key="cat.slug"
          class="px-3 py-1 rounded-full text-xs font-semibold border transition-all"
          :class="activeCategory === cat.slug
            ? 'border-emerald-500/60 text-emerald-300'
            : 'border-white/10 text-white/40 hover:border-white/30 hover:text-white/70'"
          :style="activeCategory === cat.slug ? `background:${cat.color}22` : ''"
          @click="activeCategory = cat.slug"
        >{{ cat.label }}</button>
      </div>

      <!-- Loading -->
      <div v-if="pending" class="flex items-center gap-3 text-white/30 text-sm">
        <div class="w-4 h-4 border border-white/20 border-t-white/60 rounded-full animate-spin" />
        Loading articles…
      </div>

      <!-- Empty -->
      <div v-else-if="filteredPosts.length === 0" class="text-center py-20">
        <div class="text-5xl mb-4">📰</div>
        <h2 class="text-white font-bold text-lg mb-2">No articles yet</h2>
        <p class="text-white/40 text-sm">Check back soon — market intelligence articles coming shortly.</p>
      </div>

      <!-- Post list -->
      <div v-else class="space-y-6">
        <NuxtLink
          v-for="post in filteredPosts"
          :key="post.slug"
          :to="`/blog/${post.slug}/`"
          class="block group"
        >
          <article class="border border-white/8 rounded-xl p-5 bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/20 transition-all">
            <div class="flex items-start gap-4">
              <img
                v-if="post.cover_image_url"
                :src="post.cover_image_url"
                :alt="post.title"
                class="w-20 h-20 rounded-lg object-cover shrink-0 opacity-80"
              />
              <div class="flex-1 min-w-0">
                <!-- Category badge -->
                <div v-if="post.category" class="mb-1.5">
                  <span
                    class="text-xs font-bold px-2 py-0.5 rounded-full uppercase tracking-wide"
                    :style="`background:${categoryColor(post.category)}22; color:${categoryColor(post.category)}`"
                  >{{ post.category }}</span>
                </div>
                <h2 class="text-white font-bold text-base leading-snug group-hover:text-emerald-400 transition-colors line-clamp-2 mb-1">
                  {{ post.title }}
                </h2>
                <p v-if="post.excerpt" class="text-white/40 text-sm leading-relaxed line-clamp-2 mb-2">
                  {{ post.excerpt }}
                </p>
                <div class="flex items-center gap-3 text-xs text-white/25">
                  <NuxtLink
                    v-if="post.author_slug"
                    :to="`/blog/authors/${post.author_slug}/`"
                    class="hover:text-white/60 transition-colors"
                    @click.stop
                  >{{ post.author_name }}</NuxtLink>
                  <span v-else>{{ post.author_name }}</span>
                  <span>·</span>
                  <span>{{ formatDate(post.published_at) }}</span>
                </div>
              </div>
            </div>
          </article>
        </NuxtLink>
      </div>

      <!-- Newsletter -->
      <div class="mt-10 border border-gray-800 rounded-xl p-6 bg-gray-900/40 max-w-xl mx-auto">
        <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">More macro intelligence, every week.</p>
        <p class="text-xs text-gray-500 mb-4">GDP, trade flows, market moves — free.</p>
        <NewsletterCapture source="blog_index" button-text="Subscribe free" />
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
interface BlogPost {
  id: number
  title: string
  slug: string
  excerpt?: string | null
  cover_image_url?: string | null
  author_name: string
  author_slug?: string | null
  category?: string | null
  published_at?: string | null
}

const CATEGORIES = [
  { slug: 'macro',       label: 'Macro',       color: '#a78bfa' },
  { slug: 'trade',       label: 'Trade',       color: '#34d399' },
  { slug: 'markets',     label: 'Markets',     color: '#60a5fa' },
  { slug: 'crypto',      label: 'Crypto',      color: '#f59e0b' },
  { slug: 'commodities', label: 'Commodities', color: '#fb923c' },
  { slug: 'fx',          label: 'FX',          color: '#e879f9' },
  { slug: 'geopolitics', label: 'Geopolitics', color: '#f87171' },
  { slug: 'data',        label: 'Data',        color: '#94a3b8' },
]

const CATEGORY_COLORS: Record<string, string> = Object.fromEntries(
  CATEGORIES.map(c => [c.slug, c.color])
)

function categoryColor(slug: string): string {
  return CATEGORY_COLORS[slug] ?? '#6b7280'
}

const runtimeConfig = useRuntimeConfig()
const activeCategory = ref<string | null>(null)

const { data, pending } = useAsyncData('blog-index', async () => {
  const base = import.meta.server
    ? runtimeConfig.apiBaseServer
    : runtimeConfig.public.apiBase
  const res = await fetch(`${base}/api/blog?limit=100`).catch(() => null)
  if (!res || !res.ok) return []
  const data = await res.json()
  return Array.isArray(data) ? data : []
})

const posts = computed<BlogPost[]>(() => data.value ?? [])

const filteredPosts = computed(() => {
  if (!activeCategory.value) return posts.value
  return posts.value.filter(p => p.category === activeCategory.value)
})

function formatDate(iso?: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

useSeoMeta({
  title: 'Blog — MetricsHour',
  description: 'Market intelligence articles, data analysis, and financial commentary from the MetricsHour team.',
  ogTitle: 'Blog — MetricsHour',
  ogDescription: 'Market intelligence articles, data analysis, and financial commentary.',
  ogUrl: 'https://metricshour.com/blog/',
  ogType: 'website',
  ogImage: 'https://cdn.metricshour.com/og/section/blog.png',
  ogImageAlt: 'MetricsHour Blog',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterTitle: 'Blog — MetricsHour',
  twitterDescription: 'Market intelligence articles, data analysis, and financial commentary.',
  twitterImage: 'https://cdn.metricshour.com/og/section/blog.png',
})

useHead({
  link: [
    { rel: 'canonical', href: 'https://metricshour.com/blog/' },
    { rel: 'alternate', type: 'application/rss+xml', title: 'MetricsHour Blog RSS Feed', href: 'https://api.metricshour.com/rss.xml' },
  ],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Blog — MetricsHour',
      url: 'https://metricshour.com/blog/',
      description: 'Market intelligence articles, data analysis, and financial commentary from the MetricsHour team.',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
      breadcrumb: {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: 'https://metricshour.com/blog/' },
        ],
      },
    }),
  }],
})
</script>
