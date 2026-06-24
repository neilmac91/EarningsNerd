'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { clsx } from 'clsx'
import { useQuery } from '@tanstack/react-query'
import { ChatTextIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { ShimmeringLoader } from '@/components/ShimmeringLoader'

const ADMIN_NAV = [
  { href: '/admin/invites', label: 'Invites', icon: EnvelopeSimpleIcon },
  { href: '/admin/feedback', label: 'Feedback', icon: ChatTextIcon },
] as const

function AdminSubNav() {
  const pathname = usePathname()
  return (
    <nav
      aria-label="Admin sections"
      className="border-b border-border-light bg-panel-light dark:border-white/10 dark:bg-panel-dark"
    >
      <div className="mx-auto flex max-w-7xl items-center gap-1 px-4 sm:px-6 lg:px-8">
        {ADMIN_NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`)
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? 'page' : undefined}
              className={clsx(
                'inline-flex items-center gap-1.5 border-b-2 px-3 py-3 text-sm font-medium transition-colors',
                active
                  ? 'border-brand-strong text-text-primary-light dark:border-brand-strong-dark dark:text-text-primary-dark'
                  : 'border-transparent text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark',
              )}
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
 * /dashboard. Real enforcement still lives on the backend (_require_admin); this is a UX
 * guard so non-admins never see a flash of admin chrome.
 */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()

  const { data: user, isLoading } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
    staleTime: 60_000,
  })

  const isAdmin = Boolean(user?.is_admin)

  useEffect(() => {
    if (isLoading) return
    if (!user) {
      router.replace('/login')
    } else if (!isAdmin) {
      router.replace('/dashboard')
    }
  }, [isLoading, user, isAdmin, router])

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <ShimmeringLoader className="h-8 w-48" />
        <div className="mt-6 space-y-3">
          <ShimmeringLoader className="h-40 w-full" />
          <ShimmeringLoader className="h-64 w-full" />
        </div>
      </div>
    )
  }

  // While the redirect effect runs, render nothing rather than flashing admin content.
  if (!user || !isAdmin) {
    return null
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <AdminSubNav />
      {children}
    </div>
  )
}
