import { describe, expect, it } from 'vitest'
import { isPaywallStreamError } from '@/features/summaries/api/summaries-api'

/**
 * Pins the LOAD-BEARING non-overlap between two backend stream-error messages
 * (backend/app/services/summary_stages/admission.py) and this client classifier, read by their words, as a page
 * reads a message that carries no code (a known code decides first since E31):
 *
 *  - The FREE monthly-limit message ("You've used this month's N free summaries. Upgrade to Pro…") MUST
 *    classify as paywall: it drives the trial/upgrade card and the paywall analytics.
 *  - The PRO fair-use ceiling message ("Your account has reached this month's limit for generating summaries…",
 *    the page's words since E37) MUST NOT: a fair-use-capped PRO user is already paying; showing them "start your
 *    free trial" would be an absurd (and billing-false) upsell. So must its words before E37 ("We've temporarily
 *    paused…", #618), which a server before E37 streams uncoded from a durable job while a deploy rolls out. This
 *    spec makes the choice enforceable so a future copy edit on either side can't silently break it (staff review,
 *    PR #619).
 */
describe('isPaywallStreamError vs backend stream-error copy', () => {
  it('classifies the Free monthly-limit message as paywall', () => {
    const freeLimitMessage =
      "You've used this month's 5 free summaries. Upgrade to Pro for unlimited summaries."
    expect(isPaywallStreamError(freeLimitMessage)).toBe(true)
  })

  it('does NOT classify the Pro fair-use ceiling message as paywall, in its words or its words before E37', () => {
    const proFairUseMessage =
      "Your account has reached this month's limit for generating summaries, regenerations included. " +
      'It resets next month. Contact support with any questions.'
    expect(isPaywallStreamError(proFairUseMessage)).toBe(false)
    const beforeE37 =
      "We've temporarily paused new summary generation on your account due " +
      'to unusually high recent volume. Please try again later or contact support.'
    expect(isPaywallStreamError(beforeE37)).toBe(false)
  })
})
