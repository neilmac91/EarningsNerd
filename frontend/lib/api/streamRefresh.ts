import { ensureRefreshed } from './client'
import { hasActiveSession, clearSessionActive } from './session'

/**
 * Run a raw SSE POST (one that bypasses the shared axios client) with the SAME silent
 * 401 → /refresh → replay the client's interceptor does — so a logged-in user whose short-lived
 * access cookie expired mid-session (30 min) isn't dead-ended on "sign in" while the app still
 * shows them logged in. This is the ONE home for that dance; all three sanctioned raw-fetch SSE
 * readers (summary generation, Copilot Q&A, Multi-Period Analysis) call it.
 *
 * Behaviour, mirroring `lib/api/client.ts`:
 * - Gate on `hasActiveSession()`: a guest's 401 is genuine, never a pointless refresh.
 * - Share `ensureRefreshed()`'s single in-flight promise: a concurrent 401 here + in axios must
 *   fire exactly ONE `/refresh`, because two calls on the single-use ROTATING refresh token would
 *   invalidate each other and log the user out.
 * - `clearSessionActive()` when refresh fails, so a gone session stops being treated as live.
 * - The replay runs OUTSIDE the refresh `try` (like the client) so a replayed-request error is a
 *   normal request error, not mistaken for a refresh failure.
 *
 * Returns the (possibly replayed) Response. Network throws propagate to the caller, which already
 * guards its own connect/read error handling (each reader wraps this in its own try/catch).
 *
 * @param doPost builds and sends the POST fresh each call (so the replay re-sends an identical
 *   request); must reuse the caller's AbortController signal.
 */
export async function postStreamWithRefresh(doPost: () => Promise<Response>): Promise<Response> {
  let response = await doPost()
  if (response.status === 401 && hasActiveSession()) {
    let refreshed = false
    try {
      await ensureRefreshed()
      refreshed = true
    } catch {
      clearSessionActive() // session genuinely gone — stop treating it as live
    }
    if (refreshed) {
      response = await doPost()
    }
  }
  return response
}
