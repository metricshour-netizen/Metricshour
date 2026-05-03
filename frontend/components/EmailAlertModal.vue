<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
      @click.self="$emit('update:modelValue', false)"
    >
      <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="$emit('update:modelValue', false)" />
      <div class="relative bg-[#111827] border border-[#1f2937] rounded-2xl p-6 w-full max-w-sm shadow-2xl">
        <button
          class="absolute top-4 right-4 text-gray-500 hover:text-white transition-colors"
          @click="$emit('update:modelValue', false)"
        >✕</button>

        <!-- Success state -->
        <div v-if="submitted" class="text-center py-2">
          <div class="text-3xl mb-3">✓</div>
          <p class="text-white font-semibold text-sm mb-1">{{ $t('emailAlert.success', { name: assetName }) }}</p>
          <p class="text-gray-500 text-xs">{{ $t('emailAlert.disclaimer') }}</p>
        </div>

        <!-- Form state -->
        <template v-else>
          <p class="text-[10px] font-bold uppercase tracking-widest text-emerald-500 mb-1">Alert</p>
          <h2 class="text-white font-bold text-base mb-1">{{ $t('emailAlert.title', { name: assetName }) }}</h2>
          <p class="text-gray-500 text-xs mb-5">{{ $t('emailAlert.subtitle') }}</p>

          <form @submit.prevent="submit">
            <input
              v-model="email"
              type="email"
              required
              :placeholder="$t('emailAlert.placeholder')"
              class="w-full bg-[#0f1623] border border-[#1f2937] rounded-lg px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-emerald-500 mb-3 transition-colors"
            />

            <p v-if="error" class="text-red-400 text-xs mb-3">{{ error }}</p>

            <button
              type="submit"
              :disabled="submitting"
              class="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold py-3 rounded-lg transition-colors"
            >
              {{ submitting ? $t('emailAlert.submitting') : $t('emailAlert.submit') }}
            </button>
          </form>

          <p class="text-gray-700 text-[10px] text-center mt-3">{{ $t('emailAlert.disclaimer') }}</p>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue: boolean
  assetSymbol: string
  assetName: string
  assetType?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()
const { public: { apiBase } } = useRuntimeConfig()

const email = ref('')
const submitting = ref(false)
const submitted = ref(false)
const error = ref('')

watch(() => props.modelValue, (v) => {
  if (v) {
    email.value = ''
    submitting.value = false
    submitted.value = false
    error.value = ''
  }
})

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    const res = await $fetch<{ status: string; message: string }>(`${apiBase}/api/email-alerts`, {
      method: 'POST',
      body: {
        email: email.value,
        asset_symbol: props.assetSymbol,
        asset_name: props.assetName,
        asset_type: props.assetType || 'stock',
      },
    })
    if (res.status === 'exists') {
      submitted.value = true // treat as success — don't leak which emails are registered
    } else {
      submitted.value = true
    }
  } catch {
    error.value = t('emailAlert.error')
  } finally {
    submitting.value = false
  }
}
</script>
