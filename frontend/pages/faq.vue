<template>
  <main class="max-w-3xl mx-auto px-4 py-12">
    <NuxtLink to="/" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-8 inline-block">← Home</NuxtLink>

    <h1 class="text-3xl font-bold text-white mb-2">Frequently Asked Questions</h1>
    <p class="text-gray-400 text-sm mb-10">Everything you need to know about MetricsHour.</p>

    <div class="space-y-4">
      <div
        v-for="(item, i) in faqs"
        :key="i"
        class="bg-[#111827] border border-[#1f2937] rounded-lg overflow-hidden"
      >
        <button
          class="w-full text-left px-5 py-4 flex items-center justify-between gap-4 hover:bg-[#1a2332] transition-colors"
          @click="open === i ? open = null : open = i"
        >
          <span class="text-sm font-semibold text-white">{{ item.q }}</span>
          <span class="text-gray-500 text-lg flex-shrink-0">{{ open === i ? '−' : '+' }}</span>
        </button>
        <div v-if="open === i" class="px-5 pb-5">
          <p class="text-sm text-gray-400 leading-relaxed">{{ item.a }}</p>
        </div>
      </div>
    </div>

    <div class="mt-12 bg-[#111827] border border-[#1f2937] rounded-lg p-6 text-center">
      <p class="text-sm text-gray-400 mb-3">Still have questions?</p>
      <a href="mailto:hello@metricshour.com" class="text-emerald-400 text-sm font-semibold hover:text-emerald-300 transition-colors">
        hello@metricshour.com →
      </a>
    </div>
  </main>
</template>

<script setup>
const open = ref(null)

const faqs = [
  {
    q: 'What is MetricsHour?',
    a: 'MetricsHour is a macroeconomic data platform covering 196 countries, 130+ stocks, and 38,000+ bilateral trade pairs. We connect SEC EDGAR geographic revenue data, World Bank macro indicators, and UN Comtrade bilateral trade flows in one place.',
  },
  {
    q: 'Is MetricsHour free?',
    a: 'Yes. Core features — country profiles, trade flows, stock revenue exposure, and macro indicators — are free forever. No credit card required.',
  },
  {
    q: 'Where does the data come from?',
    a: 'We aggregate data from public institutions: World Bank (GDP, inflation, governance), IMF (WEO forecasts), UN Comtrade (bilateral trade flows), SEC EDGAR (geographic revenue from 10-K filings), and Marketstack (live prices). All sources are credited on every data page.',
  },
  {
    q: 'How often is data updated?',
    a: 'Stock and crypto prices update every 1–15 minutes during market hours. Macro indicators (GDP, inflation, etc.) update annually when World Bank and IMF publish new data. Trade flow data updates annually from UN Comtrade.',
  },
  {
    q: 'What is geographic revenue exposure?',
    a: 'For each stock, we parse SEC EDGAR 10-K filings to extract what percentage of revenue comes from each country. For example, you can see that Apple earns roughly 19% of revenue from Greater China — and click through to see China\'s GDP growth, trade balance, and more.',
  },
  {
    q: 'How many trade pairs does MetricsHour cover?',
    a: 'We cover 38,000+ bilateral trade relationships across 170 countries. Each pair shows total trade volume, top exported products, and links to both countries\' macro profiles.',
  },
  {
    q: 'Can I create an account?',
    a: 'Yes. Creating a free account lets you save watchlists, set price alerts, and access additional features as we roll them out. Sign up at metricshour.com/join.',
  },
  {
    q: 'How do I search for a country, stock, or trade pair?',
    a: 'Use the search bar on the homepage (press / anywhere on the site). You can search by country name or code, stock ticker, or two countries separated by a dash (e.g. "us-cn" for the US–China trade pair).',
  },
  {
    q: 'Is the data accurate?',
    a: 'We source directly from institutional data providers (World Bank, IMF, UN, SEC) and do not manually modify figures. Some indicators have reporting lags of 1–2 years, which we display clearly. Live prices come from Marketstack and may have a short delay.',
  },
  {
    q: 'Do you have an API?',
    a: 'Not publicly yet. If you\'re interested in API access for research or commercial use, reach out at hello@metricshour.com.',
  },
]

useSeoMeta({
  title: 'FAQ — MetricsHour',
  description: 'Answers to common questions about MetricsHour — data sources, pricing, coverage, and how geographic revenue exposure works.',
  ogTitle: 'FAQ — MetricsHour',
  ogDescription: 'Answers to common questions about MetricsHour — data sources, pricing, coverage, and how geographic revenue exposure works.',
  ogUrl: 'https://metricshour.com/faq/',
  ogType: 'website',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/faq/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: faqs.map(item => ({
        '@type': 'Question',
        name: item.q,
        acceptedAnswer: {
          '@type': 'Answer',
          text: item.a,
        },
      })),
    }),
  }],
})
</script>
