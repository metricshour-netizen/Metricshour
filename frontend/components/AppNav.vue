<template>
  <nav class="border-b border-[#1f2937] bg-[#0a0e1a]/95 backdrop-blur-sm sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
      <NuxtLink to="/" class="text-emerald-400 font-bold tracking-tight text-lg">
        METRICSHOUR
      </NuxtLink>

      <div class="flex items-center gap-4 sm:gap-5 text-sm text-gray-400">
        <NuxtLink to="/feed" class="hover:text-white transition-colors text-emerald-300 font-semibold flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {{ isLoggedIn ? 'For You' : 'Feed' }}
        </NuxtLink>
        <NuxtLink to="/markets" class="hover:text-white transition-colors font-medium">Markets</NuxtLink>
        <NuxtLink to="/countries" class="hover:text-white transition-colors hidden md:block">Countries</NuxtLink>
        <NuxtLink to="/trade" class="hover:text-white transition-colors hidden md:block">Trade</NuxtLink>
        <NuxtLink to="/pricing" class="hover:text-white transition-colors text-emerald-400 hidden sm:block">Pro →</NuxtLink>

        <!-- Auth area -->
        <template v-if="isLoggedIn && user">
          <div class="flex items-center gap-3">
            <!-- Admin CRM link — visible when logged in -->
            <NuxtLink
              to="/admin/blog"
              class="text-xs text-gray-500 hover:text-purple-400 transition-colors hidden md:block font-medium"
              title="Blog CRM"
            >✍️ CRM</NuxtLink>
            <span class="text-xs text-gray-600 hidden md:block truncate max-w-[110px]">{{ user.email }}</span>
            <button
              class="text-xs text-gray-500 hover:text-red-400 transition-colors"
              @click="logout"
            >Out</button>
          </div>
        </template>
        <template v-else>
          <button
            class="text-xs bg-emerald-700 hover:bg-emerald-600 text-white px-3 py-1.5 rounded-lg transition-colors font-semibold"
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
