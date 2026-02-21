// API client — auto-injects Bearer token when the user is logged in.

export function useApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  function _authHeaders(): Record<string, string> {
    // Access the shared auth token state directly (no hook call — safe outside setup)
    if (import.meta.client) {
      const TOKEN_KEY = 'mh_auth_token'
      const t = localStorage.getItem(TOKEN_KEY)
      if (t) return { Authorization: `Bearer ${t}` }
    }
    return {}
  }

  async function get<T>(path: string, params?: Record<string, string | boolean | number>): Promise<T> {
    const url = new URL(`${base}${path}`)
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
    }
    const res = await fetch(url.toString(), { headers: _authHeaders() })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async function post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || `API error: ${res.status}`)
    }
    if (res.status === 204) return undefined as T
    return res.json()
  }

  async function put<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || `API error: ${res.status}`)
    }
    return res.json()
  }

  async function del(path: string): Promise<void> {
    const res = await fetch(`${base}${path}`, {
      method: 'DELETE',
      headers: _authHeaders(),
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
  }

  return { get, post, put, del }
}
