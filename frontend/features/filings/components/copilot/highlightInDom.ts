/**
 * Turn a matched citation excerpt into an on-screen highlight inside the rendered filing (P7b).
 *
 * Builds a flat-text projection of the container's text nodes (with an offset→node map), runs the
 * pure {@link findExcerptMatch} matcher, maps the resulting offsets back to a DOM Range, then:
 *   - paints the exact span via the CSS Custom Highlight API when supported (`::highlight(...)`),
 *   - flashes the enclosing block (works everywhere, incl. browsers without the Highlight API),
 *   - scrolls the passage into view inside the container, and only there.
 * Returns true when a passage was located and highlighted.
 */
import { findExcerptMatch } from './excerptMatch'
import { flashElement } from '@/lib/citationFlash'

const HIGHLIGHT_NAME = 'copilot-citation'

/**
 * Paint for `::highlight(copilot-citation)`. Registered from here as a constructed stylesheet rather
 * than in `app/globals.css`: lightningcss (Next 16.3's CSS pipeline) does not know the `::highlight()`
 * pseudo-element — it emits a SelectorError warning and, with error recovery, keeps the rule, but
 * Next's build surfaces that as "Parsing CSS source code failed" on every build. Same visual as
 * before — the sage of `.citation-flash`, 22% — and it only ever runs where the Highlight API exists,
 * which implies constructable stylesheets too.
 */
export const CITATION_HIGHLIGHT_CSS = `::highlight(${HIGHLIGHT_NAME}) { background-color: rgba(79, 122, 99, 0.22); color: inherit; }`

let highlightSheet: CSSStyleSheet | null = null

/**
 * Adopt the `::highlight(copilot-citation)` rule once per document. Safe to call repeatedly: the
 * memo alone is not trusted — if some other code reassigned `document.adoptedStyleSheets` without
 * spreading the existing list, our sheet is gone while the memo says installed, so re-adopt.
 */
export function ensureCitationHighlightStyle(): void {
  if (highlightSheet && document.adoptedStyleSheets.includes(highlightSheet)) return
  try {
    const sheet = highlightSheet ?? new CSSStyleSheet()
    if (!highlightSheet) sheet.replaceSync(CITATION_HIGHLIGHT_CSS)
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]
    highlightSheet = sheet
  } catch {
    // No constructable stylesheets (jsdom, very old engines): the block flash below still shows.
  }
}

/** Test-only: forget the adopted sheet so each spec starts from a fresh document. */
export function __resetCitationHighlightStyleForTests(): void {
  highlightSheet = null
}

interface NodeSpan {
  node: Text
  start: number
}

function buildFlatText(container: HTMLElement): { text: string; nodes: NodeSpan[] } {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  let text = ''
  const nodes: NodeSpan[] = []
  let node = walker.nextNode() as Text | null
  while (node) {
    nodes.push({ node, start: text.length })
    text += node.data
    node = walker.nextNode() as Text | null
  }
  return { text, nodes }
}

function locate(nodes: NodeSpan[], offset: number, boundary: 'start' | 'end'): { node: Text; offset: number } | null {
  // Starts belong to their first character; exclusive ends belong to their last character.
  // Looking up the character (rather than the shared boundary) also skips empty text nodes.
  const characterOffset = boundary === 'end' ? offset - 1 : offset
  for (const span of nodes) {
    if (characterOffset >= span.start && characterOffset < span.start + span.node.data.length) {
      return { node: span.node, offset: offset - span.start }
    }
  }
  return null
}

function flashBlock(node: Node) {
  let el: HTMLElement | null = node.parentElement
  // Walk up to a block-ish element so the flash reads as a paragraph pulse, not a sub-span.
  while (el && el.parentElement && getComputedStyle(el).display === 'inline') {
    el = el.parentElement
  }
  if (!el) return
  flashElement(el)
}

/** A box that can scroll on this axis: its computed overflow there is auto, scroll or hidden. */
const SCROLLS = /^(auto|scroll|hidden)$/

const clamp = (value: number, max: number) => Math.min(Math.max(value, 0), Math.max(max, 0))

/**
 * Bring `target` into view inside `container` and nowhere else (EN-04). Each scroll box from the
 * target up to and including the container moves: a wide table's own box sideways to its nearest
 * edge, the reader down or up so the passage sits in its middle (or starts at its top when it is the
 * taller of the two). Each box sees the target where the boxes inside it will have moved it. Nothing
 * outside the container scrolls: scrollIntoView scrolled every scrollable ancestor, the page
 * included, and with a reader wider than its pane that slid the whole filing page sideways. jsdom
 * and old engines have no Element.scrollTo: the offsets are assigned instead.
 */
function revealWithin(container: HTMLElement, target: HTMLElement): void {
  if (target === container || !container.contains(target)) return
  let { left: tLeft, right: tRight, top: tTop, bottom: tBottom } = target.getBoundingClientRect()
  for (let box = target.parentElement; box; box = box === container ? null : box.parentElement) {
    const style = getComputedStyle(box)
    const b = box.getBoundingClientRect()
    const left = b.left + box.clientLeft
    const top = b.top + box.clientTop
    let x = box.scrollLeft
    let y = box.scrollTop
    if (SCROLLS.test(style.overflowX) && box.scrollWidth > box.clientWidth) {
      if (tLeft < left || tRight - tLeft > box.clientWidth) x += tLeft - left
      else if (tRight > left + box.clientWidth) x += tRight - (left + box.clientWidth)
      x = clamp(x, box.scrollWidth - box.clientWidth)
    }
    if (SCROLLS.test(style.overflowY) && box.scrollHeight > box.clientHeight) {
      y += tTop - top - Math.max(0, (box.clientHeight - (tBottom - tTop)) / 2)
      y = clamp(y, box.scrollHeight - box.clientHeight)
    }
    const dx = x - box.scrollLeft
    const dy = y - box.scrollTop
    if (!dx && !dy) continue
    const to: ScrollToOptions = {}
    if (dx) to.left = x
    if (dy) to.top = y
    if (typeof box.scrollTo === 'function') {
      box.scrollTo({ ...to, behavior: 'smooth' })
    } else {
      if (dx) box.scrollLeft = x
      if (dy) box.scrollTop = y
    }
    tLeft -= dx
    tRight -= dx
    tTop -= dy
    tBottom -= dy
  }
}

export function clearCitationHighlight(): void {
  const highlights = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights
  if (highlights) highlights.delete(HIGHLIGHT_NAME)
}

export function highlightExcerptInDom(container: HTMLElement, excerpt: string): boolean {
  const flat = buildFlatText(container)
  const match = findExcerptMatch(flat.text, excerpt)
  if (!match) return false

  const startLoc = locate(flat.nodes, match.start, 'start')
  const endLoc = locate(flat.nodes, match.end, 'end')
  if (!startLoc || !endLoc) return false

  const range = document.createRange()
  try {
    range.setStart(startLoc.node, startLoc.offset)
    range.setEnd(endLoc.node, endLoc.offset)
  } catch {
    return false
  }

  // Exact-span paint via the CSS Custom Highlight API (Chrome/Safari/modern FF). Feature-detected;
  // older browsers + jsdom simply skip this and rely on the block flash + scroll below.
  const w = window as unknown as { Highlight?: new (r: Range) => unknown }
  const highlights = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights
  if (typeof w.Highlight === 'function' && highlights) {
    ensureCitationHighlightStyle()
    highlights.delete(HIGHLIGHT_NAME)
    highlights.set(HIGHLIGHT_NAME, new w.Highlight(range))
  }

  flashBlock(startLoc.node)

  const target = startLoc.node.parentElement
  if (target) revealWithin(container, target)
  return true
}
