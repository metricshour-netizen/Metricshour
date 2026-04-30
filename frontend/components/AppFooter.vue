<template>
  <footer class="border-t border-[#1f2937] mt-16 bg-[#070c14]">
    <!-- Logo back to home -->
    <div class="flex justify-center pt-6 pb-2">
      <NuxtLink to="/" class="text-emerald-500/60 hover:text-emerald-400 font-bold tracking-tight text-sm transition-colors">METRICSHOUR</NuxtLink>
    </div>

    <!-- Nav links — grouped by category for crawlability -->
    <div class="max-w-7xl mx-auto px-4 py-4 grid grid-cols-2 sm:grid-cols-4 gap-y-4 gap-x-8 text-xs text-gray-600">
      <div>
        <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-2">Markets</div>
        <div class="flex flex-col gap-1.5">
          <NuxtLink to="/markets/"     class="hover:text-gray-400 transition-colors">Overview</NuxtLink>
          <NuxtLink to="/stocks/"      class="hover:text-gray-400 transition-colors">Stocks</NuxtLink>
          <NuxtLink to="/crypto/"      class="hover:text-gray-400 transition-colors">Crypto</NuxtLink>
          <NuxtLink to="/etfs/"        class="hover:text-gray-400 transition-colors">ETFs</NuxtLink>
          <NuxtLink to="/fx/"          class="hover:text-gray-400 transition-colors">FX</NuxtLink>
          <NuxtLink to="/commodities/" class="hover:text-gray-400 transition-colors">Commodities</NuxtLink>
          <NuxtLink to="/sectors/"     class="hover:text-gray-400 transition-colors">Sectors</NuxtLink>
        </div>
      </div>
      <div>
        <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-2">Economy</div>
        <div class="flex flex-col gap-1.5">
          <NuxtLink to="/countries/"   class="hover:text-gray-400 transition-colors">Countries</NuxtLink>
          <NuxtLink to="/trade/"       class="hover:text-gray-400 transition-colors">Trade Flows</NuxtLink>
          <NuxtLink to="/compare/"     class="hover:text-gray-400 transition-colors">Compare</NuxtLink>
          <NuxtLink to="/blocs/"       class="hover:text-gray-400 transition-colors">Blocs</NuxtLink>
          <NuxtLink to="/china/"       class="hover:text-gray-400 transition-colors">China A-Shares</NuxtLink>
        </div>
      </div>
      <div>
        <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-2">Tools</div>
        <div class="flex flex-col gap-1.5">
          <NuxtLink to="/screener/"    class="hover:text-gray-400 transition-colors">Screener</NuxtLink>
          <NuxtLink to="/rates/"       class="hover:text-gray-400 transition-colors">Interest Rates</NuxtLink>
          <NuxtLink to="/yield-curve/" class="hover:text-gray-400 transition-colors">Yield Curve</NuxtLink>
          <NuxtLink to="/earnings/"    class="hover:text-gray-400 transition-colors">Earnings</NuxtLink>
          <NuxtLink to="/feed/"        class="hover:text-gray-400 transition-colors">Live Feed</NuxtLink>
        </div>
      </div>
      <div>
        <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-2">Resources</div>
        <div class="flex flex-col gap-1.5">
          <NuxtLink to="/blog/"        class="hover:text-gray-400 transition-colors">Blog</NuxtLink>
          <NuxtLink to="/login/"       class="hover:text-gray-400 transition-colors">Sign In</NuxtLink>
          <NuxtLink to="/join/"        class="hover:text-emerald-400 text-emerald-600 transition-colors font-medium">Join Free</NuxtLink>
        </div>
      </div>
    </div>

    <!-- Legal links -->
    <div class="flex flex-wrap gap-x-5 gap-y-1 justify-center text-[11px] text-gray-700 pb-1">
      <NuxtLink to="/about"   class="hover:text-gray-500 transition-colors">About</NuxtLink>
      <span class="text-gray-800">·</span>
      <NuxtLink to="/faq"     class="hover:text-gray-500 transition-colors">FAQ</NuxtLink>
      <span class="text-gray-800">·</span>
      <NuxtLink to="/privacy" class="hover:text-gray-500 transition-colors">Privacy Policy</NuxtLink>
      <span class="text-gray-800">·</span>
      <NuxtLink to="/terms"   class="hover:text-gray-500 transition-colors">Terms of Service</NuxtLink>
      <span class="text-gray-800">·</span>
      <a href="mailto:hello@metricshour.com" class="hover:text-gray-500 transition-colors">Contact</a>
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
      <p>
        Data:
        <a href="https://data.worldbank.org" target="_blank" rel="noopener noreferrer" class="hover:text-gray-500 transition-colors">World Bank</a>
        ·
        <a href="https://efts.sec.gov/LATEST/search-index?forms=10-K,10-Q" target="_blank" rel="noopener noreferrer" class="hover:text-gray-500 transition-colors">SEC EDGAR</a>
        ·
        <a href="https://comtradeplus.un.org" target="_blank" rel="noopener noreferrer" class="hover:text-gray-500 transition-colors">UN Comtrade</a>
        ·
        <span class="text-gray-700">REST Countries</span>
        ·
        <a href="https://data.imf.org" target="_blank" rel="noopener noreferrer" class="hover:text-gray-500 transition-colors">IMF</a>
        ·
        <a href="https://fred.stlouisfed.org" target="_blank" rel="noopener noreferrer" class="hover:text-gray-500 transition-colors">FRED</a>
      </p>
      <p>© {{ new Date().getFullYear() }} MetricsHour · All rights reserved</p>
    </div>
  </footer>
</template>
