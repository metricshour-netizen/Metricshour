<template>
  <!-- Full-screen TikTok-style card -->
  <article
    ref="cardEl"
    class="relative w-full h-full flex flex-col overflow-hidden select-none"
    :style="bgStyle"
  >
    <!-- Cover image (R2 URL for blogs) -->
    <img
      v-if="event.image_url"
      :src="event.image_url"
      alt=""
      class="absolute inset-0 w-full h-full object-cover"
      loading="lazy"
    />

    <!-- Gradient overlay — always on so text is readable -->
    <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-black/10" />

    <!-- Content area — sits above gradient -->
    <div class="relative flex flex-col justify-end h-full p-5 pb-6 gap-3">

      <!-- Type badge + time -->
      <div class="flex items-center gap-2">
        <span
          class="text-xs font-bold px-2 py-0.5 rounded-full"
          :class="badgeClass"
        >{{ typeLabel }}</span>
        <span class="text-xs text-gray-400">{{ relativeTime }}</span>
      </div>

      <!-- Title -->
      <h2 class="text-white font-bold text-xl leading-snug line-clamp-3">
        {{ event.title }}
      </h2>

      <!-- Excerpt / body -->
      <p v-if="event.body" class="text-gray-300 text-sm leading-relaxed line-clamp-2">
        {{ event.body }}
      </p>

      <!-- Asset / country tags -->
      <div v-if="hasTags" class="flex flex-wrap gap-1.5">
        <span
          v-for="tag in displayTags"
          :key="tag"
          class="text-xs bg-white/10 text-gray-300 px-2 py-0.5 rounded-full"
        >{{ tag }}</span>
      </div>

      <!-- Actions row -->
      <div class="flex items-center gap-3 pt-1">
        <button
          class="flex items-center gap-1.5 text-sm font-medium transition-colors"
          :class="isSaved ? 'text-emerald-400' : 'text-gray-400 hover:text-emerald-400'"
          @click.stop="handleSave"
        >
          <span>{{ isSaved ? '★' : '☆' }}</span>
          <span class="hidden sm:inline">{{ isSaved ? 'Saved' : 'Save' }}</span>
        </button>

        <button
          class="flex items-center gap-1.5 text-sm text-gray-400 hover:text-yellow-400 transition-colors"
          @click.stop="handleSkip"
        >
          <span>⏭</span>
          <span class="hidden sm:inline">Skip</span>
        </button>

        <a
          v-if="event.source_url"
          :href="externalUrl"
          :target="isExternal ? '_blank' : '_self'"
          class="flex items-center gap-1.5 text-sm text-gray-400 hover:text-blue-400 transition-colors ml-auto"
          @click.stop
        >
          <span class="hidden sm:inline">Open</span>
          <span>↗</span>
        </a>
      </div>
    </div>
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

// ── Background gradient (for non-image cards) ─────────────────────────────────
const GRADIENTS: Record<string, string> = {
  price_move: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #0f2027 100%)',
  indicator_release: 'linear-gradient(135deg, #0a1628 0%, #1a2a4a 50%, #0a1628 100%)',
  trade_update: 'linear-gradient(135deg, #1a1a0a 0%, #2a3a10 50%, #1a1a0a 100%)',
  blog: 'linear-gradient(135deg, #1a0a2a 0%, #2a1a3a 50%, #1a0a2a 100%)',
  macro_release: 'linear-gradient(135deg, #0a1628 0%, #1a2a4a 50%, #0a1628 100%)',
}

const bgStyle = computed(() => {
  if (props.event.image_url) return {}
  const grad = GRADIENTS[props.event.event_type] || GRADIENTS.price_move
  return { background: grad }
})

// ── Badge ─────────────────────────────────────────────────────────────────────
const BADGE_LABELS: Record<string, string> = {
  price_move: 'PRICE MOVE',
  indicator_release: 'MACRO',
  trade_update: 'TRADE',
  blog: 'ARTICLE',
  macro_release: 'MACRO',
}

const BADGE_CLASSES: Record<string, string> = {
  price_move: 'bg-emerald-500/30 text-emerald-300',
  indicator_release: 'bg-blue-500/30 text-blue-300',
  macro_release: 'bg-blue-500/30 text-blue-300',
  trade_update: 'bg-yellow-500/30 text-yellow-300',
  blog: 'bg-purple-500/30 text-purple-300',
}

const typeLabel = computed(() => BADGE_LABELS[props.event.event_type] || props.event.event_type.toUpperCase())
const badgeClass = computed(() => BADGE_CLASSES[props.event.event_type] || 'bg-gray-500/30 text-gray-300')

// ── Time ──────────────────────────────────────────────────────────────────────
const relativeTime = computed(() => {
  const now = Date.now()
  const then = new Date(props.event.published_at).getTime()
  const diff = Math.max(0, now - then)
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
})

// ── Tags ──────────────────────────────────────────────────────────────────────
const hasTags = computed(() =>
  (props.event.related_asset_ids?.length ?? 0) > 0 ||
  (props.event.related_country_ids?.length ?? 0) > 0,
)

const displayTags = computed(() => {
  // We only have IDs — show them as compact tags
  const tags: string[] = []
  const subtype = props.event.event_subtype
  if (subtype) tags.push(subtype.toUpperCase())
  return tags.slice(0, 3)
})

// ── External URL ─────────────────────────────────────────────────────────────
const isExternal = computed(() => {
  const url = props.event.source_url || ''
  return url.startsWith('http')
})

const externalUrl = computed(() => props.event.source_url || '#')

// ── Actions ───────────────────────────────────────────────────────────────────
async function _interact(type: string) {
  if (!isLoggedIn.value) return
  try {
    await post(`/api/feed/${props.event.id}/interact`, { interaction_type: type })
  } catch { /* ignore */ }
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

// Auto-record view when card mounts (visible in viewport)
onMounted(() => {
  if (!isLoggedIn.value) return
  const el = cardEl.value
  if (!el) return
  const obs = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting) {
        _interact('view')
        obs.disconnect()
      }
    },
    { threshold: 0.5 },
  )
  obs.observe(el)
})
</script>
