<template>
  <div v-if="!submitted"
    class="flex flex-col sm:flex-row items-start sm:items-center gap-2 bg-[#111827] border border-[#1f2937] rounded-xl px-4 py-3"
    style="max-height: 80px; overflow: hidden"
  >
    <p class="text-xs text-gray-300 leading-snug flex-1 min-w-0 truncate">{{ ctaCopy }}</p>
    <div class="flex items-center gap-2 shrink-0 w-full sm:w-auto">
      <input
        v-model="email"
        type="email"
        :placeholder="$t('emailAlert.placeholder')"
        class="flex-1 sm:w-36 bg-[#0d1520] border border-[#1f2937] text-white text-xs rounded-lg px-2.5 py-2 focus:outline-none focus:border-emerald-600 placeholder-gray-600"
        @keydown.enter="submit"
      />
      <button
        @click="submit"
        :disabled="submitting || !email.trim()"
        class="bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-semibold px-3 py-2 rounded-lg whitespace-nowrap transition-colors disabled:opacity-50"
      >{{ submitting ? '...' : ctaButton }}</button>
    </div>
  </div>
  <div v-else class="text-xs text-emerald-400 text-center py-2">
    {{ $t('emailAlert.success', { name: assetName || assetSymbol || '' }) }}
  </div>
</template>

<script setup lang="ts">
const { t } = useI18n()
const { public: { apiBase } } = useRuntimeConfig()

const props = defineProps<{
  contextType: 'stock_earnings' | 'stock_risk' | 'stock_general' | 'country' | 'smart_money' | 'lens' | 'calendar'
  assetSymbol?: string
  assetName?: string
  riskLevel?: string
  earningsDate?: string
}>()

const email = ref('')
const submitting = ref(false)
const submitted = ref(false)

const ctaCopy = computed(() => {
  switch (props.contextType) {
    case 'stock_earnings':
      return props.earningsDate
        ? t('contextualCTA.earnings', { ticker: props.assetSymbol, date: props.earningsDate })
        : t('contextualCTA.general', { ticker: props.assetSymbol })
    case 'stock_risk':
      return t('contextualCTA.risk', { ticker: props.assetSymbol })
    case 'country':
      return t('contextualCTA.country', { name: props.assetName })
    case 'smart_money':
      return t('contextualCTA.smartMoney', { name: props.assetName })
    case 'lens':
      return t('contextualCTA.lens')
    case 'calendar':
      return t('contextualCTA.calendar', { event: props.assetName })
    default:
      return t('contextualCTA.general', { ticker: props.assetSymbol })
  }
})

const ctaButton = computed(() => {
  switch (props.contextType) {
    case 'stock_earnings': return t('contextualCTA.buttonEarnings')
    case 'country':        return t('contextualCTA.buttonCountry')
    default:               return t('contextualCTA.buttonDefault')
  }
})

async function submit() {
  if (!email.value.trim()) return
  submitting.value = true
  try {
    await $fetch(`${apiBase}/api/email-alerts`, {
      method: 'POST',
      body: {
        email: email.value.trim(),
        asset_symbol: props.assetSymbol || props.contextType,
        asset_name: props.assetName || props.assetSymbol || '',
        asset_type: props.contextType,
      },
    })
    submitted.value = true
  } catch {}
  submitting.value = false
}
</script>
