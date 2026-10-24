'use client'

import { useRef, useState, type ReactNode } from 'react'
import { startOAuthWithInvite } from '@/features/auth/api/auth-api'
import { oauthStartHref } from '@/features/auth/lib/oauthStart'
import { cx } from '@/components/ui'
import type { AccountAgreement } from '@/features/legal/api/legal-api'

export interface OAuthSignup {
  ready: boolean
  prepare: () => Promise<AccountAgreement | null>
}

/** The provider as the buttons name it ("Continue with Google"), so a failed start says what did not continue. */
const PROVIDER_NAME = { google: 'Google', apple: 'Apple' } as const

/**
 * The clickable surface shared by the brand sign-in buttons. Without an invite it is a plain link
 * to the redirecting backend start (works without JS). With an invite it is a button: the token is
 * sent in the body of `POST /api/auth/<provider>/start` and the browser then follows the provider
 * URL the backend returns, so the raw single-use invite never appears in any request URL.
 * The control owns the brand focus ring, so both shapes carry it whatever the caller passes.
 */
export default function OAuthStartControl({
  apiBase,
  provider,
  invite,
  signup,
  className,
  children,
}: {
  apiBase: string
  provider: 'google' | 'apple'
  invite?: string
  signup?: OAuthSignup
  className: string
  children: ReactNode
}) {
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)

  if (!invite && !signup) {
    return (
      <a href={oauthStartHref(apiBase, provider)} className={cx('focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark', className)}>
        {children}
      </a>
    )
  }

  const start = async () => {
    if (inFlight.current || (signup && !signup.ready)) return
    inFlight.current = true
    setBusy(true)
    setFailed(false)
    try {
      const agreement = signup ? await signup.prepare() : undefined
      if (signup && !agreement) return
      const url = await startOAuthWithInvite(provider, invite, agreement ?? undefined)
      window.location.assign(url)
    } catch {
      setFailed(true)
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }

  return (
    <div>
      <button type="button" onClick={start} aria-disabled={busy || (signup && !signup.ready) || undefined} aria-busy={busy || undefined} className={cx('focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark', className)}>
        {children}
      </button>
      {failed && (
        <p role="status" className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Couldn&apos;t continue with {PROVIDER_NAME[provider]}. Please try again.
        </p>
      )}
    </div>
  )
}
