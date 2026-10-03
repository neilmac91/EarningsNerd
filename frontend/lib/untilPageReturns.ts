/**
 * For a mutation whose success navigates the whole page away (`window.location.href = …`, e.g. to
 * Stripe): return this from `onSuccess` so the control stays busy while the page leaves, since a
 * focused button that went live again would take a second Enter and open a second session.
 *
 * It settles on `pageshow` (a back-forward cache restore brings the page back with the button live)
 * or after `timeoutMs`, whichever comes first. The timeout covers a navigation that never commits
 * (the user pressed Esc or Stop), which fires no event, so the button would otherwise stay busy
 * until a reload.
 */
export const PAGE_LEAVE_TIMEOUT_MS = 10_000

export function untilPageReturns(timeoutMs: number = PAGE_LEAVE_TIMEOUT_MS): Promise<void> {
  return new Promise((resolve) => {
    const settle = () => {
      window.removeEventListener('pageshow', settle)
      window.clearTimeout(timer)
      resolve()
    }
    const timer = window.setTimeout(settle, timeoutMs)
    window.addEventListener('pageshow', settle)
  })
}
