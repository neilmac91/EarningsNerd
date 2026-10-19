/**
 * Turn a matched citation excerpt into an on-screen highlight inside the rendered filing (P7b).
 *
 * Builds a flat-text projection of the container's text nodes (with an offset→node map), runs the
 * pure {@link findExcerptMatch} matcher, maps the resulting offsets back to a DOM Range, then:
 *   - paints the exact span via the CSS Custom Highlight API when supported (`::highlight(...)`), in
 *     the device's paint when the server located the passage and in the neutral find paint otherwise,
 *   - flashes the enclosing block (works everywhere, incl. browsers without the Highlight API),
 *   - scrolls the passage into view inside the container, and only there.
 * Returns true when the text was found in the container and highlighted.
 */
import { findExcerptMatch } from './excerptMatch'
import { flashElement } from '@/lib/citationFlash'
import { prefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { CONSENT_INSET_PROPERTY } from '@/lib/consentLayer'

/** The device's highlight: a passage the server located (D-044). */
const LOCATED_HIGHLIGHT = 'copilot-citation'
/** The neutral find highlight: where a jump the server did not locate landed. */
const FIND_HIGHLIGHT = 'copilot-find'

/**
 * Paint for `::highlight(copilot-citation)`: the brand device's mark on a passage the server located
 * (D-044), so a located passage looks the same in the reader as on the landing page. It takes `.en-mark`'s
 * tint and 2px hairline from app/globals.css, light and dark (a `.dark` rule, as globals.css pairs the
 * device; tests/unit/highlightInDom.spec.ts holds the values to the stylesheet's). The Highlight API
 * paints colours and text decorations only, so the tint fills the passage's content area (`.en-mark`
 * starts it at 62% of the line box) and the hairline is a 2px underline, unbroken by descenders, set
 * where the tint ends: Newsreader's content area ends 0.2632em below the baseline, measured in Chromium.
 * The passage reads in the primary ink, as the landing's marked block does: the reader's secondary ink
 * measures 4.49:1 on the dark tint over the slate panel, under the 4.5:1 floor.
 * Registered from here as a constructed stylesheet rather than in `app/globals.css`: lightningcss
 * (Next 16.3's CSS pipeline) does not know the `::highlight()` pseudo-element: it emits a
 * SelectorError warning and, with error recovery, keeps the rule, but Next's build surfaces that as
 * "Parsing CSS source code failed" on every build. It only ever runs where the Highlight API exists,
 * which implies constructable stylesheets too.
 */
/* eslint-disable no-restricted-syntax -- a constructed stylesheet has no Tailwind token: these are .en-mark's tint and hairline (brand-weak, brand-border and their dark pair) and the primary ink pair, and the find paint's brand sage at 22%, held to app/globals.css and tailwind.config.js by tests/unit/highlightInDom.spec.ts. */
export const CITATION_HIGHLIGHT_CSS = [
  `::highlight(${LOCATED_HIGHLIGHT}) { background-color: #ECF2EE; color: #1A1A17; text-decoration: underline 2px #CFE0D6; text-decoration-skip-ink: none; text-underline-offset: calc(0.2632em - 2px); }`,
  `.dark ::highlight(${LOCATED_HIGHLIGHT}) { background-color: rgba(127, 178, 149, 0.14); color: #D7DADC; text-decoration-color: rgba(127, 178, 149, 0.28); }`,
].join('\n')

/**
 * Paint for `::highlight(copilot-find)`: where a jump the server did not locate lands, so the reader still
 * sees where it landed: a summary chip's section heading (every metric chip, a verified XBRL figure's
 * included, and every Cited chip), or the text an XBRL fact's jump found. Nothing unlocated takes the
 * device (D-044), so this is the reader's neutral sage from before it: the brand sage at 22%, one rule for
 * both themes as it was, in the reader's own ink, with no hairline.
 */
export const FIND_HIGHLIGHT_CSS = `::highlight(${FIND_HIGHLIGHT}) { background-color: rgba(79, 122, 99, 0.22); color: inherit; }`
/* eslint-enable no-restricted-syntax */

let highlightSheet: CSSStyleSheet | null = null

/**
 * Adopt the two highlights' rules once per document, in one sheet. Safe to call repeatedly: the
 * memo alone is not trusted — if some other code reassigned `document.adoptedStyleSheets` without
 * spreading the existing list, our sheet is gone while the memo says installed, so re-adopt.
 */
export function ensureCitationHighlightStyle(): void {
  if (highlightSheet && document.adoptedStyleSheets.includes(highlightSheet)) return
  try {
    const sheet = highlightSheet ?? new CSSStyleSheet()
    if (!highlightSheet) sheet.replaceSync(`${CITATION_HIGHLIGHT_CSS}\n${FIND_HIGHLIGHT_CSS}`)
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

/** The consent bar's height while it shows (lib/consentLayer publishes it on <html>), else 0. */
const consentInset = () => parseFloat(document.documentElement.style.getPropertyValue(CONSENT_INSET_PROPERTY)) || 0

/**
 * Bring `target` into view inside `container` and nowhere else (EN-04). Each scroll box from the
 * target up to and including the container moves: a wide table's own box sideways to its nearest
 * edge, the reader down or up so the passage sits in the middle of its on-screen part (or starts at
 * its top when it is the taller of the two). Each box sees the target where the boxes inside it will have moved it. Nothing
 * outside the container scrolls: scrollIntoView scrolled every scrollable ancestor, the page
 * included, and with a reader wider than its pane that slid the whole filing page sideways. The
 * scroll is smooth, except under prefers-reduced-motion, where it jumps ('auto': neither the reader
 * nor a table's box sets a scroll-behavior). jsdom and old engines have no Element.scrollTo: the
 * offsets are assigned instead.
 */
function revealWithin(container: HTMLElement, target: HTMLElement): void {
  if (target === container || !container.contains(target)) return
  const behavior: ScrollBehavior = prefersReducedMotion() ? 'auto' : 'smooth'
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
      // Centre in the part of the box on screen: before the desktop pane sticks, its lower part sits
      // below the fold (and the consent bar covers the bottom while it shows), and this never scrolls
      // the page to make up for it. A box wholly off screen centres in its own height.
      const viewTop = Math.max(top, 0)
      const viewBottom = Math.min(top + box.clientHeight, window.innerHeight - consentInset())
      const [from, height] = viewBottom > viewTop ? [viewTop, viewBottom - viewTop] : [top, box.clientHeight]
      y += tTop - from - Math.max(0, (height - (tBottom - tTop)) / 2)
      y = clamp(y, box.scrollHeight - box.clientHeight)
    }
    const dx = x - box.scrollLeft
    const dy = y - box.scrollTop
    if (!dx && !dy) continue
    const to: ScrollToOptions = {}
    if (dx) to.left = x
    if (dy) to.top = y
    if (typeof box.scrollTo === 'function') {
      box.scrollTo({ ...to, behavior })
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
  if (!highlights) return
  highlights.delete(LOCATED_HIGHLIGHT)
  highlights.delete(FIND_HIGHLIGHT)
}

/**
 * `located` says the server located the passage (D-044): only then does it take the device's highlight.
 * Anything else, and a caller that does not say, lands in the neutral find highlight. One of the two is
 * registered at a time.
 */
export function highlightExcerptInDom(container: HTMLElement, excerpt: string, { located = false }: { located?: boolean } = {}): boolean {
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
    highlights.delete(LOCATED_HIGHLIGHT)
    highlights.delete(FIND_HIGHLIGHT)
    highlights.set(located ? LOCATED_HIGHLIGHT : FIND_HIGHLIGHT, new w.Highlight(range))
  }

  flashBlock(startLoc.node)

  const target = startLoc.node.parentElement
  if (target) revealWithin(container, target)
  return true
}
