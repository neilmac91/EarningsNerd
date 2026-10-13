'use client'

import Link from 'next/link'
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GuidanceCard, buttonVariants } from '@/components/ui'
import analytics from '@/lib/analytics'
import { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'
import {
  loginHrefWithRedirect,
  registerHrefWithRedirect,
  stashPostAuthRedirect,
} from '@/lib/postAuthRedirect'
import type { Filing } from '@/features/filings/api/filings-api'
import { getRegistrationConfig } from '@/features/marketing/api/access-api'
import { ACCESS_COPY, resolveAccessMode } from '@/features/marketing/lib/access'
import { FREE_SUMMARY_LIMIT, TRIAL_DAYS } from '@/lib/planLimits'
import { queryKeys } from '@/lib/queryKeys'

/**
 * Shown in place of auto-generation when a signed-out visitor lands on a filing with NO cached
 * summary. Generation requires an account (the backend 401s anonymous callers); already-generated
 * summaries still render for everyone, so this gate only appears where a fresh AI run would start.
 * Log in and Create free account carry ?redirect= so the visitor lands back on this filing after
 * authenticating; the invite CTA goes to /waitlist without one, and the stashed redirect below covers it.
 *
 * The account CTA follows the one access decision (features/marketing/lib/access.ts), read from the
 * same registration payload the pricing page reads. Until it answers, and when it cannot, the gate
 * fails closed to the invite copy: in invite-only mode /register rejects a signup without an invite,
 * so "Create a free account" would promise what the API refuses.
 */
export function GenerateSignupGate({ filing, entryPoint }: { filing: Filing; entryPoint: string }) {
  // RAW path — the href builders encode exactly once (a pre-encoded value would double-encode and
  // the receiver would silently drop it to `/`; see postAuthRedirect).
  const redirectPath = `/filing/${filing.id}`
  const ticker = filing.company?.ticker ?? null

  useEffect(() => {
    // Belt-and-suspenders with the ?redirect= links below: the query thread dies when the
    // verification email opens a NEW tab, so stash the destination too — login consumes it as
    // the fallback and the converted user still lands back on this filing.
    stashPostAuthRedirect(redirectPath)
    analytics.signupGateShown({
      filingId: filing.id,
      ticker,
      filingType: filing.filing_type,
      entryPoint,
    })
  }, [filing.id, redirectPath, ticker, filing.filing_type, entryPoint])

  const { data: registration } = useQuery({
    queryKey: queryKeys.registrationConfig(),
    queryFn: getRegistrationConfig,
    retry: false,
    staleTime: 60 * 60 * 1000,
  })
  const isPublic = resolveAccessMode(registration ?? null) === 'public'
  const login = (
    <Link href={loginHrefWithRedirect(redirectPath)} className={buttonVariants({ variant: 'ghost' })}>
      Log in
    </Link>
  )

  if (!isPublic) {
    return (
      <GuidanceCard
        title="Summaries need an account"
        headingLevel="h2"
        description="EarningsNerd is in private beta. Request an invite, or log in if you have one."
        action={
          <>
            <Link href={ACCESS_COPY.invite.href} className={buttonVariants()}>
              {ACCESS_COPY.invite.cta}
            </Link>
            {login}
          </>
        }
      />
    )
  }

  return (
    <GuidanceCard
      title="Create a free account to analyze this filing"
      headingLevel="h2"
      description={
        <>
          Free accounts get {FREE_SUMMARY_LIMIT} AI summaries a month, no credit card required.
          {ENABLE_PRO_TRIAL && (
            <> Want unlimited? First-time Pro monthly subscribers get {TRIAL_DAYS} days free, cancel anytime.</>
          )}
        </>
      }
      action={
        <>
          <Link href={registerHrefWithRedirect(redirectPath)} className={buttonVariants()}>
            Create free account
          </Link>
          {login}
        </>
      }
    />
  )
}
