/**
 * Layout twins (EN-03). A component that renders one chip in two responsive layouts, with CSS showing
 * one (FinancialMetricsTable: its phone cards and its md+ table), marks both copies `data-layout-twin`
 * with the same per-instance key. Anything that remembers a chip as a focus target reads it through
 * here: SourceTrace's own sheet and popover, and the research pane's opener (FilingViewerContext). A
 * breakpoint that hid the remembered copy then sends focus to the copy now shown, never to a
 * display:none element, where focus() does nothing and focus falls to <body>.
 */

/** The rendered copy paired with `el` by `data-layout-twin`, other than `el` itself; null when there is none. */
export function shownTwin(el: HTMLElement, key: string | undefined = el.dataset.layoutTwin): HTMLElement | null {
  if (!key) return null
  const copies = Array.from(document.querySelectorAll<HTMLElement>('[data-layout-twin]'))
  return copies.find((copy) => copy !== el && copy.dataset.layoutTwin === key && copy.getClientRects().length > 0) ?? null
}

/** `el` while it is rendered; its rendered twin once a breakpoint has hidden it; otherwise `el` as it is. */
export function renderedCopy(el: HTMLElement | null): HTMLElement | null {
  if (!el || !el.dataset.layoutTwin || el.getClientRects().length > 0) return el
  return shownTwin(el) ?? el
}
