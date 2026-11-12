/**
 * The routes that render in AuthShell, the auth pages' own full-screen shell, so the marketing
 * header and footer are suppressed there (components/SiteChrome.tsx). React-free, so the e2e specs
 * read the same list the shell uses (tests/e2e/text-floors.spec.ts) instead of retyping it.
 */
export const AUTH_ROUTES: readonly string[] = [
  '/login',
  '/register',
  '/check-email',
  '/verify-email',
  '/forgot-password',
  '/reset-password',
  // The landing of a Google or Apple login, which exchanges its one-time code (E29 (5)): no site header, so no /me read
  // of the header's runs around the exchange.
  '/auth/complete',
]

export function isAuthRoute(pathname: string | null): boolean {
  if (!pathname) return false
  return AUTH_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`))
}
