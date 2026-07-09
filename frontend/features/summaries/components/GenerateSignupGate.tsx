'use client'

import Link from 'next/link'
import { useEffect } from 'react'
import { GuidanceCard, buttonVariants } from '@/components/ui'
import { SparkleIcon } from '@/lib/icons'
import analytics from '@/lib/analytics'
import { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'
import { stashPostAuthRedirect } from '@/lib/postAuthRedirect'
import type { Filing } from '@/features/filings/api/filings-api'

/**
 * Shown in place of auto-generation when a signed-out visitor lands on a filing with NO cached
 * summary. Generation requires an account (the backend 401s anonymous callers); already-generated
 * summaries still render for everyone, so this gate only appears where a fresh AI run would start.
 * Both CTAs carry ?redirect= so the visitor lands back on this filing after authenticating.
 */
export function GenerateSignupGate({ filing, entryPoint }: { filing: Filing; entryPoint: string }) {
  const redirect = encodeURIComponent(`/filing/${filing.id}`)
  const ticker = filing.company?.ticker ?? null

  useEffect(() => {
    // Belt-and-suspenders with the ?redirect= links below: the query thread dies when the
    // verification email opens a NEW tab, so stash the destination too — login consumes it as
    // the fallback and the converted user still lands back on this filing.
    stashPostAuthRedirect(`/filing/${filing.id}`)
    analytics.signupGateShown({
      filingId: filing.id,
      ticker,
      filingType: filing.filing_type,
      entryPoint,
    })
  }, [filing.id, ticker, filing.filing_type, entryPoint])

  return (
    <GuidanceCard
      icon={<SparkleIcon className="h-5 w-5" aria-hidden="true" />}
      title="Create a free account to analyze this filing"
      description={
        <>
          Free accounts get 5 AI summaries a month, no credit card required.
          {ENABLE_PRO_TRIAL && (
            <> Want unlimited? First-time Pro monthly subscribers get 7 days free, cancel anytime.</>
          )}
        </>
      }
      action={
        <>
          <Link href={`/register?redirect=${redirect}`} className={buttonVariants()}>
            Create free account
          </Link>
          <Link href={`/login?redirect=${redirect}`} className={buttonVariants({ variant: 'ghost' })}>
            Log in
          </Link>
        </>
      }
    />
  )
}
