<template>
  <Head>
    <Meta name="robots" content="noindex, nofollow" />
  </Head>
  <div></div>
</template>

<script setup lang="ts">
// /auth/ has no content — redirect to homepage
navigateTo('/', { redirectCode: 301 })
</script>
