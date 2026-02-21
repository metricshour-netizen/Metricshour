<template>
  <nav class="border-b border-[#1f2937] bg-[#0a0e1a]/95 backdrop-blur-sm sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
      <NuxtLink to="/" class="text-emerald-400 font-bold tracking-tight text-base sm:text-lg">
        METRICSHOUR
      </NuxtLink>

      <!-- Desktop nav (sm+) -->
      <div class="hidden sm:flex items-center gap-4 sm:gap-5 text-sm text-gray-400">
        <NuxtLink to="/feed" class="hover:text-white transition-colors text-emerald-300 font-semibold flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {{ isLoggedIn ? 'For You' : 'Feed' }}
        </NuxtLink>
        <NuxtLink to="/markets" class="hover:text-white transition-colors font-medium">Markets</NuxtLink>
        <NuxtLink to="/countries" class="hover:text-white transition-colors">Countries</NuxtLink>
        <NuxtLink to="/trade" class="hover:text-white transition-colors">Trade</NuxtLink>
        <NuxtLink to="/pricing" class="hover:text-white transition-colors text-emerald-400">Pro →</NuxtLink>

        <template v-if="isLoggedIn && user">
          <div class="flex items-center gap-3">
            <NuxtLink to="/admin/blog" class="text-xs text-gray-500 hover:text-purple-400 transition-colors hidden md:block font-medium" title="Blog CRM">✍️ CRM</NuxtLink>
            <span class="text-xs text-gray-600 hidden md:block truncate max-w-[110px]">{{ user.email }}</span>
            <button class="text-xs text-gray-500 hover:text-red-400 transition-colors" @click="logout">Out</button>
          </div>
        </template>
        <template v-else>
          <button class="text-xs bg-emerald-700 hover:bg-emerald-600 text-white px-3 py-1.5 rounded-lg transition-colors font-semibold" @click="showAuth = true">Sign In</button>
        </template>
      </div>

      <!-- Mobile right: Feed + hamburger -->
      <div class="flex sm:hidden items-center gap-3">
        <NuxtLink to="/feed" class="text-emerald-300 font-semibold text-sm flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {{ isLoggedIn ? 'For You' : 'Feed' }}
        </NuxtLink>
        <button @click="menuOpen = !menuOpen" class="text-gray-400 hover:text-white transition-colors p-1.5 -mr-1.5" aria-label="Menu">
          <svg v-if="!menuOpen" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile dropdown menu -->
    <div v-if="menuOpen" class="sm:hidden border-t border-[#1f2937] bg-[#0a0e1a] px-4 py-2">
      <NuxtLink to="/markets"   @click="menuOpen = false" class="flex items-center justify-between py-3 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Markets <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/countries" @click="menuOpen = false" class="flex items-center justify-between py-3 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Countries <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/trade"     @click="menuOpen = false" class="flex items-center justify-between py-3 text-sm text-gray-300 hover:text-white border-b border-[#1f2937]">Trade <span class="text-gray-600 text-xs">→</span></NuxtLink>
      <NuxtLink to="/pricing"   @click="menuOpen = false" class="flex items-center justify-between py-3 text-sm text-emerald-400 font-semibold border-b border-[#1f2937]">Pro → <span class="text-[10px] bg-emerald-900/40 text-emerald-400 px-2 py-0.5 rounded">Upgrade</span></NuxtLink>
      <div class="py-3">
        <template v-if="isLoggedIn && user">
          <div class="flex items-center justify-between">
            <span class="text-xs text-gray-500 truncate max-w-[200px]">{{ user.email }}</span>
            <button class="text-xs text-gray-500 hover:text-red-400 transition-colors" @click="logout; menuOpen = false">Sign out</button>
          </div>
        </template>
        <template v-else>
          <button class="w-full bg-emerald-700 hover:bg-emerald-600 text-white text-sm font-semibold py-2.5 rounded-lg transition-colors" @click="showAuth = true; menuOpen = false">Sign In</button>
        </template>
      </div>
    </div>
  </nav>

  <AuthModal v-model="showAuth" />
</template>

<script setup lang="ts">
const { isLoggedIn, user, logout } = useAuth()
const showAuth = ref(false)
const menuOpen = ref(false)
</script>
