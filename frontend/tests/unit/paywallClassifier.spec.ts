import { describe, expect, it } from 'vitest'
import { isPaywallStreamError } from '@/features/summaries/api/summaries-api'

/**
 * Pins the LOAD-BEARING non-overlap between two backend stream-error messages
 * (backend/app/services/summary_pipeline.py) and this client classifier:
 *
 *  - The FREE monthly-limit message ("…monthly limit of N summaries. Upgrade to Pro…") MUST
 *    classify as paywall — it drives the trial/upgrade card and the paywall analytics.
 *  - The PRO fair-use ceiling message from #618 ("We've temporarily paused…") MUST NOT — a
 *    fair-use-capped PRO user is already paying; showing them "start your free trial" would be
 *    an absurd (and billing-false) upsell. #618 chose its wording to avoid the classifier's
 *    substrings; this spec makes that choice enforceable so a future copy edit on either side
 *    can't silently break it (staff review, PR #619).
 */
describe('isPaywallStreamError vs backend stream-error copy', () => {
  it('classifies the Free monthly-limit message as paywall', () => {
    const freeLimitMessage =
      "You've reached your monthly limit of 5 summaries. Upgrade to Pro for unlimited summaries."
    expect(isPaywallStreamError(freeLimitMessage)).toBe(true)
  })

  it("does NOT classify the Pro fair-use ceiling message (#618) as paywall", () => {
    const proFairUseMessage =
      "We've temporarily paused new summary generation on your account due " +
      'to unusually high recent volume. Please try again later or contact support.'
    expect(isPaywallStreamError(proFairUseMessage)).toBe(false)
  })
})
