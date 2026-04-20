export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',

  css: ['~/assets/css/main.css'],

  postcss: {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  },

  runtimeConfig: {
    // Private — server-side only. Bypasses Cloudflare to prevent JSON body transformation.
    apiBaseServer: process.env.NUXT_API_BASE_SERVER || 'http://127.0.0.1:8000',
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'https://api.metricshour.com',
      // R2 CDN base URL — cdn.metricshour.com is a Cloudflare R2 custom domain.
      // Snapshots are served direct from R2 edge (~10ms), no API hop needed.
      // The /snapshots/ API proxy remains as fallback if R2 is unreachable.
      r2PublicUrl: process.env.NUXT_PUBLIC_R2_URL || 'https://cdn.metricshour.com',
      telegramBotUsername: process.env.NUXT_PUBLIC_TELEGRAM_BOT_USERNAME || 'MetricshourBot',
    },
  },

  app: {
    head: {
      htmlAttrs: { lang: 'en' },
      charset: 'utf-8',
      title: 'MetricsHour — See Where Your Stocks Make Money From',
      meta: [
        { name: 'description', content: 'Country revenue breakdowns for 775+ stocks, from SEC filings. Plus bilateral trade flows, macro data, yield curve, and earnings — all free.' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'robots', content: 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1' },
        { property: 'og:site_name', content: 'MetricsHour' },
        { property: 'og:locale', content: 'en_US' },
        { property: 'og:image', content: 'https://cdn.metricshour.com/og/section/home.png' },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: '@metricshour' },
        { name: 'twitter:image', content: 'https://cdn.metricshour.com/og/section/home.png' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'alternate', type: 'application/rss+xml', title: 'MetricsHour Blog', href: 'https://api.metricshour.com/rss.xml' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap' },
      ],
      script: [
        {
          src: 'https://analytics.metricshour.com/script.js',
          defer: true,
          'data-website-id': '89f67ce6-dc4e-46e2-aebe-2673b2d360a7',
          'data-cfasync': 'false',
        },
      ],
    },
  },

  nitro: {
    preset: 'node-server',
  },

  // Security headers applied globally via routeRules catch-all
  // Cloudflare strips these on the edge — they arrive from Nuxt for direct-access coverage
  routeRules: {
    '/**': {
      headers: {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
      },
    },
    '/sitemap.xml': { redirect: { to: 'https://api.metricshour.com/sitemap.xml', statusCode: 301 } },

    // Edge cache headers — Cloudflare respects s-maxage; client gets max-age
    // Share preview pages (social crawlers) — 5 min edge cache, stale ok for up to 1h
    '/s/**': { headers: { 'Cache-Control': 'public, s-maxage=300, max-age=60, stale-while-revalidate=3600' } },
    // Homepage — 1h edge cache
    '/': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    // Listing/index pages — 1h edge cache
    '/countries': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/stocks': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/trade': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/commodities': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/indices': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/blog': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/compare': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/crypto': { headers: { 'Cache-Control': 'public, s-maxage=120, max-age=60, stale-while-revalidate=3600' } },
    '/etfs': { headers: { 'Cache-Control': 'public, s-maxage=900, max-age=300, stale-while-revalidate=86400' } },
    '/fx': { headers: { 'Cache-Control': 'public, s-maxage=900, max-age=300, stale-while-revalidate=86400' } },
    '/pricing': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/about': { headers: { 'Cache-Control': 'public, s-maxage=86400, max-age=3600' } },
    '/privacy': { headers: { 'Cache-Control': 'public, s-maxage=86400, max-age=3600' } },
    '/terms': { headers: { 'Cache-Control': 'public, s-maxage=86400, max-age=3600' } },
    // Dynamic entity pages — 30 min edge cache, stale up to 24h
    '/countries/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/stocks/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    // Top 50 trade corridors — 8h edge cache (data is annual, safe to cache aggressively)
    '/trade/united-states--china/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/united-states--germany/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/united-states--japan/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/united-states--mexico/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/united-states--canada/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/china--united-states/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/china--germany/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/china--japan/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/china--south-korea/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/germany--france/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/germany--united-states/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/germany--china/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/japan--china/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/japan--united-states/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/india--united-states/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/india--china/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/united-kingdom--united-states/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/united-kingdom--germany/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/france--germany/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    '/trade/south-korea--china/': { headers: { 'Cache-Control': 'public, s-maxage=28800, max-age=3600, stale-while-revalidate=604800' } },
    // All other trade pages — 4h edge cache (was 30m)
    '/trade/**': { headers: { 'Cache-Control': 'public, s-maxage=14400, max-age=3600, stale-while-revalidate=604800' } },
    '/commodities/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/indices/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    // Crypto detail pages — 2 min edge cache (prices update every minute)
    '/crypto/**': { headers: { 'Cache-Control': 'public, s-maxage=120, max-age=60, stale-while-revalidate=3600' } },
    // ETF + FX detail pages — 30 min edge cache
    '/etfs/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/fx/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    // China A-shares + rates — 30 min edge cache (daily close data)
    '/china/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/rates/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/blog/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/compare/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    // Markets + Feed — 5 min (data changes frequently)
    '/markets': { headers: { 'Cache-Control': 'public, s-maxage=300, max-age=60, stale-while-revalidate=3600' } },
    '/feed': { headers: { 'Cache-Control': 'public, s-maxage=300, max-age=60, stale-while-revalidate=3600' } },
    '/feed/**': { headers: { 'Cache-Control': 'public, s-maxage=300, max-age=60, stale-while-revalidate=3600' } },

    '/register/': { redirect: { to: '/join', statusCode: 301 } },
    '/register': { redirect: { to: '/join', statusCode: 301 } },
    '/signup/': { redirect: { to: '/join', statusCode: 301 } },
    '/signup': { redirect: { to: '/join', statusCode: 301 } },
    // Common commodity name aliases → canonical ticker URLs
    '/commodities/gold/': { redirect: { to: '/commodities/xauusd/', statusCode: 301 } },
    '/commodities/gold': { redirect: { to: '/commodities/xauusd/', statusCode: 301 } },
    '/commodities/silver/': { redirect: { to: '/commodities/xagusd/', statusCode: 301 } },
    '/commodities/silver': { redirect: { to: '/commodities/xagusd/', statusCode: 301 } },
    '/commodities/platinum/': { redirect: { to: '/commodities/xptusd/', statusCode: 301 } },
    '/commodities/platinum': { redirect: { to: '/commodities/xptusd/', statusCode: 301 } },
    '/commodities/oil/': { redirect: { to: '/commodities/wti/', statusCode: 301 } },
    '/commodities/oil': { redirect: { to: '/commodities/wti/', statusCode: 301 } },
    '/commodities/crude-oil/': { redirect: { to: '/commodities/wti/', statusCode: 301 } },
    '/commodities/crude-oil': { redirect: { to: '/commodities/wti/', statusCode: 301 } },
    '/commodities/natural-gas/': { redirect: { to: '/commodities/ng/', statusCode: 301 } },
    '/commodities/natural-gas': { redirect: { to: '/commodities/ng/', statusCode: 301 } },
    '/commodities/wheat/': { redirect: { to: '/commodities/zw/', statusCode: 301 } },
    '/commodities/wheat': { redirect: { to: '/commodities/zw/', statusCode: 301 } },
    '/commodities/corn/': { redirect: { to: '/commodities/zc/', statusCode: 301 } },
    '/commodities/corn': { redirect: { to: '/commodities/zc/', statusCode: 301 } },
    '/commodities/copper/': { redirect: { to: '/commodities/hg/', statusCode: 301 } },
    '/commodities/copper': { redirect: { to: '/commodities/hg/', statusCode: 301 } },
    '/commodities/coffee/': { redirect: { to: '/commodities/kc/', statusCode: 301 } },
    '/commodities/coffee': { redirect: { to: '/commodities/kc/', statusCode: 301 } },
    // Blog slug cleanup — old numeric-suffix URLs → canonical slugs
    '/blog/chinas-18-billion-trade-grip-on-nigeria-the-hidden-dependency-that-shapes-africas-largest-economy-3/': { redirect: { to: '/blog/chinas-18-billion-trade-grip-on-nigeria-the-hidden-dependency-that-shapes-africas-largest-economy/', statusCode: 301 } },
    '/blog/chinas-18-billion-trade-grip-on-nigeria-the-hidden-dependency-that-shapes-africas-largest-economy-3': { redirect: { to: '/blog/chinas-18-billion-trade-grip-on-nigeria-the-hidden-dependency-that-shapes-africas-largest-economy/', statusCode: 301 } },
    '/blog/nigeria-oil-exports-the-us-stocks-at-risk-from-africa-petro-giant-1/': { redirect: { to: '/blog/nigeria-oil-exports-the-us-stocks-at-risk-from-africa-petro-giant/', statusCode: 301 } },
    '/blog/nigeria-oil-exports-the-us-stocks-at-risk-from-africa-petro-giant-1': { redirect: { to: '/blog/nigeria-oil-exports-the-us-stocks-at-risk-from-africa-petro-giant/', statusCode: 301 } },
    // Nigerian stock tickers — redirect old /stocks/ paths to dedicated Nigeria pages
    '/stocks/seplat/': { redirect: { to: '/nigeria/sepl.l/', statusCode: 301 } },
    '/stocks/seplat': { redirect: { to: '/nigeria/sepl.l/', statusCode: 301 } },
    '/stocks/SEPLAT/': { redirect: { to: '/nigeria/sepl.l/', statusCode: 301 } },
    '/stocks/SEPLAT': { redirect: { to: '/nigeria/sepl.l/', statusCode: 301 } },
    '/stocks/aaf.l/': { redirect: { to: '/nigeria/aaf.l/', statusCode: 301 } },
    '/stocks/aaf.l': { redirect: { to: '/nigeria/aaf.l/', statusCode: 301 } },
    '/stocks/dangcem/': { redirect: { to: '/nigeria/dangcem/', statusCode: 301 } },
    '/stocks/dangcem': { redirect: { to: '/nigeria/dangcem/', statusCode: 301 } },
    '/stocks/mtnn/': { redirect: { to: '/nigeria/mtnn/', statusCode: 301 } },
    '/stocks/mtnn': { redirect: { to: '/nigeria/mtnn/', statusCode: 301 } },
    '/stocks/zenithbank/': { redirect: { to: '/nigeria/zenithbank/', statusCode: 301 } },
    '/stocks/zenithbank': { redirect: { to: '/nigeria/zenithbank/', statusCode: 301 } },
    '/stocks/gtco/': { redirect: { to: '/nigeria/gtco/', statusCode: 301 } },
    '/stocks/gtco': { redirect: { to: '/nigeria/gtco/', statusCode: 301 } },
    '/stocks/accesscorp/': { redirect: { to: '/nigeria/accesscorp/', statusCode: 301 } },
    '/stocks/accesscorp': { redirect: { to: '/nigeria/accesscorp/', statusCode: 301 } },
    // Keyword cannibalization — duplicate posts consolidated
    '/blog/teslas-213-billion-china-revenue-the-gigafactory-bet-every-tsla-investor-should-understand/': { redirect: { to: '/blog/tesla-china-revenue-percentage-2026/', statusCode: 301 } },
    '/blog/teslas-213-billion-china-revenue-the-gigafactory-bet-every-tsla-investor-should-understand': { redirect: { to: '/blog/tesla-china-revenue-percentage-2026/', statusCode: 301 } },
    '/blog/nvidia-china-revenue-percentage-fy2024-export-controls-tariff-risk-nvda-investors/': { redirect: { to: '/blog/nvidia-china-revenue-chip-export-controls-nvda/', statusCode: 301 } },
    '/blog/nvidia-china-revenue-percentage-fy2024-export-controls-tariff-risk-nvda-investors': { redirect: { to: '/blog/nvidia-china-revenue-chip-export-controls-nvda/', statusCode: 301 } },
  },
})
