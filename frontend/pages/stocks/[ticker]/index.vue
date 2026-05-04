<template>
  <div>
    <!-- Hero band -->
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/stocks/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Stocks
        </NuxtLink>

        <div v-if="pending" class="h-20 flex items-center">
          <div class="space-y-2">
            <div class="h-8 w-40 bg-[#1f2937] rounded animate-pulse"/>
            <div class="h-4 w-64 bg-[#1f2937] rounded animate-pulse"/>
          </div>
        </div>
        <div v-else-if="error || !stock" class="text-red-400 text-sm py-6">Stock not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <!-- Left: identity -->
            <div class="flex items-start gap-4">
              <div class="w-14 h-14 rounded-xl bg-[#1f2937] border border-[#374151] flex items-center justify-center text-2xl shrink-0" aria-hidden="true">
                {{ stock.country?.flag || '🏢' }}
              </div>
              <div>
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <h1 class="text-3xl font-extrabold text-white tracking-tight">{{ stock.name }} ({{ stock.symbol }}) — Revenue by Country</h1>
                  <span class="text-xs bg-[#1f2937] text-gray-400 px-2 py-1 rounded-md">{{ stock.exchange }}</span>
                  <span v-if="stock.sector" class="text-xs border border-emerald-800 text-emerald-400 px-2 py-1 rounded-md">{{ stock.sector }}</span>
                  <span v-if="geoRisk" class="text-xs font-bold px-2 py-1 rounded-md"
                    :class="{
                      'bg-red-900/40 text-red-400 border border-red-800': geoRisk === 'HIGH',
                      'bg-yellow-900/40 text-yellow-400 border border-yellow-800': geoRisk === 'MEDIUM',
                      'bg-emerald-900/40 text-emerald-400 border border-emerald-800': geoRisk === 'LOW',
                    }">{{ geoRisk }} GEO RISK</span>
                </div>
                <p class="text-gray-300 font-medium">{{ stock.symbol }}</p>
                <p class="text-xs text-gray-500 leading-relaxed mt-1 max-w-lg">
                  {{ stock.sector }} company{{ stock.country ? ` headquartered in ${stock.country.name}` : '' }}.
                  Geographic revenue tracked across {{ stock.country_revenues?.length || 'multiple' }} markets — source: SEC EDGAR 10-K.
                </p>
                <p v-if="stock.country" class="text-gray-600 text-xs mt-0.5">{{ stock.country.name }} · {{ stock.industry || stock.sector }}</p>
              </div>
            </div>

            <!-- Right: price + follow -->
            <div class="flex items-start gap-4">
              <div class="text-right">
                <div class="text-4xl font-extrabold text-white tabular-nums tracking-tight">
                  {{ stock.price ? fmtStockPrice(stock.price.close, stock.currency) : '—' }}
                </div>
                <div v-if="stock.price?.change_pct != null" class="text-sm font-bold tabular-nums mt-1"
                     :class="stock.price.change_pct >= 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ stock.price.change_pct >= 0 ? '▲' : '▼' }} {{ Math.abs(stock.price.change_pct).toFixed(2) }}% today
                </div>
                <div class="text-xs text-gray-600 mt-1">
                  <template v-if="stock.price">Last updated · <span class="font-mono text-emerald-700">{{ fmtPriceTs(stock.price.fetched_at || stock.price.timestamp) }}</span></template>
                  <template v-else>Awaiting price feed</template>
                </div>
                <div class="flex items-center gap-2 mt-1">
                  <div class="text-sm font-semibold text-gray-400">{{ fmtCap(stock.market_cap_usd) }} market cap</div>
                  <span v-if="stock.market_open === true" class="inline-flex items-center gap-1 text-[10px] font-mono font-semibold text-emerald-400">
                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block"></span>Open
                  </span>
                  <span v-else-if="stock.market_open === false" class="inline-flex items-center gap-1 text-[10px] font-mono text-gray-600">
                    <span class="w-1.5 h-1.5 rounded-full bg-gray-600 inline-block"></span>Closed
                  </span>
                </div>
              </div>
              <button
                class="mt-1 flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-lg border transition-colors"
                :class="isFollowing
                  ? 'border-emerald-700 text-emerald-400 bg-emerald-900/20 hover:bg-red-900/20 hover:text-red-400 hover:border-red-700'
                  : 'border-[#374151] text-gray-400 hover:border-emerald-600 hover:text-emerald-400'"
                @click="toggleFollow"
              >{{ isFollowing ? '★ Following' : '☆ Follow' }}</button>
              <button
                @click="isLoggedIn ? (showAlertModal = true) : (showEmailAlertModal = true)"
                class="mt-1 flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-lg border border-amber-800 text-amber-400 hover:bg-amber-900/20 transition-colors"
              >🔔 Alert</button>
              <!-- "Why moving" badge — only shown when stock has >3% move -->
              <NuxtLink
                v-if="isSignificantMove"
                :to="`/stocks/${ticker.toLowerCase()}/moving/`"
                class="mt-1 flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-lg border transition-colors animate-pulse"
                :class="stock.price.change_pct >= 0
                  ? 'border-emerald-700 text-emerald-400 bg-emerald-900/10 hover:bg-emerald-900/20'
                  : 'border-red-800 text-red-400 bg-red-900/10 hover:bg-red-900/20'"
              >
                {{ stock.price.change_pct >= 0 ? '▲' : '▼' }} Why moving?
              </NuxtLink>
              <ShareCard
                type="stock"
                :slug="stock.symbol"
                :name="stock.name"
              />
            </div>
          </div>
        </template>
      </div>
    </div>

    <main class="max-w-7xl mx-auto px-4 py-8" v-if="stock">

      <!-- Stats row -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Market Cap</div>
          <div class="text-white font-bold text-lg">{{ fmtCap(stock.market_cap_usd) }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Exchange</div>
          <div class="text-white font-bold text-lg">{{ stock.exchange || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Sector</div>
          <div class="text-white font-bold text-sm leading-snug mt-1">{{ stock.sector || '—' }}</div>
        </div>
        <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
          <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Geo Markets</div>
          <div class="text-white font-bold text-lg">{{ stock.country_revenues?.length || '—' }}</div>
          <div class="text-[10px] text-gray-600 mt-0.5">countries tracked</div>
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
        <!-- History: compact scrollable log -->
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

      <!-- Geographic Revenue — core differentiator -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <div class="flex items-start justify-between mb-5 flex-wrap gap-3">
          <div>
            <h2 class="text-base font-bold text-white mb-1">Geographic Revenue Exposure</h2>
            <p class="text-xs text-gray-500">Where {{ stock.symbol }} earns its revenue — SEC EDGAR 10-K filings</p>
          </div>
          <div v-if="geoRisk" class="text-right">
            <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Concentration Risk</div>
            <span class="text-sm font-bold px-3 py-1.5 rounded-lg"
              :class="{
                'bg-red-900/40 text-red-400 border border-red-800': geoRisk === 'HIGH',
                'bg-yellow-900/40 text-yellow-400 border border-yellow-800': geoRisk === 'MEDIUM',
                'bg-emerald-900/40 text-emerald-400 border border-emerald-800': geoRisk === 'LOW',
              }">{{ geoRisk }}</span>
            <div class="text-[10px] text-gray-600 mt-1">{{ topCountryPct }}% in largest market</div>
          </div>
        </div>

        <div v-if="stock.country_revenues?.length" class="space-y-3.5">
          <div v-for="(r, i) in stock.country_revenues" :key="r.country.code" class="flex items-center gap-3">
            <NuxtLink
              :to="`/countries/${r.country.code.toLowerCase()}`"
              class="w-32 sm:w-44 flex items-center gap-2 shrink-0 min-w-0 group"
            >
              <span class="text-base shrink-0" aria-hidden="true">{{ r.country.flag }}</span>
              <span class="text-xs text-gray-300 group-hover:text-emerald-400 truncate flex-1 transition-colors">{{ r.country.name }}</span>
            </NuxtLink>
            <div
              class="flex-1 bg-[#1f2937] rounded-full h-3 overflow-hidden"
              role="progressbar"
              :aria-valuenow="r.revenue_pct"
              aria-valuemin="0"
              aria-valuemax="100"
              :aria-label="`${r.country.name}: ${r.revenue_pct.toFixed(1)}% of ${stock.symbol} revenue`"
            >
              <div
                class="h-full rounded-full transition-all"
                :class="i === 0 ? 'bg-emerald-400' : i === 1 ? 'bg-emerald-500' : i === 2 ? 'bg-emerald-600' : 'bg-[#374151]'"
                :style="{ width: `${r.revenue_pct}%` }"
              />
            </div>
            <span class="text-sm font-bold text-white tabular-nums w-12 text-right shrink-0">
              {{ r.revenue_pct.toFixed(1) }}%
            </span>
            <NuxtLink
              :to="`/countries/${r.country.code.toLowerCase()}`"
              class="shrink-0 text-[10px] font-semibold text-emerald-600 hover:text-emerald-400 border border-emerald-900 hover:border-emerald-600 px-2 py-1 rounded transition-colors whitespace-nowrap hidden sm:inline-flex items-center gap-0.5"
            >
              View country →
            </NuxtLink>
          </div>
          <!-- Mobile: tap country name to go to dashboard -->
          <p class="text-[10px] text-gray-600 sm:hidden mt-1">Tap a country name to view its macro dashboard</p>
          <p class="text-xs text-gray-600 mt-3 pt-3 border-t border-[#1f2937]">
            Source: SEC EDGAR 10-K · FY{{ stock.country_revenues[0]?.fiscal_year }}
          </p>
        </div>

        <div v-else class="py-4 text-sm text-gray-600">
          SEC EDGAR geographic revenue data not yet available for {{ stock.symbol }}.
          Revenue breakdown is sourced from annual 10-K filings and may not be available for all companies.
        </div>
      </div>

      <!-- Earnings Impact Estimate -->
      <div v-if="earningsImpact" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <div class="flex items-start justify-between mb-3 flex-wrap gap-2">
          <h2 class="text-base font-bold text-white">{{ $t('earningsImpact.title') }}</h2>
          <span class="text-[10px] text-gray-600 bg-[#1f2937] px-2 py-1 rounded">{{ $t('earningsImpact.disclaimer') }}</span>
        </div>
        <p class="text-sm text-gray-300 leading-relaxed">
          {{ $t('earningsImpact.formula', {
            country: earningsImpact.country,
            value: earningsImpact.impact >= 0 ? `+$${earningsImpact.impact.toFixed(2)}` : `-$${Math.abs(earningsImpact.impact).toFixed(2)}`
          }) }}
        </p>
        <p class="text-[10px] text-gray-600 mt-2">{{ $t('earningsImpact.source') }}</p>
      </div>

      <!-- Macro Risk Timeline -->
      <div v-if="revenueHistory && revenueHistory.length >= 3" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <div class="flex items-center justify-between mb-1">
          <h2 class="text-base font-bold text-white">{{ $t('macroRisk.title') }}</h2>
          <span class="text-[10px] text-gray-500">{{ $t('macroRisk.source') }}</span>
        </div>
        <p class="text-xs text-gray-600 mb-4">China revenue % vs CNY/USD exchange rate · {{ revenueHistory[0]?.year }}–{{ revenueHistory[revenueHistory.length - 1]?.year }}</p>
        <EChartLine
          :option="macroRiskChartOption"
          height="180px"
          :aria-label="`${stock.symbol} China revenue vs CNY/USD over time`"
        />
      </div>

      <!-- Price Chart — full width above the 2-col grid -->
      <div class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6">
        <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 class="text-base font-bold text-white">Price Chart</h2>
          <div class="flex items-center gap-1.5">
            <button
              v-for="p in pricePeriods"
              :key="p.key"
              @click="activePeriod = p.key"
              class="text-xs px-2.5 py-1 rounded transition-colors font-medium"
              :class="activePeriod === p.key
                ? 'bg-emerald-600 text-white'
                : 'text-gray-500 hover:text-gray-300'"
            >{{ p.label }}</button>
          </div>
        </div>

        <div v-if="pricesPending" class="h-48 bg-[#0d1117] rounded-lg animate-pulse" />
        <div v-else-if="!visiblePrices.length" class="h-48 rounded-lg bg-[#0d1117] flex flex-col items-center justify-center gap-2">
          <span class="text-gray-700 text-2xl">📈</span>
          <span class="text-gray-600 text-xs">Price feed warming up — check back shortly</span>
        </div>
        <EChartLine
          v-else
          :option="priceChartOption"
          height="200px"
          :aria-label="`${stock.symbol} price chart — ${priceRangeLabel}`"
        />

        <div v-if="visiblePrices.length" class="flex items-center justify-between mt-2">
          <span class="text-[10px] text-gray-600">{{ priceRangeLabel }}</span>
          <span class="text-[10px] text-gray-600">{{ visiblePrices.length }} candles · 15m interval</span>
        </div>
      </div>

      <!-- News Feed -->
      <div v-if="newsItems?.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-5 mb-6">
        <h2 class="text-base font-bold text-white mb-4">Latest News</h2>
        <div class="space-y-3">
          <a
            v-for="article in newsItems"
            :key="article.id"
            :href="article.url"
            target="_blank"
            rel="noopener noreferrer"
            class="block group"
          >
            <div class="flex items-start gap-3 p-3 rounded-lg hover:bg-[#0d1117] transition-colors">
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-200 group-hover:text-emerald-400 transition-colors leading-snug line-clamp-2">{{ article.title }}</p>
                <div class="flex items-center gap-2 mt-1">
                  <span class="text-[10px] text-gray-600 font-medium">{{ article.source }}</span>
                  <span class="text-[10px] text-gray-700">·</span>
                  <span class="text-[10px] text-gray-600">{{ new Date(article.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</span>
                </div>
              </div>
              <span class="text-gray-700 group-hover:text-emerald-600 transition-colors text-xs shrink-0 mt-0.5">↗</span>
            </div>
          </a>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <!-- Country Context -->
        <div v-if="stock.country" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6">
          <h2 class="text-base font-bold text-white mb-4">HQ Country Context</h2>
          <div class="flex items-center gap-3 mb-4 p-3 rounded-lg bg-[#0d1117] border border-[#1f2937]">
            <span class="text-3xl" aria-hidden="true">{{ stock.country.flag }}</span>
            <div>
              <div class="text-white font-semibold">{{ stock.country.name }}</div>
              <div class="text-xs text-gray-500">Headquarters country</div>
            </div>
            <NuxtLink
              :to="`/countries/${stock.country.code.toLowerCase()}`"
              class="ml-auto text-xs text-emerald-500 hover:text-emerald-400 transition-colors font-semibold"
            >View macro →</NuxtLink>
          </div>
          <div v-if="stock.country.indicators" class="grid grid-cols-2 gap-3">
            <div class="bg-[#0d1117] rounded-lg p-3">
              <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">GDP</div>
              <div class="text-sm font-bold text-white">{{ fmtGdp(stock.country.indicators?.gdp_usd) }}</div>
            </div>
            <div class="bg-[#0d1117] rounded-lg p-3">
              <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">GDP Growth</div>
              <div class="text-sm font-bold" :class="(stock.country.indicators?.gdp_growth_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ stock.country.indicators?.gdp_growth_pct?.toFixed(1) ?? '—' }}%
              </div>
            </div>
            <div class="bg-[#0d1117] rounded-lg p-3">
              <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Inflation</div>
              <div class="text-sm font-bold text-white">{{ stock.country.indicators?.inflation_pct?.toFixed(1) ?? '—' }}%</div>
            </div>
            <div class="bg-[#0d1117] rounded-lg p-3">
              <div class="text-[10px] text-gray-500 uppercase tracking-wider mb-1">Interest Rate</div>
              <div class="text-sm font-bold text-white">{{ stock.country.indicators?.interest_rate_pct?.toFixed(2) ?? '—' }}%</div>
            </div>
          </div>
          <!-- Cross-link: HQ country → top revenue market trade corridor -->
          <div v-if="tradeFlowLinks.length" class="mt-3 pt-3 border-t border-[#1f2937]">
            <p class="text-[10px] text-gray-600 mb-1.5">Key trade corridor for {{ stock.symbol }}</p>
            <NuxtLink
              :to="`/trade/${tradeFlowLinks[0].pair}`"
              class="inline-flex items-center gap-2 text-xs text-emerald-600 hover:text-emerald-400 transition-colors"
            >
              <span aria-hidden="true">{{ stock.country.flag }}</span>
              <span aria-hidden="true">↔</span>
              <span aria-hidden="true">{{ tradeFlowLinks[0].flag }}</span>
              {{ stock.country.name }} – {{ tradeFlowLinks[0].name }} bilateral trade →
            </NuxtLink>
          </div>
        </div>
      </div>

      <!-- Related Trade Flows — internal linking moat -->
      <div v-if="tradeFlowLinks.length" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <h2 class="text-base font-bold text-white mb-1">Trade Flows Impacting {{ stock.symbol }}</h2>
        <p class="text-xs text-gray-500 mb-4">
          Bilateral trade between {{ stock.country?.name }} and {{ stock.symbol }}'s key revenue markets
        </p>
        <div class="flex flex-wrap gap-2">
          <NuxtLink
            v-for="r in tradeFlowLinks"
            :key="r.pair"
            :to="`/trade/${r.pair}`"
            class="flex items-center gap-2 bg-[#0d1117] border border-[#1f2937] hover:border-emerald-700 rounded-lg px-3 py-2 transition-colors group"
          >
            <span class="text-base leading-none" aria-hidden="true">{{ stock.country?.flag }}</span>
            <span class="text-[10px] text-gray-600 font-mono">↔</span>
            <span class="text-base leading-none" aria-hidden="true">{{ r.flag }}</span>
            <div>
              <div class="text-xs font-semibold text-white group-hover:text-emerald-400 transition-colors">
                {{ stock.country?.code }} – {{ r.code }}
              </div>
              <div class="text-[9px] text-gray-600">{{ r.revPct.toFixed(0) }}% revenue</div>
            </div>
            <span class="text-emerald-800 text-xs ml-1 group-hover:text-emerald-500 transition-colors">→</span>
          </NuxtLink>
        </div>
      </div>

      <!-- Comparable Stocks — lower China exposure in same sector -->
      <div v-if="stock.sector && (comparableStocks?.length || comparableLoading)" class="bg-[#111827] border border-[#1f2937] rounded-xl p-6 mb-6">
        <div class="flex items-center justify-between mb-1">
          <h2 class="text-base font-bold text-white">{{ $t('comparableStocks.title') }}</h2>
          <span class="text-xs text-gray-500 bg-[#1f2937] px-2 py-1 rounded">{{ stock.sector }}</span>
        </div>
        <p class="text-xs text-gray-500 mb-4">
          {{ $t('comparableStocks.subtitle', { sector: stock.sector }) }} — similar market cap, less China exposure.
        </p>
        <div v-if="comparableLoading" class="space-y-2">
          <div v-for="i in 3" :key="i" class="h-10 bg-[#1f2937] rounded-lg animate-pulse"/>
        </div>
        <div v-else-if="!comparableStocks?.length" class="text-gray-600 text-xs">{{ $t('comparableStocks.noResults') }}</div>
        <div v-else class="divide-y divide-[#1f2937]">
          <NuxtLink
            v-for="s in comparableStocks"
            :key="s.symbol"
            :to="`/stocks/${s.symbol.toLowerCase()}`"
            class="flex items-center justify-between py-3 hover:bg-[#1f2937] -mx-2 px-2 rounded-lg transition-colors"
          >
            <div class="flex items-center gap-3 min-w-0 flex-1">
              <div class="min-w-0">
                <div class="text-sm font-bold text-emerald-400">{{ s.symbol }}</div>
                <div class="text-xs text-gray-500 truncate max-w-[180px]">{{ s.name }}</div>
              </div>
            </div>
            <div class="flex items-center gap-4 shrink-0">
              <div class="text-right hidden sm:block">
                <div class="text-[10px] text-gray-600">{{ $t('comparableStocks.cn') }}</div>
                <div class="text-xs tabular-nums font-semibold" :class="s.china_pct > 0 ? 'text-red-400' : 'text-gray-600'">{{ s.china_pct }}%</div>
              </div>
              <div class="text-right hidden sm:block">
                <div class="text-[10px] text-gray-600">{{ $t('comparableStocks.us') }}</div>
                <div class="text-xs tabular-nums font-semibold text-blue-400">{{ s.us_pct }}%</div>
              </div>
              <span class="text-sm font-semibold text-white tabular-nums">{{ fmtCap(s.market_cap_usd) }}</span>
            </div>
          </NuxtLink>
        </div>
        <div v-if="comparableStocks?.length" class="mt-4 pt-3 border-t border-[#1f2937]">
          <NuxtLink
            :to="`/screener/?sector=${encodeURIComponent(stock.sector)}&china_max=${Math.max(0, currentChinaPct - 1)}&sort_by=china_pct&sort_dir=asc`"
            class="text-xs text-emerald-600 hover:text-emerald-400 transition-colors"
          >View all low-China {{ stock.sector }} stocks in Screener →</NuxtLink>
        </div>
      </div>

      <p class="text-xs text-gray-700 text-center">Data: SEC EDGAR · World Bank · REST Countries</p>

      <ShareEmbed
        :embed-url="`/embed/stocks/${ticker.toLowerCase()}`"
        :download-url="`${apiBase}/api/assets/${ticker}/prices/download?interval=1d&limit=365`"
      />

      <!-- Newsletter -->
      <div class="mt-8 border border-gray-800 rounded-xl p-6 bg-gray-900/40">
        <p class="text-xs font-mono text-emerald-500 uppercase tracking-widest mb-1">Weekly Briefing</p>
        <p class="text-sm font-semibold text-white mb-1">Market moves + macro context, every week.</p>
        <p class="text-xs text-gray-500 mb-4">Stock exposure, trade flows, economic shifts — free.</p>
        <NewsletterCapture :source="`stock_page_${ticker}`" button-text="Subscribe free" />
      </div>
    </main>
  </div>
  <AuthModal v-model="showAuthModal" />
  <AlertModal
    v-model="showAlertModal"
    :asset="stock ? { id: stock.id, symbol: stock.symbol, name: stock.name } : null"
    :current-price="stock?.price?.close"
  />
  <EmailAlertModal
    v-model="showEmailAlertModal"
    :asset-symbol="stock?.symbol ?? ''"
    :asset-name="stock?.name ?? ''"
    asset-type="stock"
  />
</template>

<script setup lang="ts">
const route = useRoute()
const { get, post, del } = useApi()
const { r2Fetch } = useR2Fetch()
const { isLoggedIn } = useAuth()
const { public: { apiBase } } = useRuntimeConfig()

const ticker = (route.params.ticker as string).toUpperCase()

// Index tickers belong on /indices/[symbol] — redirect immediately
const INDEX_SYMBOLS = new Set(['SPX','NDX','DJI','RUT','VIX','UKX','CAC','DAX','IBEX','SMI','NKY','HSI','SHCOMP','KOSPI','SENSEX','ASX200','MSCIW','MSCIEM'])
if (INDEX_SYMBOLS.has(ticker)) {
  await navigateTo(`/indices/${ticker.toLowerCase()}/`, { redirectCode: 301 })
}

const { data: stock, pending, error } = await useAsyncData(
  `stock-${ticker}`,
  () => r2Fetch<any>(`snapshots/stocks/${ticker.toLowerCase()}.json`, `/api/assets/${ticker}`).catch(() => null),
)
if (!stock.value) throw createError({ statusCode: 404, statusMessage: 'Stock not found' })

// ETFs and crypto have dedicated pages — redirect to canonical asset-type URL
if (stock.value.asset_type === 'etf') {
  await navigateTo(`/etfs/${ticker.toLowerCase()}/`, { redirectCode: 301 })
}
if (stock.value.asset_type === 'crypto') {
  await navigateTo(`/crypto/${ticker.toLowerCase()}/`, { redirectCode: 301 })
}

// entity type depends on asset_type (commodity vs stock)
const summaryEntityType = computed(() =>
  stock.value?.asset_type === 'commodity' ? 'commodity' : 'stock'
)
const insightEntityType = computed(() =>
  stock.value?.asset_type === 'commodity' ? 'commodity_insight' : 'stock_insight'
)

const { data: pageSummary } = useAsyncData(
  `summary-${ticker}`,
  async () => {
    const t = summaryEntityType.value
    return get<any>(`/api/summaries/${t}/${ticker}`).catch(() => null)
  },
  { server: false, watch: [summaryEntityType] },
)

const insightBaseType = computed(() =>
  stock.value?.asset_type === 'commodity' ? 'commodity' : 'stock'
)

const { data: pageInsights } = useAsyncData(
  `insights-${ticker}`,
  async () => {
    const t = insightBaseType.value
    return get<any[]>(`/api/insights/${t}/${ticker}`).catch(() => [])
  },
  { server: false, watch: [insightBaseType] },
)

// ─── News ────────────────────────────────────────────────────────────────────

const { data: newsItems } = useAsyncData(
  `news-${ticker}`,
  () => get<any[]>(`/api/news/${ticker}`).catch(() => []),
  { server: false },
)

// ─── Price chart ──────────────────────────────────────────────────────────────

const pricePeriods = [
  { key: '1D', label: '1D', hours: 8 },
  { key: '3D', label: '3D', hours: 72 },
  { key: 'ALL', label: 'All', hours: 0 },
]
const activePeriod = ref('ALL')

const { data: pricesRaw, pending: pricesPending } = useAsyncData(
  `prices-${ticker}`,
  () => get<any[]>(`/api/assets/${ticker}/prices`, { interval: '15m', limit: 500 }).catch(() => []),
  { server: false },
)

const visiblePrices = computed(() => {
  const all = pricesRaw.value ?? []
  const period = pricePeriods.find(p => p.key === activePeriod.value)
  if (!period || period.hours === 0) return all
  const cutoff = Date.now() - period.hours * 3600 * 1000
  return all.filter((p: any) => new Date(p.t).getTime() >= cutoff)
})

const priceChartOption = computed(() => {
  const data = visiblePrices.value
  if (!data.length) return {}

  const times = data.map((p: any) => {
    const d = new Date(p.t)
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  })
  const closes = data.map((p: any) => p.c)
  const first = closes[0]
  const last = closes[closes.length - 1]
  const isUp = last >= first
  const lineColor = isUp ? '#10b981' : '#f87171'
  const areaColor = isUp ? 'rgba(16,185,129,0.08)' : 'rgba(248,113,113,0.08)'

  return {
    backgroundColor: 'transparent',
    grid: { top: 8, right: 12, bottom: 28, left: 52, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1117',
      borderColor: '#1f2937',
      borderWidth: 1,
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      formatter: (params: any[]) => {
        const p = params[0]
        const raw = data[p.dataIndex]
        const lines = [`<b>${p.name}</b>`]
        lines.push(`Close: <b style="color:${lineColor}">${fmtStockPrice(raw.c, stock.value?.currency)}</b>`)
        if (raw.o != null) lines.push(`Open: ${fmtStockPrice(raw.o, stock.value?.currency)}`)
        if (raw.h != null) lines.push(`High: ${fmtStockPrice(raw.h, stock.value?.currency)} · Low: ${fmtStockPrice(raw.l, stock.value?.currency)}`)
        return lines.join('<br/>')
      },
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLine: { lineStyle: { color: '#1f2937' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#4b5563',
        fontSize: 10,
        interval: Math.max(0, Math.floor(times.length / 6) - 1),
      },
    },
    yAxis: {
      type: 'value',
      scale: true,
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: {
        color: '#4b5563',
        fontSize: 10,
        formatter: (v: number) => fmtStockPrice(v, stock.value?.currency),
      },
    },
    series: [{
      type: 'line',
      data: closes,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: lineColor, width: 2 },
      areaStyle: { color: areaColor },
    }],
  }
})

const priceRangeLabel = computed(() => {
  const data = visiblePrices.value
  if (!data.length) return ''
  const from = new Date(data[0].t)
  const to = new Date(data[data.length - 1].t)
  return `${from.toLocaleDateString()} → ${to.toLocaleDateString()}`
})

// Current China % for this stock (from revenue data)
const currentChinaPct = computed(() => {
  const revs = stock.value?.country_revenues ?? []
  const cnRev = (revs as any[]).find((r: any) => r.country?.code === 'CN')
  return cnRev ? Math.round(cnRev.revenue_pct) : 0
})

const currentMcapB = computed(() => {
  const mcap = stock.value?.market_cap_usd
  return mcap ? mcap / 1e9 : null
})

const { data: comparableData, pending: comparableLoading } = useAsyncData(
  `comparable-${ticker}`,
  async () => {
    if (!stock.value?.sector) return { results: [] }
    const chinaCap = currentChinaPct.value > 0 ? currentChinaPct.value - 1 : 1
    const params: Record<string, any> = {
      sector: stock.value.sector,
      china_max: chinaCap,
      sort_by: 'market_cap',
      limit: 10,
    }
    if (currentMcapB.value) {
      params.market_cap_min = Math.round(currentMcapB.value * 0.5)
      params.market_cap_max = Math.round(currentMcapB.value * 2)
    }
    return $fetch<any>(`${apiBase}/api/screener`, { params })
  },
  { server: false, watch: [() => stock.value?.sector, currentChinaPct] },
)

const comparableStocks = computed(() =>
  (comparableData.value?.results ?? [])
    .filter((s: any) => s.symbol !== ticker)
    .slice(0, 3),
)

// Revenue history for macro risk chart
const { data: revenueHistory } = useAsyncData(
  `rev-history-${ticker}`,
  () => $fetch<any[]>(`${apiBase}/api/screener/revenue-history/${ticker}`).catch(() => []),
  { server: false },
)

// Earnings data for impact estimate
const { data: earningsData } = useAsyncData(
  `earnings-${ticker}`,
  () => $fetch<any[]>(`${apiBase}/api/earnings/stocks/${ticker}`).catch(() => []),
  { server: false },
)

const earningsImpact = computed(() => {
  if (!stock.value?.country_revenues?.length) return null
  const revs = stock.value.country_revenues as any[]
  if (!revs.length) return null
  const topRev = revs[0]
  const latestEps = (earningsData.value ?? []).find((e: any) => e.eps_actual != null)?.eps_actual
  if (latestEps == null) return null
  const impact = (topRev.revenue_pct / 100) * Math.abs(latestEps) * 0.20
  return {
    country: topRev.country?.name ?? 'top market',
    impact: latestEps >= 0 ? -impact : impact,
  }
})

const macroRiskChartOption = computed(() => {
  if (!revenueHistory.value?.length) return {}
  const data = revenueHistory.value
  const years = data.map((d: any) => String(d.year))
  const chinaPcts = data.map((d: any) => d.china_pct)

  return {
    backgroundColor: 'transparent',
    grid: { top: 30, right: 20, bottom: 30, left: 50, containLabel: false },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: years,
      axisLabel: { color: '#4b5563', fontSize: 10 },
      axisLine: { lineStyle: { color: '#1f2937' } },
    },
    yAxis: {
      type: 'value',
      name: 'Revenue %',
      nameTextStyle: { color: '#4b5563', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1a2235', type: 'dashed' } },
      axisLabel: { color: '#4b5563', fontSize: 10, formatter: (v: number) => `${v}%` },
    },
    series: [{
      name: 'China Rev %',
      type: 'line',
      data: chinaPcts,
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { color: '#ef4444', width: 2 },
      itemStyle: { color: '#ef4444' },
      areaStyle: { color: 'rgba(239,68,68,0.1)' },
    }],
  }
})

// Trade flow links — link to bilateral trade pages for top revenue countries
const tradeFlowLinks = computed(() => {
  if (!stock.value?.country || !stock.value.country_revenues?.length) return []
  const hqCode = stock.value.country.code.toLowerCase()
  return (stock.value.country_revenues as any[])
    .filter((r: any) => r.country.code.toLowerCase() !== hqCode)
    .slice(0, 5)
    .map((r: any) => ({
      pair: `${hqCode}-${r.country.code.toLowerCase()}`,
      code: r.country.code,
      flag: r.country.flag,
      name: r.country.name,
      revPct: r.revenue_pct,
    }))
})

const topCountryPct = computed(() => {
  const revs = stock.value?.country_revenues ?? []
  if (!revs.length) return 0
  return Math.max(...revs.map((r: any) => r.revenue_pct))
})

const isSignificantMove = computed(() => {
  const pct = stock.value?.price?.change_pct
  return pct != null && Math.abs(pct) >= 3
})

const geoRisk = computed(() => {
  if (!stock.value?.country_revenues?.length) return null
  const top = topCountryPct.value
  if (top > 40) return 'HIGH'
  if (top > 20) return 'MEDIUM'
  return 'LOW'
})

function fmtStockPrice(v: number | null | undefined, currency?: string): string {
  if (v == null) return '—'
  if (currency === 'GBp') return `${v.toFixed(2)}p`
  if (currency === 'CNY') return `¥${v.toFixed(2)}`
  if (currency === 'NGN') return `₦${v.toFixed(2)}`
  return `$${v.toFixed(2)}`
}

function fmtCap(v: number | null): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

function fmtPriceTs(ts: string | undefined): string {
  if (!ts) return '—'
  const d = new Date(ts)
  if (isNaN(d.getTime())) return '—'
  const hrs = d.getUTCHours(), mins = d.getUTCMinutes()
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
  // Daily candles have no meaningful intraday time — omit 00:00 UTC
  if (hrs === 0 && mins === 0) return date
  return date + ' · ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC'
}

function fmtGdp(v: number | null | undefined): string {
  if (!v) return '—'
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return `$${(v / 1e6).toFixed(0)}M`
}

const showAuthModal = ref(false)
const showAlertModal = ref(false)
const showEmailAlertModal = ref(false)

const isFollowing = ref(false)

onMounted(async () => {
  // Fire-and-forget page view tracking
  const ticker = route.params.ticker as string
  post('/api/track', { entity_type: 'stock', entity_code: ticker.toUpperCase() }).catch(() => {})

  if (!isLoggedIn.value || !stock.value?.id) return
  try {
    const follows = await get<any[]>('/api/feed/follows')
    isFollowing.value = follows.some((f: any) => f.entity_type === 'asset' && f.entity_id === stock.value!.id)
  } catch { /* ignore */ }
})

async function toggleFollow() {
  if (!isLoggedIn.value) { showAuthModal.value = true; return }
  if (!stock.value?.id) return
  try {
    if (isFollowing.value) {
      await del(`/api/feed/follows/asset/${stock.value.id}`)
      isFollowing.value = false
    } else {
      await post('/api/feed/follows', { entity_type: 'asset', entity_id: stock.value.id })
      isFollowing.value = true
    }
  } catch { /* ignore */ }
}

const { public: { r2PublicUrl } } = useRuntimeConfig()
const ogImageUrl = computed(() =>
  r2PublicUrl
    ? `${r2PublicUrl}/og/stocks/${ticker.toLowerCase()}.png`
    : `https://cdn.metricshour.com/og/stocks/${ticker.toLowerCase()}.png`,
)

// ── SEO helpers: inject real revenue data for long-tail keyword ranking ───────
const _topRevs = computed(() => ((stock.value as any)?.country_revenues ?? []).slice(0, 3))

const _seoTitle = computed(() => {
  if (!stock.value) return `${ticker} Stock — MetricsHour`
  const sym  = (stock.value as any).symbol
  const name = (stock.value as any).name
  const revs = _topRevs.value
  if (revs.length >= 2) {
    const top2 = (revs as any[]).slice(0, 2)
      .map((r: any) => `${r.country.name} ${(r.revenue_pct as number).toFixed(0)}%`)
      .join(', ')
    return `${sym} Revenue: ${top2} — MetricsHour`
  }
  if (revs.length === 1) {
    return `${sym} — ${name} | Geographic Revenue — MetricsHour`
  }
  // No geo revenue (e.g. LSE/NGX stocks) — focus on price & exchange
  const exch = (stock.value as any).exchange || ''
  return `${sym} Stock Price${exch ? ` (${exch})` : ''} — ${name} | MetricsHour`
})

const _seoDesc = computed(() => {
  if (!stock.value) return ''
  const s    = stock.value as any
  const sym  = s.symbol
  const name = s.name
  const revs = _topRevs.value as any[]
  const fy   = revs[0]?.fiscal_year ? ` FY${revs[0].fiscal_year}` : ''
  const cap  = s.market_cap_usd
  const capStr = cap
    ? (cap >= 1e12 ? `$${(cap / 1e12).toFixed(1)}T` : `$${(cap / 1e9).toFixed(0)}B`)
    : null
  const parts: string[] = [`${name} (${sym})`]
  if (revs.length) {
    const revStr = revs.slice(0, 3)
      .map((r: any) => `${r.country.name} ${(r.revenue_pct as number).toFixed(0)}%`)
      .join(', ')
    parts.push(`earns ${revStr}`)
    if (capStr) parts.push(`market cap ${capStr}`)
    parts.push(`Geographic revenue from SEC EDGAR${fy}`)
  } else {
    // No geo revenue: describe via exchange, sector, price, currency
    const exch = s.exchange ? `Listed on ${s.exchange}` : ''
    const sector = s.sector ? `${s.sector} sector` : ''
    const currency = s.currency ? `prices in ${s.currency}` : ''
    const hq = s.country?.name ? `headquartered in ${s.country.name}` : ''
    const details = [exch, sector, hq, currency].filter(Boolean).join(', ')
    if (details) parts.push(details)
    if (capStr) parts.push(`market cap ${capStr}`)
    parts.push('Price chart, data and analysis on MetricsHour')
  }
  return parts.join('. ') + '.'
})

// noindex only if the stock record failed to load after fetch completed
const _hasContent = computed(() => {
  if (pending.value) return true // still loading — don't noindex prematurely
  return !!stock.value // any loaded stock has at least name, symbol, sector
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: `https://metricshour.com/stocks/${ticker.toLowerCase()}/`,
  ogType: 'website',
  ogImage: ogImageUrl,
  ogImageWidth: '1200',
  ogImageHeight: '630',
  ogImageType: 'image/png',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  twitterImage: ogImageUrl,
  twitterCard: 'summary_large_image',
  robots: computed(() => _hasContent.value ? 'index, follow' : 'noindex, follow'),
})

function buildStockFaqs(s: any) {
  const faqs: { '@type': string; name: string; acceptedAnswer: { '@type': string; text: string } }[] = []
  const push = (q: string, a: string) => faqs.push({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })

  if (s.market_cap_usd != null) {
    const cap = s.market_cap_usd >= 1e12 ? `$${(s.market_cap_usd / 1e12).toFixed(2)} trillion` : `$${(s.market_cap_usd / 1e9).toFixed(1)} billion`
    push(`What is ${s.symbol}'s market cap?`, `${s.name} (${s.symbol}) has a market capitalisation of approximately ${cap}.`)
  }
  if (s.sector) {
    push(`What sector is ${s.symbol} in?`, `${s.name} (${s.symbol}) operates in the ${s.sector} sector${s.industry ? `, specifically in ${s.industry}` : ''}.`)
  }
  if (s.exchange) {
    push(`What exchange is ${s.symbol} listed on?`, `${s.symbol} is listed on the ${s.exchange}.`)
  }
  const revs: any[] = s.country_revenues ?? []
  if (revs.length) {
    const topRev = revs[0]
    push(`What is ${s.symbol}'s largest international market?`, `${s.name}'s largest market by revenue is ${topRev.country?.name ?? 'N/A'}, accounting for ${topRev.revenue_pct?.toFixed(1)}% of revenue (FY${topRev.fiscal_year}). Source: SEC EDGAR.`)
    const countryList = revs.slice(0, 5).map((r: any) => `${r.country?.name} (${r.revenue_pct?.toFixed(1)}%)`).join(', ')
    push(`What countries does ${s.symbol} earn revenue from?`, `${s.name} earns revenue from ${revs.length} tracked countries including: ${countryList}. Full geographic breakdown available on MetricsHour. Source: SEC EDGAR.`)
  }
  if (s.country?.name) {
    push(`Where is ${s.symbol} headquartered?`, `${s.name} is headquartered in ${s.country.name}.`)
  }
  return faqs
}

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/stocks/${ticker.toLowerCase()}/` }],
  script: stock.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: `${stock.value.symbol} — ${stock.value.name} — MetricsHour`,
        url: `https://metricshour.com/stocks/${ticker.toLowerCase()}/`,
        description: `${stock.value.name} (${stock.value.symbol}) geographic revenue breakdown from SEC EDGAR.`,
        datePublished: '2026-03-01',
        dateModified: stock.value.price?.timestamp ? stock.value.price.timestamp.slice(0, 10) : new Date().toISOString().slice(0, 10),
        mainEntity: { '@type': 'Corporation', name: stock.value.name, tickerSymbol: stock.value.symbol },
        speakable: {
          '@type': 'SpeakableSpecification',
          cssSelector: ['.page-summary', '.page-insight-latest'],
        },
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'Stocks', item: 'https://metricshour.com/stocks/' },
            { '@type': 'ListItem', position: 3, name: stock.value.symbol, item: `https://metricshour.com/stocks/${ticker.toLowerCase()}/` },
          ],
        },
      }),
    },
    ...(buildStockFaqs(stock.value).length ? [{
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: buildStockFaqs(stock.value),
      }),
    }] : []),
    ...((stock.value as any).country_revenues?.length ? [{
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Dataset',
        name: `${(stock.value as any).symbol} Geographic Revenue Breakdown`,
        description: `${(stock.value as any).name} revenue by country from SEC EDGAR 10-K FY${(stock.value as any).country_revenues[0]?.fiscal_year}.`,
        url: `https://metricshour.com/stocks/${ticker.toLowerCase()}/`,
        creator: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com' },
        license: 'https://metricshour.com/terms/',
        keywords: [
          `${(stock.value as any).symbol} geographic revenue`,
          `${(stock.value as any).symbol} revenue by country`,
          `${(stock.value as any).name} international revenue`,
          `${(stock.value as any).symbol} China revenue`,
        ],
        mainEntity: { '@type': 'Corporation', name: (stock.value as any).name, tickerSymbol: (stock.value as any).symbol },
        variableMeasured: ((stock.value as any).country_revenues as any[]).slice(0, 10).map((r: any) => ({
          '@type': 'PropertyValue',
          name: `Revenue from ${r.country?.name}`,
          value: `${(r.revenue_pct as number)?.toFixed(1)}%`,
          description: `${(stock.value as any).symbol} earns ${(r.revenue_pct as number)?.toFixed(1)}% of revenue from ${r.country?.name} (FY${r.fiscal_year})`,
        })),
      }),
    }] : []),
  ] : [],
})))
const expandedInsights = ref<Set<string>>(new Set())
const showAllInsights = ref(false)
const toggleInsight = (key: string) => {
  const s = new Set(expandedInsights.value)
  s.has(key) ? s.delete(key) : s.add(key)
  expandedInsights.value = s
}
</script>
