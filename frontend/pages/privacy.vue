<template>
  <main class="max-w-3xl mx-auto px-4 py-12">
    <NuxtLink to="/" class="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-8 inline-block">← Home</NuxtLink>

    <h1 class="text-2xl font-bold text-white mb-2">Privacy Policy</h1>
    <p class="text-xs text-gray-600 mb-8">Last updated: February 2026</p>

    <div class="space-y-8 text-sm text-gray-400 leading-relaxed">

      <section>
        <h2 class="text-base font-semibold text-white mb-3">1. Who We Are</h2>
        <p>MetricsHour ("we", "us", "our") operates metricshour.com, a financial data intelligence platform providing macro-economic data, stock market information, bilateral trade flows, and related content. We are committed to protecting the personal information of our users.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">2. Information We Collect</h2>
        <p class="mb-2"><span class="text-gray-300 font-medium">Account information:</span> When you register, we collect your email address and a hashed password. We never store plaintext passwords.</p>
        <p class="mb-2"><span class="text-gray-300 font-medium">Usage data:</span> We may collect anonymised page view data, referrer URLs, and browser/device type to understand how the platform is used and improve it.</p>
        <p class="mb-2"><span class="text-gray-300 font-medium">Communications:</span> If you contact us by email or the feedback form, we retain that correspondence to respond to your enquiry.</p>
        <p><span class="text-gray-300 font-medium">We do not collect:</span> payment card details (handled entirely by our payment processor), precise location data, or any biometric data.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">3. How We Use Your Information</h2>
        <ul class="list-disc list-inside space-y-1.5">
          <li>To create and manage your MetricsHour account</li>
          <li>To provide access to features appropriate to your subscription tier</li>
          <li>To send transactional emails (password reset, account notices) — not marketing unless you opt in</li>
          <li>To improve the platform based on aggregated, anonymised usage patterns</li>
          <li>To comply with applicable laws and regulations</li>
        </ul>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">4. Data Sharing</h2>
        <p class="mb-2">We do <span class="text-white font-medium">not</span> sell, rent, or trade your personal data to third parties.</p>
        <p>We use trusted infrastructure and service providers who may process data on our behalf:</p>
        <ul class="list-disc list-inside space-y-1.5 mt-2">
          <li><span class="text-gray-300">CDN &amp; network security</span> — content delivery and DDoS protection</li>
          <li><span class="text-gray-300">Cloud database hosting</span> — encrypted storage in data centres with SOC 2 compliance</li>
          <li><span class="text-gray-300">Caching infrastructure</span> — serverless cache for performance and job queues</li>
        </ul>
        <p class="mt-2">Each provider is contractually bound to protect your data and may not use it for their own purposes.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">5. Cookies & Local Storage</h2>
        <p class="mb-2">We use browser local storage (not third-party cookies) for:</p>
        <ul class="list-disc list-inside space-y-1.5">
          <li>Keeping you logged in (JWT token stored locally)</li>
          <li>Remembering UI preferences such as dark/light mode and terminal view toggle</li>
        </ul>
        <p class="mt-2">We do not use advertising cookies or third-party tracking cookies.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">6. Data Retention</h2>
        <p>Account data is retained for as long as your account is active. If you delete your account, your personal information is deleted within 30 days, except where retention is required by law.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">7. Your Rights</h2>
        <p class="mb-2">Depending on your jurisdiction you may have the right to:</p>
        <ul class="list-disc list-inside space-y-1.5">
          <li>Access the personal data we hold about you</li>
          <li>Correct inaccurate data</li>
          <li>Request deletion of your account and associated data</li>
          <li>Object to or restrict certain processing</li>
          <li>Data portability (receive your data in a machine-readable format)</li>
        </ul>
        <p class="mt-2">To exercise any of these rights, email us at <a href="mailto:hello@metricshour.com" class="text-emerald-500 hover:text-emerald-400">hello@metricshour.com</a>. We will respond within 30 days.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">8. Security</h2>
        <p>All data is transmitted over HTTPS/TLS. Passwords are hashed using Argon2id before storage. We conduct periodic security reviews and apply security patches promptly. No method of transmission over the internet is 100% secure; we cannot guarantee absolute security.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">9. Children</h2>
        <p>MetricsHour is not directed at children under 16. We do not knowingly collect data from anyone under 16. If you believe a child has provided us with personal information, please contact us and we will delete it.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">10. Changes to This Policy</h2>
        <p>We may update this policy periodically. We will notify registered users of material changes by email. Continued use of the platform after changes constitutes acceptance of the updated policy.</p>
      </section>

      <section>
        <h2 class="text-base font-semibold text-white mb-3">11. Contact</h2>
        <p>For any privacy-related questions or requests: <a href="mailto:hello@metricshour.com" class="text-emerald-500 hover:text-emerald-400">hello@metricshour.com</a></p>
      </section>

    </div>

    <div class="mt-10 pt-6 border-t border-[#1f2937] flex gap-6 text-xs text-gray-600">
      <NuxtLink to="/terms" class="hover:text-gray-400 transition-colors">Terms of Service</NuxtLink>
      <NuxtLink to="/" class="hover:text-gray-400 transition-colors">← Back to MetricsHour</NuxtLink>
    </div>
  </main>
</template>

<script setup lang="ts">
useSeoMeta({
  title: 'Privacy Policy — MetricsHour',
  description: 'How MetricsHour collects, uses, and protects your personal data.',
  ogDescription: 'How MetricsHour collects, uses, and protects your personal data.',
  ogTitle: 'Privacy Policy — MetricsHour',
  ogUrl: 'https://metricshour.com/privacy/',
  ogImage: 'https://cdn.metricshour.com/og/section/home.png',
  ogImageWidth: '1200',
  ogImageHeight: '630',
  twitterImage: 'https://cdn.metricshour.com/og/section/home.png',
  twitterCard: 'summary_large_image',
})
useHead({
  link: [{ rel: 'canonical', href: 'https://metricshour.com/privacy/' }],
  script: [{
    type: 'application/ld+json',
    innerHTML: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'Privacy Policy — MetricsHour',
      url: 'https://metricshour.com/privacy/',
      isPartOf: { '@type': 'WebSite', name: 'MetricsHour', url: 'https://metricshour.com' },
    }),
  }],
})
</script>
