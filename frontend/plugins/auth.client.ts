// Hydrate auth state from localStorage on every client-side page load.
//
// In Nuxt SSG mode, useState() restores from pre-rendered __NUXT_DATA__ (always null
// for auth) rather than calling the initializer. This plugin reads localStorage after
// hydration so tokens persist across page refreshes and full navigations.
export default defineNuxtPlugin(async () => {
  const auth = useAuth()
  if (auth.token.value) return   // already set (e.g. same-session navigation)

  const stored = localStorage.getItem('mh_auth_token')
  if (stored) {
    auth.token.value = stored
    await auth.restore()         // verify token + load user info from /api/auth/me
  }
})
