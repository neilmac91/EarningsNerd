// The Trace-to-Source chip's class recipe, in a module without 'use client' so server components can call
// it too. A function exported from a 'use client' module is a client reference wherever server code
// imports it, and calling one on the server fails the prerender (lessons/frontend-client-exports-need-next-build.md;
// gate: tests/unit/serverCallsClientExport.spec.ts).

/**
 * The chip's full trigger className (2026-10 critique P-10): 12px/500 in the data face, 20px tall
 * (16px leading, 1px padding and a 1px hairline each side; no fixed or min height, so a long label
 * still wraps inside a phone card), a hairline pill on the panel fill with secondary ink that
 * brightens on hover. The 16px radius reads as a full pill on one line and as a rounded box when a
 * long label wraps (a 9999px radius turned a wrapped chip into a capsule). `selected` is the brand tint, for the chip whose passage the research pane is
 * showing. The verified/cited distinction lives in the glyph and the label, not the colour. Shared
 * so the landing page's Trace-to-Source demo and the homepage example render a chip identical to the
 * product's.
 */
export const sourceTraceChipClass = (selected = false): string => {
  const tone = selected
    ? 'border-brand-border bg-brand-weak text-brand-strong dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark'
    : 'border-border-light bg-panel-light text-text-secondary-light hover:bg-white dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:hover:bg-white/5'
  return `inline-flex items-center gap-1 rounded-xl border px-2 py-px text-left align-middle font-data text-xs font-medium leading-4 transition-colors duration-fast focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${tone}`
}
