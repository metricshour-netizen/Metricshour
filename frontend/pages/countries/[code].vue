<template>
  <main class="max-w-7xl mx-auto px-4 py-10">
    <NuxtLink to="/countries/" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
      ← Countries
    </NuxtLink>

    <div v-if="pending" class="text-gray-500 text-sm">Loading...</div>
    <div v-else-if="error || !country" class="text-red-400 text-sm">Country not found.</div>

    <template v-else>
      <!-- Header -->
      <div class="mb-8">
        <div class="flex items-start gap-4 mb-3">
          <span class="text-5xl leading-none" aria-hidden="true">{{ country.flag }}</span>
          <div>
            <h1 class="text-2xl font-bold text-white">{{ country.name }} Economy: GDP, Trade &amp; Macro Data</h1>
            <p class="text-gray-500 text-sm">{{ country.name_official }}</p>
            <p class="text-gray-500 text-sm">{{ country.region }} · {{ country.subregion }}</p>
          </div>
        </div>
        <!-- Static SEO intro — SSR-rendered before pageSummary loads -->
        <p class="text-xs text-gray-500 leading-relaxed mt-3 max-w-2xl">
          {{ country.name }} economy dashboard — GDP, inflation, trade, and 80+ macroeconomic indicators.
          {{ country.region }}{{ country.income_level ? ' · ' + country.income_level.replace(/_/g, ' ') + ' economy' : '' }}.
          Top trade partners, global stock exposure, and monetary policy data from World Bank, IMF, and UN Comtrade.
        </p>
        <!-- Hero stats -->
        <div class="flex gap-6 mt-4 flex-wrap">
          <div>
            <span class="text-xs text-gray-500 block">GDP</span>
            <span class="text-lg font-bold text-white">{{ fmt('gdp_usd', country.indicators?.gdp_usd) }}</span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block">Population</span>
            <span class="text-lg font-bold text-white">{{ fmt('population', country.indicators?.population) }}</span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block">GDP Growth</span>
            <span class="text-lg font-bold" :class="(country.indicators?.gdp_growth_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
              {{ fmt('gdp_growth_pct', country.indicators?.gdp_growth_pct) }}
            </span>
          </div>
          <div>
            <span class="text-xs text-gray-500 block">Inflation</span>
            <span class="text-lg font-bold text-white">{{ fmt('inflation_pct', country.indicators?.inflation_pct) }}</span>
          </div>
        </div>
        <div class="flex items-center gap-3 mt-3 flex-wrap">
          <div class="flex gap-2 flex-wrap">
            <span
              v-for="g in country.groupings"
              :key="g"
              class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded"
            >{{ g }}</span>
          </div>
          <!-- Follow button -->
          <button
            class="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors"
            :class="isFollowing
              ? 'border-emerald-700 text-emerald-400 bg-emerald-900/20 hover:bg-red-900/20 hover:text-red-400 hover:border-red-700'
              : 'border-[#1f2937] text-gray-400 hover:border-emerald-700 hover:text-emerald-400'"
            @click="toggleFollow"
          >
            {{ isFollowing ? '★ Following' : '☆ Follow' }}
          </button>
        </div>
      </div>

      <!-- Page Summary -->
      <div v-if="pageSummary?.summary" class="page-summary bg-[#111827] border border-[#1f2937] rounded-lg p-4 mb-3 text-sm text-gray-400 leading-relaxed">
        {{ pageSummary.summary }}
      </div>

      <!-- Daily Insights -->
      <div v-if="pageInsights?.length" class="mb-6">
        <!-- Latest: full card -->
        <div class="relative border rounded-lg p-4 overflow-hidden bg-[#0d1520] border-emerald-900/50 page-insight-latest">
          <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"/>
          <div class="flex items-start gap-3">
            <span class="text-base mt-0.5 shrink-0 text-emerald-500" aria-hidden="true">◆</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                <span class="text-[10px] font-bold uppercase tracking-widest text-emerald-500">MetricsHour Intelligence</span>
                <span class="text-[10px] text-gray-600">· Daily analyst take</span>
                <span class="text-[10px] text-gray-700 ml-auto">{{ new Date(pageInsights[0].generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</span>
              </div>
              <p class="text-sm leading-relaxed text-gray-200">{{ pageInsights[0].summary }}</p>
            </div>
          </div>
        </div>
        <!-- History: compact list, 2 shown by default -->
        <div v-if="pageInsights.length > 1" class="mt-1.5 border border-[#1a2030] rounded-lg overflow-hidden">
          <div class="divide-y divide-[#131b27]">
            <div
              v-for="(insight, i) in pageInsights.slice(1)"
              v-show="showAllInsights || i < 2"
              :key="insight.generated_at"
              class="flex items-start gap-3 px-3 py-2 bg-[#0a0d14] cursor-pointer"
              @click="toggleInsight(insight.generated_at)"
            >
              <span class="text-[10px] text-gray-600 shrink-0 mt-0.5 w-16">{{ new Date(insight.generated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) }}</span>
              <p class="text-xs text-gray-500 leading-relaxed" :class="expandedInsights.has(insight.generated_at) ? '' : 'line-clamp-2'">{{ insight.summary }}</p>
            </div>
          </div>
          <button
            v-if="pageInsights.length > 3"
            class="w-full px-3 py-2 text-[10px] text-gray-600 hover:text-emerald-400 bg-[#0a0d14] border-t border-[#1a2030] transition-colors text-left"
            @click="showAllInsights = !showAllInsights"
          >
            {{ showAllInsights ? '↑ Show less' : `↓ Read more (${pageInsights.length - 3} more insights)` }}
          </button>
        </div>
      </div>

      <!-- Quick facts -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Capital</div>
          <div class="text-white font-medium text-sm">{{ country.capital || 'N/A' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Currency</div>
          <div class="text-white font-medium text-sm">{{ country.currency_code }} {{ country.currency_symbol }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">S&P Rating</div>
          <div class="text-white font-medium text-sm">{{ country.credit_rating_sp || 'N/A' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">Income Level</div>
          <div class="text-white font-medium text-sm capitalize">
            {{ country.income_level?.replace(/_/g, ' ') || 'N/A' }}
          </div>
        </div>
      </div>

      <!-- Key indicators — 6 card grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        <div v-for="kpi in keyIndicators" :key="kpi.label" class="bg-[#111827] border border-[#1f2937] rounded-lg p-4">
          <div class="text-xs text-gray-500 mb-1">{{ kpi.label }}</div>
          <div class="text-white font-semibold text-sm">{{ kpi.value }}</div>
        </div>
      </div>

      <!-- GDP Chart -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5 mb-4">
        <div class="flex items-center justify-between mb-1">
          <h2 class="text-sm font-bold text-white">GDP History</h2>
          <span v-if="gdpHistory?.length" class="text-xs text-emerald-400 font-medium tabular-nums">
            {{ fmt('gdp_usd', gdpHistory[gdpHistory.length - 1]?.gdp) }}
          </span>
        </div>
        <p class="text-xs text-gray-600 mb-3">Total annual economic output in current US dollars · Source: <a :href="`https://data.worldbank.org/country/${(country as any).code3?.toLowerCase()}`" target="_blank" rel="noopener noreferrer" class="underline hover:text-gray-400 transition-colors">World Bank</a></p>
        <div v-if="!gdpHistory?.length" class="h-36 flex items-center justify-center text-gray-600 text-xs">
          No GDP history data available
        </div>
        <EChartLine
          v-else
          :option="gdpChartOption"
          height="160px"
          :aria-label="`${country?.name} GDP history chart`"
        />
      </div>

      <!-- Macro indicators chart -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5 mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-bold text-white">Key Indicators Over Time</h2>
          <span class="text-[10px] text-gray-600"><a :href="`https://data.worldbank.org/country/${(country as any).code3?.toLowerCase()}`" target="_blank" rel="noopener noreferrer" class="underline hover:text-gray-400 transition-colors">World Bank</a> · 2000–2024</span>
        </div>
        <div v-if="timeseriesLoading" class="h-44 bg-[#0d1117] rounded-lg animate-pulse" />
        <div v-else-if="!hasTimeseries" class="h-44 flex items-center justify-center text-gray-600 text-xs">
          Indicator history not available
        </div>
        <EChartLine
          v-else
          :option="macroChartOption"
          height="176px"
          :aria-label="`${country?.name} GDP growth, inflation, interest rate and unemployment over time`"
        />
      </div>

      <!-- Macro indicators -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <IndicatorSection title="Economy" :rows="economyRows" :alertable="isLoggedIn" @set-alert="openMacroAlert" />
        <IndicatorSection title="Monetary" :rows="monetaryRows" :alertable="isLoggedIn" @set-alert="openMacroAlert" />
        <IndicatorSection title="Trade" :rows="tradeRows" :alertable="isLoggedIn" @set-alert="openMacroAlert" />
        <IndicatorSection title="Fiscal" :rows="fiscalRows" :alertable="isLoggedIn" @set-alert="openMacroAlert" />
        <IndicatorSection title="Social" :rows="socialRows" :alertable="isLoggedIn" @set-alert="openMacroAlert" />
        <IndicatorSection title="Governance" :rows="governanceRows" :alertable="isLoggedIn" @set-alert="openMacroAlert" />
      </div>

      <!-- Macro Alert Modal -->
      <Teleport to="body">
        <div v-if="macroAlertModal.open" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="macroAlertModal.open = false">
          <div class="absolute inset-0 bg-black/70 backdrop-blur-sm"/>
          <div class="relative bg-[#111827] border border-[#1f2937] rounded-xl p-6 w-full max-w-sm shadow-2xl">
            <button class="absolute top-4 right-4 text-gray-500 hover:text-white" @click="macroAlertModal.open = false">✕</button>
            <div class="mb-5">
              <p class="text-[10px] text-emerald-500 font-bold uppercase tracking-widest mb-1">Macro Alert</p>
              <p class="text-white font-bold text-lg">{{ country?.name }}</p>
              <p class="text-gray-400 text-sm">{{ macroAlertModal.label }}</p>
            </div>
            <!-- Condition toggle -->
            <div class="flex gap-2 mb-4">
              <button
                class="flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors"
                :class="macroAlertModal.condition === 'above' ? 'bg-emerald-900/40 border-emerald-500 text-emerald-400' : 'bg-[#0d1117] border-[#1f2937] text-gray-500'"
                @click="macroAlertModal.condition = 'above'"
              >Goes above ↑</button>
              <button
                class="flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors"
                :class="macroAlertModal.condition === 'below' ? 'bg-red-900/40 border-red-500 text-red-400' : 'bg-[#0d1117] border-[#1f2937] text-gray-500'"
                @click="macroAlertModal.condition = 'below'"
              >Drops below ↓</button>
            </div>
            <!-- Threshold input -->
            <div class="mb-4">
              <label class="text-[10px] text-gray-500 uppercase tracking-widest mb-1.5 block">Threshold</label>
              <div class="flex items-center gap-2 bg-[#0d1117] border border-[#1f2937] rounded-lg px-3 py-2">
                <input
                  v-model.number="macroAlertModal.threshold"
                  type="number"
                  step="any"
                  class="flex-1 bg-transparent text-white text-sm outline-none tabular-nums"
                  placeholder="Enter value"
                />
                <span class="text-gray-500 text-xs shrink-0">{{ macroAlertModal.unit }}</span>
              </div>
              <p v-if="macroAlertModal.currentValue != null" class="text-[10px] text-gray-600 mt-1">
                Current: {{ macroAlertModal.currentValue }}{{ macroAlertModal.unit }}
              </p>
            </div>
            <!-- Cooldown -->
            <div class="mb-5">
              <label class="text-[10px] text-gray-500 uppercase tracking-widest mb-1.5 block">Re-alert cooldown</label>
              <select v-model.number="macroAlertModal.cooldownDays" class="w-full bg-[#0d1117] border border-[#1f2937] rounded-lg px-3 py-2 text-white text-sm outline-none">
                <option :value="1">Every day (if condition holds)</option>
                <option :value="7">Once a week</option>
                <option :value="14">Every 2 weeks</option>
                <option :value="30">Once a month</option>
              </select>
            </div>
            <!-- Submit -->
            <button
              class="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm transition-colors disabled:opacity-50"
              :disabled="macroAlertModal.saving"
              @click="saveMacroAlert"
            >
              {{ macroAlertModal.saving ? 'Saving…' : 'Set Alert' }}
            </button>
            <p v-if="macroAlertModal.error" class="text-red-400 text-xs mt-2 text-center">{{ macroAlertModal.error }}</p>
            <p v-if="macroAlertModal.success" class="text-emerald-400 text-xs mt-2 text-center">Alert saved! You'll be notified via Telegram or email.</p>
          </div>
        </div>
      </Teleport>

      <!-- Trade Partners -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-6">
        <h2 class="text-sm font-bold text-white mb-1">Top Trade Partners</h2>
        <p class="text-xs text-gray-500 mb-4">
          Bilateral goods trade ranked by total volume — click any partner to view the full trade corridor breakdown. Source: <a href="https://comtradeplus.un.org" target="_blank" rel="noopener noreferrer" class="underline hover:text-gray-400 transition-colors">UN Comtrade</a>.
        </p>
        <div v-if="tradePartnersLoading" class="space-y-2">
          <div v-for="i in 5" :key="i" class="h-6 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="!tradePartners?.length" class="text-gray-600 text-xs">No trade data available</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-xs text-gray-500 border-b border-[#1f2937]">
                <th class="text-left py-2 font-medium" scope="col">Partner</th>
                <th class="text-right py-2 font-medium" scope="col">Exports</th>
                <th class="text-right py-2 font-medium" scope="col">Imports</th>
                <th class="text-right py-2 font-medium" scope="col">Balance</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="p in tradePartners"
                :key="p.partner.code"
                class="border-b border-[#1f2937] hover:bg-[#1f2937] transition-colors"
              >
                <td class="py-2.5">
                  <div class="flex items-center gap-2 flex-wrap">
                    <NuxtLink
                      :to="`/trade/${code.toLowerCase()}--${p.partner.slug ?? p.partner.code.toLowerCase()}`"
                      class="flex items-center gap-2 hover:text-emerald-400 transition-colors"
                    >
                      <span aria-hidden="true">{{ p.partner.flag }}</span>
                      <span class="text-white">{{ p.partner.name }}</span>
                    </NuxtLink>
                    <NuxtLink
                      :to="`/countries/${p.partner.code.toLowerCase()}`"
                      class="text-[10px] text-gray-600 hover:text-emerald-400 transition-colors whitespace-nowrap hidden sm:inline"
                    >macro →</NuxtLink>
                  </div>
                </td>
                <td class="text-right py-2.5 text-gray-300 tabular-nums">{{ fmtUsd(p.exports_usd) }}</td>
                <td class="text-right py-2.5 text-gray-300 tabular-nums">{{ fmtUsd(p.imports_usd) }}</td>
                <td class="text-right py-2.5 tabular-nums font-medium" :class="p.balance_usd >= 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ fmtUsd(p.balance_usd) }}
                </td>
              </tr>
            </tbody>
          </table>
          <!-- Corridor quick-links -->
          <div v-if="tradePartners?.length" class="mt-4 pt-4 border-t border-[#1f2937]">
            <p class="text-[10px] text-gray-600 uppercase tracking-wider mb-2">Explore trade corridors</p>
            <div class="flex flex-wrap gap-2">
              <NuxtLink
                v-for="p in (tradePartners || []).slice(0, 6)"
                :key="p.partner.code"
                :to="`/trade/${code.toLowerCase()}--${p.partner.slug ?? p.partner.code.toLowerCase()}`"
                class="flex items-center gap-1.5 text-[11px] text-emerald-700 hover:text-emerald-400 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-800 px-2 py-1 rounded transition-colors"
              >
                <span aria-hidden="true">{{ p.partner.flag }}</span>
                {{ country.name }} – {{ p.partner.name }} →
              </NuxtLink>
            </div>
          </div>
        </div>
      </div>

      <!-- Global stocks exposed -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-4">
        <h2 class="text-sm font-bold text-white mb-1">Global stocks exposed to {{ country.name }}</h2>
        <p class="text-xs text-gray-500 mb-4">
          Companies worldwide with significant revenue from {{ country.name }} — ranked by revenue share.
          Each bar shows what percentage of that company's total annual revenue comes from {{ country.name }}.
          Source: SEC EDGAR 10-K.
        </p>
        <div v-if="stocksLoading" class="space-y-2">
          <div v-for="i in 5" :key="i" class="h-6 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="!exposedStocks?.length" class="text-gray-600 text-xs">No stock exposure data available</div>
        <div v-else class="space-y-3">
          <NuxtLink
            v-for="s in exposedStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol.toLowerCase()}`"
            class="flex items-center gap-3 group hover:bg-[#1f2937] rounded-lg px-2 py-1 -mx-2 transition-colors"
          >
            <span class="w-16 text-xs font-mono font-bold text-emerald-400 group-hover:text-emerald-300 shrink-0">{{ s.symbol }}</span>
            <span class="text-xs text-gray-400 flex-1 truncate group-hover:text-gray-200 transition-colors">{{ s.name }}</span>
            <div
              class="w-24 bg-[#1f2937] rounded-full h-1.5 shrink-0"
              role="progressbar"
              :aria-valuenow="s.revenue_pct"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-label="`${s.symbol} earns ${s.revenue_pct.toFixed(1)}% of revenue from ${country.name}`"
            >
              <div class="bg-emerald-500 h-full rounded-full" :style="{ width: `${Math.min(s.revenue_pct, 100)}%` }"/>
            </div>
            <span class="text-xs text-white tabular-nums w-10 text-right shrink-0">{{ s.revenue_pct.toFixed(1) }}%</span>
          </NuxtLink>
          <p class="text-xs text-gray-600 mt-2">Source: SEC EDGAR 10-K · FY{{ exposedStocks[0]?.fiscal_year }}</p>
        </div>
      </div>

      <!-- Top local entities by market cap -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-6 mb-6">
        <h2 class="text-sm font-bold text-white mb-1">Top local entities by market cap</h2>
        <p class="text-xs text-gray-500 mb-4">Publicly traded companies headquartered in {{ country.name }}</p>
        <div v-if="localStocksLoading" class="space-y-2">
          <div v-for="i in 4" :key="i" class="h-10 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="!localStocks?.length" class="text-gray-600 text-xs">No local listed companies on record</div>
        <div v-else class="space-y-2">
          <NuxtLink
            v-for="(s, i) in localStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol.toLowerCase()}`"
            class="flex items-center gap-3 hover:bg-[#1f2937] rounded-lg px-2 py-2 -mx-2 transition-colors group"
          >
            <span class="text-xs text-gray-600 w-4 shrink-0">{{ i + 1 }}</span>
            <span class="text-xs font-mono font-bold text-emerald-400 w-14 shrink-0 group-hover:text-emerald-300">{{ s.symbol }}</span>
            <span class="text-xs text-gray-300 flex-1 truncate">{{ s.name }}</span>
            <span class="text-xs text-white tabular-nums font-semibold shrink-0">{{ fmtCap(s.market_cap_usd) }}</span>
            <span class="text-emerald-600 text-xs shrink-0">→</span>
          </NuxtLink>
        </div>
      </div>

      <!-- Exports & resources -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Major Exports</h2>
          <div v-if="country.major_exports?.length" class="flex gap-2 flex-wrap">
            <span
              v-for="e in country.major_exports"
              :key="e"
              class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded capitalize"
            >{{ e }}</span>
          </div>
          <div v-else class="text-xs text-gray-600">
            Export composition data pending —
            <NuxtLink :to="`/trade?country=${code.toUpperCase()}`" class="text-emerald-700 hover:text-emerald-500 transition-colors">see trade flows →</NuxtLink>
          </div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-lg p-5">
          <h2 class="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Natural Resources</h2>
          <div v-if="country.natural_resources?.length" class="flex gap-2 flex-wrap">
            <span
              v-for="r in country.natural_resources"
              :key="r"
              class="text-xs bg-[#1f2937] text-gray-300 px-2 py-1 rounded capitalize"
            >{{ r }}</span>
          </div>
          <div v-else class="text-xs text-gray-600">Natural resource data pending</div>
        </div>
      </div>

      <!-- Compare economies with top trade partners -->
      <div v-if="tradePartners?.length" class="bg-[#111827] border border-[#1f2937] rounded-lg p-5 mb-6">
        <h2 class="text-sm font-bold text-white mb-1">Compare {{ country.name }} economy</h2>
        <p class="text-xs text-gray-500 mb-3">
          Side-by-side GDP, inflation, and trade comparison with {{ country.name }}'s top trading partners.
        </p>
        <div class="flex flex-wrap gap-2">
          <NuxtLink
            v-for="p in (tradePartners || []).slice(0, 6)"
            :key="p.partner.code"
            :to="`/compare/${[code.toLowerCase(), p.partner.code.toLowerCase()].sort().join('-vs-')}`"
            class="flex items-center gap-1.5 text-xs text-emerald-600 hover:text-emerald-400 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-800 px-3 py-2 rounded-lg transition-colors"
          >
            <span aria-hidden="true">{{ country.flag }}</span>
            <span class="text-gray-600 text-[10px]">vs</span>
            <span aria-hidden="true">{{ p.partner.flag }}</span>
            {{ country.name }} vs {{ p.partner.name }} →
          </NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-600">Data: <a :href="`https://data.worldbank.org/country/${(country as any).code3?.toLowerCase()}`" target="_blank" rel="noopener noreferrer" class="underline hover:text-gray-400 transition-colors">World Bank</a> · REST Countries · <a :href="`https://www.imf.org/en/countries/${(country as any).code3}`" target="_blank" rel="noopener noreferrer" class="underline hover:text-gray-400 transition-colors">IMF</a> · <a href="https://comtradeplus.un.org" target="_blank" rel="noopener noreferrer" class="underline hover:text-gray-400 transition-colors">UN Comtrade</a> · SEC EDGAR</p>

      <ShareEmbed
        :embed-url="`/embed/country/${code.toLowerCase()}`"
        :download-url="`/api/countries/${code}/indicators/download`"
      />

      <!-- Newsletter -->
      <div class="mt-8 border border-gray-800 rounded-xl p-6 bg-gray-900/40">
        <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">Get macro moves explained every week.</p>
        <p class="text-xs text-gray-500 mb-4">GDP shifts, trade flows, central bank decisions — free.</p>
        <NewsletterCapture :source="`country_page_${code}`" button-text="Subscribe free" />
      </div>
    </template>
  </main>
  <AuthModal v-model="showAuthModal" />
</template>

<script setup lang="ts">
const route = useRoute()
const { get, post, del } = useApi()
const { r2Fetch } = useR2Fetch()
const { isLoggedIn } = useAuth()

const code = (route.params.code as string).toLowerCase()

const { data: country, pending, error } = await useAsyncData(
  `country-${code}`,
  () => r2Fetch<any>(`snapshots/countries/${code}.json`, `/api/countries/${code}`).catch(() => null),
)
if (!country.value) throw createError({ statusCode: 404, statusMessage: 'Country not found' })

// Trade partners, exposed stocks, and local stocks are bundled in the R2 snapshot.
// Use computed to extract them — no separate API call needed.
const tradePartners = computed(() => (country.value?.trade_partners ?? []).filter((p: any) => p?.partner?.code))
const tradePartnersLoading = computed(() => pending.value)
const exposedStocks = computed(() => country.value?.exposed_stocks ?? null)
const stocksLoading = computed(() => pending.value)
const localStocks = computed(() => country.value?.local_stocks ?? null)
const localStocksLoading = computed(() => pending.value)

// Charts load client-side only (large data, not needed for initial render)
const { data: gdpHistory, pending: gdpLoading } = useAsyncData(
  `gdp-history-${code}`,
  () => get<any[]>(`/api/countries/${code}/gdp-history`).catch(() => []),
  { server: false },
)

const { data: timeseries, pending: timeseriesLoading } = useAsyncData(
  `timeseries-${code}`,
  () => get<Record<string, any[]>>(`/api/countries/${code}/timeseries`, {
    keys: 'gdp_growth_pct,inflation_pct,interest_rate_pct,unemployment_pct',
  }).catch(() => ({})),
  { server: false },
)

const { data: pageSummary } = useAsyncData(
  `summary-country-${code}`,
  () => get<any>(`/api/summaries/country/${code.toUpperCase()}`).catch(() => null),
  { server: false },
)

const { data: pageInsights } = useAsyncData(
  `insights-country-${code}`,
  () => get<any[]>(`/api/insights/country/${code.toUpperCase()}`).catch(() => []),
  { server: false },
)

// ── Follow ────────────────────────────────────────────────────────────────────
const showAuthModal = ref(false)
const isFollowing = ref(false)

onMounted(async () => {
  // Fire-and-forget page view tracking
  post('/api/track', { entity_type: 'country', entity_code: code.toUpperCase() }).catch(() => {})

  if (!isLoggedIn.value || !country.value?.id) return
  try {
    const follows = await get<any[]>('/api/feed/follows')
    isFollowing.value = follows.some(
      (f: any) => f.entity_type === 'country' && f.entity_id === country.value!.id,
    )
  } catch { /* ignore */ }
})

async function toggleFollow() {
  if (!isLoggedIn.value) { showAuthModal.value = true; return }
  if (!country.value?.id) return
  try {
    if (isFollowing.value) {
      await del(`/api/feed/follows/country/${country.value.id}`)
      isFollowing.value = false
    } else {
      await post('/api/feed/follows', { entity_type: 'country', entity_id: country.value.id })
      isFollowing.value = true
    }
  } catch { /* ignore */ }
}

const { public: { r2PublicUrl } } = useRuntimeConfig()
const ogImageUrl = computed(() =>
  r2PublicUrl
    ? `${r2PublicUrl}/og/countries/${code.toLowerCase()}.png`
    : `https://cdn.metricshour.com/og/countries/${code.toLowerCase()}.png`,
)

// ── SEO helpers: inject real data for long-tail keyword ranking ───────────────
const _ind = computed(() => (country.value as any)?.indicators ?? {})

function _fmtGdp(v: number | null | undefined): string | null {
  if (v == null) return null
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return null
}

const _seoTitle = computed(() => {
  if (!country.value) return 'Country Economy — MetricsHour'
  const name = (country.value as any).name
  const gdp  = _fmtGdp(_ind.value.gdp_usd)
  const grow = _ind.value.gdp_growth_pct != null
    ? `${_ind.value.gdp_growth_pct >= 0 ? '+' : ''}${(_ind.value.gdp_growth_pct as number).toFixed(1)}% Growth`
    : null
  if (gdp && grow) return `${name} Economy: GDP ${gdp}, ${grow} — MetricsHour`
  return `${name} Economy & Macro Indicators — MetricsHour`
})

const _seoDesc = computed(() => {
  if (!country.value) return ''
  const c    = country.value as any
  const name = c.name
  const gdp  = _fmtGdp(_ind.value.gdp_usd)
  const grow = _ind.value.gdp_growth_pct != null
    ? `${_ind.value.gdp_growth_pct >= 0 ? '+' : ''}${(_ind.value.gdp_growth_pct as number).toFixed(1)}%`
    : null
  const inf  = _ind.value.inflation_pct != null ? `${(_ind.value.inflation_pct as number).toFixed(1)}%` : null
  const rate = _ind.value.interest_rate_pct != null ? `${(_ind.value.interest_rate_pct as number).toFixed(2)}%` : null
  const parts: string[] = []
  if (gdp && grow) parts.push(`${name}'s GDP is ${gdp} (${grow} growth)`)
  else parts.push(`${name} economy and macro data`)
  if (inf)  parts.push(`inflation ${inf}`)
  if (rate) parts.push(`interest rate ${rate}`)
  parts.push('80+ indicators from World Bank, IMF and UN Comtrade')
  return parts.join('. ') + '.'
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: `https://metricshour.com/countries/${code}/`,
  ogType: 'website',
  ogImage: ogImageUrl,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  ogImageType: 'image/png',
  twitterImage: ogImageUrl,
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  twitterCard: 'summary_large_image',
  robots: computed(() => (error.value && !country.value) ? 'noindex, follow' : 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1'),
})

function buildCountryFaqs(c: any) {
  const ind = c.indicators ?? {}
  const faqs: { '@type': string; name: string; acceptedAnswer: { '@type': string; text: string } }[] = []
  const push = (q: string, a: string) => faqs.push({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })

  if (ind.gdp_usd != null) {
    const gdp = ind.gdp_usd >= 1e12 ? `$${(ind.gdp_usd / 1e12).toFixed(1)} trillion` : `$${(ind.gdp_usd / 1e9).toFixed(0)} billion`
    const growth = ind.gdp_growth_pct != null ? ` growing at ${ind.gdp_growth_pct.toFixed(1)}% annually` : ''
    push(`What is ${c.name}'s GDP?`, `${c.name}'s GDP is ${gdp}${growth}. Source: World Bank.`)
  }
  if (ind.inflation_pct != null) {
    push(`What is ${c.name}'s inflation rate?`, `${c.name}'s inflation rate is ${ind.inflation_pct.toFixed(1)}% (latest annual figure). Source: World Bank / IMF.`)
  }
  if (ind.interest_rate_pct != null) {
    push(`What is ${c.name}'s central bank interest rate?`, `${c.name}'s central bank policy rate is ${ind.interest_rate_pct.toFixed(2)}%. Source: World Bank.`)
  }
  if (ind.unemployment_pct != null) {
    push(`What is ${c.name}'s unemployment rate?`, `${c.name}'s unemployment rate is ${ind.unemployment_pct.toFixed(1)}%. Source: World Bank.`)
  }
  if (ind.government_debt_gdp_pct != null) {
    push(`What is ${c.name}'s government debt as a percentage of GDP?`, `${c.name}'s general government debt is ${ind.government_debt_gdp_pct.toFixed(0)}% of GDP. Source: IMF.`)
  }
  if (c.groupings?.length) {
    const blocs = c.groupings.join(', ')
    push(`What international organisations is ${c.name} a member of?`, `${c.name} is a member of: ${blocs}. These memberships shape its trade policy, diplomatic relationships, and economic agreements.`)
  }
  if (c.credit_rating_sp) {
    push(`What is ${c.name}'s S&P credit rating?`, `${c.name} has an S&P sovereign credit rating of ${c.credit_rating_sp}. This rating reflects the country's ability to service its government debt.`)
  }
  if (c.major_exports) {
    push(`What does ${c.name} export?`, `${c.name}'s major exports include: ${c.major_exports}. Full bilateral trade flow data is tracked on MetricsHour.`)
  }
  return faqs
}

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/countries/${code}/` }],
  script: country.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: `${country.value.name} Economy & Macro Data — MetricsHour`,
        url: `https://metricshour.com/countries/${code}/`,
        description: `GDP, inflation, trade flows, and 80+ macro indicators for ${country.value.name}. Data from World Bank, IMF, and UN Comtrade.`,
        datePublished: '2026-03-01',
        dateModified: new Date().toISOString().slice(0, 10),
        mainEntity: { '@type': 'Country', name: country.value.name },
        speakable: {
          '@type': 'SpeakableSpecification',
          cssSelector: ['.page-summary', '.page-insight-latest'],
        },
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'Countries', item: 'https://metricshour.com/countries/' },
            { '@type': 'ListItem', position: 3, name: country.value.name, item: `https://metricshour.com/countries/${code}/` },
          ],
        },
      }),
    },
    ...(buildCountryFaqs(country.value).length ? [{
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: buildCountryFaqs(country.value),
      }),
    }] : []),
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify((() => {
        const ind = (country.value as any).indicators ?? {}
        const measured: any[] = []
        if (ind.gdp_usd != null)           measured.push({ '@type': 'PropertyValue', name: 'GDP (USD)', value: String(ind.gdp_usd), unitCode: 'USD' })
        if (ind.gdp_growth_pct != null)    measured.push({ '@type': 'PropertyValue', name: 'GDP Growth Rate', value: `${ind.gdp_growth_pct}%` })
        if (ind.inflation_pct != null)     measured.push({ '@type': 'PropertyValue', name: 'Inflation Rate', value: `${ind.inflation_pct}%` })
        if (ind.interest_rate_pct != null) measured.push({ '@type': 'PropertyValue', name: 'Central Bank Interest Rate', value: `${ind.interest_rate_pct}%` })
        if (ind.unemployment_pct != null)  measured.push({ '@type': 'PropertyValue', name: 'Unemployment Rate', value: `${ind.unemployment_pct}%` })
        if (ind.government_debt_gdp_pct != null) measured.push({ '@type': 'PropertyValue', name: 'Government Debt (% GDP)', value: `${ind.government_debt_gdp_pct}%` })
        return {
          '@context': 'https://schema.org',
          '@type': 'Dataset',
          name: `${country.value.name} Economic Indicators`,
          description: `GDP, inflation, interest rates and 80+ macro indicators for ${country.value.name}. Source: World Bank, IMF, UN Comtrade.`,
          url: `https://metricshour.com/countries/${code}/`,
          creator: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com' },
          license: 'https://metricshour.com/terms/',
          keywords: [`${country.value.name} GDP`, `${country.value.name} inflation`, `${country.value.name} economy`, `${country.value.name} macro data`],
          temporalCoverage: '2015/..',
          mainEntity: { '@type': 'Country', name: country.value.name },
          variableMeasured: measured,
        }
      })()),
    },
  ] : [],
})))

// ─── Formatting helpers ──────────────────────────────────────────────────────

function fmt(key: string, val: number | null | undefined): string {
  if (val === undefined || val === null) return 'N/A'

  if (key.endsWith('_usd')) {
    const abs = Math.abs(val)
    const sign = val < 0 ? '-' : ''
    if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`
    if (abs >= 1e9)  return `${sign}$${(abs / 1e9).toFixed(1)}B`
    if (abs >= 1e6)  return `${sign}$${(abs / 1e6).toFixed(1)}M`
    return `${sign}$${abs.toLocaleString()}`
  }

  if (key.endsWith('_pct')) return `${val.toFixed(1)}%`

  if (key === 'population') {
    if (val >= 1e9) return `${(val / 1e9).toFixed(2)}B`
    if (val >= 1e6) return `${(val / 1e6).toFixed(1)}M`
    return val.toLocaleString()
  }

  if (key === 'hdi') return val.toFixed(3)
  if (key === 'gini_coefficient') return val.toFixed(1)
  if (key === 'life_expectancy') return `${val.toFixed(1)} yrs`
  if (key === 'infant_mortality_per_1000') return `${val.toFixed(1)} / 1k`
  if (key.endsWith('_index')) return val.toFixed(2)

  return val.toFixed(1)
}

function fmtCap(v: number | null | undefined): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(1)}T`
  if (abs >= 1e9)  return `${sign}$${(abs / 1e9).toFixed(1)}B`
  if (abs >= 1e6)  return `${sign}$${(abs / 1e6).toFixed(0)}M`
  return `${sign}$${abs.toLocaleString()}`
}

function row(label: string, key: string) {
  const val = country.value?.indicators?.[key]
  const year = country.value?.indicator_years?.[key]
  return { label, value: fmt(key, val), raw: val ?? null, year: year ?? null }
}

// ─── Key indicator cards ─────────────────────────────────────────────────────

const keyIndicators = computed(() => {
  const ind = country.value?.indicators ?? {}
  return [
    { label: 'GDP', value: fmt('gdp_usd', ind.gdp_usd) },
    { label: 'GDP Growth', value: fmt('gdp_growth_pct', ind.gdp_growth_pct) },
    { label: 'Inflation', value: fmt('inflation_pct', ind.inflation_pct) },
    { label: 'Unemployment', value: fmt('unemployment_pct', ind.unemployment_pct) },
    { label: 'Interest Rate', value: fmt('interest_rate_pct', ind.interest_rate_pct) },
    { label: 'Debt / GDP', value: fmt('government_debt_gdp_pct', ind.government_debt_gdp_pct) },
  ]
})

// ─── Indicator sections ───────────────────────────────────────────────────────

// Helper that also carries indicatorKey for macro alerts
const irow = (label: string, key: string) => ({ ...row(label, key), indicatorKey: key })

const economyRows = computed(() => [
  irow('GDP', 'gdp_usd'),
  irow('GDP per capita', 'gdp_per_capita_usd'),
  irow('GDP growth', 'gdp_growth_pct'),
  irow('GDP (PPP)', 'gdp_ppp_usd'),
  irow('GDP per capita (PPP)', 'gdp_per_capita_ppp_usd'),
  row('Population', 'population'),
].filter(r => r.raw !== null))

const monetaryRows = computed(() => [
  irow('Inflation', 'inflation_pct'),
  irow('Interest rate', 'interest_rate_pct'),
  irow('Real interest rate', 'real_interest_rate_pct'),
  irow('Foreign reserves', 'foreign_reserves_usd'),
  irow('M2 Supply (% GDP)', 'money_supply_m2_gdp_pct'),
].filter(r => r.raw !== null))

const tradeRows = computed(() => {
  const ind = country.value?.indicators ?? {}
  const tradeBalance = (ind.exports_usd != null && ind.imports_usd != null)
    ? ind.exports_usd - ind.imports_usd
    : null
  const tradeOpenness = (ind.exports_usd != null && ind.imports_usd != null && ind.gdp_usd != null)
    ? ((ind.exports_usd + ind.imports_usd) / ind.gdp_usd) * 100
    : null
  return [
    irow('Exports', 'exports_usd'),
    irow('Imports', 'imports_usd'),
    { label: 'Trade balance', value: fmt('trade_balance_usd', tradeBalance), raw: tradeBalance },
    { label: 'Trade openness', value: fmt('trade_openness_pct', tradeOpenness), raw: tradeOpenness },
    irow('Current account (% GDP)', 'current_account_gdp_pct'),
    irow('FDI inflows', 'fdi_inflows_usd'),
  ].filter(r => r.raw !== null)
})

const fiscalRows = computed(() => [
  irow('Govt debt (% GDP)', 'government_debt_gdp_pct'),
  irow('Budget balance (% GDP)', 'budget_balance_gdp_pct'),
  irow('Tax revenue (% GDP)', 'tax_revenue_gdp_pct'),
  irow('Military spending (% GDP)', 'military_spending_gdp_pct'),
].filter(r => r.raw !== null))

const socialRows = computed(() => [
  irow('Unemployment', 'unemployment_pct'),
  irow('Life expectancy', 'life_expectancy'),
  irow('Gini coefficient', 'gini_coefficient'),
  irow('Internet penetration', 'internet_penetration_pct'),
  irow('Literacy rate', 'literacy_rate_pct'),
  row('Poverty rate', 'poverty_rate_pct'),
  row('Urban population', 'urban_population_pct'),
  row('Infant mortality', 'infant_mortality_per_1000'),
].filter(r => r.raw !== null))

const governanceRows = computed(() => [
  irow('Corruption control', 'control_of_corruption_index'),
  irow('Rule of law', 'rule_of_law_index'),
  irow('Political stability', 'political_stability_index'),
  irow('Govt effectiveness', 'government_effectiveness_index'),
  irow('Regulatory quality', 'regulatory_quality_index'),
  irow('Voice & accountability', 'voice_accountability_index'),
].filter(r => r.raw !== null))

// ─── Insight history expansion ───────────────────────────────────────────────
const showAllInsights = ref(false)
const expandedInsights = ref<Set<string>>(new Set())
const toggleInsight = (key: string) => {
  const s = new Set(expandedInsights.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedInsights.value = s
}

// ─── Macro Alert Modal ────────────────────────────────────────────────────────
const INDICATOR_UNITS: Record<string, string> = {
  gdp_growth_pct: '%', inflation_pct: '%', unemployment_pct: '%',
  government_debt_gdp_pct: '%', budget_balance_gdp_pct: '%',
  current_account_gdp_pct: '%', interest_rate_pct: '%',
  real_interest_rate_pct: '%', money_supply_m2_gdp_pct: '%',
  tax_revenue_gdp_pct: '%', military_spending_gdp_pct: '%',
  literacy_rate_pct: '%', internet_penetration_pct: '%',
  urban_population_pct: '%', gdp_usd: 'USD', gdp_per_capita_usd: 'USD',
  exports_usd: 'USD', imports_usd: 'USD', fdi_inflows_usd: 'USD',
  foreign_reserves_usd: 'USD',
}

const macroAlertModal = reactive({
  open: false,
  indicatorKey: '',
  label: '',
  condition: 'above' as 'above' | 'below',
  threshold: 0,
  currentValue: null as number | null,
  unit: '',
  cooldownDays: 7,
  saving: false,
  error: '',
  success: false,
})

function openMacroAlert(payload: { indicatorKey: string; label: string; currentValue: number }) {
  macroAlertModal.indicatorKey = payload.indicatorKey
  macroAlertModal.label = payload.label
  macroAlertModal.currentValue = payload.currentValue
  macroAlertModal.threshold = Math.round(payload.currentValue * 100) / 100
  macroAlertModal.unit = INDICATOR_UNITS[payload.indicatorKey] ?? ''
  macroAlertModal.condition = 'above'
  macroAlertModal.cooldownDays = 7
  macroAlertModal.error = ''
  macroAlertModal.success = false
  macroAlertModal.open = true
}

async function saveMacroAlert() {
  macroAlertModal.saving = true
  macroAlertModal.error = ''
  macroAlertModal.success = false
  try {
    await post('/api/alerts/macro', {
      country_code: code.toUpperCase(),
      indicator_name: macroAlertModal.indicatorKey,
      condition: macroAlertModal.condition,
      threshold: macroAlertModal.threshold,
      cooldown_days: macroAlertModal.cooldownDays,
    })
    macroAlertModal.success = true
    setTimeout(() => { macroAlertModal.open = false }, 1500)
  } catch (e: any) {
    macroAlertModal.error = e?.data?.detail ?? 'Failed to save alert.'
  } finally {
    macroAlertModal.saving = false
  }
}

// ─── GDP chart (ECharts) ──────────────────────────────────────────────────────

const gdpChartOption = computed(() => {
  const data = gdpHistory.value ?? []
  if (!data.length) return {}
  const years = data.map((d: any) => String(d.year))
  const values = data.map((d: any) => d.gdp)

  function fmtGdpAxis(v: number) {
    if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
    if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
    return `$${(v / 1e6).toFixed(0)}M`
  }

  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 12, bottom: 28, left: 60, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1117',
      borderColor: '#1f2937',
      borderWidth: 1,
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      formatter: (params: any[]) => {
        const p = params[0]
        return `<b>${p.name}</b><br/>GDP: <b style="color:#10b981">${fmtGdpAxis(p.value)}</b>`
      },
    },
    xAxis: {
      type: 'category',
      data: years,
      axisLine: { lineStyle: { color: '#1f2937' } },
      axisTick: { show: false },
      axisLabel: { color: '#4b5563', fontSize: 10, interval: Math.max(0, Math.floor(years.length / 5) - 1) },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: { color: '#4b5563', fontSize: 10, formatter: fmtGdpAxis },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#10b981', width: 2 },
      areaStyle: { color: 'rgba(16,185,129,0.08)' },
    }],
  }
})

// ─── Macro timeseries chart (ECharts multi-line) ──────────────────────────────

const INDICATOR_META: Record<string, { label: string; color: string }> = {
  gdp_growth_pct:   { label: 'GDP Growth %',  color: '#10b981' },
  inflation_pct:    { label: 'Inflation %',    color: '#f59e0b' },
  interest_rate_pct:{ label: 'Interest Rate %',color: '#60a5fa' },
  unemployment_pct: { label: 'Unemployment %', color: '#a78bfa' },
}

const hasTimeseries = computed(() => {
  const ts = timeseries.value ?? {}
  return Object.values(ts).some((v: any) => v?.length > 0)
})

const macroChartOption = computed(() => {
  const ts = timeseries.value ?? {}
  const allYears = [...new Set(
    Object.values(ts).flatMap((arr: any) => arr.map((d: any) => d.year))
  )].sort() as number[]

  const series = Object.entries(ts)
    .filter(([, arr]) => (arr as any[]).length > 0)
    .map(([key, arr]) => {
      const meta = INDICATOR_META[key] ?? { label: key, color: '#6b7280' }
      const yearMap = Object.fromEntries((arr as any[]).map((d: any) => [d.year, d.value]))
      return {
        name: meta.label,
        type: 'line',
        data: allYears.map(y => yearMap[y] ?? null),
        connectNulls: false,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: meta.color, width: 1.5 },
        itemStyle: { color: meta.color },
      }
    })

  return {
    backgroundColor: 'transparent',
    legend: {
      top: 0,
      right: 0,
      textStyle: { color: '#9ca3af', fontSize: 10 },
      itemWidth: 12,
      itemHeight: 3,
    },
    grid: { top: 28, right: 12, bottom: 28, left: 48, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1117',
      borderColor: '#1f2937',
      borderWidth: 1,
      textStyle: { color: '#e5e7eb', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: allYears.map(String),
      axisLine: { lineStyle: { color: '#1f2937' } },
      axisTick: { show: false },
      axisLabel: { color: '#4b5563', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: {
        color: '#4b5563',
        fontSize: 10,
        formatter: (v: number) => `${v.toFixed(1)}%`,
      },
    },
    series,
  }
})
</script>
