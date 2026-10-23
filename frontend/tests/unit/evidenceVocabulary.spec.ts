import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * The evidence vocabulary as a gate (D-058, the founder's review of 2026-10-22; docs/voice-and-style.md rule 2 and its
 * vocabulary; CLAUDE.md rule 12). Two rules, read from the source:
 *
 * 1. A retired evidence label never ships: "SEC XBRL", "Verified in filing" and "Source match found" anywhere, in any
 *    case; as a whole label, or a whole part of a "·" pair, the "Cited", "Located in the filing" and bare "Verified"
 *    badges used to read, the punctuation and symbols around them aside ("Verified ✓", "✓ Verified", "Cited."), and in
 *    any case where they are rendered ("VERIFIED"); a heading is a label too. And a bare "SEC EDGAR" wherever it is
 *    rendered (JSX text, an attribute, a `{…}` expression, or a same-file constant one renders by name): the sign-in
 *    page's trust signal read as if the SEC vouched for the figures (chief design on #1530). The labels the product
 *    shows live in one module, features/filings/lib/evidenceLabels.ts; "located in the filing" stays in prose.
 * 2. A link to the source names SEC.gov, not EDGAR, in any case: no link's text (its own and its children's),
 *    aria-label, title or other copy names it. A link is an <a> or <Link>, or any element given an address: an href,
 *    a url or a link, or a prop named for one (backHref, ctaHref, secUrl), as SourceTrace takes its url.
 *
 * Copy is what the TypeScript syntax tree holds as text: string literals, template text and JSX text, and, inside a
 * link, a same-file constant it renders by name: a string or a template (`as const` and `satisfies` aside), or one
 * field of a same-file object. Not copy: comments, identifiers, the values of attributes that are never shown (an
 * address such as an href or edgarCompanyUrl's result, a class, a data-* hook, an id and the references to one), and a
 * value a comparison reads (`s === 'Verified'`, a `case`). An event handler's strings are not a link's copy, but rule 1
 * still reads them, since a handler may set text that is shown (a toast, a label held in state).
 * An attribution outside a link ("Data sourced from SEC EDGAR" in the footer and AiDisclaimer) is not a label, and the
 * plan's R9 leaves it, as it leaves the legal pages (LEGAL, whose links keep their published words). The scan reads
 * .ts, .tsx, .js and .jsx modules.
 *
 * It cannot follow copy another module hands a link. The vocabulary module, whose labels other modules render in
 * links (sourceLinkLabel(url), which evidenceLabels.spec.ts pins), names EDGAR nowhere in its copy, which the second
 * case checks; copy any other module hands a link stays review-checked, as does a label built by concatenation, split
 * across elements or read from an array. The OG card's template is read for rule 1, each of its text segments as a
 * label. The planted forms below hold the scan's reach: each way to break a rule fails, each look-alike passes.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED = ['app', 'components', 'features', 'lib']
const LEGAL = ['app/terms/', 'app/privacy/']
const OG_TEMPLATE = 'scripts/brand/og-template.html'
const LABELS_MODULE = 'features/filings/lib/evidenceLabels.ts'

// The server's own reason string: compared and used as the key of the badge's words, never shown (SummaryDisplay
// REASON_WORDS).
const RETIRED_ALLOWED = new Set(['features/summaries/components/SummaryDisplay.tsx: financial figures not grounded in SEC XBRL data'])

const RETIRED_ANYWHERE = /SEC XBRL|Verified in filing|Source match found/i
const WHOLE_LABELS = ['Cited', 'Located in the filing', 'Verified']
const WHOLE_LABELS_ANY_CASE = new Set([...WHOLE_LABELS, 'SEC EDGAR'].map((label) => label.toLowerCase()))
// A label's own words: the punctuation, symbols and spaces around it are not part of it ("Verified ✓", "Cited.").
const labelWords = (text: string) => text.replace(/^[\s\p{P}\p{S}]+|[\s\p{P}\p{S}]+$/gu, '')

/** Whether text is a retired label, `rendered` when the text is shown as it stands (JSX text, an attribute, a `{…}`). */
export function retiredText(text: string, rendered: boolean): boolean {
  if (RETIRED_ANYWHERE.test(text)) return true
  const parts = text.split('·').map(labelWords)
  if (parts.some((part) => WHOLE_LABELS.includes(part))) return true
  return rendered && parts.some((part) => WHOLE_LABELS_ANY_CASE.has(part.toLowerCase()))
}

// An element given an address is a link: an href, a url or a link, or a prop named for one (backHref, ctaHref, secUrl).
const ADDRESS_ATTRIBUTE = /^(?:href|url|link)$|(?:Href|Url)$/
// Attributes whose values are never shown: sources, classes, link and loading hints, keys, data-* hooks, and ids with
// the references to them. An event handler's strings are not a link's copy, though one may set text that is shown.
const UNSHOWN_ATTRIBUTE = /^(?:src|className|rel|target|id|key|prefetch|htmlFor|aria-(?:controls|describedby|labelledby|owns))$|^data-/
const HANDLER_ATTRIBUTE = /^on[A-Z]/
const isLinkTag = (tag: string) => tag === 'a' || tag === 'Link'
const attributeName = (attribute: ts.JsxAttribute) => attribute.name.getText()
const shownAttribute = (attribute: ts.JsxAttribute) =>
  !ADDRESS_ATTRIBUTE.test(attributeName(attribute)) && !UNSHOWN_ATTRIBUTE.test(attributeName(attribute)) && !HANDLER_ATTRIBUTE.test(attributeName(attribute))

/** Where a value is written as it stands (through `?:`, `||`, `??` and parentheses): an attribute, a `{…}` child, or neither. */
function writtenTo(node: ts.Node): ts.JsxAttribute | 'child' | null {
  let at: ts.Node = node
  while (ts.isConditionalExpression(at.parent) || ts.isParenthesizedExpression(at.parent) || ts.isBinaryExpression(at.parent)) {
    at = at.parent
  }
  if (ts.isJsxExpression(at.parent)) at = at.parent
  if (ts.isJsxAttribute(at.parent)) return at.parent
  return ts.isJsxExpression(at) ? 'child' : null
}

/** Where JSX shows a value as it stands: JSX text, a `{…}` child, or the value of an attribute that is shown. */
function rendered(node: ts.Node): boolean {
  if (ts.isJsxText(node)) return true
  const to = writtenTo(node)
  return to === 'child' || (to !== null && shownAttribute(to))
}

/** A value written to an attribute that is never shown (an address, a class, a data-* hook, an id): not copy. */
function unshown(node: ts.Node): boolean {
  const to = writtenTo(node)
  return to !== null && to !== 'child' && !shownAttribute(to) && !HANDLER_ATTRIBUTE.test(attributeName(to))
}

const EQUALITY = new Set([
  ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsToken,
])
/** A value a comparison reads (`s === 'Verified'`, `case 'Cited':`): matched against, never shown. */
const compared = (node: ts.Node) =>
  (ts.isBinaryExpression(node.parent) && EQUALITY.has(node.parent.operatorToken.kind)) ||
  (ts.isCaseClause(node.parent) && node.parent.expression === node)

const SOURCE_FILE = /\.[jt]sx?$/
export const isSourceFile = (name: string) => SOURCE_FILE.test(name) && !name.endsWith('.d.ts')

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(path.join(FRONTEND, dir), { withFileTypes: true })) {
    const rel = `${dir}/${entry.name}`
    if (entry.isDirectory()) sourceFiles(rel, out)
    else if (isSourceFile(entry.name)) out.push(rel)
  }
  return out
}

const scriptKind = (rel: string) =>
  rel.endsWith('.ts') ? ts.ScriptKind.TS : rel.endsWith('.jsx') ? ts.ScriptKind.JSX : rel.endsWith('.js') ? ts.ScriptKind.JS : ts.ScriptKind.TSX

function textOf(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text
  if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) return node.text
  if (ts.isJsxText(node)) return node.text
  return null
}

function visit(node: ts.Node, fn: (n: ts.Node) => void) {
  fn(node)
  node.forEachChild((child) => visit(child, fn))
}

/** An initializer without what leaves its value as it is: `as const`, `satisfies`, a type assertion, `!`, parentheses. */
function unwrap(node: ts.Expression): ts.Expression {
  let at = node
  while (ts.isAsExpression(at) || ts.isSatisfiesExpression(at) || ts.isTypeAssertionExpression(at) || ts.isNonNullExpression(at) || ts.isParenthesizedExpression(at)) {
    at = at.expression
  }
  return at
}

/** The copy an initializer holds: a string, or a template's text without its substitutions. */
function initializerText(node: ts.Expression): string | null {
  const value = unwrap(node)
  if (ts.isTemplateExpression(value)) return [value.head.text, ...value.templateSpans.map((span) => span.literal.text)].join(' ')
  return ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value) ? value.text : null
}

/** The same file's constants: `NAME` for `const NAME = '…'` (or a template), `NAME.field` for a field of `const NAME = { … }`. */
function fileConstants(sf: ts.SourceFile): Map<string, string> {
  const out = new Map<string, string>()
  visit(sf, (node) => {
    if (!ts.isVariableDeclaration(node) || !ts.isIdentifier(node.name) || !node.initializer) return
    const name = node.name.text
    const text = initializerText(node.initializer)
    if (text !== null) out.set(name, text)
    const value = unwrap(node.initializer)
    if (!ts.isObjectLiteralExpression(value)) return
    for (const field of value.properties) {
      if (!ts.isPropertyAssignment(field) || !(ts.isIdentifier(field.name) || ts.isStringLiteral(field.name))) continue
      const fieldText = initializerText(field.initializer)
      if (fieldText !== null) out.set(`${name}.${field.name.text}`, fieldText)
    }
  })
  return out
}

/** The copy of the same-file constant a node names: `NAME`, `NAME.field`, or a constant a member reads (`NAME.trim()`).
    A name that only labels something (a member's, an attribute's, a field's, a tag's, a declaration's) names none. */
function constantText(node: ts.Node, constants: Map<string, string>): string | null {
  if (ts.isPropertyAccessExpression(node)) {
    return ts.isIdentifier(node.expression) ? (constants.get(`${node.expression.text}.${node.name.text}`) ?? null) : null
  }
  if (!ts.isIdentifier(node)) return null
  const parent = node.parent
  const onlyLabels =
    ((ts.isPropertyAccessExpression(parent) || ts.isJsxAttribute(parent) || ts.isPropertyAssignment(parent) || ts.isVariableDeclaration(parent)) &&
      parent.name === node) ||
    ((ts.isJsxOpeningElement(parent) || ts.isJsxSelfClosingElement(parent) || ts.isJsxClosingElement(parent)) && parent.tagName === node)
  return onlyLabels ? null : (constants.get(node.text) ?? null)
}

/** Every piece of copy inside a link element: its text, its children's, and its attributes' but for those that are not copy. */
function linkCopy(element: ts.JsxElement | ts.JsxSelfClosingElement, constants: Map<string, string>): string[] {
  const out: string[] = []
  const read = (node: ts.Node) => {
    if (ts.isJsxAttribute(node) && !shownAttribute(node)) return
    const text = textOf(node) ?? constantText(node, constants)
    if (text !== null) out.push(text)
    node.forEachChild(read)
  }
  read(element)
  return out
}

export interface Breach {
  rule: 'retired label' | 'link names EDGAR'
  at: string
  text: string
}

export function scan(rel: string, source: string): Breach[] {
  if (LEGAL.some((dir) => rel.startsWith(dir))) return []
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, scriptKind(rel))
  const at = (node: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
  const constants = fileConstants(sf)
  const breaches: Breach[] = []
  visit(sf, (node) => {
    // Rule 1: a node's own text, or the text of a same-file constant JSX renders by name.
    const own = textOf(node)
    const text = own ?? constantText(node, constants)
    if (text !== null) {
      const shown = rendered(node)
      if ((own !== null || shown) && !compared(node) && !unshown(node) && retiredText(text, shown) && !RETIRED_ALLOWED.has(`${rel}: ${text}`)) {
        breaches.push({ rule: 'retired label', at: at(node), text: text.trim() })
      }
    }
    // Rule 2: every link's copy.
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const opening = ts.isJsxElement(node) ? node.openingElement : node
      const hasAddress = opening.attributes.properties.some((p) => ts.isJsxAttribute(p) && ADDRESS_ATTRIBUTE.test(attributeName(p)))
      if (isLinkTag(opening.tagName.getText()) || hasAddress) {
        for (const copy of linkCopy(node, constants)) {
          if (/edgar/i.test(copy)) breaches.push({ rule: 'link names EDGAR', at: at(node), text: copy.trim() })
        }
      }
    }
  })
  return breaches
}

/** The OG card's text segments: what each element shows, the comments, style and script blocks taken out. */
export const htmlSegments = (html: string) =>
  html.replace(/<!--[\s\S]*?-->/g, ' ').replace(/<(style|script)\b[\s\S]*?<\/\1>/gi, ' ')
    .split(/<[^>]+>/).map((segment) => segment.trim()).filter(Boolean)

describe('the evidence vocabulary (D-058)', () => {
  const files = SCANNED.flatMap((dir) => sourceFiles(dir))

  it('reads the app', () => {
    expect(files).toEqual(expect.arrayContaining([
      LABELS_MODULE,
      'features/filings/components/SourceTrace.tsx',
      'features/filings/components/FilingIndex.tsx',
      'app/waitlist/page.tsx',
    ]))
  })

  it('ships no retired evidence label, and every link to the source names SEC.gov', () => {
    const breaches = files.flatMap((rel) => scan(rel, readFileSync(path.join(FRONTEND, rel), 'utf8')))
    expect(breaches).toEqual([])
  })

  it('keeps EDGAR out of the vocabulary module, whose labels other modules render in links', () => {
    const sf = ts.createSourceFile(LABELS_MODULE, readFileSync(path.join(FRONTEND, LABELS_MODULE), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
    const copy: string[] = []
    visit(sf, (node) => {
      const text = textOf(node)
      if (text !== null) copy.push(text)
    })
    expect(copy, 'the module holds the labels').toEqual(expect.arrayContaining(['Matches filing', 'Quote not found']))
    expect(copy.filter((text) => /edgar/i.test(text))).toEqual([])
  })

  it('keeps its one allowed literal only while the badge still compares it', () => {
    const display = readFileSync(path.join(FRONTEND, 'features/summaries/components/SummaryDisplay.tsx'), 'utf8')
    for (const entry of RETIRED_ALLOWED) expect(display).toContain(`'${entry.split(': ')[1]}'`)
  })

  it('the OG card shows no retired label', () => {
    const segments = htmlSegments(readFileSync(path.join(FRONTEND, OG_TEMPLATE), 'utf8'))
    expect(segments).toContain('Apple Inc.')
    expect(segments.filter((segment) => retiredText(segment, true))).toEqual([])
  })
})

describe('the vocabulary scan holds its reach', () => {
  const breaches = (source: string, rel = 'features/x/Planted.tsx') => scan(rel, source).map((b) => b.rule)

  it.each([
    ['a link that names EDGAR', `export const A = () => <a href="https://www.sec.gov">Full history on SEC EDGAR</a>`],
    ['a link whose name names EDGAR', 'export const A = ({ u }: { u: string }) => <a href={u} aria-label={`View the 10-K on SEC EDGAR (opens in a new tab)`}>10-K</a>'],
    ['a link whose hidden text names EDGAR', `export const A = ({ u }: { u: string }) => <a href={u}><span aria-hidden="true">EDGAR</span></a>`],
    ['a link that names it in another case', `export const A = ({ u }: { u: string }) => <a href={u} title="Open on Edgar">10-K</a>`],
    ['a Link that renders a same-file constant naming EDGAR', `const LABEL = 'Original on SEC EDGAR'\nexport const A = () => <Link href="/f">{LABEL}</Link>`],
    ['any element given an href', `export const A = () => <Button href="https://www.sec.gov">Open on EDGAR</Button>`],
    ['an element given a url, as SourceTrace takes one', `export const A = ({ u }: { u: string }) => <SourceTrace url={u} label="Open on SEC EDGAR" />`],
    ['an element given an address by another name', `export const A = () => <SecondaryHeader backHref="/filings" backLabel="Back to EDGAR" />`],
    ['a constant built from a template', 'const FORM = \'10-K\'\nconst LABEL = `Open the ${FORM} on SEC EDGAR`\nexport const A = () => <a href="/f">{LABEL}</a>'],
    ['a constant written as const', `const LABEL = 'Open on SEC EDGAR' as const\nexport const A = () => <a href="/f">{LABEL}</a>`],
    ['a constant written with satisfies', `const LABEL = 'Open on SEC EDGAR' satisfies string\nexport const A = () => <a href="/f">{LABEL}</a>`],
    ['a field of a same-file object', `const LABELS = { source: 'Open on SEC EDGAR' } as const\nexport const A = () => <a href="/f">{LABELS.source}</a>`],
    ['a constant the link reads a member of', `const LABEL = 'Open on SEC EDGAR'\nexport const A = () => <a href="/f">{LABEL.toUpperCase()}</a>`],
  ])('fails %s', (_, source) => {
    expect(breaches(source)).toContain('link names EDGAR')
  })

  it.each([
    ['the old figure label', `export const B = () => <Badge>SEC XBRL</Badge>`],
    ['the old figure label in lower case', `export const L = 'sec xbrl figures'`],
    ['the old passage label', `export const L = 'Verified in filing'`],
    ['the old chip label', `export const L = cond ? 'Cited' : 'Matches filing'`],
    ['the old label in a template', 'export const L = (n: number) => `${n} SEC XBRL figures`'],
    ['the old hero chip', `export const C = () => <a href="https://www.sec.gov">Located in the filing</a>`],
    ['a bare source name as a label', `export const T = () => <span><ShieldCheckIcon />SEC EDGAR</span>`],
    ['the old match phrase', `export const S = 'Source match found'`],
    ['a bare verified badge', `export const V = () => <span><CheckCircleIcon />Verified</span>`],
    ['a badge with a mark after it', `export const V = () => <span>Verified ✓</span>`],
    ['a badge with a mark before it', `export const V = () => <span>✓ Verified</span>`],
    ['a badge in capitals', `export const V = () => <span>VERIFIED</span>`],
    ['a chip with a stop', `export const V = () => <span>Cited.</span>`],
    ['a heading that reads only the old word, which is a label too', `export const H = () => <h3>Cited</h3>`],
    ['the old label as one part of a pair', `export const V = () => <span>Revenue · Verified</span>`],
    ['a bare source name as an expression', `export const T = () => <span>{'SEC EDGAR'}</span>`],
    ['a bare source name handed as a prop', `export const T = () => <Signal label="SEC EDGAR" />`],
    ['a bare source name in a title', `export const T = () => <span title="SEC EDGAR">10-K</span>`],
    ['a bare source name behind a condition', `export const T = ({ x }: { x: boolean }) => <span>{x ? 'SEC EDGAR' : null}</span>`],
    ['a bare source name rendered by name', `const SOURCE = 'SEC EDGAR'\nexport const T = () => <span>{SOURCE}</span>`],
    ['a constant badge in capitals rendered by name', `const BADGE = 'VERIFIED'\nexport const T = () => <Badge label={BADGE} />`],
    ['a label a handler sets', `export const B = () => <button onClick={() => setLabel('Verified')}>Check</button>`],
    ['a shown attribute in capitals behind a condition', `export const B = ({ ok }: { ok: boolean }) => <Chip label={ok ? 'CITED' : ''} />`],
  ])('fails %s', (_, source) => {
    expect(breaches(source)).toContain('retired label')
  })

  it.each([
    ['an attribution outside a link', `export const F = () => <p>Data sourced from SEC EDGAR</p>`],
    ['a comment inside a link', `export const A = ({ u }: { u: string }) => <a href={u}>{/* the EDGAR document */}Open the filing on SEC.gov</a>`],
    ['an address built from an EDGAR helper', `export const A = ({ cik }: { cik: string }) => <a href={edgarCompanyUrl(cik)}>Full history on SEC.gov</a>`],
    ['an address handed as a url', `export const A = () => <SourceTrace url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany" label="Open the 10-K on SEC.gov" />`],
    ['an analytics event in a link’s handler', `export const A = ({ u }: { u: string }) => <a href={u} onClick={() => track('Opened SEC EDGAR')}>Open on SEC.gov</a>`],
    ['a test hook naming EDGAR', `export const A = ({ u }: { u: string }) => <a href={u} data-testid="EDGAR-link">Open on SEC.gov</a>`],
    ['an attribute that shares a constant’s name', `const title = 'EDGAR full-text search'\nexport const A = ({ u }: { u: string }) => <a href={u} title="Open on SEC.gov">10-K</a>`],
    ['a member that shares a constant’s name', `const label = 'SEC EDGAR'\nexport const A = ({ u, x }: { u: string; x: { label: string } }) => <a href={u}>{x.label}</a>`],
    ['a sentence that cites', `export const P = () => <p>Official filings, cited and traceable to the source.</p>`],
    ['an acronym behind a plain word', `export const H = () => <details><summary>How we check</summary>We compare it with the XBRL data.</details>`],
    ['the product word in prose', `export const P = () => <p>Excerpts located in the filing’s own text, or withheld.</p>`],
    ['a source name in a keyword list', `export const K = ['SEC filings', 'SEC EDGAR']`],
    ['a sentence that starts with the word', `export const P = () => <p>Verified by the auditor before filing.</p>`],
    ['the negated word', `export const P = () => <span>Unverified</span>`],
    ['a value a comparison reads', `export const isVerified = (s: string) => s === 'Verified'`],
    ['a case a switch reads', `export function words(s: string) { switch (s) { case 'Cited': return 'Quote found in filing'; default: return s } }`],
    ['a status value that is never shown', `export const STATUS = 'verified'`],
    ['a type that names a field', `type Evidence = Omit<FigureEvidence, 'verified'>`],
    ['a state a data attribute carries', `export const S = ({ ok }: { ok: boolean }) => <span data-state={ok ? 'Verified' : 'pending'}>Matches filing</span>`],
    ['an id that reads like a label', `export const S = () => <section id="Cited" aria-labelledby="SEC EDGAR">Quote found in filing</section>`],
  ])('passes %s', (_, source) => {
    expect(breaches(source)).toEqual([])
  })

  it('reads .js and .jsx modules as the app may hold them (allowJs)', () => {
    expect(['Panel.jsx', 'panel.js', 'Panel.tsx', 'panel.ts'].every(isSourceFile)).toBe(true)
    expect(['panel.d.ts', 'panel.json', 'panel.css'].some(isSourceFile)).toBe(false)
    expect(breaches(`export const A = ({ u }) => <a href={u}>Full history on SEC EDGAR</a>`, 'features/x/Planted.jsx')).toContain('link names EDGAR')
    expect(breaches(`export const B = () => <span>Verified in filing</span>`, 'features/x/planted.js')).toContain('retired label')
  })

  it('leaves the legal pages, whose links keep their published words', () => {
    expect(breaches(`export const A = () => <a href="https://www.sec.gov">SEC EDGAR</a>`, 'app/terms/page.tsx')).toEqual([])
  })
})

describe('the OG card scan', () => {
  it.each([
    ['{ } Revenue · SEC XBRL', true],
    ['{ } Revenue · Verified', true],
    ['{ } Revenue · Source match found', true],
    ['{ } Revenue · Matches filing', false],
  ])('reads "%s" as retired: %s', (chip, retired) => {
    const html = `<style>.chip{}</style><div class="meta"><span class="chip">${chip}</span><span><b>Apple Inc.</b></span></div>`
    expect(htmlSegments(html).some((segment) => retiredText(segment, true))).toBe(retired)
  })
})
