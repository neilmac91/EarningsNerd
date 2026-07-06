'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleNotchIcon, WarningCircleIcon, XIcon } from '@/lib/icons'
import { getCurrentUserSafe, resendVerification } from '@/features/auth/api/auth-api'
import { EMAIL_VERIFICATION_REQUIRED_EVENT } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'

/**
 * Global, graceful intercept of the backend's "verify your email" 403. The axios
 * interceptor dispatches EMAIL_VERIFICATION_REQUIRED_EVENT when an unverified user
 * hits a gated action (generate / checkout); this modal turns that into a friendly
 * resend prompt instead of a raw error toast.
 */
export default function EmailVerificationModal() {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [resent, setResent] = useState(false)
  const router = useRouter()
  const queryClient = useQueryClient()

  const { data: user } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
    staleTime: 60_000,
  })

  useEffect(() => {
    const handler = () => {
      setResent(false)
      setOpen(true)
    }
    window.addEventListener(EMAIL_VERIFICATION_REQUIRED_EVENT, handler)
    return () => window.removeEventListener(EMAIL_VERIFICATION_REQUIRED_EVENT, handler)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  if (!open) return null

  const handleResend = async () => {
    if (!user?.email || loading || resent) return
    setLoading(true)
    try {
      await resendVerification(user.email)
      setResent(true)
    } catch {
      // best-effort
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
    router.refresh()
    setOpen(false)
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="verify-modal-title"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border-light bg-panel-light p-6 shadow-e4 dark:shadow-none dark:border-border-dark dark:bg-panel-dark"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-warning-dark/15">
            <WarningCircleIcon className="h-5 w-5 text-warning-light dark:text-warning-dark" />
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close"
            className="rounded p-1 text-text-tertiary-light transition-colors hover:bg-black/5 dark:text-text-secondary-dark dark:hover:bg-white/5"
          >
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        <h2
          id="verify-modal-title"
          className="mt-4 text-lg font-semibold text-text-primary-light dark:text-text-primary-dark"
        >
          Verify your email to continue
        </h2>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          {resent ? (
            <>
              We sent a fresh link to{' '}
              <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
                {user?.email}
              </span>
              . Click it, then come back and refresh.
            </>
          ) : (
            <>
              Generating summaries and subscribing require a verified email. We sent a link to{' '}
              <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
                {user?.email}
              </span>
              .
            </>
          )}
        </p>

        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={handleResend}
            disabled={loading || resent}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-border-light bg-transparent px-4 py-2.5 text-sm font-medium text-text-primary-light transition hover:bg-black/5 disabled:opacity-50 dark:border-border-dark dark:text-text-primary-dark dark:hover:bg-white/5"
          >
            {loading && <CircleNotchIcon className="h-4 w-4 animate-spin" />}
            {resent ? 'Link sent' : 'Resend link'}
          </button>
          <button
            type="button"
            onClick={handleRefresh}
            className="flex-1 rounded-lg bg-brand text-white hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark px-4 py-2.5 text-sm font-semibold transition active:scale-[0.99]"
          >
            I&apos;ve verified — refresh
          </button>
        </div>
      </div>
    </div>
  )
}
