import { describe, it, expect, beforeEach } from 'vitest'
import { NextRequest } from 'next/server'
import { middleware } from '@/middleware'
import manifest from '@/app/manifest'
import { SOCIAL_CARD } from '@/lib/socialCard'

// Mirror production (vercel.json sets WAITLIST_MODE=false) so the pass-through case below
// isn't intercepted by the separate waitlist gate.
beforeEach(() => {
  process.env.WAITLIST_MODE = 'false'
})

function reqFor(path: string, opts: { session?: boolean; accessToken?: boolean } = {}): NextRequest {
  const req = new NextRequest(new URL(`https://earningsnerd.io${path}`))
  if (opts.session) req.cookies.set('en_session', '1')
  if (opts.accessToken) req.cookies.set('earningsnerd_access_token', 'jwt')
  return req
}

describe('protected-route middleware (redirect-loop regression)', () => {
  it.each(['/dashboard', '/dashboard/watchlist', '/dashboard/settings'])(
    'redirects %s to /login (preserving the redirect param) when no session cookie',
    (path) => {
      const res = middleware(reqFor(path))
      const location = res.headers.get('location')
      expect(location).toContain('/login')
      expect(location).toContain(`redirect=${encodeURIComponent(path)}`)
    },
  )

  it('passes protected routes through when the durable en_session cookie is present', () => {
    const res = middleware(reqFor('/dashboard/watchlist', { session: true }))
    expect(res.headers.get('location')).toBeNull() // NextResponse.next() => no redirect
  })

  it('gates on en_session, NOT the short-lived access token (30-min-bounce regression)', () => {
    // Access token present but no en_session => still gated. Confirms the guard no longer
    // depends on the cookie that rotates every 30 minutes.
    const res = middleware(reqFor('/dashboard', { accessToken: true }))
    expect(res.headers.get('location')).toContain('/login')
  })
})

describe('waitlist gate (WAITLIST_MODE=true, the rollback state)', () => {
  beforeEach(() => {
    process.env.WAITLIST_MODE = 'true'
  })

  // The files every page points at must survive the gate: the social card (lib/socialCard.ts, read by
  // scrapers with no session), the touch icon and PWA icons, the manifest, and /terms, which the
  // footer links beside /privacy. Redirecting any of them to /waitlist breaks link previews and icons.
  // Read from the sources, so a moved card or a new manifest icon is checked without editing this list.
  const cardPath = new URL(SOCIAL_CARD.url, 'https://earningsnerd.io').pathname
  const manifestIcons = (manifest().icons ?? []).map((icon) => icon.src)

  it('reads the card and the manifest icons from their sources', () => {
    expect(cardPath).toBe('/og-image.png')
    expect(manifestIcons.length).toBeGreaterThanOrEqual(4)
  })

  it.each([
    cardPath,
    '/apple-touch-icon.png',
    ...manifestIcons,
    '/manifest.webmanifest',
    '/favicon.ico',
    '/assets/earningsnerd-appicon.svg',
    '/terms',
    '/privacy',
  ])('lets %s through', (path) => {
    expect(middleware(reqFor(path)).headers.get('location')).toBeNull()
  })

  it('still sends the gated homepage to /waitlist (the allowlist is not a blanket pass)', () => {
    expect(middleware(reqFor('/')).headers.get('location')).toContain('/waitlist')
    expect(middleware(reqFor('/og-image.png.html')).headers.get('location')).toContain('/waitlist')
  })
})
