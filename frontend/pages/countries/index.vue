<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white">Countries</h1>
      <p class="text-gray-500 text-sm mt-1">196 countries · GDP, inflation, trade, and 80+ macro indicators</p>
    </div>

    <!-- Filters -->
    <div class="flex gap-2 flex-wrap mb-6">
      <button v-for="f in filters" :key="f.key"
        @click="activeFilter = activeFilter === f.key ? null : f.key"
        class="px-3 py-1 rounded text-xs font-medium border transition-colors"
        :class="activeFilter === f.key
          ? 'bg-emerald-500 border-emerald-500 text-black'
          : 'border-[#1f2937] text-gray-400 hover:border-gray-500'">
        {{ f.label }}
      </button>
    </div>

    <div v-if="pending" class="text-gray-500">Loading...</div>
    <div v-else-if="error" class="text-red-400">Failed to load countries</div>
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      <NuxtLink
        v-for="c in filtered"
        :key="c.code"
        :to="`/countries/${c.code.toLowerCase()}`"
        class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg p-4 transition-colors"
      >
        <div class="flex items-center gap-2 mb-2">
          <span class="text-xl">{{ c.flag }}</span>
          <span class="font-medium text-white text-sm">{{ c.name }}</span>
        </div>
        <div class="text-xs text-gray-500 flex gap-2 flex-wrap">
          <span>{{ c.region }}</span>
          <span v-if="c.currency_code">· {{ c.currency_code }}</span>
        </div>
        <div class="flex gap-1 mt-2 flex-wrap">
          <span v-for="g in c.groupings.slice(0, 3)" :key="g"
                class="text-[10px] bg-[#1f2937] text-gray-400 px-1.5 py-0.5 rounded">
            {{ g }}
          </span>
        </div>
      </NuxtLink>
    </div>
  </main>
</template>

<script setup lang="ts">
const filters = [
  { key: 'is_g20', label: 'G20' },
  { key: 'is_g7', label: 'G7' },
  { key: 'is_eu', label: 'EU' },
  { key: 'is_nato', label: 'NATO' },
  { key: 'is_opec', label: 'OPEC' },
  { key: 'is_brics', label: 'BRICS' },
]
const activeFilter = ref<string | null>(null)

const { get } = useApi()
const { data: countries, pending, error } = await useAsyncData('countries-all',
  () => get('/api/countries')
)

const filtered = computed(() => {
  if (!countries.value) return []
  if (!activeFilter.value) return countries.value
  return countries.value.filter((c: any) => c[activeFilter.value!])
})

useSeoMeta({
  title: 'Countries — MetricsHour',
  description: 'Macro data for 196 countries: GDP, inflation, trade, debt, and 80+ indicators.',
})
</script>
