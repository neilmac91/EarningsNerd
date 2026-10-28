/**
 * Each call of logoutAndResetAccount (features/auth/lib/accountQueryState.ts), by the file it sits in: the control it
 * settles. Not a spec: the two specs that hold the logout share it. logoutCallSitesGate.spec.ts finds exactly one call in
 * each file and none elsewhere, and failedLogoutChecksSession.spec.tsx runs its failure cases on a control for each file,
 * so a new control that logs out joins this list and both specs.
 */
export const LOGOUT_CALL_SITES: Record<string, string> = {
  'app/dashboard/page.tsx': "the dashboard's Log out, through its logout mutation",
  'components/Header.tsx': "the site header's mobile menu",
  'features/auth/components/UserMenu.tsx': "the site header's account menu",
}

/**
 * Each control that logs out of every session, by the file it sits in: it does so through logoutAllInTurn, the one-logout
 * flight's entry for it (E157). logoutCallSitesGate.spec.ts finds that entry named once in each file and in no other
 * outside the flight's own module, and logoutAllJoinsTheFlight.spec.tsx runs its cases on a control for each file, so a
 * new one joins this list and both specs.
 */
export const LOGOUT_ALL_CALL_SITES: Record<string, string> = {
  'features/settings/components/ConnectedAccounts.tsx': 'the settings page\'s "Log out of all devices", through its mutation',
}
