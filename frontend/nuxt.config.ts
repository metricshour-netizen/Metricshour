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
      r2PublicUrl: process.env.NUXT_PUBLIC_R2_URL || 'https://api.metricshour.com',
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
        { property: 'og:image', content: 'https://api.metricshour.com/og/section/home.png' },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: '@metricshour' },
        { name: 'twitter:image', content: 'https://api.metricshour.com/og/section/home.png' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap' },
      ],
      script: [
        {
          src: 'https://cloud.umami.is/script.js',
          defer: true,
          'data-website-id': '3dfdd2ad-bcbd-408f-9739-e6b058b1ce1c',
          'data-cfasync': 'false',
        },
      ],
    },
  },

  nitro: {
    preset: 'static',
  },
})
