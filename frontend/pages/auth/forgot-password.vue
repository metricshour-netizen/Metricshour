<template>
  <div class="min-h-screen bg-[#0a0e1a] flex items-center justify-center px-4">
    <div class="w-full max-w-md">
      <NuxtLink to="/" class="flex items-center gap-2 mb-8 text-emerald-400 font-extrabold text-xl tracking-tight hover:text-emerald-300 transition-colors">
        MetricsHour
      </NuxtLink>

      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-8">
        <h1 class="text-2xl font-bold text-white mb-2">Forgot password</h1>
        <p class="text-gray-400 text-sm mb-6">Enter your email and we'll send a reset link if an account exists.</p>

        <form @submit.prevent="submit">
          <label class="block text-xs text-gray-400 uppercase tracking-wider mb-2">Email</label>
          <input
            v-model="email"
            type="email"
            required
            placeholder="you@example.com"
            class="w-full bg-[#0d1117] border border-[#374151] rounded-lg px-4 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors mb-4"
          />

          <button
            type="submit"
            :disabled="loading || sent"
            class="w-full bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-bold text-sm py-3 rounded-lg transition-colors"
          >
            {{ loading ? 'Sending…' : sent ? 'Email sent ✓' : 'Send reset link' }}
          </button>

          <p v-if="error" class="text-red-400 text-sm mt-3 text-center">{{ error }}</p>
          <p v-if="sent" class="text-gray-400 text-sm mt-3 text-center">Check your inbox — the link expires in 1 hour.</p>
        </form>

        <p class="text-center text-sm text-gray-600 mt-6">
          <NuxtLink to="/" class="text-emerald-400 hover:text-emerald-300 transition-colors">← Back to MetricsHour</NuxtLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
useSeoMeta({
  title: 'Forgot Password — MetricsHour',
  robots: 'noindex',
})
useHead({ link: [{ rel: 'canonical', href: 'https://metricshour.com/auth/forgot-password/' }] })

const config = useRuntimeConfig()
const email = ref('')
const loading = ref(false)
const sent = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await $fetch(`${config.public.apiBase}/api/auth/forgot-password`, {
      method: 'POST',
      body: { email: email.value },
    })
    sent.value = true
  } catch {
    error.value = 'Something went wrong. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>
