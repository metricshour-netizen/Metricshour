<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-[100] flex items-center justify-center p-4"
      @click.self="$emit('update:modelValue', false)"
    >
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      <!-- Modal -->
      <div class="relative w-full max-w-sm bg-[#0d1117] border border-[#1f2937] rounded-2xl p-6 shadow-2xl">
        <!-- Close -->
        <button
          class="absolute top-4 right-4 text-gray-500 hover:text-white transition-colors"
          @click="$emit('update:modelValue', false)"
        >✕</button>

        <h2 class="text-white font-bold text-lg mb-1">
          {{ tab === 'login' ? 'Sign In' : 'Create Account' }}
        </h2>
        <p class="text-gray-500 text-xs mb-5">
          {{ tab === 'login' ? 'Welcome back to MetricsHour' : 'Start tracking global markets' }}
        </p>

        <!-- Tabs -->
        <div class="flex gap-1 bg-[#111827] rounded-lg p-1 mb-5">
          <button
            class="flex-1 text-sm py-2.5 rounded-md transition-colors font-medium"
            :class="tab === 'login' ? 'bg-emerald-600 text-white' : 'text-gray-500 hover:text-gray-300'"
            @click="tab = 'login'; error = ''"
          >Sign In</button>
          <button
            class="flex-1 text-sm py-2.5 rounded-md transition-colors font-medium"
            :class="tab === 'register' ? 'bg-emerald-600 text-white' : 'text-gray-500 hover:text-gray-300'"
            @click="tab = 'register'; error = ''"
          >Register</button>
        </div>

        <!-- Form -->
        <form @submit.prevent="submit" class="space-y-3">
          <div>
            <label class="text-xs text-gray-500 block mb-1">Email</label>
            <input
              v-model="email"
              type="email"
              required
              autocomplete="email"
              placeholder="you@example.com"
              class="w-full bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">Password</label>
            <input
              v-model="password"
              type="password"
              required
              autocomplete="current-password"
              placeholder="Min. 8 characters"
              class="w-full bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>

          <div v-if="error" class="text-red-400 text-xs bg-red-900/20 border border-red-900/40 rounded-lg px-3 py-2">
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm rounded-lg py-3 transition-colors"
          >
            {{ loading ? 'Please wait…' : (tab === 'login' ? 'Sign In' : 'Create Account') }}
          </button>
        </form>

        <!-- Divider -->
        <div class="flex items-center gap-3 my-4">
          <div class="flex-1 h-px bg-[#1f2937]" />
          <span class="text-xs text-gray-600">or</span>
          <div class="flex-1 h-px bg-[#1f2937]" />
        </div>

        <!-- Google Sign In -->
        <a
          :href="`${apiBase}/api/auth/google/authorize`"
          class="flex items-center justify-center gap-3 w-full border border-[#1f2937] hover:border-gray-500 rounded-lg py-2.5 transition-colors group"
        >
          <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            <path fill="none" d="M0 0h48v48H0z"/>
          </svg>
          <span class="text-sm text-gray-300 group-hover:text-white transition-colors font-medium">Continue with Google</span>
        </a>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const { login, register } = useAuth()
const { public: { apiBase } } = useRuntimeConfig()

const tab = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    if (tab.value === 'login') {
      await login(email.value, password.value)
    } else {
      await register(email.value, password.value)
    }
    email.value = ''
    password.value = ''
    emit('update:modelValue', false)
  } catch (e: any) {
    error.value = e.message || 'Something went wrong'
  } finally {
    loading.value = false
  }
}
</script>
