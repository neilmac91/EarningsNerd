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

export function middleware(request: NextRequest) {
  const waitlistMode = process.env.WAITLIST_MODE !== 'false'
  if (!waitlistMode) {
    return NextResponse.next()
  }

  const { pathname } = request.nextUrl

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
