/**
 * Whose session this browser holds, as the app last read it, for PostHog's start. posthog-js keeps an identified
 * reader's id in its own storage across page loads until reset(), and a session can end while no page is open: a
 * refresh token lapses, or "Log out of all devices" or an account deletion runs on another device. The session marker
 * (lib/api/session.ts) still reads as a session then. So for a browser with that marker, the provider starts PostHog
 * only once the app's own read of the session (GET /api/auth/me, through hooks/usePostHogUserIdentification.ts) has
 * settled, and in `loaded` resets a kept identity that the read does not confirm, before posthog-js sends anything
 * (app/posthog-provider.tsx). Nothing here is stored: it lives for the page.
 */
let settled: { account: string | null } | undefined
const waiting: Array<() => void> = []

/** The hook reports each settled read: the account's id, or null for no account or a read that failed. */
export function reportAccountRead(account: string | null): void {
  settled = { account }
  for (const then of waiting.splice(0)) then()
}

/** Runs `then` once the session has been read: at once if it has, else at the next report. */
export function whenAccountRead(then: () => void): void {
  if (settled) then()
  else waiting.push(then)
}

/** The account the last settled read names; null for none, or before any read has settled. */
export function settledAccount(): string | null {
  return settled?.account ?? null
}
