const BASE = 'https://metricshour.com'
const API = 'https://api.metricshour.com'

const STATIC_ROUTES = [
  { loc: `${BASE}/`,           priority: '1.0', changefreq: 'daily' },
  { loc: `${BASE}/markets`,    priority: '0.9', changefreq: 'daily' },
  { loc: `${BASE}/stocks`,     priority: '0.9', changefreq: 'daily' },
  { loc: `${BASE}/countries`,  priority: '0.9', changefreq: 'weekly' },
  { loc: `${BASE}/trade`,      priority: '0.9', changefreq: 'weekly' },
  { loc: `${BASE}/commodities`, priority: '0.8', changefreq: 'daily' },
  { loc: `${BASE}/pricing`,    priority: '0.7', changefreq: 'monthly' },
  { loc: `${BASE}/feed`,       priority: '0.6', changefreq: 'daily' },
]

function urlEntry(loc: string, priority: string, changefreq: string): string {
  return `  <url>\n    <loc>${loc}</loc>\n    <changefreq>${changefreq}</changefreq>\n    <priority>${priority}</priority>\n  </url>`
}

export default defineEventHandler(async () => {
  const entries: string[] = STATIC_ROUTES.map(r => urlEntry(r.loc, r.priority, r.changefreq))

  try {
    const [assets, countries, trades, blogPosts] = await Promise.allSettled([
      $fetch<any[]>(`${API}/api/assets`),
      $fetch<any[]>(`${API}/api/countries`),
      $fetch<any[]>(`${API}/api/trade`),
      $fetch<any[]>(`${API}/api/blog`).catch(() => []),
    ])

    if (assets.status === 'fulfilled') {
      for (const a of assets.value) {
        if (a.symbol) {
          entries.push(urlEntry(`${BASE}/stocks/${a.symbol}`, '0.7', 'daily'))
        }
      }
    }

    if (countries.status === 'fulfilled') {
      for (const c of countries.value) {
        if (c.code) {
          entries.push(urlEntry(`${BASE}/countries/${c.code.toLowerCase()}`, '0.7', 'weekly'))
        }
      }
    }

    if (trades.status === 'fulfilled') {
      for (const t of trades.value) {
        const exp = t.exporter?.code?.toLowerCase()
        const imp = t.importer?.code?.toLowerCase()
        if (exp && imp) {
          entries.push(urlEntry(`${BASE}/trade/${exp}-${imp}`, '0.6', 'monthly'))
        }
      }
    }

    if (blogPosts.status === 'fulfilled' && Array.isArray(blogPosts.value)) {
      for (const p of blogPosts.value) {
        if (p.slug) {
          entries.push(urlEntry(`${BASE}/blog/${p.slug}`, '0.8', 'weekly'))
        }
      }
    }
  } catch {
    // Return sitemap with at least static routes if API is unreachable
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${entries.join('\n')}\n</urlset>`

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  })
})
