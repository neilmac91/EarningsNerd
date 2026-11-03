import { describe, expect, it, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@/lib/api/client', async (original) => ({
  ...(await original<typeof import('@/lib/api/client')>()),
  default: { get: mocks.get },
}))

import { getInviteReadiness } from '@/features/admin/api/admin-api'
import {
  COLLECTION_REASONS,
  INVITATION_EMAIL_REASONS,
  INVITED_COHORT_REASONS,
  UNKNOWN_REASON,
  UNKNOWN_REASON_TOO,
  heldCapabilities,
  inviteAvailability,
  reasonSentences,
} from '@/features/admin/lib/inviteReadiness'
import { COHORT_EXCEPTION_HELD, COHORT_ONLY, COLLECTION_HELD, EMAIL_HELD, READY } from './fixtures/inviteReadiness'

/**
 * What the admin invites page may offer comes from GET /api/admin/invites/readiness, read so it fails closed: no
 * answer turns both capabilities off, invitation email is never on while collection is off, and a malformed answer is
 * a failed read. Each reason code becomes a sentence that names what holds it and who or what clears it, registration
 * held reads apart from invitation email held, and a code the page does not know still says something holds it.
 */

describe('availability fails closed', () => {
  it('turns both off with no answer, and invitation email off while collection is', () => {
    expect(inviteAvailability(undefined)).toEqual({ links: false, email: false, cohortOnly: false })
    expect(inviteAvailability(READY)).toEqual({ links: true, email: true, cohortOnly: false })
    expect(inviteAvailability(EMAIL_HELD)).toEqual({ links: true, email: false, cohortOnly: false })
    expect(inviteAvailability(COLLECTION_HELD)).toEqual({ links: false, email: false, cohortOnly: false })
    // An answer that says email is on while links are off is still read as both off.
    const inconsistent = {
      collection: { available: false, reasons: [] }, invited_cohort: COHORT_EXCEPTION_HELD,
      invitation_email: { available: true, reasons: [] },
    }
    expect(inviteAvailability(inconsistent)).toEqual({ links: false, email: false, cohortOnly: false })
  })

  it('opens links for the invited cohort alone while collection is held, and never says cohort-only beside it', () => {
    expect(inviteAvailability(COHORT_ONLY)).toEqual({ links: true, email: false, cohortOnly: true })
    expect(inviteAvailability({ ...COHORT_ONLY, invitation_email: { available: true, reasons: [] } }))
      .toEqual({ links: true, email: true, cohortOnly: true })
    // With collection open the exception narrows nothing: every link the general path takes.
    expect(inviteAvailability({ ...READY, invited_cohort: { available: true, reasons: [] } }))
      .toEqual({ links: true, email: true, cohortOnly: false })
  })
})

describe('the readiness read', () => {
  beforeEach(() => mocks.get.mockReset())

  it('reads the admin route through the shared client, with cancellation', async () => {
    mocks.get.mockResolvedValue({ data: EMAIL_HELD })
    const signal = new AbortController().signal
    await expect(getInviteReadiness(signal)).resolves.toEqual(EMAIL_HELD)
    expect(mocks.get).toHaveBeenCalledWith('/api/admin/invites/readiness', { signal })
  })

  it.each([
    ['no body', null],
    ['no invitation_email', { collection: READY.collection, invited_cohort: READY.invited_cohort }],
    ['a string flag', { ...READY, collection: { available: 'true', reasons: [] } }],
    ['no reasons', { ...READY, invitation_email: { available: false } }],
    ['a reason that is not a code', { ...READY, invitation_email: { available: false, reasons: [{ code: 'x' }] } }],
    ['a string flag on the exception', { ...READY, invited_cohort: { available: 'true', reasons: [] } }],
    ['a null exception', { ...READY, invited_cohort: null }],
  ])('refuses %s, so the page treats the read as failed', async (_name, body) => {
    mocks.get.mockResolvedValue({ data: body })
    await expect(getInviteReadiness()).rejects.toThrow('Availability could not be checked.')
  })

  it('reads an answer from before the exception as the exception held, and changes nothing else', async () => {
    mocks.get.mockResolvedValue({ data: { collection: READY.collection, invitation_email: READY.invitation_email } })
    await expect(getInviteReadiness()).resolves.toEqual({ ...READY, invited_cohort: { available: false, reasons: [] } })
  })

  it('keeps the exception\'s answer as the server gives it', async () => {
    mocks.get.mockResolvedValue({ data: COHORT_ONLY })
    await expect(getInviteReadiness()).resolves.toEqual(COHORT_ONLY)
  })
})

describe('each reason says what holds it and who or what clears it', () => {
  it('names the operator setting behind each collection code', () => {
    expect(reasonSentences(['collection_disabled'], COLLECTION_REASONS)[0]).toMatch(/\(LEGAL_COLLECTION_ENABLED is off\)\. The operator turns it on/)
    expect(reasonSentences(['operator_unpublished'], COLLECTION_REASONS)[0]).toMatch(/\(LEGAL_OPERATOR_PUBLISHED is off\)\. The operator publishes them/)
    expect(reasonSentences(['operator_incomplete'], COLLECTION_REASONS)[0]).toMatch(/missing or invalid\. The operator completes the LEGAL_OPERATOR settings/)
  })

  it('names what holds invitation email, the founder\'s approval and the provider\'s two settings included', () => {
    expect(reasonSentences(['collection_unavailable'], INVITATION_EMAIL_REASONS)).toEqual(['It waits for registration to open.'])
    expect(reasonSentences(['invitation_email_disabled'], INVITATION_EMAIL_REASONS)[0]).toMatch(
      /LEGAL_INVITATION_EMAIL_ENABLED is off\)\. It goes on once the founder approves the permission policy and a test send\./,
    )
    expect(reasonSentences(['provider_unconfigured'], INVITATION_EMAIL_REASONS)[0]).toMatch(/RESEND_API_KEY is empty/)
    expect(reasonSentences(['provider_feedback_unverified'], INVITATION_EMAIL_REASONS)[0]).toMatch(
      /Bounces and spam reports can't be recorded \(RESEND_WEBHOOK_SECRET is missing or invalid\)/,
    )
  })

  it('names the setting behind each invited-cohort code', () => {
    expect(reasonSentences(['registration_not_invite_only'], INVITED_COHORT_REASONS)[0]).toMatch(/REGISTRATION_MODE is public/)
    expect(reasonSentences(['invited_cohort_disabled'], INVITED_COHORT_REASONS)[0]).toMatch(/LEGAL_INVITED_COHORT_ENABLED is off/)
    expect(reasonSentences(['invited_cohort_unset'], INVITED_COHORT_REASONS)[0]).toMatch(
      /LEGAL_INVITED_COHORT is empty, or has spaces at either end, a control character or more than 64 characters/,
    )
  })

  it('keeps the server\'s order, says a code it does not know once, and says something holds it when none is named', () => {
    expect(reasonSentences(['collection_disabled', 'new_code', 'operator_unpublished', 'other_code'], COLLECTION_REASONS)).toEqual([
      COLLECTION_REASONS.collection_disabled,
      COLLECTION_REASONS.operator_unpublished,
      UNKNOWN_REASON_TOO,
    ])
    expect(reasonSentences(['new_code'], COLLECTION_REASONS)).toEqual([UNKNOWN_REASON])
    expect(reasonSentences([], COLLECTION_REASONS)).toEqual([UNKNOWN_REASON])
    expect(reasonSentences(['constructor'], COLLECTION_REASONS)).toEqual([UNKNOWN_REASON])
  })
})

describe('the banner tells registration held apart from invitation email held', () => {
  it('holds nothing when both are available', () => {
    expect(heldCapabilities(READY)).toEqual([])
  })

  it('with only invitation email held, says links can still go out by hand', () => {
    const held = heldCapabilities(EMAIL_HELD)
    expect(held.map((h) => h.title)).toEqual(['Invitation email is on hold'])
    expect(held[0].description).toBe(
      `${INVITATION_EMAIL_REASONS.invitation_email_disabled} You can still create invite links with Email invites off and share them yourself.`,
    )
  })

  it('with registration held, says what holds it, that links and Resend wait, and that invitation email waits for it', () => {
    const held = heldCapabilities(COLLECTION_HELD)
    expect(held.map((h) => h.title)).toEqual(['Registration is on hold', 'Invitation email is on hold'])
    expect(held[0].description).toBe(
      `${COLLECTION_REASONS.collection_disabled} ${COLLECTION_REASONS.operator_unpublished} Until registration opens, you can't create invite links or resend one. The list and Revoke still work.`,
    )
    expect(held[1].description).toBe(
      `${INVITATION_EMAIL_REASONS.collection_unavailable} ${INVITATION_EMAIL_REASONS.invitation_email_disabled}`,
    )
    expect(held[1].description).not.toMatch(/share them yourself/)
  })

  it('names registration as what holds invitation email even when the answer leaves it out', () => {
    const held = heldCapabilities({
      collection: { available: false, reasons: ['operator_incomplete'] }, invited_cohort: COHORT_EXCEPTION_HELD,
      invitation_email: { available: false, reasons: [] },
    })
    expect(held[1].description).toBe(INVITATION_EMAIL_REASONS.collection_unavailable)
  })

  it('with only the invited cohort open, says registration is open to it alone and what a link needs', () => {
    const held = heldCapabilities(COHORT_ONLY)
    expect(held.map((h) => h.key)).toEqual(['collection', 'invitation_email'])
    expect(held[0].title).toBe('Registration is open to the invited cohort only')
    expect(held[0].description).toBe(
      `${COLLECTION_REASONS.collection_disabled} ${COLLECTION_REASONS.operator_unpublished} Until registration opens, a new invite link must be bound to an address and carry the cohort set in LEGAL_INVITED_COHORT, exactly, and only such a link can be resent. The list and Revoke still work.`,
    )
    // Links are open, so invitation email waits only for its own conditions, and links can still go out by hand.
    expect(held[1].description).toBe(
      `${INVITATION_EMAIL_REASONS.invitation_email_disabled} You can still create invite links with Email invites off and share them yourself.`,
    )
  })

  it('names an exception switched on but held, and stays quiet about one switched off', () => {
    const misset = heldCapabilities({ ...COLLECTION_HELD, invited_cohort: { available: false, reasons: ['invited_cohort_unset'] } })
    expect(misset[0].title).toBe('Registration is on hold')
    expect(misset[0].description).toBe(
      `${COLLECTION_REASONS.collection_disabled} ${COLLECTION_REASONS.operator_unpublished} The invited-cohort exception is switched on but held: ${INVITED_COHORT_REASONS.invited_cohort_unset} Until registration opens, you can't create invite links or resend one. The list and Revoke still work.`,
    )
    expect(heldCapabilities(COLLECTION_HELD)[0].description).not.toMatch(/invited-cohort/)
  })

  it('writes each title as one phrase with no semicolon', () => {
    for (const { title } of [...heldCapabilities(COLLECTION_HELD), ...heldCapabilities(COHORT_ONLY)]) {
      expect(title).not.toMatch(/;/)
    }
  })
})
