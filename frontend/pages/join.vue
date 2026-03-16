<template>
  <div class="min-h-screen bg-[#0a0e1a] flex flex-col">
    <!-- Nav logo only -->
    <div class="border-b border-[#1f2937] px-6 py-4">
      <NuxtLink to="/" class="text-emerald-400 font-bold tracking-tight text-lg">METRICSHOUR</NuxtLink>
    </div>

    <div class="flex-1 flex items-center justify-center px-4 py-12">
      <div class="w-full max-w-4xl flex flex-col lg:flex-row gap-12 lg:gap-16 items-center lg:items-start">

        <!-- Left: value props (desktop only) -->
        <div class="hidden lg:block flex-1 pt-2">
          <h1 class="text-white font-bold text-3xl leading-tight mb-3">
            The global economy,<br>at your fingertips.
          </h1>
          <p class="text-gray-400 text-sm mb-8 leading-relaxed">
            Free access to real-time markets, 250+ country economies, bilateral trade flows, and AI-powered insights.
          </p>
          <ul class="space-y-4">
            <li v-for="item in features" :key="item.label" class="flex items-start gap-3">
              <span class="text-emerald-400 mt-0.5 text-base leading-none">{{ item.icon }}</span>
              <div>
                <p class="text-white text-sm font-medium">{{ item.label }}</p>
                <p class="text-gray-500 text-xs mt-0.5">{{ item.desc }}</p>
              </div>
            </li>
          </ul>
          <p class="text-xs text-gray-600 mt-8">Free forever. No credit card required.</p>
        </div>

        <!-- Right: form -->
        <div class="w-full max-w-sm lg:flex-shrink-0">
          <h2 class="text-white font-bold text-2xl mb-1">Create your account</h2>
          <p class="text-gray-500 text-sm mb-8">Free. No credit card required.</p>

          <form @submit.prevent="submit" class="space-y-4">
            <div>
              <label class="text-xs text-gray-500 block mb-1.5">Email</label>
              <input
                v-model="email"
                type="email"
                required
                autocomplete="email"
                placeholder="you@example.com"
                class="w-full bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
              />
            </div>
            <div>
              <label class="text-xs text-gray-500 block mb-1.5">Password</label>
              <input
                v-model="password"
                type="password"
                required
                autocomplete="new-password"
                placeholder="Min. 8 characters"
                class="w-full bg-[#111827] border border-[#1f2937] rounded-lg px-3 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-emerald-500 transition-colors"
              />
            </div>

            <div v-if="error" class="text-red-400 text-xs bg-red-900/20 border border-red-900/40 rounded-lg px-3 py-2.5">
              {{ error }}
            </div>

            <button
              type="submit"
              :disabled="loading"
              class="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-lg py-3 transition-colors"
            >
              {{ loading ? 'Creating account…' : 'Create Free Account' }}
            </button>

            <p class="text-xs text-gray-600 text-center leading-relaxed">
              By signing up you agree to our
              <NuxtLink to="/terms" class="text-gray-500 hover:text-gray-400 underline underline-offset-2">Terms</NuxtLink>
              and
              <NuxtLink to="/privacy" class="text-gray-500 hover:text-gray-400 underline underline-offset-2">Privacy Policy</NuxtLink>.
            </p>
          </form>

          <!-- Divider -->
          <div class="flex items-center gap-3 my-5">
            <div class="flex-1 h-px bg-[#1f2937]" />
            <span class="text-xs text-gray-600">or</span>
            <div class="flex-1 h-px bg-[#1f2937]" />
          </div>

          <!-- Google -->
          <a
            :href="`${apiBase}/api/auth/google/authorize`"
            class="flex items-center justify-center gap-3 w-full border border-[#1f2937] hover:border-gray-500 rounded-lg py-3 transition-colors group"
          >
            <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
              <path fill="none" d="M0 0h48v48H0z"/>
            </svg>
            <span class="text-sm text-gray-300 group-hover:text-white transition-colors">Continue with Google</span>
          </a>

          <p class="text-center text-xs text-gray-600 mt-6">
            Already have an account?
            <NuxtLink to="/login" class="text-emerald-500 hover:text-emerald-400 transition-colors font-medium">Sign in</NuxtLink>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
useSeoMeta({
  title: 'Join MetricsHour — Free Global Markets & Economic Data',
  description: 'Create a free MetricsHour account. Track 250+ country economies, real-time markets, trade flows, price alerts, and AI-powered insights.',
  robots: 'index, follow',
})

const { register, isLoggedIn } = useAuth()
const { public: { apiBase } } = useRuntimeConfig()

if (isLoggedIn.value) navigateTo('/')

const features = [
  { icon: '🌍', label: '250+ Country Economies', desc: 'GDP, inflation, trade balance, interest rates and 80+ indicators per country.' },
  { icon: '📈', label: 'Real-Time Markets', desc: 'Stocks, commodities, FX, crypto — live prices with alerts when they move.' },
  { icon: '🔀', label: 'Global Trade Flows', desc: '3,000+ bilateral trade corridors with product-level breakdowns.' },
  { icon: '🔔', label: 'Price & Macro Alerts', desc: 'Get notified the moment a market or economic threshold is crossed.' },
  { icon: '⭐', label: 'Personal Watchlist', desc: 'Track the assets and countries that matter to you, in one place.' },
]

const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await register(email.value, password.value)
    navigateTo('/')
  } catch (e: any) {
    error.value = e.message || 'Could not create account'
  } finally {
    loading.value = false
  }
}
</script>
