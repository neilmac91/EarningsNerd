import { afterEach, describe, expect, it, vi } from 'vitest'
import sitemap from '@/app/sitemap'

const origin = 'https://www.earningsnerd.io'
const xml = (ticker: string, date: string) =>
  `<urlset><url><loc>https://wrong-host.example/company/${ticker}/</loc>` +
  `<lastmod>${date}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url></urlset>`

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('sitemap regeneration', () => {
  it('requests fresh upstream bodies and publishes the latest canonical entries', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response(xml('AAPL', '2026-09-01')))
      .mockResolvedValueOnce(new Response(xml('MSFT', '2026-09-05')))
    vi.stubGlobal('fetch', fetch)

    expect(await sitemap()).toEqual([{
      url: `${origin}/company/AAPL`, lastModified: new Date('2026-09-01'),
      changeFrequency: 'daily', priority: 0.8,
    }])
    expect(await sitemap()).toEqual([{
      url: `${origin}/company/MSFT`, lastModified: new Date('2026-09-05'),
      changeFrequency: 'daily', priority: 0.8,
    }])
    expect(fetch).toHaveBeenCalledTimes(2)
    for (const [url, options] of fetch.mock.calls) {
      expect(url).toMatch(/\/sitemap\.xml$/)
      expect(options.cache).toBe('no-store')
      expect(options.next).toBeUndefined()
      expect(options.signal).toBeInstanceOf(AbortSignal)
    }
  })

  it.each(['unreachable', 'HTTP error', 'empty XML'])(
    'retains the complete static core including terms when the backend is %s',
    async (failure) => {
      // A plain throwing function avoids Vitest's rejecting-mock call tracking issue.
      vi.stubGlobal('fetch', async () => {
        if (failure === 'unreachable') throw new TypeError('Network unavailable')
        return failure === 'HTTP error'
          ? new Response('', { status: 503 })
          : new Response('<urlset></urlset>')
      })
      const entries = await sitemap()
      expect(entries.map((entry) => entry.url)).toEqual([
        `${origin}/`, `${origin}/pricing`, `${origin}/contact`,
        `${origin}/privacy`, `${origin}/terms`, `${origin}/security`,
      ])
      expect(entries.every((entry) => entry.lastModified === undefined)).toBe(true)
    },
  )
})
