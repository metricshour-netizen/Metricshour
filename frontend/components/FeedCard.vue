<template>
  <article
    ref="cardEl"
    class="feed-card relative w-full h-full overflow-hidden select-none"
    :class="{ 'is-high-importance': isHighImportance }"
  >

    <!-- ── Background layer ─────────────────────────────────────────── -->
    <div class="absolute inset-0" :style="bgBase" />

    <!-- Radial glow orb -->
    <div class="absolute inset-0 pointer-events-none" :style="glowStyle" />

    <!-- Animated noise grain overlay -->
    <div class="absolute inset-0 opacity-[0.035] pointer-events-none noise-layer" />

    <!-- Cover image (blogs) -->
    <img
      v-if="event.image_url"
      :src="event.image_url"
      alt=""
      class="absolute inset-0 w-full h-full object-cover"
      loading="lazy"
    />

    <!-- Strong bottom gradient for readability -->
    <div class="absolute inset-0 bg-gradient-to-t from-black via-black/60 to-transparent pointer-events-none" />
    <!-- Subtle top vignette -->
    <div class="absolute inset-0 bg-gradient-to-b from-black/40 to-transparent pointer-events-none" style="height: 30%" />

    <!-- ── Importance heat bar (top edge) ───────────────────────────── -->
    <div class="absolute top-0 left-0 right-0 h-0.5 z-10">
      <div
        class="h-full transition-all duration-700"
        :style="{ width: `${(event.importance_score || 0) * 10}%`, background: accentColor }"
      />
    </div>

    <!-- ── Main content ─────────────────────────────────────────────── -->
    <div class="relative h-full flex flex-col z-10">

      <!-- Top meta row -->
      <div class="flex items-center justify-between px-5 pt-5 pb-2">
        <div class="flex items-center gap-2">
          <!-- Type badge -->
          <span
            class="type-badge text-[10px] font-black tracking-widest uppercase px-2.5 py-1 rounded-md"
            :style="badgeStyle"
          >{{ typeLabel }}</span>

          <!-- Importance dots for high-impact events -->
          <div v-if="isHighImportance" class="flex gap-0.5">
            <span
              v-for="i in importanceDots"
              :key="i"
              class="w-1 h-1 rounded-full animate-pulse"
              :style="{ background: accentColor }"
            />
          </div>
        </div>

        <span class="text-xs text-white/40 font-mono">{{ relativeTime }}</span>
      </div>

      <!-- ── Hero visual (middle of card) ─────────────────────────── -->
      <div class="flex-1 flex items-center justify-center px-5">

        <!-- PRICE MOVE hero -->
        <div v-if="eventType === 'price_move'" class="text-center">
          <div class="text-7xl sm:text-8xl font-black tabular-nums leading-none mb-2" :style="{ color: priceColor }">
            {{ changeSign }}{{ Math.abs(changePct).toFixed(1) }}<span class="text-4xl sm:text-5xl">%</span>
          </div>
          <div class="flex items-center justify-center gap-2 mb-1">
            <span class="text-2xl font-black text-white tracking-tight">{{ eventData.symbol }}</span>
            <span class="text-xs text-white/50 font-mono">{{ eventData.currency }}</span>
          </div>
          <div class="text-sm text-white/40 font-mono">
            {{ eventData.price ? Number(eventData.price).toLocaleString(undefined, { maximumFractionDigits: 4 }) : '' }}
          </div>
          <!-- Direction arrow -->
          <div class="mt-4 text-5xl" :style="{ color: priceColor }">
            {{ changePct > 0 ? '↑' : '↓' }}
          </div>
        </div>

        <!-- INDICATOR RELEASE hero -->
        <div v-else-if="eventType === 'indicator_release' || eventType === 'macro_release'" class="text-center">
          <!-- Country flag big -->
          <div class="text-7xl sm:text-8xl mb-4 drop-shadow-2xl">{{ countryFlag }}</div>
          <!-- Value big -->
          <div class="text-5xl sm:text-6xl font-black tabular-nums text-white leading-none mb-1">
            {{ formattedValue }}
          </div>
          <div class="text-sm font-semibold uppercase tracking-widest mt-2" :style="{ color: accentColor }">
            {{ indicatorLabel }}
          </div>
        </div>

        <!-- TRADE UPDATE hero -->
        <div v-else-if="eventType === 'trade_update'" class="text-center">
          <div class="flex items-center justify-center gap-3 mb-4">
            <span class="text-5xl sm:text-6xl drop-shadow-2xl">{{ tradeExporterFlag }}</span>
            <div class="flex flex-col items-center gap-1">
              <div class="text-white/60 text-2xl">→</div>
              <div class="text-[10px] text-white/30 font-mono tracking-widest">TRADE</div>
            </div>
            <span class="text-5xl sm:text-6xl drop-shadow-2xl">{{ tradeImporterFlag }}</span>
          </div>
          <div class="text-5xl sm:text-6xl font-black text-white tabular-nums leading-none">
            ${{ tradeValueB }}<span class="text-3xl text-white/60">B</span>
          </div>
          <div class="text-xs text-white/40 font-mono mt-2 tracking-widest">
            {{ eventData.year }} BILATERAL
          </div>
        </div>

        <!-- BLOG / default hero -->
        <div v-else class="text-center px-4">
          <div class="text-6xl mb-6">{{ blogEmoji }}</div>
          <div class="text-xs font-black uppercase tracking-[0.25em] mb-3" :style="{ color: accentColor }">
            {{ typeLabel }}
          </div>
        </div>

      </div>

      <!-- ── Bottom content + action rail ────────────────────────── -->
      <div class="flex items-end gap-3 px-4 pb-8">

        <!-- Text content (left) -->
        <div class="flex-1 min-w-0 space-y-2">
          <h2 class="text-white font-bold text-lg sm:text-xl leading-tight line-clamp-3 drop-shadow-md">
            {{ cleanTitle }}
          </h2>
          <p v-if="event.body" class="text-white/55 text-sm leading-relaxed line-clamp-2">
            {{ event.body }}
          </p>

          <!-- Tags row -->
          <div class="flex flex-wrap gap-1.5 pt-0.5">
            <span
              v-if="eventData.country_code"
              class="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border border-white/10 bg-white/5 text-white/60"
            >{{ eventData.country_code }}</span>
            <span
              v-if="event.event_subtype"
              class="inline-flex text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border border-white/10 bg-white/5 text-white/60"
            >{{ subtypeLabel }}</span>
          </div>
        </div>

        <!-- Action rail (right, vertical TikTok-style) -->
        <div class="flex flex-col items-center gap-5 pb-1 shrink-0">

          <!-- Save -->
          <button
            class="action-btn flex flex-col items-center gap-1"
            :class="isSaved ? 'saved' : ''"
            @click.stop="handleSave"
          >
            <div
              class="w-11 h-11 rounded-full flex items-center justify-center text-xl transition-all duration-200"
              :class="isSaved
                ? 'bg-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.6)]'
                : 'bg-white/10 backdrop-blur-sm hover:bg-white/20'"
            >{{ isSaved ? '★' : '☆' }}</div>
            <span class="text-[10px] text-white/40">{{ isSaved ? 'Saved' : 'Save' }}</span>
          </button>

          <!-- Skip -->
          <button
            class="action-btn flex flex-col items-center gap-1"
            @click.stop="handleSkip"
          >
            <div class="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm hover:bg-white/20 flex items-center justify-center text-lg transition-all duration-200">
              ✕
            </div>
            <span class="text-[10px] text-white/40">Skip</span>
          </button>

          <!-- Open link -->
          <a
            v-if="event.source_url"
            :href="externalUrl"
            :target="isExternal ? '_blank' : '_self'"
            class="action-btn flex flex-col items-center gap-1"
            @click.stop
          >
            <div class="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm hover:bg-white/20 flex items-center justify-center text-lg transition-all duration-200">
              ↗
            </div>
            <span class="text-[10px] text-white/40">Open</span>
          </a>

        </div>
      </div>
    </div>

    <!-- High-importance pulse ring -->
    <div
      v-if="isHighImportance"
      class="absolute inset-0 pointer-events-none rounded-none"
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

// ── Accent colour per event type ─────────────────────────────────────────────
const ACCENT: Record<string, string> = {
  price_move:        '#10b981', // emerald
  indicator_release: '#3b82f6', // blue
  macro_release:     '#3b82f6',
  trade_update:      '#f59e0b', // amber
  blog:              '#a855f7', // purple
}
const accentColor = computed(() => ACCENT[eventType.value] || '#6b7280')

// ── Backgrounds ───────────────────────────────────────────────────────────────
const BG: Record<string, string> = {
  price_move:        '#03100d',
  indicator_release: '#030a1a',
  macro_release:     '#030a1a',
  trade_update:      '#0f0a00',
  blog:              '#0a0315',
}
const bgBase = computed(() => ({
  background: BG[eventType.value] || '#050505',
}))

const glowStyle = computed(() => {
  const color = accentColor.value
  const intensity = Math.max(0.08, Math.min(0.28, (props.event.importance_score || 5) / 10 * 0.28))
  return {
    background: `radial-gradient(ellipse 70% 55% at 50% 35%, ${color}${Math.round(intensity * 255).toString(16).padStart(2, '0')} 0%, transparent 70%)`,
  }
})

// ── Price move specifics ──────────────────────────────────────────────────────
const changePct = computed(() => Number(eventData.value.change_pct) || 0)
const changeSign = computed(() => changePct.value >= 0 ? '+' : '')
const priceColor = computed(() => changePct.value >= 0 ? '#10b981' : '#ef4444')

// ── Indicator specifics ───────────────────────────────────────────────────────
const COUNTRY_FLAGS: Record<string, string> = {
  US: '🇺🇸', GB: '🇬🇧', DE: '🇩🇪', FR: '🇫🇷', JP: '🇯🇵', CN: '🇨🇳',
  CA: '🇨🇦', AU: '🇦🇺', CH: '🇨🇭', IN: '🇮🇳', BR: '🇧🇷', RU: '🇷🇺',
  KR: '🇰🇷', MX: '🇲🇽', IT: '🇮🇹', ES: '🇪🇸', NL: '🇳🇱', SE: '🇸🇪',
  NO: '🇳🇴', DK: '🇩🇰', SG: '🇸🇬', HK: '🇭🇰', ZA: '🇿🇦', AR: '🇦🇷',
  SA: '🇸🇦', AE: '🇦🇪', NG: '🇳🇬', EG: '🇪🇬', PK: '🇵🇰', DZ: '🇩🇿',
  AD: '🇦🇩', AW: '🇦🇼', ID: '🇮🇩', TR: '🇹🇷', PL: '🇵🇱', UA: '🇺🇦',
}

const countryFlag = computed(() => {
  // First try the title which often has the flag emoji at the start
  const titleFlag = props.event.title.match(/^([\u{1F1E0}-\u{1F1FF}]{2})/u)?.[1]
  if (titleFlag) return titleFlag
  const code = eventData.value.country_code
  return code ? (COUNTRY_FLAGS[code] || '🌍') : '🌍'
})

const formattedValue = computed(() => {
  const v = eventData.value.value
  if (v === undefined || v === null) return '—'
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

// ── Trade specifics ───────────────────────────────────────────────────────────
const tradeValueB = computed(() => {
  const v = eventData.value.value_usd
  return v ? (Number(v) / 1e9).toFixed(0) : '—'
})

const tradeExporterFlag = computed(() => {
  const code = eventData.value.exporter
  return code ? (COUNTRY_FLAGS[code] || '🌍') : '🌍'
})

const tradeImporterFlag = computed(() => {
  const code = eventData.value.importer
  return code ? (COUNTRY_FLAGS[code] || '🌍') : '🌍'
})

// ── Blog / default ────────────────────────────────────────────────────────────
const BLOG_EMOJI: Record<string, string> = {
  blog: '📰', article: '📰', default: '📊',
}
const blogEmoji = computed(() => BLOG_EMOJI[eventType.value] || BLOG_EMOJI.default)

// ── Badge ─────────────────────────────────────────────────────────────────────
const TYPE_LABELS: Record<string, string> = {
  price_move:        '⚡ Price Move',
  indicator_release: '📈 Macro',
  macro_release:     '📈 Macro',
  trade_update:      '🌐 Trade',
  blog:              '✍️ Article',
}
const typeLabel = computed(() => TYPE_LABELS[eventType.value] || eventType.value.replace(/_/g, ' ').toUpperCase())

const badgeStyle = computed(() => ({
  background: `${accentColor.value}22`,
  color: accentColor.value,
  border: `1px solid ${accentColor.value}44`,
}))

// ── Title cleaning (strip flag emoji from start if present) ───────────────────
const cleanTitle = computed(() => {
  // Strip leading flag emoji from title (we show it in the hero instead)
  return props.event.title.replace(/^[\u{1F1E0}-\u{1F1FF}]{2}\s*/u, '').trim()
})

// ── Subtype label ─────────────────────────────────────────────────────────────
const subtypeLabel = computed(() => {
  const s = props.event.event_subtype || ''
  return s.replace(/_/g, ' ').replace(/pct$/, '%').replace(/usd$/, 'USD').toUpperCase()
})

// ── Importance ────────────────────────────────────────────────────────────────
const isHighImportance = computed(() => (props.event.importance_score || 0) >= 8)
const importanceDots = computed(() => Math.min(3, Math.floor((props.event.importance_score || 0) / 3)))

const pulseRingStyle = computed(() => ({
  boxShadow: `inset 0 0 0 1px ${accentColor.value}33`,
}))

// ── Time ──────────────────────────────────────────────────────────────────────
const relativeTime = computed(() => {
  const diff = Math.max(0, Date.now() - new Date(props.event.published_at).getTime())
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
})

// ── External URL ─────────────────────────────────────────────────────────────
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
.feed-card {
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
}

/* CSS noise grain (no external assets) */
.noise-layer {
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='1'/%3E%3C/svg%3E");
  background-size: 128px 128px;
}

.type-badge {
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.action-btn {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.action-btn > div {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.action-btn:active > div {
  transform: scale(0.88);
}

.action-btn.saved > div {
  animation: pop 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes pop {
  0%   { transform: scale(1); }
  50%  { transform: scale(1.3); }
  100% { transform: scale(1); }
}

/* High importance glow pulse */
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
