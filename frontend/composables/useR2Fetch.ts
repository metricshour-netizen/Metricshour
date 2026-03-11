/**
 * R2-first fetch with API fallback.
 *
 * r2Fetch   — for detail snapshots (flat objects): countries, stocks, trade pairs.
 * r2ListFetch — for list snapshots ({ generated_at, count, data: [...] }) — auto-unwraps to array.
 *
 * Snapshot origin: GET /snapshots/{key} on api.metricshour.com
 *   → FastAPI proxies to R2 and returns with Cache-Control headers
 *   → Cloudflare caches at the edge for 1 hour
 *   → On cache miss, falls back to the regular API endpoint
 *
 * When cdn.metricshour.com is configured as a Cloudflare R2 custom domain,
 * set NUXT_PUBLIC_R2_URL=https://cdn.metricshour.com to serve direct from R2.
 */
export function useR2Fetch() {
  const config = useRuntimeConfig()
  // Default: use the API's /snapshots/ proxy — Cloudflare caches responses at edge.
  // Override with NUXT_PUBLIC_R2_URL once cdn.metricshour.com R2 custom domain is set up.
  const r2Base = (config.public.r2PublicUrl as string) || (config.public.apiBase as string)
  const apiBase = config.public.apiBase as string

  async function r2Fetch<T>(r2Key: string, apiFallback: string): Promise<T> {
    if (r2Base) {
      try {
        const res = await fetch(`${r2Base.replace(/\/$/, '')}/${r2Key}`, {
          signal: AbortSignal.timeout(3000),
        })
        if (res.ok) return res.json() as Promise<T>
      } catch {
        // R2 miss, timeout, or network error — fall through to API
      }
    }

    const res = await fetch(`${apiBase.replace(/\/$/, '')}${apiFallback}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json() as Promise<T>
  }

  // List snapshots are wrapped: { generated_at, count, data: [...] }
  // This helper unwraps them so pages receive a plain array (same shape as the API).
  async function r2ListFetch<T>(r2Key: string, apiFallback: string): Promise<T[]> {
    const result = await r2Fetch<any>(r2Key, apiFallback)
    return (Array.isArray(result?.data) ? result.data : result) as T[]
  }

  return { r2Fetch, r2ListFetch }
}
