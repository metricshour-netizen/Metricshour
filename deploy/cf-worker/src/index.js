/**
 * MetricsHour API Cache Worker
 *
 * Caching strategy:
 *   - API responses: CF Cache API (caches.default) — free, no quotas, per-datacenter
 *   - OG images:     R2 direct serve — zero origin hit, global CDN
 *   - KV:            Reserved for spotlight/intelligence (globally consistent hot data)
 *
 * CF Cache API vs KV:
 *   KV: 100k reads/day + 1k writes/day (free tier) — use for globally-consistent hot keys
 *   Cache API: unlimited, URL-keyed, per-datacenter — ideal for API response caching
 *
 * Deploy: wrangler deploy
 * DNS: api.metricshour.com → Worker (orange cloud in Cloudflare dashboard)
 */

// TTL per route pattern (seconds). Cache-Control max-age drives CF edge eviction.
const CACHE_RULES = [
  { re: /^\/api\/countries\/[A-Z]{2,3}$/, ttl: 3600 },
  { re: /^\/api\/countries\/[A-Z]{2,3}\/trade-partners$/, ttl: 3600 },
  { re: /^\/api\/countries\/[A-Z]{2,3}\/gdp-history$/, ttl: 86400 },
  { re: /^\/api\/countries\/[A-Z]{2,3}\/timeseries/, ttl: 86400 },
  { re: /^\/api\/countries$/, ttl: 300 },
  { re: /^\/api\/assets\/[A-Z0-9.\-]+$/, ttl: 900 },
  { re: /^\/api\/assets$/, ttl: 300 },
  { re: /^\/api\/trade\/[A-Z]{2,3}-[A-Z]{2,3}$/, ttl: 86400 },
  { re: /^\/api\/intelligence\/spotlight$/, ttl: 10800 },
  { re: /^\/api\/summaries\/[a-z]+\/.+$/, ttl: 3600 },
  { re: /^\/api\/feed$/, ttl: 60 },
]

// KV-served routes: globally consistent, written by backend workers on data updates
const KV_RULES = [
  { re: /^\/api\/intelligence\/spotlight$/, key: 'spotlight' },
]

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url)

    // ── CORS preflight ────────────────────────────────────────────────────────
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders() })
    }

    // ── /og/* — forward to origin (R2 binding not yet enabled) ──────────────
    if (request.method === 'GET' && url.pathname.startsWith('/og/')) {
      return forwardToOrigin(request, env)
    }

    // Only cache GET requests
    if (request.method !== 'GET') {
      return forwardToOrigin(request, env)
    }

    // ── KV-served routes (globally consistent hot data) ───────────────────────
    const kvRule = KV_RULES.find(r => r.re.test(url.pathname))
    if (kvRule) {
      const cached = await env.API_CACHE.get(kvRule.key)
      if (cached !== null) {
        return jsonResponse(cached, 'KV-HIT')
      }
      // KV miss — fall through to CF Cache / origin
    }

    // ── CF Cache API (free, no quotas, per-datacenter) ────────────────────────
    const rule = CACHE_RULES.find(r => r.re.test(url.pathname))
    if (!rule) {
      return forwardToOrigin(request, env)
    }

    const cache = caches.default
    const cacheRequest = new Request(url.toString(), { method: 'GET' })

    const cached = await cache.match(cacheRequest)
    if (cached) {
      const body = await cached.text()
      return jsonResponse(body, 'HIT', rule.ttl)
    }

    // Cache miss — fetch from origin
    const originResp = await forwardToOrigin(request, env)
    if (!originResp.ok) return addCors(originResp)

    const body = await originResp.text()

    // Store in CF Cache async (don't block response)
    ctx.waitUntil(
      cache.put(
        cacheRequest,
        new Response(body, {
          headers: {
            'Content-Type': 'application/json',
            'Cache-Control': `public, max-age=${rule.ttl}`,
          },
        })
      )
    )

    return jsonResponse(body, 'MISS', rule.ttl)
  },
}

function forwardToOrigin(request, env) {
  const url = new URL(request.url)
  const originUrl = env.ORIGIN + url.pathname + url.search
  return fetch(originUrl, {
    method: request.method,
    headers: { ...Object.fromEntries(request.headers), host: new URL(env.ORIGIN).host },
    body: request.body,
  })
}

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  }
}

function jsonResponse(body, cacheStatus, ttl = 60) {
  return new Response(body, {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': `public, max-age=${ttl}`,
      'X-Cache': cacheStatus,
      ...corsHeaders(),
    },
  })
}

function addCors(response) {
  const r = new Response(response.body, response)
  Object.entries(corsHeaders()).forEach(([k, v]) => r.headers.set(k, v))
  return r
}
