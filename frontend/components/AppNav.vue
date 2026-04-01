<template>
  <nav class="border-b border-[#1f2937] bg-[#0a0e1a]/95 backdrop-blur-sm sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
      <NuxtLink to="/" class="text-emerald-400 font-bold tracking-tight text-base sm:text-lg py-3 -my-3 pr-4" @click="logoClick">
        METRICSHOUR
      </NuxtLink>

      <!-- Desktop nav (sm+) -->
      <div class="hidden sm:flex items-center gap-4 sm:gap-5 text-sm text-gray-400">
        <NuxtLink to="/feed/" class="hover:text-white transition-colors text-emerald-300 font-semibold flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {{ isLoggedIn ? 'For You' : 'Feed' }}
        </NuxtLink>
        <NuxtLink to="/markets/" class="hover:text-white transition-colors font-medium">Markets</NuxtLink>
        <NuxtLink to="/countries/" class="hover:text-white transition-colors">Countries</NuxtLink>
        <NuxtLink to="/trade/" class="hover:text-white transition-colors">Trade</NuxtLink>
        <NuxtLink to="/sectors/" class="hover:text-white transition-colors">Sectors</NuxtLink>
        <NuxtLink to="/commodities/" class="hover:text-white transition-colors">Commodities</NuxtLink>
        <NuxtLink to="/crypto/" class="hover:text-white transition-colors">Crypto</NuxtLink>
        <NuxtLink to="/etfs/" class="hover:text-white transition-colors">ETFs</NuxtLink>
        <NuxtLink to="/fx/" class="hover:text-white transition-colors">FX</NuxtLink>
        <NuxtLink to="/rates/" class="hover:text-white transition-colors">Rates</NuxtLink>
        <NuxtLink to="/earnings/" class="hover:text-white transition-colors">Earnings</NuxtLink>
        <NuxtLink to="/screener/" class="hover:text-white transition-colors text-amber-400/80">Screener</NuxtLink>

        <template v-if="isLoggedIn && user">
          <div class="flex items-center gap-3">
            <NuxtLink to="/watchlist" class="text-xs text-gray-400 hover:text-white transition-colors font-medium" title="Watchlist">⭐ Watchlist</NuxtLink>
            <NuxtLink to="/alerts" class="text-xs text-amber-400 hover:text-amber-300 transition-colors font-medium" title="Price Alerts">🔔 Alerts</NuxtLink>
            <NuxtLink v-if="user?.is_admin" to="/admin/dashboard" class="text-xs text-gray-500 hover:text-purple-400 transition-colors hidden md:block font-medium" title="Admin">⚙️ Admin</NuxtLink>
            <NuxtLink v-if="user?.is_admin" to="/admin/blog" class="text-xs text-gray-500 hover:text-purple-400 transition-colors hidden md:block font-medium" title="Blog CRM">✍️ CRM</NuxtLink>
            <span class="text-xs text-gray-600 hidden md:block truncate max-w-[110px]">{{ user.email }}</span>
            <button class="text-xs text-gray-500 hover:text-red-400 transition-colors" @click="logout">Out</button>
          </div>
        </template>
        <template v-else>
          <NuxtLink to="/login/" class="text-xs text-gray-300 hover:text-white transition-colors font-medium">Sign In</NuxtLink>
          <NuxtLink to="/join/" class="text-xs bg-emerald-700 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg transition-colors font-semibold">Join Free</NuxtLink>
        </template>
        <!-- Search trigger -->
        <button
          @click="searchOpen = true"
          class="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 border border-[#1f2937] hover:border-[#374151] px-2.5 py-1.5 rounded-lg transition-colors font-mono"
          title="Search (press /)"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
          </svg>
          <span class="hidden md:inline">Search</span>
          <kbd class="hidden md:inline-flex items-center px-1 py-0.5 rounded border border-[#374151] bg-[#0d1117] text-gray-600 text-[10px]">/</kbd>
        </button>
        <!-- Dark/light toggle -->
        <button class="text-lg leading-none" :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'" @click="toggleTheme">{{ isDark ? '☀️' : '🌙' }}</button>
      </div>

      <!-- Mobile right: search + Feed + hamburger -->
      <div class="flex sm:hidden items-center gap-3">
        <button @click="searchOpen = true" class="text-gray-400 hover:text-white transition-colors p-1" aria-label="Search">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
          </svg>
        </button>
        <NuxtLink to="/feed/" class="text-emerald-300 font-semibold text-sm flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {{ isLoggedIn ? 'For You' : 'Feed' }}
        </NuxtLink>
        <button @click="menuOpen = !menuOpen" class="text-gray-400 hover:text-white transition-colors p-2 -mr-2" aria-label="Menu">
          <svg v-if="!menuOpen" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
          <svg v-else class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile dropdown menu -->
    <div v-if="menuOpen" class="sm:hidden border-t border-[#1f2937] bg-[#0a0e1a] px-4 py-2">
      <NuxtLink to="/"            @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-emerald-400 font-semibold border-b border-[#1f2937]">Home <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/markets/"     @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Markets <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/countries/"   @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Countries <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/trade/"       @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Trade <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/sectors/"     @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Sectors <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/commodities/" @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Commodities <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/crypto/"     @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Crypto <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/etfs/"       @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">ETFs <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/fx/"         @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">FX <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/rates/"      @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Rates <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/earnings/"   @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Earnings <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/screener/"   @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-amber-400/80 hover:text-white border-b border-[#1f2937]">Screener <span class="text-gray-600 text-xs">→</span></NuxtLink>
<template v-if="isLoggedIn && user">
        <NuxtLink to="/watchlist"  @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">⭐ Watchlist <span class="text-gray-600 text-xs">→</span></NuxtLink>
        <NuxtLink to="/alerts"    @click="menuOpen = false" class="flex items-center justify-between py-3.5 text-sm text-amber-400 hover:text-amber-300 border-b border-[#1f2937]">🔔 Alerts <span class="text-gray-600 text-xs">→</span></NuxtLink>
      </template>
      <div class="py-3 space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-600">Appearance</span>
          <button
            class="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white border border-[#1f2937] px-3 py-1.5 rounded-lg transition-colors"
            @click="toggleTheme"
          >{{ isDark ? '☀️ Light' : '🌙 Dark' }}</button>
        </div>
        <template v-if="isLoggedIn && user">
          <div class="flex items-center justify-between">
            <span class="text-xs text-gray-500 truncate max-w-[200px]">{{ user.email }}</span>
            <button class="text-xs text-gray-500 hover:text-red-400 transition-colors" @click="logout(); menuOpen = false">Sign out</button>
          </div>
        </template>
        <template v-else>
          <div class="flex gap-2">
            <NuxtLink to="/login/" @click="menuOpen = false" class="flex-1 text-center text-sm text-gray-300 border border-[#1f2937] py-2.5 rounded-lg transition-colors hover:text-white font-medium">Sign In</NuxtLink>
            <NuxtLink to="/join/" @click="menuOpen = false" class="flex-1 text-center bg-emerald-700 hover:bg-emerald-600 text-white text-sm font-semibold py-2.5 rounded-lg transition-colors">Join Free</NuxtLink>
          </div>
        </template>
      </div>
    </div>
  </nav>

  <AuthModal v-model="showAuth" />
  <SearchModal v-model="searchOpen" />
</template>

<script setup lang="ts">
const { isLoggedIn, user, logout } = useAuth()
const showAuth = ref(false)
const menuOpen = ref(false)
const searchOpen = ref(false)
const route = useRoute()

function logoClick() {
  menuOpen.value = false
  if (route.path === '/') window.scrollTo({ top: 0, behavior: 'smooth' })
}

const isDark = ref(true)
onMounted(() => {
  isDark.value = localStorage.getItem('theme') !== 'light'
  document.documentElement.classList.toggle('light-mode', !isDark.value)

  // Global "/" shortcut opens search from any page
  document.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
      e.preventDefault()
      searchOpen.value = true
    }
  })
})
function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
  document.documentElement.classList.toggle('light-mode', !isDark.value)
}
</script>
