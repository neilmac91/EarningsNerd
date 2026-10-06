/**
 * The consent layer: how the cookie-consent bar tells the rest of the chrome that it is there.
 *
 * The bar is fixed to the bottom of the viewport on `z-consent` (35): above the page's own chrome
 * (in-page sticky chrome rides z-sticky 30, and a sticky section nav passing through the bar's
 * region must not paint over a consent choice) and above the z-30 workspace scrims, BENEATH the
 * research chrome it used to cover — the z-40 workspace sheets, "Ask this Filing" launcher and
 * coachmark (DESIGN_SYSTEM §4 Stacking). A lower z alone would let that chrome cover a consent
 * choice, so while the bar is mounted it publishes its height on <html>: `--consent-inset` (a CSS
 * length) and `data-consent-visible`. The bottom-anchored chrome adds the inset to its bottom
 * offset (BOTTOM_CHROME_OFFSET for the inline-positioned launchers and coachmark, the
 * `bottom-[var(--consent-inset,0px)]` class on the sheets, the desktop pane's sticky height), and
 * the document's scroll-padding-bottom (app/globals.css) reserves the same height, so a focus or
 * scrollIntoView never lands a control behind the bar (the desktop pane's composer, focused on
 * open, scrolls clear of it). Both sets of controls stay visible and operable. Without the bar the
 * property is unset and every consumer falls back to 0px, exactly where it sat before.
 *
 * React consumers that need the boolean (FilingWorkspace keeps the coachmark quiet while the bar
 * is visible, so it never points at a covered launcher) read it through hooks/useConsentLayer,
 * which subscribes to CONSENT_LAYER_EVENT. The server never renders the bar, so the attribute and
 * property appear only after hydration: SSR markup stays deterministic and nothing mismatches.
 *
 * This module changes nothing about consent itself: what is stored, the `cookieConsentChanged`
 * event and the analytics gating stay in components/CookieConsent.tsx.
 *
 * Gate: tests/unit/bottomChromeLadder.spec.ts (no fixed chrome outranks the workspace layers at
 * the launcher corner; the pinned bottom chrome takes this inset).
 */
export const CONSENT_INSET_PROPERTY = '--consent-inset'
export const CONSENT_VISIBLE_ATTRIBUTE = 'data-consent-visible'
export const CONSENT_LAYER_EVENT = 'consentLayerChanged'

/** The bar's height while it is mounted, else 0 — a CSS length for calc(). */
export const CONSENT_INSET = `var(${CONSENT_INSET_PROPERTY}, 0px)`

/**
 * Bottom offset for the fixed launchers (Ask, Feedback) and the coachmark: a 1.25rem base gap, the
 * device's bottom safe-area inset on notched phones (viewport-fit=cover in app/layout.tsx) and the
 * consent bar's height while it is mounted. The bar carries the safe-area padding itself, so above
 * it the gap is 1.25rem from its top edge: `max(1.25rem, safe - inset)` is `max(1.25rem, safe)`
 * without the bar and `1.25rem` with it (the bar is at least as tall as the safe-area inset).
 */
export const BOTTOM_CHROME_OFFSET = `calc(max(1.25rem, env(safe-area-inset-bottom) - ${CONSENT_INSET}) + ${CONSENT_INSET})`

export interface ConsentLayerDetail {
  visible: boolean
  /** The bar's measured height in CSS px (0 while visible but not yet measured). */
  height: number
}

/** Called by CookieConsent with the bar's current height, or null once the bar is gone. */
export function publishConsentLayer(height: number | null): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (height === null) {
    root.style.removeProperty(CONSENT_INSET_PROPERTY)
    root.removeAttribute(CONSENT_VISIBLE_ATTRIBUTE)
  } else {
    root.style.setProperty(CONSENT_INSET_PROPERTY, `${Math.ceil(height)}px`)
    root.setAttribute(CONSENT_VISIBLE_ATTRIBUTE, 'true')
  }
  const detail: ConsentLayerDetail = { visible: height !== null, height: height ?? 0 }
  window.dispatchEvent(new CustomEvent<ConsentLayerDetail>(CONSENT_LAYER_EVENT, { detail }))
}

/** Whether the bar is on screen right now (false on the server). */
export function isConsentLayerVisible(): boolean {
  return typeof document !== 'undefined' && document.documentElement.hasAttribute(CONSENT_VISIBLE_ATTRIBUTE)
}

/** useSyncExternalStore-shaped subscription to the bar coming and going. */
export function subscribeConsentLayer(onChange: () => void): () => void {
  if (typeof window === 'undefined') return () => {}
  window.addEventListener(CONSENT_LAYER_EVENT, onChange)
  return () => window.removeEventListener(CONSENT_LAYER_EVENT, onChange)
}
