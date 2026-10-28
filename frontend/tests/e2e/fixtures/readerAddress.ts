import type { Locator } from '@playwright/test'

/** Where a reader's own address paints when a sentence sets it (chief design on #1745). An address has no break
 *  opportunity, so under 200% text one longer than the line ran past its paragraph until it took `break-words`, and it
 *  breaks after its @ before anywhere else (AddressText, chief design on #1750). Read inside `scope`: the address's
 *  boxes that leave its paragraph and those that leave the screen, the text it paints on each line, what scrolls
 *  sideways, and whether the page does. */
export type AddressFit = { found: boolean; past: string[]; offscreen: string[]; pieces: string[]; scrolls: string[]; page: string | null }

/** The address read whole, or broken after its @ and nowhere else. */
export const atItsAt = (address: string) => [[address], [address.slice(0, address.lastIndexOf('@') + 1), address.slice(address.lastIndexOf('@') + 1)]]

export const addressFit = (scope: Locator, email: string): Promise<AddressFit> =>
  scope.evaluate((root, address): AddressFit => {
    // The address's own element: a span or strong in a sentence, or a paragraph that holds it alone (/check-email,
    // the settings page's Profile card). A paragraph that sets it in a sentence holds more text, so never matches.
    const holder = [...root.querySelectorAll('span, strong, p')].find((el) => el.textContent === address)
    if (!holder) return { found: false, past: [], offscreen: [], pieces: [], scrolls: [], page: null }
    const paragraph = holder.closest('p')!.getBoundingClientRect()
    const doc = document.documentElement
    const boxes = [...holder.getClientRects()]
    const span = (r: DOMRect) => `${Math.round(r.left)}-${Math.round(r.right)}px`
    const past = boxes
      .filter((r) => r.left < paragraph.left - 0.5 || r.right > paragraph.right + 0.5)
      .map((r) => `${span(r)} in ${Math.round(paragraph.left)}-${Math.round(paragraph.right)}px`)
    const offscreen = boxes.filter((r) => r.left < -0.5 || r.right > doc.clientWidth + 0.5).map((r) => `${span(r)} on a ${doc.clientWidth}px screen`)
    // Each character's line, read from its own box, so a break shows where it falls.
    const lines = new Map<number, string>()
    const walker = document.createTreeWalker(holder, NodeFilter.SHOW_TEXT)
    while (walker.nextNode()) {
      const text = walker.currentNode as Text
      for (let i = 0; i < text.length; i += 1) {
        const range = document.createRange()
        range.setStart(text, i)
        range.setEnd(text, i + 1)
        const top = Math.round(range.getBoundingClientRect().top)
        lines.set(top, (lines.get(top) ?? '') + text.data[i])
      }
    }
    const pieces = [...lines.entries()].sort(([a], [b]) => a - b).map(([, piece]) => piece)
    const scrolls = [root, ...root.querySelectorAll('*')]
      .filter((el) => el.scrollWidth > el.clientWidth + 1 && ['auto', 'scroll'].includes(getComputedStyle(el).overflowX))
      .map((el) => `<${el.tagName.toLowerCase()}> ${el.scrollWidth}px in ${el.clientWidth}px`)
    const page = doc.scrollWidth > doc.clientWidth ? `${doc.scrollWidth}px in ${doc.clientWidth}px` : null
    return { found: true, past, offscreen, pieces, scrolls, page }
  }, email)
