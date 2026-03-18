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
      title: 'MetricsHour — Global Financial Intelligence',
      meta: [
        { name: 'description', content: 'Stocks, macro, trade flows, and commodities in one place. Understand how global events affect your investments.' },
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

  routeRules: {
    '/sitemap.xml': { redirect: { to: 'https://api.metricshour.com/sitemap.xml', statusCode: 301 } },
    '/robots.txt': { redirect: { to: 'https://api.metricshour.com/robots.txt', statusCode: 301 } },

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
    '/pricing': { headers: { 'Cache-Control': 'public, s-maxage=3600, max-age=300, stale-while-revalidate=86400' } },
    '/about': { headers: { 'Cache-Control': 'public, s-maxage=86400, max-age=3600' } },
    '/privacy': { headers: { 'Cache-Control': 'public, s-maxage=86400, max-age=3600' } },
    '/terms': { headers: { 'Cache-Control': 'public, s-maxage=86400, max-age=3600' } },
    // Dynamic entity pages — 30 min edge cache, stale up to 24h
    '/countries/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/stocks/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/trade/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/commodities/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
    '/indices/**': { headers: { 'Cache-Control': 'public, s-maxage=1800, max-age=300, stale-while-revalidate=86400' } },
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
  },
})
