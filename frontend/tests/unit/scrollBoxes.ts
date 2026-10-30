import { vi } from 'vitest'

/**
 * jsdom lays nothing out and scrolls nothing. These give the specs the geometry a scroll box has and a watch on every way
 * the page could move, so a reveal can be read as what it scrolls (CopilotComposer's revealInScrollBox, E248).
 */

export const rect = (top: number, height: number) =>
  ({ x: 0, y: top, top, bottom: top + height, left: 0, right: 300, width: 300, height, toJSON: () => ({}) }) as DOMRect

/** Give `box` a scroll box's overflow and on-screen rect, and record each write to its scrollTop. `set` moves it without
 *  a write, as the reader's own scroll does. */
export function scrollBox(box: HTMLElement, top: number, height: number) {
  box.style.overflowY = 'auto'
  const writes: number[] = []
  let scrollTop = 0
  Object.defineProperty(box, 'scrollTop', {
    configurable: true,
    get: () => scrollTop,
    set: (value: number) => {
      scrollTop = value
      writes.push(value)
    },
  })
  Object.defineProperty(box, 'clientHeight', { configurable: true, get: () => height })
  box.getBoundingClientRect = () => rect(top, height)
  return {
    writes,
    get scrollTop() {
      return scrollTop
    },
    set: (value: number) => {
      scrollTop = value
    },
    reset: () => {
      scrollTop = 0
      writes.length = 0
    },
  }
}

/** Every way the page itself could move (the browser's own reveal, which jsdom lacks, and the window's scroll), and the
 *  options each focus was given. `restore` undoes the watch. */
export function watchThePage() {
  const moves: string[] = []
  const jsdomScrollIntoView = Element.prototype.scrollIntoView
  Element.prototype.scrollIntoView = vi.fn(() => {
    moves.push('scrollIntoView')
  })
  const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {
    moves.push('scrollTo')
  })
  const scrollBy = vi.spyOn(window, 'scrollBy').mockImplementation(() => {
    moves.push('scrollBy')
  })
  const focus = vi.spyOn(HTMLElement.prototype, 'focus')
  return {
    moves,
    focusOptions: (el: Element) => focus.mock.contexts.flatMap((ctx, i) => (ctx === el ? [focus.mock.calls[i][0]] : [])),
    restore: () => {
      Element.prototype.scrollIntoView = jsdomScrollIntoView
      scrollTo.mockRestore()
      scrollBy.mockRestore()
      focus.mockRestore()
    },
  }
}
