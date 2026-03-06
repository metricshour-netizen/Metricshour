<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="modelValue" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4" @click.self="$emit('update:modelValue', false)">
        <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="$emit('update:modelValue', false)" />
        <div class="relative w-full max-w-sm bg-[#111827] border border-[#1f2937] rounded-2xl shadow-2xl z-10 p-6">
          <!-- Header -->
          <div class="flex items-center justify-between mb-5">
            <div>
              <h2 class="text-base font-bold text-white">Set Price Alert</h2>
              <p class="text-xs text-gray-500 mt-0.5">{{ asset?.symbol }} · {{ asset?.name }}</p>
            </div>
            <button @click="$emit('update:modelValue', false)" class="text-gray-600 hover:text-gray-300 transition-colors text-xl leading-none">✕</button>
          </div>

          <!-- Current price -->
          <div v-if="currentPrice" class="bg-[#0d1117] border border-[#1f2937] rounded-lg px-4 py-3 mb-5 flex items-center justify-between">
            <span class="text-xs text-gray-500">Current price</span>
            <span class="font-mono font-bold text-white">${{ fmtPrice(currentPrice) }}</span>
          </div>

          <!-- Form -->
          <div class="space-y-4">
            <!-- Condition toggle -->
            <div>
              <label class="text-xs text-gray-500 mb-2 block">Alert when price goes</label>
              <div class="grid grid-cols-2 gap-2">
                <button
                  @click="condition = 'above'"
                  class="py-2.5 rounded-lg text-sm font-semibold border transition-all"
                  :class="condition === 'above'
                    ? 'bg-emerald-500/10 border-emerald-500 text-emerald-400'
                    : 'border-[#1f2937] text-gray-500 hover:border-gray-500'"
                >↑ Above</button>
                <button
                  @click="condition = 'below'"
                  class="py-2.5 rounded-lg text-sm font-semibold border transition-all"
                  :class="condition === 'below'
                    ? 'bg-red-500/10 border-red-500 text-red-400'
                    : 'border-[#1f2937] text-gray-500 hover:border-gray-500'"
                >↓ Below</button>
              </div>
            </div>

            <!-- Price input -->
            <div>
              <label class="text-xs text-gray-500 mb-2 block">Target price (USD)</label>
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 font-bold">$</span>
                <input
                  v-model="targetPrice"
                  type="number"
                  step="0.01"
                  min="0"
                  placeholder="0.00"
                  class="w-full bg-[#0d1117] border border-[#1f2937] rounded-lg pl-7 pr-4 py-3 text-white font-mono font-bold text-sm focus:outline-none focus:border-emerald-500 transition-colors"
                />
              </div>
              <!-- Quick buttons -->
              <div v-if="currentPrice" class="flex gap-1.5 mt-2 flex-wrap">
                <button
                  v-for="pct in quickPcts"
                  :key="pct"
                  @click="applyQuickPct(pct)"
                  class="text-[10px] px-2 py-1 rounded border border-[#1f2937] text-gray-600 hover:border-gray-500 hover:text-gray-400 transition-colors font-mono"
                >{{ pct > 0 ? '+' : '' }}{{ pct }}%</button>
              </div>
            </div>

            <!-- Channels -->
            <div class="bg-[#0d1117] border border-[#1f2937] rounded-lg p-3 space-y-2.5">
              <p class="text-xs text-gray-500 font-medium">Notify via</p>
              <label class="flex items-center gap-3 cursor-pointer group">
                <div class="relative">
                  <input type="checkbox" v-model="notifyEmail" class="sr-only" />
                  <div class="w-9 h-5 rounded-full transition-colors" :class="notifyEmail ? 'bg-emerald-600' : 'bg-[#1f2937]'">
                    <div class="w-4 h-4 bg-white rounded-full absolute top-0.5 transition-transform" :class="notifyEmail ? 'translate-x-4' : 'translate-x-0.5'" />
                  </div>
                </div>
                <span class="text-sm text-gray-300">Email</span>
                <span class="text-xs text-gray-600 ml-auto">{{ userEmail }}</span>
              </label>
              <label class="flex items-center gap-3 cursor-pointer group">
                <div class="relative">
                  <input type="checkbox" v-model="notifyTelegram" class="sr-only" />
                  <div class="w-9 h-5 rounded-full transition-colors" :class="notifyTelegram ? 'bg-emerald-600' : 'bg-[#1f2937]'">
                    <div class="w-4 h-4 bg-white rounded-full absolute top-0.5 transition-transform" :class="notifyTelegram ? 'translate-x-4' : 'translate-x-0.5'" />
                  </div>
                </div>
                <span class="text-sm text-gray-300">Telegram</span>
                <span v-if="telegramConnected" class="text-[10px] text-emerald-600 ml-auto">Connected ✓</span>
                <NuxtLink v-else to="/alerts" @click="$emit('update:modelValue', false)" class="text-[10px] text-amber-500 hover:text-amber-400 ml-auto transition-colors">Connect →</NuxtLink>
              </label>
            </div>

            <!-- Error -->
            <p v-if="error" class="text-xs text-red-400">{{ error }}</p>

            <!-- Submit -->
            <button
              @click="submit"
              :disabled="loading || !targetPrice"
              class="w-full py-3 rounded-xl font-bold text-sm transition-all"
              :class="loading || !targetPrice
                ? 'bg-[#1f2937] text-gray-600 cursor-not-allowed'
                : 'bg-emerald-500 hover:bg-emerald-400 text-black'"
            >
              {{ loading ? 'Setting alert…' : 'Set Alert' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue: boolean
  asset: { id: number; symbol: string; name: string } | null
  currentPrice?: number | null
}>()
const emit = defineEmits(['update:modelValue', 'created'])

const { post, get } = useApi()
const { user } = useAuth()

const condition = ref<'above' | 'below'>('above')
const targetPrice = ref<number | ''>('')
const notifyEmail = ref(true)
const notifyTelegram = ref(false)
const telegramConnected = ref(false)
const loading = ref(false)
const error = ref('')

const userEmail = computed(() => user.value?.email || '')
const quickPcts = computed(() =>
  condition.value === 'above' ? [5, 10, 20] : [-5, -10, -20]
)

function fmtPrice(v: number): string {
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (v >= 1) return v.toFixed(2)
  return v.toFixed(4)
}

function applyQuickPct(pct: number) {
  if (!props.currentPrice) return
  targetPrice.value = parseFloat((props.currentPrice * (1 + pct / 100)).toFixed(4))
}

// Load notification prefs when modal opens
watch(() => props.modelValue, async (open) => {
  if (!open) return
  error.value = ''
  targetPrice.value = ''
  condition.value = 'above'
  try {
    const prefs = await get<any>('/api/alerts/prefs')
    notifyEmail.value = prefs.notify_email
    notifyTelegram.value = prefs.notify_telegram
    telegramConnected.value = prefs.telegram_connected
  } catch { /* not logged in — will fail at submit */ }
})

async function submit() {
  if (!props.asset || !targetPrice.value) return
  error.value = ''
  loading.value = true
  try {
    const alert = await post('/api/alerts', {
      asset_id: props.asset.id,
      condition: condition.value,
      target_price: Number(targetPrice.value),
    })
    // Update prefs in background
    post('/api/alerts/prefs', { notify_telegram: notifyTelegram.value, notify_email: notifyEmail.value }).catch(() => {})
    emit('created', alert)
    emit('update:modelValue', false)
  } catch (e: any) {
    error.value = e?.data?.detail || e?.message || 'Failed to create alert'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
