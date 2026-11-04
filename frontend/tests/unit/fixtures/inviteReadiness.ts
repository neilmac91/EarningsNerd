import type { InviteDelivery, InviteReadiness, InviteRecord } from '@/features/admin/api/admin-api'

/** The invited-cohort exception as an invite-only service holds it by default: switched off, no cohort set. */
export const COHORT_EXCEPTION_HELD = { available: false, reasons: ['invited_cohort_disabled', 'invited_cohort_unset'] }

/** GET /api/admin/invites/readiness answers (backend legal_readiness_service), for the admin invites specs. */
export const READY: InviteReadiness = {
  collection: { available: true, reasons: [] },
  invited_cohort: COHORT_EXCEPTION_HELD,
  invitation_email: { available: true, reasons: [] },
}

/** Registration open, invitation email off until the founder's approval: links only. */
export const EMAIL_HELD: InviteReadiness = {
  collection: { available: true, reasons: [] },
  invited_cohort: COHORT_EXCEPTION_HELD,
  invitation_email: { available: false, reasons: ['invitation_email_disabled'] },
}

/** Registration closed, which holds invitation email too. */
export const COLLECTION_HELD: InviteReadiness = {
  collection: { available: false, reasons: ['collection_disabled', 'operator_unpublished'] },
  invited_cohort: COHORT_EXCEPTION_HELD,
  invitation_email: { available: false, reasons: ['collection_unavailable', 'invitation_email_disabled'] },
}

/** Registration closed but the invited-cohort exception open: links for the cohort alone, invitation email off. */
export const COHORT_ONLY: InviteReadiness = {
  collection: { available: false, reasons: ['collection_disabled', 'operator_unpublished'] },
  invited_cohort: { available: true, reasons: [] },
  invitation_email: { available: false, reasons: ['invitation_email_disabled'] },
}

/** An emailed invite's delivery, in a given state. */
export const delivery = (overrides: Partial<InviteDelivery> = {}): InviteDelivery => ({
  status: 'accepted',
  error_kind: null,
  bounce_type: null,
  permission_via: 'email',
  permission_requested_on: '2026-10-30',
  created_at: '2026-10-31T09:00:00Z',
  updated_at: '2026-10-31T09:00:05Z',
  ...overrides,
})

/** A pending invite to `email`, never emailed unless the overrides say so. */
export const pendingInvite = (overrides: Partial<InviteRecord> = {}): InviteRecord => ({
  id: 1,
  email: 'alice@example.com',
  status: 'pending',
  cohort: 'beta',
  expires_at: '2026-11-08T00:00:00Z',
  used_at: null,
  user_id: null,
  created_at: '2026-10-31T00:00:00Z',
  delivery: null,
  email_suppression: null,
  ...overrides,
})
