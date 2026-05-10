<template>
  <main class="max-w-3xl mx-auto px-4 py-10">
    <NuxtLink to="/tools/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-6 inline-flex items-center gap-1">
      ← Tools
    </NuxtLink>

    <div class="mb-8">
      <h1 class="text-2xl sm:text-3xl font-extrabold text-white">FX Calculator</h1>
      <p class="text-gray-400 text-sm mt-2">Convert any currency using live exchange rates.</p>
    </div>

    <!-- Converter -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6 mb-6">
      <!-- Amount input -->
      <div class="mb-4">
        <label class="text-xs text-gray-500 mb-2 block uppercase tracking-wider">Amount</label>
        <input
          v-model.number="amount"
          type="number"
          min="0"
          step="any"
          class="w-full bg-[#0d1117] border border-[#1f2937] rounded-xl px-4 py-3 text-xl font-bold text-white placeholder-gray-700 focus:outline-none focus:border-emerald-500 transition-colors tabular-nums"
          placeholder="1"
          @input="compute"
        />
      </div>

      <!-- From / To row -->
      <div class="flex items-center gap-3">
        <div class="flex-1">
          <label class="text-xs text-gray-500 mb-2 block uppercase tracking-wider">From</label>
          <select
            v-model="fromCurrency"
            class="w-full bg-[#0d1117] border border-[#1f2937] rounded-xl px-4 py-3 text-sm font-semibold text-white focus:outline-none focus:border-emerald-500 transition-colors appearance-none cursor-pointer"
            @change="compute"
          >
            <optgroup label="Popular">
              <option v-for="c in popularCurrencies" :key="c.code" :value="c.code">
                {{ c.code }} — {{ c.name }}
              </option>
            </optgroup>
            <optgroup label="All currencies">
              <option v-for="c in otherCurrencies" :key="c.code" :value="c.code">
                {{ c.code }} — {{ c.name }}
              </option>
            </optgroup>
          </select>
        </div>

        <!-- Swap button -->
        <button
          class="mt-6 w-10 h-10 rounded-full border border-[#1f2937] bg-[#1a2235] hover:border-emerald-600 hover:text-emerald-400 text-gray-400 transition-colors flex items-center justify-center shrink-0 text-lg"
          title="Swap currencies"
          @click="swap"
        >⇄</button>

        <div class="flex-1">
          <label class="text-xs text-gray-500 mb-2 block uppercase tracking-wider">To</label>
          <select
            v-model="toCurrency"
            class="w-full bg-[#0d1117] border border-[#1f2937] rounded-xl px-4 py-3 text-sm font-semibold text-white focus:outline-none focus:border-emerald-500 transition-colors appearance-none cursor-pointer"
            @change="compute"
          >
            <optgroup label="Popular">
              <option v-for="c in popularCurrencies" :key="c.code" :value="c.code">
                {{ c.code }} — {{ c.name }}
              </option>
            </optgroup>
            <optgroup label="All currencies">
              <option v-for="c in otherCurrencies" :key="c.code" :value="c.code">
                {{ c.code }} — {{ c.name }}
              </option>
            </optgroup>
          </select>
        </div>
      </div>

      <!-- Result -->
      <div class="mt-6 p-4 bg-[#0d1117] rounded-xl border border-[#1f2937]">
        <div v-if="pending" class="text-gray-600 text-sm">Loading rates…</div>
        <div v-else-if="result !== null">
          <div class="text-3xl font-extrabold text-white tabular-nums mb-1">
            <span class="text-gray-500">{{ fmtAmount(amount) }} {{ fromCurrency }}</span>
            <span class="text-gray-600 mx-2">=</span>
            <span class="text-emerald-400">{{ fmtAmount(result) }} {{ toCurrency }}</span>
          </div>
          <div class="text-xs text-gray-600 mt-2">
            1 {{ fromCurrency }} = {{ fmtRate(crossRate) }} {{ toCurrency }}
            <span class="mx-2">·</span>
            1 {{ toCurrency }} = {{ fmtRate(1 / crossRate) }} {{ fromCurrency }}
          </div>
        </div>
        <div v-else class="text-gray-600 text-sm">Rate unavailable for this pair.</div>
      </div>

      <p v-if="updatedAt" class="text-[10px] text-gray-700 mt-3 text-right">
        Rates updated {{ updatedAt }}
      </p>
    </div>

    <!-- Cross rates table -->
    <div v-if="rates && fromCurrency" class="bg-[#111827] border border-[#1f2937] rounded-2xl p-6 mb-6">
      <h2 class="text-sm font-bold text-white mb-4">{{ amount || 1 }} {{ fromCurrency }} in major currencies</h2>
      <div class="divide-y divide-[#1f2937]">
        <div
          v-for="c in majorCurrenciesFor"
          :key="c.code"
          class="flex items-center justify-between py-3 text-sm cursor-pointer hover:bg-[#1a2235] -mx-2 px-2 rounded-lg transition-colors"
          @click="toCurrency = c.code; compute()"
        >
          <div class="flex items-center gap-2">
            <span class="text-base">{{ c.flag }}</span>
            <span class="text-gray-300 font-medium">{{ c.code }}</span>
            <span class="text-gray-600 text-xs">{{ c.name }}</span>
          </div>
          <span class="tabular-nums font-semibold text-white">{{ fmtAmount(convertTo(amount || 1, c.code)) }}</span>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
const { get } = useApi()
const { fmtPrice } = useCurrency()

const POPULAR = ['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'CHF', 'AUD', 'CAD']

const ALL_CURRENCIES: { code: string; name: string; flag: string }[] = [
  { code: 'USD', name: 'US Dollar',           flag: '🇺🇸' },
  { code: 'EUR', name: 'Euro',                flag: '🇪🇺' },
  { code: 'GBP', name: 'British Pound',       flag: '🇬🇧' },
  { code: 'JPY', name: 'Japanese Yen',        flag: '🇯🇵' },
  { code: 'CNY', name: 'Chinese Yuan',        flag: '🇨🇳' },
  { code: 'CHF', name: 'Swiss Franc',         flag: '🇨🇭' },
  { code: 'AUD', name: 'Australian Dollar',   flag: '🇦🇺' },
  { code: 'CAD', name: 'Canadian Dollar',     flag: '🇨🇦' },
  { code: 'HKD', name: 'Hong Kong Dollar',    flag: '🇭🇰' },
  { code: 'SGD', name: 'Singapore Dollar',    flag: '🇸🇬' },
  { code: 'KRW', name: 'Korean Won',          flag: '🇰🇷' },
  { code: 'INR', name: 'Indian Rupee',        flag: '🇮🇳' },
  { code: 'BRL', name: 'Brazilian Real',      flag: '🇧🇷' },
  { code: 'MXN', name: 'Mexican Peso',        flag: '🇲🇽' },
  { code: 'ZAR', name: 'South African Rand',  flag: '🇿🇦' },
  { code: 'SEK', name: 'Swedish Krona',       flag: '🇸🇪' },
  { code: 'NOK', name: 'Norwegian Krone',     flag: '🇳🇴' },
  { code: 'DKK', name: 'Danish Krone',        flag: '🇩🇰' },
  { code: 'NZD', name: 'New Zealand Dollar',  flag: '🇳🇿' },
  { code: 'TRY', name: 'Turkish Lira',        flag: '🇹🇷' },
  { code: 'RUB', name: 'Russian Ruble',       flag: '🇷🇺' },
  { code: 'SAR', name: 'Saudi Riyal',         flag: '🇸🇦' },
  { code: 'AED', name: 'UAE Dirham',          flag: '🇦🇪' },
  { code: 'PLN', name: 'Polish Zloty',        flag: '🇵🇱' },
  { code: 'THB', name: 'Thai Baht',           flag: '🇹🇭' },
  { code: 'IDR', name: 'Indonesian Rupiah',   flag: '🇮🇩' },
  { code: 'MYR', name: 'Malaysian Ringgit',   flag: '🇲🇾' },
  { code: 'TWD', name: 'Taiwan Dollar',       flag: '🇹🇼' },
  { code: 'NGN', name: 'Nigerian Naira',      flag: '🇳🇬' },
  { code: 'EGP', name: 'Egyptian Pound',      flag: '🇪🇬' },
  { code: 'CZK', name: 'Czech Koruna',        flag: '🇨🇿' },
  { code: 'HUF', name: 'Hungarian Forint',    flag: '🇭🇺' },
  { code: 'ILS', name: 'Israeli Shekel',      flag: '🇮🇱' },
  { code: 'PKR', name: 'Pakistani Rupee',     flag: '🇵🇰' },
  { code: 'VND', name: 'Vietnamese Dong',     flag: '🇻🇳' },
  { code: 'CLP', name: 'Chilean Peso',        flag: '🇨🇱' },
  { code: 'COP', name: 'Colombian Peso',      flag: '🇨🇴' },
  { code: 'PEN', name: 'Peruvian Sol',        flag: '🇵🇪' },
  { code: 'ARS', name: 'Argentine Peso',      flag: '🇦🇷' },
  { code: 'BDT', name: 'Bangladeshi Taka',    flag: '🇧🇩' },
  { code: 'LKR', name: 'Sri Lankan Rupee',    flag: '🇱🇰' },
  { code: 'MAD', name: 'Moroccan Dirham',     flag: '🇲🇦' },
  { code: 'QAR', name: 'Qatari Riyal',        flag: '🇶🇦' },
  { code: 'KWD', name: 'Kuwaiti Dinar',       flag: '🇰🇼' },
]

const route = useRoute()
const fromCurrency = ref((route.query.from as string) || 'USD')
const toCurrency = ref((route.query.to as string) || 'EUR')
const amount = ref<number>(Number(route.query.amount) || 1)
const rates = ref<Record<string, number> | null>(null)
const result = ref<number | null>(null)
const crossRate = ref(1)
const updatedAt = ref('')

const { pending } = useAsyncData('fx-rates', async () => {
  const data = await get<{ rates: Record<string, number> }>('/api/assets/fx-rates').catch(() => null)
  if (data?.rates) {
    rates.value = data.rates
    updatedAt.value = new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) + ' UTC'
    compute()
  }
  return data
}, { server: false })

const popularCurrencies = computed(() =>
  ALL_CURRENCIES.filter(c => POPULAR.includes(c.code))
)

const otherCurrencies = computed(() => {
  if (!rates.value) return ALL_CURRENCIES.filter(c => !POPULAR.includes(c.code))
  const available = new Set(Object.keys(rates.value))
  return ALL_CURRENCIES.filter(c => !POPULAR.includes(c.code) && available.has(c.code))
})

const majorCurrenciesFor = computed(() => {
  const MAJORS = ['USD', 'EUR', 'GBP', 'JPY', 'CNY', 'CHF', 'AUD', 'CAD', 'HKD', 'SGD', 'INR', 'BRL']
  return ALL_CURRENCIES.filter(c => MAJORS.includes(c.code) && c.code !== fromCurrency.value)
})

function getUsdRate(currency: string): number | null {
  if (!rates.value) return null
  return rates.value[currency] ?? null
}

function convertTo(amt: number, to: string): number | null {
  const fromRate = getUsdRate(fromCurrency.value)
  const toRate = getUsdRate(to)
  if (fromRate == null || toRate == null) return null
  return (amt / fromRate) * toRate
}

function compute() {
  const v = convertTo(amount.value || 1, toCurrency.value)
  result.value = v
  if (v !== null) {
    const fromRate = getUsdRate(fromCurrency.value) ?? 1
    const toRate = getUsdRate(toCurrency.value) ?? 1
    crossRate.value = toRate / fromRate
  }
}

function swap() {
  const tmp = fromCurrency.value
  fromCurrency.value = toCurrency.value
  toCurrency.value = tmp
  compute()
}

function fmtAmount(v: number | null): string {
  if (v == null) return '—'
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1) return v.toFixed(4).replace(/\.?0+$/, '')
  return v.toFixed(6)
}

function fmtRate(v: number): string {
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1) return v.toFixed(4)
  return v.toFixed(6)
}

useSeoMeta({
  title: 'FX Currency Calculator — Live Rates | MetricsHour',
  description: 'Convert any currency using live exchange rates. Supports 40+ world currencies. Free FX calculator from MetricsHour.',
  ogTitle: 'FX Currency Calculator — MetricsHour',
  ogDescription: 'Live currency converter. Convert between USD, EUR, GBP, JPY, CNY, and 40+ other currencies.',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/tools/fx-calculator' }],
})
</script>
