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
      r2PublicUrl: process.env.NUXT_PUBLIC_R2_URL || '',
    },
  },

  app: {
    head: {
      title: 'MetricsHour — Global Financial Intelligence',
      meta: [
        { name: 'description', content: 'Stocks, macro, trade flows, and commodities in one place. Understand how global events affect your investments.' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { property: 'og:site_name', content: 'MetricsHour' },
        { property: 'og:image', content: 'https://metricshour.com/og-image.png' },
        { property: 'og:image:width', content: '1200' },
        { property: 'og:image:height', content: '630' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:site', content: '@metricshour' },
        { name: 'twitter:image', content: 'https://metricshour.com/og-image.png' },
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    },
  },

  nitro: {
    preset: 'static',
  },
})
