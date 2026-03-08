<template>
  <div></div>
</template>

<script setup lang="ts">
// /auth/ has no content — redirect to homepage
navigateTo('/', { redirectCode: 301 })

useSeoMeta({ robots: 'noindex, nofollow' })
</script>
