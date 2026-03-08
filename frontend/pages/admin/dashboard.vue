<template>
  <main class="max-w-6xl mx-auto px-4 py-8">
    <!-- Auth guard -->
    <div v-if="!isLoggedIn" class="text-center py-20">
      <p class="text-gray-400 mb-4">You must be signed in to access this page.</p>
    </div>
    <div v-else-if="!isAdmin" class="text-center py-20">
      <p class="text-2xl mb-3">🔒</p>
      <p class="text-gray-400 text-sm">Admin access only.</p>
    </div>

    <template v-else>
      <div class="flex items-center justify-between mb-6">
        <h1 class="text-xl font-bold text-white">Admin Dashboard</h1>
        <div class="flex gap-3">
          <NuxtLink to="/admin/blog" class="text-xs text-emerald-400 hover:text-emerald-300 transition-colors">Blog CRM →</NuxtLink>
          <button class="text-xs text-gray-500 hover:text-white transition-colors" @click="refresh">↻ Refresh</button>
        </div>
      </div>

      <div v-if="pending" class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div v-for="i in 4" :key="i" class="h-20 bg-[#111827] rounded-xl animate-pulse" />
      </div>

      <template v-else-if="stats">
        <!-- ── KPI row ─────────────────────────────────────────────────── -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">Total Users</div>
            <div class="text-2xl font-bold text-white tabular-nums">{{ stats.users.total }}</div>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">New (7d)</div>
            <div class="text-2xl font-bold text-emerald-400 tabular-nums">+{{ stats.users.new_7d }}</div>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">Paid Users</div>
            <div class="text-2xl font-bold text-amber-400 tabular-nums">{{ stats.users.paid }}</div>
          </div>
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wider mb-1">Logins (7d)</div>
            <div class="text-2xl font-bold text-sky-400 tabular-nums">{{ stats.logins.total_7d }}</div>
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          <!-- ── Recent logins ────────────────────────────────────────── -->
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
            <h2 class="text-sm font-bold text-white mb-4">Recent Logins</h2>
            <div class="space-y-2">
              <div
                v-for="(l, i) in stats.logins.recent"
                :key="i"
                class="flex items-center justify-between py-2 border-b border-[#1f2937] last:border-0"
              >
                <div class="min-w-0">
                  <div class="text-xs font-medium text-white truncate max-w-[180px]">{{ l.email }}</div>
                  <div class="text-[10px] text-gray-600 font-mono">{{ l.ip || '—' }} · {{ l.method }}</div>
                </div>
                <div class="text-[10px] text-gray-500 shrink-0 ml-2">{{ fmtTime(l.created_at) }}</div>
              </div>
              <div v-if="!stats.logins.recent.length" class="text-xs text-gray-600 py-2">No logins recorded yet.</div>
            </div>
          </div>

          <!-- ── Recent signups ───────────────────────────────────────── -->
          <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
            <h2 class="text-sm font-bold text-white mb-4">Recent Signups</h2>
            <div class="space-y-2">
              <div
                v-for="u in stats.signups"
                :key="u.id"
                class="flex items-center justify-between py-2 border-b border-[#1f2937] last:border-0"
              >
                <div class="min-w-0">
                  <div class="text-xs font-medium text-white truncate max-w-[200px]">{{ u.email }}</div>
                  <div class="text-[10px] text-gray-600">{{ fmtTime(u.created_at) }}</div>
                </div>
                <span
                  class="text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ml-2"
                  :class="u.tier === 'free' ? 'bg-[#1f2937] text-gray-400' : 'bg-emerald-900/40 text-emerald-400'"
                >{{ u.tier }}</span>
              </div>
              <div v-if="!stats.signups.length" class="text-xs text-gray-600 py-2">No signups yet.</div>
            </div>
          </div>
        </div>

        <!-- ── Top pages (7d) ────────────────────────────────────────── -->
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <h2 class="text-sm font-bold text-white mb-4">Top Pages — Last 7 Days</h2>
          <div v-if="stats.top_pages.length" class="space-y-2">
            <div
              v-for="(p, i) in stats.top_pages"
              :key="i"
              class="flex items-center gap-3"
            >
              <span class="text-xs text-gray-600 w-5 text-right tabular-nums">{{ i + 1 }}</span>
              <span
                class="text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0"
                :class="{
                  'bg-sky-900/40 text-sky-400': p.entity_type === 'country',
                  'bg-emerald-900/40 text-emerald-400': p.entity_type === 'stock',
                  'bg-purple-900/40 text-purple-400': p.entity_type === 'trade',
                  'bg-amber-900/40 text-amber-400': p.entity_type === 'commodity',
                }"
              >{{ p.entity_type }}</span>
              <NuxtLink
                :to="pageLink(p)"
                class="text-xs text-white hover:text-emerald-400 transition-colors flex-1 truncate font-mono"
              >{{ p.entity_code }}</NuxtLink>
              <span class="text-xs tabular-nums text-gray-400 shrink-0">{{ p.views.toLocaleString() }} views</span>
              <div class="w-24 h-1.5 bg-[#1f2937] rounded-full overflow-hidden shrink-0">
                <div
                  class="h-full bg-emerald-500 rounded-full"
                  :style="{ width: `${(p.views / stats.top_pages[0].views) * 100}%` }"
                />
              </div>
            </div>
          </div>
          <div v-else class="text-xs text-gray-600">No page views tracked yet — views will appear here after the frontend deploys.</div>
        </div>
      </template>
    </template>
  </main>
</template>

<script setup lang="ts">
import { useAuth } from '~/composables/useAuth'
import { useApi } from '~/composables/useApi'

const { isLoggedIn, isAdmin, token } = useAuth()
const { get } = useApi()

const stats = ref<any>(null)
const pending = ref(true)
const error = ref('')

async function load() {
  if (!isLoggedIn.value || !isAdmin.value) { pending.value = false; return }
  pending.value = true
  try {
    stats.value = await get('/api/admin/stats')
  } catch (e: any) {
    error.value = e?.message || 'Failed to load stats'
  } finally {
    pending.value = false
  }
}

function refresh() { load() }

function fmtTime(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

function pageLink(p: any) {
  if (p.entity_type === 'country') return `/countries/${p.entity_code.toLowerCase()}`
  if (p.entity_type === 'stock') return `/stocks/${p.entity_code}`
  if (p.entity_type === 'trade') return `/trade/${p.entity_code}`
  return '/commodities'
}

useHead({
  title: 'Admin Dashboard — MetricsHour',
  meta: [{ name: 'robots', content: 'noindex, nofollow' }],
})

onMounted(load)
</script>
