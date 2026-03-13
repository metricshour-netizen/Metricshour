<template>
  <div class="min-h-screen bg-[#030303] text-white">
    <div class="max-w-3xl mx-auto px-4 py-16">

      <h1 class="text-3xl font-black tracking-tight text-white mb-2">MetricsHour Intelligence</h1>
      <p class="text-white/40 text-sm mb-10">Analysis, data insights, and market commentary.</p>

      <!-- Loading -->
      <div v-if="pending" class="flex items-center gap-3 text-white/30 text-sm">
        <div class="w-4 h-4 border border-white/20 border-t-white/60 rounded-full animate-spin" />
        Loading articles…
      </div>

      <!-- Empty -->
      <div v-else-if="posts.length === 0" class="text-center py-20">
        <div class="text-5xl mb-4">📰</div>
        <h2 class="text-white font-bold text-lg mb-2">No articles yet</h2>
        <p class="text-white/40 text-sm">Check back soon — market intelligence articles coming shortly.</p>
      </div>

      <!-- Post list -->
      <div v-else class="space-y-6">
        <NuxtLink
          v-for="post in posts"
          :key="post.slug"
          :to="`/blog/${post.slug}`"
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
                <h2 class="text-white font-bold text-base leading-snug group-hover:text-emerald-400 transition-colors line-clamp-2 mb-1">
                  {{ post.title }}
                </h2>
                <p v-if="post.excerpt" class="text-white/40 text-sm leading-relaxed line-clamp-2 mb-2">
                  {{ post.excerpt }}
                </p>
                <div class="flex items-center gap-3 text-xs text-white/25">
                  <span>{{ post.author_name }}</span>
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
  published_at?: string | null
}

const { get } = useApi()
const posts = ref<BlogPost[]>([])
const pending = ref(true)

onMounted(async () => {
  try {
    const data = await get<BlogPost[]>('/api/blog', { limit: 50 })
    posts.value = Array.isArray(data) ? data : []
  } catch {
    posts.value = []
  } finally {
    pending.value = false
  }
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
  ogImage: 'https://api.metricshour.com/og/section/home.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterImage: 'https://api.metricshour.com/og/section/home.png',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/blog/' }],
})
</script>
