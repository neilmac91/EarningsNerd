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

const HIGHLIGHT_NAME = 'copilot-citation'
const FLASH_CLASS = 'citation-flash'
const FLASH_MS = 1500

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
  el.classList.remove(FLASH_CLASS)
  // Force reflow so re-adding the class restarts the animation on repeat clicks.
  void el.offsetWidth
  el.classList.add(FLASH_CLASS)
  window.setTimeout(() => el?.classList.remove(FLASH_CLASS), FLASH_MS)
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
