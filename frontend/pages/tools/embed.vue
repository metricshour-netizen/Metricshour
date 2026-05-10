<template>
  <main class="max-w-3xl mx-auto px-4 py-10">
    <NuxtLink to="/tools/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-6 inline-flex items-center gap-1">
      ← Tools
    </NuxtLink>

    <div class="mb-8">
      <h1 class="text-2xl sm:text-3xl font-extrabold text-white">Embed Widget Generator</h1>
      <p class="text-gray-400 text-sm mt-2">Embed MetricsHour data on your website or blog with a single line of code.</p>
    </div>

    <!-- Widget type selector -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6 mb-6">
      <h2 class="text-sm font-bold text-white mb-4">1. Choose widget type</h2>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <button
          v-for="t in types"
          :key="t.key"
          @click="widgetType = t.key; identifier = ''"
          class="flex items-center gap-3 px-4 py-3 rounded-xl border transition-all text-left"
          :class="widgetType === t.key
            ? 'border-emerald-500 bg-emerald-900/10 text-white'
            : 'border-[#1f2937] text-gray-400 hover:border-gray-500 hover:text-gray-200'"
        >
          <span class="text-xl" aria-hidden="true">{{ t.icon }}</span>
          <div>
            <div class="text-sm font-semibold">{{ t.label }}</div>
            <div class="text-[10px] text-gray-600 leading-tight mt-0.5">{{ t.desc }}</div>
          </div>
        </button>
      </div>
    </div>

    <!-- Identifier input -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6 mb-6">
      <h2 class="text-sm font-bold text-white mb-4">2. Enter {{ activeType?.label }} identifier</h2>
      <input
        v-model="identifier"
        type="text"
        :placeholder="activeType?.placeholder"
        class="w-full bg-[#0d1117] border border-[#1f2937] rounded-xl px-4 py-3 text-sm font-mono text-white placeholder-gray-700 focus:outline-none focus:border-emerald-500 transition-colors uppercase"
        @input="identifier = identifier.toUpperCase()"
      />
      <p class="text-[10px] text-gray-600 mt-2">Example: {{ activeType?.example }}</p>
    </div>

    <!-- Options -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6 mb-6">
      <h2 class="text-sm font-bold text-white mb-4">3. Customise</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="text-xs text-gray-500 mb-2 block">Width (px)</label>
          <select
            v-model="width"
            class="w-full bg-[#0d1117] border border-[#1f2937] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
          >
            <option value="300">300px</option>
            <option value="400">400px</option>
            <option value="500">500px</option>
            <option value="600">600px</option>
            <option value="100%">100% (fluid)</option>
          </select>
        </div>
        <div>
          <label class="text-xs text-gray-500 mb-2 block">Theme</label>
          <select
            v-model="theme"
            class="w-full bg-[#0d1117] border border-[#1f2937] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
          >
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Embed code output -->
    <div v-if="embedUrl" class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6 mb-6">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-bold text-white">4. Copy embed code</h2>
        <button
          @click="copyCode"
          class="text-xs font-semibold px-3 py-1.5 rounded-lg border transition-colors"
          :class="copied ? 'border-emerald-600 text-emerald-400 bg-emerald-900/20' : 'border-[#374151] text-gray-400 hover:border-emerald-600 hover:text-emerald-400'"
        >{{ copied ? '✓ Copied' : 'Copy code' }}</button>
      </div>
      <pre class="bg-[#0d1117] rounded-lg p-4 text-xs text-emerald-300 font-mono overflow-x-auto whitespace-pre-wrap break-all">{{ embedCode }}</pre>
    </div>

    <!-- Preview -->
    <div v-if="embedUrl" class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6">
      <h2 class="text-sm font-bold text-white mb-4">Preview</h2>
      <iframe
        :src="embedUrl"
        :width="width === '100%' ? '100%' : Number(width)"
        height="400"
        frameborder="0"
        scrolling="no"
        class="rounded-xl border border-[#1f2937] w-full"
      />
    </div>
  </main>
</template>

<script setup lang="ts">
const { public: { apiBase } } = useRuntimeConfig()

const types = [
  { key: 'stock',   icon: '📈', label: 'Stock',   desc: 'Price chart + revenue', placeholder: 'e.g. AAPL', example: 'AAPL' },
  { key: 'country', icon: '🌍', label: 'Country',  desc: 'GDP & macro data',      placeholder: 'e.g. US',   example: 'US' },
  { key: 'trade',   icon: '🔀', label: 'Trade',    desc: 'Bilateral trade flow',  placeholder: 'e.g. US-CN', example: 'US-CN' },
]

const widgetType = ref('stock')
const identifier = ref('')
const width = ref('600')
const theme = ref('dark')
const copied = ref(false)

const activeType = computed(() => types.find(t => t.key === widgetType.value))

const embedPath = computed(() => {
  if (!identifier.value.trim()) return null
  const id = identifier.value.trim().toLowerCase()
  if (widgetType.value === 'stock') return `/embed/stocks/${id}`
  if (widgetType.value === 'country') return `/embed/country/${id}`
  if (widgetType.value === 'trade') return `/embed/trade/${id}`
  return null
})

const embedUrl = computed(() => {
  if (!embedPath.value) return null
  return `https://metricshour.com${embedPath.value}`
})

const embedCode = computed(() => {
  if (!embedUrl.value) return ''
  const w = width.value === '100%' ? '100%' : `${width.value}px`
  return `<iframe\n  src="${embedUrl.value}"\n  width="${w}"\n  height="400"\n  frameborder="0"\n  scrolling="no"\n  style="border-radius:12px;border:1px solid #1f2937"\n></iframe>`
})

async function copyCode() {
  if (!embedCode.value) return
  await navigator.clipboard.writeText(embedCode.value).catch(() => {})
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

useSeoMeta({
  title: 'Embed Widget Generator — MetricsHour',
  description: 'Embed MetricsHour financial data widgets on your website. Stocks, country macros, and trade flow charts. Free embed code generator.',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/tools/embed/' }],
})
</script>
