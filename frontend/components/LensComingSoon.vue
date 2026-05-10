<template>
  <div class="text-center py-8">
    <div class="text-5xl mb-4">{{ assetType === 'crypto' ? '₿' : '🏭' }}</div>
    <h2 class="text-xl font-bold text-white mb-2">
      {{ assetType === 'crypto' ? $t('lens.coming.cryptoTitle') : $t('lens.coming.commoditiesTitle') }}
    </h2>
    <p class="text-gray-500 text-sm mb-6">
      {{ assetType === 'crypto' ? $t('lens.coming.cryptoDesc') : $t('lens.coming.commoditiesDesc') }}
    </p>

    <!-- Features list -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6 text-left max-w-sm mx-auto">
      <div class="text-xs text-gray-600 uppercase tracking-wider mb-3 font-semibold">Coming features</div>
      <ul class="space-y-2">
        <li v-for="feature in features" :key="feature" class="flex items-start gap-2 text-sm text-gray-400">
          <span class="text-emerald-600 mt-0.5 shrink-0">·</span>
          {{ feature }}
        </li>
      </ul>
    </div>

    <!-- Email capture -->
    <div class="max-w-sm mx-auto mb-6">
      <p class="text-xs text-gray-500 mb-3">{{ $t('lens.coming.notifyMe', { type: assetType }) }}</p>
      <form @submit.prevent="subscribe" class="flex gap-2">
        <input v-model="email" type="email" placeholder="your@email.com"
          class="flex-1 bg-[#111827] border border-[#1f2937] rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-700 focus:outline-none focus:border-emerald-700" />
        <button type="submit" :disabled="!email || subscribed"
          class="px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-all whitespace-nowrap">
          {{ subscribed ? '✓' : $t('lens.coming.notifyButton') }}
        </button>
      </form>
    </div>

    <!-- CTAs -->
    <div class="flex gap-3 justify-center flex-wrap">
      <button @click="$emit('analyzeStock')" class="px-4 py-2 rounded-xl text-sm font-semibold bg-[#111827] border border-[#1f2937] text-emerald-400 hover:border-emerald-700 transition-all">
        {{ $t('lens.coming.analyzeStock') }}
      </button>
      <button @click="$emit('analyzeForex')" class="px-4 py-2 rounded-xl text-sm font-semibold bg-[#111827] border border-[#1f2937] text-gray-400 hover:text-white transition-all">
        {{ $t('lens.coming.analyzeForex') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const { t } = useI18n()
const { get } = useApi()

const props = defineProps<{ assetType: string }>()
defineEmits(['analyzeStock', 'analyzeForex'])

const email = ref('')
const subscribed = ref(false)

const features = computed(() => {
  if (props.assetType === 'crypto') {
    return (t('lens.coming.cryptoFeatures', []) as any) || [
      'Regulatory status across 196 countries',
      'Macro correlation analysis',
      'Risk-on/risk-off signals',
      'Country adoption tracking',
    ]
  }
  return (t('lens.coming.commoditiesFeatures', []) as any) || [
    'Production by country',
    'Supply disruption risk',
    'Demand signals by region',
    'USD correlation analysis',
  ]
})

async function subscribe() {
  if (!email.value) return
  try {
    await get(`/api/newsletter/subscribe?email=${encodeURIComponent(email.value)}&source=lens_${props.assetType}`)
    subscribed.value = true
  } catch {
    subscribed.value = true // optimistic
  }
}
</script>
