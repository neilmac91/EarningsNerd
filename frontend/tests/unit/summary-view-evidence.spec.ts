import { beforeEach, describe, expect, it, vi } from 'vitest'
import posthog from 'posthog-js'
import { getCookiePreferences } from '@/components/CookieConsent'
import { analytics, type SummaryViewIdentity } from '@/lib/analytics'

vi.mock('posthog-js', () => ({ default: { capture: vi.fn() } }))
vi.mock('@sentry/nextjs', () => ({ setUser: vi.fn() }))
vi.mock('@/components/CookieConsent', () => ({ getCookiePreferences: vi.fn() }))

const identity: SummaryViewIdentity = { state: 'authenticated', accountId: '7' }
const view = { identity, summaryId: 91, filingId: 42, ticker: 'TST', filingType: '10-K', entryPoint: 'direct' }

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getCookiePreferences).mockReturnValue({ essential: true, analytics: true, sessionRecording: false, timestamp: '2026-09-28T00:00:00Z' })
})

describe('summary view evidence', () => {
  it.each<SummaryViewIdentity>([identity, { state: 'anonymous', accountId: null }, { state: 'unknown', accountId: null }])('retains event identity independently of person traits: $state', (snapshot) => {
    analytics.summaryViewed({ ...view, identity: snapshot })
    expect(posthog.capture).toHaveBeenCalledWith('summary_viewed', expect.objectContaining({
      evidence_version: 1, auth_state_at_event: snapshot.state, account_id_at_event: snapshot.accountId,
      analytics_consent_at_event: true, summary_id: 91, filing_id: 42,
    }))
  })

  it.each([null, false])('does not send or queue a view without affirmative consent: %s', (consent) => {
    vi.mocked(getCookiePreferences).mockReturnValue(consent === null ? null : { essential: true, analytics: false, sessionRecording: false, timestamp: '2026-09-28T00:00:00Z' })
    analytics.summaryViewed(view)
    expect(posthog.capture).not.toHaveBeenCalled()
  })
})
