import { SESSION_KEY } from '@/lib/api/session'

/**
 * The pricing page's first paint takes a returning reader's plan from a hint, not a read (E228).
 *
 * /pricing is a static page, so its first paint knows nothing of the reader: the usage card that holds its place from
 * the identity read's answer (E226) mounted only then, and a Pro account's billing switch left only then (E227), and
 * a signed-in reader's plans moved down as the read answered. Two values in the browser already say who is likely
 * reading: the API client's session flag (lib/api/session.ts), set by a sign-in and cleared by a logout or by an
 * identity read that finds no session, and the plan this page last named, written here once the identity read
 * answers. A script before the plans marks the document from both (`data-pricing-hint`, "free" or "pro"), and the
 * card and the switch take the plan's place from the first paint, by CSS alone, so the page stays static. A hint left
 * from a session that has since lapsed moves a guest's plans up once: that read clears the flag, so the next load
 * paints as a guest's.
 */
export const PRICING_PLAN_KEY = 'en_pricing_plan'

/** The script that marks the document before the plans paint. Storage it cannot read leaves the page unmarked. */
export const PRICING_HINT_BOOTSTRAP = `(function(){try{
  if (localStorage.getItem(${JSON.stringify(SESSION_KEY)}) === '1')
    document.documentElement.dataset.pricingHint = localStorage.getItem(${JSON.stringify(PRICING_PLAN_KEY)}) === 'pro' ? 'pro' : 'free';
}catch(e){}})();`

/** Records the plan the identity read named, or a guest, for the next load, and keeps this document's mark with it. */
export function rememberPricingPlan(user: { is_pro?: boolean } | null): void {
  const root = document.documentElement
  if (user) root.dataset.pricingHint = user.is_pro ? 'pro' : 'free'
  else delete root.dataset.pricingHint
  try {
    if (user) window.localStorage.setItem(PRICING_PLAN_KEY, user.is_pro ? 'pro' : 'free')
    else window.localStorage.removeItem(PRICING_PLAN_KEY)
  } catch {
    // Storage unavailable: the next load paints unmarked, as before E228.
  }
}
