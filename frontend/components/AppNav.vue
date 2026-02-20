<template>
  <nav class="border-b border-[#1f2937] bg-[#0a0e1a] sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
      <NuxtLink to="/" class="text-emerald-400 font-bold tracking-tight text-lg">
        METRICSHOUR
      </NuxtLink>
      <div class="flex items-center gap-6 text-sm text-gray-400">
        <NuxtLink to="/countries" class="hover:text-white transition-colors">Countries</NuxtLink>
        <NuxtLink to="/stocks" class="hover:text-white transition-colors">Stocks</NuxtLink>
        <NuxtLink to="/trade" class="hover:text-white transition-colors">Trade</NuxtLink>
        <NuxtLink to="/commodities" class="hover:text-white transition-colors">Commodities</NuxtLink>
        <NuxtLink to="/pricing" class="hover:text-white transition-colors text-emerald-400">Pro →</NuxtLink>
      </div>
    </div>
  </nav>
</template>
