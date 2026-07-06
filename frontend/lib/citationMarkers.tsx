import { Children, cloneElement, Fragment, isValidElement, type ReactElement, type ReactNode } from 'react'

export interface MarkerCitation {
  /** Numeric for filing-text excerpts ([1], [2]); an "F#" string for XBRL/computed figures. */
  n: number | string
}

/**
 * Walk a react-markdown subtree and replace inline `[n]` / `[F#]` markers with interactive chips.
 * Only a marker matching a known citation becomes a chip; anything else stays literal text (the
 * model emitted a bracket that isn't a real citation, or an unresolved reference). Recurses into
 * arrays and element children so chips render inside `<strong>`, `<em>`, `<li>`, `<td>`, etc.
 *
 * Shared by the Copilot answer renderer and the Multi-Period Analysis narrative renderer — both
 * consume the same `[n]`/`[F#]` citation contract (DESIGN_SYSTEM.md's chip-recipe section). Each
 * caller supplies its own `renderChip` so the chip's interaction (viewer highlight vs.
 * scroll-to-source) and citation shape stay caller-specific.
 */
export function injectCitationMarkers<C extends MarkerCitation>(
  children: ReactNode,
  citations: C[],
  renderChip: (citation: C, key: string) => ReactNode
): ReactNode {
  // Key by uppercased string so both numeric markers ([1]) and "F#" markers ([F1]) match.
  const byN = new Map(citations.map((c) => [String(c.n).toUpperCase(), c]))

  const walk = (node: ReactNode, keyPrefix: string): ReactNode => {
    if (typeof node === 'string') {
      // Split keeping the captured marker; even indices are literal text, odd are `[n]`/`[F n]` ids.
      // Case-insensitive + whitespace-tolerant so a minor LLM variation ([f1], [F 1]) still renders.
      const parts = node.split(/\[(F?\s*\d+)\]/gi)
      if (parts.length === 1) return node
      const out: ReactNode[] = []
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i]
        if (i % 2 === 1) {
          const citation = byN.get(part.replace(/\s+/g, '').toUpperCase())
          if (citation) {
            out.push(renderChip(citation, `${keyPrefix}-cite-${i}`))
          } else {
            // No matching citation — preserve the literal marker.
            out.push(`[${part}]`)
          }
        } else if (part) {
          out.push(part)
        }
      }
      return out
    }

    if (Array.isArray(node)) {
      return node.map((child, i) => (
        <Fragment key={`${keyPrefix}-${i}`}>{walk(child, `${keyPrefix}-${i}`)}</Fragment>
      ))
    }

    if (isValidElement(node)) {
      const el = node as ReactElement<{ children?: ReactNode }>
      if (el.props?.children == null) return node
      return cloneElement(el, undefined, walk(el.props.children, `${keyPrefix}-c`))
    }

    return node
  }

  return Children.toArray(children).map((child, i) => (
    <Fragment key={`cite-root-${i}`}>{walk(child, `root-${i}`)}</Fragment>
  ))
}
