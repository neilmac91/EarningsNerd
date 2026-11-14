// What a browser is sent that Vercel's platform sends for the app and Cloudflare leaves to the Worker: one address
// for each page, HTTPS only, and no page kept by the browser. cloudflare-front.mjs applies both functions to every
// request it answers; they live here, apart from the entry point, so tests/unit/cloudflareBrowser.spec.ts can run
// them without a build. docs/DEPLOYMENT.md, "Frontend on Cloudflare Workers (staging)".

// `wrangler dev` hands a Worker that has no hostname its local requests as they came: over HTTP, at a loopback
// address. One with a hostname is handed them at that hostname, and over HTTPS because its wrangler file says so
// (`dev.upstream_protocol`), so that this file treats a local request as it would a real one.
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]'])

/**
 * The redirect for a request that did not arrive at the site's one address: over HTTP, or at another of the
 * Worker's hostnames (production's bare domain). 308, as Vercel answers both, so the method and body are kept.
 * Null for a request that is already there. A Worker without CANONICAL_HOST, on a workers.dev address, only has
 * its HTTP requests moved to HTTPS.
 */
export function canonicalRedirect(request, env) {
  const url = new URL(request.url)
  if (LOCAL_HOSTS.has(url.hostname)) return null
  const host = env.CANONICAL_HOST || url.hostname
  if (url.protocol === 'https:' && url.hostname === host) return null
  return new Response(null, { status: 308, headers: { Location: `https://${host}${url.pathname}${url.search}` } })
}

/**
 * The response as a browser should receive it.
 *
 * HSTS, with Vercel's own value: Vercel adds it to every response, and Cloudflare adds none unless the zone is set to.
 *
 * Cache-Control: OpenNext marks a cached page `s-maxage=<seconds>, stale-while-revalidate=2592000`, written for a
 * CDN in front of it. Here nothing is in front but the browser, which may show such a page again from its own
 * cache for 30 days while it re-fetches, with scripts a later deploy has removed. Vercel keeps that header for its
 * own cache and sends browsers the one below; the page cache in R2 is not read through this header.
 */
export function forBrowser(response) {
  // A copy, because a response the runtime hands back can carry immutable headers.
  const sent = new Response(response.body, response)
  sent.headers.set('Strict-Transport-Security', 'max-age=63072000')
  if (/(^|[\s,])s-maxage=/i.test(sent.headers.get('Cache-Control') ?? '')) {
    sent.headers.set('Cache-Control', 'public, max-age=0, must-revalidate')
  }
  return sent
}
