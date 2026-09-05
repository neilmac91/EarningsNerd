/**
 * Turn a matched citation excerpt into an on-screen highlight inside the rendered filing (P7b).
 *
 * Builds a flat-text projection of the container's text nodes (with an offset→node map), runs the
 * pure {@link findExcerptMatch} matcher, maps the resulting offsets back to a DOM Range, then:
 *   - paints the exact span via the CSS Custom Highlight API when supported (`::highlight(...)`),
 *   - flashes the enclosing block (works everywhere, incl. browsers without the Highlight API),
 *   - scrolls the passage into view.
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

function locate(nodes: NodeSpan[], offset: number): { node: Text; offset: number } | null {
  for (const span of nodes) {
    if (offset >= span.start && offset <= span.start + span.node.data.length) {
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

export function clearCitationHighlight(): void {
  const highlights = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights
  if (highlights) highlights.delete(HIGHLIGHT_NAME)
}

export function highlightExcerptInDom(container: HTMLElement, excerpt: string): boolean {
  const flat = buildFlatText(container)
  const match = findExcerptMatch(flat.text, excerpt)
  if (!match) return false

  const startLoc = locate(flat.nodes, match.start)
  const endLoc = locate(flat.nodes, match.end)
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
  if (target && typeof target.scrollIntoView === 'function') {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  return true
}
