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
    },
  },

  app: {
    head: {
      title: 'MetricsHour — Global Financial Intelligence',
      meta: [
        { name: 'description', content: 'Stocks, macro, trade flows, and commodities in one place. Understand how global events affect your investments.' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    },
  },

  nitro: {
    preset: 'cloudflare-pages',
  },
})
