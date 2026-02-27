<template>
  <article
    ref="cardEl"
    class="feed-card relative w-full h-full overflow-hidden select-none cursor-pointer"
    :class="{ 'is-high-importance': isHighImportance }"
    @click="handleCardClick"
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

          <!-- Share: Twitter / X -->
          <a
            :href="`https://twitter.com/intent/tweet?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(cleanTitle)}`"
            target="_blank"
            rel="noopener"
            class="action-btn flex flex-col items-center gap-1"
            aria-label="Share on X (Twitter)"
            @click.stop
          >
            <div class="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center transition-all hover:bg-sky-500/20">
              <svg class="w-4 h-4 text-sky-400 fill-current" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
              </svg>
            </div>
            <span class="text-[10px] text-white/40">Tweet</span>
          </a>

          <!-- Share: WhatsApp -->
          <a
            :href="`https://wa.me/?text=${encodeURIComponent(cleanTitle + ' ' + shareUrl)}`"
            target="_blank"
            rel="noopener"
            class="action-btn flex flex-col items-center gap-1"
            aria-label="Share on WhatsApp"
            @click.stop
          >
            <div class="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center transition-all hover:bg-emerald-500/20">
              <svg class="w-4 h-4 text-emerald-400 fill-current" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
              </svg>
            </div>
            <span class="text-[10px] text-white/40">WhatsApp</span>
          </a>

          <!-- Share: LinkedIn -->
          <a
            :href="`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`"
            target="_blank"
            rel="noopener"
            class="action-btn flex flex-col items-center gap-1"
            aria-label="Share on LinkedIn"
            @click.stop
          >
            <div class="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center transition-all hover:bg-sky-600/20">
              <svg class="w-4 h-4 text-sky-300 fill-current" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
              </svg>
            </div>
            <span class="text-[10px] text-white/40">LinkedIn</span>
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
// Point share links to the API origin (/s/{id}) — bypasses CF Bot Fight Mode
// so Twitterbot/LinkedIn/WhatsApp crawlers get OG meta tags from FastAPI directly
const _runtimeConfig = useRuntimeConfig()
const shareUrl = computed(() => `${_runtimeConfig.public.apiBase}/s/${props.event.id}`)

function handleCardClick() {
  const url = props.event.source_url
  if (url) {
    url.startsWith('http') ? window.open(url, '_blank', 'noopener') : navigateTo(url)
    return
  }

  // No source_url — navigate to the most relevant page based on event type
  const type = props.event.event_type
  const data = props.event.event_data || {}

  if (type === 'price_move' && data.symbol) {
    navigateTo(`/stocks/${data.symbol}`)
  } else if ((type === 'macro_release' || type === 'indicator_release') && data.country_code) {
    navigateTo(`/countries/${(data.country_code as string).toLowerCase()}`)
  } else if (type === 'trade_update' && data.exporter && data.importer) {
    navigateTo(`/trade/${data.exporter}-${data.importer}`)
  } else if (type === 'central_bank') {
    navigateTo('/markets')
  } else {
    // Fallback — open the feed detail page for this event
    navigateTo(`/feed/${props.event.id}`)
  }
}

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
