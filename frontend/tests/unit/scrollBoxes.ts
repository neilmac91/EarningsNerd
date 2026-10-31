import { vi } from 'vitest'

/**
 * jsdom lays nothing out and scrolls nothing. These give the specs the geometry a scroll box has, a watch on the calls
 * that move the page and on each focus's options, and ResizeObservers that report when told, so a reveal can be read as
 * what it scrolls (CopilotComposer's revealInScrollBox, E248).
 */

export const rect = (top: number, height: number) =>
  ({ x: 0, y: top, top, bottom: top + height, left: 0, right: 300, width: 300, height, toJSON: () => ({}) }) as DOMRect

/** Give `box` a scroll box's overflow and on-screen rect, and record each write to its scrollTop. `set` moves it without
 *  a write, as the reader's own scroll does; `resize` changes its height with its top in place, as a pane that settles
 *  does. */
export function scrollBox(box: HTMLElement, top: number, height: number) {
  box.style.overflowY = 'auto'
  const writes: number[] = []
  let scrollTop = 0
  let clientHeight = height
  Object.defineProperty(box, 'scrollTop', {
    configurable: true,
    get: () => scrollTop,
    set: (value: number) => {
      scrollTop = value
      writes.push(value)
    },
  })
  Object.defineProperty(box, 'clientHeight', { configurable: true, get: () => clientHeight })
  box.getBoundingClientRect = () => rect(top, clientHeight)
  return {
    writes,
    get scrollTop() {
      return scrollTop
    },
    set: (value: number) => {
      scrollTop = value
    },
    resize: (value: number) => {
      clientHeight = value
    },
    reset: () => {
      scrollTop = 0
      writes.length = 0
    },
  }
}

/** The calls that move the page (scrollIntoView, and the window's scrollTo and scrollBy), and the options each focus was
 *  given: a focus without preventScroll is the browser's own reveal, which jsdom lacks. A write to the document's own
 *  scrollTop goes unwatched; the e2e reads the page's scroll. `restore` undoes the watch. */
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

/** ResizeObservers that report when a spec says so: `resize(el)` runs each one watching `el`, as the browser does once
 *  `el` changes size. Unlike the browser's, they send no first report as they start observing. Install before render;
 *  `restore` puts back the observer the setup installed. */
export function watchResizes() {
  let watching: { target: Element; observer: ResizeObserver; callback: ResizeObserverCallback }[] = []
  class Observer {
    constructor(private readonly callback: ResizeObserverCallback) {}
    observe(target: Element) {
      watching.push({ target, observer: this as unknown as ResizeObserver, callback: this.callback })
    }
    unobserve(target: Element) {
      watching = watching.filter((w) => w.observer !== (this as unknown) || w.target !== target)
    }
    disconnect() {
      watching = watching.filter((w) => w.observer !== (this as unknown))
    }
  }
  const setup = globalThis.ResizeObserver
  globalThis.ResizeObserver = Observer as unknown as typeof ResizeObserver
  return {
    resize: (el: Element) => {
      for (const { target, observer, callback } of watching) if (target === el) callback([], observer)
    },
    restore: () => {
      globalThis.ResizeObserver = setup
    },
  }
}
