// Redirect non-trailing-slash URLs to trailing-slash canonical form.
// All page canonicals use trailing slash (e.g. /countries/us/) so we enforce it
// server-side to prevent Google from seeing duplicate content at both URL forms.
export default defineEventHandler((event) => {
  const url = event.node.req.url
  if (!url) return

  // Skip: already has trailing slash, static assets (contain dot), internal Nuxt/API paths
  if (
    url === '/' ||
    url.endsWith('/') ||
    url.includes('.') ||
    url.startsWith('/_nuxt') ||
    url.startsWith('/__nuxt') ||
    url.startsWith('/api')
  ) return

  // Preserve query string
  const [path, query] = url.split('?')
  const redirectTo = path + '/' + (query ? '?' + query : '')
  return sendRedirect(event, redirectTo, 301)
})
