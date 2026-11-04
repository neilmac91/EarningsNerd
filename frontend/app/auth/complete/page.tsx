'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { Notice } from '@/components/ui'
import { completeOAuthSignIn, getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import AuthShell from '@/features/auth/components/AuthShell'
import { RetryButton } from '@/hooks/useRetainedFailure'
import { SessionLockUnavailable, SessionStillRenewing } from '@/lib/api/client'
import { getExplicitSessionGeneration } from '@/lib/api/session'
import { getErrorStatus } from '@/lib/api/types'
import { ENABLE_APPLE_SIGNIN } from '@/lib/featureFlags'
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
 * Why an exchange that was not refused did not finish, its code still unredeemed: another tab's session update held
 * the session cookies' lock past the exchange's wait (SessionStillRenewing), this browser cannot hold that lock at all
 * (SessionLockUnavailable), or the post got no answer it could use (a network error, a timeout, a 5xx).
 */
type Problem = 'renewing' | 'unavailable' | 'failed'

/** What the notice says for each problem. The browser's names the providers this build offers, as the login page's
 * buttons and its oauth_handoff_failed sentence do: a build without Sign in with Apple names Google alone. */
function noticeFor(problem: Problem): { title: string; description: string } {
  switch (problem) {
    case 'renewing':
      return {
        title: 'Another EarningsNerd tab is renewing its login',
        description: 'Your login can finish once it is done. Try again in a moment.',
      }
    case 'unavailable':
      return {
        title: `This browser couldn't finish the ${ENABLE_APPLE_SIGNIN ? 'Google or Apple' : 'Google'} login`,
        description:
          "It may be an older browser, or one that blocks this site's data. Log in again from an up-to-date browser that allows it.",
      }
    case 'failed':
      return { title: "We couldn't finish your login just now", description: 'Try again in a minute, or log in again.' }
  }
}

/** The auth pages' link (app/verify-email/page.tsx's "back to login"). */
const LINK =
  'rounded-sm font-medium text-brand-strong hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'
/** The notice that replaces the wait takes focus, so it can show the ring a keyboard user expects. */
const ANSWER = 'rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'

/**
 * The landing page of a Google or Apple login (E29 (5)) whose start asked for the handoff (oauthStartHref's
 * `handoff=1`, startOAuthWithInvite's `handoff: true`, as this app's starts do). The provider's callback answers with a
 * navigation, which cannot hold the session cookies' lock (lib/api/client.ts), so for such a start it sets no session
 * cookie: it sends the browser here with a one-time code in the URL fragment, which no request log records, and a
 * cookie that binds the code to this browser. On mount the page reads the code, takes it off the address bar at once (a
 * bookmark, a shared link or the history entry never keeps it), keeps it in this page's state alone, and exchanges it
 * (completeOAuthSignIn), which posts only inside the lock, so a refresh another tab sent with the previous account's
 * cookies answers first and cannot set those over the new session's. Then, as the login page does, it drops the
 * previous account's queries and reads the new identity, and goes to the home page; a missing or refused code goes to
 * the login page, which says so.
 *
 * An exchange that posted nothing (another tab's session update held the lock past its wait, or this browser cannot
 * hold the lock) or got no answer it could use leaves a notice in place of the wait, which takes focus, with Log in
 * again and, where another press can help, Try again, which posts the same kept code once more. A retry is safe: the
 * code is single use, so a code an earlier post redeemed is refused, and the page goes to the login page's sentence.
 * The route is an auth shell route (lib/authShellRoutes.ts), so no site header mounts here to read /me around the
 * exchange.
 *
 * A GET of a page that posts on mount, on purpose: the code is single use, lives two minutes and is redeemed only
 * from the browser that holds the binding cookie the callback set, so a link scanner or a preview fetch that loads
 * this URL has no fragment (it never leaves the browser) and no cookie, and posts nothing or is refused.
 */
export default function OAuthCompletePage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const started = useRef(false)
  // The fragment's code, read once on mount: the address bar no longer holds it when Try again posts it again.
  const code = useRef<string | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [retrying, setRetrying] = useState(false)
  const noticeRef = useRef<HTMLDivElement>(null)

  const exchange = useCallback(async (oneTimeCode: string) => {
    const explicitGeneration = getExplicitSessionGeneration()
    try {
      await completeOAuthSignIn(oneTimeCode)
      acceptLoginAndResetAccount(queryClient, explicitGeneration)
    } catch (error: unknown) {
      if (error instanceof SessionStillRenewing) setProblem('renewing')
      else if (error instanceof SessionLockUnavailable) setProblem('unavailable')
      // The code is used, expired, unbound or unknown: the login page says the login did not finish.
      else if (getErrorStatus(error) === 400) router.replace(HANDOFF_FAILED)
      else setProblem('failed')
      return
    }
    // The new account's identity before leaving, so the home page opens on it rather than on the reset's null; a
    // read that fails does not hold the login back.
    await queryClient
      .fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 })
      .catch(() => undefined)
    router.replace(LOGGED_IN)
  }, [router, queryClient])

  useEffect(() => {
    // Once per page: React's development double effect would find the fragment already cleared.
    if (started.current) return
    started.current = true
    code.current = codeFromFragment(window.location.hash)
    window.history.replaceState(null, '', window.location.pathname)
    if (!code.current) {
      router.replace(HANDOFF_FAILED)
      return
    }
    void exchange(code.current)
  }, [router, exchange])

  // The notice replaces the wait: focus goes to it, so a keyboard or screen reader user lands on what happened. Try
  // again keeps it in place, its button busy, and a Try again that leaves hands focus back to it (RetryButton).
  const shown = problem !== null
  useEffect(() => {
    if (shown) noticeRef.current?.focus({ preventScroll: true })
  }, [shown])

  // The same code again, the one the fragment held: never a fresh read of the address bar, which no longer holds it.
  const tryAgain = () => {
    if (!code.current) return
    setRetrying(true)
    void exchange(code.current).finally(() => setRetrying(false))
  }

  if (problem) {
    const notice = noticeFor(problem)
    return (
      <AuthShell>
        <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Login not finished</h1>
        <div ref={noticeRef} tabIndex={-1} className={`mt-6 ${ANSWER}`}>
          <Notice
            variant="error"
            title={notice.title}
            description={notice.description}
            // No Try again where this browser cannot hold the lock: another press would fail the same way.
            action={problem === 'unavailable' ? undefined : (
              <RetryButton
                size="sm"
                failures={[{ failed: true, error: problem, busy: retrying, retry: tryAgain }]}
                focusTarget={noticeRef}
              />
            )}
          />
        </div>
        <p className="mt-6 text-sm">
          <Link href="/login" className={LINK}>
            Log in again
          </Link>
        </p>
      </AuthShell>
    )
  }

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
