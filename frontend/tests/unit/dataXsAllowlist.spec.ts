import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * `text-data-xs` (11px) is the dense-annotation size, and nothing a reader must read as a claim takes it
 * (DESIGN_SYSTEM.md §3; docs/brand/06-system.md §6 Scale). The provenance chip that carries a
 * verification claim is 12px, and so are the in-text citation marker and every source-check label: the
 * marker is never smaller than the chip it opens, and only the margin twin (`.en-margin-mark`, a CSS
 * size in globals.css, not this class) is 11px (ASK-11, ASK-12).
 *
 * 1. DATA_XS_ALLOWED lists every file whose string literals use the class, with the count and why. It is
 *    shrink-only: a new site fails (an unlisted file, or a count above its line), and a site that leaves
 *    must lower its count or delete its line, so the list never holds a stale permission. The list's files
 *    and sites equal DATA_XS_MAX, an equality and not a ceiling (the convention of #1288's
 *    RING_RESIDUE_MAX): the PR that shrinks the list lowers the cap in the same commit, so a freed slot
 *    is gone with the site that freed it, and a list line added later fails until the cap is raised in
 *    review. A line swapped for a line in one commit keeps both totals; the diff shows the added line.
 * 2. Two recipes are held directly, wherever they appear: the in-text marker (a class string with the
 *    18px inline-target box, `min-h-[18px]`) is 12px, and a source-check label never renders at data-xs.
 *    Both states of a label (matched: "Matches filing" or "Quote found in filing"; unmatched: "Linked, not checked" or
 *    "Section linked") render through `citationVerificationLabel(…)`,
 *    and the size read is the one the label renders at: its element's own size class, else the nearest
 *    enclosing element's in the file, and at a component's root the size where the file renders that
 *    component. So moving `text-data-xs` from one site to a wrapper in the same file fails, though the
 *    file's count is unchanged. A component rendered from another file is past the scan's reach.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'lib', 'hooks']
const DATA_XS = /(?<![\w-])text-data-xs(?![\w-])/
const DATA_XS_ALL = new RegExp(DATA_XS.source, 'g')
const TEXT_XS = /(?<![\w-])text-xs(?![\w-])/
/** A text-size class (never a colour such as text-text-secondary-light or an alignment such as text-left). */
const SIZE = /(?<![\w-])text-(?:data-xs|xs|sm|base|lg|[2-9]?xl|\[[^\]]+\])(?![\w-])/

/** Each file's text-data-xs sites today, with why the annotation is dense. Shrink-only: lower DATA_XS_MAX with each shrink. */
const DATA_XS_ALLOWED: Record<string, { count: number; why: string }> = {
  'features/analysis/components/DataNoteMark.tsx': { count: 1, why: 'the superscript data-note letter beside a figure' },
  'features/analysis/components/MetricsTable.tsx': { count: 2, why: 'the column sub-header and the currency caption under a metric' },
  'features/calendar/components/EventRow.tsx': { count: 3, why: 'the compact row: form, ticker and time captions' },
  'features/calendar/components/WeekView.tsx': { count: 1, why: "a day's company count in the week header" },
  'features/filings/components/copilot/AskCopilotRail.tsx': { count: 1, why: 'the launcher kbd hint (⌘K)' },
  'features/filings/components/copilot/CitationChip.tsx': { count: 1, why: "the popover's uppercase source eyebrow" },
  'features/filings/components/copilot/CopilotMessage.tsx': {
    count: 4,
    why: "a markdown table's uppercase header, the Sources list's footnote number, an XBRL row's tag, the matched-source count",
  },
  'features/marketing/components/AnalysisDemo.tsx': { count: 1, why: "the demo card's filing caption" },
  'features/marketing/components/AskFilingDemo.tsx': { count: 3, why: "the demo's in-card eyebrow, filing caption and XBRL locator" },
  'features/marketing/components/HowItWorks.tsx': { count: 1, why: "each step's index caption" },
  'features/marketing/components/RevenueBars.tsx': { count: 3, why: 'chart annotations: axis labels, the period caption, bar values' },
  'features/marketing/components/SummaryContents.tsx': { count: 1, why: "the contents card's filing caption" },
  'features/notifications/components/NotificationBell.tsx': { count: 1, why: 'the unread count on the bell' },
}
const DATA_XS_MAX = { files: 13, sites: 23 }

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const visit = (node: ts.Node, fn: (n: ts.Node) => void) => {
  fn(node)
  ts.forEachChild(node, (child) => visit(child, fn))
}

/** The text of a string-like literal (a template's literal parts included), or null. */
function literalText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text
  if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) return node.text
  return null
}

const SOURCES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir))).map((file) => ({
  rel: path.relative(ROOT, file).split(path.sep).join('/'),
  sf: ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS),
}))

const where = (rel: string, sf: ts.SourceFile, node: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`

/** Each file's text-data-xs sites, counted in its string literals (comments do not count). */
function sitesByFile(): Map<string, number> {
  const counts = new Map<string, number>()
  for (const { rel, sf } of SOURCES) {
    let count = 0
    visit(sf, (n) => {
      const text = literalText(n)
      if (text !== null) count += text.match(DATA_XS_ALL)?.length ?? 0
    })
    if (count) counts.set(rel, count)
  }
  return counts
}

/** Every literal class string under a JSX element's own className (not its children's). */
function ownClassText(opening: ts.JsxOpeningLikeElement): string {
  const attr = opening.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'className')
  if (!attr?.initializer) return ''
  const parts: string[] = []
  visit(attr.initializer, (n) => {
    const text = literalText(n)
    if (text !== null) parts.push(text)
  })
  return parts.join(' ')
}

/** The name a component function goes by in its file: a function declaration's, or the const it is assigned to. */
function componentName(fn: ts.Node): string | null {
  if (ts.isFunctionDeclaration(fn)) return fn.name?.text ?? null
  if ((ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) && ts.isVariableDeclaration(fn.parent) && ts.isIdentifier(fn.parent.name)) {
    return fn.parent.name.text
  }
  return null
}

/** The size classes a node renders at: the nearest enclosing element's own size class in its file, and at a component's
    root the size at each place the file renders the component (none when it is rendered only from other files). */
function sizesAt(node: ts.Node, sf: ts.SourceFile, seen: Set<string> = new Set()): string[] {
  for (let at: ts.Node | undefined = node; at; at = at.parent) {
    if (ts.isJsxElement(at) || ts.isJsxSelfClosingElement(at)) {
      const size = ownClassText(ts.isJsxElement(at) ? at.openingElement : at).match(SIZE)?.[0]
      if (size) return [size]
    }
    if (ts.isFunctionDeclaration(at) || ts.isArrowFunction(at) || ts.isFunctionExpression(at)) {
      const name = componentName(at)
      if (!name || seen.has(name)) return []
      seen.add(name)
      const uses: ts.JsxOpeningLikeElement[] = []
      visit(sf, (n) => {
        if ((ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) && n.tagName.getText(sf) === name) uses.push(n)
      })
      return uses.flatMap((use) => sizesAt(ts.isJsxOpeningElement(use) ? use.parent.parent : use.parent, sf, seen))
    }
  }
  return []
}

describe('text-data-xs stays on dense annotations (shrink-only)', () => {
  it('every file that uses it is listed with its count, and no list line is stale', () => {
    const found = sitesByFile()
    const problems: string[] = []
    for (const [rel, count] of found) {
      const allowed = DATA_XS_ALLOWED[rel]
      if (!allowed) problems.push(`${rel}: ${count} text-data-xs site(s), not listed: a claim or running copy is 12px (text-xs)`)
      else if (count > allowed.count) problems.push(`${rel}: ${count} text-data-xs sites, listed ${allowed.count}: the new one is 12px (text-xs)`)
      else if (count < allowed.count) problems.push(`${rel}: ${count} text-data-xs sites, listed ${allowed.count}: lower its count`)
    }
    for (const rel of Object.keys(DATA_XS_ALLOWED)) {
      if (!found.has(rel)) problems.push(`${rel}: no text-data-xs left: delete its line`)
    }
    expect(problems).toEqual([])
  })

  it('the list only shrinks: its totals equal DATA_XS_MAX', () => {
    const lines = Object.values(DATA_XS_ALLOWED)
    // Equality, not a ceiling: a PR that shrinks the list lowers the cap in the same commit.
    expect(lines.length, 'DATA_XS_ALLOWED changed its files: move DATA_XS_MAX.files with it in the same commit').toBe(DATA_XS_MAX.files)
    expect(lines.reduce((sum, line) => sum + line.count, 0), 'DATA_XS_ALLOWED changed its sites: move DATA_XS_MAX.sites with it in the same commit').toBe(DATA_XS_MAX.sites)
  })

  it('the in-text citation marker is 12px wherever its recipe is written', () => {
    const markers: string[] = []
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        const text = literalText(n)
        if (text === null || !text.includes('min-h-[18px]')) return
        markers.push(where(rel, sf, n))
        if (DATA_XS.test(text) || !TEXT_XS.test(text)) offenders.push(`${where(rel, sf, n)} ${JSON.stringify(text.trim().slice(0, 100))}`)
      })
    }
    // The scan must see the marker recipes it guards: the Copilot chip and the analysis narrative's chip.
    expect(markers.some((m) => m.startsWith('features/filings/components/copilot/CitationChip.tsx:')), 'CitationChip marker').toBe(true)
    expect(markers.some((m) => m.startsWith('features/analysis/components/NarrativePane.tsx:')), 'NarrativePane marker').toBe(true)
    expect(offenders, 'the in-text marker is never smaller than the provenance chip: text-xs').toEqual([])
  })

  it('a source-check label is never data-xs, at its own size or the one it inherits', () => {
    const labels: string[] = []
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        if (!ts.isCallExpression(n) || !ts.isIdentifier(n.expression) || n.expression.text !== 'citationVerificationLabel') return
        let el: ts.Node | undefined = n.parent
        while (el && !ts.isJsxElement(el)) el = el.parent
        if (!el || !ts.isJsxElement(el)) return
        labels.push(where(rel, sf, n))
        const sizes = sizesAt(el, sf)
        if (sizes.some((size) => DATA_XS.test(size))) offenders.push(`${where(rel, sf, el)} renders at ${sizes.join(', ')}`)
      })
    }
    // Four sites, each state of the answer's TrustBadge and of the chip popover, all through the one helper.
    expect(labels.filter((l) => l.startsWith('features/filings/components/copilot/')).length).toBe(4)
    expect(offenders, 'a label that carries a verification claim is 12px: text-xs').toEqual([])
  })

  it('reads the size a label inherits, from a wrapper or where its component is rendered (self-check)', () => {
    const planted = ts.createSourceFile('planted.tsx', [
      "import { citationVerificationLabel } from './citationVerification'",
      'function Badge({ c }: { c: Citation }) {',
      '  return <span className="rounded-full px-2">{citationVerificationLabel(c)}</span>',
      '}',
      'export const Row = ({ c }: { c: Citation }) => (',
      '  <div className="flex text-data-xs">',
      '    <Badge c={c} />',
      '    <span className="text-xs"><b>{citationVerificationLabel(c)}</b></span>',
      '  </div>',
      ')',
    ].join('\n'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const found: string[] = []
    visit(planted, (n) => {
      if (!ts.isCallExpression(n) || !ts.isIdentifier(n.expression) || n.expression.text !== 'citationVerificationLabel') return
      let el: ts.Node | undefined = n.parent
      while (el && !ts.isJsxElement(el)) el = el.parent
      if (el) found.push(`${where('planted.tsx', planted, n)} ${sizesAt(el, planted).join(', ')}`)
    })
    // 3: the badge inherits data-xs where Row renders it; 8: its own wrapper's text-xs wins over the row's data-xs.
    expect(found).toEqual(['planted.tsx:3 text-data-xs', 'planted.tsx:8 text-xs'])
  })
})
