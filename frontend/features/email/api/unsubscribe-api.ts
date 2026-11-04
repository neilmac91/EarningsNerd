import api from '@/lib/api/client'

/**
 * The opt-out an invitation email links to (backend app/routers/email.py, EN-BETA PB-01). The email's link is
 * {FRONTEND_URL}/email/unsubscribe#token=<token>: the token rides in the fragment, which no request carries, and the
 * page posts it only when its reader presses the button, so a link scanner that fetches the page changes nothing.
 */

/** The token in a location's fragment (`#token=…`), or null when it holds none. */
export function unsubscribeTokenFrom(hash: string): string | null {
  const token = new URLSearchParams(hash.replace(/^#/, '')).get('token')?.trim()
  return token ? token : null
}

/**
 * Stop invitation email to the address the link was sent to. Resolves once the server says the address is
 * unsubscribed; rejects with the client's ApiError otherwise (404: the token names no email, 429: too many tries).
 */
export async function unsubscribeFromInvitations(token: string): Promise<void> {
  const response = await api.post('/api/email/unsubscribe', { token })
  // Only the server's own answer says it is done; anything else is no confirmation.
  if ((response.data as { status?: unknown } | null)?.status !== 'unsubscribed') {
    throw new Error('The unsubscribe could not be confirmed.')
  }
}
