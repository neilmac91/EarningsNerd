import api from '@/lib/api/client'

/**
 * Admin invite API client. All endpoints live under /api/admin and are gated by the
 * backend's _require_admin dependency (401 unauth / 403 non-admin). Request bodies use
 * snake_case to match the backend contract; the client functions accept camelCase args.
 */

export type InviteStatus = 'pending' | 'used' | 'revoked' | 'expired'

export interface InviteRecord {
  id: number
  email: string | null
  status: InviteStatus
  cohort: string | null
  expires_at: string
  used_at: string | null
  user_id: number | null
  created_at: string
}

/** The InviteResponse returned when minting (create) or resending an invite. */
export interface MintResult {
  id: number
  email: string | null
  invite_link: string
  expires_at: string
  emailed: boolean
  cohort: string | null
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
}

export interface RevokeResult {
  message: string
  invite_id: number
  status: string
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

  const response = await api.post('/api/admin/invites', body)
  return response.data
}

export const resendInvite = async (
  id: number,
  expiresInHours?: number,
): Promise<ResendResult> => {
  const body = expiresInHours !== undefined ? { expires_in_hours: expiresInHours } : {}
  const response = await api.post(`/api/admin/invites/${id}/resend`, body)
  return response.data
}

export const revokeInvite = async (id: number): Promise<RevokeResult> => {
  const response = await api.post(`/api/admin/invites/${id}/revoke`)
  return response.data
}
