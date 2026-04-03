<template>
  <div>
    <!-- Hero -->
    <div class="bg-gradient-to-b from-[#0d1520] to-[#0a0e1a] border-b border-[#1f2937]">
      <div class="max-w-7xl mx-auto px-4 py-8">
        <NuxtLink to="/blocs/" class="text-gray-600 text-xs hover:text-gray-400 transition-colors mb-5 inline-flex items-center gap-1">
          ← Blocs
        </NuxtLink>

        <div v-if="pending" class="space-y-2">
          <div class="h-8 w-48 bg-[#1f2937] rounded animate-pulse"/>
          <div class="h-4 w-80 bg-[#1f2937] rounded animate-pulse"/>
        </div>
        <div v-else-if="error || !bloc" class="text-red-400 text-sm py-6">Bloc not found.</div>

        <template v-else>
          <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
            <div class="flex items-start gap-4">
              <span class="text-5xl leading-none shrink-0">{{ bloc.emoji }}</span>
              <div>
                <h1 class="text-3xl font-extrabold text-white tracking-tight mb-1">{{ bloc.full_name }}</h1>
                <p class="text-gray-400 text-sm max-w-2xl leading-relaxed">{{ bloc.description }}</p>
                <div class="flex flex-wrap gap-4 mt-3 text-xs text-gray-600">
                  <span>Est. {{ bloc.founded }}</span>
                  <span>·</span>
                  <span>{{ bloc.hq }}</span>
                  <span>·</span>
                  <a :href="bloc.website" target="_blank" rel="noopener noreferrer" class="hover:text-gray-400 underline transition-colors">Official site ↗</a>
                </div>
              </div>
            </div>
            <!-- Key stats -->
            <div class="grid grid-cols-2 sm:grid-cols-1 gap-3 shrink-0 text-right min-w-[140px]">
              <div>
                <div class="text-2xl font-extrabold text-white tabular-nums">{{ fmtGdp(bloc.stats.total_gdp_usd) }}</div>
                <div class="text-xs text-gray-600">combined GDP</div>
              </div>
              <div>
                <div class="text-2xl font-extrabold tabular-nums" :class="growthColor(bloc.stats.avg_gdp_growth_pct)">
                  {{ fmtPct(bloc.stats.avg_gdp_growth_pct) }}
                </div>
                <div class="text-xs text-gray-600">avg GDP growth</div>
              </div>
              <div>
                <div class="text-xl font-bold text-white tabular-nums">{{ bloc.member_count }}</div>
                <div class="text-xs text-gray-600">member states</div>
              </div>
              <div v-if="bloc.stats.avg_inflation_pct != null">
                <div class="text-xl font-bold text-amber-400 tabular-nums">{{ fmtPct(bloc.stats.avg_inflation_pct) }}</div>
                <div class="text-xs text-gray-600">avg inflation</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <main v-if="bloc" class="max-w-7xl mx-auto px-4 py-8">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">

        <!-- Left: members table -->
        <div class="lg:col-span-2 space-y-8">
          <section>
            <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Member States ({{ bloc.member_count }})</h2>
            <div class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-[#1f2937] text-gray-500 text-xs">
                    <th class="text-left px-4 py-3 font-medium">Country</th>
                    <th class="text-right px-4 py-3 font-medium">GDP</th>
                    <th class="text-right px-4 py-3 font-medium hidden sm:table-cell">Growth</th>
                    <th class="text-right px-4 py-3 font-medium hidden md:table-cell">Inflation</th>
                    <th class="text-right px-4 py-3 font-medium hidden lg:table-cell">Rating (S&P)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="m in bloc.members"
                    :key="m.code"
                    class="border-b border-[#1f2937] last:border-0 hover:bg-[#1a2332] transition-colors cursor-pointer"
                    @click="navigateTo(`/countries/${m.code.toLowerCase()}/`)"
                  >
                    <td class="px-4 py-3">
                      <NuxtLink :to="`/countries/${m.code.toLowerCase()}/`" class="flex items-center gap-2 hover:text-emerald-400 transition-colors">
                        <span class="text-lg">{{ m.flag }}</span>
                        <span class="text-white font-medium">{{ m.name }}</span>
                      </NuxtLink>
                    </td>
                    <td class="px-4 py-3 text-right text-white tabular-nums font-mono text-xs">
                      {{ fmtGdp(m.gdp_usd) ?? '—' }}
                    </td>
                    <td class="px-4 py-3 text-right tabular-nums text-xs hidden sm:table-cell" :class="growthColor(m.gdp_growth_pct)">
                      {{ m.gdp_growth_pct != null ? `${m.gdp_growth_pct >= 0 ? '+' : ''}${m.gdp_growth_pct.toFixed(1)}%` : '—' }}
                    </td>
                    <td class="px-4 py-3 text-right tabular-nums text-xs text-amber-400 hidden md:table-cell">
                      {{ m.inflation_pct != null ? `${m.inflation_pct.toFixed(1)}%` : '—' }}
                    </td>
                    <td class="px-4 py-3 text-right text-xs hidden lg:table-cell">
                      <span :class="ratingColor(m.credit_rating_sp)" class="font-mono font-semibold">
                        {{ m.credit_rating_sp ?? '—' }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- FAQ section (SEO) -->
          <section class="space-y-3">
            <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider">Frequently Asked Questions</h2>
            <div v-for="faq in faqs" :key="faq.q" class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
              <div class="text-white font-medium text-sm mb-1">{{ faq.q }}</div>
              <div class="text-gray-400 text-xs leading-relaxed">{{ faq.a }}</div>
            </div>
          </section>
        </div>

        <!-- Right: exposed stocks -->
        <div class="space-y-6">
          <section v-if="bloc.exposed_stocks?.length">
            <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Most Exposed Stocks</h2>
            <div class="bg-[#111827] border border-[#1f2937] rounded-xl overflow-hidden">
              <div
                v-for="s in bloc.exposed_stocks.slice(0, 15)"
                :key="s.symbol"
                class="border-b border-[#1f2937] last:border-0 px-4 py-3 hover:bg-[#1a2332] transition-colors cursor-pointer"
                @click="navigateTo(`/stocks/${s.symbol}/`)"
              >
                <div class="flex items-center justify-between gap-2">
                  <div class="min-w-0">
                    <NuxtLink :to="`/stocks/${s.symbol}/`" class="text-emerald-400 font-mono text-xs font-bold hover:text-emerald-300 transition-colors">
                      {{ s.symbol }}
                    </NuxtLink>
                    <div class="text-gray-400 text-xs truncate">{{ s.name }}</div>
                    <div v-if="s.top_country" class="text-gray-600 text-xs">
                      {{ s.top_country.flag }} {{ s.top_country.name }} {{ s.top_country_pct.toFixed(0) }}%
                    </div>
                  </div>
                  <div class="text-right shrink-0">
                    <div class="text-white font-bold text-sm tabular-nums">{{ s.total_exposure_pct.toFixed(0) }}%</div>
                    <div class="text-gray-600 text-xs">exposure</div>
                  </div>
                </div>
              </div>
            </div>
            <p class="text-gray-700 text-xs mt-2 leading-relaxed">
              Revenue exposure across {{ bloc.member_count }} {{ bloc.name }} member states. Source: SEC EDGAR 10-K/10-Q filings.
            </p>
          </section>

          <!-- Data sources -->
          <section class="bg-[#111827] border border-[#1f2937] rounded-xl p-4">
            <div class="text-xs text-gray-500 font-semibold uppercase tracking-wider mb-3">Data Sources</div>
            <div class="space-y-1 text-xs text-gray-600">
              <div>GDP & Indicators: <span class="text-gray-400">World Bank / IMF</span></div>
              <div>Credit Ratings: <span class="text-gray-400">S&P, Moody's</span></div>
              <div>Stock Exposure: <span class="text-gray-400">SEC EDGAR 10-K/10-Q</span></div>
              <div>Membership: <span class="text-gray-400">Official bloc rosters</span></div>
            </div>
          </section>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const slug = (route.params.slug as string).toLowerCase()

const { public: { apiBase } } = useRuntimeConfig()

const { data: bloc, pending, error } = await useFetch(`/api/blocs/${slug}`, {
  baseURL: apiBase,
  key: `bloc-${slug}`,
})

// ── Formatters ────────────────────────────────────────────────────────────────
function fmtGdp(v: number | null | undefined): string | null {
  if (v == null) return null
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (v >= 1e9)  return `$${(v / 1e9).toFixed(0)}B`
  return null
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

function growthColor(v: number | null | undefined): string {
  if (v == null) return 'text-gray-500'
  return v >= 0 ? 'text-emerald-400' : 'text-red-400'
}

function ratingColor(r: string | null | undefined): string {
  if (!r) return 'text-gray-600'
  if (r.startsWith('AA')) return 'text-emerald-400'
  if (r.startsWith('A'))  return 'text-green-400'
  if (r.startsWith('BB')) return 'text-yellow-400'
  return 'text-red-400'
}

// ── FAQs (SEO / schema) ───────────────────────────────────────────────────────
const faqs = computed(() => {
  if (!bloc.value) return []
  const b = bloc.value as any
  const s = b.stats
  const list: { q: string; a: string }[] = []

  if (s.total_gdp_usd) {
    const gdp = fmtGdp(s.total_gdp_usd)
    list.push({
      q: `What is the combined GDP of ${b.full_name} members?`,
      a: `The combined GDP of all ${b.member_count} ${b.full_name} member states is approximately ${gdp}. This is calculated by summing the most recent World Bank GDP figures for each member country.`,
    })
  }
  if (s.avg_gdp_growth_pct != null) {
    list.push({
      q: `What is the average GDP growth rate of ${b.name} countries?`,
      a: `The GDP-weighted average growth rate across ${b.name} members is ${fmtPct(s.avg_gdp_growth_pct)}. This figure is weighted by each member's GDP to reflect economic size.`,
    })
  }
  if (s.avg_inflation_pct != null) {
    list.push({
      q: `What is the average inflation rate in ${b.name} countries?`,
      a: `The average inflation rate across ${b.name} member states is ${fmtPct(s.avg_inflation_pct)} (simple average of latest annual CPI data from World Bank/IMF).`,
    })
  }
  list.push({
    q: `How many countries are in ${b.full_name}?`,
    a: `${b.full_name} has ${b.member_count} member states. ${b.name} was founded in ${b.founded} and is headquartered in ${b.hq}.`,
  })
  if (b.exposed_stocks?.length) {
    const top3 = b.exposed_stocks.slice(0, 3).map((s: any) => `${s.name} (${s.symbol}, ${s.total_exposure_pct.toFixed(0)}% exposure)`).join(', ')
    list.push({
      q: `Which stocks are most exposed to ${b.name} economies?`,
      a: `The stocks with the highest revenue exposure to ${b.name} member countries are: ${top3}. Exposure is measured as a percentage of annual revenue derived from member states, based on SEC EDGAR 10-K geographic revenue disclosures.`,
    })
  }
  return list
})

// ── SEO ───────────────────────────────────────────────────────────────────────
const _seoTitle = computed(() => {
  if (!bloc.value) return 'Economic Bloc — MetricsHour'
  const b = bloc.value as any
  const gdp = fmtGdp(b.stats.total_gdp_usd)
  if (gdp) return `${b.full_name}: GDP ${gdp}, ${b.member_count} Members & Key Indicators — MetricsHour`
  return `${b.full_name}: Economy, Trade & Macro Data — MetricsHour`
})

const _seoDesc = computed(() => {
  if (!bloc.value) return ''
  const b = bloc.value as any
  const s = b.stats
  const parts: string[] = []
  const gdp = fmtGdp(s.total_gdp_usd)
  if (gdp) parts.push(`Combined GDP ${gdp}`)
  if (s.avg_gdp_growth_pct != null) parts.push(`avg growth ${fmtPct(s.avg_gdp_growth_pct)}`)
  if (s.avg_inflation_pct != null) parts.push(`avg inflation ${fmtPct(s.avg_inflation_pct)}`)
  parts.push(`${b.member_count} member states`)
  return `${b.full_name} economic data: ${parts.join(', ')}. GDP, growth, inflation, and top exposed stocks. Data from World Bank, IMF, and SEC EDGAR.`
})

useSeoMeta({
  title: _seoTitle,
  description: _seoDesc,
  ogTitle: _seoTitle,
  ogDescription: _seoDesc,
  ogUrl: computed(() => `https://metricshour.com/blocs/${slug}/`),
  ogType: 'website',
  twitterCard: 'summary_large_image',
  twitterTitle: _seoTitle,
  twitterDescription: _seoDesc,
  robots: computed(() => (!bloc.value && !pending.value) ? 'noindex, follow' : 'index, follow, max-snippet:-1, max-image-preview:large'),
})

useHead(computed(() => ({
  link: [{ rel: 'canonical', href: `https://metricshour.com/blocs/${slug}/` }],
  script: bloc.value ? [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        name: (bloc.value as any).full_name + ' Economy & Macro Data — MetricsHour',
        url: `https://metricshour.com/blocs/${slug}/`,
        description: _seoDesc.value,
        dateModified: new Date().toISOString().slice(0, 10),
        breadcrumb: {
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: 'https://metricshour.com' },
            { '@type': 'ListItem', position: 2, name: 'Blocs', item: 'https://metricshour.com/blocs/' },
            { '@type': 'ListItem', position: 3, name: (bloc.value as any).name, item: `https://metricshour.com/blocs/${slug}/` },
          ],
        },
      }),
    },
    ...(faqs.value.length ? [{
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: faqs.value.map(f => ({
          '@type': 'Question',
          name: f.q,
          acceptedAnswer: { '@type': 'Answer', text: f.a },
        })),
      }),
    }] : []),
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify((() => {
        const b = bloc.value as any
        const s = b.stats
        const measured: any[] = []
        if (s.total_gdp_usd)         measured.push({ '@type': 'PropertyValue', name: 'Combined GDP (USD)', value: String(s.total_gdp_usd), unitCode: 'USD' })
        if (s.avg_gdp_growth_pct != null) measured.push({ '@type': 'PropertyValue', name: 'Avg GDP Growth Rate', value: `${s.avg_gdp_growth_pct}%` })
        if (s.avg_inflation_pct != null)  measured.push({ '@type': 'PropertyValue', name: 'Avg Inflation Rate', value: `${s.avg_inflation_pct}%` })
        return {
          '@context': 'https://schema.org',
          '@type': 'Dataset',
          name: `${b.full_name} Economic Indicators`,
          description: `Aggregate GDP, growth, inflation, and macro data for ${b.member_count} ${b.full_name} member states. Source: World Bank, IMF.`,
          url: `https://metricshour.com/blocs/${slug}/`,
          creator: { '@type': 'Organization', name: 'MetricsHour', url: 'https://metricshour.com' },
          license: 'https://metricshour.com/terms/',
          keywords: (b.keywords ?? []).concat([`${b.name} member states`, `${b.name} economy`]),
          temporalCoverage: '2015/..',
          variableMeasured: measured,
        }
      })()),
    },
  ] : [],
})))
</script>
