<template>
  <nav class="border-b border-[#1f2937] bg-[#0a0e1a] sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
      <NuxtLink to="/" class="text-emerald-400 font-bold tracking-tight text-lg">
        METRICSHOUR
      </NuxtLink>
      <div class="flex items-center gap-4 sm:gap-6 text-sm text-gray-400">
        <NuxtLink to="/feed" class="hover:text-white transition-colors text-emerald-300 font-medium">Feed</NuxtLink>
        <NuxtLink to="/countries" class="hover:text-white transition-colors hidden sm:block">Countries</NuxtLink>
        <NuxtLink to="/stocks" class="hover:text-white transition-colors hidden sm:block">Stocks</NuxtLink>
        <NuxtLink to="/trade" class="hover:text-white transition-colors hidden sm:block">Trade</NuxtLink>
        <NuxtLink to="/commodities" class="hover:text-white transition-colors hidden sm:block">Commodities</NuxtLink>
        <NuxtLink to="/pricing" class="hover:text-white transition-colors text-emerald-400 hidden sm:block">Pro →</NuxtLink>

        <!-- Auth area -->
        <template v-if="isLoggedIn && user">
          <div class="flex items-center gap-2">
            <span class="text-xs text-gray-500 hidden md:block truncate max-w-[120px]">{{ user.email }}</span>
            <button
              class="text-xs text-gray-400 hover:text-red-400 transition-colors"
              @click="logout"
            >Sign Out</button>
          </div>
        </template>
        <template v-else>
          <button
            class="text-xs bg-emerald-700 hover:bg-emerald-600 text-white px-3 py-1.5 rounded-lg transition-colors font-medium"
            @click="showAuth = true"
          >Sign In</button>
        </template>
      </div>
    </div>
  </nav>

  <AuthModal v-model="showAuth" />
</template>

<script setup lang="ts">
const { isLoggedIn, user, logout } = useAuth()
const showAuth = ref(false)
</script>
