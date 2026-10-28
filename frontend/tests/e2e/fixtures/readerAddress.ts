import type { Locator } from '@playwright/test'

/** Where a reader's own address paints when a sentence sets it (chief design on #1745). An address has no break
 *  opportunity, so under 200% text one longer than the line ran past its paragraph until it took `break-words`. Read
 *  inside `scope`: the address's boxes that leave its paragraph, the lines it takes, what scrolls sideways, and
 *  whether the page does. */
export type AddressFit = { found: boolean; past: string[]; lines: number; scrolls: string[]; page: string | null }

export const addressFit = (scope: Locator, email: string): Promise<AddressFit> =>
  scope.evaluate((root, address): AddressFit => {
    const holder = [...root.querySelectorAll('span, strong')].find((el) => el.textContent === address)
    if (!holder) return { found: false, past: [], lines: 0, scrolls: [], page: null }
    const paragraph = holder.closest('p')!.getBoundingClientRect()
    const boxes = [...holder.getClientRects()]
    const past = boxes
      .filter((r) => r.left < paragraph.left - 0.5 || r.right > paragraph.right + 0.5)
      .map((r) => `${Math.round(r.left)}-${Math.round(r.right)}px in ${Math.round(paragraph.left)}-${Math.round(paragraph.right)}px`)
    const scrolls = [root, ...root.querySelectorAll('*')]
      .filter((el) => el.scrollWidth > el.clientWidth + 1 && ['auto', 'scroll'].includes(getComputedStyle(el).overflowX))
      .map((el) => `<${el.tagName.toLowerCase()}> ${el.scrollWidth}px in ${el.clientWidth}px`)
    const doc = document.documentElement
    const page = doc.scrollWidth > doc.clientWidth ? `${doc.scrollWidth}px in ${doc.clientWidth}px` : null
    return { found: true, past, lines: new Set(boxes.map((r) => Math.round(r.top))).size, scrolls, page }
  }, email)
