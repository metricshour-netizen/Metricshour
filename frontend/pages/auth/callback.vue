<template>
  <div class="min-h-screen bg-[#0a0e1a] flex items-center justify-center">
    <div class="text-center">
      <div v-if="error" class="space-y-3">
        <div class="text-4xl">❌</div>
        <p class="text-white font-semibold">Sign in failed</p>
        <p class="text-gray-500 text-sm">{{ errorMessage }}</p>
        <NuxtLink to="/" class="inline-block text-sm text-emerald-400 hover:text-emerald-300 transition-colors mt-2">← Back to MetricsHour</NuxtLink>
      </div>
      <div v-else class="space-y-3">
        <div class="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        <p class="text-gray-400 text-sm">Signing you in…</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
useSeoMeta({ robots: 'noindex, nofollow' })

const route = useRoute()
const { loginWithToken } = useAuth()

const error = ref(false)
const errorMessage = ref('')

const ERROR_MESSAGES: Record<string, string> = {
  invalid_state: 'Security check failed. Please try again.',
  token_exchange_failed: 'Could not connect to Google. Please try again.',
  userinfo_failed: 'Could not retrieve your Google account info.',
  no_email: 'No email address found in your Google account.',
  cancelled: 'Sign-in was cancelled.',
  access_denied: 'Access was denied. Please try again.',
}

onMounted(async () => {
  const token = route.query.token as string
  const err = route.query.error as string

  if (err) {
    error.value = true
    errorMessage.value = ERROR_MESSAGES[err] || 'Something went wrong. Please try again.'
    return
  }

  if (!token) {
    error.value = true
    errorMessage.value = 'No token received.'
    return
  }

  await loginWithToken(token)
  navigateTo('/')
})
</script>
