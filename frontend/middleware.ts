import { NextRequest, NextResponse } from 'next/server'

const ALLOWED_PATHS = new Set([
  '/waitlist',
  '/login',
  '/register',
  '/check-email',
  '/verify-email',
  '/forgot-password',
  '/reset-password',
  '/pricing',
  '/privacy',
  '/security',
  '/contact',
  '/robots.txt',
  '/sitemap.xml',
  '/favicon.ico',
])

// Demo surfaces are reachable even while the waitlist gate is up, so prospective users
// can experience the core product (choose company -> pick filing -> get summary) before
// signing up. The homepage `/` stays gated and still routes to /waitlist.
const ALLOWED_PREFIXES = ['/_next', '/api', '/public', '/assets', '/company', '/filing']

// Protected routes that require authentication
const PROTECTED_ROUTES = ['/dashboard', '/profile', '/settings', '/admin']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Check authentication for protected routes
  // Note: This is a basic check. The backend will do the actual token validation.
  const isProtectedRoute = PROTECTED_ROUTES.some(route => pathname.startsWith(route))
  if (isProtectedRoute) {
    // Durable, non-credential session marker set by the backend for the whole refresh-token
    // lifetime (see SESSION_PRESENCE_COOKIE in backend/app/routers/auth.py — keep names in sync).
    // We gate on this rather than the 30-min access token so a logged-in user isn't bounced to
    // /login whenever the access token rotates. Real auth is still enforced by the API on every
    // request (and the client silently refreshes); this only tells the edge guard a session exists.
    const hasSessionCookie = request.cookies.has('en_session')

    if (!hasSessionCookie) {
      const loginUrl = request.nextUrl.clone()
      loginUrl.pathname = '/login'
      // Add redirect parameter to return to original page after login
      loginUrl.searchParams.set('redirect', pathname)
      return NextResponse.redirect(loginUrl)
    }
  }

  // Waitlist mode check
  const waitlistMode = process.env.WAITLIST_MODE !== 'false'
  if (!waitlistMode) {
    return NextResponse.next()
  }

  if (ALLOWED_PATHS.has(pathname)) {
    return NextResponse.next()
  }

  if (ALLOWED_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return NextResponse.next()
  }

  const url = request.nextUrl.clone()
  url.pathname = '/waitlist'
  return NextResponse.redirect(url)
}

export const config = {
  matcher: ['/((?!_next/static|_next/image).*)'],
}
