import type { QueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import { advanceSessionGeneration, getSessionGeneration, isSessionGenerationCurrent, subscribeSessionLoss, getExplicitSessionGeneration, isExplicitSessionGenerationCurrent, assertExplicitSessionGeneration } from '@/lib/api/session'

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
  void queryClient.cancelQueries({ queryKey: queryKeys.subscription.all() })
  void queryClient.cancelQueries({ queryKey: queryKeys.usage.all() })
  queryClient.setQueryData(queryKeys.currentUser(), null)
  queryClient.removeQueries({ queryKey: queryKeys.subscription.all() })
  queryClient.removeQueries({ queryKey: queryKeys.usage.all() })
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
