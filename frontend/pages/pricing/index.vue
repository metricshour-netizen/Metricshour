<template>
  <main class="max-w-5xl mx-auto px-4 py-16">
    <div class="text-center mb-12">
      <h1 class="text-3xl font-bold text-white mb-3">Simple, transparent pricing</h1>
      <p class="text-gray-500">Bloomberg Terminal costs $24K/year. We don't.</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        v-for="tier in tiers"
        :key="tier.name"
        class="bg-[#111827] rounded-lg p-6 flex flex-col"
        :class="tier.featured ? 'border-2 border-emerald-500' : 'border border-[#1f2937]'"
      >
        <div v-if="tier.featured" class="text-xs text-emerald-400 font-bold uppercase tracking-wide mb-3">
          Most Popular
        </div>
        <h2 class="text-lg font-bold text-white mb-1">{{ tier.name }}</h2>
        <div class="mb-4">
          <span class="text-3xl font-bold text-white">{{ tier.price }}</span>
          <span v-if="tier.period" class="text-gray-500 text-sm">/{{ tier.period }}</span>
        </div>
        <p class="text-gray-500 text-sm mb-6">{{ tier.desc }}</p>
        <ul class="space-y-2.5 flex-1 mb-6">
          <li v-for="f in tier.features" :key="f" class="flex items-start gap-2 text-sm">
            <span class="text-emerald-400 mt-0.5 shrink-0">✓</span>
            <span class="text-gray-300">{{ f }}</span>
          </li>
        </ul>
        <button
          class="w-full py-2.5 rounded font-medium text-sm transition-colors"
          :class="tier.featured
            ? 'bg-emerald-500 hover:bg-emerald-400 text-black'
            : 'border border-[#1f2937] hover:border-gray-500 text-gray-300'"
        >
          {{ tier.cta }}
        </button>
      </div>
    </div>

    <p class="text-center text-xs text-gray-600 mt-10">
      All plans include 196 countries, 80+ macro indicators, bilateral trade data, and commodities.
      Data sourced from World Bank, UN Comtrade, SEC EDGAR, and IMF.
    </p>
  </main>
</template>

<script setup lang="ts">
const tiers = [
  {
    name: 'Free',
    price: '$0',
    period: null,
    featured: false,
    desc: 'All data, always. Prices delayed 15 minutes.',
    cta: 'Get started',
    features: [
      '196 countries + macro data',
      '15-min delayed stock prices',
      'Bilateral trade data (380 pairs)',
      'Commodities data',
      '2 price alerts',
    ],
  },
  {
    name: 'Pro',
    price: '$9.99',
    period: 'mo',
    featured: true,
    desc: 'Real-time data and AI-powered market insights.',
    cta: 'Start Pro →',
    features: [
      'Everything in Free',
      'Real-time stock prices',
      'AI market insights (Claude)',
      'CSV data export',
      'Unlimited price alerts',
    ],
  },
  {
    name: 'Analyst',
    price: '$29.99',
    period: 'mo',
    featured: false,
    desc: 'API access for developers and researchers.',
    cta: 'Start Analyst →',
    features: [
      'Everything in Pro',
      'API access (10K calls/month)',
      'Bulk data downloads',
      'Advanced chart tools',
      'Priority support',
    ],
  },
  {
    name: 'Enterprise',
    price: '$199',
    period: 'mo',
    featured: false,
    desc: 'For teams and financial institutions.',
    cta: 'Contact us',
    features: [
      'Everything in Analyst',
      'Up to 10 team seats',
      '500K API calls/month',
      'White-label option',
      'Dedicated support',
    ],
  },
]

useSeoMeta({
  title: 'Pricing — MetricsHour',
  description: 'Free global financial data. Pro from $9.99/month for real-time prices and AI insights. No Bloomberg Terminal required.',
})
</script>
