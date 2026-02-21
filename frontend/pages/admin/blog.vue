<template>
  <main class="max-w-5xl mx-auto px-4 py-8">
    <!-- Auth guard -->
    <div v-if="!isLoggedIn" class="text-center py-20">
      <p class="text-gray-400 mb-4">You must be signed in to access the admin panel.</p>
      <button
        class="bg-emerald-700 hover:bg-emerald-600 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        @click="showAuth = true"
      >Sign In</button>
      <AuthModal v-model="showAuth" />
    </div>

    <template v-else>
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-xl font-bold text-white">Blog CRM</h1>
        <button
          class="text-sm bg-emerald-700 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg transition-colors"
          @click="openNew"
        >+ New Post</button>
      </div>

      <!-- Error -->
      <div v-if="error" class="text-red-400 text-sm mb-4 bg-red-900/20 border border-red-900/40 rounded-lg px-4 py-3">{{ error }}</div>

      <!-- List -->
      <div class="space-y-3 mb-8">
        <div
          v-for="post in posts"
          :key="post.id"
          class="bg-[#111827] border border-[#1f2937] rounded-xl p-4 flex items-start justify-between gap-4"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span
                class="text-xs font-bold px-2 py-0.5 rounded-full"
                :class="post.status === 'published' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-gray-500/20 text-gray-400'"
              >{{ post.status.toUpperCase() }}</span>
              <span class="text-xs text-gray-500">Score: {{ post.importance_score }}/10</span>
              <span v-if="post.published_at" class="text-xs text-gray-600">{{ fmtDate(post.published_at) }}</span>
            </div>
            <h3 class="text-white font-medium text-sm truncate">{{ post.title }}</h3>
            <p v-if="post.excerpt" class="text-gray-500 text-xs mt-1 line-clamp-1">{{ post.excerpt }}</p>
          </div>

          <div class="flex items-center gap-2 shrink-0">
            <button
              class="text-xs text-gray-400 hover:text-white border border-[#1f2937] hover:border-gray-500 px-3 py-1.5 rounded-lg transition-colors"
              @click="openEdit(post)"
            >Edit</button>
            <button
              v-if="post.status === 'draft'"
              class="text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-900/60 hover:border-emerald-500 px-3 py-1.5 rounded-lg transition-colors"
              :disabled="publishing === post.id"
              @click="publishPost(post.id)"
            >{{ publishing === post.id ? '…' : 'Publish' }}</button>
            <a
              v-if="post.status === 'published'"
              :href="`/blog/${post.slug}`"
              target="_blank"
              class="text-xs text-blue-400 hover:text-blue-300 border border-blue-900/60 px-3 py-1.5 rounded-lg transition-colors"
            >View ↗</a>
            <button
              v-if="post.status === 'draft'"
              class="text-xs text-red-500 hover:text-red-400 border border-red-900/40 px-3 py-1.5 rounded-lg transition-colors"
              :disabled="deleting === post.id"
              @click="deletePost(post.id)"
            >{{ deleting === post.id ? '…' : 'Delete' }}</button>
          </div>
        </div>

        <div v-if="!loadingPosts && posts.length === 0" class="text-center py-12 text-gray-600 text-sm">
          No posts yet. Create your first article.
        </div>
        <div v-if="loadingPosts" class="space-y-3">
          <div v-for="i in 3" :key="i" class="h-20 bg-[#111827] rounded-xl animate-pulse" />
        </div>
      </div>

      <!-- Form panel (create / edit) -->
      <div v-if="formOpen" class="bg-[#0d1117] border border-[#1f2937] rounded-2xl p-6">
        <h2 class="text-white font-bold text-base mb-5">
          {{ editingPost ? 'Edit Post' : 'New Post' }}
        </h2>

        <form @submit.prevent="savePost" class="space-y-4">
          <div>
            <label class="text-xs text-gray-500 block mb-1">Title</label>
            <input
              v-model="form.title"
              required
              placeholder="Article title"
              class="w-full bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-2 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>

          <div>
            <label class="text-xs text-gray-500 block mb-1">Body</label>
            <textarea
              v-model="form.body"
              required
              rows="10"
              placeholder="Write your article here…"
              class="w-full bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-2 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors resize-y"
            />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-xs text-gray-500 block mb-1">Excerpt (optional — auto-generated if blank)</label>
              <textarea
                v-model="form.excerpt"
                rows="2"
                placeholder="Short summary…"
                class="w-full bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-2 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
              />
            </div>
            <div>
              <label class="text-xs text-gray-500 block mb-1">Author name</label>
              <input
                v-model="form.author_name"
                placeholder="MetricsHour Team"
                class="w-full bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-2 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
              />
            </div>
          </div>

          <div>
            <label class="text-xs text-gray-500 block mb-1">Importance score (0–10)</label>
            <input
              v-model.number="form.importance_score"
              type="number" min="0" max="10" step="0.5"
              class="w-32 bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>

          <!-- Cover image upload -->
          <div v-if="editingPost">
            <label class="text-xs text-gray-500 block mb-1">Cover image</label>
            <div class="flex items-center gap-3">
              <img v-if="editingPost.cover_image_url" :src="editingPost.cover_image_url" class="w-16 h-10 object-cover rounded" />
              <input
                ref="fileInput"
                type="file"
                accept="image/*"
                class="text-xs text-gray-400"
                @change="uploadCover"
              />
              <span v-if="uploading" class="text-xs text-gray-500">Uploading…</span>
            </div>
          </div>

          <div v-if="formError" class="text-red-400 text-xs bg-red-900/20 border border-red-900/40 rounded-lg px-3 py-2">{{ formError }}</div>

          <div class="flex items-center gap-3">
            <button
              type="submit"
              :disabled="saving"
              class="bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
            >{{ saving ? 'Saving…' : (editingPost ? 'Save Changes' : 'Create Draft') }}</button>
            <button
              type="button"
              class="text-gray-500 hover:text-gray-300 text-sm transition-colors"
              @click="formOpen = false; editingPost = null"
            >Cancel</button>
          </div>
        </form>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
interface BlogPost {
  id: number
  title: string
  slug: string
  body: string
  excerpt?: string
  cover_image_url?: string
  author_name: string
  status: string
  importance_score: number
  published_at?: string
  created_at: string
  feed_event_id?: number
}

const { get, post: apiPost, put, del } = useApi()
const { isLoggedIn } = useAuth()

const showAuth = ref(false)
const posts = ref<BlogPost[]>([])
const loadingPosts = ref(false)
const error = ref('')
const publishing = ref<number | null>(null)
const deleting = ref<number | null>(null)

// ── Form ──────────────────────────────────────────────────────────────────────
const formOpen = ref(false)
const editingPost = ref<BlogPost | null>(null)
const saving = ref(false)
const formError = ref('')
const uploading = ref(false)

const form = reactive({
  title: '',
  body: '',
  excerpt: '',
  author_name: 'MetricsHour Team',
  importance_score: 5,
})

function resetForm() {
  form.title = ''
  form.body = ''
  form.excerpt = ''
  form.author_name = 'MetricsHour Team'
  form.importance_score = 5
}

function openNew() {
  editingPost.value = null
  resetForm()
  formOpen.value = true
  formError.value = ''
}

function openEdit(p: BlogPost) {
  editingPost.value = p
  form.title = p.title
  form.body = p.body
  form.excerpt = p.excerpt || ''
  form.author_name = p.author_name
  form.importance_score = p.importance_score
  formOpen.value = true
  formError.value = ''
}

async function savePost() {
  saving.value = true
  formError.value = ''
  try {
    const payload = {
      title: form.title,
      body: form.body,
      excerpt: form.excerpt || null,
      author_name: form.author_name,
      importance_score: form.importance_score,
    }
    if (editingPost.value) {
      const updated = await put<BlogPost>(`/api/admin/blogs/${editingPost.value.id}`, payload)
      const idx = posts.value.findIndex(p => p.id === editingPost.value!.id)
      if (idx !== -1) posts.value[idx] = updated
    } else {
      const created = await apiPost<BlogPost>('/api/admin/blogs', payload)
      posts.value.unshift(created)
      editingPost.value = created
    }
    formOpen.value = false
    editingPost.value = null
  } catch (e: any) {
    formError.value = e.message || 'Save failed'
  } finally {
    saving.value = false
  }
}

async function publishPost(id: number) {
  publishing.value = id
  error.value = ''
  try {
    const updated = await apiPost<BlogPost>(`/api/admin/blogs/${id}/publish`, {})
    const idx = posts.value.findIndex(p => p.id === id)
    if (idx !== -1) posts.value[idx] = updated
  } catch (e: any) {
    error.value = e.message || 'Publish failed'
  } finally {
    publishing.value = null
  }
}

async function deletePost(id: number) {
  if (!confirm('Delete this draft?')) return
  deleting.value = id
  error.value = ''
  try {
    await del(`/api/admin/blogs/${id}`)
    posts.value = posts.value.filter(p => p.id !== id)
  } catch (e: any) {
    error.value = e.message || 'Delete failed'
  } finally {
    deleting.value = null
  }
}

// ── Cover upload ──────────────────────────────────────────────────────────────
const fileInput = ref<HTMLInputElement | null>(null)
const config = useRuntimeConfig()

async function uploadCover(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file || !editingPost.value) return
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  const TOKEN_KEY = 'mh_auth_token'
  const token = import.meta.client ? localStorage.getItem(TOKEN_KEY) : null
  try {
    const res = await fetch(`${config.public.apiBase}/api/admin/blogs/${editingPost.value.id}/cover`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    })
    if (!res.ok) throw new Error('Upload failed')
    const data = await res.json()
    editingPost.value!.cover_image_url = data.url
    const idx = posts.value.findIndex(p => p.id === editingPost.value!.id)
    if (idx !== -1) posts.value[idx].cover_image_url = data.url
  } catch (e: any) {
    formError.value = e.message || 'Upload failed'
  } finally {
    uploading.value = false
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function loadPosts() {
  if (!isLoggedIn.value) return
  loadingPosts.value = true
  try {
    posts.value = await get<BlogPost[]>('/api/admin/blogs')
  } catch (e: any) {
    error.value = e.message || 'Failed to load posts'
  } finally {
    loadingPosts.value = false
  }
}

onMounted(loadPosts)
watch(isLoggedIn, (v) => { if (v) loadPosts() })

function fmtDate(iso?: string): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

useSeoMeta({ title: 'Blog Admin — MetricsHour' })
</script>
