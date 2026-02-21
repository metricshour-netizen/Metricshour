<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-white">Countries</h1>
      <p class="text-gray-500 text-sm mt-1">196 countries · GDP, inflation, trade, and 80+ macro indicators</p>
    </div>

    <!-- Search -->
    <div class="relative mb-4">
      <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-600 text-sm pointer-events-none">🔍</span>
      <input
        v-model="search"
        type="text"
        placeholder="Search countries, regions, currencies..."
        class="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
      />
      <button v-if="search" @click="search = ''" class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400 text-xs">✕</button>
    </div>

    <!-- Group filters -->
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

    <template v-else>
      <!-- Result count when searching -->
      <p v-if="search" class="text-xs text-gray-600 mb-4">{{ filtered.length }} result{{ filtered.length !== 1 ? 's' : '' }} for "{{ search }}"</p>

      <div v-if="filtered.length" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
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

      <div v-else class="text-center py-16 text-gray-600 text-sm">
        No countries match "{{ search }}"
      </div>
    </template>
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
const search = ref('')

const { get } = useApi()
const { data: countries, pending, error } = await useAsyncData('countries-all',
  () => get('/api/countries')
)

const filtered = computed(() => {
  if (!countries.value) return []
  let list = countries.value as any[]

  if (activeFilter.value) {
    list = list.filter((c: any) => c[activeFilter.value!])
  }

  if (search.value.trim()) {
    const q = search.value.toLowerCase().trim()
    list = list.filter((c: any) =>
      c.name?.toLowerCase().includes(q) ||
      c.code?.toLowerCase().includes(q) ||
      c.region?.toLowerCase().includes(q) ||
      c.currency_code?.toLowerCase().includes(q) ||
      c.currency_name?.toLowerCase().includes(q) ||
      c.capital?.toLowerCase().includes(q)
    )
  }

  return list
})

useSeoMeta({
  title: 'Countries — MetricsHour',
  description: 'Macro data for 196 countries: GDP, inflation, trade, debt, and 80+ indicators.',
})
</script>
