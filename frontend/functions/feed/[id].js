/**
 * Cloudflare Pages Function — /feed/:id
 *
 * Social crawlers (Twitterbot, LinkedInBot, WhatsApp, Discord, Telegram, etc.)
 * don't execute JavaScript, so Nuxt SSG OG tags are invisible to them.
 *
 * This function intercepts requests from known social bots, fetches the event
 * from the FastAPI backend, and returns a minimal HTML page with full OG + Twitter
 * Card meta tags baked into the <head>.
 *
 * Real browsers pass straight through to the Nuxt static app.
 */

const API_BASE = 'https://api.metricshour.com'
const CANONICAL_BASE = 'https://metricshour.com'
const SITE_NAME = 'MetricsHour'
const TWITTER_HANDLE = '@metricshour'

const BOT_PATTERNS = [
  'Twitterbot',
  'LinkedInBot',
  'WhatsApp',
  'TelegramBot',
  'Discordbot',
  'Slackbot',
  'facebookexternalhit',
  'Googlebot',
  'bingbot',
  'Applebot',
  'Pinterest',
  'Embedly',
  'Quora Link Preview',
  'Iframely',
]

function isSocialBot(userAgent) {
  if (!userAgent) return false
  return BOT_PATTERNS.some(p => userAgent.includes(p))
}

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function truncate(str, max) {
  if (!str) return ''
  const s = str.trim()
  if (s.length <= max) return s
  return s.slice(0, max).replace(/\s+\S*$/, '') + '…'
}

export async function onRequestGet(context) {
  const { request, params, next } = context
  const ua = request.headers.get('User-Agent') || ''

  // Pass real browsers straight through to Nuxt
  if (!isSocialBot(ua)) {
    return next()
  }

  const eventId = params.id

  let event = null
  try {
    const res = await fetch(`${API_BASE}/api/feed/events/${eventId}`, {
      headers: { 'Accept': 'application/json' },
      cf: { cacheTtl: 300, cacheEverything: true },
    })
    if (res.ok) {
      event = await res.json()
    }
  } catch (_) {
    // fall through to generic meta
  }

  const canonical = `${CANONICAL_BASE}/feed/${eventId}`
  const title = event ? esc(`${event.title} — ${SITE_NAME}`) : esc(`Market Insight — ${SITE_NAME}`)
  const desc = event ? esc(truncate(event.body, 200)) : esc('Real-time global market intelligence on MetricsHour.')
  const ogImage = esc(event?.image_url || `${API_BASE}/og/feed/${eventId}.png`)

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>${title}</title>
  <meta name="robots" content="noindex">

  <meta property="og:type"         content="article">
  <meta property="og:site_name"    content="${esc(SITE_NAME)}">
  <meta property="og:url"          content="${esc(canonical)}">
  <meta property="og:title"        content="${title}">
  <meta property="og:description"  content="${desc}">
  <meta property="og:image"        content="${ogImage}">
  <meta property="og:image:width"  content="1200">
  <meta property="og:image:height" content="630">

  <meta name="twitter:card"        content="summary_large_image">
  <meta name="twitter:site"        content="${esc(TWITTER_HANDLE)}">
  <meta name="twitter:url"         content="${esc(canonical)}">
  <meta name="twitter:title"       content="${title}">
  <meta name="twitter:description" content="${desc}">
  <meta name="twitter:image"       content="${ogImage}">
</head>
<body></body>
</html>`

  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=300, s-maxage=300',
    },
  })
}
