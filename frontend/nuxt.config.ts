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
  },
})
