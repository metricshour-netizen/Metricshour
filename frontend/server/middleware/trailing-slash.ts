// Redirect to canonical form: lowercase path + trailing slash.
// Covers /stocks/AAPL/ → /stocks/aapl/ and /countries/CN/ → /countries/cn/
export default defineEventHandler((event) => {
  const url = event.node.req.url
  if (!url) return

  // Skip static assets, internal Nuxt/API paths
  if (
    url === '/' ||
    url.includes('.') ||
    url.startsWith('/_nuxt') ||
    url.startsWith('/__nuxt') ||
    url.startsWith('/api')
  ) return

  const [path, query] = url.split('?')
  const lowerPath = path.toLowerCase()
  const canonical = lowerPath.endsWith('/') ? lowerPath : lowerPath + '/'
  const qs = query ? '?' + query : ''

  if (path !== canonical) {
    return sendRedirect(event, canonical + qs, 301)
  }
})
