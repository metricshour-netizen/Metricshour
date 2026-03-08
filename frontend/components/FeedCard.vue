<template>
  <NuxtLink
    ref="cardEl"
    :to="cardRoute"
    class="feed-card relative w-full h-full overflow-hidden select-none cursor-pointer block"
    :class="{ 'is-high-importance': isHighImportance }"
  >

    <!-- ── Background ──────────────────────────────────────────────── -->
    <div class="absolute inset-0" :style="bgBase" />
    <div class="absolute inset-0 pointer-events-none" :style="glowStyle" />
    <div class="absolute inset-0 opacity-[0.03] pointer-events-none noise-layer" />


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

        <!-- DAILY INSIGHT -->
        <div v-else-if="eventType === 'daily_insight'" class="text-center px-2 w-full">
          <div class="text-4xl mb-3" :style="{ color: accentColor }">◆</div>
          <div class="text-xs font-black uppercase tracking-[0.2em] mb-3" :style="{ color: accentColor }">
            MetricsHour Intelligence
          </div>
          <div v-if="eventData.entity_flag" class="text-5xl mb-2 drop-shadow-2xl">{{ eventData.entity_flag }}</div>
          <div v-if="eventData.entity_name" class="text-sm font-bold text-white/80 leading-tight">
            {{ eventData.entity_name }}
          </div>
          <div v-if="eventData.entity_type" class="text-[10px] font-mono text-white/30 mt-1 uppercase tracking-widest">
            {{ eventData.entity_type }}
          </div>
        </div>

        <!-- BLOG / NEWS -->
        <div v-else class="text-center px-2 w-full">
          <div class="text-5xl mb-4">{{ blogEmoji }}</div>
          <div class="text-xs font-black uppercase tracking-[0.2em] mb-2" :style="{ color: accentColor }">
            {{ typeLabel }}
          </div>
        </div>

      </div>

      <!-- ── BOTTOM: text content only (action rail is absolutely positioned) -->
      <div
        class="px-4 pr-20"
        style="padding-bottom: max(2.5rem, calc(1.5rem + env(safe-area-inset-bottom)))"
      >
        <div class="space-y-1.5">
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
            <span v-if="eventData.country_code" class="meta-tag">{{ countryFlag }} {{ eventData.country_code }}</span>
            <span v-if="event.event_subtype" class="meta-tag">{{ subtypeLabel }}</span>
            <span
              v-if="eventData.symbol"
              class="meta-tag font-mono"
              :style="{ color: accentColor, borderColor: `${accentColor}44`, background: `${accentColor}11` }"
            >{{ eventData.symbol }}</span>
            <span class="meta-tag ml-auto" :style="{ color: accentColor, borderColor: `${accentColor}33`, background: `${accentColor}11` }">
              {{ '●'.repeat(Math.min(5, Math.ceil((event.importance_score || 1) / 2))) }} {{ event.importance_score || '—' }}/10
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Action rail — absolutely anchored to right edge ──────────── -->
    <div
      class="absolute right-3 z-20 flex flex-col items-center gap-4"
      style="bottom: max(5.5rem, calc(4rem + env(safe-area-inset-bottom)))"
      @click.stop
    >
      <!-- Save -->
      <button class="action-btn flex flex-col items-center gap-1" @click="handleSave">
        <div
          class="w-11 h-11 rounded-full flex items-center justify-center text-xl transition-all"
          :class="isSaved ? 'bg-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.5)]' : 'bg-white/10 backdrop-blur-sm'"
        >{{ isSaved ? '★' : '☆' }}</div>
        <span class="text-[10px] text-white/40">{{ isSaved ? 'Saved' : 'Save' }}</span>
      </button>

      <!-- Skip -->
      <button class="action-btn flex flex-col items-center gap-1" @click="handleSkip">
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

      <!-- Share button -->
      <div class="relative">
        <button
          class="action-btn flex flex-col items-center gap-1"
          aria-label="Share"
          @click="handleShare"
        >
          <div class="w-11 h-11 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center transition-all hover:bg-white/20" :class="showSharePanel ? 'bg-white/20' : ''">
            <svg class="w-4 h-4 text-white/70 fill-none stroke-current" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
            </svg>
          </div>
          <span class="text-[10px] text-white/40">Share</span>
        </button>

        <!-- Share panel (desktop / fallback) -->
        <Transition name="share-panel">
          <div
            v-if="showSharePanel"
            class="share-panel absolute right-14 bottom-0 z-50 bg-[#0f172a] border border-white/10 rounded-2xl p-3 shadow-2xl w-56"
            @click.stop
          >
            <!-- Image share row -->
            <p class="text-[10px] text-white/30 uppercase tracking-widest mb-2 px-1">Share as image</p>
            <div class="flex gap-2 mb-3">
              <button
                class="flex-1 flex flex-col items-center gap-1.5 py-2 rounded-xl hover:bg-white/10 transition-colors border border-white/10"
                :disabled="_pregenBusy || !_cachedBlobs.story"
                @click="shareAsImage('story')"
              >
                <div class="w-7 h-12 rounded overflow-hidden border-2 flex items-center justify-center text-[10px] font-bold transition-colors"
                  :class="_pregenBusy ? 'border-white/20 text-white/20 animate-pulse' : 'border-white/30 text-white/50'">
                  <img v-if="_previewUrls.story" :src="_previewUrls.story" class="w-full h-full object-cover" alt="" />
                  <span v-else>{{ _pregenBusy ? '…' : '9:16' }}</span>
                </div>
                <span class="text-[9px] text-white/40">Story</span>
              </button>
              <button
                class="flex-1 flex flex-col items-center gap-1.5 py-2 rounded-xl hover:bg-white/10 transition-colors border border-white/10"
                :disabled="_pregenBusy || !_cachedBlobs.post"
                @click="shareAsImage('post')"
              >
                <div class="w-10 h-10 rounded overflow-hidden border-2 flex items-center justify-center text-[10px] font-bold transition-colors"
                  :class="_pregenBusy ? 'border-white/20 text-white/20 animate-pulse' : 'border-white/30 text-white/50'">
                  <img v-if="_previewUrls.post" :src="_previewUrls.post" class="w-full h-full object-cover" alt="" />
                  <span v-else>{{ _pregenBusy ? '…' : '1:1' }}</span>
                </div>
                <span class="text-[9px] text-white/40">Post</span>
              </button>
            </div>
            <div class="border-t border-white/10 mb-2.5" />
            <p class="text-[10px] text-white/30 uppercase tracking-widest mb-2.5 px-1">Share via</p>
            <div class="grid grid-cols-3 gap-2">
              <a :href="`https://twitter.com/intent/tweet?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(cleanTitle)}`" target="_blank" rel="noopener" class="share-option group flex flex-col items-center gap-1.5 p-2 rounded-xl hover:bg-white/10 transition-colors">
                <svg class="w-5 h-5 text-sky-400 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.746l7.73-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                <span class="text-[9px] text-white/40">X</span>
              </a>
              <a :href="`https://wa.me/?text=${encodeURIComponent(cleanTitle + ' ' + shareUrl)}`" target="_blank" rel="noopener" class="share-option group flex flex-col items-center gap-1.5 p-2 rounded-xl hover:bg-white/10 transition-colors">
                <svg class="w-5 h-5 text-emerald-400 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
                <span class="text-[9px] text-white/40">WhatsApp</span>
              </a>
              <a :href="`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`" target="_blank" rel="noopener" class="share-option group flex flex-col items-center gap-1.5 p-2 rounded-xl hover:bg-white/10 transition-colors">
                <svg class="w-5 h-5 text-sky-300 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                <span class="text-[9px] text-white/40">LinkedIn</span>
              </a>
              <a :href="`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(cleanTitle)}`" target="_blank" rel="noopener" class="share-option group flex flex-col items-center gap-1.5 p-2 rounded-xl hover:bg-white/10 transition-colors">
                <svg class="w-5 h-5 text-sky-400 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
                <span class="text-[9px] text-white/40">Telegram</span>
              </a>
              <a :href="`https://reddit.com/submit?url=${encodeURIComponent(shareUrl)}&title=${encodeURIComponent(cleanTitle)}`" target="_blank" rel="noopener" class="share-option group flex flex-col items-center gap-1.5 p-2 rounded-xl hover:bg-white/10 transition-colors">
                <svg class="w-5 h-5 text-orange-400 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/></svg>
                <span class="text-[9px] text-white/40">Reddit</span>
              </a>
              <!-- Copy link — copies clean frontend URL -->
              <button class="share-option group flex flex-col items-center gap-1.5 p-2 rounded-xl hover:bg-white/10 transition-colors" @click="handleCopy">
                <div class="w-5 h-5 flex items-center justify-center text-white/60 text-sm">{{ copied ? '✓' : '🔗' }}</div>
                <span class="text-[9px] text-white/40">{{ copied ? 'Copied!' : 'Copy' }}</span>
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- High importance pulse ring -->
    <div
      v-if="isHighImportance"
      class="absolute inset-0 pointer-events-none"
      :style="pulseRingStyle"
    />
  </NuxtLink>

  <!-- Auth modal — shown when unauthenticated user tries to save -->
  <AuthModal v-model="showAuthModal" />
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
const showAuthModal = ref(false)

const eventType = computed(() => props.event.event_type)
const eventData = computed(() => props.event.event_data || {})

// ── Accent colour ────────────────────────────────────────────────────────────
const ACCENT: Record<string, string> = {
  price_move:        '#10b981',
  indicator_release: '#3b82f6',
  macro_release:     '#3b82f6',
  trade_update:      '#f59e0b',
  central_bank:      '#a855f7',
  geopolitical:      '#ef4444',
  commodity:         '#f59e0b',
  commodity_move:    '#f59e0b',
  blog:              '#a855f7',
  daily_insight:     '#34d399',
}
const accentColor = computed(() => ACCENT[eventType.value] || '#6b7280')

// ── Backgrounds ──────────────────────────────────────────────────────────────
const BG: Record<string, string> = {
  price_move:        '#021009',
  indicator_release: '#020818',
  macro_release:     '#020818',
  trade_update:      '#0d0800',
  central_bank:      '#080212',
  geopolitical:      '#140202',
  commodity:         '#0d0800',
  commodity_move:    '#0d0800',
  blog:              '#080212',
  daily_insight:     '#010f0a',
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
  central_bank:      '🏦 Central Bank',
  geopolitical:      '🌍 Geopolitical',
  commodity:         '🛢 Commodity',
  commodity_move:    '🛢 Commodity',
  blog:              '✍️ Article',
  daily_insight:     '◆ AI Insight',
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
const shareUrl = computed(() => `https://metricshour.com/feed/${props.event.id}`)
const { public: { r2PublicUrl } } = useRuntimeConfig()
const r2Base = (r2PublicUrl as string || 'https://api.metricshour.com').replace(/\/$/, '')

// Share panel state
const showSharePanel = ref(false)
const copied = ref(false)

// Pre-generated blobs — ready before user clicks Story/Post so navigator.share
// can be called synchronously (iOS Safari drops the gesture after any await)
const _cachedBlobs = ref<Record<'story' | 'post', Blob | null>>({ story: null, post: null })
const _previewUrls = ref<Record<'story' | 'post', string | null>>({ story: null, post: null })
const _pregenBusy = ref(false)

watch(showSharePanel, async (visible) => {
  if (!visible) {
    if (_previewUrls.value.story) URL.revokeObjectURL(_previewUrls.value.story)
    if (_previewUrls.value.post)  URL.revokeObjectURL(_previewUrls.value.post)
    _previewUrls.value = { story: null, post: null }
    _cachedBlobs.value = { story: null, post: null }
    return
  }
  if (_pregenBusy.value) return
  _pregenBusy.value = true
  try {
    const storyBlob = await generateImage('story').catch(() => null)
    _cachedBlobs.value.story = storyBlob
    if (storyBlob) _previewUrls.value.story = URL.createObjectURL(storyBlob)

    const postBlob = await generateImage('post').catch(() => null)
    _cachedBlobs.value.post = postBlob
    if (postBlob) _previewUrls.value.post = URL.createObjectURL(postBlob)
  } finally {
    _pregenBusy.value = false
  }
})

// ── Canvas image generation ───────────────────────────────────────────────────
function wrapText(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxW: number, lineH: number): number {
  const words = text.split(' ')
  let line = ''
  let curY = y
  for (const word of words) {
    const test = line ? `${line} ${word}` : word
    if (ctx.measureText(test).width > maxW && line) {
      ctx.fillText(line, x, curY)
      line = word
      curY += lineH
    } else {
      line = test
    }
  }
  if (line) ctx.fillText(line, x, curY)
  return curY + lineH
}

async function generateImage(format: 'story' | 'post'): Promise<Blob> {
  const W = 1080
  const H = format === 'story' ? 1920 : 1080
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!
  const accent = accentColor.value
  const bg = BG[eventType.value] || '#050505'
  const importance = props.event.importance_score || 5
  const type = eventType.value
  const data = eventData.value

  // Background
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, W, H)

  // Radial glow — bright centre, fading out
  const intensity = Math.max(0.25, Math.min(0.55, importance / 10 * 0.55))
  const grd = ctx.createRadialGradient(W / 2, H * 0.38, 0, W / 2, H * 0.38, W * 0.65)
  grd.addColorStop(0, accent + Math.round(intensity * 255).toString(16).padStart(2, '0'))
  grd.addColorStop(0.6, accent + '22')
  grd.addColorStop(1, 'rgba(0,0,0,0)')
  ctx.fillStyle = grd
  ctx.fillRect(0, 0, W, H)

  // Gentle bottom gradient — only the bottom quarter, so content stays visible
  const bottomGrad = ctx.createLinearGradient(0, H * 0.65, 0, H)
  bottomGrad.addColorStop(0, 'rgba(0,0,0,0)')
  bottomGrad.addColorStop(1, 'rgba(0,0,0,0.88)')
  ctx.fillStyle = bottomGrad
  ctx.fillRect(0, 0, W, H)

  // Top accent bar
  ctx.fillStyle = accent
  const barW = Math.round(W * (importance / 10))
  ctx.fillRect(0, 0, barW, 8)

  // Type badge pill
  const typeText = (TYPE_LABELS[type] || type.replace(/_/g, ' ').toUpperCase())
  ctx.font = 'bold 36px -apple-system, BlinkMacSystemFont, sans-serif'
  const badgeMetrics = ctx.measureText(typeText)
  const bx = 52, by = 60, bpad = 24, bh = 60
  const bw = badgeMetrics.width + bpad * 2
  ctx.beginPath()
  if (ctx.roundRect) {
    ctx.roundRect(bx, by, bw, bh, 12)
  } else {
    const r = 12
    ctx.moveTo(bx + r, by)
    ctx.lineTo(bx + bw - r, by)
    ctx.arcTo(bx + bw, by, bx + bw, by + r, r)
    ctx.lineTo(bx + bw, by + bh - r)
    ctx.arcTo(bx + bw, by + bh, bx + bw - r, by + bh, r)
    ctx.lineTo(bx + r, by + bh)
    ctx.arcTo(bx, by + bh, bx, by + bh - r, r)
    ctx.lineTo(bx, by + r)
    ctx.arcTo(bx, by, bx + r, by, r)
    ctx.closePath()
  }
  ctx.fillStyle = accent + '25'
  ctx.fill()
  ctx.strokeStyle = accent + '50'
  ctx.lineWidth = 2
  ctx.stroke()
  ctx.fillStyle = accent
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(typeText, bx + bpad, by + bh / 2)

  // Timestamp top-right
  ctx.font = '32px -apple-system, sans-serif'
  ctx.fillStyle = 'rgba(255,255,255,0.5)'
  ctx.textAlign = 'right'
  ctx.fillText(relativeTime.value, W - 52, by + bh / 2)

  // Hero content
  const heroY = H * (format === 'story' ? 0.38 : 0.42)
  ctx.textAlign = 'center'
  ctx.textBaseline = 'alphabetic'

  if (type === 'price_move') {
    const pct = Number(data.change_pct) || 0
    const color = pct >= 0 ? '#10b981' : '#ef4444'
    const sign = pct >= 0 ? '+' : ''
    ctx.font = `bold ${format === 'story' ? 220 : 180}px -apple-system, sans-serif`
    ctx.fillStyle = color
    ctx.fillText(`${sign}${Math.abs(pct).toFixed(2)}%`, W / 2, heroY)
    ctx.font = `bold 88px -apple-system, sans-serif`
    ctx.fillStyle = 'white'
    ctx.fillText(String(data.symbol || ''), W / 2, heroY + 110)
    if (data.name) {
      ctx.font = '44px -apple-system, sans-serif'
      ctx.fillStyle = 'rgba(255,255,255,0.35)'
      ctx.fillText(String(data.name).slice(0, 30), W / 2, heroY + 175)
    }
    if (data.price) {
      ctx.font = '52px monospace'
      ctx.fillStyle = 'rgba(255,255,255,0.3)'
      ctx.fillText(`$${Number(data.price).toLocaleString(undefined, { maximumFractionDigits: 4 })}`, W / 2, heroY + 250)
    }
    // Arrow
    ctx.font = `bold 120px sans-serif`
    ctx.fillStyle = color
    ctx.fillText(pct >= 0 ? '↑' : '↓', W / 2, heroY + 380)
  } else if (type === 'indicator_release' || type === 'macro_release') {
    ctx.font = `${format === 'story' ? 200 : 160}px serif`
    ctx.fillText(countryFlag.value, W / 2, heroY - 20)
    ctx.font = `bold ${format === 'story' ? 190 : 150}px -apple-system, sans-serif`
    ctx.fillStyle = 'white'
    ctx.fillText(formattedValue.value, W / 2, heroY + 200)
    ctx.font = 'bold 52px -apple-system, sans-serif'
    ctx.fillStyle = accent
    ctx.fillText(indicatorLabel.value.toUpperCase(), W / 2, heroY + 285)
    if (data.country_code) {
      ctx.font = '40px monospace'
      ctx.fillStyle = 'rgba(255,255,255,0.25)'
      ctx.fillText(String(data.country_code), W / 2, heroY + 345)
    }
  } else if (type === 'trade_update') {
    ctx.font = `${format === 'story' ? 180 : 140}px serif`
    ctx.fillText(`${tradeExporterFlag.value}  ↔  ${tradeImporterFlag.value}`, W / 2, heroY)
    ctx.font = `bold ${format === 'story' ? 180 : 140}px -apple-system, sans-serif`
    ctx.fillStyle = 'white'
    ctx.fillText(`$${tradeValueB.value}B`, W / 2, heroY + 200)
    ctx.font = 'bold 44px monospace'
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.fillText(`${data.year || ''} BILATERAL TRADE`, W / 2, heroY + 280)
  } else {
    ctx.font = `${format === 'story' ? 200 : 160}px serif`
    ctx.fillText(blogEmoji.value, W / 2, heroY)
    ctx.font = 'bold 56px -apple-system, sans-serif'
    ctx.fillStyle = accent
    ctx.fillText(typeLabel.value.toUpperCase(), W / 2, heroY + 100)
  }

  // Title (word-wrapped)
  ctx.textAlign = 'center'
  ctx.textBaseline = 'alphabetic'
  const titleY = format === 'story' ? H * 0.72 : H * 0.73
  ctx.font = `bold ${format === 'story' ? 70 : 62}px -apple-system, BlinkMacSystemFont, Inter, sans-serif`
  ctx.fillStyle = 'white'
  wrapText(ctx, cleanTitle.value, W / 2, titleY, W - 130, format === 'story' ? 88 : 78)

  // Meta tags row
  const metaY = format === 'story' ? H * 0.86 : H * 0.88
  const tags: string[] = []
  if (data.country_code) tags.push(`${countryFlag.value} ${data.country_code}`)
  if (data.symbol) tags.push(String(data.symbol))
  if (props.event.event_subtype) tags.push(subtypeLabel.value)
  if (tags.length) {
    ctx.font = 'bold 36px -apple-system, sans-serif'
    ctx.fillStyle = 'rgba(255,255,255,0.4)'
    ctx.fillText(tags.join('  ·  '), W / 2, metaY)
  }

  // Importance dots
  const dots = Math.min(5, Math.ceil(importance / 2))
  ctx.font = '36px sans-serif'
  ctx.fillStyle = accent
  ctx.fillText('●'.repeat(dots) + ' ' + importance + '/10', W / 2, metaY + 56)

  // Branding
  ctx.font = `bold ${format === 'story' ? 44 : 36}px -apple-system, sans-serif`
  ctx.fillStyle = '#10b981'
  ctx.fillText('METRICSHOUR', W / 2, H - 72)
  ctx.font = `${format === 'story' ? 34 : 28}px monospace`
  ctx.fillStyle = 'rgba(255,255,255,0.2)'
  ctx.fillText('metricshour.com', W / 2, H - 30)

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('toBlob failed')), 'image/png')
  })
}

function shareAsImage(format: 'story' | 'post') {
  const blob = _cachedBlobs.value[format]
  if (!blob) return  // still pre-generating — button is disabled anyway

  const file = new File([blob], `metricshour-${format}-${props.event.id}.png`, { type: 'image/png' })

  // Call navigator.share SYNCHRONOUSLY from the click handler so the browser
  // never considers the user gesture expired (iOS Safari / Chrome strict mode)
  if (typeof navigator !== 'undefined' && navigator.canShare?.({ files: [file] })) {
    navigator.share({
      files: [file],
      title: cleanTitle.value,
      text: `${cleanTitle.value} — metricshour.com/feed/${props.event.id}`,
    }).catch((err) => {
      if (err?.name !== 'AbortError') {
        // share API not available after all — fall back to download
        _downloadBlob(blob, file.name)
      }
    })
  } else {
    _downloadBlob(blob, file.name)
  }
  showSharePanel.value = false
}

function _downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function handleShare() {
  // Native Web Share API — opens system share sheet on mobile (iOS/Android)
  if (typeof navigator !== 'undefined' && navigator.share) {
    try {
      await navigator.share({ title: cleanTitle.value, url: shareUrl.value })
      return
    } catch (_) { /* user cancelled or not supported */ }
  }
  // Fallback: toggle desktop panel
  showSharePanel.value = !showSharePanel.value
}

async function handleCopy() {
  try {
    // Copy clean frontend URL (not the API redirect URL)
    await navigator.clipboard.writeText(`https://metricshour.com/feed/${props.event.id}`)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (_) {
    // last-resort fallback
    const el = document.createElement('textarea')
    el.value = `https://metricshour.com/feed/${props.event.id}`
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}

// Close share panel on outside click
function closePanelOutside(e: MouseEvent) {
  if (showSharePanel.value) showSharePanel.value = false
}
onMounted(() => document.addEventListener('click', closePanelOutside))
onUnmounted(() => document.removeEventListener('click', closePanelOutside))

// Computed route — used by NuxtLink so navigation is native <a> tag (works in snap scroll on mobile)
const cardRoute = computed(() => {
  const data = eventData.value
  const type = eventType.value

  if (type === 'price_move' && data.symbol)
    return `/stocks/${data.symbol}`
  if ((type === 'indicator_release' || type === 'macro_release' || type === 'central_bank') && data.country_code)
    return `/countries/${data.country_code.toLowerCase()}`
  if (type === 'trade_update' && data.exporter && data.importer)
    return `/trade/${data.exporter}-${data.importer}`
  if (type === 'geopolitical') {
    if (data.exporter && data.importer) return `/trade/${data.exporter}-${data.importer}`
    if (data.country_code) return `/countries/${data.country_code.toLowerCase()}`
    return `/feed/${props.event.id}`
  }
  if (type === 'commodity' || type === 'commodity_move') return '/commodities'
  if (type === 'daily_insight') {
    const et = (data.entity_type || '').toLowerCase()
    if (et === 'stock' && data.symbol) return `/stocks/${data.symbol}`
    if (et === 'country' && data.country_code) return `/countries/${data.country_code.toLowerCase()}`
    if (et === 'trade' && data.exporter && data.importer) return `/trade/${data.exporter}-${data.importer}`
    if (et === 'commodity') return '/commodities'
    return `/feed/${props.event.id}`
  }
  if (type === 'blog') {
    if (props.event.source_url?.includes('/blog/')) {
      const slug = props.event.source_url.split('/blog/')[1]?.replace(/\/$/, '')
      return slug ? `/blog/${slug}` : `/feed/${props.event.id}`
    }
    return `/feed/${props.event.id}`
  }
  if (data.symbol) return `/stocks/${data.symbol}`
  if (data.country_code) return `/countries/${data.country_code.toLowerCase()}`
  return `/feed/${props.event.id}`
})

// ── Actions ───────────────────────────────────────────────────────────────────
async function _interact(type: string) {
  if (!isLoggedIn.value) return
  try { await post(`/api/feed/${props.event.id}/interact`, { interaction_type: type }) } catch {}
}
function handleSave() {
  if (!isLoggedIn.value) { showAuthModal.value = true; return }
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

/* Share panel slide-in */
.share-panel-enter-active,
.share-panel-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.share-panel-enter-from,
.share-panel-leave-to   { opacity: 0; transform: translateX(8px) scale(0.95); }

.share-panel {
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
</style>
