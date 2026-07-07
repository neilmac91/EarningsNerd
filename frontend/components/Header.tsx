'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRightIcon, ListIcon, SignOutIcon, XIcon } from '@/lib/icons'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import UserMenu from '@/features/auth/components/UserMenu'
import NotificationBell from '@/features/notifications/components/NotificationBell'
import { ThemeToggle } from '@/components/ThemeToggle'
import { getCurrentUserSafe, logout } from '@/features/auth/api/auth-api'
import { ENABLE_ANALYSIS, ENABLE_CALENDAR } from '@/lib/featureFlags'
import { buttonVariants, Skeleton } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'

const NAV_LINKS = [
  { href: '/search', label: 'Search' },
  // Flag-gated: the /analysis and /calendar routes 404 while their flags are off, so the nav
  // entries appear only when the features go live.
  ...(ENABLE_ANALYSIS ? [{ href: '/analysis', label: 'Analysis' }] : []),
  ...(ENABLE_CALENDAR ? [{ href: '/calendar', label: 'Calendar' }] : []),
  { href: '/pricing', label: 'Pricing' },
  { href: '/contact', label: 'Contact' },
]

const MOBILE_USER_LINKS = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/dashboard/watchlist', label: 'Watchlist' },
  ...(ENABLE_CALENDAR ? [{ href: '/calendar', label: 'Calendar' }] : []),
  { href: '/dashboard/settings', label: 'Settings' },
]

export default function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const router = useRouter()
  const queryClient = useQueryClient()

  // `user` is tri-state: a user object (logged in), `null` (definitive 401 → logged out), or
  // `undefined` (still resolving, or errored with no data). getCurrentUserSafe returns `null`
  // for a 401 rather than throwing, so a "not logged in" answer never triggers a retry.
  // `isError` is the safety net: once the check has *settled* into an error (non-401 failure,
  // all retries exhausted) we degrade to the logged-out CTAs rather than trapping the user on a
  // dead placeholder circle. See the fallback branches below.
  const { data: user, isError } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    // Retry only real failures (cold-start timeouts, network blips, 5xx) — these throw. A 401
    // resolves to `null` and is left alone, so guests still settle in a single request.
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
    staleTime: 60_000,
    // The global default disables focus refetch; re-enable it here so a stranded auth check
    // recovers when the user returns to the tab, without needing a full page reload. staleTime
    // keeps this cheap (no refetch within 60s of the last success).
    refetchOnWindowFocus: true,
  })

  const handleMobileLogout = async () => {
    setMobileMenuOpen(false)
    try {
      await logout()
    } catch {
      // ignore — clear local state regardless
    }
    queryClient.setQueryData(queryKeys.currentUser(), null)
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
    router.push('/')
    router.refresh()
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border-light bg-background-light/80 backdrop-blur-xl dark:border-white/[0.06] dark:bg-background-dark/80">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Left: Logo */}
        <div className="flex items-center">
          <Link href="/" className="flex items-center gap-2.5">
            <EarningsNerdLogo variant="icon-only" iconClassName="h-10 w-10" mode="auto" />
            <span className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              Earnings<em className="italic text-brand-strong dark:text-brand-strong-dark">Nerd</em>
            </span>
          </Link>
        </div>

        {/* Center: Nav links (desktop) */}
        <nav className="hidden items-center gap-8 md:flex" aria-label="Main navigation">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-text-secondary-light transition-colors hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Right: CTAs / user menu (desktop) */}
        <div className="hidden items-center gap-3 md:flex">
          <ThemeToggle />
          {user ? (
            <>
              <NotificationBell />
              <UserMenu user={user} />
            </>
          ) : user === null || isError ? (
            <>
              <Link href="/login" className={buttonVariants({ variant: 'ghost', size: 'md' })}>
                Log In
              </Link>
              <Link href="/register" className={buttonVariants({ variant: 'primary', size: 'md' })}>
                Get Started
                <ArrowRightIcon className="h-3.5 w-3.5" />
              </Link>
            </>
          ) : (
            // Auth still resolving (pending, including retry backoff): hold the skeleton so a
            // slow/cold backend never flashes the "Log In" CTAs to a user who is actually signed
            // in. Once the query *settles* — `null` (logged out) or `isError` (gave up) — one of
            // the branches above renders, so the user is never trapped on this placeholder.
            <Skeleton className="h-9 w-9 rounded-full" />
          )}
        </div>

        {/* Mobile actions */}
        <div className="flex items-center gap-1 md:hidden">
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="inline-flex items-center justify-center rounded-lg p-2 text-text-tertiary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <XIcon className="h-5 w-5" /> : <ListIcon className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="border-t border-border-light bg-background-light dark:border-white/[0.06] dark:bg-background-dark md:hidden">
          <nav className="mx-auto max-w-7xl space-y-1 px-4 pb-4 pt-2" aria-label="Mobile navigation">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm font-medium text-text-secondary-light transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
              >
                {link.label}
              </Link>
            ))}
            <div className="mt-3 flex flex-col gap-2 border-t border-border-light pt-3 dark:border-white/[0.06]">
              {user ? (
                <>
                  <div className="px-3 pb-1">
                    <p className="truncate text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                      {user.full_name || 'Your account'}
                    </p>
                    <p className="truncate text-xs text-text-tertiary-light dark:text-text-secondary-dark">{user.email}</p>
                  </div>
                  {user.email_verified === false && (
                    <Link
                      href={`/check-email?email=${encodeURIComponent(user.email)}`}
                      onClick={() => setMobileMenuOpen(false)}
                      className="block rounded-lg bg-warning-light/10 px-3 py-2.5 text-sm font-medium text-warning-light transition-colors hover:bg-warning-light/20 dark:bg-warning-dark/10 dark:text-warning-dark dark:hover:bg-warning-dark/20"
                    >
                      Verify your email
                    </Link>
                  )}
                  {MOBILE_USER_LINKS.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className="block rounded-lg px-3 py-2.5 text-sm font-medium text-text-secondary-light transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
                    >
                      {link.label}
                    </Link>
                  ))}
                  <button
                    type="button"
                    onClick={handleMobileLogout}
                    className="flex items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-text-secondary-light transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
                  >
                    <SignOutIcon className="h-4 w-4 text-text-tertiary-light dark:text-text-secondary-dark" />
                    Log out
                  </button>
                </>
              ) : user === null || isError ? (
                <>
                  <Link
                    href="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-lg px-3 py-2.5 text-center text-sm font-medium text-text-secondary-light transition-colors hover:bg-brand-weak hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
                  >
                    Log In
                  </Link>
                  <Link
                    href="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-lg bg-brand px-3 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark"
                  >
                    Get Started
                  </Link>
                </>
              ) : (
                // Auth still resolving (pending): show a skeleton bar rather than leaving the
                // bordered container empty (a stray divider + gap), matching the desktop header's
                // loading state. A settled error falls through to the Log In / Get Started links
                // above (via `isError`), so the mobile menu is never stuck on this placeholder.
                <Skeleton className="h-9 w-full rounded-lg" />
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  )
}
