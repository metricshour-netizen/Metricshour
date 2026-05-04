// Proxy /sitemap.xml from the FastAPI backend so it serves at metricshour.com/sitemap.xml
// with the correct application/xml content type and is properly indexed by Google.
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const apiBase = (config.public?.apiBase as string) || 'https://api.metricshour.com'
  const xml = await $fetch<string>(`${apiBase}/sitemap.xml`, {
    headers: { Accept: 'application/xml' },
  })
  setHeader(event, 'Content-Type', 'application/xml; charset=utf-8')
  setHeader(event, 'Cache-Control', 'public, max-age=3600, s-maxage=3600, stale-while-revalidate=86400')
  return xml
})
