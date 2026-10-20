import type { QueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import { advanceSessionGeneration, getSessionGeneration, isSessionGenerationCurrent, subscribeSessionLoss, getExplicitSessionGeneration, isExplicitSessionGenerationCurrent, assertExplicitSessionGeneration } from '@/lib/api/session'

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

/** A late logout completion must not reset or navigate away from a newer accepted login.
 * The callback is synchronous: ownership check, reset and UI continuation share one turn.
 * Request errors still propagate; current Header/UserMenu failure navigation runs in finally.
 */
export async function logoutAndResetAccount(
  queryClient: QueryClient,
  logout: () => Promise<unknown>,
  onCurrentSettled?: (succeeded: boolean) => void,
): Promise<void> {
  const generation = getExplicitSessionGeneration()
  let succeeded = false
  try {
    await logout()
    succeeded = true
  } finally {
    if (isExplicitSessionGenerationCurrent(generation)) {
      resetAccountQueries(queryClient)
      onCurrentSettled?.(succeeded)
    }
  }
}

/** No await between final credential ownership check and replacement cache publication. */
export function acceptLoginAndResetAccount(queryClient: QueryClient, explicitGeneration: number): number {
  assertExplicitSessionGeneration(explicitGeneration)
  resetAccountQueries(queryClient)
  return getExplicitSessionGeneration()
}
