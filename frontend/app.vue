<template>
  <div>
    <AppNav />
    <NuxtPage />
    <AppFooter />

    <!-- Floating feedback button -->
    <button
      class="fixed bottom-6 right-4 z-50 bg-[#1f2937] hover:bg-[#374151] border border-[#374151] text-gray-300 text-xs font-semibold px-3 py-2 rounded-full shadow-lg transition-all flex items-center gap-1.5"
      @click="feedbackOpen = true"
    >
      💬 Feedback
    </button>

    <!-- Feedback modal -->
    <div v-if="feedbackOpen" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/60 backdrop-blur-sm" @click.self="feedbackOpen = false">
      <div class="bg-[#0a0e1a] border border-[#1f2937] rounded-2xl p-5 w-full max-w-md">
        <h3 class="text-white font-bold text-base mb-1">Send Feedback</h3>
        <p class="text-gray-500 text-xs mb-3">Bug, idea, or just saying hi — we read everything.</p>
        <textarea
          v-model="feedbackMsg"
          rows="4"
          placeholder="What's on your mind?"
          class="w-full bg-[#111827] border border-[#1f2937] text-white text-sm rounded-lg px-3 py-2 resize-none focus:outline-none focus:border-emerald-700 placeholder-gray-600"
        />
        <input
          v-model="feedbackEmail"
          type="email"
          placeholder="Email (optional — if you want a reply)"
          class="w-full mt-2 bg-[#111827] border border-[#1f2937] text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-emerald-700 placeholder-gray-600"
        />
        <div class="flex gap-2 mt-3">
          <button
            class="flex-1 bg-emerald-700 hover:bg-emerald-600 text-white text-sm font-semibold py-2 rounded-lg transition-colors disabled:opacity-50"
            :disabled="!feedbackMsg.trim() || sending"
            @click="submitFeedback"
          >{{ sending ? 'Sending...' : 'Send' }}</button>
          <button class="px-4 text-gray-500 hover:text-white text-sm transition-colors" @click="feedbackOpen = false">Cancel</button>
        </div>
        <p v-if="feedbackSent" class="text-emerald-400 text-xs mt-2 text-center">Thanks! We got your message.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const feedbackOpen = ref(false)
const feedbackMsg = ref('')
const feedbackEmail = ref('')
const sending = ref(false)
const feedbackSent = ref(false)
const route = useRoute()

async function submitFeedback() {
  if (!feedbackMsg.value.trim()) return
  sending.value = true
  try {
    await $fetch('https://api.metricshour.com/api/feedback', {
      method: 'POST',
      body: { message: feedbackMsg.value, page_url: route.fullPath, email: feedbackEmail.value || null },
    })
    feedbackSent.value = true
    feedbackMsg.value = ''
    feedbackEmail.value = ''
    setTimeout(() => { feedbackOpen.value = false; feedbackSent.value = false }, 2000)
  } catch {}
  sending.value = false
}
</script>
