import type { AnalysisCitation } from '../api/analysis-api'
import { fmtScale } from '@/lib/format'
import { compactFigure, exactFigure, exactNumber } from './figureDisplay'
import { formatAnalysisPeriod } from './periodLabels'

/** Pinned to the code-owned renderer by narrative-pane.spec.tsx until structured evidence ships. */
export const SOURCE_OPERANDS_PREFIX = ' Source operands: '

export interface NarrativeOperand {
  label: string
  value: string
  period: string
  citation: number
  derived: boolean
  /** Structured evidence already uses the server's report-wide precision plan. */
  formatted?: boolean
}
export type NarrativePart = { kind: 'markdown'; text: string } | { kind: 'evidence'; operands: NarrativeOperand[] }

/** Fold only the complete code-owned grammar. Unrecognized text and unresolved markers remain
 * in the reading line, so a parser mismatch cannot silently discard evidence or another claim. */
export function splitNarrativeEvidence(text: string, citations: AnalysisCitation[]): NarrativePart[] {
  const known = new Set(citations.map((citation) => citation.n))
  const parts: NarrativePart[] = []
  let start = 0
  let search = 0
  const operand = /([^\n;]+?) ((?:[A-Z]{3} )?[+-]?\d[\d,]*(?:\.\d+)?(?: per share|%|x|×)?) in (FY\d{4}|\d{4}Q[1-4]) \[(\d+)\]( \(derived Q4\))?/y
  while (true) {
    const prefix = text.indexOf(SOURCE_OPERANDS_PREFIX, search)
    if (prefix < 0) break
    let cursor = prefix + SOURCE_OPERANDS_PREFIX.length
    const operands: NarrativeOperand[] = []
    let complete = false
    while (cursor < text.length) {
      operand.lastIndex = cursor
      const match = operand.exec(text)
      if (!match || !known.has(Number(match[4]))) break
      operands.push({ label: match[1], value: match[2], period: match[3], citation: Number(match[4]), derived: !!match[5] })
      cursor = operand.lastIndex
      if (text.slice(cursor, cursor + 2) === '; ') { cursor += 2; continue }
      if (text[cursor] === '.' && (cursor + 1 === text.length || /\s/.test(text[cursor + 1]))) { complete = true; cursor += 1 }
      break
    }
    search = complete ? cursor : prefix + SOURCE_OPERANDS_PREFIX.length
    if (!complete) continue
    if (prefix > start) parts.push({ kind: 'markdown', text: text.slice(start, prefix) })
    parts.push({ kind: 'evidence', operands })
    start = cursor
  }
  if (start < text.length || !parts.length) parts.push({ kind: 'markdown', text: text.slice(start) })
  return parts
}

const CURRENCY_AMOUNT = /\b([A-Z]{3}) (-?\d[\d,]*(?:\.\d+)?)( per share)?\b/g
const currencyAmountKey = (amount: string, unit: string) => `${unit}:${amount.replaceAll(',', '')}`

/** Plan precision across the complete narrative, before evidence/Markdown split it into nodes.
 * Distinct amounts must not collapse to “$1.0B below $1.0B”; retain original exact tokens only
 * for these collisions, including per-share amounts that round to the same displayed cent. */
export function currencyAmountsNeedingPrecision(text: string): ReadonlySet<string> {
  const displays = new Map<string, Set<string>>()
  for (const match of text.matchAll(CURRENCY_AMOUNT)) {
    const value = Number(match[2].replaceAll(',', ''))
    if (!Number.isFinite(value)) continue
    const unit = match[1] + (match[3] ? '/shares' : '')
    const display = `${unit}:${compactFigure(value, { unit })}`
    const amounts = displays.get(display) ?? new Set<string>()
    amounts.add(currencyAmountKey(match[2], unit))
    displays.set(display, amounts)
  }
  return new Set([...displays.values()].filter((amounts) => amounts.size > 1).flatMap((amounts) => [...amounts]))
}

/** Receives prose text nodes, never Markdown source, links, code or source excerpts. */
export function compactNarrativeText(text: string, preciseAmounts: ReadonlySet<string> = currencyAmountsNeedingPrecision(text)): string {
  return text
    .replace(CURRENCY_AMOUNT, (original, currency: string, amount: string, perShare: string | undefined) => {
      const value = Number(amount.replaceAll(',', ''))
      const unit = currency + (perShare ? '/shares' : '')
      return Number.isFinite(value) && !preciseAmounts.has(currencyAmountKey(amount, unit)) ? compactFigure(value, { unit }) : original
    })
    .replace(/\b(\d+\.\d+)x\b/g, (_original, amount: string) => {
      const value = Number(amount)
      const rounded = value.toFixed(2)
      // The server intentionally adds precision around its 1.00x liquidity threshold.
      // Keep that relation visible: 1.00004x above 1.00x must not become 1.00× above 1.00×.
      return `${value !== 1 && Number(rounded) === 1 ? amount : rounded}×`
    })
    .replace(/\b\d{4}Q[1-4]\b/g, (period) => formatAnalysisPeriod(period))
}

interface TextNode { type: string; value?: string; children?: TextNode[] }

/** A small remark transformer: format prose without rewriting link destinations or code. */
export function remarkCompactAnalysis(options: { preciseAmounts?: ReadonlySet<string> } = {}) {
  return (tree: TextNode) => {
    const textNodes: TextNode[] = []
    const visit = (node: TextNode) => {
      if (node.type === 'text' && node.value) textNodes.push(node)
      node.children?.forEach(visit)
    }
    visit(tree)
    const preciseAmounts = options.preciseAmounts ?? currencyAmountsNeedingPrecision(textNodes.map((node) => node.value).join(' '))
    for (const node of textNodes) node.value = compactNarrativeText(node.value!, preciseAmounts)
  }
}

/** New citations carry explicit display units; legacy citations keep their supplied currency
 * omission. The appendix retains the exact numeric payload alongside the compact figure. */
export function citationDisplay(citation: AnalysisCitation): string {
  const match = /^(.*?) = (.*?) \(([^)]+)\)(?: — derived Q4)?$/.exec(citation.excerpt)
  if (!match) return citation.excerpt
  const [, label, sourceValue, period] = match
  if (citation.unit && typeof citation.value === 'number' && Number.isFinite(citation.value)) {
    const figure = { concept: citation.concept, unit: citation.unit }
    return `${label} · ${formatAnalysisPeriod(period)} · ${compactFigure(citation.value, figure)} (${exactFigure(citation.value, figure)})`
  }
  const value = citation.value ?? Number(sourceValue.replaceAll(',', '').replace(/[x%]$/, ''))
  if (!Number.isFinite(value)) return citation.excerpt
  const percent = sourceValue.endsWith('%')
  const ratio = sourceValue.endsWith('x')
  const cagr = label.endsWith(' CAGR')
  const exact = citation.value == null ? sourceValue.replace(/[x%]$/, '') : exactNumber(cagr ? value * 100 : value)
  const display = percent ? sourceValue : ratio ? compactNarrativeText(sourceValue) : fmtScale(value, { digits: Math.abs(value) < 1000 ? 2 : 1 })
  return `${label} · ${formatAnalysisPeriod(period)} · ${display} (${exact}${percent ? '%' : ratio ? ' ratio' : ''})`
}
