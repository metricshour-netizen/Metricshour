<template>
  <!-- ── Market Ticker Strip ──────────────────────────────────────────────── -->
  <div
    v-if="tickerItems.length"
    class="w-full bg-[#060d14] border-b border-[#1a2332] overflow-hidden select-none"
    @mouseenter="tickerPaused = true"
    @mouseleave="tickerPaused = false"
  >
    <div class="ticker-wrap">
      <div class="ticker-track" :class="{ paused: tickerPaused }">
        <NuxtLink
          v-for="(item, i) in [...tickerItems, ...tickerItems]"
          :key="`tk-${i}`"
          :to="assetLink(item.symbol, item.assetType)"
          class="inline-flex items-center gap-1.5 px-5 py-2 border-r border-[#1a2332] shrink-0 hover:bg-white/5 transition-colors"
        >
          <span class="text-[11px] font-mono font-bold" :class="item.typeColor">{{ item.symbol }}</span>
          <span class="text-[11px] text-white tabular-nums font-semibold font-mono">{{ item.priceStr }}</span>
          <span class="text-[10px] tabular-nums font-semibold font-mono" :class="item.dir >= 0 ? 'text-emerald-400' : 'text-red-400'">
            {{ item.dir >= 0 ? '▲' : '▼' }}{{ item.changePct }}
          </span>
        </NuxtLink>
      </div>
    </div>
  </div>

  <main class="max-w-7xl mx-auto px-4">

    <!-- ── Hero ──────────────────────────────────────────────────────────── -->
    <section class="pt-12 pb-8 text-center">

      <!-- Live signal badges -->
      <div class="flex items-center justify-center gap-2 flex-wrap mb-6">
        <NuxtLink to="/countries" class="inline-flex items-center gap-1.5 bg-[#111827] border border-[#1f2937] hover:border-emerald-800 text-xs text-gray-400 px-3 py-1.5 rounded-full transition-colors">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block"></span>
          196 countries tracked
        </NuxtLink>
        <NuxtLink to="/markets" class="inline-flex items-center gap-1.5 bg-[#111827] border border-[#1f2937] hover:border-sky-800 text-xs text-gray-400 px-3 py-1.5 rounded-full transition-colors">
          <span class="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse inline-block"></span>
          130+ assets live
        </NuxtLink>
        <NuxtLink
          v-if="activeSpotlight"
          :to="activeSpotlight.link"
          class="inline-flex items-center gap-1.5 bg-[#111827] border text-xs px-3 py-1.5 rounded-full font-medium transition-colors"
          :class="[spotlightColors.text, spotlightColors.border, spotlightColors.hover]"
          :title="activeSpotlight.subtext"
        >
          <span class="w-1.5 h-1.5 rounded-full animate-pulse inline-block" :class="spotlightColors.dot"></span>
          <span v-if="activeSpotlight.tag" class="opacity-50 font-normal text-[10px] uppercase tracking-wider">{{ activeSpotlight.tag }} ·</span>
          {{ activeSpotlight.text }}
        </NuxtLink>
        <span v-else class="inline-flex items-center gap-1.5 bg-[#111827] border border-emerald-900 text-xs text-emerald-400 px-3 py-1.5 rounded-full font-medium">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block"></span>
          Loading intelligence...
        </span>
      </div>

      <!-- H1 — primary SEO heading -->
      <h1 class="text-3xl sm:text-4xl lg:text-5xl font-black text-white mb-4 leading-tight tracking-tight">
        Global Financial
        <span class="text-emerald-400"> Intelligence</span>
      </h1>
      <p class="text-gray-500 text-base sm:text-lg max-w-xl mx-auto mb-8 leading-relaxed">
        Connect stock revenue exposure, bilateral trade flows, and macro data — all in one place.
      </p>

      <!-- Search bar -->
      <div class="relative max-w-xl mx-auto mb-4" ref="searchContainer">
        <div class="relative">
          <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm pointer-events-none">🔍</span>
          <input
            v-model="searchQuery"
            @input="onSearchInput"
            @keydown.escape="closeSearch"
            @keydown.down.prevent="moveFocus(1)"
            @keydown.up.prevent="moveFocus(-1)"
            @keydown.enter.prevent="selectFocused"
            @focus="searchQuery.length >= 2 && (searchOpen = true)"
            placeholder="Search countries, stocks, trade pairs..."
            class="w-full bg-[#111827] border border-[#1f2937] focus:border-emerald-500 text-white rounded-lg px-4 py-3.5 pl-9 text-sm focus:outline-none transition-colors font-mono"
            autocomplete="off"
            spellcheck="false"
          />
          <button
            v-if="searchQuery"
            @click="closeSearch"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-300 text-lg leading-none"
          >×</button>
        </div>

        <!-- Autocomplete dropdown -->
        <div
          v-if="searchOpen && (searchResults.countries.length || searchResults.assets.length)"
          class="absolute top-full left-0 right-0 mt-1 bg-[#0d1117] border border-[#1f2937] rounded-lg overflow-hidden z-50 text-left shadow-2xl"
        >
          <template v-if="searchResults.countries.length">
            <div class="px-3 py-1.5 text-[10px] text-gray-600 uppercase tracking-widest font-bold border-b border-[#1f2937] bg-[#111827]">Countries</div>
            <NuxtLink
              v-for="(c, i) in searchResults.countries"
              :key="c.code"
              :to="`/countries/${c.code.toLowerCase()}`"
              @click="closeSearch"
              class="flex items-center gap-2.5 px-3 py-2.5 hover:bg-[#1f2937] transition-colors"
              :class="focusedIndex === i ? 'bg-[#1f2937]' : ''"
            >
              <span class="text-base" aria-hidden="true">{{ c.flag }}</span>
              <span class="text-sm text-white flex-1">{{ c.name }}</span>
              <span class="text-xs text-gray-600 font-mono">{{ c.code }}</span>
            </NuxtLink>
          </template>
          <template v-if="searchResults.assets.length">
            <div class="px-3 py-1.5 text-[10px] text-gray-600 uppercase tracking-widest font-bold border-b border-[#1f2937] bg-[#111827]" :class="searchResults.countries.length ? 'border-t' : ''">Stocks & Assets</div>
            <NuxtLink
              v-for="(a, i) in searchResults.assets"
              :key="a.symbol"
              :to="assetLink(a.symbol, a.asset_type)"
              @click="closeSearch"
              class="flex items-center gap-2.5 px-3 py-2.5 hover:bg-[#1f2937] transition-colors"
              :class="focusedIndex === (searchResults.countries.length + i) ? 'bg-[#1f2937]' : ''"
            >
              <span class="text-xs font-mono font-bold text-emerald-400 w-14 shrink-0">{{ a.symbol }}</span>
              <span class="text-sm text-gray-300 flex-1 truncate">{{ a.name }}</span>
              <span class="text-[10px] text-gray-600 capitalize shrink-0 bg-[#1f2937] px-1.5 py-0.5 rounded">{{ a.asset_type }}</span>
            </NuxtLink>
          </template>
        </div>

        <!-- No results -->
        <div
          v-else-if="searchOpen && searchQuery.length >= 2 && !searchLoading"
          class="absolute top-full left-0 right-0 mt-1 bg-[#0d1117] border border-[#1f2937] rounded-lg p-4 z-50 text-center"
        >
          <span class="text-sm text-gray-600">No results for "{{ searchQuery }}"</span>
        </div>
      </div>

      <!-- Keyboard hint row — replaces the "Explore →" button -->
      <div class="flex items-center justify-center gap-3 sm:gap-5 flex-wrap text-xs text-gray-600">
        <span class="flex items-center gap-1.5">
          <kbd class="inline-flex items-center px-1.5 py-0.5 rounded border border-[#374151] bg-[#111827] text-gray-400 font-mono text-[10px]">/</kbd>
          to search
        </span>
        <span class="text-gray-700">·</span>
        <NuxtLink to="/markets" class="hover:text-gray-400 transition-colors font-medium">Browse Markets →</NuxtLink>
        <span class="text-gray-700">·</span>
        <NuxtLink to="/feed" class="text-emerald-700 hover:text-emerald-500 transition-colors flex items-center gap-1 font-medium">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse inline-block"></span>
          Live Feed
        </NuxtLink>
      </div>

    </section>

    <!-- ── Economic Calendar Strip ────────────────────────────────────────── -->
    <section class="mb-10" v-if="calendarEvents.length">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <span class="text-[10px] font-mono font-bold text-gray-600 uppercase tracking-widest">Economic Calendar</span>
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block"></span>
        </div>
        <NuxtLink to="/feed" class="text-xs text-emerald-600 hover:text-emerald-400 transition-colors">View feed →</NuxtLink>
      </div>
      <div class="overflow-x-auto -mx-4 px-4">
        <div class="flex gap-3 min-w-max pb-1">
          <div
            v-for="ev in calendarEvents"
            :key="ev.id"
            class="bg-[#111827] border border-[#1f2937] rounded-lg p-3 min-w-[160px] shrink-0 hover:border-emerald-800 transition-colors cursor-pointer"
            @click="navigateTo(calendarLink(ev))"
          >
            <div class="text-[10px] font-mono text-gray-600 mb-1.5">{{ calEventTime(ev) }}</div>
            <div class="text-xs font-bold text-white leading-snug mb-2 line-clamp-2">{{ calEventTitle(ev) }}</div>
            <div class="flex items-end justify-between gap-2">
              <div>
                <div class="text-[9px] text-gray-600 uppercase tracking-wider">Actual</div>
                <div class="text-sm font-black font-mono" :class="calValueColor(ev)">{{ calValue(ev) }}</div>
              </div>
              <div class="text-right">
                <div class="text-[9px] text-gray-600 uppercase tracking-wider">Prior</div>
                <div class="text-xs font-mono text-gray-500">{{ calPrior(ev) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ── Outcome Cards ──────────────────────────────────────────────────── -->
    <section class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-12">

      <!-- Card 1: Country Risk -->
      <NuxtLink
        to="/countries"
        class="bg-[#111827] border border-[#1f2937] hover:border-emerald-700 rounded-xl p-5 transition-all group"
      >
        <div class="flex items-start gap-3 mb-3">
          <span class="text-xl">📊</span>
          <div>
            <div class="text-[10px] font-mono font-bold tracking-widest text-emerald-600 uppercase mb-0.5">Stock Revenue Exposure</div>
            <h2 class="text-sm font-black text-white group-hover:text-emerald-400 transition-colors leading-snug">
              Find Stocks by Country Risk
            </h2>
          </div>
        </div>
        <p class="text-xs text-gray-500 leading-relaxed mb-3">
          Which stocks benefit from Germany's recovery? Which are exposed to China tensions?
          Filter by geographic revenue from SEC EDGAR filings.
        </p>
        <div class="inline-flex items-center gap-1.5 text-xs text-emerald-600 group-hover:text-emerald-400 transition-colors font-semibold">
          Show me China-exposed stocks →
        </div>
      </NuxtLink>

      <!-- Card 2: Trade Wars -->
      <NuxtLink
        to="/trade"
        class="bg-[#111827] border border-[#1f2937] hover:border-amber-700 rounded-xl p-5 transition-all group"
      >
        <div class="flex items-start gap-3 mb-3">
          <span class="text-xl">🌐</span>
          <div>
            <div class="text-[10px] font-mono font-bold tracking-widest text-amber-600 uppercase mb-0.5">Bilateral Trade</div>
            <h2 class="text-sm font-black text-white group-hover:text-amber-400 transition-colors leading-snug">
              Track Trade Wars in Real-Time
            </h2>
          </div>
        </div>
        <p class="text-xs text-gray-500 leading-relaxed mb-3">
          US-China deficit widening? EUR-USD trade shifting?
          See which stocks are impacted immediately. Every bilateral relationship with top products.
        </p>
        <div class="inline-flex items-center gap-1.5 text-xs text-amber-600 group-hover:text-amber-400 transition-colors font-semibold">
          View Trade Relationships →
        </div>
      </NuxtLink>

      <!-- Card 3: Country Macro -->
      <NuxtLink
        to="/countries"
        class="bg-[#111827] border border-[#1f2937] hover:border-blue-700 rounded-xl p-5 transition-all group"
      >
        <div class="flex items-start gap-3 mb-3">
          <span class="text-xl">🌍</span>
          <div>
            <div class="text-[10px] font-mono font-bold tracking-widest text-blue-500 uppercase mb-0.5">Country Macro</div>
            <h2 class="text-sm font-black text-white group-hover:text-blue-400 transition-colors leading-snug">
              196 Countries. 80+ Indicators. Connected.
            </h2>
          </div>
        </div>
        <p class="text-xs text-gray-500 leading-relaxed mb-3">
          GDP, inflation, trade balance, debt — every country linked to every stock and trade pair.
          World Bank · IMF · UN Comtrade data.
        </p>
        <div class="inline-flex items-center gap-1.5 text-xs text-blue-500 group-hover:text-blue-400 transition-colors font-semibold">
          Browse Countries →
        </div>
      </NuxtLink>

      <!-- Card 4: Commodities chain -->
      <NuxtLink
        to="/commodities"
        class="bg-[#111827] border border-[#1f2937] hover:border-orange-700 rounded-xl p-5 transition-all group"
      >
        <div class="flex items-start gap-3 mb-3">
          <span class="text-xl">🛢️</span>
          <div>
            <div class="text-[10px] font-mono font-bold tracking-widest text-orange-500 uppercase mb-0.5">Commodities Chain</div>
            <h2 class="text-sm font-black text-white group-hover:text-orange-400 transition-colors leading-snug">
              Commodity → Economy → Portfolio
            </h2>
          </div>
        </div>
        <p class="text-xs text-gray-500 leading-relaxed mb-3">
          Oil spikes. Germany's exports fall. Auto stocks drop.
          See the full chain — before it hits your portfolio. 80+ instruments tracked.
        </p>
        <div class="inline-flex items-center gap-1.5 text-xs text-orange-500 group-hover:text-orange-400 transition-colors font-semibold">
          View Commodities →
        </div>
      </NuxtLink>

    </section>

    <!-- ── Live data: Top Stocks + G20 Countries ──────────────────────────── -->
    <section class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">

      <!-- Top Stocks by Market Cap -->
      <div>
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-bold text-white font-mono uppercase tracking-widest">Top Stocks</h2>
          <NuxtLink to="/stocks" class="text-xs text-emerald-600 hover:text-emerald-400 transition-colors">View all →</NuxtLink>
        </div>
        <div v-if="stocksPending" class="space-y-2">
          <div v-for="i in 5" :key="i" class="h-14 bg-[#111827] rounded-lg animate-pulse"/>
        </div>
        <div v-else-if="stocksError" class="text-red-400 text-sm">Failed to load stocks</div>
        <div v-else class="space-y-2">
          <NuxtLink
            v-for="s in topStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol.toLowerCase()}`"
            class="flex items-center gap-3 bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg px-3 py-2.5 transition-colors group"
          >
            <span class="text-lg leading-none shrink-0" aria-hidden="true">{{ s.country?.flag || '🏢' }}</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5">
                <span class="text-xs font-mono font-bold text-emerald-400 group-hover:text-emerald-300">{{ s.symbol }}</span>
                <span class="text-xs text-gray-500 truncate">{{ s.name }}</span>
              </div>
              <span class="text-[10px] text-gray-700">{{ s.sector }}</span>
            </div>
            <div class="text-right shrink-0">
              <div class="text-sm font-semibold tabular-nums font-mono" :class="s.price?.close ? 'text-white' : 'text-gray-600'">{{ s.price?.close ? fmtTickerPrice(s.price.close) : '—' }}</div>
              <div class="text-[10px] text-gray-600 tabular-nums font-mono mt-0.5">{{ fmtCap(s.market_cap_usd) }}</div>
            </div>
          </NuxtLink>
        </div>
      </div>

      <!-- G20 Countries -->
      <div>
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-bold text-white font-mono uppercase tracking-widest">G20 Countries</h2>
          <NuxtLink to="/countries" class="text-xs text-emerald-600 hover:text-emerald-400 transition-colors">View all 196 →</NuxtLink>
        </div>
        <div v-if="countriesPending" class="grid grid-cols-4 sm:grid-cols-5 gap-2">
          <div v-for="i in 20" :key="i" class="h-16 bg-[#111827] rounded-lg animate-pulse"/>
        </div>
        <div v-else class="grid grid-cols-4 sm:grid-cols-5 gap-2">
          <NuxtLink
            v-for="c in (countries?.length ? countries : G20_FALLBACK)"
            :key="c.code"
            :to="`/countries/${c.code.toLowerCase()}`"
            class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg p-2 transition-colors flex flex-col items-center"
          >
            <div class="text-xl mb-0.5" aria-hidden="true">{{ c.flag }}</div>
            <div class="text-[9px] font-mono text-gray-600 text-center leading-tight">{{ c.name.split(' ')[0] }}</div>
          </NuxtLink>
        </div>
      </div>

    </section>

    <!-- ── Major Trade Relationships ─────────────────────────────────────── -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-sm font-bold text-white font-mono uppercase tracking-widest">Major Trade Relationships</h2>
        <NuxtLink to="/trade" class="text-xs text-emerald-600 hover:text-emerald-400 transition-colors">View all →</NuxtLink>
      </div>
      <div v-if="tradesPending" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div v-for="i in 6" :key="i" class="h-20 bg-[#111827] rounded-lg animate-pulse"/>
      </div>
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <NuxtLink
          v-for="t in topTrades"
          :key="`${t.exporter?.code}-${t.importer?.code}`"
          :to="`/trade/${t.exporter?.slug ?? t.exporter?.code?.toLowerCase()}--${t.importer?.slug ?? t.importer?.code?.toLowerCase()}`"
          class="bg-[#111827] border border-[#1f2937] hover:border-emerald-500 rounded-lg p-4 transition-colors group"
        >
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xl" aria-hidden="true">{{ t.exporter?.flag }}</span>
            <span class="text-xs text-gray-600" aria-hidden="true">↔</span>
            <span class="text-xl" aria-hidden="true">{{ t.importer?.flag }}</span>
            <span class="text-xs font-semibold text-white ml-1 truncate group-hover:text-emerald-400 transition-colors">
              {{ t.exporter?.name }} – {{ t.importer?.name }}
            </span>
          </div>
          <div class="flex gap-4">
            <div>
              <div class="text-[10px] text-gray-600 uppercase tracking-wider">Total Trade</div>
              <div class="text-sm font-semibold text-white font-mono tabular-nums">{{ fmtUsd(t.trade_value_usd) }}</div>
            </div>
            <div>
              <div class="text-[10px] text-gray-600 uppercase tracking-wider">Balance</div>
              <div class="text-sm font-semibold font-mono tabular-nums" :class="(t.balance_usd ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ fmtUsd(t.balance_usd) }}
              </div>
            </div>
          </div>
        </NuxtLink>
      </div>
    </section>

    <!-- ── Newsletter capture ─────────────────────────────────────────────── -->
    <section class="max-w-xl mx-auto px-4 py-10 text-center">
      <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-2">Weekly Briefing</p>
      <h2 class="text-xl font-bold text-white mb-2">The macro moves that matter, explained.</h2>
      <p class="text-sm text-gray-400 mb-5">GDP shifts, trade flows, central bank decisions — plain language, every week. Free.</p>
      <NewsletterCapture source="homepage" button-text="Subscribe free" class="max-w-sm mx-auto" />
    </section>

    <!-- ── Data sources ───────────────────────────────────────────────────── -->
    <p class="text-center text-[11px] text-gray-700 pb-6">
      Data: World Bank · SEC EDGAR · UN Comtrade · REST Countries · IMF · CoinGecko
    </p>

  </main>
</template>

<script setup lang="ts">
const { get } = useApi()
const router = useRouter()

// ── G20 Countries ─────────────────────────────────────────────────────────────
const { data: countries, pending: countriesPending } = useAsyncData(
  'g20',
  () => get<any[]>('/api/countries', { is_g20: 'true' }).catch(() => []),
)

// Fallback G20 grid — shown when API hasn't loaded yet or is unreachable
const G20_FALLBACK = [
  { code: 'US', flag: '🇺🇸', name: 'United States' },
  { code: 'CN', flag: '🇨🇳', name: 'China' },
  { code: 'DE', flag: '🇩🇪', name: 'Germany' },
  { code: 'JP', flag: '🇯🇵', name: 'Japan' },
  { code: 'GB', flag: '🇬🇧', name: 'United Kingdom' },
  { code: 'FR', flag: '🇫🇷', name: 'France' },
  { code: 'IN', flag: '🇮🇳', name: 'India' },
  { code: 'BR', flag: '🇧🇷', name: 'Brazil' },
  { code: 'CA', flag: '🇨🇦', name: 'Canada' },
  { code: 'AU', flag: '🇦🇺', name: 'Australia' },
  { code: 'KR', flag: '🇰🇷', name: 'South Korea' },
  { code: 'IT', flag: '🇮🇹', name: 'Italy' },
  { code: 'RU', flag: '🇷🇺', name: 'Russia' },
  { code: 'MX', flag: '🇲🇽', name: 'Mexico' },
  { code: 'SA', flag: '🇸🇦', name: 'Saudi Arabia' },
  { code: 'AR', flag: '🇦🇷', name: 'Argentina' },
  { code: 'ZA', flag: '🇿🇦', name: 'South Africa' },
  { code: 'ID', flag: '🇮🇩', name: 'Indonesia' },
  { code: 'TR', flag: '🇹🇷', name: 'Turkey' },
  { code: 'EU', flag: '🇪🇺', name: 'European Union' },
]

// ── Top Stocks ────────────────────────────────────────────────────────────────
const { data: allStocks, pending: stocksPending, error: stocksError } = useAsyncData(
  'top-stocks',
  () => get<any[]>('/api/assets', { type: 'stock' }).catch(() => []),
)

// ── Trade pairs ───────────────────────────────────────────────────────────────
const { data: trades, pending: tradesPending } = useAsyncData(
  'top-trades',
  () => get<any[]>('/api/trade').catch(() => []),
)

const topStocks = computed(() => (allStocks.value ?? []).slice(0, 5))
const topTrades = computed(() => (trades.value ?? []).slice(0, 6))

// ── Economic Calendar (from recent feed events) ────────────────────────────
const { data: feedData } = useAsyncData(
  'home-calendar',
  () => get<any[]>('/api/feed').catch(() => []),
  { server: false },
)

const calendarEvents = computed(() => {
  const events = feedData.value ?? []
  return events
    .filter((e: any) => e.event_type === 'indicator_release' || e.event_type === 'macro_release')
    .slice(0, 8)
})

function calEventTime(ev: any): string {
  const d = new Date(ev.published_at)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const timeStr = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  return isToday ? `Today · ${timeStr}` : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ` · ${timeStr}`
}

function calEventTitle(ev: any): string {
  const ind = (ev.event_data?.indicator || ev.event_subtype || ev.title || '')
  return ind.replace(/_/g, ' ').replace(/pct$/, ' %').replace(/usd$/, ' USD').trim()
    || ev.title || 'Market Event'
}

function calValue(ev: any): string {
  const v = ev.event_data?.value
  if (v == null) return '—'
  const n = Number(v)
  if (isNaN(n)) return String(v)
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  return n.toFixed(Math.abs(n) < 100 ? 2 : 0)
}

function calPrior(_ev: any): string {
  // prior data not yet in DB — show dash
  return '—'
}

function calValueColor(ev: any): string {
  const v = Number(ev.event_data?.value)
  if (isNaN(v)) return 'text-white'
  if (ev.event_data?.indicator?.includes('unemployment') || ev.event_data?.indicator?.includes('inflation'))
    return v > 5 ? 'text-red-400' : 'text-emerald-400'
  return v >= 0 ? 'text-emerald-400' : 'text-red-400'
}

function calendarLink(ev: any): string {
  const data = ev.event_data || {}
  if (data.country_code) return `/countries/${data.country_code.toLowerCase()}`
  return '/feed'
}

// ── Search ────────────────────────────────────────────────────────────────────
const searchQuery = ref('')
const searchOpen = ref(false)
const searchLoading = ref(false)
const focusedIndex = ref(-1)
const searchResults = ref<{ countries: any[]; assets: any[] }>({ countries: [], assets: [] })
let searchTimeout: ReturnType<typeof setTimeout> | null = null

function onSearchInput() {
  if (searchTimeout) clearTimeout(searchTimeout)
  const q = searchQuery.value.trim()
  focusedIndex.value = -1
  if (q.length < 2) { searchResults.value = { countries: [], assets: [] }; searchOpen.value = false; return }
  searchTimeout = setTimeout(async () => {
    searchLoading.value = true
    try { const res = await get<any>('/api/search', { q }); searchResults.value = res; searchOpen.value = true }
    catch { /* silent */ }
    finally { searchLoading.value = false }
  }, 280)
}

function closeSearch() {
  searchOpen.value = false; searchQuery.value = ''
  searchResults.value = { countries: [], assets: [] }; focusedIndex.value = -1
}

const allResults = computed(() => [
  ...searchResults.value.countries.map((c: any) => ({ type: 'country', ...c })),
  ...searchResults.value.assets.map((a: any) => ({ type: 'asset', ...a })),
])

function moveFocus(dir: 1 | -1) {
  const max = allResults.value.length - 1
  if (max < 0) return
  focusedIndex.value = Math.max(-1, Math.min(max, focusedIndex.value + dir))
}

function selectFocused() {
  if (focusedIndex.value < 0) return
  const item = allResults.value[focusedIndex.value]
  if (!item) return
  item.type === 'country'
    ? router.push(`/countries/${item.code.toLowerCase()}`)
    : router.push(assetLink(item.symbol, item.asset_type))
  closeSearch()
}

// Keyboard shortcut: press "/" focuses search
if (import.meta.client) {
  document.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
      e.preventDefault()
      const input = document.querySelector('input[placeholder*="Search"]') as HTMLInputElement
      input?.focus()
    }
  })
  document.addEventListener('click', () => { searchOpen.value = false })
}

// ── Formatting ────────────────────────────────────────────────────────────────
function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9) return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(0)}M`
  return `${sign}$${abs.toLocaleString()}`
}

// ── Adaptive Spotlight ────────────────────────────────────────────────────────
// Map card type → Tailwind colour classes (explicit names so Tailwind JIT keeps them)
const CARD_COLORS: Record<string, { text: string; border: string; dot: string; hover: string }> = {
  stock_insight:     { text: 'text-emerald-400', border: 'border-emerald-900', dot: 'bg-emerald-400', hover: 'hover:border-emerald-600' },
  geo_revenue:       { text: 'text-sky-400',     border: 'border-sky-900',     dot: 'bg-sky-400',     hover: 'hover:border-sky-600' },
  country_insight:   { text: 'text-amber-400',   border: 'border-amber-900',   dot: 'bg-amber-400',   hover: 'hover:border-amber-600' },
  trade_insight:     { text: 'text-violet-400',  border: 'border-violet-900',  dot: 'bg-violet-400',  hover: 'hover:border-violet-600' },
  macro:              { text: 'text-orange-400',  border: 'border-orange-900',  dot: 'bg-orange-400',  hover: 'hover:border-orange-600' },
  commodity_insight: { text: 'text-rose-400',    border: 'border-rose-900',    dot: 'bg-rose-400',    hover: 'hover:border-rose-600' },
}
const spotlightColors = computed(() =>
  CARD_COLORS[activeSpotlight.value?.type ?? ''] ?? CARD_COLORS.stock_insight
)

// Infer country from timezone (privacy-safe — no network call, no storage)
function _tzToCountry(): string {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
    const region = tz.split('/')[0]
    const map: Record<string, string> = {
      America: 'US', Europe: 'GB', Asia: 'CN', Australia: 'AU',
      Pacific: 'AU', Africa: 'ZA', Indian: 'IN',
    }
    return map[region] ?? ''
  } catch { return '' }
}

const userCountry = ref('')
const { data: spotlightData, refresh: refreshSpotlight } = useAsyncData('spotlight',
  () => {
    const c = userCountry.value
    return get<any[]>(`/api/intelligence/spotlight${c ? '?country=' + c : ''}`).catch(() => [])
  },
  { server: false },
)
const spotlightIndex = ref(0)
const activeSpotlight = computed(() => (spotlightData.value ?? [])[spotlightIndex.value] ?? null)

let spotlightTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  const country = _tzToCountry()
  if (country) { userCountry.value = country; refreshSpotlight() }
  spotlightTimer = setInterval(() => {
    const len = (spotlightData.value ?? []).length
    if (len > 1) spotlightIndex.value = (spotlightIndex.value + 1) % len
  }, 6000)
})
onUnmounted(() => { if (spotlightTimer) clearInterval(spotlightTimer) })

// ── Market Ticker ─────────────────────────────────────────────────────────────
const TICKER_SYMBOLS = ['BTC', 'ETH', 'SOL', 'AAPL', 'NVDA', 'TSLA', 'MSFT', 'SPY', 'QQQ', 'XAUUSD', 'WTI', 'EURUSD', 'USDJPY', 'BNB', 'XAGUSD']
const tickerPaused = ref(false)

const { data: tickerRaw } = useAsyncData('ticker',
  () => get<any[]>('/api/assets').catch(() => []),
  { server: false },
)

function assetLink(symbol: string, assetType: string): string {
  const sym = symbol.toLowerCase()
  if (assetType === 'commodity') return `/commodities/${sym}`
  if (assetType === 'index') return `/indices/${sym}`
  return `/stocks/${sym}`
}

function tickerTypeColor(type: string): string {
  const map: Record<string, string> = {
    crypto: 'text-amber-400', stock: 'text-emerald-400', etf: 'text-sky-400',
    index: 'text-purple-400', commodity: 'text-blue-400', fx: 'text-teal-400', bond: 'text-rose-400',
  }
  return map[type] ?? 'text-gray-400'
}

function fmtTickerPrice(v: number): string {
  if (v >= 10000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  if (v >= 1) return `$${v.toFixed(2)}`
  return `$${v.toFixed(4)}`
}

const tickerItems = computed(() => {
  const assets = tickerRaw.value ?? []
  return TICKER_SYMBOLS
    .map(sym => (assets as any[]).find(a => a.symbol === sym))
    .filter(Boolean)
    .map((a: any) => {
      const p = a.price
      if (!p?.close) return null
      const open = p.open || p.close
      const dir = p.close >= open ? 1 : -1
      const pct = open > 0 ? Math.abs((p.close - open) / open * 100) : 0
      return { symbol: a.symbol, assetType: a.asset_type, priceStr: fmtTickerPrice(p.close), changePct: pct.toFixed(2) + '%', dir, typeColor: tickerTypeColor(a.asset_type) }
    })
    .filter(Boolean) as { symbol: string; priceStr: string; changePct: string; dir: number; typeColor: string }[]
})

// ── SEO ───────────────────────────────────────────────────────────────────────
useSeoMeta({
  title: 'MetricsHour — Global Financial Intelligence',
  description: 'Connect stock geographic revenue, bilateral trade flows, and country macro data. 196 countries, 130+ assets, 38,000+ trade pairs. Free forever.',
  ogTitle: 'MetricsHour — Global Financial Intelligence',
  ogDescription: 'Connect stock geographic revenue, bilateral trade flows, and country macro data. 196 countries, 130+ assets, 38,000+ trade pairs. Free forever.',
  ogUrl: 'https://metricshour.com/',
  ogType: 'website',
  ogImage: 'https://api.metricshour.com/og/section/home.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterTitle: 'MetricsHour — Global Financial Intelligence',
  twitterDescription: 'Connect stock geographic revenue, bilateral trade flows, and country macro data. 196 countries, 130+ assets, 38,000+ trade pairs. Free forever.',
  twitterImage: 'https://api.metricshour.com/og/section/home.png',
  twitterCard: 'summary_large_image',
})

useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@graph': [
        {
          '@type': 'Organization',
          name: 'MetricsHour',
          url: 'https://metricshour.com',
          logo: 'https://metricshour.com/favicon.svg',
          sameAs: ['https://twitter.com/metricshour'],
          description: 'Global financial intelligence platform — stocks, macro data, bilateral trade flows, and commodities.',
        },
        {
          '@type': 'WebSite',
          name: 'MetricsHour',
          url: 'https://metricshour.com',
          potentialAction: {
            '@type': 'SearchAction',
            target: { '@type': 'EntryPoint', urlTemplate: 'https://metricshour.com/?q={search_term_string}' },
            'query-input': 'required name=search_term_string',
          },
        },
      ],
    }),
  }],
})
</script>

<style scoped>
.ticker-wrap { overflow: hidden; width: 100%; }
.ticker-track { display: inline-flex; animation: ticker-scroll 45s linear infinite; }
.ticker-track.paused { animation-play-state: paused; }
@keyframes ticker-scroll {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}
</style>
