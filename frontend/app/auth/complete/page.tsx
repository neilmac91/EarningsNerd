'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { completeOAuthSignIn, getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import AuthShell from '@/features/auth/components/AuthShell'
import { getExplicitSessionGeneration } from '@/lib/api/session'
import { CircleNotchIcon } from '@/lib/icons'
import { queryKeys } from '@/lib/queryKeys'

/** Where a login goes once the exchange took: the home page, where the callback's redirect used to land it. */
const LOGGED_IN = '/'
/** Where it goes when the code is missing or refused: the login page, which says why (OAUTH_ERROR_MESSAGES). */
const HANDOFF_FAILED = '/login?error=oauth_handoff_failed'

/** The one-time code a Google or Apple callback put in this page's URL fragment, or null. */
function codeFromFragment(hash: string): string | null {
  return new URLSearchParams(hash.replace(/^#/, '')).get('code') || null
}

/**
 * The landing page of a Google or Apple login (E29 (5)). The provider's callback answers with a navigation, which
 * cannot hold the session cookies' lock (lib/api/client.ts), so it sets no session cookie: it sends the browser here
 * with a one-time code in the URL fragment, which no request log records, and a cookie that binds the code to this
 * browser. On mount the page reads the code, takes it off the address bar at once (a bookmark, a shared link or the
 * history entry never keeps it), and exchanges it (completeOAuthSignIn), posting under the lock as a password login
 * does, so a refresh another tab sent with the previous account's cookies answers first and cannot set those over the
 * new session's. Then, as the login page does, it drops the previous account's queries and reads the new identity,
 * and goes to the home page; a missing or refused code goes to the login page, which says so. The route is an auth
 * shell route (lib/authShellRoutes.ts), so no site header mounts here to read /me around the exchange.
 *
 * A GET of a page that posts on mount, on purpose: the code is single use, lives two minutes and is redeemed only
 * from the browser that holds the binding cookie the callback set, so a link scanner or a preview fetch that loads
 * this URL has no fragment (it never leaves the browser) and no cookie, and posts nothing or is refused.
 */
export default function OAuthCompletePage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const started = useRef(false)

  useEffect(() => {
    // Once per page: React's development double effect would find the fragment already cleared.
    if (started.current) return
    started.current = true
    const code = codeFromFragment(window.location.hash)
    window.history.replaceState(null, '', window.location.pathname)
    if (!code) {
      router.replace(HANDOFF_FAILED)
      return
    }
    const explicitGeneration = getExplicitSessionGeneration()
    void (async () => {
      try {
        await completeOAuthSignIn(code)
        acceptLoginAndResetAccount(queryClient, explicitGeneration)
      } catch {
        router.replace(HANDOFF_FAILED)
        return
      }
      // The new account's identity before leaving, so the home page opens on it rather than on the reset's null; a
      // read that fails does not hold the login back.
      await queryClient
        .fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 })
        .catch(() => undefined)
      router.replace(LOGGED_IN)
    })()
  }, [router, queryClient])

  return (
    <AuthShell>
      <div role="status" className="text-center">
        <CircleNotchIcon
          aria-hidden="true"
          className="mx-auto mb-4 h-10 w-10 animate-spin motion-reduce:animate-none text-brand-strong dark:text-brand-strong-dark"
        />
        <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          Logging you in…
        </h1>
        <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Finishing your login, then taking you to the home page.
        </p>
      </div>
    </AuthShell>
  )
}
