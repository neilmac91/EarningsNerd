'use client'

import { useRef, useState, type ReactNode } from 'react'
import { startOAuthWithInvite } from '@/features/auth/api/auth-api'
import { oauthStartHref } from '@/features/auth/lib/oauthStart'

/**
 * The clickable surface shared by the brand sign-in buttons. Without an invite it is a plain link
 * to the redirecting backend start (works without JS). With an invite it is a button: the token is
 * sent in the body of `POST /api/auth/<provider>/start` and the browser then follows the provider
 * URL the backend returns, so the raw single-use invite never appears in any request URL.
 */
export default function OAuthStartControl({
  apiBase,
  provider,
  invite,
  className,
  children,
}: {
  apiBase: string
  provider: 'google' | 'apple'
  invite?: string
  className: string
  children: ReactNode
}) {
  const [failed, setFailed] = useState(false)
  const inFlight = useRef(false)

  if (!invite) {
    return (
      <a href={oauthStartHref(apiBase, provider)} className={className}>
        {children}
      </a>
    )
  }

  const start = async () => {
    if (inFlight.current) return
    inFlight.current = true
    setFailed(false)
    try {
      const url = await startOAuthWithInvite(provider, invite)
      window.location.assign(url)
    } catch {
      setFailed(true)
      inFlight.current = false
    }
  }

  return (
    <div>
      <button type="button" onClick={start} className={className}>
        {children}
      </button>
      {failed && (
        <p role="status" className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Couldn&apos;t start sign-in. Please try again.
        </p>
      )}
    </div>
  )
}
