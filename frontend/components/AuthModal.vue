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
