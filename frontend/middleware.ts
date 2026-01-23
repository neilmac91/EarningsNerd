import { NextRequest, NextResponse } from 'next/server'

const ALLOWED_PATHS = new Set([
  '/waitlist',
  '/privacy',
  '/security',
  '/contact',
  '/robots.txt',
  '/sitemap.xml',
  '/favicon.ico',
])

const ALLOWED_PREFIXES = ['/_next', '/api', '/public', '/assets']

// Protected routes that require authentication
const PROTECTED_ROUTES = ['/dashboard', '/profile', '/settings']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Check authentication for protected routes
  // Note: This is a basic check. The backend will do the actual token validation.
  const isProtectedRoute = PROTECTED_ROUTES.some(route => pathname.startsWith(route))
  if (isProtectedRoute) {
    // Check for session cookie (adjust cookie name if needed)
    // The actual cookie name might be different - checking common patterns
    const hasSessionCookie = request.cookies.has('session') ||
                             request.cookies.has('auth_token') ||
                             request.cookies.has('token') ||
                             // FastAPI typically uses 'session' or custom name
                             Array.from(request.cookies.getAll()).some(cookie =>
                               cookie.name.includes('session') || cookie.name.includes('auth')
                             )

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
