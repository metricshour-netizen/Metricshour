<template>
  <main class="max-w-7xl mx-auto px-4 py-10">

    <!-- Breadcrumb -->
    <nav class="text-xs text-gray-600 mb-6 flex items-center gap-1.5">
      <NuxtLink to="/" class="hover:text-gray-400">Home</NuxtLink>
      <span>/</span>
      <NuxtLink to="/commodities" class="hover:text-gray-400">Commodities</NuxtLink>
      <span>/</span>
      <span class="text-gray-400">{{ meta.name }}</span>
    </nav>

    <!-- Hero -->
    <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
      <div>
        <div class="flex items-center gap-3 mb-1">
          <span class="text-4xl">{{ meta.icon }}</span>
          <div>
            <h1 class="text-2xl sm:text-3xl font-extrabold text-white">{{ meta.name }}</h1>
            <p class="text-xs text-gray-500 font-mono">{{ symbol.toUpperCase() }} · {{ meta.unit }} · {{ meta.category }}</p>
          </div>
        </div>
      </div>
      <div class="text-right">
        <div v-if="latestPrice" class="text-3xl font-extrabold text-white tabular-nums">
          {{ fmtPrice(latestPrice.c) }}
        </div>
        <div v-if="change24h !== null" class="text-sm font-bold mt-0.5" :class="change24h >= 0 ? 'text-emerald-400' : 'text-red-400'">
          {{ change24h >= 0 ? '+' : '' }}{{ change24h.toFixed(2) }}%
          <span class="text-gray-600 font-normal ml-1">24h</span>
        </div>
        <div v-if="latestPrice" class="text-xs text-gray-600 mt-1">
          Updated {{ fmtTs(latestPrice.t) }}
        </div>
      </div>
    </div>

    <!-- Summary + Insights -->
    <div v-if="pageSummary?.summary" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-4 text-sm text-gray-400 leading-relaxed">
      {{ pageSummary.summary }}
    </div>
    <div v-if="pageInsights?.length" class="mb-4 space-y-2">
      <div
        v-for="(insight, i) in pageInsights"
        :key="insight.generated_at"
        class="relative border rounded-lg p-4 overflow-hidden"
        :class="i === 0 ? 'bg-[#0d1520] border-emerald-900/50' : 'bg-[#0b0f1a] border-[#1f2937]'"
      >
        <div v-if="i === 0" class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"/>
        <div class="flex items-start gap-3">
          <span class="text-base mt-0.5 shrink-0" :class="i === 0 ? 'text-emerald-500' : 'text-gray-600'">◆</span>
          <div class="flex-1 min-w-0">
            <div class="text-xs text-gray-500 mb-1">{{ fmtTs(insight.generated_at) }}</div>
            <p class="text-sm text-gray-300 leading-relaxed">{{ insight.summary }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Price Chart -->
    <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4 mb-6">
      <div class="flex items-center justify-between mb-3">
        <span class="text-xs text-gray-500 uppercase tracking-widest">Price Chart</span>
        <div class="flex gap-1">
          <button
            v-for="r in RANGES"
            :key="r.label"
            @click="activeRange = r.days"
            class="text-xs px-2 py-0.5 rounded transition-colors"
            :class="activeRange === r.days ? 'bg-emerald-600 text-white' : 'text-gray-500 hover:text-gray-300'"
          >{{ r.label }}</button>
        </div>
      </div>
      <EChartLine v-if="chartOption" :option="chartOption" height="220px" />
      <div v-else class="h-[220px] flex items-center justify-center text-gray-600 text-sm">No price data</div>
    </div>

    <!-- Stats row -->
    <div v-if="stats" class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
      <div v-for="s in stats" :key="s.label" class="bg-[#111827] border border-[#1f2937] rounded-xl p-3">
        <div class="text-[10px] text-gray-600 uppercase tracking-widest mb-1">{{ s.label }}</div>
        <div class="text-sm font-bold text-white tabular-nums">{{ s.value }}</div>
      </div>
    </div>

    <div class="grid lg:grid-cols-3 gap-6">

      <!-- Description + producers -->
      <div class="lg:col-span-2 space-y-6">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <h2 class="text-xs text-gray-500 uppercase tracking-widest mb-3">About {{ meta.name }}</h2>
          <p class="text-sm text-gray-300 leading-relaxed">{{ meta.description }}</p>
        </div>

        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <h2 class="text-xs text-gray-500 uppercase tracking-widest mb-3">Key Producers &amp; Consumers</h2>
          <div class="flex flex-wrap gap-2">
            <NuxtLink
              v-for="c in meta.producers"
              :key="c.code"
              :to="`/countries/${c.code.toLowerCase()}`"
              class="text-xs bg-[#1f2937] hover:bg-[#2d3748] text-gray-300 hover:text-emerald-300 px-3 py-1.5 rounded-full transition-colors"
            >
              {{ c.flag }} {{ c.name }}
            </NuxtLink>
          </div>
        </div>
      </div>

      <!-- Related trade corridors -->
      <div class="space-y-6">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <h2 class="text-xs text-gray-500 uppercase tracking-widest mb-3">Related Trade Flows</h2>
          <div class="space-y-2">
            <NuxtLink
              v-for="t in meta.tradeFlows"
              :key="t.pair"
              :to="`/trade/${t.pair}`"
              class="flex items-center gap-2 text-xs text-gray-400 hover:text-emerald-300 transition-colors py-1"
            >
              <span class="text-emerald-600">↗</span>
              {{ t.label }}
            </NuxtLink>
          </div>
        </div>

        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5">
          <h2 class="text-xs text-gray-500 uppercase tracking-widest mb-3">Related Markets</h2>
          <div class="space-y-1.5">
            <NuxtLink
              v-for="r in meta.related"
              :key="r.symbol"
              :to="r.path"
              class="flex items-center justify-between text-xs py-1 border-b border-[#1f2937] last:border-0 hover:text-emerald-300 transition-colors text-gray-400"
            >
              <span>{{ r.label }}</span>
              <span class="text-gray-600 font-mono">{{ r.symbol }}</span>
            </NuxtLink>
          </div>
        </div>
      </div>

    </div>
  </main>
</template>

<script setup lang="ts">
const route = useRoute()
const symbol = route.params.symbol as string
const { get } = useApi()

// ── Static commodity metadata ────────────────────────────────────────────────
const COMMODITY_META: Record<string, any> = {
  XAUUSD: {
    icon: '🥇', name: 'Gold', category: 'Precious Metal', unit: 'USD/oz',
    description: 'Gold is the world\'s primary safe-haven asset and store of value. Central banks hold gold as a reserve asset, and investors buy it during periods of inflation, geopolitical instability, or currency weakness. Gold prices are quoted in USD per troy ounce and trade on major exchanges including COMEX. Supply comes mainly from mining, with recycled gold also contributing to the market.',
    producers: [{ code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'AU', name: 'Australia', flag: '🇦🇺' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }, { code: 'ZA', name: 'South Africa', flag: '🇿🇦' }, { code: 'US', name: 'United States', flag: '🇺🇸' }],
    tradeFlows: [{ pair: 'cn-au', label: 'China ↔ Australia' }, { pair: 'us-za', label: 'US ↔ South Africa' }],
    related: [{ symbol: 'XAGUSD', label: 'Silver', path: '/commodities/xagusd' }, { symbol: 'XPTUSD', label: 'Platinum', path: '/commodities/xptusd' }, { symbol: 'HG', label: 'Copper', path: '/commodities/hg' }],
  },
  XAGUSD: {
    icon: '🥈', name: 'Silver', category: 'Precious Metal', unit: 'USD/oz',
    description: 'Silver is both a precious metal and an industrial commodity, used in electronics, solar panels, and medical equipment. It trades alongside gold as a safe-haven asset but is more volatile due to its industrial demand. Silver prices are quoted in USD per troy ounce. Mexico, China, and Peru are the top producers. The gold-to-silver ratio is widely watched by commodity traders.',
    producers: [{ code: 'MX', name: 'Mexico', flag: '🇲🇽' }, { code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'PE', name: 'Peru', flag: '🇵🇪' }, { code: 'CL', name: 'Chile', flag: '🇨🇱' }],
    tradeFlows: [{ pair: 'mx-us', label: 'Mexico ↔ US' }, { pair: 'cn-us', label: 'China ↔ US' }],
    related: [{ symbol: 'XAUUSD', label: 'Gold', path: '/commodities/xauusd' }, { symbol: 'XPTUSD', label: 'Platinum', path: '/commodities/xptusd' }],
  },
  XPTUSD: {
    icon: '⚪', name: 'Platinum', category: 'Precious Metal', unit: 'USD/oz',
    description: 'Platinum is a rare precious metal used primarily in catalytic converters for automobiles, jewellery, and industrial applications. South Africa supplies over 70% of world platinum production. Demand is closely tied to auto manufacturing and tightening emissions regulations. Platinum often trades at a premium to gold but has fallen below gold in recent years due to the shift to electric vehicles.',
    producers: [{ code: 'ZA', name: 'South Africa', flag: '🇿🇦' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }, { code: 'ZW', name: 'Zimbabwe', flag: '🇿🇼' }],
    tradeFlows: [{ pair: 'za-us', label: 'South Africa ↔ US' }, { pair: 'za-jp', label: 'South Africa ↔ Japan' }],
    related: [{ symbol: 'XAUUSD', label: 'Gold', path: '/commodities/xauusd' }, { symbol: 'XAGUSD', label: 'Silver', path: '/commodities/xagusd' }],
  },
  WTI: {
    icon: '🛢️', name: 'Crude Oil (WTI)', category: 'Energy', unit: 'USD/bbl',
    description: 'West Texas Intermediate (WTI) is the primary US crude oil benchmark, priced in USD per barrel and traded on NYMEX. It is a light, sweet crude with low sulphur content, making it easy to refine into gasoline and diesel. WTI prices are driven by OPEC+ supply decisions, US shale output, global demand, and geopolitical events. It is the most liquid energy futures market in the world.',
    producers: [{ code: 'US', name: 'United States', flag: '🇺🇸' }, { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }, { code: 'CA', name: 'Canada', flag: '🇨🇦' }],
    tradeFlows: [{ pair: 'us-cn', label: 'US ↔ China' }, { pair: 'sa-cn', label: 'Saudi Arabia ↔ China' }, { pair: 'us-ca', label: 'US ↔ Canada' }],
    related: [{ symbol: 'BRENT', label: 'Brent Crude', path: '/commodities/brent' }, { symbol: 'NG', label: 'Natural Gas', path: '/commodities/ng' }, { symbol: 'GASOLINE', label: 'Gasoline', path: '/commodities/gasoline' }],
  },
  BRENT: {
    icon: '🛢️', name: 'Crude Oil (Brent)', category: 'Energy', unit: 'USD/bbl',
    description: 'Brent Crude is the global oil benchmark, representing about two-thirds of all internationally traded crude oil contracts. It is extracted from the North Sea and priced in USD per barrel on the ICE exchange. Brent trades at a slight premium to WTI. It is used to price oil from Europe, Africa, and the Middle East. OPEC+ production quotas are the primary driver of Brent prices.',
    producers: [{ code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }, { code: 'NG', name: 'Nigeria', flag: '🇳🇬' }, { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' }],
    tradeFlows: [{ pair: 'sa-cn', label: 'Saudi Arabia ↔ China' }, { pair: 'ru-cn', label: 'Russia ↔ China' }, { pair: 'ng-eu', label: 'Nigeria → Europe' }],
    related: [{ symbol: 'WTI', label: 'WTI Crude', path: '/commodities/wti' }, { symbol: 'NG', label: 'Natural Gas', path: '/commodities/ng' }],
  },
  NG: {
    icon: '🔥', name: 'Natural Gas', category: 'Energy', unit: 'USD/MMBtu',
    description: 'Natural gas is a fossil fuel used for electricity generation, heating, and industrial processes. US natural gas (Henry Hub) is the global benchmark, priced in USD per million British thermal units (MMBtu). Prices are highly seasonal, spiking in winter due to heating demand. LNG (liquefied natural gas) has created a global market, with Qatar, Australia, and the US as leading exporters.',
    producers: [{ code: 'US', name: 'United States', flag: '🇺🇸' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }, { code: 'QA', name: 'Qatar', flag: '🇶🇦' }, { code: 'AU', name: 'Australia', flag: '🇦🇺' }],
    tradeFlows: [{ pair: 'us-eu', label: 'US → Europe (LNG)' }, { pair: 'qa-jp', label: 'Qatar ↔ Japan' }, { pair: 'au-cn', label: 'Australia ↔ China' }],
    related: [{ symbol: 'WTI', label: 'WTI Crude', path: '/commodities/wti' }, { symbol: 'BRENT', label: 'Brent Crude', path: '/commodities/brent' }, { symbol: 'COAL', label: 'Coal', path: '/commodities/coal' }],
  },
  GASOLINE: {
    icon: '⛽', name: 'Gasoline', category: 'Energy', unit: 'USD/gal',
    description: 'RBOB Gasoline futures track the wholesale price of reformulated blendstock for oxygenate blending, the standard unleaded gasoline traded on NYMEX. Gasoline is refined primarily from crude oil. Prices are closely correlated with WTI crude but also influenced by refinery capacity, seasonal demand (summer driving season), and ethanol blending requirements.',
    producers: [{ code: 'US', name: 'United States', flag: '🇺🇸' }, { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦' }],
    tradeFlows: [{ pair: 'us-mx', label: 'US ↔ Mexico' }],
    related: [{ symbol: 'WTI', label: 'WTI Crude', path: '/commodities/wti' }, { symbol: 'BRENT', label: 'Brent Crude', path: '/commodities/brent' }],
  },
  HG: {
    icon: '🔶', name: 'Copper', category: 'Base Metal', unit: 'USD/lb',
    description: 'Copper is an essential industrial metal used in construction, electrical wiring, motors, and electronics. It is often called "Doctor Copper" because its price is considered a leading indicator of global economic health — demand rises with manufacturing and construction activity. Chile produces over 25% of world supply. China accounts for over 50% of global copper consumption.',
    producers: [{ code: 'CL', name: 'Chile', flag: '🇨🇱' }, { code: 'PE', name: 'Peru', flag: '🇵🇪' }, { code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'CD', name: 'DR Congo', flag: '🇨🇩' }],
    tradeFlows: [{ pair: 'cl-cn', label: 'Chile ↔ China' }, { pair: 'pe-cn', label: 'Peru ↔ China' }, { pair: 'cl-us', label: 'Chile ↔ US' }],
    related: [{ symbol: 'ALI', label: 'Aluminum', path: '/commodities/ali' }, { symbol: 'XAGUSD', label: 'Silver', path: '/commodities/xagusd' }],
  },
  ALI: {
    icon: '🔩', name: 'Aluminum', category: 'Base Metal', unit: 'USD/lb',
    description: 'Aluminum is the most widely used non-ferrous metal, found in packaging, transportation, construction, and aerospace. It is energy-intensive to produce, making aluminum prices sensitive to electricity costs. China produces over half of global aluminum output. The metal is highly recyclable — recycled aluminum uses only 5% of the energy required for primary production.',
    producers: [{ code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'IN', name: 'India', flag: '🇮🇳' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }, { code: 'CA', name: 'Canada', flag: '🇨🇦' }],
    tradeFlows: [{ pair: 'cn-us', label: 'China ↔ US' }, { pair: 'ru-eu', label: 'Russia → Europe' }],
    related: [{ symbol: 'HG', label: 'Copper', path: '/commodities/hg' }, { symbol: 'ZNC', label: 'Zinc', path: '/commodities/znc' }],
  },
  ZC: {
    icon: '🌽', name: 'Corn', category: 'Agriculture', unit: 'USc/bu',
    description: 'Corn (Maize) is the world\'s most produced grain, used for animal feed, ethanol fuel, and human food. US corn futures trade on CBOT in US cents per bushel. The United States produces about 30% of global corn output. Corn prices are driven by US growing conditions, export demand from China and Mexico, and ethanol mandates. The USDA crop reports are key price catalysts.',
    producers: [{ code: 'US', name: 'United States', flag: '🇺🇸' }, { code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'BR', name: 'Brazil', flag: '🇧🇷' }, { code: 'AR', name: 'Argentina', flag: '🇦🇷' }],
    tradeFlows: [{ pair: 'us-cn', label: 'US ↔ China' }, { pair: 'us-mx', label: 'US ↔ Mexico' }, { pair: 'br-cn', label: 'Brazil ↔ China' }],
    related: [{ symbol: 'ZW', label: 'Wheat', path: '/commodities/zw' }, { symbol: 'ZS', label: 'Soybeans', path: '/commodities/zs' }],
  },
  ZW: {
    icon: '🌾', name: 'Wheat', category: 'Agriculture', unit: 'USc/bu',
    description: 'Wheat is a global staple food crop and one of the most traded agricultural commodities. US wheat futures (CBOT) are priced in US cents per bushel. The Russia-Ukraine conflict in 2022 caused a major price spike as both countries are leading exporters. Wheat prices are influenced by weather conditions in major growing regions, export restrictions, and currency movements.',
    producers: [{ code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'IN', name: 'India', flag: '🇮🇳' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }, { code: 'US', name: 'United States', flag: '🇺🇸' }, { code: 'FR', name: 'France', flag: '🇫🇷' }],
    tradeFlows: [{ pair: 'ru-eg', label: 'Russia ↔ Egypt' }, { pair: 'us-eg', label: 'US ↔ Egypt' }, { pair: 'fr-dz', label: 'France → Algeria' }],
    related: [{ symbol: 'ZC', label: 'Corn', path: '/commodities/zc' }, { symbol: 'ZS', label: 'Soybeans', path: '/commodities/zs' }],
  },
  ZS: {
    icon: '🫘', name: 'Soybeans', category: 'Agriculture', unit: 'USc/bu',
    description: 'Soybeans are among the most important oilseed crops globally, used for animal feed, cooking oil, and biofuel. US soybean futures trade on CBOT. Brazil has overtaken the US as the world\'s largest soybean exporter. China is by far the largest importer, importing over 60% of globally traded soybeans for its livestock industry. US-China trade tensions directly impact soybean prices.',
    producers: [{ code: 'BR', name: 'Brazil', flag: '🇧🇷' }, { code: 'US', name: 'United States', flag: '🇺🇸' }, { code: 'AR', name: 'Argentina', flag: '🇦🇷' }],
    tradeFlows: [{ pair: 'br-cn', label: 'Brazil ↔ China' }, { pair: 'us-cn', label: 'US ↔ China' }, { pair: 'ar-cn', label: 'Argentina ↔ China' }],
    related: [{ symbol: 'ZC', label: 'Corn', path: '/commodities/zc' }, { symbol: 'ZW', label: 'Wheat', path: '/commodities/zw' }],
  },
  KC: {
    icon: '☕', name: 'Coffee', category: 'Agriculture', unit: 'USc/lb',
    description: 'Coffee (Arabica) futures trade on ICE in US cents per pound. Brazil is the world\'s largest producer, accounting for about 40% of global output, followed by Vietnam and Colombia. Coffee prices are sensitive to weather in Brazil (frost, drought), currency movements, and speculative positioning. Robusta coffee, traded on ICE Europe, is used primarily for instant coffee.',
    producers: [{ code: 'BR', name: 'Brazil', flag: '🇧🇷' }, { code: 'VN', name: 'Vietnam', flag: '🇻🇳' }, { code: 'CO', name: 'Colombia', flag: '🇨🇴' }, { code: 'ET', name: 'Ethiopia', flag: '🇪🇹' }],
    tradeFlows: [{ pair: 'br-us', label: 'Brazil ↔ US' }, { pair: 'co-us', label: 'Colombia ↔ US' }],
    related: [{ symbol: 'CC', label: 'Cocoa', path: '/commodities/cc' }, { symbol: 'SB', label: 'Sugar', path: '/commodities/sb' }],
  },
  CC: {
    icon: '🍫', name: 'Cocoa', category: 'Agriculture', unit: 'USD/MT',
    description: 'Cocoa futures trade on ICE in USD per metric tonne. Ivory Coast and Ghana together produce about 60% of the world\'s cocoa. Cocoa prices are highly sensitive to West African weather and political stability. Demand is driven by the global chocolate industry. In 2024, cocoa hit record highs due to El Niño-driven crop failures in West Africa.',
    producers: [{ code: 'CI', name: 'Ivory Coast', flag: '🇨🇮' }, { code: 'GH', name: 'Ghana', flag: '🇬🇭' }, { code: 'ID', name: 'Indonesia', flag: '🇮🇩' }, { code: 'CM', name: 'Cameroon', flag: '🇨🇲' }],
    tradeFlows: [{ pair: 'ci-nl', label: 'Ivory Coast → Netherlands' }, { pair: 'gh-nl', label: 'Ghana → Netherlands' }],
    related: [{ symbol: 'KC', label: 'Coffee', path: '/commodities/kc' }, { symbol: 'SB', label: 'Sugar', path: '/commodities/sb' }],
  },
  SB: {
    icon: '🍬', name: 'Sugar', category: 'Agriculture', unit: 'USc/lb',
    description: 'Raw sugar (Sugar No. 11) futures trade on ICE in US cents per pound. Brazil is the world\'s largest sugar exporter, with India also a major player. Sugar prices are influenced by Brazilian ethanol production economics (sugarcane is used for both sugar and ethanol), Indian government export policies, and weather conditions in growing regions.',
    producers: [{ code: 'BR', name: 'Brazil', flag: '🇧🇷' }, { code: 'IN', name: 'India', flag: '🇮🇳' }, { code: 'TH', name: 'Thailand', flag: '🇹🇭' }, { code: 'AU', name: 'Australia', flag: '🇦🇺' }],
    tradeFlows: [{ pair: 'br-cn', label: 'Brazil ↔ China' }, { pair: 'in-us', label: 'India ↔ US' }],
    related: [{ symbol: 'KC', label: 'Coffee', path: '/commodities/kc' }, { symbol: 'CC', label: 'Cocoa', path: '/commodities/cc' }, { symbol: 'CT', label: 'Cotton', path: '/commodities/ct' }],
  },
  CT: {
    icon: '🧵', name: 'Cotton', category: 'Agriculture', unit: 'USc/lb',
    description: 'Cotton No. 2 futures trade on ICE in US cents per pound. Cotton is the world\'s most widely used natural fibre, used in clothing, textiles, and industrial products. India and China are the largest producers, while the US is the largest exporter. Cotton prices are influenced by textile demand in Asia, US crop reports, and competition from synthetic fibres.',
    producers: [{ code: 'IN', name: 'India', flag: '🇮🇳' }, { code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'US', name: 'United States', flag: '🇺🇸' }, { code: 'BR', name: 'Brazil', flag: '🇧🇷' }],
    tradeFlows: [{ pair: 'us-cn', label: 'US ↔ China' }, { pair: 'us-bd', label: 'US → Bangladesh' }],
    related: [{ symbol: 'ZC', label: 'Corn', path: '/commodities/zc' }, { symbol: 'SB', label: 'Sugar', path: '/commodities/sb' }],
  },
  LE: {
    icon: '🐄', name: 'Live Cattle', category: 'Agriculture', unit: 'USc/lb',
    description: 'Live Cattle futures trade on CME in US cents per pound. The US is the world\'s largest beef producer and a major exporter. Cattle prices are influenced by feed costs (corn, hay), consumer beef demand, herd sizes, and export demand from Japan, South Korea, and China. Tight US cattle supplies in 2023-2024 pushed prices to record highs.',
    producers: [{ code: 'US', name: 'United States', flag: '🇺🇸' }, { code: 'BR', name: 'Brazil', flag: '🇧🇷' }, { code: 'AU', name: 'Australia', flag: '🇦🇺' }],
    tradeFlows: [{ pair: 'us-jp', label: 'US ↔ Japan' }, { pair: 'au-cn', label: 'Australia ↔ China' }, { pair: 'br-cn', label: 'Brazil ↔ China' }],
    related: [{ symbol: 'ZC', label: 'Corn', path: '/commodities/zc' }, { symbol: 'ZS', label: 'Soybeans', path: '/commodities/zs' }],
  },
  COAL: {
    icon: '⬛', name: 'Coal', category: 'Energy', unit: 'USD/MT',
    description: 'Thermal coal is a key fossil fuel used in power generation and steel production. Australia and Indonesia are the world\'s largest coal exporters. China and India are the largest consumers. Coal prices are influenced by energy demand, natural gas prices, and carbon emission regulations. The global energy transition is gradually reducing coal\'s share in electricity generation.',
    producers: [{ code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'AU', name: 'Australia', flag: '🇦🇺' }, { code: 'ID', name: 'Indonesia', flag: '🇮🇩' }, { code: 'IN', name: 'India', flag: '🇮🇳' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }],
    tradeFlows: [{ pair: 'au-cn', label: 'Australia ↔ China' }, { pair: 'id-cn', label: 'Indonesia ↔ China' }, { pair: 'au-jp', label: 'Australia ↔ Japan' }],
    related: [{ symbol: 'NG', label: 'Natural Gas', path: '/commodities/ng' }, { symbol: 'WTI', label: 'Crude Oil', path: '/commodities/wti' }],
  },
  NI: {
    icon: '🔘', name: 'Nickel', category: 'Base Metal', unit: 'USD/MT',
    description: 'Nickel is an essential metal used in stainless steel production and, increasingly, in electric vehicle batteries (NMC lithium-ion cells). Indonesia is the world\'s largest nickel producer. Prices are driven by stainless steel demand in China, EV battery demand growth, and supply developments in Indonesia and the Philippines.',
    producers: [{ code: 'ID', name: 'Indonesia', flag: '🇮🇩' }, { code: 'PH', name: 'Philippines', flag: '🇵🇭' }, { code: 'RU', name: 'Russia', flag: '🇷🇺' }, { code: 'CA', name: 'Canada', flag: '🇨🇦' }],
    tradeFlows: [{ pair: 'id-cn', label: 'Indonesia ↔ China' }, { pair: 'ru-eu', label: 'Russia → Europe' }],
    related: [{ symbol: 'HG', label: 'Copper', path: '/commodities/hg' }, { symbol: 'ALI', label: 'Aluminum', path: '/commodities/ali' }, { symbol: 'ZNC', label: 'Zinc', path: '/commodities/znc' }],
  },
  ZNC: {
    icon: '🔷', name: 'Zinc', category: 'Base Metal', unit: 'USD/MT',
    description: 'Zinc is primarily used to galvanize steel (anti-corrosion coating) and in die-casting alloys. China is both the largest producer and consumer of zinc. Prices respond to construction activity (the largest end-use sector), mining supply disruptions, and LME inventory levels. Zinc is mined as a co-product alongside lead, silver, and copper.',
    producers: [{ code: 'CN', name: 'China', flag: '🇨🇳' }, { code: 'AU', name: 'Australia', flag: '🇦🇺' }, { code: 'PE', name: 'Peru', flag: '🇵🇪' }, { code: 'IN', name: 'India', flag: '🇮🇳' }],
    tradeFlows: [{ pair: 'au-cn', label: 'Australia ↔ China' }, { pair: 'pe-cn', label: 'Peru ↔ China' }],
    related: [{ symbol: 'HG', label: 'Copper', path: '/commodities/hg' }, { symbol: 'ALI', label: 'Aluminum', path: '/commodities/ali' }, { symbol: 'NI', label: 'Nickel', path: '/commodities/ni' }],
  },
  PALM: {
    icon: '🌴', name: 'Palm Oil', category: 'Agriculture', unit: 'MYR/MT',
    description: 'Palm oil is the world\'s most widely consumed vegetable oil, used in food, cosmetics, and biofuels. Indonesia and Malaysia together produce over 85% of global palm oil supply. Prices are sourced from Bursa Malaysia Crude Palm Oil futures (FCPO), quoted in Malaysian Ringgit per metric tonne. Prices are influenced by weather (El Niño), biodiesel mandates, and demand from India and China.',
    producers: [{ code: 'ID', name: 'Indonesia', flag: '🇮🇩' }, { code: 'MY', name: 'Malaysia', flag: '🇲🇾' }, { code: 'TH', name: 'Thailand', flag: '🇹🇭' }],
    tradeFlows: [{ pair: 'id-cn', label: 'Indonesia ↔ China' }, { pair: 'my-in', label: 'Malaysia ↔ India' }, { pair: 'id-in', label: 'Indonesia ↔ India' }],
    related: [{ symbol: 'ZS', label: 'Soybeans', path: '/commodities/zs' }, { symbol: 'KC', label: 'Coffee', path: '/commodities/kc' }],
  },
}

const DEFAULT_META = {
  icon: '📊', name: symbol.toUpperCase(), category: 'Commodity', unit: 'USD',
  description: `${symbol.toUpperCase()} is a globally traded commodity. Track live prices, historical data, and market analysis on MetricsHour.`,
  producers: [], tradeFlows: [], related: [],
}

const meta = computed(() => COMMODITY_META[symbol.toUpperCase()] ?? DEFAULT_META)

// ── API data ─────────────────────────────────────────────────────────────────
const { data: asset } = useAsyncData(
  `commodity-${symbol}`,
  () => get<any>(`/api/assets/${symbol.toUpperCase()}`).catch(() => null),
)

const { data: pricesRaw } = useAsyncData(
  `commodity-prices-${symbol}`,
  () => get<any[]>(`/api/assets/${symbol.toUpperCase()}/prices?interval=1d&limit=365`).catch(() => []),
)

const { data: pageSummary } = useAsyncData(
  `summary-commodity-${symbol}`,
  () => get<any>(`/api/summaries/commodity/${symbol.toUpperCase()}`).catch(() => null),
  { server: false },
)

const { data: pageInsightsRaw } = useAsyncData(
  `insights-commodity-${symbol}`,
  () => get<any>(`/api/summaries/commodity_insight/${symbol.toUpperCase()}`).catch(() => null),
  { server: false },
)
const pageInsights = computed(() => pageInsightsRaw.value ? [pageInsightsRaw.value] : [])

// ── Price helpers ─────────────────────────────────────────────────────────────
const latestPrice = computed(() => {
  const p = pricesRaw.value
  if (!p?.length) return asset.value?.price ?? null
  return p[p.length - 1]
})

const change24h = computed(() => {
  const p = pricesRaw.value
  if (!p || p.length < 2) return null
  const prev = p[p.length - 2].c
  const curr = p[p.length - 1].c
  if (!prev) return null
  return ((curr - prev) / prev) * 100
})

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return '—'
  if (v >= 1000) return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  return `$${v.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')}`
}

function fmtTs(t: string | null | undefined): string {
  if (!t) return '—'
  return new Date(t).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

// ── Stats ──────────────────────────────────────────────────────────────────────
const stats = computed(() => {
  const p = pricesRaw.value
  if (!p?.length) return null
  const closes = p.map((x: any) => x.c).filter(Boolean)
  if (!closes.length) return null
  const high52 = Math.max(...closes)
  const low52  = Math.min(...closes)
  const avg    = closes.reduce((a: number, b: number) => a + b, 0) / closes.length
  const latest = closes[closes.length - 1]
  return [
    { label: '52W High', value: fmtPrice(high52) },
    { label: '52W Low',  value: fmtPrice(low52) },
    { label: '1Y Avg',   value: fmtPrice(avg) },
    { label: 'From 52W High', value: `${(((latest - high52) / high52) * 100).toFixed(1)}%` },
  ]
})

// ── Chart ─────────────────────────────────────────────────────────────────────
const RANGES = [
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
]
const activeRange = ref(90)

const chartOption = computed(() => {
  const p = pricesRaw.value
  if (!p?.length) return null
  const slice = p.slice(-activeRange.value)
  const dates  = slice.map((x: any) => x.t?.slice(0, 10))
  const closes = slice.map((x: any) => x.c)
  const isUp   = closes[closes.length - 1] >= closes[0]
  const color  = isUp ? '#34d399' : '#f87171'
  return {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 8, bottom: 40, containLabel: true },
    tooltip: { trigger: 'axis', backgroundColor: '#1f2937', borderColor: '#374151', textStyle: { color: '#fff', fontSize: 11 }, formatter: (p: any) => `${p[0].axisValue}<br/>${fmtPrice(p[0].value)}` },
    xAxis: { type: 'category', data: dates, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, interval: Math.floor(slice.length / 5) } },
    yAxis: { type: 'value', scale: true, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => fmtPrice(v) }, splitLine: { lineStyle: { color: '#1f2937' } } },
    series: [{ type: 'line', data: closes, smooth: true, symbol: 'none', lineStyle: { color, width: 2 }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '33' }, { offset: 1, color: color + '00' }] } } }],
  }
})

// ── SEO ───────────────────────────────────────────────────────────────────────
const _price = computed(() => latestPrice.value?.c ?? null)
const _priceStr = computed(() => _price.value ? fmtPrice(_price.value) : null)

const _seoTitle = computed(() =>
  _priceStr.value
    ? `${meta.value.name} Price Today: ${_priceStr.value} — MetricsHour`
    : `${meta.value.name} Price & Market Data — MetricsHour`,
)

const _seoDesc = computed(() => {
  const name = meta.value.name
  const price = _priceStr.value
  const chg   = change24h.value
  const parts: string[] = []
  if (price) {
    const chgStr = chg != null ? ` (${chg >= 0 ? '+' : ''}${chg.toFixed(2)}% today)` : ''
    parts.push(`${name} spot price: ${price}${chgStr}`)
  }
  parts.push(`52-week high/low, historical chart, and producer country data`)
  parts.push(`Track ${name.toLowerCase()} prices and global trade flows on MetricsHour`)
  return parts.join('. ') + '.'
})

const { public: { r2PublicUrl: _r2 } } = useRuntimeConfig()
const _ogImage = `${_r2}/og/section/commodities.png`

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: `https://metricshour.com/commodities/${symbol.toLowerCase()}/`,
  ogType: 'website',
  ogImage: _ogImage,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterCard: 'summary_large_image',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  twitterImage: _ogImage,
  robots: 'index, follow',
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/commodities/${symbol.toLowerCase()}/` }],
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: _seoTitle.value,
        url: `https://metricshour.com/commodities/${symbol.toLowerCase()}/`,
        description: _seoDesc.value,
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'Commodities', item: 'https://metricshour.com/commodities/' },
            { '@type': 'ListItem', position: 3, name: meta.value.name, item: `https://metricshour.com/commodities/${symbol.toLowerCase()}/` },
          ],
        },
      }),
    },
    ...(_price.value ? [{
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Dataset',
        name: `${meta.value.name} Price Data`,
        description: `Historical and current ${meta.value.name} price data in ${meta.value.unit}.`,
        url: `https://metricshour.com/commodities/${symbol.toLowerCase()}/`,
        creator: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com' },
        keywords: [`${meta.value.name} price`, `${symbol.toUpperCase()} price today`, `${meta.value.name} spot price`, `${meta.value.name} historical data`],
        variableMeasured: [
          { '@type': 'PropertyValue', name: `${meta.value.name} Spot Price`, value: String(_price.value), unitCode: meta.value.unit },
          ...(stats.value ? [
            { '@type': 'PropertyValue', name: '52-Week High', value: stats.value[0].value },
            { '@type': 'PropertyValue', name: '52-Week Low',  value: stats.value[1].value },
          ] : []),
        ],
      }),
    }] : []),
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: [
          {
            '@type': 'Question',
            name: `What is the current ${meta.value.name} price?`,
            acceptedAnswer: { '@type': 'Answer', text: _price.value ? `The current ${meta.value.name} price is ${_priceStr.value} (${meta.value.unit}). Prices are updated daily on MetricsHour.` : `${meta.value.name} prices are tracked daily on MetricsHour.` },
          },
          {
            '@type': 'Question',
            name: `What countries produce the most ${meta.value.name}?`,
            acceptedAnswer: { '@type': 'Answer', text: meta.value.producers.length ? `The top ${meta.value.name} producers are: ${meta.value.producers.map((p: any) => p.name).join(', ')}.` : `${meta.value.name} is produced in multiple countries globally.` },
          },
          {
            '@type': 'Question',
            name: `What drives ${meta.value.name} prices?`,
            acceptedAnswer: { '@type': 'Answer', text: `${meta.value.description.slice(0, 200)}...` },
          },
        ],
      }),
    },
  ],
})))
</script>
