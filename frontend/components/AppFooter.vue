<template>
  <footer class="border-t border-[#1f2937] mt-16 bg-[#070c14]">
    <!-- Logo back to home -->
    <div class="flex justify-center pt-6 pb-2">
      <NuxtLink to="/" class="text-emerald-500/60 hover:text-emerald-400 font-bold tracking-tight text-sm transition-colors">METRICSHOUR</NuxtLink>
    </div>

    <!-- Links row -->
    <div class="max-w-7xl mx-auto px-4 py-3 flex flex-wrap gap-x-6 gap-y-2 justify-center text-xs text-gray-600">
      <NuxtLink to="/markets"     class="hover:text-gray-400 transition-colors">Markets</NuxtLink>
      <NuxtLink to="/countries"   class="hover:text-gray-400 transition-colors">Countries</NuxtLink>
      <NuxtLink to="/trade"       class="hover:text-gray-400 transition-colors">Trade</NuxtLink>
      <NuxtLink to="/commodities" class="hover:text-gray-400 transition-colors">Commodities</NuxtLink>
      <NuxtLink to="/feed"        class="hover:text-gray-400 transition-colors">Feed</NuxtLink>
      <NuxtLink to="/pricing"     class="hover:text-emerald-500 transition-colors text-emerald-700">Pro</NuxtLink>
    </div>

    <!-- Disclaimer -->
    <div class="border-t border-[#1a2332] px-4 py-4">
      <p class="max-w-3xl mx-auto text-center text-[11px] text-gray-700 leading-relaxed">
        <span class="font-semibold text-gray-600">Disclaimer:</span>
        The information on MetricsHour is for educational and informational purposes only.
        It does not constitute financial advice, investment advice, trading advice, or any other type of advice.
        MetricsHour does not recommend that any asset should be bought, sold, or held.
        Always do your own research and consult a licensed financial advisor before making any investment decision.
        Past performance is not indicative of future results.
      </p>
    </div>

    <!-- Data sources + copyright -->
    <div class="border-t border-[#1a2332] px-4 py-4 text-center text-[10px] text-gray-700 space-y-1">
      <p>Data: World Bank · SEC EDGAR · UN Comtrade · REST Countries · IMF · CoinGecko · Marketstack</p>
      <p>© {{ new Date().getFullYear() }} MetricsHour · All rights reserved</p>
    </div>
  </footer>
</template>
