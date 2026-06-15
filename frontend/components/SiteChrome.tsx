'use client'

import { usePathname } from 'next/navigation'
import Header from '@/components/Header'
import Footer from '@/components/Footer'

// Auth routes render their own full-screen immersive shell (AuthShell), so the
// marketing header/footer are suppressed there.
const AUTH_ROUTES = [
  '/login',
  '/register',
  '/check-email',
  '/verify-email',
  '/forgot-password',
  '/reset-password',
]

function isAuthRoute(pathname: string | null): boolean {
  if (!pathname) return false
  return AUTH_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`))
}

export function SiteHeader() {
  return isAuthRoute(usePathname()) ? null : <Header />
}

export function SiteFooter() {
  return isAuthRoute(usePathname()) ? null : <Footer />
}
