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
 *    case; as a whole label, or a whole part of a pair (split at "·", "•" or "|"), the "Cited", "Located in the
 *    filing" and bare "Verified" badges used to read, the punctuation and symbols around them aside ("Verified ✓",
 *    "✓ Verified", "Cited."), and in any case where they are rendered ("VERIFIED"); a heading is a label too. And a
 *    bare "SEC EDGAR" wherever it is rendered (JSX text, an attribute, a `{…}` expression, or a same-file constant one
 *    renders by name): the sign-in page's trust signal read as if the SEC vouched for the figures (chief design on
 *    #1530). The labels the product shows live in one module, features/filings/lib/evidenceLabels.ts; "located in the
 *    filing" stays in prose.
 * 2. A link to the source names SEC.gov, not EDGAR, in any case: no link's text (its own and its children's),
 *    aria-label, title or other copy names it. A link is an <a> or <Link>, or any element given an address: an href,
 *    a url, a link or a `to`, or a prop named for one (backHref, ctaHref, secUrl, documentURL, fragment_url,
 *    sourceLink), as SourceTrace takes its url.
 *
 * Copy is what the TypeScript syntax tree holds as text: string literals, template text and JSX text, and a same-file
 * constant JSX renders by name, as it stands or through a method that keeps its words (`.trim()`, a change of case): a
 * string or a template (`as const` and `satisfies` aside), or one field of a same-file object. A name resolves as
 * TypeScript resolves it, so a parameter or another function's constant that shares the name is not that constant.
 * Not copy: comments, identifiers, the values of attributes that are never shown (an address such as an href or
 * edgarCompanyUrl's result, a class, a data-* hook but `data-en-ref`, whose value MarkedCopy shows as the margin's
 * mark, a download's file name, an id and the references to one), and,
 * outside JSX, a value a match reads: a comparison (`s === 'Verified'`), a `case`, a membership or affix test
 * (`includes`, `startsWith`, `endsWith`, `indexOf`, `has`, `get`), an object key, or a literal type. Inside JSX a
 * matched value is copy, since what it matches may be what is shown (`{s === 'Cited' ? s : ''}`). An event handler's
 * strings are not a link's copy, and rule 1 reads them as it reads a string outside JSX, since a handler may set text
 * that is shown (a toast, a label held in state): the retired phrases in any case and the whole labels in their own
 * case, so a handler's "VERIFIED" or bare "SEC EDGAR" stays review-checked. An attribution outside a link ("Data sourced from SEC EDGAR" in the footer and AiDisclaimer)
 * is not a label, and the plan's R9 leaves it, as it leaves the legal pages (LEGAL, whose links keep their published
 * words). The scan reads the .ts, .tsx, .js and .jsx modules in app, components, features, hooks and lib, and what the
 * stylesheets there add with `content:`.
 *
 * It cannot follow copy another module hands a link. The vocabulary module, whose labels other modules render in
 * links (sourceLinkLabel(url), which evidenceLabels.spec.ts pins), names EDGAR nowhere in its copy, which a case below
 * checks; copy any other module hands a link stays review-checked, as do a label built by concatenation or a template
 * that embeds a constant, one split across elements or read from an array, an object's keys a module renders
 * (`Object.keys`), and a class's generated content (`before:content-['…']`). The OG card's template is read for rule 1,
 * each of its text segments (its entities decoded) and each `content:` its styles add as a label. The planted forms
 * below hold the scan's reach: each way to break a rule fails, each look-alike passes.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED = ['app', 'components', 'features', 'hooks', 'lib']
const LEGAL = ['app/terms/', 'app/privacy/']
const OG_TEMPLATE = 'scripts/brand/og-template.html'
const LABELS_MODULE = 'features/filings/lib/evidenceLabels.ts'
const BADGE_MODULE = 'features/summaries/components/SummaryDisplay.tsx'

// The server's own reason string, declared once and only compared or used as the key of the badge's words, never
// shown (SummaryDisplay REASON_WORDS and BADGE_WORDS). The allowance covers that declaration's literal, not a read of it.
const RETIRED_ALLOWED = new Set([`${BADGE_MODULE}: financial figures not grounded in SEC XBRL data`])

const RETIRED_ANYWHERE = /SEC XBRL|Verified in filing|Source match found/i
const WHOLE_LABELS = ['Cited', 'Located in the filing', 'Verified']
const WHOLE_LABELS_ANY_CASE = new Set([...WHOLE_LABELS, 'SEC EDGAR'].map((label) => label.toLowerCase()))
// The parts of a pair: "Revenue · Matches filing", "Revenue • Matches filing", "Revenue | Matches filing".
const PAIR = /[·•|]/
// A label's own words: the punctuation, symbols and spaces around it are not part of it ("Verified ✓", "Cited.").
const labelWords = (text: string) => text.replace(/^[\s\p{P}\p{S}]+|[\s\p{P}\p{S}]+$/gu, '')

/** Whether text is a retired label, `rendered` when the text is shown as it stands (JSX text, an attribute, a `{…}`). */
export function retiredText(text: string, rendered: boolean): boolean {
  if (RETIRED_ANYWHERE.test(text)) return true
  const parts = text.split(PAIR).map(labelWords)
  if (parts.some((part) => WHOLE_LABELS.includes(part))) return true
  return rendered && parts.some((part) => WHOLE_LABELS_ANY_CASE.has(part.toLowerCase()))
}

// An element given an address is a link: an href, a url, a link or a `to`, or a prop named for one.
const ADDRESS_ATTRIBUTE = /^(?:href|url|link|to)$|(?:Href|Url|URL|Link)$|_(?:href|url|link)$/
// Attributes whose values are never shown: sources, classes, link and loading hints, a download's file name, keys,
// data-* hooks (but `data-en-ref`, which MarkedCopy shows), and ids with the references to them. An event handler's
// strings are not a link's copy, though one may set text that is shown.
const SHOWN_DATA_ATTRIBUTE = 'data-en-ref'
const UNSHOWN_ATTRIBUTE =
  /^(?:src|className|rel|target|id|key|prefetch|as|download|form|htmlFor|aria-(?:activedescendant|controls|describedby|details|flowto|labelledby|owns))$|^data-(?!en-ref$)/
const HANDLER_ATTRIBUTE = /^on[A-Z]/
const isLinkTag = (tag: string) => tag === 'a' || tag === 'Link'
const attributeName = (attribute: ts.JsxAttribute) => attribute.name.getText()
const shownAttribute = (attribute: ts.JsxAttribute) =>
  !ADDRESS_ATTRIBUTE.test(attributeName(attribute)) && !UNSHOWN_ATTRIBUTE.test(attributeName(attribute)) && !HANDLER_ATTRIBUTE.test(attributeName(attribute))

// String methods that return the same words: a label read through one is the same label (`SOURCE.trim()`).
const KEEPS_WORDS = new Set(['trim', 'trimStart', 'trimEnd', 'toUpperCase', 'toLowerCase', 'toLocaleUpperCase', 'toLocaleLowerCase', 'normalize'])

/** The expression that carries a value as it stands: through `?:`, `||`, `??`, parentheses and a method that keeps its words. */
function carrier(node: ts.Node): ts.Node {
  let at = node
  for (;;) {
    const parent = at.parent
    if (ts.isConditionalExpression(parent) || ts.isParenthesizedExpression(parent) || ts.isBinaryExpression(parent)) at = parent
    else if (ts.isPropertyAccessExpression(parent) && parent.expression === at && KEEPS_WORDS.has(parent.name.text) && ts.isCallExpression(parent.parent)) at = parent.parent
    else return at
  }
}

/** Where a value is written as it stands: an attribute, a `{…}` child, or neither. */
function writtenTo(node: ts.Node): ts.JsxAttribute | 'child' | null {
  let at = carrier(node)
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
// Methods that test a text or a collection against a value: the value is matched, never shown.
const MATCHERS = new Set(['includes', 'startsWith', 'endsWith', 'indexOf', 'lastIndexOf', 'has', 'get'])

/** A value a match reads: a comparison (`s === 'Verified'`), a `case`, a membership or affix test
    (`labels.includes('Cited')`), an object key (`{ 'Cited': … }`, `words['Cited']`), or a literal type. */
function matched(node: ts.Node): boolean {
  const parent = node.parent
  return (
    (ts.isBinaryExpression(parent) && EQUALITY.has(parent.operatorToken.kind)) ||
    (ts.isCaseClause(parent) && parent.expression === node) ||
    (ts.isCallExpression(parent) && parent.arguments[0] === node && ts.isPropertyAccessExpression(parent.expression) && MATCHERS.has(parent.expression.name.text)) ||
    ((ts.isPropertyAssignment(parent) || ts.isPropertySignature(parent)) && parent.name === node) ||
    (ts.isElementAccessExpression(parent) && parent.argumentExpression === node) ||
    ts.isLiteralTypeNode(parent)
  )
}

/** Whether a node sits inside JSX: in a `{…}` or an attribute's value, through any expression or function. */
function insideJsx(node: ts.Node): boolean {
  for (let at = node.parent; !ts.isSourceFile(at); at = at.parent) if (ts.isJsxExpression(at) || ts.isJsxAttribute(at)) return true
  return false
}

const SOURCE_FILE = /\.[jt]sx?$/
export const isSourceFile = (name: string) => SOURCE_FILE.test(name) && !name.endsWith('.d.ts')

function filesUnder(dir: string, keep: (name: string) => boolean, out: string[] = []): string[] {
  for (const entry of readdirSync(path.join(FRONTEND, dir), { withFileTypes: true })) {
    const rel = `${dir}/${entry.name}`
    if (entry.isDirectory()) filesUnder(rel, keep, out)
    else if (keep(entry.name)) out.push(rel)
  }
  return out
}

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

/** The declaration a literal is the value of (through `as const`, `satisfies` and parentheses), if any. */
function declarationOf(node: ts.Node): ts.VariableDeclaration | undefined {
  let at = node
  while (ts.isAsExpression(at.parent) || ts.isSatisfiesExpression(at.parent) || ts.isParenthesizedExpression(at.parent)) at = at.parent
  return ts.isVariableDeclaration(at.parent) && at.parent.initializer === at ? at.parent : undefined
}

interface Constant {
  text: string | null
  fields: Map<string, string>
}

/** The file's constants by declaration: `const NAME = '…'` (or a template), and the fields of `const NAME = { … }`. */
function fileConstants(sf: ts.SourceFile): Map<ts.Node, Constant> {
  const out = new Map<ts.Node, Constant>()
  visit(sf, (node) => {
    if (!ts.isVariableDeclaration(node) || !ts.isIdentifier(node.name) || !node.initializer) return
    const value = unwrap(node.initializer)
    const fields = new Map<string, string>()
    if (ts.isObjectLiteralExpression(value)) {
      for (const field of value.properties) {
        if (!ts.isPropertyAssignment(field) || !(ts.isIdentifier(field.name) || ts.isStringLiteral(field.name))) continue
        const fieldText = initializerText(field.initializer)
        if (fieldText !== null) fields.set(field.name.text, fieldText)
      }
    }
    const text = initializerText(node.initializer)
    if (text !== null || fields.size) out.set(node, { text, fields })
  })
  return out
}

/** A name that only labels something (a member's, an attribute's, a field's, a tag's, a declaration's) and reads no value. */
function onlyLabels(node: ts.Identifier): boolean {
  const parent = node.parent
  return (
    ((ts.isPropertyAccessExpression(parent) || ts.isJsxAttribute(parent) || ts.isPropertyAssignment(parent) || ts.isVariableDeclaration(parent)) &&
      parent.name === node) ||
    ((ts.isJsxOpeningElement(parent) || ts.isJsxSelfClosingElement(parent) || ts.isJsxClosingElement(parent)) && parent.tagName === node)
  )
}

/** A program over `files` (path → source), so each name resolves to its own declaration as TypeScript resolves it. */
function programOver(files: Map<string, string>): ts.Program {
  const options: ts.CompilerOptions = { allowJs: true, jsx: ts.JsxEmit.Preserve, noLib: true, noResolve: true, types: [], target: ts.ScriptTarget.Latest }
  const sources = new Map([...files].map(([rel, source]) => [path.join(FRONTEND, rel), source]))
  const host = ts.createCompilerHost(options, true)
  host.getSourceFile = (name, version) => {
    const source = sources.get(name)
    return source === undefined ? undefined : ts.createSourceFile(name, source, version, true)
  }
  host.fileExists = (name) => sources.has(name)
  host.readFile = (name) => sources.get(name)
  return ts.createProgram({ rootNames: [...sources.keys()], options, host })
}

/** Every piece of copy inside a link element: its text, its children's, and its attributes' but for those that are not copy. */
function linkCopy(element: ts.JsxElement | ts.JsxSelfClosingElement, constantText: (node: ts.Node) => string | null): string[] {
  const out: string[] = []
  const read = (node: ts.Node) => {
    if (ts.isJsxAttribute(node) && !shownAttribute(node)) return
    const text = textOf(node) ?? constantText(node)
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

function scanFile(rel: string, sf: ts.SourceFile, checker: ts.TypeChecker): Breach[] {
  if (LEGAL.some((dir) => rel.startsWith(dir))) return []
  const at = (node: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
  const constants = fileConstants(sf)
  const names = new Set([...constants.keys()].map((declaration) => ((declaration as ts.VariableDeclaration).name as ts.Identifier).text))
  const constantOf = (name: ts.Identifier) => {
    const declaration = names.has(name.text) ? checker.getSymbolAtLocation(name)?.valueDeclaration : undefined
    return declaration ? constants.get(declaration) : undefined
  }
  /** The copy of the same-file constant a node reads: `NAME`, `NAME.field`, or `NAME` under a member (`NAME.trim()`). */
  const constantText = (node: ts.Node): string | null => {
    if (ts.isPropertyAccessExpression(node)) return ts.isIdentifier(node.expression) ? (constantOf(node.expression)?.fields.get(node.name.text) ?? null) : null
    return ts.isIdentifier(node) && !onlyLabels(node) ? (constantOf(node)?.text ?? null) : null
  }
  const breaches: Breach[] = []
  visit(sf, (node) => {
    // Rule 1: a node's own text, or the text of a same-file constant JSX renders by name.
    const own = textOf(node)
    const text = own ?? constantText(node)
    if (text !== null) {
      const shown = rendered(node)
      const notCopy = unshown(node) || (matched(node) && !insideJsx(node))
      const allowed = own !== null && declarationOf(node) !== undefined && RETIRED_ALLOWED.has(`${rel}: ${text}`)
      if ((own !== null || shown) && !notCopy && !allowed && retiredText(text, shown)) {
        breaches.push({ rule: 'retired label', at: at(node), text: text.trim() })
      }
    }
    // Rule 2: every link's copy.
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const opening = ts.isJsxElement(node) ? node.openingElement : node
      const hasAddress = opening.attributes.properties.some((p) => ts.isJsxAttribute(p) && ADDRESS_ATTRIBUTE.test(attributeName(p)))
      if (isLinkTag(opening.tagName.getText()) || hasAddress) {
        for (const copy of linkCopy(node, constantText)) {
          if (/edgar/i.test(copy)) breaches.push({ rule: 'link names EDGAR', at: at(node), text: copy.trim() })
        }
      }
    }
  })
  return breaches
}

/** Every breach in `files` (path → source), read in one program. */
export function scanAll(files: Map<string, string>): Breach[] {
  const program = programOver(files)
  const checker = program.getTypeChecker()
  return [...files.keys()].flatMap((rel) => scanFile(rel, program.getSourceFile(path.join(FRONTEND, rel))!, checker))
}

export const scan = (rel: string, source: string) => scanAll(new Map([[rel, source]]))

/** The text a stylesheet adds with `content:`, its comments taken out. */
export const cssContent = (css: string) =>
  [...css.replace(/\/\*[\s\S]*?\*\//g, ' ').matchAll(/content\s*:\s*(['"])(.*?)\1/g)].map(([, , text]) => text).filter(Boolean)

const ENTITIES: Record<string, string> = { nbsp: ' ', middot: '·', bull: '•', amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", check: '✓' }
const decodeEntities = (text: string) =>
  text.replace(/&(?:#(\d+)|#x([\da-f]+)|([a-z]+));/gi, (entity, decimal, hex, name) =>
    decimal ? String.fromCodePoint(Number(decimal)) : hex ? String.fromCodePoint(parseInt(hex, 16)) : (ENTITIES[name.toLowerCase()] ?? entity),
  )

/** The OG card's text segments: what each element shows, its entities decoded, and what its styles add with
    `content:`; comments and script blocks taken out. */
export function htmlSegments(html: string): string[] {
  const page = html.replace(/<!--[\s\S]*?-->/g, ' ')
  const added = [...page.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].flatMap(([, css]) => cssContent(css))
  const shown = page.replace(/<(style|script)\b[\s\S]*?<\/\1>/gi, ' ').split(/<[^>]+>/)
  return [...shown, ...added].map((segment) => decodeEntities(segment).trim()).filter(Boolean)
}

describe('the evidence vocabulary (D-058)', () => {
  const files = SCANNED.flatMap((dir) => filesUnder(dir, isSourceFile))

  it('reads the app', () => {
    expect(files).toEqual(
      expect.arrayContaining([
        LABELS_MODULE,
        'features/filings/components/SourceTrace.tsx',
        'features/filings/components/FilingIndex.tsx',
        'app/waitlist/page.tsx',
        'components/AiDisclaimer.tsx',
        'hooks/useRetainedFailure.tsx',
        'lib/citationMarkers.tsx',
      ]),
    )
  })

  it('ships no retired evidence label, and every link to the source names SEC.gov', () => {
    const breaches = scanAll(new Map(files.map((rel) => [rel, readFileSync(path.join(FRONTEND, rel), 'utf8')])))
    expect(breaches).toEqual([])
  })

  it('adds no retired label with a stylesheet’s content', () => {
    const sheets = SCANNED.flatMap((dir) => filesUnder(dir, (name) => name.endsWith('.css')))
    expect(sheets).toContain('app/globals.css')
    expect(sheets.flatMap((rel) => cssContent(readFileSync(path.join(FRONTEND, rel), 'utf8')).filter((text) => retiredText(text, true)))).toEqual([])
  })

  it('reads the one data attribute the app shows', () => {
    // MarkedCopy measures each `data-en-ref` mark and shows its value in the margin; another such reader is a data
    // attribute this gate must read too.
    expect(readFileSync(path.join(FRONTEND, 'components/ui/MarkedCopy.tsx'), 'utf8')).toContain(`querySelectorAll<HTMLElement>('[${SHOWN_DATA_ATTRIBUTE}]')`)
    expect(UNSHOWN_ATTRIBUTE.test(SHOWN_DATA_ATTRIBUTE)).toBe(false)
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

  it('keeps its one allowed literal only while the badge declares it once and only compares it or keys words by it', () => {
    const program = programOver(new Map([[BADGE_MODULE, readFileSync(path.join(FRONTEND, BADGE_MODULE), 'utf8')]]))
    const checker = program.getTypeChecker()
    const sf = program.getSourceFile(path.join(FRONTEND, BADGE_MODULE))!
    for (const entry of RETIRED_ALLOWED) {
      const text = entry.slice(`${BADGE_MODULE}: `.length)
      const literals: ts.Node[] = []
      visit(sf, (node) => {
        if (textOf(node) === text) literals.push(node)
      })
      expect(literals, 'the literal is written once').toHaveLength(1)
      const declaration = declarationOf(literals[0])
      expect(declaration, 'as a constant').toBeDefined()
      const reads: ts.Identifier[] = []
      visit(sf, (node) => {
        if (ts.isIdentifier(node) && node !== declaration!.name && checker.getSymbolAtLocation(node)?.valueDeclaration === declaration) reads.push(node)
      })
      expect(reads.filter((read) => matched(read) && !insideJsx(read)).length, 'the badge compares it').toBeGreaterThan(0)
      const shown = reads.filter((read) => !(matched(read) && !insideJsx(read)) && !ts.isComputedPropertyName(read.parent))
      expect(shown.map((read) => sf.getLineAndCharacterOfPosition(read.getStart(sf)).line + 1)).toEqual([])
    }
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
    ['an element given a URL in capitals', `export const A = () => <Row documentURL="https://www.sec.gov" label="Open on EDGAR" />`],
    ['an element given an address in snake case', `export const A = () => <Row fragment_url="https://www.sec.gov" label="Open on EDGAR" />`],
    ['an element given a link by another name', `export const A = () => <Row sourceLink="https://www.sec.gov" label="Open on EDGAR" />`],
    ['an element given a route', `export const A = () => <NavLink to="/filings">Open on EDGAR</NavLink>`],
    ['a constant built from a template', 'const FORM = \'10-K\'\nconst LABEL = `Open the ${FORM} on SEC EDGAR`\nexport const A = () => <a href="/f">{LABEL}</a>'],
    ['a constant written as const', `const LABEL = 'Open on SEC EDGAR' as const\nexport const A = () => <a href="/f">{LABEL}</a>`],
    ['a constant written with satisfies', `const LABEL = 'Open on SEC EDGAR' satisfies string\nexport const A = () => <a href="/f">{LABEL}</a>`],
    ['a field of a same-file object', `const LABELS = { source: 'Open on SEC EDGAR' } as const\nexport const A = () => <a href="/f">{LABELS.source}</a>`],
    ['a constant the link reads a member of', `const LABEL = 'Open on SEC EDGAR'\nexport const A = () => <a href="/f">{LABEL.toUpperCase()}</a>`],
    [
      'a function’s constant, while another function binds the name to other words',
      `function X() { const label = 'Open on SEC EDGAR'; return <a href="/f">{label}</a> }\nfunction Y() { const label = 'Open on SEC.gov'; return <span>{label}</span> }`,
    ],
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
    ['the old label as one part of a bulleted pair', `export const V = () => <span>Revenue • Verified</span>`],
    ['the old label as one part of a piped pair', `export const V = () => <span>Revenue | Cited</span>`],
    ['a bare source name as an expression', `export const T = () => <span>{'SEC EDGAR'}</span>`],
    ['a bare source name handed as a prop', `export const T = () => <Signal label="SEC EDGAR" />`],
    ['a bare source name in a title', `export const T = () => <span title="SEC EDGAR">10-K</span>`],
    ['a bare source name behind a condition', `export const T = ({ x }: { x: boolean }) => <span>{x ? 'SEC EDGAR' : null}</span>`],
    ['a bare source name rendered by name', `const SOURCE = 'SEC EDGAR'\nexport const T = () => <span>{SOURCE}</span>`],
    ['a bare source name rendered through trim', `const SOURCE = 'SEC EDGAR'\nexport const T = () => <span>{SOURCE.trim()}</span>`],
    ['a badge rendered in capitals through toUpperCase', `const BADGE = 'verified'\nexport const T = () => <span>{BADGE.toUpperCase()}</span>`],
    ['a constant badge in capitals rendered by name', `const BADGE = 'VERIFIED'\nexport const T = () => <Badge label={BADGE} />`],
    ['a label a handler sets', `export const B = () => <button onClick={() => setLabel('Verified')}>Check</button>`],
    ['a shown attribute in capitals behind a condition', `export const B = ({ ok }: { ok: boolean }) => <Chip label={ok ? 'CITED' : ''} />`],
    ['a compared label JSX renders through its variable', `export const A = ({ s }: { s: string }) => <span>{s === 'Cited' ? s : ''}</span>`],
    ['a compared label shown behind &&', `export const A = ({ b }: { b: string }) => <div>{b === 'Verified' && <span>{b}</span>}</div>`],
    ['a matched label inside JSX', `export const A = ({ s }: { s: string }) => <span>{s.startsWith('Cited') ? s : ''}</span>`],
    ['a margin mark MarkedCopy shows', `export const M = () => <p>Revenue<span data-en-ref="Verified" aria-hidden="true">[1]</span></p>`],
    ['a retired phrase as a margin mark', `export const M = () => <p>Revenue<span data-en-ref="SEC XBRL">[1]</span></p>`],
  ])('fails %s', (_, source) => {
    expect(breaches(source)).toContain('retired label')
  })

  it.each([
    ['rendered by name', `const GROUNDING_REASON = 'financial figures not grounded in SEC XBRL data'\nexport const T = () => <span>{GROUNDING_REASON}</span>`],
    ['written into JSX', `export const T = () => <span>{'financial figures not grounded in SEC XBRL data'}</span>`],
  ])('fails the allowed reason %s', (_, source) => {
    expect(breaches(source, BADGE_MODULE)).toContain('retired label')
  })

  it.each([
    ['an attribution outside a link', `export const F = () => <p>Data sourced from SEC EDGAR</p>`],
    ['a comment inside a link', `export const A = ({ u }: { u: string }) => <a href={u}>{/* the EDGAR document */}Open the filing on SEC.gov</a>`],
    ['an address built from an EDGAR helper', `export const A = ({ cik }: { cik: string }) => <a href={edgarCompanyUrl(cik)}>Full history on SEC.gov</a>`],
    ['an address handed as a url', `export const A = () => <SourceTrace url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany" label="Open the 10-K on SEC.gov" />`],
    ['an analytics event in a link’s handler', `export const A = ({ u }: { u: string }) => <a href={u} onClick={() => track('Opened SEC EDGAR')}>Open on SEC.gov</a>`],
    ['a test hook naming EDGAR', `export const A = ({ u }: { u: string }) => <a href={u} data-testid="EDGAR-link">Open on SEC.gov</a>`],
    ['a download’s file name', `export const A = ({ u }: { u: string }) => <a href={u} download="edgar-10k.pdf">Open on SEC.gov</a>`],
    ['a decorated route', `export const A = () => <Link href="/f" as="/edgar/f">Open on SEC.gov</Link>`],
    ['an id a link refers to', `export const A = ({ u }: { u: string }) => <a href={u} aria-details="edgar-note" form="edgar-form">Open on SEC.gov</a>`],
    ['an attribute that shares a constant’s name', `const title = 'EDGAR full-text search'\nexport const A = ({ u }: { u: string }) => <a href={u} title="Open on SEC.gov">10-K</a>`],
    ['a member that shares a constant’s name', `const label = 'SEC EDGAR'\nexport const A = ({ u, x }: { u: string; x: { label: string } }) => <a href={u}>{x.label}</a>`],
    ['a parameter that shares a constant’s name', `const label = 'Open on SEC EDGAR'\nexport const A = ({ u, label }: { u: string; label: string }) => <a href={u}>{label}</a>`],
    ['a sentence that cites', `export const P = () => <p>Official filings, cited and traceable to the source.</p>`],
    ['an acronym behind a plain word', `export const H = () => <details><summary>How we check</summary>We compare it with the XBRL data.</details>`],
    ['the product word in prose', `export const P = () => <p>Excerpts located in the filing’s own text, or withheld.</p>`],
    ['a source name in a keyword list', `export const K = ['SEC filings', 'SEC EDGAR']`],
    ['a sentence that starts with the word', `export const P = () => <p>Verified by the auditor before filing.</p>`],
    ['the negated word', `export const P = () => <span>Unverified</span>`],
    ['a value a comparison reads', `export const isVerified = (s: string) => s === 'Verified'`],
    ['a case a switch reads', `export function words(s: string) { switch (s) { case 'Cited': return 'Quote found in filing'; default: return s } }`],
    ['a value a membership test reads', `export const cites = (labels: string[]) => labels.includes('Cited') || labels.indexOf('Verified') > 0`],
    ['a value an affix test reads', `export const cites = (s: string) => s.startsWith('Cited') || s.endsWith('Verified')`],
    ['a key a set or map reads', `export const known = (s: Set<string>, m: Map<string, string>) => s.has('Cited') && m.get('Verified')`],
    ['an object key', `export const WORDS: Record<string, string> = { 'Cited': 'Quote found in filing', Verified: 'Matches filing' }`],
    ['a key read from an object', `export const word = (w: Record<string, string>) => w['Cited']`],
    ['a literal type', `export type Status = 'Verified' | 'Unverified'`],
    ['a status value that is never shown', `export const STATUS = 'verified'`],
    ['a type that names a field', `type Evidence = Omit<FigureEvidence, 'verified'>`],
    ['a state a data attribute carries', `export const S = ({ ok }: { ok: boolean }) => <span data-state={ok ? 'Verified' : 'pending'}>Matches filing</span>`],
    ['an id that reads like a label', `export const S = () => <section id="Cited" aria-labelledby="SEC EDGAR">Quote found in filing</section>`],
    ['a compared label in a class', `export const S = ({ s }: { s: string }) => <span className={s === 'Cited' ? 'font-semibold' : ''}>{s.length}</span>`],
  ])('passes %s', (_, source) => {
    expect(breaches(source)).toEqual([])
  })

  it('passes the allowed reason as the one constant the badge compares', () => {
    const source = [
      `const GROUNDING_REASON = 'financial figures not grounded in SEC XBRL data'`,
      `const WORDS: Record<string, string> = { [GROUNDING_REASON]: 'filed revenue or net income not stated' }`,
      `export const label = (reasons: string[]) => (reasons[0] === GROUNDING_REASON ? 'Partial coverage' : WORDS[reasons[0]])`,
    ].join('\n')
    expect(breaches(source, BADGE_MODULE)).toEqual([])
    expect(breaches(source), 'only in the badge’s module').toContain('retired label')
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

  it('reads the text a stylesheet adds', () => {
    expect(cssContent(`.chip::after { content: 'Verified'; }\n/* .old::after { content: 'Cited'; } */\n.rule::before { content: ''; }`)).toEqual(['Verified'])
  })
})

describe('the OG card scan', () => {
  it.each([
    ['{ } Revenue · SEC XBRL', true],
    ['{ } Revenue · Verified', true],
    ['{ } Revenue · Source match found', true],
    ['{ } Revenue · SEC&nbsp;XBRL', true],
    ['{ } Revenue &middot; Verified', true],
    ['{ } Revenue &#183; Cited', true],
    ['{ } Revenue • Verified', true],
    ['{ } Revenue · Matches filing', false],
    ['{ } Revenue &middot; Matches filing', false],
  ])('reads "%s" as retired: %s', (chip, retired) => {
    const html = `<style>.chip{}</style><div class="meta"><span class="chip">${chip}</span><span><b>Apple Inc.</b></span></div>`
    expect(htmlSegments(html).some((segment) => retiredText(segment, true))).toBe(retired)
  })

  it('reads the text its styles add', () => {
    const html = `<style>.chip::after { content: "Verified"; }</style><span class="chip">Revenue</span>`
    expect(htmlSegments(html).some((segment) => retiredText(segment, true))).toBe(true)
  })
})
