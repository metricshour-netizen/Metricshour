<template>
  <main class="max-w-3xl mx-auto px-4 py-10">
    <NuxtLink to="/feed/" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
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
      <div
        class="prose prose-invert prose-sm max-w-none text-gray-300 leading-relaxed mb-10
               prose-headings:text-white prose-headings:font-bold
               prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-3
               prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-2
               prose-p:text-gray-300 prose-p:leading-relaxed
               prose-a:text-emerald-400 prose-a:no-underline hover:prose-a:underline
               prose-strong:text-white
               prose-em:text-gray-400
               prose-blockquote:border-emerald-500 prose-blockquote:text-gray-400
               prose-table:text-sm prose-table:w-full
               prose-th:text-white prose-th:bg-[#111827] prose-th:px-3 prose-th:py-2
               prose-td:px-3 prose-td:py-2 prose-td:border-gray-800
               prose-img:rounded-xl prose-img:w-full prose-img:my-6
               prose-hr:border-gray-800
               prose-code:text-emerald-400 prose-code:bg-[#0d1117] prose-code:px-1 prose-code:rounded"
        v-html="renderedBody"
      />

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

      <!-- Related entities — stocks + countries tagged in post -->
      <div v-if="relatedAssets.length || relatedCountries.length" class="mb-8">
        <p class="text-xs font-mono text-gray-600 uppercase tracking-widest mb-3">Explore in MetricsHour</p>
        <div class="flex flex-wrap gap-2">
          <NuxtLink
            v-for="a in relatedAssets"
            :key="a.id"
            :to="`/stocks/${a.symbol.toLowerCase()}`"
            class="inline-flex items-center gap-1.5 text-xs bg-[#111827] border border-[#1f2937] hover:border-emerald-500/40 text-gray-300 hover:text-emerald-400 px-3 py-1.5 rounded-lg transition-colors"
          >
            <span class="font-mono font-bold text-emerald-400">{{ a.symbol }}</span>
            <span class="text-gray-500">{{ a.name.split(' ').slice(0, 2).join(' ') }}</span>
          </NuxtLink>
          <NuxtLink
            v-for="c in relatedCountries"
            :key="c.id"
            :to="`/countries/${c.code.toLowerCase()}`"
            class="inline-flex items-center gap-1.5 text-xs bg-[#111827] border border-[#1f2937] hover:border-blue-500/40 text-gray-300 hover:text-blue-400 px-3 py-1.5 rounded-lg transition-colors"
          >
            <span>{{ c.flag }}</span>
            <span>{{ c.name }}</span>
          </NuxtLink>
        </div>
      </div>

      <!-- More articles -->
      <div v-if="otherPosts.length" class="mb-8 border-t border-[#1f2937] pt-6">
        <p class="text-xs font-mono text-gray-600 uppercase tracking-widest mb-3">More from MetricsHour</p>
        <div class="space-y-3">
          <NuxtLink
            v-for="p in otherPosts"
            :key="p.id"
            :to="`/blog/${p.slug}/`"
            class="block group"
          >
            <p class="text-sm text-gray-300 group-hover:text-white transition-colors leading-snug">{{ p.title }}</p>
            <p class="text-xs text-gray-600 mt-0.5">{{ fmtDate(p.published_at) }}</p>
          </NuxtLink>
        </div>
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
import { marked, Renderer } from 'marked'

// Custom renderer: add explicit classes to img/a/blockquote so they display
// correctly without requiring @tailwindcss/typography plugin
const renderer = new Renderer()
renderer.image = ({ href, title, text }: { href: string; title?: string | null; text: string }) => {
  const titleAttr = title ? ` title="${title}"` : ''
  return `<img src="${href}" alt="${text}"${titleAttr} class="w-full rounded-xl my-6 block" loading="lazy" />`
}
marked.use({ renderer })

interface BlogPost {
  id: number
  title: string
  slug: string
  body: string
  excerpt?: string
  cover_image_url?: string
  author_name: string
  published_at?: string
  updated_at?: string
  related_asset_ids?: number[] | null
  related_country_ids?: number[] | null
}

interface RelatedAsset {
  id: number
  symbol: string
  name: string
  asset_type: string
  price?: { close: number; change_pct: number } | null
}

interface RelatedCountry {
  id: number
  code: string
  name: string
  flag: string
}

const route = useRoute()
const runtimeConfig = useRuntimeConfig()

const slug = route.params.slug as string
const articleUrl = `https://metricshour.com/blog/${slug}/`

// Single SSR-compatible fetch: post + related entities + other posts in one pass
const { data: pageData, pending, error } = useAsyncData(
  `blog-${slug}`,
  async () => {
    // On the server, call the API directly (bypasses Cloudflare which strips markdown images)
    const base = import.meta.server
      ? runtimeConfig.apiBaseServer
      : runtimeConfig.public.apiBase

    const res = await fetch(`${base}/api/blog/${slug}`).catch(() => null)
    if (!res || !res.ok) return null
    const post = await res.json() as BlogPost

    // Fetch related assets + countries server-side so they appear in SSR HTML
    const [assetList, countryList, otherList] = await Promise.all([
      post.related_asset_ids?.length
        ? fetch(`${base}/api/assets?limit=200`).then(r => r.ok ? r.json() : []).catch(() => [])
        : Promise.resolve([]),
      post.related_country_ids?.length
        ? fetch(`${base}/api/countries?limit=300`).then(r => r.ok ? r.json() : []).catch(() => [])
        : Promise.resolve([]),
      fetch(`${base}/api/blog?limit=6`).then(r => r.ok ? r.json() : []).catch(() => []),
    ])

    const assets: RelatedAsset[] = (Array.isArray(assetList) ? assetList : (assetList.items ?? []))
      .filter((a: RelatedAsset) => post.related_asset_ids?.includes(a.id))
      .slice(0, 6)

    const countries: RelatedCountry[] = (Array.isArray(countryList) ? countryList : (countryList.items ?? []))
      .filter((c: RelatedCountry) => post.related_country_ids?.includes(c.id))
      .slice(0, 8)

    const others: BlogPost[] = (Array.isArray(otherList) ? otherList : [])
      .filter((p: BlogPost) => p.slug !== slug)
      .slice(0, 3)

    return { post, assets, countries, others }
  },
)

const post = computed(() => pageData.value?.post ?? null)
const relatedAssets = computed(() => pageData.value?.assets ?? [])
const relatedCountries = computed(() => pageData.value?.countries ?? [])
const otherPosts = computed(() => pageData.value?.others ?? [])

const renderedBody = computed(() => {
  if (!post.value?.body) return ''
  return marked.parse(post.value.body, { async: false }) as string
})

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
  ogImageAlt: computed(() => post.value?.title || 'MetricsHour'),
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterTitle: computed(() => post.value ? `${post.value.title} — MetricsHour` : 'Article — MetricsHour'),
  twitterDescription: computed(() => post.value?.excerpt || ''),
  twitterImage: computed(() => post.value?.cover_image_url || 'https://cdn.metricshour.com/og/section/home.png'),
  twitterCard: 'summary_large_image',
})

useHead({
  link: [{ rel: 'canonical', href: `https://metricshour.com/blog/${slug}/` }],
  script: [
    {
      type: 'application/ld+json',
      innerHTML: computed(() => {
        if (!post.value) return '{}'
        const imgUrl = post.value.cover_image_url || 'https://cdn.metricshour.com/og/section/home.png'
        const words = post.value.body ? post.value.body.split(/\s+/).length : 0
        return JSON.stringify({
          '@context': 'https://schema.org',
          '@type': 'Article',
          headline: post.value.title,
          description: post.value.excerpt || '',
          image: { '@type': 'ImageObject', url: imgUrl, width: 1200, height: 630 },
          author: { '@type': 'Person', name: post.value.author_name },
          creator: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com' },
          license: 'https://metricshour.com/terms',
          publisher: {
            '@type': 'Organization',
            name: 'MetricsHour',
            url: 'https://metricshour.com',
            logo: { '@type': 'ImageObject', url: 'https://metricshour.com/og-image.png', width: 1200, height: 630 },
          },
          datePublished: post.value.published_at || '',
          dateModified: post.value.updated_at || post.value.published_at || '',
          mainEntityOfPage: { '@type': 'WebPage', '@id': `https://metricshour.com/blog/${slug}/` },
          url: `https://metricshour.com/blog/${slug}/`,
          inLanguage: 'en',
          wordCount: words,
        })
      }),
    },
    {
      type: 'application/ld+json',
      innerHTML: computed(() => JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
          { '@type': 'ListItem', position: 2, name: 'Blog', item: 'https://metricshour.com/blog/' },
          { '@type': 'ListItem', position: 3, name: post.value?.title || slug, item: `https://metricshour.com/blog/${slug}/` },
        ],
      })),
    },
  ],
})
</script>
