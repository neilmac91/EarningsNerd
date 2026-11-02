import { describe, expect, it } from 'vitest'
import {
  DELIVERY_STATUSES,
  EMAIL_SUPPRESSIONS,
  PERMISSION_VIA,
  type BounceType,
  type DeliveryStatus,
} from '@/features/admin/api/admin-api'
import {
  NOT_EMAILED,
  PERMISSION_VIA_LABELS,
  SUPPRESSION_NOTES,
  deliveryState,
  permissionLine,
  resendEmails,
  suppressionNote,
  type DeliveryState,
} from '@/features/admin/lib/inviteDelivery'
import { delivery } from './fixtures/inviteReadiness'

/**
 * The words the admin list uses for an invitation email claim no more than the evidence (EN-BETA PB-01): the email
 * provider's acceptance is never delivery, "delivered" is only the recipient's mail server taking it, and no state
 * says the person received, read or opened it, or that it reached an inbox. A send that ended unknown says it may or
 * may not have gone, and what Resend does about it.
 */

/** A claim no state may make, as a whole word. */
const PROOF_OF_RECEIPT = /\b(received|inbox|read|opened)\b/i

const text = (state: DeliveryState) => [state.label, state.hint ?? ''].join(' ')
const stateOf = (status: string, more: { error_kind?: string | null; bounce_type?: BounceType | null } = {}) =>
  deliveryState(delivery({ status: status as DeliveryStatus, ...more }))

/** Every state the list can show: each status, each bounce type, each failure kind, and the unemailed link. */
const EVERY_STATE: Array<[string, DeliveryState]> = [
  ['not emailed', deliveryState(null)],
  ...DELIVERY_STATUSES.map((status): [string, DeliveryState] => [status, stateOf(status)]),
  ...(['permanent', 'temporary', 'undetermined'] as const).map((bounce): [string, DeliveryState] => [
    `bounced ${bounce}`,
    stateOf('bounced', { bounce_type: bounce }),
  ]),
  ...['held', 'provider_retryable', 'provider_rejected', 'provider:reached_quota', 'ProviderTimeout'].map(
    (kind): [string, DeliveryState] => [`failed ${kind}`, stateOf('failed', { error_kind: kind })],
  ),
  ['a status this page does not know', stateOf('opened')],
]

describe('invitation email states claim no more than the evidence', () => {
  it.each(EVERY_STATE)('%s never says received, read, opened or inbox', (_name, state) => {
    expect(state.label).toBeTruthy()
    expect(text(state)).not.toMatch(PROOF_OF_RECEIPT)
  })

  it('names every status the backend records (DELIVERY_STATUSES mirrors app/models/invite_mail.py)', () => {
    expect([...DELIVERY_STATUSES].sort()).toEqual(
      ['accepted', 'bounced', 'complained', 'delayed', 'delivered', 'failed', 'sending', 'suppressed', 'unknown'],
    )
  })

  it('reads the provider accepting it as acceptance, never as delivery', () => {
    const accepted = stateOf('accepted')
    expect(accepted.label).toBe('Accepted by the email provider')
    expect(accepted.hint).toBe("Delivery isn't confirmed.")
    expect(text(accepted)).not.toMatch(/\bdeliver(ed|s)?\b|\bsent\b/i)
  })

  it('reads a delivery as the recipient\'s mail server taking it, and says that is not proof it reached them', () => {
    const delivered = stateOf('delivered')
    expect(delivered.label).toBe("Delivered to the recipient's mail server")
    expect(delivered.hint).toBe('Not proof it reached them.')
  })

  it('says how a bounce bounced, when the provider said', () => {
    expect(stateOf('bounced', { bounce_type: 'permanent' }).label).toBe('Bounced permanently')
    expect(stateOf('bounced', { bounce_type: 'temporary' }).label).toBe('Bounced temporarily')
    expect(stateOf('bounced', { bounce_type: 'undetermined' }).label).toBe('Bounced')
    expect(stateOf('bounced').label).toBe('Bounced')
  })

  it('names the states in between and after: sending, delayed, a spam report, the provider\'s suppression', () => {
    expect(text(stateOf('sending'))).toBe('Sending Waiting for the email provider to answer.')
    expect(text(stateOf('delayed'))).toBe('Delivery delayed The email provider is still trying.')
    expect(stateOf('complained')).toEqual({ label: 'Reported as spam' })
    expect(stateOf('suppressed')).toEqual({ label: 'Not sent: the email provider suppressed this address' })
  })

  it('says why a send failed by its error kind, and nothing it does not know', () => {
    expect(stateOf('failed', { error_kind: 'held' })).toEqual({ label: 'Not sent', hint: 'Email delivery was held.' })
    expect(stateOf('failed', { error_kind: 'provider_retryable' }).hint).toBe('The email provider was unavailable.')
    expect(stateOf('failed', { error_kind: 'provider_rejected' }).hint).toBe('The email provider rejected it.')
    expect(stateOf('failed', { error_kind: 'provider:reached_quota' }).hint).toBe('The email provider gave this reason: reached_quota')
    for (const kind of [null, 'ProviderTimeout', 'provider:', 'constructor', 'toString']) {
      expect(stateOf('failed', { error_kind: kind }), String(kind)).toEqual({ label: 'Not sent', hint: undefined })
    }
  })

  it('says an unknown outcome may or may not have gone, and what Resend does about it', () => {
    const unknown = stateOf('unknown')
    expect(unknown.label).toBe('Outcome unknown')
    expect(unknown.hint).toBe("It may or may not have been sent. Don't resend blindly: Resend revokes this link and sends a new one.")
  })

  it('claims nothing for a status it does not know, an inherited key included', () => {
    for (const status of ['opened', 'constructor', '__proto__']) {
      expect(stateOf(status), status).toEqual({ label: 'Delivery state not recognised' })
    }
    expect(deliveryState(null)).toBe(NOT_EMAILED)
    expect(deliveryState(undefined)).toEqual({ label: 'Not emailed' })
  })
})

describe('a suppressed address is its own note', () => {
  it('names each reason the backend records, distinctly', () => {
    expect(Object.keys(SUPPRESSION_NOTES).sort()).toEqual([...EMAIL_SUPPRESSIONS].sort())
    expect(EMAIL_SUPPRESSIONS.map((reason) => suppressionNote(reason))).toEqual([
      'Unsubscribed from invitation emails',
      'Bounced permanently',
      'Reported as spam',
      'Suppressed by the email provider',
    ])
    for (const note of Object.values(SUPPRESSION_NOTES)) expect(note).not.toMatch(PROOF_OF_RECEIPT)
  })

  it('says nothing for an address nothing holds, and still withholds for a reason it does not know', () => {
    expect(suppressionNote(null)).toBeNull()
    expect(suppressionNote(undefined)).toBeNull()
    expect(suppressionNote('soft_bounce' as never)).toBe('No invitation email goes to this address')
  })
})

describe('the request an emailed invite was sent under', () => {
  it('reads how and on which calendar day the person asked', () => {
    expect(permissionLine(delivery({ permission_via: 'email', permission_requested_on: '2026-10-30' }))).toBe('Asked by email, Oct 30, 2026')
    expect(PERMISSION_VIA.map((via) => permissionLine(delivery({ permission_via: via })))).toEqual([
      'Asked by email, Oct 30, 2026',
      'Asked by message, Oct 30, 2026',
      'Asked on a call, Oct 30, 2026',
      'Asked in person, Oct 30, 2026',
      'Asked another way, Oct 30, 2026',
    ])
    expect(permissionLine(delivery({ permission_via: 'carrier_pigeon', permission_requested_on: 'soon' }))).toBe('Asked')
  })

  it('offers each channel the backend takes under a label of its own', () => {
    expect(Object.keys(PERMISSION_VIA_LABELS)).toEqual([...PERMISSION_VIA])
    expect(Object.values(PERMISSION_VIA_LABELS)).toEqual(['Email', 'Message', 'Call', 'In person', 'Other'])
  })
})

describe('a resend emails the new link only on the terms of the first email', () => {
  const emailed = { delivery: delivery(), email_suppression: null }
  it.each([
    ['emailed before, invitation email available, address not suppressed', emailed, true, true],
    ['emailed before, invitation email held', emailed, false, false],
    ['never emailed', { delivery: null, email_suppression: null }, true, false],
    ['emailed before, then unsubscribed', { ...emailed, email_suppression: 'unsubscribed' as const }, true, false],
    ['emailed before, then bounced permanently', { ...emailed, email_suppression: 'hard_bounce' as const }, true, false],
  ])('%s', (_name, invite, available, expected) => {
    expect(resendEmails(invite, available)).toBe(expected)
  })
})
