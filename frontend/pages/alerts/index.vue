<template>
  <main class="max-w-2xl mx-auto px-4 py-10">
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white">Price Alerts</h1>
      <p class="text-gray-500 text-sm mt-1">Instant notifications when assets hit your targets</p>
    </div>

    <!-- Not logged in -->
    <div v-if="!isLoggedIn" class="bg-[#111827] border border-[#1f2937] rounded-xl p-8 text-center">
      <div class="text-4xl mb-3">🔔</div>
      <p class="text-white font-semibold mb-1">Sign in to manage alerts</p>
      <p class="text-gray-500 text-sm mb-4">Create an account to get Telegram + email alerts when prices move.</p>
      <button @click="showAuth = true" class="bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm px-6 py-2.5 rounded-lg transition-colors">Sign In / Register</button>
    </div>

    <template v-else>
      <!-- Notification prefs -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6">
        <h2 class="text-sm font-bold text-white mb-4">Notification Channels</h2>
        <div class="space-y-4">
          <!-- Email -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 bg-[#1f2937] rounded-lg flex items-center justify-center text-base">✉️</div>
              <div>
                <div class="text-sm text-white font-medium">Email</div>
                <div class="text-xs text-gray-500">{{ user?.email }}</div>
              </div>
            </div>
            <label class="relative cursor-pointer">
              <input type="checkbox" v-model="prefs.notify_email" @change="savePrefs" class="sr-only" />
              <div class="w-11 h-6 rounded-full transition-colors" :class="prefs.notify_email ? 'bg-emerald-600' : 'bg-[#1f2937]'">
                <div class="w-5 h-5 bg-white rounded-full absolute top-0.5 transition-transform shadow-sm" :class="prefs.notify_email ? 'translate-x-5' : 'translate-x-0.5'" />
              </div>
            </label>
          </div>

          <!-- Telegram -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 bg-[#1f2937] rounded-lg flex items-center justify-center text-base">✈️</div>
              <div>
                <div class="text-sm text-white font-medium">Telegram</div>
                <div class="text-xs" :class="prefs.telegram_connected ? 'text-emerald-500' : 'text-gray-500'">
                  {{ prefs.telegram_connected ? 'Connected' : 'Not connected' }}
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <label v-if="prefs.telegram_connected" class="relative cursor-pointer">
                <input type="checkbox" v-model="prefs.notify_telegram" @change="savePrefs" class="sr-only" />
                <div class="w-11 h-6 rounded-full transition-colors" :class="prefs.notify_telegram ? 'bg-emerald-600' : 'bg-[#1f2937]'">
                  <div class="w-5 h-5 bg-white rounded-full absolute top-0.5 transition-transform shadow-sm" :class="prefs.notify_telegram ? 'translate-x-5' : 'translate-x-0.5'" />
                </div>
              </label>
              <button
                v-if="!prefs.telegram_connected"
                @click="generateCode"
                :disabled="codeLoading"
                class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-[#0088cc]/10 border border-[#0088cc]/30 text-[#29a8eb] hover:bg-[#0088cc]/20 transition-colors"
              >{{ codeLoading ? '…' : 'Connect Telegram' }}</button>
              <button
                v-else
                @click="disconnectTelegram"
                class="text-xs text-gray-600 hover:text-red-400 transition-colors"
              >Disconnect</button>
            </div>
          </div>

          <!-- Telegram connect instructions -->
          <div v-if="linkCode" class="bg-[#0088cc]/5 border border-[#0088cc]/20 rounded-lg p-4">
            <p class="text-xs text-gray-400 mb-3">
              1. Open Telegram and start a chat with
              <a :href="`https://t.me/${botUsername}`" target="_blank" rel="noopener" class="text-[#29a8eb] font-semibold">@{{ botUsername }}</a>
            </p>
            <p class="text-xs text-gray-400 mb-3">2. Send this code to the bot:</p>
            <div class="flex items-center gap-3">
              <code class="font-mono font-bold text-xl tracking-[0.3em] text-white bg-[#0d1117] border border-[#1f2937] rounded-lg px-4 py-2">{{ linkCode }}</code>
              <button @click="copyCode" class="text-xs text-gray-500 hover:text-gray-300 transition-colors">{{ copied ? 'Copied!' : 'Copy' }}</button>
            </div>
            <p class="text-[10px] text-gray-600 mt-2">Expires in {{ codeExpiry }}</p>
          </div>
        </div>
      </div>

      <!-- Active alerts -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden mb-6">
        <div class="flex items-center justify-between px-5 py-4 border-b border-[#1f2937]">
          <h2 class="text-sm font-bold text-white">Active Alerts</h2>
          <NuxtLink to="/stocks" class="text-xs text-emerald-600 hover:text-emerald-400 transition-colors">+ Add from stocks →</NuxtLink>
        </div>

        <div v-if="alertsLoading" class="p-5 space-y-3">
          <div v-for="i in 3" :key="i" class="h-12 bg-[#1f2937] rounded-lg animate-pulse" />
        </div>
        <div v-else-if="!activeAlerts.length" class="px-5 py-8 text-center">
          <div class="text-3xl mb-2">🔔</div>
          <p class="text-gray-500 text-sm">No active alerts.</p>
          <p class="text-gray-600 text-xs mt-1">Go to a stock page and click "Set Alert".</p>
        </div>
        <div v-else class="divide-y divide-[#1f2937]">
          <div v-for="a in activeAlerts" :key="a.id" class="flex items-center gap-4 px-5 py-3.5">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <NuxtLink :to="assetLink(a.asset)" class="text-sm font-bold text-emerald-400 hover:text-emerald-300 font-mono">{{ a.asset?.symbol }}</NuxtLink>
                <span class="text-[10px] px-1.5 py-0.5 rounded font-semibold"
                  :class="a.condition === 'above' ? 'bg-emerald-900/40 text-emerald-400' : 'bg-red-900/40 text-red-400'">
                  {{ a.condition === 'above' ? '↑ Above' : '↓ Below' }} ${{ a.target_price.toLocaleString() }}
                </span>
              </div>
              <div class="text-xs text-gray-600 truncate mt-0.5">{{ a.asset?.name }}</div>
            </div>
            <button @click="deleteAlert(a.id)" class="text-gray-700 hover:text-red-400 transition-colors text-sm shrink-0">✕</button>
          </div>
        </div>
      </div>

      <!-- Triggered history -->
      <div v-if="triggeredAlerts.length" class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden mb-6">
        <div class="px-5 py-4 border-b border-[#1f2937]">
          <h2 class="text-sm font-bold text-white">Recently Triggered</h2>
        </div>
        <div class="divide-y divide-[#1f2937]">
          <div v-for="a in triggeredAlerts.slice(0,5)" :key="a.id" class="flex items-center gap-4 px-5 py-3 opacity-60">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-sm font-bold text-gray-400 font-mono">{{ a.asset?.symbol }}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded font-semibold bg-gray-800 text-gray-500">
                  {{ a.condition === 'above' ? '↑' : '↓' }} ${{ a.target_price.toLocaleString() }}
                </span>
                <span class="text-[10px] text-emerald-700">✓ Triggered</span>
              </div>
              <div class="text-[10px] text-gray-700 mt-0.5">{{ fmtDate(a.triggered_at) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Delivery log -->
      <div v-if="deliveries.length" class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
        <div class="px-5 py-4 border-b border-[#1f2937]">
          <h2 class="text-sm font-bold text-white">Delivery Log</h2>
        </div>
        <div class="divide-y divide-[#1f2937]">
          <div v-for="d in deliveries.slice(0, 10)" :key="d.id" class="flex items-center gap-3 px-5 py-2.5 text-xs">
            <span class="text-gray-500 font-mono shrink-0">{{ fmtDate(d.triggered_at) }}</span>
            <span class="text-gray-500 capitalize">{{ d.channel }}</span>
            <span v-if="d.error" class="text-red-500 truncate">{{ d.error }}</span>
            <span v-else class="text-emerald-600">✓ Sent</span>
          </div>
        </div>
      </div>
    </template>

    <AuthModal v-model="showAuth" />
  </main>
</template>

<script setup lang="ts">
const { get, post, del } = useApi()
const { isLoggedIn, user } = useAuth()

function assetLink(asset: any): string {
  if (!asset) return '/markets'
  const sym = asset.symbol?.toLowerCase()
  if (asset.asset_type === 'commodity') return `/commodities/${sym}`
  if (asset.asset_type === 'index') return `/indices/${sym}`
  return `/stocks/${sym}`
}

const showAuth = ref(false)
const alertsLoading = ref(true)
const codeLoading = ref(false)
const linkCode = ref('')
const copied = ref(false)
const codeExpiry = ref('10 min')

const botUsername = computed(() => useRuntimeConfig().public.telegramBotUsername || 'MetricsHourBot')

const prefs = ref({ notify_email: true, notify_telegram: false, telegram_connected: false })
const allAlerts = ref<any[]>([])
const deliveries = ref<any[]>([])

const activeAlerts = computed(() => allAlerts.value.filter(a => a.is_active))
const triggeredAlerts = computed(() => allAlerts.value.filter(a => !a.is_active && a.triggered_at))

onMounted(async () => {
  if (!isLoggedIn.value) return
  await Promise.all([loadAlerts(), loadPrefs(), loadDeliveries()])
})

async function loadAlerts() {
  alertsLoading.value = true
  try { allAlerts.value = await get<any[]>('/api/alerts') } catch { /* ignore */ }
  alertsLoading.value = false
}

async function loadPrefs() {
  try { prefs.value = await get<any>('/api/alerts/prefs') } catch { /* ignore */ }
}

async function loadDeliveries() {
  try { deliveries.value = await get<any[]>('/api/alerts/deliveries') } catch { /* ignore */ }
}

async function savePrefs() {
  try {
    await post('/api/alerts/prefs', { notify_telegram: prefs.value.notify_telegram, notify_email: prefs.value.notify_email })
  } catch { /* ignore */ }
}

async function generateCode() {
  codeLoading.value = true
  try {
    const res = await post<any>('/api/alerts/telegram/generate-code', {})
    linkCode.value = res.code
    // Countdown
    let secs = res.expires_in_seconds
    const interval = setInterval(() => {
      secs--
      if (secs <= 0) { clearInterval(interval); linkCode.value = '' }
      const m = Math.floor(secs / 60)
      const s = secs % 60
      codeExpiry.value = m > 0 ? `${m}m ${s}s` : `${s}s`
    }, 1000)
  } catch { /* ignore */ }
  codeLoading.value = false
}

async function copyCode() {
  if (!linkCode.value) return
  await navigator.clipboard.writeText(linkCode.value).catch(() => {})
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

async function disconnectTelegram() {
  try {
    await post('/api/alerts/telegram/disconnect', {})
    prefs.value.telegram_connected = false
    prefs.value.notify_telegram = false
    linkCode.value = ''
  } catch { /* ignore */ }
}

async function deleteAlert(id: number) {
  try {
    await del(`/api/alerts/${id}`)
    allAlerts.value = allAlerts.value.filter(a => a.id !== id)
  } catch { /* ignore */ }
}

function fmtDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
    d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

useSeoMeta({
  title: 'Price Alerts — MetricsHour',
  description: 'Set price alerts on stocks, crypto, and commodities. Get instant Telegram and email notifications when assets hit your targets.',
  robots: 'noindex, nofollow',
})
useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/alerts/' }],
})
</script>
