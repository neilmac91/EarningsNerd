import { formatLocalDate } from '@/lib/format'
import type {
  DeliveryStatus,
  EmailSuppression,
  InviteDelivery,
  InviteRecord,
  PermissionVia,
} from '@/features/admin/api/admin-api'

/**
 * What the admin list says about an invite's email, in words that claim no more than the evidence: the provider's
 * acceptance is never delivery, and "delivered" is only the recipient's mail server taking it, never proof the
 * person has it. No state reads as received, opened or seen in an inbox (tests/unit/inviteDeliveryLabels.spec.ts).
 */
export interface DeliveryState {
  label: string
  hint?: string
}

/** A link that was never emailed: the admin shared it, or will. */
export const NOT_EMAILED: DeliveryState = { label: 'Not emailed' }

const STATES: Record<Exclude<DeliveryStatus, 'bounced' | 'failed'>, DeliveryState> = {
  sending: { label: 'Sending', hint: 'Waiting for the email provider to answer.' },
  accepted: { label: 'Accepted by the email provider', hint: "Delivery isn't confirmed." },
  delayed: { label: 'Delivery delayed', hint: 'The email provider is still trying.' },
  delivered: { label: "Delivered to the recipient's mail server", hint: 'Not proof it reached them.' },
  complained: { label: 'Reported as spam' },
  suppressed: { label: 'Not sent: the email provider suppressed this address' },
  unknown: {
    label: 'Outcome unknown',
    hint: "It may or may not have been sent. Don't resend blindly: Resend revokes this link and sends a new one.",
  },
}

/** A record's own entry for a key the server sent, never one inherited from Object (a "constructor" kind). */
function own<T>(record: Record<string, T>, key: string | null | undefined): T | undefined {
  return key != null && Object.prototype.hasOwnProperty.call(record, key) ? record[key] : undefined
}

const BOUNCED: Record<string, string> = {
  permanent: 'Bounced permanently',
  temporary: 'Bounced temporarily',
}

/** Why a send failed, from the delivery's error kind; a kind this page does not know adds nothing. */
const FAILED_BECAUSE: Record<string, string> = {
  held: 'Email delivery was held.',
  provider_retryable: 'The email provider was unavailable.',
  provider_rejected: 'The email provider rejected it.',
}

function failedHint(kind: string | null): string | undefined {
  if (!kind) return undefined
  const known = own(FAILED_BECAUSE, kind)
  if (known) return known
  // "provider:<reason>": the provider's own reason for an email it failed after taking it.
  const [source, ...reason] = kind.split(':')
  if (source === 'provider' && reason.join(':').trim()) return `The email provider gave this reason: ${reason.join(':').trim()}`
  return undefined
}

/** The state of one invitation email, or of a link never emailed. A status this page does not know claims nothing. */
export function deliveryState(
  delivery: Pick<InviteDelivery, 'status' | 'error_kind' | 'bounce_type'> | null | undefined,
): DeliveryState {
  if (!delivery) return NOT_EMAILED
  const { status } = delivery
  if (status === 'bounced') return { label: own(BOUNCED, delivery.bounce_type) ?? 'Bounced' }
  if (status === 'failed') return { label: 'Not sent', hint: failedHint(delivery.error_kind) }
  return own<DeliveryState>(STATES, status) ?? { label: 'Delivery state not recognised' }
}

/** Why an address gets no invitation email, as the row's note says it. */
export const SUPPRESSION_NOTES: Record<EmailSuppression, string> = {
  unsubscribed: 'Unsubscribed from invitation emails',
  hard_bounce: 'Bounced permanently',
  complaint: 'Reported as spam',
  provider_suppressed: 'Suppressed by the email provider',
}

/** The note for a suppressed address; one this page does not know still withholds email. */
export function suppressionNote(suppression: EmailSuppression | null | undefined): string | null {
  if (!suppression) return null
  return own<string>(SUPPRESSION_NOTES, suppression) ?? 'No invitation email goes to this address'
}

/** How the recipient asked, as the permission form offers it. */
export const PERMISSION_VIA_LABELS: Record<PermissionVia, string> = {
  email: 'Email',
  message: 'Message',
  call: 'Call',
  in_person: 'In person',
  other: 'Other',
}

const ASKED: Record<PermissionVia, string> = {
  email: 'Asked by email',
  message: 'Asked by message',
  call: 'Asked on a call',
  in_person: 'Asked in person',
  other: 'Asked another way',
}

/** The request an emailed invite was sent under: how the person asked, and the day ("Asked by email, Oct 30, 2026"). */
export function permissionLine(delivery: Pick<InviteDelivery, 'permission_via' | 'permission_requested_on'>): string {
  const asked = own<string>(ASKED, delivery.permission_via) ?? 'Asked'
  // A calendar day, not an instant: formatLocalDate keeps its own day for a reader behind UTC.
  const day = formatLocalDate(delivery.permission_requested_on, 'MMM d, yyyy')
  return day ? `${asked}, ${day}` : asked
}

/**
 * Whether a resend asks the backend to email the new link: only for an invite emailed before (the backend reuses
 * that first request's permission), while invitation email is available and the address is not suppressed.
 * Otherwise the resend makes a new link to share by hand.
 */
export function resendEmails(
  invite: Pick<InviteRecord, 'delivery' | 'email_suppression'>,
  invitationEmailAvailable: boolean,
): boolean {
  return Boolean(invite.delivery) && invitationEmailAvailable && !invite.email_suppression
}
