<template>
  <!-- Full-viewport TikTok-style feed container -->
  <div class="fixed inset-0 flex flex-col bg-black" style="top: 48px;">

    <!-- Not-logged-in banner (dismissable) -->
    <Transition name="slide-down">
      <div
        v-if="!isLoggedIn && showBanner"
        class="bg-[#0d1117] border-b border-[#1f2937] px-4 py-2 flex items-center justify-between gap-3 flex-shrink-0 z-10"
      >
        <p class="text-xs text-gray-400">
          <span class="text-emerald-400 font-medium">Sign in</span> to personalise your feed — events you follow rank higher.
        </p>
        <div class="flex items-center gap-2 shrink-0">
          <button
            class="text-xs bg-emerald-700 hover:bg-emerald-600 text-white px-3 py-1 rounded-lg transition-colors"
            @click="showAuth = true"
          >Sign In</button>
          <button class="text-gray-600 hover:text-gray-400 text-xs" @click="showBanner = false">✕</button>
        </div>
      </div>
    </Transition>

    <!-- Snap scroll container -->
    <div
      ref="scrollEl"
      class="flex-1 overflow-y-scroll snap-y snap-mandatory"
      style="-webkit-overflow-scrolling: touch; scroll-snap-type: y mandatory;"
      @scroll.passive="onScroll"
    >
      <!-- Each card fills exactly the viewport height -->
      <div
        v-for="(event, idx) in visibleEvents"
        :key="event.id"
        class="snap-start"
        :style="cardStyle"
      >
        <FeedCard
          :event="event"
          @save="onSave"
          @skip="onSkip(event.id, idx)"
        />
      </div>

      <!-- Load more trigger -->
      <div
        v-if="hasMore"
        ref="loadMoreEl"
        class="snap-start flex items-center justify-center"
        :style="cardStyle"
      >
        <button
          class="text-emerald-400 text-sm font-medium hover:text-emerald-300 transition-colors"
          @click="loadMore"
        >
          {{ loadingMore ? 'Loading…' : 'Load more →' }}
        </button>
      </div>

      <!-- Empty state -->
      <div
        v-if="!pending && visibleEvents.length === 0"
        class="snap-start flex flex-col items-center justify-center text-center p-8"
        :style="cardStyle"
      >
        <div class="text-4xl mb-4">📊</div>
        <h2 class="text-white font-bold text-lg mb-2">Feed loading up</h2>
        <p class="text-gray-500 text-sm max-w-xs">
          Market events appear here as they happen. Run the feed seeder to populate initial events.
        </p>
        <button
          v-if="!isLoggedIn"
          class="mt-4 text-xs bg-emerald-700 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg transition-colors"
          @click="showAuth = true"
        >Sign in to personalise</button>
      </div>

      <!-- Loading state -->
      <div
        v-if="pending"
        class="snap-start flex flex-col items-center justify-center"
        :style="cardStyle"
      >
        <div class="animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full mb-3" />
        <p class="text-gray-500 text-xs">Loading your feed…</p>
      </div>
    </div>

    <!-- Floating follows sidebar (desktop only) -->
    <div
      v-if="isLoggedIn && follows.length"
      class="hidden xl:flex fixed right-4 top-20 flex-col gap-2 z-20 w-48"
    >
      <div class="bg-[#0d1117]/90 backdrop-blur border border-[#1f2937] rounded-xl p-3">
        <p class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2">Following</p>
        <div class="space-y-1">
          <div
            v-for="f in follows.slice(0, 8)"
            :key="f.id"
            class="flex items-center justify-between gap-2"
          >
            <span class="text-xs text-gray-300 truncate">
              {{ f.entity_type === 'asset' ? '📈' : '🌍' }} {{ f.entity_id }}
            </span>
            <button
              class="text-xs text-gray-600 hover:text-red-400 transition-colors"
              @click="unfollow(f.entity_type, f.entity_id)"
            >✕</button>
          </div>
        </div>
      </div>
    </div>
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
}

interface Follow {
  id: number
  entity_type: string
  entity_id: number
  followed_at: string
}

const { get, del } = useApi()
const { isLoggedIn } = useAuth()

const showAuth = ref(false)
const showBanner = ref(true)

// ── Feed state ────────────────────────────────────────────────────────────────
const allEvents = ref<FeedEvent[]>([])
const skippedIds = ref<Set<number>>(new Set())
const page = ref(1)
const hasMore = ref(true)
const loadingMore = ref(false)
const pending = ref(true)

const visibleEvents = computed(() =>
  allEvents.value.filter(e => !skippedIds.value.has(e.id)),
)

// ── Card sizing ───────────────────────────────────────────────────────────────
// Cards fill the area below the nav (48px) and optional banner
const bannerH = computed(() => (!isLoggedIn.value && showBanner.value ? 40 : 0))

const cardStyle = computed(() => ({
  height: `calc(100vh - 48px - ${bannerH.value}px)`,
  minHeight: `calc(100vh - 48px - ${bannerH.value}px)`,
}))

// ── Load feed ─────────────────────────────────────────────────────────────────
async function fetchPage(p: number) {
  try {
    const data = await get<{ page: number; page_size: number; events: FeedEvent[] }>(
      '/api/feed',
      { page: p, page_size: 20 },
    )
    allEvents.value.push(...data.events)
    hasMore.value = data.events.length === 20
  } catch (e) {
    hasMore.value = false
  }
}

async function loadMore() {
  if (loadingMore.value) return
  loadingMore.value = true
  page.value++
  await fetchPage(page.value)
  loadingMore.value = false
}

// ── Actions ───────────────────────────────────────────────────────────────────
function onSave(id: number) { /* FeedCard handles the API call */ }

function onSkip(id: number, idx: number) {
  skippedIds.value.add(id)
}

// ── Scroll → load more when near bottom ──────────────────────────────────────
const scrollEl = ref<HTMLElement | null>(null)

function onScroll() {
  const el = scrollEl.value
  if (!el || loadingMore.value || !hasMore.value) return
  const nearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - el.clientHeight * 1.5
  if (nearBottom) loadMore()
}

// ── Follows sidebar ───────────────────────────────────────────────────────────
const follows = ref<Follow[]>([])

async function loadFollows() {
  if (!isLoggedIn.value) return
  try {
    follows.value = await get<Follow[]>('/api/feed/follows')
  } catch { /* not logged in or network error */ }
}

async function unfollow(entityType: string, entityId: number) {
  try {
    await del(`/api/feed/follows/${entityType}/${entityId}`)
    follows.value = follows.value.filter(
      f => !(f.entity_type === entityType && f.entity_id === entityId),
    )
  } catch { /* ignore */ }
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(async () => {
  pending.value = true
  await fetchPage(1)
  pending.value = false
  await loadFollows()
})

// Reload feed when user logs in
watch(isLoggedIn, async (loggedIn) => {
  if (loggedIn) {
    allEvents.value = []
    page.value = 1
    hasMore.value = true
    skippedIds.value.clear()
    pending.value = true
    await fetchPage(1)
    pending.value = false
    await loadFollows()
  }
})

useSeoMeta({
  title: 'For You — MetricsHour',
  description: 'Personalised market feed — price moves, macro releases, and analyst articles ranked for you.',
})
</script>

<style scoped>
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.2s ease;
}
.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}
</style>
