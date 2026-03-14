// API client — auto-injects Bearer token when the user is logged in.

const API_TIMEOUT_MS = 15000

function _fetchWithTimeout(url: string, options: RequestInit): Promise<Response> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS)
  return fetch(url, { ...options, signal: ctrl.signal }).finally(() => clearTimeout(timer))
}

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
    const res = await _fetchWithTimeout(url.toString(), { headers: _authHeaders() })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return res.json()
  }

  async function post<T>(path: string, body: unknown): Promise<T> {
    const res = await _fetchWithTimeout(`${base}${path}`, {
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
    const res = await _fetchWithTimeout(`${base}${path}`, {
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
    const res = await _fetchWithTimeout(`${base}${path}`, {
      method: 'DELETE',
      headers: _authHeaders(),
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
  }

  return { get, post, put, del }
}
