import { hashKey, type QueryClient, type QueryState } from '@tanstack/react-query'
import { toast } from 'sonner'
import { getCurrentUserSafe, type CurrentUser } from '@/features/auth/api/auth-api'
import { ApiError, cancelRefresh } from '@/lib/api/client'
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
  queryKeys.feedback.all(),
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

/** Another tab's sign-in or logout reaches this one only through /me (the Header reads it again on focus, once its last
 * read is a minute old), and resets nothing (E29 (3)). A read that names another reader than the one this tab last
 * showed finds the account families still holding that reader's snapshots. So does a read that names no one: a logout
 * in another tab, or a lost session another tab found first, clears the shared session marker, so this tab's 401 reads
 * as a guest's, and a guest's disabled reads still return what the cache holds (the calendar's alert bells). Either
 * way the families go, as a reset's do, and the session generation moves on, so that reader's answers still in flight
 * write nothing (E29 (1)); the new identity stays. A reset in this tab (a logout, a login, a lost session) empties the
 * families itself and writes its null by hand, and a failed logout then puts back the reader it found, so neither
 * counts. A cleared cache (`queryClient.clear()`) writes no null, so a /me that answers no one after it drops the
 * families again, already empty. The cache calls this inside the update, before any observer hears of it, so no render
 * shows the new identity beside the previous reader's snapshots. */
function watchReader(queryClient: QueryClient): () => void {
  const identity = hashKey(queryKeys.currentUser())
  const readerOf = (data: unknown) => (data as CurrentUser | null | undefined)?.id ?? null
  let reader = readerOf(queryClient.getQueryData(queryKeys.currentUser()))
  return queryClient.getQueryCache().subscribe((event) => {
    if (event.type !== 'updated' || event.action.type !== 'success' || event.query.queryHash !== identity) return
    const previous = reader
    reader = readerOf(event.query.state.data)
    // A reset's null is written by hand (setQueryData); a /me's is fetched.
    if (previous === null || previous === reader || (reader === null && event.action.manual)) return
    advanceSessionGeneration('session-loss')
    for (const queryKey of ACCOUNT_QUERY_FAMILIES) void queryClient.cancelQueries({ queryKey })
    for (const queryKey of ACCOUNT_QUERY_FAMILIES) queryClient.removeQueries({ queryKey })
  })
}

export function subscribeAccountQueryReset(queryClient: QueryClient): () => void {
  const stopLossReset = subscribeSessionLoss((generation) => {
    if (isSessionGenerationCurrent(generation)) resetAccountQueries(queryClient, generation, 'session-loss')
  })
  const stopReaderWatch = watchReader(queryClient)
  return () => {
    stopLossReset()
    stopReaderWatch()
  }
}

/** What /me says of this browser's session after a logout request that failed: no user, the user, or nothing. */
type SessionRead = 'guest' | 'user' | 'unknown'

/** How long a failed logout waits for /me, a refresh it starts included, before it tells the reader the logout did not
 * take. That refresh is a bare request with no timeout of its own (lib/api/refresh.ts), so one that never answered
 * would hold the logout, its report and the menus' focus return for good. */
export const SESSION_READ_LIMIT_MS = 10_000

/** After a logout request that failed: whether this browser is logged out anyway. The API answers a revoke that
 * failed with a 503 that clears the session cookies; a request that never arrived, or the API's 504, clears none,
 * and the session goes on. /me decides: no user means the cookies are gone. The read goes into the current-user
 * query, so a session that survived shows again, and it starts in the turn of the reset before it, so no render
 * sees a settled null before it answers (isConfirmedGuest). It reads past the cache (staleTime 0: the app's queries
 * keep a read fresh for a minute) and runs offline too (networkMode 'always'): paused, it would hold the logout
 * until the connection came back. A read that fails cannot tell, nor can one still unanswered at the limit: a timeout
 * never counts as a logout that took. At the limit the read is cancelled, its request with it, and the current-user
 * query goes back to the identity it held when the read began. So is a refresh in flight: its answer sets the session
 * cookies, and one landing after a login that followed would put this session's back over that login's, which no
 * generation fence stops (client.ts's cancelRefresh).
 */
async function readSession(queryClient: QueryClient): Promise<SessionRead> {
  let timer: ReturnType<typeof setTimeout> | undefined
  const limit = new Promise<'limit'>((resolve) => { timer = setTimeout(() => resolve('limit'), SESSION_READ_LIMIT_MS) })
  const read = queryClient
    .fetchQuery({
      queryKey: queryKeys.currentUser(),
      queryFn: getCurrentUserSafe,
      staleTime: 0,
      retry: false,
      networkMode: 'always',
    })
    .then((user): SessionRead => (user === null ? 'guest' : 'user'), (): SessionRead => 'unknown')
  const outcome = await Promise.race([read, limit]).finally(() => clearTimeout(timer))
  if (outcome !== 'limit') return outcome
  cancelRefresh()
  await queryClient.cancelQueries({ queryKey: queryKeys.currentUser() })
  return 'unknown'
}

/** Put the reader's identity back as the reset found it, read at the time it was read, so it is no fresher than it
 * was. A logout whose request failed calls it twice, each time with no transition of this tab since its own reset:
 * in that reset's turn, so the account menu stays while /me is read, and when /me could not be read either, so the
 * menu and its Log out stay for another try. The account families stay removed, and refetch under this identity. */
function restoreIdentity(queryClient: QueryClient, shown: QueryState<CurrentUser | null> | undefined): void {
  if (shown?.data) queryClient.setQueryData(queryKeys.currentUser(), shown.data, { updatedAt: shown.dataUpdatedAt })
}

/** A logout running in this tab, and the explicit generation it answers for: the one it found, then its own reset's
 * once its request has failed and /me is read. */
interface LogoutUnderWay {
  generation: number
  settled: Promise<void>
}

/** One logout at a time, for the controls that log out through this helper (the account menu, the mobile menu and the
 * dashboard; the settings page's "Log out of all devices" runs outside it, E157). A second would undo the first: its
 * request clears the session flag (auth-api's logout) while the first reads /me, so a lapsed access cookie reads as a
 * guest and the first leaves as logged out with the refresh cookie alive; and its answer, landing after the first's
 * reset moved the generation past the one it started with, is dropped, so a logout it completed leaves the tab showing
 * the account. A login accepted meanwhile moves the generation past this one, and that account's logout starts its
 * own. */
let logoutUnderWay: LogoutUnderWay | null = null

/** A late logout completion must not reset or navigate away from a newer accepted login.
 * The callback is synchronous and shares a turn with the ownership check before it: the reset's turn when the
 * request succeeded, and when it failed, the turn the read of /me ended in, by its answer or by its limit.
 * The account snapshots reset once the request settles, failed or not. A failed request (a network error, a 5xx,
 * the API's 504) may still have logged this browser out, so the reader keeps their identity on screen while /me is
 * read (readSession), and the callback hears success when it answers no user: the logout resolves. After the API's
 * own 503 (it cleared this browser's cookies but could not end the session on the server) the reader is warned in
 * the API's words. Otherwise the logout did not take: the reader is told so, the callback hears failure, the tab
 * stays where it is, and the logout rejects with the request's error. The session flag goes back to what the logout
 * found for the read, since the request clears it (auth-api's logout) and a lapsed access cookie then reads as a
 * guest: /me 401s, and only the flag lets that 401 renew the session from the refresh cookie. A login accepted
 * meanwhile owns the tab, and nothing follows for this logout but its error. A call while a logout of the same
 * session runs (a second press) joins it (logoutUnderWay): it settles as that logout does, and neither its request
 * nor its callback runs.
 */
export function logoutAndResetAccount(
  queryClient: QueryClient,
  logout: () => Promise<unknown>,
  onCurrentSettled?: (succeeded: boolean) => void,
): Promise<void> {
  if (logoutUnderWay && isExplicitSessionGenerationCurrent(logoutUnderWay.generation)) return logoutUnderWay.settled
  const run = { generation: getExplicitSessionGeneration() } as LogoutUnderWay
  run.settled = settleLogout(queryClient, logout, run, onCurrentSettled).finally(() => {
    if (logoutUnderWay === run) logoutUnderWay = null
  })
  logoutUnderWay = run
  return run.settled
}

async function settleLogout(
  queryClient: QueryClient,
  logout: () => Promise<unknown>,
  run: LogoutUnderWay,
  onCurrentSettled?: (succeeded: boolean) => void,
): Promise<void> {
  const generation = run.generation
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
    // A press while /me is read joins this logout.
    run.generation = reset
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
      // The session may live on in the database until it expires, so the reader hears it (the logout route's 503).
      const { error } = failure
      if (error instanceof ApiError && error.status === 503 && error.backendDetail) toast.warning(error.backendDetail)
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
