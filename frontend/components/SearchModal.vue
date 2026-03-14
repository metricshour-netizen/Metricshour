<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-[200] bg-black/60 backdrop-blur-sm flex items-start justify-center pt-16 px-4"
      @mousedown.self="$emit('update:modelValue', false)"
    >
      <div class="w-full max-w-xl bg-[#0d1117] border border-[#1f2937] rounded-xl shadow-2xl overflow-hidden">
        <!-- Search input -->
        <div class="flex items-center gap-3 px-4 py-3 border-b border-[#1f2937]">
          <svg class="w-4 h-4 text-gray-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
          </svg>
          <input
            ref="inputRef"
            v-model="q"
            type="text"
            placeholder="Search countries, stocks, commodities…"
            class="flex-1 bg-transparent text-white placeholder-gray-600 text-sm outline-none"
            autocomplete="off"
            spellcheck="false"
            @input="onInput"
            @keydown.escape="$emit('update:modelValue', false)"
            @keydown.down.prevent="moveFocus(1)"
            @keydown.up.prevent="moveFocus(-1)"
            @keydown.enter.prevent="selectFocused"
          />
          <kbd class="text-[10px] text-gray-600 border border-[#374151] rounded px-1.5 py-0.5 font-mono">ESC</kbd>
        </div>

        <!-- Results -->
        <div class="max-h-[420px] overflow-y-auto">
          <!-- Loading -->
          <div v-if="loading" class="px-4 py-6 text-center text-xs text-gray-600">Searching…</div>

          <!-- No results -->
          <div v-else-if="q.length >= 2 && !loading && !hasResults" class="px-4 py-6 text-center text-xs text-gray-600">
            No results for "{{ q }}"
          </div>

          <!-- Countries -->
          <template v-if="results.countries?.length">
            <div class="px-4 pt-3 pb-1 text-[10px] font-semibold text-gray-600 uppercase tracking-widest">Countries</div>
            <NuxtLink
              v-for="(item, i) in results.countries"
              :key="'c-' + item.code"
              :to="`/countries/${item.code.toLowerCase()}`"
              :class="['flex items-center gap-3 px-4 py-2.5 hover:bg-[#111827] transition-colors text-sm', focusIndex === i ? 'bg-[#111827]' : '']"
              @click="$emit('update:modelValue', false)"
            >
              <span class="text-xl w-7 text-center">{{ item.flag }}</span>
              <span class="text-white font-medium">{{ item.name }}</span>
              <span class="ml-auto text-xs text-gray-600">{{ item.code }}</span>
            </NuxtLink>
          </template>

          <!-- Assets -->
          <template v-if="results.assets?.length">
            <div class="px-4 pt-3 pb-1 text-[10px] font-semibold text-gray-600 uppercase tracking-widest">Assets</div>
            <NuxtLink
              v-for="(item, i) in results.assets"
              :key="'a-' + item.symbol"
              :to="assetPath(item)"
              :class="['flex items-center gap-3 px-4 py-2.5 hover:bg-[#111827] transition-colors text-sm', focusIndex === countryCount + i ? 'bg-[#111827]' : '']"
              @click="$emit('update:modelValue', false)"
            >
              <span class="text-xs font-bold text-emerald-400 w-12 truncate">{{ item.symbol }}</span>
              <span class="text-white">{{ item.name }}</span>
              <span class="ml-auto text-xs text-gray-600 capitalize">{{ item.asset_type }}</span>
            </NuxtLink>
          </template>

          <!-- Empty hint (no query) -->
          <div v-if="!q" class="px-4 py-5 text-xs text-gray-700 text-center">
            Type to search countries, stocks, crypto, commodities
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const { $apiFetch } = useNuxtApp()
const inputRef = ref<HTMLInputElement | null>(null)
const q = ref('')
const loading = ref(false)
const focusIndex = ref(-1)
const results = ref<{ countries?: any[]; assets?: any[] }>({})

let debounceTimer: ReturnType<typeof setTimeout> | null = null

const countryCount = computed(() => results.value.countries?.length ?? 0)
const hasResults = computed(() => countryCount.value > 0 || (results.value.assets?.length ?? 0) > 0)

watch(() => props.modelValue, (open) => {
  if (open) {
    nextTick(() => inputRef.value?.focus())
    q.value = ''
    results.value = {}
    focusIndex.value = -1
  }
})

function onInput() {
  focusIndex.value = -1
  if (debounceTimer) clearTimeout(debounceTimer)
  if (q.value.length < 2) {
    results.value = {}
    return
  }
  debounceTimer = setTimeout(doSearch, 280)
}

async function doSearch() {
  loading.value = true
  try {
    const data = await $apiFetch(`/api/search?q=${encodeURIComponent(q.value)}`)
    results.value = data as { countries?: any[]; assets?: any[] }
  } catch {
    results.value = {}
  } finally {
    loading.value = false
  }
}

function moveFocus(dir: number) {
  const total = countryCount.value + (results.value.assets?.length ?? 0)
  if (!total) return
  focusIndex.value = (focusIndex.value + dir + total) % total
}

function selectFocused() {
  // Navigate to focused item on enter — let browser handle NuxtLink
  const el = document.querySelector<HTMLAnchorElement>('.bg-\\[\\#111827\\] a, a.bg-\\[\\#111827\\]')
  if (el) { el.click(); return }
  emit('update:modelValue', false)
}

function assetPath(item: any): string {
  if (item.asset_type === 'stock') return `/stocks/${item.symbol.toLowerCase()}`
  if (item.asset_type === 'commodity') return `/commodities/${item.symbol.toLowerCase()}`
  if (item.asset_type === 'crypto') return `/crypto/${item.symbol.toLowerCase()}`
  return `/markets`
}
</script>
