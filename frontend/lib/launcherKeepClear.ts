/**
 * Regions the floating feedback launcher must not rest over (DESIGN_SYSTEM.md §4 Stacking): the analysis headline
 * figures, which mark their root `data-launcher-keep-clear`. The launcher steps aside while its box, GAP px around,
 * meets one: it fades and lets the pointer through to the figure beneath, and keyboard focus brings it back. It never
 * moves, so it stays one fixed site on its rung at BOTTOM_CHROME_OFFSET (tests/unit/bottomChromeLadder.spec.ts).
 * Only figures a reader can read count: a strip inside an `inert` or `aria-hidden="true"` subtree (PeekLocked's
 * blurred preview, the Free analysis teaser's) has nothing a tap could reach, so the launcher stays over it. The
 * landing's AnalysisDemo is neither, so its strip counts.
 *
 * Gates: tests/unit/feedback-launcher-keep-clear.spec.tsx (the rule and the launcher's classes) and
 * tests/e2e/feedback-launcher-keep-clear.spec.ts (a 390px phone: the figure under the launcher takes the pointer).
 */
export const LAUNCHER_KEEP_CLEAR_SELECTOR = '[data-launcher-keep-clear]'

/** The clearance around the launcher's box, in CSS px: a region nearer than this counts as under it. */
export const LAUNCHER_KEEP_CLEAR_GAP = 8

/** The subtrees whose regions do not count: a locked preview is both. */
const UNREADABLE = '[inert], [aria-hidden="true"]'

/** Whether any keep-clear region under `root` meets `box` grown by the gap on every side. A region that renders no
 *  box (display:none, or empty), or that sits in an inert or aria-hidden subtree, is skipped. */
export function overlapsKeepClear(box: Pick<DOMRect, 'top' | 'bottom' | 'left' | 'right'>, root: ParentNode = document): boolean {
  const gap = LAUNCHER_KEEP_CLEAR_GAP
  for (const el of root.querySelectorAll(LAUNCHER_KEEP_CLEAR_SELECTOR)) {
    if (el.closest(UNREADABLE)) continue
    const r = el.getBoundingClientRect()
    if (!r.width && !r.height) continue
    if (r.left < box.right + gap && r.right > box.left - gap && r.top < box.bottom + gap && r.bottom > box.top - gap) return true
  }
  return false
}
