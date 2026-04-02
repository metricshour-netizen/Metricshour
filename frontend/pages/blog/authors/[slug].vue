<template>
  <div class="min-h-screen bg-[#030303] text-white">
    <div class="max-w-3xl mx-auto px-4 py-16">

      <NuxtLink to="/blog/" class="text-white/30 text-sm hover:text-white/60 transition-colors mb-8 inline-block">
        ← Blog
      </NuxtLink>

      <div v-if="pendingAuthor" class="space-y-4 mt-4">
        <div class="h-20 bg-white/5 rounded-xl animate-pulse" />
      </div>

      <div v-else-if="!author" class="text-red-400 text-sm mt-4">Author not found.</div>

      <template v-else>
        <!-- Author header -->
        <div class="flex items-start gap-5 mb-10">
          <img
            v-if="author.avatar_url"
            :src="author.avatar_url"
            :alt="author.name"
            class="w-16 h-16 rounded-full object-cover shrink-0"
          />
          <div
            v-else
            class="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0"
          >
            <span class="text-emerald-400 font-black text-xl">{{ author.name.charAt(0) }}</span>
          </div>
          <div>
            <h1 class="text-2xl font-black text-white leading-tight">{{ author.name }}</h1>
            <p v-if="author.title" class="text-white/40 text-sm mt-0.5">{{ author.title }}</p>
            <a
              v-if="author.twitter_handle"
              :href="`https://twitter.com/${author.twitter_handle}`"
              target="_blank" rel="noopener"
              class="inline-flex items-center gap-1 mt-2 text-xs text-sky-400 hover:text-sky-300 transition-colors"
            >𝕏 @{{ author.twitter_handle }}</a>
          </div>
        </div>

        <p v-if="author.bio" class="text-white/50 text-sm leading-relaxed mb-10 max-w-xl">{{ author.bio }}</p>

        <!-- Author's articles -->
        <div v-if="pendingPosts" class="space-y-4">
          <div v-for="i in 3" :key="i" class="h-24 bg-white/5 rounded-xl animate-pulse" />
        </div>

        <div v-else>
          <p class="text-xs font-mono text-white/20 uppercase tracking-widest mb-4">
            {{ posts.length }} article{{ posts.length === 1 ? '' : 's' }}
          </p>
          <div class="space-y-4">
            <NuxtLink
              v-for="post in posts"
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
                    class="w-16 h-16 rounded-lg object-cover shrink-0 opacity-80"
                  />
                  <div class="flex-1 min-w-0">
                    <div v-if="post.category" class="mb-1.5">
                      <span
                        class="text-xs font-bold px-2 py-0.5 rounded-full uppercase tracking-wide"
                        :style="`background:${categoryColor(post.category)}22; color:${categoryColor(post.category)}`"
                      >{{ post.category }}</span>
                    </div>
                    <h2 class="text-white font-bold text-sm leading-snug group-hover:text-emerald-400 transition-colors line-clamp-2 mb-1">
                      {{ post.title }}
                    </h2>
                    <p v-if="post.excerpt" class="text-white/35 text-xs leading-relaxed line-clamp-2 mb-1.5">
                      {{ post.excerpt }}
                    </p>
                    <span class="text-xs text-white/20">{{ formatDate(post.published_at) }}</span>
                  </div>
                </div>
              </article>
            </NuxtLink>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Author {
  slug: string
  name: string
  title?: string | null
  bio?: string | null
  avatar_url?: string | null
  twitter_handle?: string | null
}

interface BlogPost {
  id: number
  title: string
  slug: string
  excerpt?: string | null
  cover_image_url?: string | null
  author_name: string
  category?: string | null
  published_at?: string | null
}

const CATEGORY_COLORS: Record<string, string> = {
  macro: '#a78bfa', trade: '#34d399', markets: '#60a5fa', crypto: '#f59e0b',
  commodities: '#fb923c', fx: '#e879f9', geopolitics: '#f87171', data: '#94a3b8',
}
function categoryColor(slug: string): string {
  return CATEGORY_COLORS[slug] ?? '#6b7280'
}

const route = useRoute()
const slug = computed(() => route.params.slug as string)
const runtimeConfig = useRuntimeConfig()

function apiBase() {
  return import.meta.server
    ? runtimeConfig.apiBaseServer
    : runtimeConfig.public.apiBase
}

const { data: author, pending: pendingAuthor } = useAsyncData(`author-${slug.value}`, async () => {
  const res = await fetch(`${apiBase()}/api/blog/authors/${slug.value}`).catch(() => null)
  if (!res || !res.ok) return null
  return res.json() as Promise<Author>
})

const { data: postsData, pending: pendingPosts } = useAsyncData(`author-posts-${slug.value}`, async () => {
  const res = await fetch(`${apiBase()}/api/blog/authors/${slug.value}/posts?limit=50`).catch(() => null)
  if (!res || !res.ok) return []
  const data = await res.json()
  return Array.isArray(data) ? data : []
})

const posts = computed<BlogPost[]>(() => postsData.value ?? [])

function formatDate(iso?: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

watchEffect(() => {
  if (author.value) {
    useSeoMeta({
      title: `${author.value.name} — MetricsHour`,
      description: author.value.bio ?? `Articles by ${author.value.name} on MetricsHour.`,
      ogTitle: `${author.value.name} — MetricsHour`,
      ogDescription: author.value.bio ?? `Articles by ${author.value.name}.`,
    })
    useHead({
      link: [{ rel: 'canonical', href: `https://metricshour.com/blog/authors/${slug.value}/` }],
    })
  }
})
</script>
