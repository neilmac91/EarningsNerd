import type { FeedbackAttachment } from '@/features/feedback/api/feedback-api'
import api from '@/lib/api/client'

/**
 * Admin invite API client. All endpoints live under /api/admin and are gated by the
 * backend's _require_admin dependency (401 unauth / 403 non-admin). Request bodies use
 * snake_case to match the backend contract; the client functions accept camelCase args.
 */

export type InviteStatus = 'pending' | 'used' | 'revoked' | 'expired'

/**
 * What the evidence says of one emailed invitation link (backend app/models/invite_mail.py). `accepted` is only the
 * email provider taking the message, and `delivered` only the recipient's mail server taking it: neither says the
 * person has it. `unknown` is a send whose answer was lost, so it may or may not have gone.
 */
export const DELIVERY_STATUSES = [
  'sending', 'accepted', 'delayed', 'delivered', 'bounced', 'complained', 'suppressed', 'failed', 'unknown',
] as const
export type DeliveryStatus = (typeof DELIVERY_STATUSES)[number]
export type BounceType = 'permanent' | 'temporary' | 'undetermined'

/** Why an address gets no invitation email: an unsubscribe, a permanent bounce, a spam report or the provider's list. */
export const EMAIL_SUPPRESSIONS = ['unsubscribed', 'hard_bounce', 'complaint', 'provider_suppressed'] as const
export type EmailSuppression = (typeof EMAIL_SUPPRESSIONS)[number]

/** How the recipient asked for an invitation (backend PERMISSION_VIA). */
export const PERMISSION_VIA = ['email', 'message', 'call', 'in_person', 'other'] as const
export type PermissionVia = (typeof PERMISSION_VIA)[number]

/** The recipient's own request for an invitation, which an emailed invite records: how, and the day (YYYY-MM-DD). */
export interface InvitePermission {
  requested_via: PermissionVia
  requested_on: string
}

/** An emailed invite's delivery, as the list shows it: its state and the request it was sent under. */
export interface InviteDelivery {
  status: DeliveryStatus
  /** Why a send failed or ended unknown, from a closed set of codes ("held", "provider_rejected", "provider:<reason>"). */
  error_kind: string | null
  bounce_type: BounceType | null
  permission_via: string
  permission_requested_on: string
  created_at: string
  updated_at: string
}

export interface InviteRecord {
  id: number
  email: string | null
  status: InviteStatus
  cohort: string | null
  expires_at: string
  used_at: string | null
  user_id: number | null
  created_at: string
  /** The invitation email's state, or null for a link that was never emailed. */
  delivery: InviteDelivery | null
  /** Why this address gets no invitation email, or null when nothing holds it. */
  email_suppression: EmailSuppression | null
}

/** The InviteResponse returned when minting (create) or resending an invite. */
export interface MintResult {
  id: number
  email: string | null
  invite_link: string
  expires_at: string
  /** The email provider accepted the email: never delivery, which `delivery_status` describes as far as it is known. */
  emailed: boolean
  cohort: string | null
  /** The emailed invite's state, or null when no email was asked for. */
  delivery_status: DeliveryStatus | null
}

/** A resend mints a fresh invite and revokes the old one, echoing the old id back. */
export interface ResendResult extends MintResult {
  revoked_invite_id: number
}

export interface CreateInviteInput {
  email?: string
  cohort?: string
  expiresInHours?: number
  sendEmail?: boolean
  /** Required with `sendEmail`: the request the email is sent under, the same for every address in one send. */
  permission?: InvitePermission
}

export interface ResendInviteInput {
  /** Always sent: true only to email the new link of an invite emailed before (its first request stands), while
   *  invitation email is available and its address is not suppressed; false makes a new link to share by hand. */
  sendEmail: boolean
  expiresInHours?: number
  permission?: InvitePermission
}

/** One capability's answer: available, or the codes of the conditions that hold it (codes, never values). */
export interface InviteCapability {
  available: boolean
  reasons: string[]
}

/** What holds new invite links (collection, or the invited-cohort exception) and requested invitation email, as the
 *  admin page reads it. */
export interface InviteReadiness {
  collection: InviteCapability
  /** Collection held, it alone opens links: each bound to an address and in the configured cohort (named nowhere). */
  invited_cohort: InviteCapability
  invitation_email: InviteCapability
}

/** The invited-cohort exception held, with no reason, as an API from before it answers by leaving the field out. */
const COHORT_EXCEPTION_ABSENT: InviteCapability = { available: false, reasons: [] }

function capabilityOf(value: unknown): InviteCapability | null {
  if (!value || typeof value !== 'object') return null
  const { available, reasons } = value as { available?: unknown; reasons?: unknown }
  if (typeof available !== 'boolean' || !Array.isArray(reasons)) return null
  if (!reasons.every((reason): reason is string => typeof reason === 'string')) return null
  return { available, reasons }
}

export interface RevokeResult {
  message: string
  invite_id: number
  status: string
}

/**
 * What holds new invite links and invitation email. The page turns off what this says is held, and treats a failed
 * or malformed read as all held (fail closed); every invite route checks again on the server, so a stale answer
 * can only turn a control off, never let one through. An answer without `invited_cohort` (an API from before the
 * exception) holds the exception and changes nothing else; one with it malformed fails the read.
 */
export const getInviteReadiness = async (signal?: AbortSignal): Promise<InviteReadiness> => {
  const response = await api.get('/api/admin/invites/readiness', { signal })
  const data = response.data as { collection?: unknown; invited_cohort?: unknown; invitation_email?: unknown } | null
  const collection = capabilityOf(data?.collection)
  const invitedCohort = data && 'invited_cohort' in data ? capabilityOf(data.invited_cohort) : COHORT_EXCEPTION_ABSENT
  const invitationEmail = capabilityOf(data?.invitation_email)
  if (!collection || !invitedCohort || !invitationEmail) throw new Error('Availability could not be checked.')
  return { collection, invited_cohort: invitedCohort, invitation_email: invitationEmail }
}

export const listInvites = async (): Promise<InviteRecord[]> => {
  const response = await api.get('/api/admin/invites')
  return response.data.invites
}

export const createInvite = async (input: CreateInviteInput): Promise<MintResult> => {
  // Only forward fields the caller actually set, so the backend applies its own defaults
  // (e.g. INVITE_EXPIRY_HOURS) for anything omitted.
  const body: Record<string, unknown> = {}
  if (input.email !== undefined) body.email = input.email
  if (input.cohort !== undefined) body.cohort = input.cohort
  if (input.expiresInHours !== undefined) body.expires_in_hours = input.expiresInHours
  if (input.sendEmail !== undefined) body.send_email = input.sendEmail
  if (input.permission !== undefined) body.permission = input.permission

  const response = await api.post('/api/admin/invites', body)
  return response.data
}

export const resendInvite = async (id: number, input: ResendInviteInput): Promise<ResendResult> => {
  // send_email is always explicit: left out, the backend emails any bound invite's replacement.
  const body: Record<string, unknown> = { send_email: input.sendEmail }
  if (input.expiresInHours !== undefined) body.expires_in_hours = input.expiresInHours
  if (input.permission !== undefined) body.permission = input.permission
  const response = await api.post(`/api/admin/invites/${id}/resend`, body)
  return response.data
}

export const revokeInvite = async (id: number): Promise<RevokeResult> => {
  const response = await api.post(`/api/admin/invites/${id}/revoke`)
  return response.data
}

// ── Feedback ───────────────────────────────────────────────────────────────────

export type FeedbackType = 'bug' | 'feature' | 'general'
export type FeedbackStatus = 'new' | 'triaged' | 'resolved'

export interface FeedbackRecord {
  attachment_count?: number
  attachments?: FeedbackAttachment[]
  id: number
  user_id: number | null
  user_email: string | null
  type: FeedbackType
  message: string
  page_url: string | null
  status: FeedbackStatus
  created_at: string
}

export const listFeedback = async (filters?: {
  status?: string
  type?: string
}): Promise<FeedbackRecord[]> => {
  // Only forward filters the caller actually set (and not the sentinel 'all') so the backend
  // returns everything by default.
  const params: Record<string, string> = {}
  if (filters?.status && filters.status !== 'all') params.status = filters.status
  if (filters?.type && filters.type !== 'all') params.type = filters.type

  const response = await api.get('/api/admin/feedback', { params })
  return response.data.feedback
}

export const updateFeedbackStatus = async (
  id: number,
  status: FeedbackStatus,
): Promise<FeedbackRecord> => {
  const response = await api.patch(`/api/admin/feedback/${id}`, { status })
  return response.data
}
