import type { QueryClient } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import { advanceSessionGeneration, getSessionGeneration, isSessionGenerationCurrent, subscribeSessionLoss } from '@/lib/api/session'

/** Drop identity-derived snapshots before a replacement identity can be accepted.
 * cancelQueries starts cancellation synchronously. No post-await cleanup may erase the next
 * account. Do not clear the active-session marker: successful login already established it.
 */
export function resetAccountQueries(queryClient: QueryClient, generation = getSessionGeneration()): void {
  if (!isSessionGenerationCurrent(generation)) return
  advanceSessionGeneration()
  void queryClient.cancelQueries({ queryKey: queryKeys.currentUser() })
  void queryClient.cancelQueries({ queryKey: queryKeys.subscription.all() })
  void queryClient.cancelQueries({ queryKey: queryKeys.usage.all() })
  queryClient.setQueryData(queryKeys.currentUser(), null)
  queryClient.removeQueries({ queryKey: queryKeys.subscription.all() })
  queryClient.removeQueries({ queryKey: queryKeys.usage.all() })
}

export function subscribeAccountQueryReset(queryClient: QueryClient): () => void {
  return subscribeSessionLoss((generation) => {
    if (isSessionGenerationCurrent(generation)) resetAccountQueries(queryClient, generation)
  })
}

/** A late logout completion must not reset an identity established by a newer transition. */
export async function logoutAndResetAccount(queryClient: QueryClient, logout: () => Promise<unknown>): Promise<void> {
  const generation = getSessionGeneration()
  try {
    await logout()
  } finally {
    resetAccountQueries(queryClient, generation)
  }
}
