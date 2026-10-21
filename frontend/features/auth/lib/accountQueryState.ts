import type { QueryClient, QueryState } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getCurrentUserSafe, type CurrentUser } from '@/features/auth/api/auth-api'
import { queryKeys } from '@/lib/queryKeys'
import { advanceSessionGeneration, getSessionGeneration, isSessionGenerationCurrent, subscribeSessionLoss, getExplicitSessionGeneration, isExplicitSessionGenerationCurrent, assertExplicitSessionGeneration, hasActiveSession, markSessionActive, clearSessionActive } from '@/lib/api/session'

/** What a logout that did not take tells the reader, whatever /me answered: their account, or nothing it could read (a
 * connection that dropped, or a /me or a refresh that answered 5xx while the connection worked). */
export const LOGOUT_FAILED_MESSAGE = "We couldn't log you out. Try again in a moment."

/** Every query family that holds one account's data, by key prefix. Most are unkeyed by the reader,
 * so after a logout or login in this tab the next account would read the previous one's snapshot
 * until a refetch; the reset removes them all. `savedSummaries` covers `savedSummaryStatus`, which
 * shares its prefix. tests/unit/accountQueryState.spec.tsx classifies every family in queryKeys as
 * account-owned or shared, and every member of an owned family under its one prefix, so a new family
 * or member cannot escape this list.
 */
export const ACCOUNT_QUERY_FAMILIES = [
  queryKeys.subscription.all(),
  queryKeys.usage.all(),
  queryKeys.wordingReview.all(), // the reader's own labels and receipts
  // Keyed by the reader, but a reader whose /me failed reads under the anonymous key with their own
  // session, so a Pro reader's full report can sit in the entry the next anonymous viewer reads.
  queryKeys.whatChanged.all(),
  queryKeys.savedSummaries(),
  queryKeys.watchlist(),
  queryKeys.watchlistInsights(),
  queryKeys.earningsAlertTickers(),
  queryKeys.dashboardFeed(),
  queryKeys.dashboardCalendar(),
  queryKeys.notifications(),
  queryKeys.notificationPreferences(),
  queryKeys.authConnections(),
  queryKeys.adminInvites(),
  queryKeys.adminFeedback.all(),
] as const

/** Drop identity-derived snapshots before a replacement identity can be accepted.
 * cancelQueries starts cancellation synchronously. No post-await cleanup may erase the next
 * account. Do not clear the active-session marker: successful login already established it.
 */
export function resetAccountQueries(
  queryClient: QueryClient,
  generation = getSessionGeneration(),
  reason: 'explicit' | 'session-loss' = 'explicit',
): void {
  if (!isSessionGenerationCurrent(generation)) return
  advanceSessionGeneration(reason)
  void queryClient.cancelQueries({ queryKey: queryKeys.currentUser() })
  for (const queryKey of ACCOUNT_QUERY_FAMILIES) void queryClient.cancelQueries({ queryKey })
  queryClient.setQueryData(queryKeys.currentUser(), null)
  // Another account in this tab starts from its own reads.
  for (const queryKey of ACCOUNT_QUERY_FAMILIES) queryClient.removeQueries({ queryKey })
}

export function subscribeAccountQueryReset(queryClient: QueryClient): () => void {
  return subscribeSessionLoss((generation) => {
    if (isSessionGenerationCurrent(generation)) resetAccountQueries(queryClient, generation, 'session-loss')
  })
}

/** What /me says of this browser's session after a logout request that failed: no user, the user, or nothing. */
type SessionRead = 'guest' | 'user' | 'unknown'

/** After a logout request that failed: whether this browser is logged out anyway. The API answers a revoke that
 * failed with a 503 that clears the session cookies; a request that never arrived, or the API's 504, clears none,
 * and the session goes on. /me decides: no user means the cookies are gone. The read goes into the current-user
 * query, so a session that survived shows again, and it starts in the turn of the reset before it, so no render
 * sees a settled null before it answers (isConfirmedGuest). It reads past the cache (staleTime 0: the app's queries
 * keep a read fresh for a minute) and runs offline too (networkMode 'always'): paused, it would hold the logout
 * until the connection came back. A read that fails cannot tell.
 */
async function readSession(queryClient: QueryClient): Promise<SessionRead> {
  try {
    const user = await queryClient.fetchQuery({
      queryKey: queryKeys.currentUser(),
      queryFn: getCurrentUserSafe,
      staleTime: 0,
      retry: false,
      networkMode: 'always',
    })
    return user === null ? 'guest' : 'user'
  } catch {
    return 'unknown'
  }
}

/** Put the reader's identity back as the reset found it, read at the time it was read, so it is no fresher than it
 * was. A logout whose request failed calls it twice, each time with no transition of this tab since its own reset:
 * in that reset's turn, so the account menu stays while /me is read, and when /me could not be read either, so the
 * menu and its Log out stay for another try. The account families stay removed, and refetch under this identity. */
function restoreIdentity(queryClient: QueryClient, shown: QueryState<CurrentUser | null> | undefined): void {
  if (shown?.data) queryClient.setQueryData(queryKeys.currentUser(), shown.data, { updatedAt: shown.dataUpdatedAt })
}

/** A late logout completion must not reset or navigate away from a newer accepted login.
 * The callback is synchronous and shares a turn with the ownership check before it: the reset's turn when the
 * request succeeded, the turn /me answered in when it failed.
 * The account snapshots reset once the request settles, failed or not. A failed request (a network error, a 5xx,
 * the API's 504) may still have logged this browser out, so the reader keeps their identity on screen while /me is
 * read (readSession), and the callback hears success when it answers no user: the logout resolves. Otherwise the
 * logout did not take: the reader is told so, the callback hears failure, the tab stays where it is, and the logout
 * rejects with the request's error. The session flag goes back to what the logout found for the read, since the
 * request clears it (auth-api's logout) and a lapsed access cookie then reads as a guest: /me 401s, and only the
 * flag lets that 401 renew the session from the refresh cookie. A login accepted meanwhile owns the tab, and nothing
 * follows for this logout but its error.
 */
export async function logoutAndResetAccount(
  queryClient: QueryClient,
  logout: () => Promise<unknown>,
  onCurrentSettled?: (succeeded: boolean) => void,
): Promise<void> {
  const generation = getExplicitSessionGeneration()
  const sessionWasActive = hasActiveSession()
  let failure: { error: unknown } | null = null
  try {
    await logout()
  } catch (error) {
    failure = { error }
  }
  if (!isExplicitSessionGenerationCurrent(generation)) {
    if (failure) throw failure.error
    return
  }
  const shown = queryClient.getQueryState<CurrentUser | null>(queryKeys.currentUser())
  resetAccountQueries(queryClient)
  if (failure) {
    // The reset's own generation: an explicit transition (a login accepted) moves both checks below, a lost session
    // only the second.
    const reset = getSessionGeneration()
    restoreIdentity(queryClient, shown)
    // The flag as the logout found it, so a 401 from the read renews a lapsed access cookie.
    if (sessionWasActive) markSessionActive()
    const read = await readSession(queryClient)
    if (!isExplicitSessionGenerationCurrent(reset)) throw failure.error
    // No user: logged out, flag and all. A user: /me's answer has marked the flag. A read that failed leaves the flag
    // as the logout found it (only a lost session clears it, and that moves the session generation), and the identity
    // goes back as the reset found it.
    if (read === 'guest') {
      clearSessionActive()
    } else {
      if (read === 'unknown' && isSessionGenerationCurrent(reset)) restoreIdentity(queryClient, shown)
      toast.error(LOGOUT_FAILED_MESSAGE)
      onCurrentSettled?.(false)
      throw failure.error
    }
  }
  onCurrentSettled?.(true)
}

/** No await between final credential ownership check and replacement cache publication. */
export function acceptLoginAndResetAccount(queryClient: QueryClient, explicitGeneration: number): number {
  assertExplicitSessionGeneration(explicitGeneration)
  resetAccountQueries(queryClient)
  return getExplicitSessionGeneration()
}
