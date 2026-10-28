import type { Locator } from '@playwright/test'

/** Where a reader's own address paints when a sentence sets it (chief design on #1745). An address has no break
 *  opportunity, so under 200% text one longer than the line ran past its paragraph until it took `break-words`. Read
 *  inside `scope`: the address's boxes that leave its paragraph and those that leave the screen, the lines it takes,
 *  what scrolls sideways, and whether the page does. */
export type AddressFit = { found: boolean; past: string[]; offscreen: string[]; lines: number; scrolls: string[]; page: string | null }

export const addressFit = (scope: Locator, email: string): Promise<AddressFit> =>
  scope.evaluate((root, address): AddressFit => {
    const holder = [...root.querySelectorAll('span, strong')].find((el) => el.textContent === address)
    if (!holder) return { found: false, past: [], offscreen: [], lines: 0, scrolls: [], page: null }
    const paragraph = holder.closest('p')!.getBoundingClientRect()
    const doc = document.documentElement
    const boxes = [...holder.getClientRects()]
    const span = (r: DOMRect) => `${Math.round(r.left)}-${Math.round(r.right)}px`
    const past = boxes
      .filter((r) => r.left < paragraph.left - 0.5 || r.right > paragraph.right + 0.5)
      .map((r) => `${span(r)} in ${Math.round(paragraph.left)}-${Math.round(paragraph.right)}px`)
    const offscreen = boxes.filter((r) => r.left < -0.5 || r.right > doc.clientWidth + 0.5).map((r) => `${span(r)} on a ${doc.clientWidth}px screen`)
    const scrolls = [root, ...root.querySelectorAll('*')]
      .filter((el) => el.scrollWidth > el.clientWidth + 1 && ['auto', 'scroll'].includes(getComputedStyle(el).overflowX))
      .map((el) => `<${el.tagName.toLowerCase()}> ${el.scrollWidth}px in ${el.clientWidth}px`)
    const page = doc.scrollWidth > doc.clientWidth ? `${doc.scrollWidth}px in ${doc.clientWidth}px` : null
    return { found: true, past, offscreen, lines: new Set(boxes.map((r) => Math.round(r.top))).size, scrolls, page }
  }, email)
