/**
 * MetricsHour Social Share Worker
 *
 * Intercepts requests to metricshour.com/feed/{id} from social crawlers
 * (Twitterbot, facebookexternalhit, LinkedInBot, Slackbot, WhatsApp, etc.)
 * and returns a minimal HTML page with proper og:meta tags fetched from the API.
 *
 * All other requests pass through to Cloudflare Pages normally.
 *
 * Deploy: wrangler deploy (from deploy/cf-worker-share/)
 * Route:  metricshour.com/feed/*  (set in Cloudflare dashboard or wrangler.toml)
 */

const SOCIAL_BOTS = /Twitterbot|facebookexternalhit|LinkedInBot|Slackbot|WhatsApp|TelegramBot|Discordbot|Googlebot|bingbot|Applebot|Pinterest/i

const TYPE_DESCRIPTIONS = {
  price_move: 'Live price movement tracked on MetricsHour.',
  indicator_release: 'Macro economic data release on MetricsHour.',
  macro_release: 'Macro economic data release on MetricsHour.',
  trade_update: 'Bilateral trade flow update on MetricsHour.',
  blog: 'Market analysis and insights on MetricsHour.',
}

const TYPE_OG_IMAGES = {
  price_move: 'https://metricshour.com/og-feed-price.png',
  indicator_release: 'https://metricshour.com/og-feed-macro.png',
  macro_release: 'https://metricshour.com/og-feed-macro.png',
  trade_update: 'https://metricshour.com/og-feed-trade.png',
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export default {
  async fetch(request) {
    const url = new URL(request.url)
    const ua = request.headers.get('User-Agent') || ''

    // Only intercept /feed/{numeric_id} paths
    const feedMatch = url.pathname.match(/^\/feed\/(\d+)$/)
    if (!feedMatch) {
      return fetch(request)
    }

    // Only intercept social crawlers — real users get the normal page
    if (!SOCIAL_BOTS.test(ua)) {
      return fetch(request)
    }

    const eventId = feedMatch[1]
    const pageUrl = `https://metricshour.com/feed/${eventId}`

    try {
      const apiRes = await fetch(
        `https://api.metricshour.com/api/feed/events/${eventId}`,
        { headers: { 'User-Agent': 'MetricsHour-ShareWorker/1.0' } }
      )

      if (!apiRes.ok) {
        // Event not found — pass through to Pages (shows 404 page)
        return fetch(request)
      }

      const event = await apiRes.json()

      const title = escapeHtml(event.title || 'Market Insight')
      const description = escapeHtml(
        event.body ||
        TYPE_DESCRIPTIONS[event.event_type] ||
        'Real-time global financial intelligence on MetricsHour.'
      )
      // Prefer event's own image_url, then type-specific fallback, then global og
      const image =
        event.image_url ||
        TYPE_OG_IMAGES[event.event_type] ||
        'https://metricshour.com/og-image.png'

      const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>${title} — MetricsHour</title>

  <!-- Open Graph -->
  <meta property="og:type"        content="article" />
  <meta property="og:site_name"   content="MetricsHour" />
  <meta property="og:url"         content="${escapeHtml(pageUrl)}" />
  <meta property="og:title"       content="${title} — MetricsHour" />
  <meta property="og:description" content="${description}" />
  <meta property="og:image"       content="${escapeHtml(image)}" />
  <meta property="og:image:width"  content="1200" />
  <meta property="og:image:height" content="630" />

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image" />
  <meta name="twitter:site"        content="@metricshour" />
  <meta name="twitter:title"       content="${title} — MetricsHour" />
  <meta name="twitter:description" content="${description}" />
  <meta name="twitter:image"       content="${escapeHtml(image)}" />

  <!-- Redirect browsers to the real page -->
  <meta http-equiv="refresh" content="0;url=${escapeHtml(pageUrl)}" />
  <link rel="canonical" href="${escapeHtml(pageUrl)}" />
</head>
<body>
  <p>Redirecting to <a href="${escapeHtml(pageUrl)}">MetricsHour</a>...</p>
</body>
</html>`

      return new Response(html, {
        status: 200,
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'public, max-age=300',
        },
      })
    } catch {
      // Any error — fall through to normal Pages response
      return fetch(request)
    }
  },
}
