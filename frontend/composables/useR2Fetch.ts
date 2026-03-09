/**
 * R2-first fetch with API fallback.
 *
 * Tries the Cloudflare R2 CDN snapshot first (~10ms edge latency).
 * Falls back to FastAPI if R2 returns a non-200 or the request fails.
 *
 * Usage:
 *   const data = await r2Fetch<CountryData>(
 *     `snapshots/countries/${code}.json`,
 *     `/api/countries/${code}`,
 *   )
 */
export function useR2Fetch() {
  const config = useRuntimeConfig()
  const r2Base = config.public.r2PublicUrl as string
  const apiBase = config.public.apiBase as string

  async function r2Fetch<T>(r2Key: string, apiFallback: string): Promise<T> {
    // Try R2 CDN first
    if (r2Base) {
      try {
        const res = await fetch(`${r2Base.replace(/\/$/, '')}/${r2Key}`, {
          // 3s timeout — if R2 is slow, fall through to API immediately
          signal: AbortSignal.timeout(3000),
        })
        if (res.ok) {
          const json = await res.json()
          // R2 snapshots wrap list data in { data: [...] } but detail pages are flat objects.
          // Return as-is — callers handle both shapes.
          return json as T
        }
      } catch {
        // R2 miss, timeout, or network error — fall through silently
      }
    }

    // Fall back to FastAPI
    const res = await fetch(`${apiBase.replace(/\/$/, '')}${apiFallback}`)
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json() as Promise<T>
  }

  return { r2Fetch }
}
