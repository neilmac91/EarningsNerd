/**
 * For a mutation whose success navigates the whole page away (`window.location.href = …`, e.g. to
 * Stripe): return this from `onSuccess` so the control stays busy while the page leaves, since a
 * focused button that went live again would take a second Enter and open a second session.
 *
 * It settles when the page is still the user's after all:
 * - on `pageshow`, a back-forward cache restore, which brings the page back with the button live;
 * - on the Navigation API's `navigateerror`, which Chromium fires when the pending cross-document
 *   navigation is aborted (the user pressed Esc or Stop, or `window.stop()`).
 *
 * A navigation that is only slow fires neither, so the button stays busy for as long as it takes.
 * Where the Navigation API is missing, an aborted navigation fires nothing at all. There it falls back
 * to settling after `timeoutMs`, so the button cannot stay busy until a reload. The cost is a possible
 * second session if a navigation takes longer than that, which is harmless.
 */
export const PAGE_LEAVE_TIMEOUT_MS = 10_000

export function untilPageReturns(timeoutMs: number = PAGE_LEAVE_TIMEOUT_MS): Promise<void> {
  return new Promise((resolve) => {
    const navigation = 'navigation' in window ? window.navigation : undefined
    let timer: number | undefined
    const settle = () => {
      window.removeEventListener('pageshow', settle)
      navigation?.removeEventListener('navigateerror', settle)
      window.clearTimeout(timer)
      resolve()
    }
    window.addEventListener('pageshow', settle)
    if (navigation) navigation.addEventListener('navigateerror', settle)
    else timer = window.setTimeout(settle, timeoutMs)
  })
}
