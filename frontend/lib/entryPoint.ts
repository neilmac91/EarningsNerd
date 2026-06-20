// Activation-funnel attribution: where did the session that led here enter the app?
//
// An explicit `?entry=` param (set by CTAs, e.g. the homepage "see an example" link) wins;
// otherwise the document referrer identifies the session's acquisition path. `document.referrer`
// is fixed per document load, so client-side navigations report the session's original entry —
// which is the segmentation the activation funnel cares about.
//
// Shared by the filing and company pages so `company_viewed` / `filing_viewed` / `summary_viewed`
// all attribute to the same source.
export const getEntryPoint = (): string => {
  if (typeof window === 'undefined') return 'unknown'
  const explicit = new URLSearchParams(window.location.search).get('entry')
  if (explicit) return explicit.slice(0, 64)
  const referrer = document.referrer
  if (!referrer) return 'direct'
  try {
    const ref = new URL(referrer)
    if (ref.origin !== window.location.origin) return 'external'
    if (ref.pathname === '/') return 'homepage'
    if (ref.pathname === '/waitlist') return 'waitlist'
    if (ref.pathname.startsWith('/company/')) return 'company_page'
    // Exact-or-subpath so '/compared' / '/compare-plans' don't false-match (consistent with
    // the '/company/' check above).
    if (ref.pathname === '/compare' || ref.pathname.startsWith('/compare/')) return 'compare'
    return 'internal'
  } catch {
    return 'unknown'
  }
}
