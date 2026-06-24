import api from '@/lib/api/client'

// Admin-only client for the beta invite endpoints (backend/app/routers/admin.py).
// Every call is gated server-side by `_require_admin` — a non-admin gets 403 regardless of UI.

export interface MintInviteInput {
  /** Optional binding: only this address may redeem the invite. Omit for an any-email link. */
  email?: string
  /** Defaults to the backend's INVITE_EXPIRY_HOURS (168h) when omitted. */
  expiresInHours?: number
  /** When true (and an email is given) the backend also emails the magic link best-effort. */
  sendEmail?: boolean
}

export interface MintedInvite {
  id: number
  email: string | null
  // Raw token rides in this link and is shown exactly once — only its hash is stored server-side.
  invite_link: string
  expires_at: string
  emailed: boolean
}

export type InviteStatus = 'pending' | 'used' | 'revoked' | 'expired'

export interface InviteListItem {
  id: number
  email: string | null
  status: InviteStatus
  expires_at: string | null
  used_at: string | null
  user_id: number | null
  created_at: string | null
}

export const mintInvite = async (input: MintInviteInput): Promise<MintedInvite> => {
  const response = await api.post('/api/admin/invites', {
    email: input.email || undefined,
    expires_in_hours: input.expiresInHours ?? undefined,
    send_email: input.sendEmail ?? false,
  })
  return response.data
}

export const listInvites = async (): Promise<InviteListItem[]> => {
  const response = await api.get('/api/admin/invites')
  return response.data?.invites ?? []
}

export const revokeInvite = async (id: number): Promise<{ status: InviteStatus }> => {
  const response = await api.post(`/api/admin/invites/${id}/revoke`)
  return response.data
}
