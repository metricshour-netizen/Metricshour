<template>
  <div class="feed-viewport fixed inset-0 bg-black" style="top: 48px;">

    <!-- "For You" label (top left, logged in only) -->
    <Transition name="fade">
      <div
        v-if="isLoggedIn"
        class="fixed top-[52px] left-4 z-30 pointer-events-none"
      >
        <span class="text-[10px] font-black uppercase tracking-[0.2em] text-white/25">For You</span>
      </div>
    </Transition>

    <!-- Scroll dot progress (right edge, desktop) -->
    <div
      v-if="visibleEvents.length > 1"
      class="hidden sm:flex fixed right-3 top-1/2 -translate-y-1/2 flex-col gap-1.5 z-30"
    >
      <div
        v-for="(_, i) in Math.min(visibleEvents.length, 12)"
        :key="i"
        class="w-1 rounded-full transition-all duration-300 cursor-pointer"
        :class="i === activeIndex ? 'h-5 opacity-100' : 'h-1.5 opacity-25'"
        :style="i === activeIndex ? { background: activeAccent } : { background: 'white' }"
        @click="scrollToCard(i)"
      />
    </div>

    <!-- Snap scroll container -->
    <div
      ref="scrollEl"
      class="h-full overflow-y-scroll snap-y snap-mandatory"
      style="-webkit-overflow-scrolling: touch; scrollbar-width: none;"
      @scroll.passive="onScroll"
    >

      <!-- Feed cards -->
      <div
        v-for="(event, idx) in visibleEvents"
        :key="event.id"
        class="snap-start snap-always"
        :style="cardStyle"
      >
        <FeedCard
          :event="event"
          @save="onSave"
          @skip="onSkip(event.id)"
        />
      </div>

      <!-- Load more card -->
      <div
        v-if="hasMore && !pending"
        class="snap-start snap-always flex items-center justify-center"
        :style="cardStyle"
      >
        <button
          class="group flex flex-col items-center gap-3"
          @click="loadMore"
        >
          <div class="w-14 h-14 rounded-full border border-white/20 flex items-center justify-center text-2xl group-hover:border-emerald-500 transition-colors">
            {{ loadingMore ? '…' : '↓' }}
          </div>
          <span class="text-xs text-white/40 group-hover:text-white/70 transition-colors">
            {{ loadingMore ? 'Loading…' : 'Load more' }}
          </span>
        </button>
      </div>

      <!-- Empty state -->
      <div
        v-if="!pending && visibleEvents.length === 0"
        class="snap-start flex flex-col items-center justify-center text-center p-8"
        :style="cardStyle"
        style="background: #030303;"
      >
        <div class="text-6xl mb-5">📡</div>
        <h2 class="text-white font-bold text-xl mb-2">Feed is warming up</h2>
        <p class="text-white/40 text-sm max-w-xs leading-relaxed">
          Market events will appear as prices move and indicators update.
        </p>
      </div>

      <!-- Loading -->
      <div
        v-if="pending"
        class="snap-start flex flex-col items-center justify-center gap-4"
        :style="cardStyle"
        style="background: #030303;"
      >
        <div class="relative w-12 h-12">
          <div class="absolute inset-0 rounded-full border-2 border-emerald-500/20" />
          <div class="absolute inset-0 rounded-full border-2 border-transparent border-t-emerald-500 animate-spin" />
        </div>
        <p class="text-white/30 text-xs tracking-widest uppercase">Loading feed</p>
      </div>

    </div>

    <!-- Auth pill (bottom centre, only when not logged in) -->
    <Transition name="fade-up">
      <div
        v-if="!isLoggedIn && showAuthPill"
        class="fixed bottom-6 left-1/2 -translate-x-1/2 z-30"
      >
        <button
          class="auth-pill flex items-center gap-2.5 px-5 py-3 rounded-full text-sm font-semibold text-white shadow-2xl"
          @click="showAuth = true"
        >
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
          Sign in for your personalised feed
          <span class="text-white/60 text-xs ml-1">→</span>
        </button>
      </div>
    </Transition>

  </div>

  <AuthModal v-model="showAuth" />
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

const { get, del } = useApi()
const { isLoggedIn } = useAuth()

const showAuth = ref(false)
const showAuthPill = ref(false)

// Show auth pill after 3 seconds
onMounted(() => { setTimeout(() => { showAuthPill.value = true }, 3000) })

// ── Feed state ────────────────────────────────────────────────────────────────
const allEvents = ref<FeedEvent[]>([])
const skippedIds = ref<Set<number>>(new Set())
const page = ref(1)
const hasMore = ref(true)
const loadingMore = ref(false)
const pending = ref(true)
const activeIndex = ref(0)

const visibleEvents = computed(() =>
  allEvents.value.filter(e => !skippedIds.value.has(e.id)),
)

const ACCENT: Record<string, string> = {
  price_move: '#10b981', indicator_release: '#3b82f6', macro_release: '#3b82f6',
  trade_update: '#f59e0b', blog: '#a855f7',
}
const activeAccent = computed(() => {
  const ev = visibleEvents.value[activeIndex.value]
  return ev ? (ACCENT[ev.event_type] || '#6b7280') : '#10b981'
})

// ── Card height ───────────────────────────────────────────────────────────────
const cardStyle = computed(() => ({
  height: 'calc(100vh - 48px)',
  minHeight: 'calc(100vh - 48px)',
}))

// ── Fetch ─────────────────────────────────────────────────────────────────────
async function fetchPage(p: number) {
  try {
    const data = await get<{ page: number; page_size: number; events: FeedEvent[] }>(
      '/api/feed', { page: p, page_size: 20 },
    )
    allEvents.value.push(...data.events)
    hasMore.value = data.events.length === 20
  } catch { hasMore.value = false }
}

async function loadMore() {
  if (loadingMore.value) return
  loadingMore.value = true
  page.value++
  await fetchPage(page.value)
  loadingMore.value = false
}

// ── Scroll tracking ───────────────────────────────────────────────────────────
const scrollEl = ref<HTMLElement | null>(null)
const cardRefs = ref<HTMLElement[]>([])

function onScroll() {
  const el = scrollEl.value
  if (!el) return
  const cardH = el.clientHeight
  activeIndex.value = Math.round(el.scrollTop / cardH)

  // Load more near end
  if (!loadingMore.value && hasMore.value) {
    const nearBottom = el.scrollTop + cardH >= el.scrollHeight - cardH * 2
    if (nearBottom) loadMore()
  }
}

function scrollToCard(idx: number) {
  const el = scrollEl.value
  if (!el) return
  el.scrollTo({ top: idx * el.clientHeight, behavior: 'smooth' })
}

// ── Actions ───────────────────────────────────────────────────────────────────
function onSave(_id: number) {}
function onSkip(id: number) { skippedIds.value.add(id) }

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(async () => {
  pending.value = true
  await fetchPage(1)
  pending.value = false
})

watch(isLoggedIn, async (v) => {
  if (v) {
    allEvents.value = []
    page.value = 1
    hasMore.value = true
    skippedIds.value.clear()
    activeIndex.value = 0
    pending.value = true
    await fetchPage(1)
    pending.value = false
    showAuthPill.value = false
  }
})

useSeoMeta({
  title: computed(() => isLoggedIn.value ? 'For You — MetricsHour' : 'Feed — MetricsHour'),
  description: 'Personalised market intelligence feed. Price moves, macro releases, and trade updates ranked for you.',
})
</script>

<style scoped>
/* Hide scrollbar */
.feed-viewport ::-webkit-scrollbar { display: none; }

.auth-pill {
  background: linear-gradient(135deg, rgba(16,185,129,0.2) 0%, rgba(59,130,246,0.2) 100%);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.5s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.fade-up-enter-active, .fade-up-leave-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.fade-up-enter-from, .fade-up-leave-to {
  opacity: 0;
  transform: translate(-50%, 16px);
}
</style>
