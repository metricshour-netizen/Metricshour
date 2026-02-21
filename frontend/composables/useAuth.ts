// Auth composable — persists token in localStorage, shares state globally via useState.

const TOKEN_KEY = 'mh_auth_token'

interface AuthUser {
  id: number
  email: string
  tier: string
  is_admin: boolean
}

export function useAuth() {
  const token = useState<string | null>('auth.token', () => {
    if (import.meta.client) {
      return localStorage.getItem(TOKEN_KEY)
    }
    return null
  })

  const user = useState<AuthUser | null>('auth.user', () => null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => !!user.value?.is_admin)

  function _persist(t: string | null) {
    token.value = t
    if (import.meta.client) {
      if (t) {
        localStorage.setItem(TOKEN_KEY, t)
      } else {
        localStorage.removeItem(TOKEN_KEY)
      }
    }
  }

  async function restore() {
    // Re-load user info from /api/auth/me on app mount if token exists
    if (!token.value) return
    try {
      const config = useRuntimeConfig()
      const res = await fetch(`${config.public.apiBase}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token.value}` },
      })
      if (!res.ok) {
        _persist(null)
        user.value = null
        return
      }
      user.value = await res.json()
    } catch {
      // Network error — keep the token, don't wipe user session
    }
  }

  async function login(email: string, password: string): Promise<void> {
    const config = useRuntimeConfig()
    const form = new URLSearchParams({ username: email, password })
    const res = await fetch(`${config.public.apiBase}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || 'Login failed')
    }
    const data = await res.json()
    _persist(data.access_token)
    await restore()
  }

  async function register(email: string, password: string): Promise<void> {
    const config = useRuntimeConfig()
    const res = await fetch(`${config.public.apiBase}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || 'Registration failed')
    }
    const data = await res.json()
    _persist(data.access_token)
    await restore()
  }

  function logout() {
    _persist(null)
    user.value = null
  }

  return { token, user, isLoggedIn, isAdmin, login, register, logout, restore }
}
