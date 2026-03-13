<template>
  <div class="newsletter-capture">
    <div v-if="state === 'idle' || state === 'loading'" class="flex flex-col sm:flex-row gap-2">
      <input
        v-model="email"
        type="email"
        :placeholder="placeholder"
        class="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 transition-colors"
        :disabled="state === 'loading'"
        @keydown.enter="submit"
      />
      <button
        class="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-60 text-black font-semibold text-sm px-5 py-2.5 rounded-lg transition-colors whitespace-nowrap"
        :disabled="state === 'loading'"
        @click="submit"
      >
        <span v-if="state === 'loading'" class="inline-block w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin align-middle mr-1" />
        {{ state === 'loading' ? 'Subscribing…' : buttonText }}
      </button>
    </div>

    <div v-else-if="state === 'success'" class="flex items-center gap-2 text-emerald-400 text-sm py-2">
      <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
      </svg>
      <span>{{ successMessage }}</span>
    </div>

    <div v-else-if="state === 'error'" class="flex flex-col gap-2">
      <p class="text-red-400 text-xs">{{ errorMessage }}</p>
      <div class="flex flex-col sm:flex-row gap-2">
        <input
          v-model="email"
          type="email"
          :placeholder="placeholder"
          class="flex-1 bg-gray-900 border border-red-700 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 transition-colors"
          @keydown.enter="submit"
        />
        <button
          class="bg-emerald-500 hover:bg-emerald-400 text-black font-semibold text-sm px-5 py-2.5 rounded-lg transition-colors whitespace-nowrap"
          @click="submit"
        >
          {{ buttonText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  source?: string
  placeholder?: string
  buttonText?: string
  successMessage?: string
}>(), {
  source: 'unknown',
  placeholder: 'your@email.com',
  buttonText: 'Get weekly insights',
  successMessage: 'You\'re in. Weekly macro intelligence incoming.',
})

const { public: { apiBase } } = useRuntimeConfig()

const email = ref('')
const state = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
const errorMessage = ref('')

async function submit() {
  const trimmed = email.value.trim()
  if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
    state.value = 'error'
    errorMessage.value = 'Please enter a valid email address.'
    return
  }
  state.value = 'loading'
  try {
    const res = await $fetch(`${apiBase}/api/newsletter/subscribe`, {
      method: 'POST',
      body: { email: trimmed, source: props.source },
    })
    state.value = 'success'
  } catch (err: any) {
    state.value = 'error'
    errorMessage.value = err?.data?.detail || 'Something went wrong. Please try again.'
  }
}
</script>
