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

export function isAuthRoute(pathname: string | null): boolean {
  if (!pathname) return false
  return AUTH_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`))
}

/**
 * Skip link: the first focusable element on every page with the site header, so keyboard and
 * screen-reader users can bypass the header nav. Visually hidden until focused, then pinned
 * top-left above the sticky header (z above its z-50). Targets the `#main` content wrapper in
 * app/layout.tsx (a tabIndex=-1 div, because pages own their single <main> landmark and a second
 * <main> would nest landmarks).
 */
export function SkipToContent() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:border focus:border-border-light focus:bg-panel-light focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-brand-strong focus:shadow-ring-brand focus:outline-none dark:focus:border-white/10 dark:focus:bg-panel-dark dark:focus:text-brand-strong-dark dark:focus:shadow-ring-brand-dark"
    >
      Skip to main content
    </a>
  )
}

export function SiteHeader() {
  return isAuthRoute(usePathname()) ? null : (
    <>
      <SkipToContent />
      <Header />
    </>
  )
}

export function SiteFooter() {
  return isAuthRoute(usePathname()) ? null : <Footer />
}
