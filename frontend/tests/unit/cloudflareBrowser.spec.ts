// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { canonicalRedirect, forBrowser } from '../../cloudflare-browser.mjs'

/**
 * What the front Worker does for a browser that Vercel's platform does for the app (cloudflare-browser.mjs):
 * one address per page, HTTPS only, and a page the browser does not keep. The expected values are the ones
 * production sent on Vercel on 2026-11-14 (docs/DEPLOYMENT.md, "Moving production to Cloudflare Workers").
 */
const production = { CANONICAL_HOST: 'www.earningsnerd.io' }
const locationOf = (url: string, env: Record<string, string>, init?: RequestInit) => {
  const redirect = canonicalRedirect(new Request(url, init), env)
  return redirect ? [redirect.status, redirect.headers.get('Location')] : null
}

describe('canonicalRedirect', () => {
  it('leaves a request at the site\'s own address alone', () => {
    expect(locationOf('https://www.earningsnerd.io/company/AAPL?tab=filings', production)).toBeNull()
    expect(locationOf('https://staging.earningsnerd.io/', { CANONICAL_HOST: 'staging.earningsnerd.io' })).toBeNull()
  })

  it('sends the bare domain and plain HTTP to it in one step, keeping the path and the query', () => {
    expect(locationOf('https://earningsnerd.io/pricing?x=1', production)).toEqual([308, 'https://www.earningsnerd.io/pricing?x=1'])
    expect(locationOf('http://www.earningsnerd.io/', production)).toEqual([308, 'https://www.earningsnerd.io/'])
    expect(locationOf('http://earningsnerd.io/filing/3', production)).toEqual([308, 'https://www.earningsnerd.io/filing/3'])
    // 308, not 301 or 302: a form posted to the old address is posted again, not turned into a GET.
    expect(locationOf('https://earningsnerd.io/api/x', production, { method: 'POST' })).toEqual([308, 'https://www.earningsnerd.io/api/x'])
  })

  it('never builds the address from anything but the path and the query', () => {
    // A path that begins with two slashes would read as another host if it were pasted after the scheme alone.
    const [, location] = locationOf('https://earningsnerd.io//evil.example/x', production) ?? []
    expect(new URL(location as string).host).toBe('www.earningsnerd.io')
  })

  it('moves a Worker without a hostname of its own to HTTPS and nowhere else', () => {
    expect(locationOf('https://earningsnerd-frontend.example.workers.dev/pricing', {})).toBeNull()
    expect(locationOf('http://earningsnerd-frontend.example.workers.dev/pricing', {})).toEqual([308, 'https://earningsnerd-frontend.example.workers.dev/pricing'])
  })

  it('leaves the local Workers runtime alone, which is requested over HTTP at a loopback address', () => {
    for (const local of ['http://127.0.0.1:8788/pricing', 'http://localhost:8787/', 'http://[::1]:8787/']) {
      expect(locationOf(local, { CANONICAL_HOST: 'staging.earningsnerd.io' }), local).toBeNull()
    }
  })
})

describe('forBrowser', () => {
  const sent = (headers: Record<string, string>, status = 200) => forBrowser(new Response(status === 304 ? null : 'page', { status, headers }))

  it('adds HSTS to every response, with the value Vercel sent', () => {
    for (const response of [sent({}), sent({}, 404), sent({ Location: '/login' }, 307), sent({}, 304)]) {
      expect(response.headers.get('Strict-Transport-Security')).toBe('max-age=63072000')
    }
  })

  it('replaces the caching header OpenNext writes for a CDN with the one Vercel sends a browser', () => {
    for (const cdn of ['s-maxage=1800, stale-while-revalidate=2592000', 'public, s-maxage=31536000', 'S-MaxAge=60']) {
      expect(sent({ 'Cache-Control': cdn }).headers.get('Cache-Control'), cdn).toBe('public, max-age=0, must-revalidate')
    }
  })

  it('leaves every other caching header as the app set it', () => {
    for (const own of ['private, no-cache, no-store, max-age=0, must-revalidate', 'public,max-age=31536000,immutable', 'no-store']) {
      expect(sent({ 'Cache-Control': own }).headers.get('Cache-Control')).toBe(own)
    }
    expect(sent({}).headers.has('Cache-Control')).toBe(false)
  })

  it('sends the response it was given otherwise: the status, the body and the other headers', async () => {
    const response = sent({ 'Cache-Control': 's-maxage=60', 'X-Frame-Options': 'DENY', 'x-nextjs-cache': 'HIT' }, 404)
    expect([response.status, response.headers.get('X-Frame-Options'), response.headers.get('x-nextjs-cache')]).toEqual([404, 'DENY', 'HIT'])
    expect(await response.text()).toBe('page')
  })

  it('copies a response whose headers cannot be changed, as the runtime hands them back', () => {
    const fixed = Response.redirect('https://www.earningsnerd.io/login', 307)
    expect(() => fixed.headers.set('x', 'y')).toThrow()
    expect(forBrowser(fixed).headers.get('Strict-Transport-Security')).toBe('max-age=63072000')
  })
})
