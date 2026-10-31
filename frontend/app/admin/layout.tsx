'use client'

import { useEffect, useRef, type RefObject } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { ChatTextIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { isConfirmedGuest } from '@/features/auth/lib/confirmedGuest'
import AccountLoadFailure from '@/features/auth/components/AccountLoadFailure'
import { Skeleton } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'
import { useRetainedFailure } from '@/hooks/useRetainedFailure'

const ADMIN_NAV = [
  { href: '/admin/invites', label: 'Invites', icon: EnvelopeSimpleIcon },
  { href: '/admin/feedback', label: 'Feedback', icon: ChatTextIcon },
] as const

/** `navRef` makes the nav a focus target (`tabIndex={-1}`, out of the Tab order): where the account card's Try again
    hands focus when the admin section replaces it. */
function AdminSubNav({ navRef }: { navRef: RefObject<HTMLElement> }) {
  const pathname = usePathname()
  return (
    <nav
      ref={navRef}
      tabIndex={-1}
      aria-label="Admin sections"
      className="border-b border-border-light bg-panel-light outline-none dark:border-white/10 dark:bg-panel-dark"
    >
      {/* flex-wrap: at 200% text the two tabs are wider than a phone, and an unwrapped row took the page to 443px. */}
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-1 px-4 sm:px-6 lg:px-8">
        {ADMIN_NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`)
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? 'page' : undefined}
              className={`inline-flex items-center gap-1.5 rounded-t-lg border-b-2 px-3 py-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${
                active
                  ? 'border-brand-strong text-text-primary-light dark:border-brand-strong-dark dark:text-text-primary-dark'
                  : 'border-transparent text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-white'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}

/**
 * Admin section gate. Mirrors the dashboard's redirect-if-not-logged-in pattern but adds an
 * is_admin check on top: anonymous visitors go to /login, signed-in non-admins go to
 * /dashboard, and a reader whose account could not be read gets the dashboard's account card.
 * Real enforcement still lives on the backend (_require_admin); this is a UX guard so
 * non-admins never see a flash of admin chrome.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()

  const userQuery = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
    staleTime: 60_000,
  })
  // isPending, not isLoading, as the dashboard reads it: a first load paused offline is still loading, not a blank page.
  const { data: user, isPending } = userQuery
  // A failed read keeps the account card, and a focused Try again in it, mounted through the refetch until data
  // replaces it.
  const userFailure = useRetainedFailure(userQuery, queryKeys.currentUser())
  const navRef = useRef<HTMLElement>(null)

  const isAdmin = Boolean(user?.is_admin)
  // Only a confirmed guest leaves for /login: never a null still being read, or a read that failed.
  const guest = isConfirmedGuest(userQuery)

  useEffect(() => {
    if (guest) {
      router.replace('/login')
    } else if (user && !isAdmin) {
      router.replace('/dashboard')
    }
  }, [guest, user, isAdmin, router])

  if (isPending && !userFailure.failed) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div role="status" aria-label="Loading admin">
          <Skeleton className="h-8 w-48" />
          <div className="mt-6 space-y-3">
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
          <span className="sr-only">Loading…</span>
        </div>
      </div>
    )
  }

  // The account could not be read (offline, a 5xx) and there is no user to check: neither a guest to send to /login nor
  // an admin. A refetch that fails with the user in hand keeps the section.
  if (userFailure.failed && !user) {
    return <AccountLoadFailure failure={userFailure} focusTarget={navRef} title="Unable to load the admin section" />
  }

  // While the redirect effect runs, render nothing rather than flashing admin content.
  if (!user || !isAdmin) {
    return null
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <AdminSubNav navRef={navRef} />
      {children}
    </div>
  )
}
