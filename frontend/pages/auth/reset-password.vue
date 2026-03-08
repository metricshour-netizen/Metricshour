<template>
  <div class="min-h-screen bg-[#0a0e1a] flex items-center justify-center px-4">
    <div class="w-full max-w-md">
      <NuxtLink to="/" class="flex items-center gap-2 mb-8 text-emerald-400 font-extrabold text-xl tracking-tight hover:text-emerald-300 transition-colors">
        MetricsHour
      </NuxtLink>

      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-8">
        <template v-if="!token">
          <h1 class="text-2xl font-bold text-white mb-2">Invalid link</h1>
          <p class="text-gray-400 text-sm mb-6">This reset link is missing or malformed.</p>
          <NuxtLink to="/auth/forgot-password" class="text-emerald-400 hover:text-emerald-300 text-sm transition-colors">Request a new reset link →</NuxtLink>
        </template>

        <template v-else-if="done">
          <h1 class="text-2xl font-bold text-white mb-2">Password updated</h1>
          <p class="text-gray-400 text-sm mb-6">Your password has been changed. You can now sign in.</p>
          <NuxtLink to="/" class="inline-block bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm px-6 py-3 rounded-lg transition-colors">Go to MetricsHour →</NuxtLink>
        </template>

        <template v-else>
          <h1 class="text-2xl font-bold text-white mb-2">Set new password</h1>
          <p class="text-gray-400 text-sm mb-6">Choose a strong password — at least 8 characters.</p>

          <form @submit.prevent="submit">
            <label class="block text-xs text-gray-400 uppercase tracking-wider mb-2">New password</label>
            <input
              v-model="password"
              type="password"
              required
              minlength="8"
              placeholder="Min. 8 characters"
              class="w-full bg-[#0d1117] border border-[#374151] rounded-lg px-4 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors mb-4"
            />

            <button
              type="submit"
              :disabled="loading"
              class="w-full bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-bold text-sm py-3 rounded-lg transition-colors"
            >
              {{ loading ? 'Saving…' : 'Update password' }}
            </button>

            <p v-if="error" class="text-red-400 text-sm mt-3 text-center">{{ error }}</p>
          </form>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
useSeoMeta({
  title: 'Reset Password — MetricsHour',
  robots: 'noindex',
})
useHead({ link: [{ rel: 'canonical', href: 'https://metricshour.com/auth/reset-password/' }] })

const config = useRuntimeConfig()
const route = useRoute()

// Use ref + onMounted instead of computed: route.query is empty during SSG
// pre-render, so a computed always returns undefined server-side and the
// hydrated DOM never switches to the form state.
const token = ref<string | undefined>(undefined)
onMounted(() => {
  token.value = route.query.token as string | undefined
})

const password = ref('')
const loading = ref(false)
const done = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await $fetch(`${config.public.apiBase}/api/auth/reset-password`, {
      method: 'POST',
      body: { token: token.value, password: password.value },
    })
    done.value = true
  } catch (e: any) {
    error.value = e?.data?.detail || 'Reset link is invalid or has expired.'
  } finally {
    loading.value = false
  }
}
</script>
