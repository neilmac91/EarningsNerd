/**
 * An account must not outlive its reader in PostHog's storage. posthog-js keeps an identified reader's id across page
 * loads until reset(), and reset() works only on a loaded client. lib/analytics.ts's forgetAccount, which the
 * identification hook calls for every guest and whenever the account goes, cannot reset while PostHog is not loaded on
 * the page (analytics refused or not chosen yet). It leaves word here instead, and the provider resets an identity
 * PostHog kept the next time it loads, before it sends anything (app/posthog-provider.tsx).
 *
 * The word is a flag in this origin's local storage; it names no account. It is left only where PostHog has stored
 * something, which needs an allow first, so a browser that never allowed analytics gets nothing. Storage that cannot be
 * read or written leaves the provider's check for a browser without a session in place.
 */
const FORGET_KEY = 'en_posthog_forget_account'
// posthog-js's own entry, `ph_<project key>_posthog`: a cookie that holds the identity, and a local-storage entry of the
// same name that holds it where cookies cannot.
const POSTHOG_ENTRY = /^ph_.+_posthog$/

function postHogStoredHere(): boolean {
  try {
    const cookies = document.cookie.split(';').map(cookie => cookie.split('=')[0].trim())
    const entries = Array.from({ length: window.localStorage.length }, (_, i) => window.localStorage.key(i) ?? '')
    return [...cookies, ...entries].some(name => POSTHOG_ENTRY.test(name))
  } catch {
    return false
  }
}

export function markAccountToForget(): void {
  if (!postHogStoredHere()) return
  try {
    window.localStorage.setItem(FORGET_KEY, '1')
  } catch {
    /* storage blocked */
  }
}

/** Whether an account may have gone while PostHog was not loaded; reading it clears the word. */
export function takeAccountToForget(): boolean {
  try {
    const pending = window.localStorage.getItem(FORGET_KEY) === '1'
    window.localStorage.removeItem(FORGET_KEY)
    return pending
  } catch {
    return false
  }
}
