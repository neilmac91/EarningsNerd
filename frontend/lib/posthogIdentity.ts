/**
 * An account must not outlive its reader in PostHog's storage. posthog-js keeps an identified reader's id across page
 * loads until reset(), and reset() works only on a loaded client. When the account goes away while PostHog is not
 * loaded on the page (analytics refused or not chosen yet), lib/analytics.ts leaves word here, and the provider resets
 * the kept identity the next time PostHog loads, before it sends anything (app/posthog-provider.tsx). The word is a
 * flag in this origin's storage; it names no account. Storage that cannot be read or written leaves the provider's
 * check for a browser without a session in place.
 */
const FORGET_KEY = 'en_posthog_forget_account'

export function markAccountToForget(): void {
  try {
    window.localStorage.setItem(FORGET_KEY, '1')
  } catch {
    /* storage blocked */
  }
}

/** Whether an account went away while PostHog was not loaded; reading it clears the word. */
export function takeAccountToForget(): boolean {
  try {
    const pending = window.localStorage.getItem(FORGET_KEY) === '1'
    window.localStorage.removeItem(FORGET_KEY)
    return pending
  } catch {
    return false
  }
}
