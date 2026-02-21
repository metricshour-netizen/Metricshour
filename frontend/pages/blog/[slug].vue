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

      <!-- Footer -->
      <div class="border-t border-[#1f2937] pt-6">
        <p class="text-xs text-gray-600">Published on MetricsHour · {{ fmtDate(post.published_at) }}</p>
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

const { data: post, pending, error } = await useAsyncData(
  `blog-${slug}`,
  () => get<BlogPost>(`/api/blog/${slug}`),
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
  ogImage: computed(() => post.value?.cover_image_url || ''),
})
</script>
