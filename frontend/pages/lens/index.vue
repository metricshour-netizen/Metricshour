<template>
  <main class="max-w-4xl mx-auto px-4 py-10">
    <!-- Header -->
    <div class="mb-8 text-center">
      <div class="text-4xl mb-3">🔭</div>
      <h1 class="text-2xl sm:text-3xl font-extrabold text-white mb-2">{{ $t('lens.title') }}</h1>
      <p class="text-gray-400 text-sm max-w-lg mx-auto">{{ $t('lens.subtitle') }}</p>
    </div>

    <!-- Asset type tabs -->
    <div class="flex gap-1.5 mb-6 justify-center flex-wrap">
      <button v-for="tab in TABS" :key="tab.key"
        @click="activeTab = tab.key"
        class="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold border transition-all"
        :class="activeTab === tab.key
          ? 'bg-emerald-600 border-emerald-500 text-white'
          : 'bg-[#111827] border-[#1f2937] text-gray-400 hover:text-white hover:border-gray-600'">
        {{ tab.label }}
        <span v-if="tab.soon" class="text-[9px] bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded-full">{{ $t('lens.comingSoon') }}</span>
      </button>
    </div>

    <!-- Stocks input -->
    <div v-if="activeTab === 'stocks'" class="max-w-lg mx-auto">
      <div class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6">
        <div class="text-xs text-emerald-500 font-bold uppercase tracking-widest mb-4">Pre-Trade Analysis · Stocks</div>

        <div class="mb-4 relative" ref="stockDropdownRef">
          <label class="text-xs text-gray-500 mb-1.5 block">Company name or ticker</label>
          <input
            v-model="stockInput"
            @input="onStockInput"
            @keydown.enter="pickFirstOrAnalyze"
            @keydown.escape="closeStockDropdown"
            @focus="onStockFocus"
            type="text"
            placeholder="Apple, NVDA, Microsoft..."
            class="w-full bg-[#0d1520] border border-[#1f2937] rounded-xl px-4 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-700 font-mono uppercase tracking-wider"
            autocomplete="off"
          />
          <!-- Autocomplete dropdown -->
          <div v-if="showStockDropdown && stockSuggestions.length"
            class="absolute left-0 right-0 top-full mt-1 bg-[#0d1520] border border-[#1f2937] rounded-xl overflow-hidden z-50 shadow-xl">
            <button
              v-for="s in stockSuggestions" :key="s.symbol"
              @click="selectStock(s)"
              class="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-[#111827] transition-colors text-left">
              <span class="font-mono font-bold text-emerald-400 text-sm w-16 shrink-0">{{ s.symbol }}</span>
              <span class="text-gray-300 text-sm truncate">{{ s.name }}</span>
              <span v-if="s.sector" class="text-gray-600 text-xs ml-auto shrink-0">{{ s.sector }}</span>
            </button>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label class="text-xs text-gray-500 mb-1.5 block">{{ $t('lens.inputs.sizePlaceholder') }}</label>
            <input
              v-model.number="sizeInput"
              type="number"
              placeholder="10000"
              class="w-full bg-[#0d1520] border border-[#1f2937] rounded-xl px-4 py-3 text-white text-sm placeholder-gray-700 focus:outline-none focus:border-emerald-700"
            />
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1.5 block">Direction</label>
            <div class="flex gap-2">
              <button @click="direction = 'long'"
                class="flex-1 py-3 rounded-xl text-sm font-semibold border transition-all"
                :class="direction === 'long' ? 'bg-emerald-900 border-emerald-700 text-emerald-300' : 'bg-[#0d1520] border-[#1f2937] text-gray-500'">
                {{ $t('lens.direction.long') }}
              </button>
              <button @click="direction = 'short'"
                class="flex-1 py-3 rounded-xl text-sm font-semibold border transition-all"
                :class="direction === 'short' ? 'bg-red-900 border-red-700 text-red-300' : 'bg-[#0d1520] border-[#1f2937] text-gray-500'">
                {{ $t('lens.direction.short') }}
              </button>
            </div>
          </div>
        </div>

        <button @click="analyzeStock" :disabled="!stockInput.trim()"
          class="w-full py-3 rounded-xl text-sm font-bold transition-all"
          :class="stockInput.trim() ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-[#1f2937] text-gray-600 cursor-not-allowed'">
          {{ $t('lens.inputs.analyze') }}
        </button>
      </div>

      <!-- Mode cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
        <div class="bg-[#0d1520] border border-emerald-900/50 rounded-xl p-4">
          <div class="text-xs text-emerald-500 font-bold uppercase tracking-wider mb-1">● {{ $t('lens.modes.preTrade') }}</div>
          <p class="text-xs text-gray-400">{{ $t('lens.modes.preTradeDesc') }}</p>
        </div>
        <div class="bg-[#0a0e1a] border border-[#1f2937] rounded-xl p-4 opacity-50">
          <div class="text-xs text-gray-600 font-bold uppercase tracking-wider mb-1">○ {{ $t('lens.modes.postTrade') }} · {{ $t('lens.modes.postTradeSoon') }}</div>
          <p class="text-xs text-gray-600">{{ $t('lens.modes.postTradeDesc') }}</p>
        </div>
      </div>
    </div>

    <!-- Forex input -->
    <div v-else-if="activeTab === 'forex'" class="max-w-lg mx-auto">
      <div class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6">
        <div class="text-xs text-emerald-500 font-bold uppercase tracking-widest mb-4">Pre-Trade Analysis · Forex</div>

        <div class="mb-4">
          <label class="text-xs text-gray-500 mb-1.5 block">Currency pair</label>
          <input
            v-model="forexInput"
            @keydown.enter="analyzeForex"
            type="text"
            :placeholder="$t('lens.inputs.forexPlaceholder')"
            class="w-full bg-[#0d1520] border border-[#1f2937] rounded-xl px-4 py-3 text-white text-sm placeholder-gray-700 focus:outline-none focus:border-emerald-700 font-mono uppercase tracking-wider"
            autocomplete="off"
          />
        </div>

        <div class="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label class="text-xs text-gray-500 mb-1.5 block">{{ $t('lens.inputs.sizePlaceholder') }}</label>
            <input
              v-model.number="sizeInput"
              type="number"
              placeholder="10000"
              class="w-full bg-[#0d1520] border border-[#1f2937] rounded-xl px-4 py-3 text-white text-sm placeholder-gray-700 focus:outline-none focus:border-emerald-700"
            />
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1.5 block">Direction</label>
            <div class="flex gap-2">
              <button @click="direction = 'long'"
                class="flex-1 py-3 rounded-xl text-sm font-semibold border transition-all"
                :class="direction === 'long' ? 'bg-emerald-900 border-emerald-700 text-emerald-300' : 'bg-[#0d1520] border-[#1f2937] text-gray-500'">
                {{ $t('lens.direction.long') }}
              </button>
              <button @click="direction = 'short'"
                class="flex-1 py-3 rounded-xl text-sm font-semibold border transition-all"
                :class="direction === 'short' ? 'bg-red-900 border-red-700 text-red-300' : 'bg-[#0d1520] border-[#1f2937] text-gray-500'">
                {{ $t('lens.direction.short') }}
              </button>
            </div>
          </div>
        </div>

        <button @click="analyzeForex" :disabled="!forexInput.trim()"
          class="w-full py-3 rounded-xl text-sm font-bold transition-all"
          :class="forexInput.trim() ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-[#1f2937] text-gray-600 cursor-not-allowed'">
          {{ $t('lens.inputs.analyze') }}
        </button>
      </div>
    </div>

    <!-- Coming soon tabs -->
    <div v-else class="max-w-lg mx-auto">
      <LensComingSoon
        :asset-type="activeTab"
        @analyze-stock="activeTab = 'stocks'"
        @analyze-forex="activeTab = 'forex'"
      />
    </div>
  </main>
</template>

<script setup lang="ts">
const { t } = useI18n()
const router = useRouter()
const { get } = useApi()

const TABS = [
  { key: 'stocks',      label: t('lens.tabs.stocks'),      soon: false },
  { key: 'forex',       label: t('lens.tabs.forex'),        soon: false },
  { key: 'crypto',      label: t('lens.tabs.crypto'),       soon: true  },
  { key: 'commodities', label: t('lens.tabs.commodities'),  soon: true  },
]

const activeTab  = ref<string>('stocks')
const stockInput = ref('')
const forexInput = ref('')
const sizeInput  = ref<number | null>(null)
const direction  = ref<'long' | 'short'>('long')

// Stock search autocomplete
const stockSuggestions = ref<Array<{symbol: string; name: string; sector: string | null}>>([])
const showStockDropdown = ref(false)
const stockDropdownRef = ref<HTMLElement | null>(null)
let _searchTimer: ReturnType<typeof setTimeout> | null = null
let _selectedTicker = ref('')  // track when user picked from dropdown

function onStockInput() {
  _selectedTicker.value = ''
  const q = stockInput.value.trim()
  if (q.length < 2) {
    stockSuggestions.value = []
    showStockDropdown.value = false
    return
  }
  if (_searchTimer) clearTimeout(_searchTimer)
  _searchTimer = setTimeout(async () => {
    try {
      const res = await get(`/search?q=${encodeURIComponent(q)}`)
      const assets = (res?.assets || []).filter((a: any) => a.asset_type === 'stock').slice(0, 6)
      stockSuggestions.value = assets
      showStockDropdown.value = assets.length > 0
    } catch {
      stockSuggestions.value = []
      showStockDropdown.value = false
    }
  }, 220)
}

function selectStock(s: {symbol: string; name: string}) {
  _selectedTicker.value = s.symbol
  stockInput.value = s.symbol
  showStockDropdown.value = false
  stockSuggestions.value = []
}

function closeStockDropdown() {
  showStockDropdown.value = false
}

function pickFirstOrAnalyze() {
  if (showStockDropdown.value && stockSuggestions.value.length) {
    selectStock(stockSuggestions.value[0])
  } else {
    analyzeStock()
  }
}

function onStockFocus() {
  if (stockSuggestions.value.length) showStockDropdown.value = true
}

// Close dropdown on outside click
onMounted(() => {
  document.addEventListener('click', (e) => {
    if (stockDropdownRef.value && !stockDropdownRef.value.contains(e.target as Node)) {
      showStockDropdown.value = false
    }
  })
})

function analyzeStock() {
  const ticker = (_selectedTicker.value || stockInput.value).trim().toUpperCase()
  if (!ticker) return
  showStockDropdown.value = false
  const params: Record<string, string> = { direction: direction.value }
  if (sizeInput.value) params.size = String(sizeInput.value)
  router.push({ path: `/lens/stocks/${ticker.toLowerCase()}`, query: params })
}

function analyzeForex() {
  const pair = forexInput.value.trim().toUpperCase()
  if (!pair) return
  const params: Record<string, string> = { direction: direction.value }
  if (sizeInput.value) params.size = String(sizeInput.value)
  router.push({ path: `/lens/forex/${pair.toLowerCase()}`, query: params })
}

useSeoMeta({
  title: `${t('lens.title')} — Pre-Trade Analysis — MetricsHour`,
  description: t('lens.subtitle'),
  robots: 'index, follow',
})
useHead({ link: [{ rel: 'canonical', href: 'https://metricshour.com/lens/' }] })
</script>
