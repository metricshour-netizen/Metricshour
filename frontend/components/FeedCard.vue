<template>
  <article
    ref="cardEl"
    class="feed-card relative w-full h-full overflow-hidden select-none"
    :class="{ 'is-high-importance': isHighImportance }"
  >

    <!-- ── Background ──────────────────────────────────────────────── -->
    <div class="absolute inset-0" :style="bgBase" />
    <div class="absolute inset-0 pointer-events-none" :style="glowStyle" />
    <div class="absolute inset-0 opacity-[0.03] pointer-events-none noise-layer" />

    <!-- Cover image (blogs) -->
    <img
      v-if="event.image_url"
      :src="event.image_url"
      alt=""
      class="absolute inset-0 w-full h-full object-cover opacity-40"
      loading="lazy"
    />

    <!-- Gradients for readability -->
    <div class="absolute inset-0 bg-gradient-to-t from-black/95 via-black/50 to-transparent pointer-events-none" />
    <div class="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-black/60 to-transparent pointer-events-none" />

    <!-- ── Importance bar (top edge) ────────────────────────────────── -->
    <div class="absolute top-0 left-0 right-0 h-0.5 z-10">
      <div
        class="h-full transition-all duration-700"
        :style="{ width: `${(event.importance_score || 0) * 10}%`, background: accentColor }"
      />
    </div>

    <!-- ── Main content ──────────────────────────────────────────────── -->
    <div class="relative h-full flex flex-col z-10">

      <!-- ── TOP: source + time ──────────────────────────────────────── -->
      <div class="flex items-start justify-between px-4 pt-4 pb-2 gap-2">
        <div class="flex items-center gap-2 flex-wrap">
          <!-- Type badge -->
          <span
            class="type-badge text-[11px] font-black tracking-widest uppercase px-2.5 py-1 rounded-md shrink-0"
            :style="badgeStyle"
          >{{ typeLabel }}</span>
          <!-- High importance dots -->
          <div v-if="isHighImportance" class="flex gap-0.5 items-center">
            <span
              v-for="i in importanceDots" :key="i"
              class="w-1.5 h-1.5 rounded-full animate-pulse"
              :style="{ background: accentColor }"
            />
          </div>
        </div>
        <!-- Timestamp block -->
        <div class="text-right shrink-0">
          <div class="text-xs font-semibold text-white/70">{{ relativeTime }}</div>
          <div class="text-[10px] text-white/30 font-mono mt-0.5">{{ absoluteTime }}</div>
        </div>
      </div>

      <!-- ── HERO visual (fills middle) ─────────────────────────────── -->
      <div class="flex-1 flex items-center justify-center px-5 py-2">

        <!-- PRICE MOVE -->
        <div v-if="eventType === 'price_move'" class="text-center w-full">
          <div class="text-5xl sm:text-6xl font-black tabular-nums leading-none mb-2" :style="{ color: priceColor }">
            {{ changeSign }}{{ Math.abs(changePct).toFixed(2) }}<span class="text-2xl sm:text-3xl opacity-80">%</span>
          </div>
          <div class="flex items-center justify-center gap-2 mt-3">
            <span class="text-xl font-black text-white tracking-tight">{{ eventData.symbol }}</span>
            <span v-if="eventData.name" class="text-xs text-white/40 truncate max-w-[140px]">{{ eventData.name }}</span>
          </div>
          <div v-if="eventData.price" class="text-sm text-white/50 font-mono mt-1">
            ${{ Number(eventData.price).toLocaleString(undefined, { maximumFractionDigits: 4 }) }}
          </div>
          <div class="mt-4 text-4xl" :style="{ color: priceColor }">
            {{ changePct > 0 ? '↑' : '↓' }}
          </div>
        </div>

        <!-- INDICATOR RELEASE -->
        <div v-else-if="eventType === 'indicator_release' || eventType === 'macro_release'" class="text-center w-full">
          <div class="text-6xl sm:text-7xl mb-3 drop-shadow-2xl">{{ countryFlag }}</div>
          <div class="text-4xl sm:text-5xl font-black tabular-nums text-white leading-none mb-2">
            {{ formattedValue }}
          </div>
          <div class="text-xs font-bold uppercase tracking-widest mt-2 px-4" :style="{ color: accentColor }">
            {{ indicatorLabel }}
          </div>
          <div v-if="eventData.country_code" class="text-xs text-white/30 font-mono mt-1">{{ eventData.country_code }}</div>
        </div>

        <!-- TRADE UPDATE -->
        <div v-else-if="eventType === 'trade_update'" class="text-center w-full">
          <div class="flex items-center justify-center gap-4 mb-4">
            <div class="flex flex-col items-center gap-1">
              <span class="text-5xl drop-shadow-2xl">{{ tradeExporterFlag }}</span>
              <span class="text-[10px] text-white/30 font-mono">{{ eventData.exporter }}</span>
            </div>
            <div class="flex flex-col items-center gap-1">
              <div class="text-white/40 text-xl">↔</div>
              <div class="text-[9px] text-white/20 font-mono tracking-widest">BILATERAL</div>
            </div>
            <div class="flex flex-col items-center gap-1">
              <span class="text-5xl drop-shadow-2xl">{{ tradeImporterFlag }}</span>
              <span class="text-[10px] text-white/30 font-mono">{{ eventData.importer }}</span>
            </div>
          </div>
          <div class="text-4xl sm:text-5xl font-black text-white tabular-nums leading-none">
            ${{ tradeValueB }}<span class="text-2xl text-white/50">B</span>
          </div>
          <div class="text-xs text-white/30 font-mono mt-2 tracking-widest">{{ eventData.year }} TRADE VOLUME</div>
        </div>

        <!-- BLOG / NEWS -->
        <div v-else class="text-center px-2 w-full">
          <div class="text-5xl mb-4">{{ blogEmoji }}</div>
          <div class="text-xs font-black uppercase tracking-[0.2em] mb-2" :style="{ color: accentColor }">
            {{ typeLabel }}
          </div>
        </div>

      </div>

      <!-- ── BOTTOM: content + actions ──────────────────────────────── -->
      <div class="flex items-end gap-3 px-4 pb-6">

        <!-- Text (left) -->
        <div class="flex-1 min-w-0 space-y-1.5">

          <!-- Title -->
          <h2 class="text-white font-bold text-base sm:text-lg leading-snug line-clamp-3 drop-shadow-md">
            {{ cleanTitle }}
          </h2>

          <!-- Body excerpt (blog/articles) -->
          <p v-if="event.body" class="text-white/50 text-sm leading-relaxed line-clamp-2">
            {{ event.body }}
          </p>

          <!-- Rich metadata row -->
          <div class="flex flex-wrap items-center gap-1.5 pt-1">
            <span
              v-if="eventData.country_code"
              class="meta-tag"
            >{{ countryFlag }} {{ eventData.country_code }}</span>
            <span
              v-if="event.event_subtype"
              class="meta-tag"
            >{{ subtypeLabel }}</span>
            <span
              v-if="eventData.symbol"
              class="meta-tag font-mono"
              :style="{ color: accentColor, borderColor: `${accentColor}44`, background: `${accentColor}11` }"
            >{{ eventData.symbol }}</span>
            <!-- Score -->
            <span class="meta-tag ml-auto" :style="{ color: accentColor, borderColor: `${accentColor}33`, background: `${accentColor}11` }">
              {{ '●'.repeat(Math.min(5, Math.ceil((event.importance_score || 1) / 2))) }} {{ event.importance_score || '—' }}/10
            </span>
          </div>

        </div>

        <!-- Action rail (TikTok-style vertical) -->
        <div class="flex flex-col items-center gap-4 pb-1 shrink-0">

          <!-- Save -->
          <button class="action-btn flex flex-col items-center gap-1" @click.stop="handleSave">
            <div
              class="w-11 h-11 rounded-full flex items-center justify-center text-xl transition-all"
              :class="isSaved ? 'bg-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.5)]' : 'bg-white/10 backdrop-blur-sm'"
            >{{ isSaved ? '★' : '☆' }}</div>
            <span class="text-[10px] text-white/40">{{ isSaved ? 'Saved' : 'Save' }}</span>
          </button>

          <!-- Skip -->
          <button class="action-btn flex flex-col items-center gap-1" @click.stop="handleSkip">
            <div class="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center text-lg transition-all">✕</div>
            <span class="text-[10px] text-white/40">Skip</span>
          </button>

          <!-- Open -->
          <a
            v-if="event.source_url"
            :href="externalUrl"
            :target="isExternal ? '_blank' : '_self'"
            class="action-btn flex flex-col items-center gap-1"
            @click.stop
          >
            <div class="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center text-lg transition-all">↗</div>
            <span class="text-[10px] text-white/40">Open</span>
          </a>

        </div>
      </div>
    </div>

    <!-- High importance pulse ring -->
    <div
      v-if="isHighImportance"
      class="absolute inset-0 pointer-events-none"
      :style="pulseRingStyle"
    />
  </article>
</template>

<script setup lang="ts">
interface FeedEvent {
  id: number
  title: string
  body?: string | null
  event_type: string
  event_subtype?: string | null
  source_url?: string | null
  image_url?: string | null
  published_at: string
  related_asset_ids?: number[] | null
  related_country_ids?: number[] | null
  importance_score?: number | null
  event_data?: Record<string, any> | null
}

const props = defineProps<{ event: FeedEvent }>()
const emit = defineEmits<{
  (e: 'save', id: number): void
  (e: 'skip', id: number): void
}>()

const { post } = useApi()
const { isLoggedIn } = useAuth()
const cardEl = ref<HTMLElement | null>(null)
const isSaved = ref(false)

const eventType = computed(() => props.event.event_type)
const eventData = computed(() => props.event.event_data || {})

// ── Accent colour ────────────────────────────────────────────────────────────
const ACCENT: Record<string, string> = {
  price_move:        '#10b981',
  indicator_release: '#3b82f6',
  macro_release:     '#3b82f6',
  trade_update:      '#f59e0b',
  blog:              '#a855f7',
}
const accentColor = computed(() => ACCENT[eventType.value] || '#6b7280')

// ── Backgrounds ──────────────────────────────────────────────────────────────
const BG: Record<string, string> = {
  price_move:        '#021009',
  indicator_release: '#020818',
  macro_release:     '#020818',
  trade_update:      '#0d0800',
  blog:              '#080212',
}
const bgBase = computed(() => ({ background: BG[eventType.value] || '#050505' }))

const glowStyle = computed(() => {
  const color = accentColor.value
  const intensity = Math.max(0.06, Math.min(0.22, (props.event.importance_score || 5) / 10 * 0.22))
  return {
    background: `radial-gradient(ellipse 80% 50% at 50% 30%, ${color}${Math.round(intensity * 255).toString(16).padStart(2, '0')} 0%, transparent 70%)`,
  }
})

// ── Price move ───────────────────────────────────────────────────────────────
const changePct = computed(() => Number(eventData.value.change_pct) || 0)
const changeSign = computed(() => changePct.value >= 0 ? '+' : '')
const priceColor = computed(() => changePct.value >= 0 ? '#10b981' : '#ef4444')

// ── Indicator ────────────────────────────────────────────────────────────────
const COUNTRY_FLAGS: Record<string, string> = {
  US:'🇺🇸',GB:'🇬🇧',DE:'🇩🇪',FR:'🇫🇷',JP:'🇯🇵',CN:'🇨🇳',CA:'🇨🇦',AU:'🇦🇺',
  CH:'🇨🇭',IN:'🇮🇳',BR:'🇧🇷',RU:'🇷🇺',KR:'🇰🇷',MX:'🇲🇽',IT:'🇮🇹',ES:'🇪🇸',
  NL:'🇳🇱',SE:'🇸🇪',NO:'🇳🇴',DK:'🇩🇰',SG:'🇸🇬',HK:'🇭🇰',ZA:'🇿🇦',AR:'🇦🇷',
  SA:'🇸🇦',AE:'🇦🇪',NG:'🇳🇬',EG:'🇪🇬',PK:'🇵🇰',ID:'🇮🇩',TR:'🇹🇷',PL:'🇵🇱',
}
const countryFlag = computed(() => {
  const titleFlag = props.event.title.match(/^([\u{1F1E0}-\u{1F1FF}]{2})/u)?.[1]
  if (titleFlag) return titleFlag
  const code = eventData.value.country_code
  return code ? (COUNTRY_FLAGS[code] || '🌍') : '🌍'
})
const formattedValue = computed(() => {
  const v = eventData.value.value
  if (v == null) return '—'
  const n = Number(v)
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (Math.abs(n) >= 1e9)  return `$${(n / 1e9).toFixed(1)}B`
  if (Math.abs(n) >= 1e6)  return `$${(n / 1e6).toFixed(1)}M`
  return n.toFixed(n % 1 !== 0 ? 2 : 0)
})
const indicatorLabel = computed(() => {
  const ind = eventData.value.indicator || props.event.event_subtype || ''
  return ind.replace(/_/g, ' ').replace(/pct$/, '%').replace(/usd$/, 'USD')
})

// ── Trade ─────────────────────────────────────────────────────────────────────
const tradeValueB = computed(() => {
  const v = eventData.value.value_usd
  return v ? (Number(v) / 1e9).toFixed(0) : '—'
})
const tradeExporterFlag = computed(() => COUNTRY_FLAGS[eventData.value.exporter] || '🌍')
const tradeImporterFlag = computed(() => COUNTRY_FLAGS[eventData.value.importer] || '🌍')

// ── Blog / default ────────────────────────────────────────────────────────────
const BLOG_EMOJI: Record<string, string> = { blog: '📰', article: '📰' }
const blogEmoji = computed(() => BLOG_EMOJI[eventType.value] || '📊')

// ── Badge ─────────────────────────────────────────────────────────────────────
const TYPE_LABELS: Record<string, string> = {
  price_move:        '⚡ Price Move',
  indicator_release: '📈 Macro Data',
  macro_release:     '📈 Macro Data',
  trade_update:      '🌐 Trade',
  blog:              '✍️ Article',
}
const typeLabel = computed(() => TYPE_LABELS[eventType.value] || eventType.value.replace(/_/g, ' ').toUpperCase())
const badgeStyle = computed(() => ({
  background: `${accentColor.value}20`,
  color: accentColor.value,
  border: `1px solid ${accentColor.value}40`,
}))

const cleanTitle = computed(() =>
  props.event.title.replace(/^[\u{1F1E0}-\u{1F1FF}]{2}\s*/u, '').trim()
)
const subtypeLabel = computed(() => {
  const s = props.event.event_subtype || ''
  return s.replace(/_/g, ' ').replace(/pct$/, '%').replace(/usd$/, 'USD').toUpperCase()
})

// ── Importance ────────────────────────────────────────────────────────────────
const isHighImportance = computed(() => (props.event.importance_score || 0) >= 8)
const importanceDots = computed(() => Math.min(3, Math.floor((props.event.importance_score || 0) / 3)))
const pulseRingStyle = computed(() => ({ boxShadow: `inset 0 0 0 1px ${accentColor.value}30` }))

// ── Timestamps ────────────────────────────────────────────────────────────────
const relativeTime = computed(() => {
  const diff = Math.max(0, Date.now() - new Date(props.event.published_at).getTime())
  const mins = Math.floor(diff / 60000)
  if (mins < 1)  return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24)  return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7)  return `${days}d ago`
  return `${Math.floor(days / 7)}w ago`
})

const absoluteTime = computed(() => {
  const d = new Date(props.event.published_at)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    + ' · '
    + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
})

// ── External URL ──────────────────────────────────────────────────────────────
const isExternal = computed(() => (props.event.source_url || '').startsWith('http'))
const externalUrl = computed(() => props.event.source_url || '#')

// ── Actions ───────────────────────────────────────────────────────────────────
async function _interact(type: string) {
  if (!isLoggedIn.value) return
  try { await post(`/api/feed/${props.event.id}/interact`, { interaction_type: type }) } catch {}
}
function handleSave() {
  if (!isLoggedIn.value) return
  isSaved.value = !isSaved.value
  _interact(isSaved.value ? 'save' : 'view')
  emit('save', props.event.id)
}
function handleSkip() {
  _interact('skip')
  emit('skip', props.event.id)
}

onMounted(() => {
  if (!isLoggedIn.value) return
  const obs = new IntersectionObserver(
    (e) => { if (e[0].isIntersecting) { _interact('view'); obs.disconnect() } },
    { threshold: 0.5 },
  )
  if (cardEl.value) obs.observe(cardEl.value)
})
</script>

<style scoped>
.feed-card { font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif; }

.noise-layer {
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='1'/%3E%3C/svg%3E");
  background-size: 128px 128px;
}

.type-badge {
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.meta-tag {
  display: inline-flex;
  align-items: center;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 9999px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.55);
}

.action-btn {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.action-btn > div { transition: transform 0.15s ease, box-shadow 0.15s ease; }
.action-btn:active > div { transform: scale(0.88); }

.is-high-importance::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  animation: importance-pulse 3s ease-in-out infinite;
}
@keyframes importance-pulse {
  0%, 100% { opacity: 0; }
  50%       { opacity: 1; }
}
</style>
