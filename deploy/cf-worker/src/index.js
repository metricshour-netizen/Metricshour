/**
 * MetricsHour API Cache Worker
 * Intercepts GET requests to api.metricshour.com, serves from KV when cached.
 * Cache TTLs mirror the backend Redis TTLs.
 *
 * Deploy: wrangler deploy
 * DNS: api.metricshour.com → Worker (orange cloud in Cloudflare dashboard)
 */

const CACHE_RULES = [
  // Pattern, TTL in seconds
  { re: /^\/api\/countries\/[A-Z]{2,3}$/, ttl: 3600 },
  { re: /^\/api\/countries\/[A-Z]{2,3}\/trade-partners$/, ttl: 3600 },
  { re: /^\/api\/countries\/[A-Z]{2,3}\/gdp-history$/, ttl: 3600 },
  { re: /^\/api\/countries\/[A-Z]{2,3}\/timeseries/, ttl: 3600 },
  { re: /^\/api\/countries$/, ttl: 300 },
  { re: /^\/api\/assets\/[A-Z0-9.\-]+$/, ttl: 900 },
  { re: /^\/api\/assets$/, ttl: 300 },
  { re: /^\/api\/trade\/[A-Z]{2,3}\/[A-Z]{2,3}$/, ttl: 21600 },
  { re: /^\/api\/intelligence\/spotlight$/, ttl: 10800 },
  { re: /^\/api\/summaries\/[a-z]+\/.+$/, ttl: 3600 },
]

export default {
  async fetch(request, env) {
    const url = new URL(request.url)

    // ── /og/* — serve PNG images directly from R2 (edge CDN, zero origin hit) ──
    if (request.method === 'GET' && url.pathname.startsWith('/og/')) {
      const key = url.pathname.slice(1)  // strip leading /  →  og/feed/1.png
      const obj = await env.R2.get(key)
      if (obj) {
        return new Response(obj.body, {
          headers: {
            'Content-Type': 'image/png',
            'Cache-Control': 'public, max-age=86400, s-maxage=86400',
            'X-Served-From': 'R2',
          },
        })
      }
      // Not in R2 yet — fall through to origin (FastAPI generates it + uploads to R2)
      return forwardToOrigin(request, env)
    }

    // Only cache safe, idempotent GET requests
    if (request.method !== 'GET') {
      return forwardToOrigin(request, env)
    }

    // Find applicable cache rule
    const rule = CACHE_RULES.find(r => r.re.test(url.pathname))
    if (!rule) {
      return forwardToOrigin(request, env)
    }

    // Include query string in key so ?region=EU is cached separately
    const cacheKey = url.pathname + url.search

    // L1: KV hit → serve immediately (~1ms at edge)
    const cached = await env.API_CACHE.get(cacheKey)
    if (cached !== null) {
      return new Response(cached, {
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': `public, max-age=${rule.ttl}`,
          'X-Cache': 'HIT',
          'Access-Control-Allow-Origin': '*',
        },
      })
    }

    // KV miss → fetch from origin, store in KV
    const originResp = await forwardToOrigin(request, env)
    if (!originResp.ok) return originResp

    const body = await originResp.text()

    // Store async (don't await) so we don't add latency on cache misses
    env.API_CACHE.put(cacheKey, body, { expirationTtl: rule.ttl })

    return new Response(body, {
      status: originResp.status,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': `public, max-age=${rule.ttl}`,
        'X-Cache': 'MISS',
        'Access-Control-Allow-Origin': '*',
      },
    })
  },
}

function forwardToOrigin(request, env) {
  const url = new URL(request.url)
  const originUrl = env.ORIGIN + url.pathname + url.search
  return fetch(originUrl, {
    method: request.method,
    headers: request.headers,
    body: request.body,
  })
}
