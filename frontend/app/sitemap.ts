import type { MetadataRoute } from 'next'

const SITE_URL = 'https://www.earningsnerd.io'

// Re-fetch the backend sitemap hourly.
export const revalidate = 3600

// Resolved inline (instead of importing lib/api/client) to keep axios and its
// interceptors out of this metadata route's server bundle.
const getBackendUrl = (): string => {
  const url =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    (process.env.NODE_ENV === 'development'
      ? 'http://localhost:8000'
      : 'https://api.earningsnerd.io')
  // Tolerate a configured trailing slash (avoids `//sitemap.xml`).
  return url.replace(/\/$/, '')
}

const STATIC_ENTRIES: MetadataRoute.Sitemap = [
  { url: `${SITE_URL}/`, changeFrequency: 'daily', priority: 1 },
  { url: `${SITE_URL}/pricing`, changeFrequency: 'weekly', priority: 0.8 },
]

type ChangeFrequency = MetadataRoute.Sitemap[number]['changeFrequency']
const VALID_FREQUENCIES = new Set([
  'always', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'never',
])

/**
 * Proxies the backend's company-aware sitemap (`GET /sitemap.xml` on the API).
 * URLs are re-based onto the canonical site origin so a misconfigured backend
 * base URL can't leak a wrong host to crawlers. Falls back to the static core
 * routes if the backend is unreachable (e.g. during CI builds).
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  try {
    const res = await fetch(`${getBackendUrl()}/sitemap.xml`, {
      next: { revalidate: 3600 },
      // Cap the fetch well under Vercel's 60s per-route export limit. A cold backend container can
      // make /sitemap.xml slow, and a hanging fetch never throws — so without this the production
      // build (which prerenders this route) blocks for 60s and aborts. On timeout we fall through to
      // the static core routes below: a degraded sitemap, but a successful deploy (ISR refills it
      // hourly once the backend is warm).
      signal: AbortSignal.timeout(20000),
    })
    if (!res.ok) return STATIC_ENTRIES

    const xml = await res.text()
    const entries: MetadataRoute.Sitemap = []

    for (const block of xml.match(/<url>[\s\S]*?<\/url>/g) ?? []) {
      const loc = block.match(/<loc>(.*?)<\/loc>/)?.[1]
      if (!loc) continue

      let path: string
      try {
        path = new URL(loc).pathname
      } catch {
        continue
      }

      const lastmod = block.match(/<lastmod>(.*?)<\/lastmod>/)?.[1]
      const changefreq = block.match(/<changefreq>(.*?)<\/changefreq>/)?.[1]
      const priority = Number(block.match(/<priority>(.*?)<\/priority>/)?.[1])

      entries.push({
        url: `${SITE_URL}${path === '/' ? '/' : path.replace(/\/$/, '')}`,
        ...(lastmod ? { lastModified: new Date(lastmod) } : {}),
        ...(changefreq && VALID_FREQUENCIES.has(changefreq)
          ? { changeFrequency: changefreq as ChangeFrequency }
          : {}),
        ...(Number.isFinite(priority) ? { priority } : {}),
      })
    }

    return entries.length > 0 ? entries : STATIC_ENTRIES
  } catch {
    return STATIC_ENTRIES
  }
}
