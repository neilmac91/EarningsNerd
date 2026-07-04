'use client'

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { CircleNotchIcon, WarningCircleIcon, XIcon } from '@/lib/icons'
import { getCurrentUserSafe, resendVerification } from '@/features/auth/api/auth-api'
import { isAuthRoute } from '@/components/SiteChrome'

const DISMISS_KEY = 'verifyBannerDismissed'

/**
 * Slim, session-dismissible banner shown to logged-in users who haven't verified
 * their email yet (email_verified gates AI generation + checkout on the backend).
 */
export default function VerificationBanner() {
  const pathname = usePathname()
  const { data: user } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
    staleTime: 60_000,
  })

  const [dismissed, setDismissed] = useState(true) // start hidden to avoid SSR flash
  const [loading, setLoading] = useState(false)
  const [resent, setResent] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time sessionStorage read; effect is the SSR-safe way to hydrate the dismissed flag
    setDismissed(sessionStorage.getItem(DISMISS_KEY) === '1')
  }, [])

  if (!user || user.email_verified !== false) return null
  if (dismissed || isAuthRoute(pathname)) return null

  const handleResend = async () => {
    if (loading || resent) return
    setLoading(true)
    try {
      await resendVerification(user.email)
      setResent(true)
    } catch {
      // best-effort; keep the banner quiet on failure
    } finally {
      setLoading(false)
    }
  }

  const handleDismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, '1')
    setDismissed(true)
  }

  return (
    <div className="border-b border-warning-light/30 bg-warning-light/10 text-warning-light dark:border-warning-dark/20 dark:bg-warning-dark/10 dark:text-warning-dark">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2.5 text-sm sm:px-6 lg:px-8">
        <WarningCircleIcon className="h-4 w-4 shrink-0" />
        <p className="flex-1">
          {resent ? (
            <>Verification email sent — check your inbox.</>
          ) : (
            <>Verify your email to generate summaries and subscribe.</>
          )}
        </p>
        {!resent && (
          <button
            type="button"
            onClick={handleResend}
            disabled={loading}
            className="inline-flex shrink-0 items-center gap-1.5 font-semibold underline-offset-2 hover:underline disabled:opacity-50"
          >
            {loading && <CircleNotchIcon className="h-3.5 w-3.5 animate-spin" />}
            Resend link
          </button>
        )}
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Dismiss"
          className="shrink-0 rounded p-1 transition-colors hover:bg-warning-dark/15"
        >
          <XIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
