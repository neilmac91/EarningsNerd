import axios from 'axios'

/**
 * Exchange the HttpOnly refresh cookie for a fresh access token.
 *
 * Uses a bare axios call (not the shared `api` instance) so it never recurses through the
 * 401 response interceptor. The new access/refresh cookies are set by the server on the
 * response; nothing is read or stored in JS. Rejects if the refresh token is missing,
 * expired, or already used — the caller treats that as "session gone".
 */
export async function refreshAccessToken(baseUrl: string): Promise<void> {
  await axios.post(`${baseUrl}/api/auth/refresh`, {}, { withCredentials: true })
}
