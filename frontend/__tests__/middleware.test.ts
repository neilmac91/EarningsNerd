import { describe, it, expect, beforeEach } from 'vitest'
import { NextRequest } from 'next/server'
import { middleware } from '@/middleware'

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
