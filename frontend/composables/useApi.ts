export function useApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  async function get<T>(path: string, params?: Record<string, string | boolean>): Promise<T> {
    const url = new URL(`${base}${path}`)
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
    }
    const res = await fetch(url.toString())
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  return { get }
}
