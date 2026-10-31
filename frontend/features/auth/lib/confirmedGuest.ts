import type { QueryObserverResult } from '@tanstack/react-query'

/**
 * Whether the current-user read says this tab has no session: a settled null. /me answers a guest with null
 * (getCurrentUserSafe turns its 401 into null), and a logout or a lost session resets the read to null. A null still
 * being read is not settled: a logout whose request failed reads /me before it decides (logoutAndResetAccount), and a
 * fetch paused offline has not answered. A read that failed (offline, a 5xx) cannot tell either. Every guard that sends
 * the reader to /login asks this (tests/unit/loginRedirectsAskConfirmedGuest.spec.ts).
 */
export function isConfirmedGuest(read: Pick<QueryObserverResult<unknown>, 'data' | 'fetchStatus' | 'isError'>): boolean {
  return read.data === null && read.fetchStatus === 'idle' && !read.isError
}
