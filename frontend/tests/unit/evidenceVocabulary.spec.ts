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
 * string or a template (`as const`, `satisfies`, `!` and parentheses aside), each value a `?:`, `??` or `||` chooses
 * between, or one field of a same-file object. A name resolves as TypeScript resolves it, so a parameter or another
 * function's constant that shares the name is not that constant. Copy is read as a reader reads it: its character
 * references decoded as HTML decodes them (`&nbsp;`, `&#160;`, which JSX decodes in its text and an attribute's string,
 * and markup a module sets in its own), markup in a string by its text, a compatibility form as its letter (NFKC), the
 * invisible characters taken out, and each run of white space, a line break included, as one space. Not copy: comments,
 * identifiers, the values of attributes that are never shown (an address such as an href or edgarCompanyUrl's result, a
 * class, a data-* hook but `data-en-ref`, whose value MarkedCopy shows as the margin's mark, a download's file name, an
 * id and the references to one), and, outside JSX, a value a match reads: a comparison (`s === 'Verified'`), a `case`,
 * a membership or affix test (`includes`, `startsWith`, `endsWith`, `indexOf`, `has`, `get`), an object key, or a
 * literal type. Inside JSX a matched value is copy, since what it matches may be what is shown
 * (`{s === 'Cited' ? s : ''}`). An event handler's strings are not a link's copy, and rule 1 reads them as it reads a
 * string outside JSX, since a handler may set text that is shown (a toast, a label held in state): the retired phrases
 * in any case and the whole labels in their own case, so a handler's "VERIFIED" or bare "SEC EDGAR" stays
 * review-checked. An attribution outside a link ("Data sourced from SEC EDGAR" in the footer and AiDisclaimer) is not a
 * label, and the plan's R9 leaves it, as it leaves the legal pages (LEGAL, whose links keep their published words). The
 * scan reads the .ts, .tsx, .js and .jsx modules in app, components, features, hooks and lib, what the stylesheets
 * there add with `content:` (a declaration's strings joined, their escapes read: `"Verified \2713"`, its alternative
 * text after a "/" apart), and a class's generated content in a module or a stylesheet's `@apply`
 * (`before:content-['…']`, `after:[content:'…']`, an underscore a space). Each data attribute whose value the app reads
 * is listed with what it is for (DATA_READS), and one a stylesheet or a class shows with `attr()` must be one the scan
 * reads as copy.
 *
 * It cannot follow copy another module hands a link. The vocabulary module, whose labels other modules render in links
 * (sourceLinkLabel(url), which evidenceLabels.spec.ts pins), names EDGAR nowhere in its copy, which a case below
 * checks; copy any other module hands a link stays review-checked, as do a label built by concatenation or a template
 * that embeds a constant, one split across elements or read from an array, an object's keys a module renders
 * (`Object.keys`), and a control that opens an address from a handler (`window.open`). The OG card's template is read
 * for rule 1 as a browser lays it out: each element's text and each text node's, a `<br>` a space, and each `content:`
 * its styles add, as a label. The planted forms below hold the scan's reach: each way to break a rule fails, each
 * look-alike passes.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED = ['app', 'components', 'features', 'hooks', 'lib']
const LEGAL = ['app/terms/', 'app/privacy/']
const OG_TEMPLATE = 'scripts/brand/og-template.html'
const LABELS_MODULE = 'features/filings/lib/evidenceLabels.ts'
const BADGE_MODULE = 'features/summaries/components/SummaryDisplay.tsx'

// The data attributes whose values the app reads, and what for. A value read to be shown is copy, which the scan reads
// (MarkedCopy shows each `data-en-ref` as the margin's mark); one read to pick an element is not. A new read is listed
// here first.
const DATA_READS: Record<string, 'shown' | 'picks an element'> = {
  'data-en-ref': 'shown',
  'data-change-id': 'picks an element', // WordingChanges: the change a key press marks
  'data-layout-twin': 'picks an element', // layoutTwin: the copy of an element that is laid out
}

// The server's own reason string, declared once and only compared or used as the key of the badge's words, never
// shown (SummaryDisplay REASON_WORDS and BADGE_WORDS). The allowance covers that declaration's literal, not a read of it,
// and holds only while the badge never exports the constant, which would carry it where this scan cannot follow
// (allowanceProblems).
const RETIRED_ALLOWED = new Set([`${BADGE_MODULE}: financial figures not grounded in SEC XBRL data`])

const RETIRED_ANYWHERE = /SEC XBRL|Verified in filing|Source match found/i
const WHOLE_LABELS = ['Cited', 'Located in the filing', 'Verified']
const WHOLE_LABELS_ANY_CASE = new Set([...WHOLE_LABELS, 'SEC EDGAR'].map((label) => label.toLowerCase()))
// The parts of a pair: "Revenue · Matches filing", "Revenue • Matches filing", "Revenue | Matches filing".
const PAIR = /[·•|]/
// A label's own words: the punctuation, symbols and spaces around it are not part of it ("Verified ✓", "Cited.").
const labelWords = (text: string) => text.replace(/^[\s\p{P}\p{S}]+|[\s\p{P}\p{S}]+$/gu, '')

/** Text as a reader reads it: a compatibility form as its letter (NFKC, which reads a no-break space as a space), the
    invisible characters taken out (Default_Ignorable_Code_Point: a soft hyphen, a zero-width space or joiner), and each
    run of white space, a line break included, as one space, as a page lays it out. */
const asRead = (text: string) =>
  text.normalize('NFKC').replace(/\p{Default_Ignorable_Code_Point}/gu, '').replace(/\s+/gu, ' ')

/** Whether text is a retired label, `rendered` when the text is shown as it stands (JSX text, an attribute, a `{…}`). */
export function retiredText(text: string, rendered: boolean): boolean {
  const read = asRead(text)
  if (RETIRED_ANYWHERE.test(read)) return true
  const parts = read.split(PAIR).map(labelWords)
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
/** The attributes among `names` the scan does not read as copy: an address, a handler's, or one never shown. */
export const unreadAttributes = (names: string[]) =>
  names.filter((name) => ADDRESS_ATTRIBUTE.test(name) || UNSHOWN_ATTRIBUTE.test(name) || HANDLER_ATTRIBUTE.test(name))

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

/** Text as HTML reads it (`&nbsp;`, `&#160;`, `&CenterDot;`): jsdom's decoder, which knows every name JSX and Next's
    compiler decode, and HTML's newer ones. Markup in a string (an `__html`) is read by its text, its tags left out;
    other text through a textarea, whose content is text and character references, never tags. */
function decoded(text: string): string {
  if (/<[a-z!/]/i.test(text)) {
    const holder = document.createElement('template')
    holder.innerHTML = text
    return holder.content.textContent ?? text
  }
  if (!/&#?\w/.test(text)) return text
  const holder = document.createElement('textarea')
  holder.innerHTML = text
  return holder.value
}

function textOf(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node)) return decoded(node.text)
  if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) return decoded(node.text)
  return null
}

function visit(node: ts.Node, fn: (n: ts.Node) => void) {
  fn(node)
  node.forEachChild((child) => visit(child, fn))
}

/** An initializer without what leaves its value as it is: `as const`, `satisfies`, `!`, parentheses. (A `<T>` assertion
    is written only in a .ts module, which holds no JSX to render a constant.) */
function unwrap(node: ts.Expression): ts.Expression {
  let at = node
  while (ts.isAsExpression(at) || ts.isSatisfiesExpression(at) || ts.isNonNullExpression(at) || ts.isParenthesizedExpression(at)) {
    at = at.expression
  }
  return at
}

/** The copy an initializer holds: a string, a template's text without its substitutions, or each of the values a
    `?:`, `??` or `||` chooses between, joined at "|" so each reads as a label of its own. */
function initializerText(node: ts.Expression): string | null {
  const value = unwrap(node)
  const choices = ts.isConditionalExpression(value)
    ? [value.whenTrue, value.whenFalse]
    : ts.isBinaryExpression(value) && (value.operatorToken.kind === ts.SyntaxKind.BarBarToken || value.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken)
      ? [value.left, value.right]
      : null
  if (choices) {
    const texts = choices.map(initializerText).filter((text): text is string => text !== null)
    return texts.length ? texts.join(' | ') : null
  }
  if (ts.isTemplateExpression(value)) return decoded([value.head.text, ...value.templateSpans.map((span) => span.literal.text)].join(' '))
  return ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value) ? decoded(value.text) : null
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
          if (/edgar/i.test(asRead(copy))) breaches.push({ rule: 'link names EDGAR', at: at(node), text: copy.trim() })
        }
      }
    }
    // A class's generated content is shown, though the class is not copy.
    if (own !== null) {
      for (const generated of classContent(own).texts) {
        if (retiredText(generated, true)) breaches.push({ rule: 'retired label', at: at(node), text: generated })
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

// A `content:` declaration's value, to the end of the declaration: its strings (which may hold `;` or `}`) and the rest.
// A custom property named for content (`--chip-content`) is read too; `justify-content` and `align-content` hold no
// string.
const CONTENT_DECLARATION = /content\s*:((?:"(?:[^"\\]|\\[\s\S])*"|'(?:[^'\\]|\\[\s\S])*'|[^;}"'])*)/gi
// A CSS string, or the "/" that sets a content's alternative text apart (`content: "✓" / "Checked"`).
const CSS_TOKEN = /"((?:[^"\\]|\\[\s\S])*)"|'((?:[^'\\]|\\[\s\S])*)'|(\/)/g
const contentValues = (css: string) => [...css.replace(/\/\*[\s\S]*?\*\//g, ' ').matchAll(CONTENT_DECLARATION)].map(([, value]) => value)

/** A CSS string's text, its escapes read as CSS reads them: `\2713 ` is ✓, `\"` a quote, an escaped line break nothing. */
const cssUnescaped = (text: string) =>
  text.replace(/\\(?:([\da-f]{1,6})(?:\r\n|[ \t\r\n\f])?|(?:\r\n|[\r\n\f])|([\s\S]))/gi, (_, hex: string | undefined, char: string | undefined) => {
    if (hex === undefined) return char ?? ''
    const code = parseInt(hex, 16)
    return code === 0 || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff) ? '�' : String.fromCodePoint(code)
  })

/** The text a stylesheet adds with `content:`, its comments taken out: each declaration's strings, joined as CSS joins
    them, their escapes read, and its alternative text after a "/" read apart. */
export const cssContent = (css: string) =>
  contentValues(css)
    .flatMap((value) => {
      const parts = ['']
      for (const [, double, single, slash] of value.matchAll(CSS_TOKEN)) {
        if (slash) parts.push('')
        else parts[parts.length - 1] += cssUnescaped(double ?? single)
      }
      return parts
    })
    .filter(Boolean)

/** The attributes a stylesheet's `content:` shows the value of (`attr(data-label)`). */
export const cssShownAttributes = (css: string) =>
  contentValues(css).flatMap((value) => [...value.matchAll(/\battr\(\s*([\w-]+)/gi)].map(([, name]) => name))

// A class's generated content: `before:content-['Matches_filing']` (an underscore is a space, `\_` an underscore),
// `after:content-[attr(data-label)]`, or an arbitrary property, `after:[content:'Matches_filing']`.
const CLASS_CONTENT = /(?:content-\[|\[content:)(?:'([^'\s]*)'|"([^"\s]*)"|attr\(([\w-]+)\))\]/g

/** What the generated content of the classes in a text shows: its texts, and the attributes it shows with `attr()`. */
export function classContent(text: string): { texts: string[]; attributes: string[] } {
  const texts: string[] = []
  const attributes: string[] = []
  for (const [, single, double, attribute] of text.matchAll(CLASS_CONTENT)) {
    if (attribute) attributes.push(attribute)
    else texts.push((single ?? double).replace(/\\_|_/g, (match) => (match === '_' ? ' ' : '_')))
  }
  return { texts, attributes }
}

/** The data attributes a module reads the value of: `el.dataset.name`, `el.dataset['name']`, a name destructured from
    `el.dataset`, and `el.getAttribute('data-…')`; one read by a computed name, through a name of its own or by a rest
    element is `data-*`, which no entry lists, so it fails until it is written out. A write or a delete is no read. A
    dataset handed on whole is not followed (review-checked), and a JSON field named `dataset` reads as one (it fails
    closed). */
export function dataReadsIn(sf: ts.SourceFile): string[] {
  const out: string[] = []
  const attribute = (name: string) => `data-${name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`
  const isDataset = (node: ts.Node) => ts.isPropertyAccessExpression(node) && node.name.text === 'dataset'
  const written = (node: ts.Node) =>
    ts.isDeleteExpression(node.parent) || (ts.isBinaryExpression(node.parent) && node.parent.left === node && node.parent.operatorToken.kind === ts.SyntaxKind.EqualsToken)
  visit(sf, (node) => {
    if (ts.isPropertyAccessExpression(node) && isDataset(node.expression)) {
      if (!written(node)) out.push(attribute(node.name.text))
    } else if (ts.isElementAccessExpression(node) && isDataset(node.expression)) {
      if (!written(node)) out.push(ts.isStringLiteralLike(node.argumentExpression) ? attribute(node.argumentExpression.text) : 'data-*')
    } else if (ts.isVariableDeclaration(node) && ts.isObjectBindingPattern(node.name) && node.initializer && isDataset(unwrap(node.initializer))) {
      for (const element of node.name.elements) {
        const name = element.propertyName ?? element.name
        out.push(!element.dotDotDotToken && (ts.isIdentifier(name) || ts.isStringLiteral(name)) ? attribute(name.text) : 'data-*')
      }
    } else if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'getAttribute') {
      const [name] = node.arguments
      if (name && !ts.isStringLiteralLike(name)) out.push('data-*')
      else if (name && name.text.startsWith('data-')) out.push(name.text)
    }
  })
  return out
}

/** Why the badge's allowed literal could be shown, one line a problem, none while it holds: the badge writes it once,
    as a constant it does not export, compares it, and reads it nowhere else but as the key of its words. A read is the
    constant's name, a shorthand property that takes its value, or an export specifier that names it. */
export function allowanceProblems(source: string): string[] {
  const program = programOver(new Map([[BADGE_MODULE, source]]))
  const checker = program.getTypeChecker()
  const sf = program.getSourceFile(path.join(FRONTEND, BADGE_MODULE))!
  const line = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const problems: string[] = []
  for (const entry of RETIRED_ALLOWED) {
    const text = entry.slice(`${BADGE_MODULE}: `.length)
    const literals: ts.Node[] = []
    visit(sf, (node) => {
      if (textOf(node) === text) literals.push(node)
    })
    if (literals.length !== 1) {
      problems.push(`the literal is written ${literals.length} times`)
      continue
    }
    const declaration = declarationOf(literals[0])
    if (declaration === undefined) {
      problems.push(`line ${line(literals[0])}: the literal is not a constant's value`)
      continue
    }
    if (ts.getCombinedModifierFlags(declaration) & ts.ModifierFlags.Export) problems.push(`line ${line(declaration)}: the constant is exported`)
    const reads: ts.Identifier[] = []
    visit(sf, (node) => {
      if (!ts.isIdentifier(node) || node === declaration.name) return
      const parent = node.parent
      const symbol = ts.isShorthandPropertyAssignment(parent)
        ? checker.getShorthandAssignmentValueSymbol(parent)
        : ts.isExportSpecifier(parent)
          ? checker.getExportSpecifierLocalTargetSymbol(parent)
          : checker.getSymbolAtLocation(node)
      if (symbol?.valueDeclaration === declaration) reads.push(node)
    })
    const compares = reads.filter((read) => matched(read) && !insideJsx(read))
    if (!compares.length) problems.push('the badge never compares it')
    for (const read of reads) {
      if (!compares.includes(read) && !ts.isComputedPropertyName(read.parent)) problems.push(`line ${line(read)}: read where it may be shown`)
    }
  }
  return problems
}

/** The OG card's text as a browser lays it out: each element's text and each text node's, its character references
    decoded as HTML decodes them, and what its styles add with `content:`; comments, styles and scripts are not text. */
export function htmlSegments(html: string): string[] {
  const page = new DOMParser().parseFromString(html, 'text/html')
  const added = [...page.querySelectorAll('style')].flatMap((style) => cssContent(style.textContent ?? ''))
  page.querySelectorAll('style, script, template').forEach((node) => node.remove())
  page.querySelectorAll('br').forEach((br) => br.replaceWith(' '))
  const shown = [page.body, ...page.body.querySelectorAll('*')].flatMap((element) => [
    element.textContent ?? '',
    ...[...element.childNodes].filter((child) => child.nodeType === Node.TEXT_NODE).map((child) => child.textContent ?? ''),
  ])
  return [...shown, ...added].map((segment) => segment.trim()).filter(Boolean)
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

  const sheets = SCANNED.flatMap((dir) => filesUnder(dir, (name) => name.endsWith('.css')))

  it('adds no retired label with a stylesheet’s content', () => {
    expect(sheets).toContain('app/globals.css')
    const added = sheets.flatMap((rel) => {
      const css = readFileSync(path.join(FRONTEND, rel), 'utf8')
      return [...cssContent(css), ...classContent(css).texts]
    })
    expect(added.filter((text) => retiredText(text, true))).toEqual([])
  })

  it('reads as copy each data attribute whose value the app shows', () => {
    // MarkedCopy measures each `data-en-ref` mark and shows its value in the margin.
    expect(readFileSync(path.join(FRONTEND, 'components/ui/MarkedCopy.tsx'), 'utf8')).toContain(`querySelectorAll<HTMLElement>('[${SHOWN_DATA_ATTRIBUTE}]')`)
    const program = programOver(new Map(files.map((rel) => [rel, readFileSync(path.join(FRONTEND, rel), 'utf8')])))
    const read = new Set(files.flatMap((rel) => dataReadsIn(program.getSourceFile(path.join(FRONTEND, rel))!)))
    expect([...read].sort(), 'each data attribute the app reads is listed with what it is for').toEqual(Object.keys(DATA_READS).sort())
    for (const [name, use] of Object.entries(DATA_READS)) expect(UNSHOWN_ATTRIBUTE.test(name), `${name}: ${use}`).toBe(use !== 'shown')
    // An attribute a stylesheet or a class shows with attr() is copy.
    const styled = [
      ...sheets.flatMap((rel) => {
        const css = readFileSync(path.join(FRONTEND, rel), 'utf8')
        return [...cssShownAttributes(css), ...classContent(css).attributes]
      }),
      ...files.flatMap((rel) => {
        const shown: string[] = []
        visit(program.getSourceFile(path.join(FRONTEND, rel))!, (node) => {
          const text = textOf(node)
          if (text !== null) shown.push(...classContent(text).attributes)
        })
        return shown
      }),
    ]
    expect(unreadAttributes(styled)).toEqual([])
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

  it('keeps its one allowed literal only while the badge declares it once, never exports it, and only compares it or keys words by it', () => {
    expect(allowanceProblems(readFileSync(path.join(FRONTEND, BADGE_MODULE), 'utf8'))).toEqual([])
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
    ['an element given an address by a prop named for a URL', `export const A = () => <Row secUrl="https://www.sec.gov" label="Open on EDGAR" />`],
    ['an element given a link', `export const A = () => <Row link="https://www.sec.gov" label="Open on EDGAR" />`],
    ['a constant in parentheses', `const LABEL = ('Open on SEC EDGAR')\nexport const A = () => <a href="/f">{LABEL}</a>`],
    ['a constant asserted not null', `const LABEL = 'Open on SEC EDGAR'!\nexport const A = () => <a href="/f">{LABEL}</a>`],
    ['a field keyed by a string', `const LABELS = { 'source': 'Open on SEC EDGAR' }\nexport const A = () => <a href="/f">{LABELS.source}</a>`],
    ['a link that names it with a soft hyphen', `export const A = ({ u }: { u: string }) => <a href={u}>Full history on ED&shy;GAR</a>`],
    [
      'a constant a condition chooses',
      `export const A = ({ u, annual }: { u: string; annual: boolean }) => { const label = annual ? 'Open the 10-K on EDGAR' : 'Open the 10-Q on SEC.gov'; return <a href={u}>{label}</a> }`,
    ],
    ['a constant with a default', `export const A = ({ u, l }: { u: string; l?: string }) => { const label = l ?? 'Open on EDGAR'; return <a href={u}>{label}</a> }`],
    ['a constant with a fallback', `const LABEL = process.env.X || 'Open on EDGAR'\nexport const A = () => <a href="/f">{LABEL}</a>`],
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
    ['the old figure label wrapped across lines', `export const P = () => (\n  <p>\n    Figures are checked against SEC\n    XBRL data.\n  </p>\n)`],
    ['a pair spaced with character references', `export const V = () => <span>Revenue&nbsp;·&nbsp;Verified</span>`],
    ['a pair written in numeric references', `export const V = () => <span>Revenue&#160;&#183;&#160;Verified</span>`],
    ['a pair split by a reference HTML names', `export const V = () => <span>Revenue &CenterDot; Cited</span>`],
    ['the old figure label with a no-break space', "export const L = 'SEC\\u00a0XBRL figures'"],
    ['the old figure label with a no-break space by reference', `export const B = () => <Badge>SEC&#160;XBRL</Badge>`],
    ['a bare source name spaced twice', `export const T = () => <span>{'SEC  EDGAR'}</span>`],
    ['a bare source name in an attribute, spaced by reference', `export const T = () => <span title="SEC&nbsp;EDGAR">10-K</span>`],
    ['a badge with a soft hyphen', `export const V = () => <span>Veri&shy;fied</span>`],
    ['a badge with a zero-width space', "export const V = () => <span>{'Veri\\u200bfied'}</span>"],
    ['a badge in full-width letters', `export const V = () => <span>ＶＥＲＩＦＩＥＤ</span>`],
    ['a badge in parentheses', `export const T = () => <span>{('SEC EDGAR')}</span>`],
    ['a class’s generated content', `export const V = () => <span className="after:content-['Verified']">Revenue</span>`],
    ['a class’s generated content, its spaces written as underscores', `export const V = () => <span className="before:content-['Verified_in_filing']" />`],
    ['a class’s generated content in capitals', `export const V = () => <span className="after:content-['VERIFIED']">Revenue</span>`],
    ['a class’s generated content in double quotes', `export const V = () => <span className={'after:content-["Verified"]'}>Revenue</span>`],
    ['an arbitrary property’s content', `export const V = () => <span className="after:[content:'Verified']">Revenue</span>`],
    ['a badge a condition chooses', `export const B = ({ ok }: { ok: boolean }) => { const BADGE = ok ? 'VERIFIED' : 'PENDING'; return <span>{BADGE}</span> }`],
    ['a bare source name a condition chooses', `export const T = ({ x }: { x: boolean }) => { const SOURCE = x ? 'SEC EDGAR' : 'SEC.gov'; return <span>{SOURCE}</span> }`],
    ['markup a module sets', `export const M = () => <span dangerouslySetInnerHTML={{ __html: 'Revenue · <b>Verified</b>' }} />`],
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
    ['a class’s generated quote marks', `export const Q = () => <blockquote className="before:content-['“'] after:content-['”']">Revenue grew.</blockquote>`],
    ['a counter a class generates', `export const R = () => <span className="before:content-[counter(row,decimal-leading-zero)]" />`],
    ['prose wrapped across lines', `export const P = () => (\n  <p>\n    Each figure is checked against the filing’s\n    XBRL data.\n  </p>\n)`],
    [
      'a condition that chooses between the plain labels',
      `export const B = ({ ok }: { ok: boolean }) => { const BADGE = ok ? 'Matches filing' : 'Linked, not checked'; return <span>{BADGE}</span> }`,
    ],
    ['markup with plain words', `export const M = () => <span dangerouslySetInnerHTML={{ __html: '<b>Matches filing</b>' }} />`],
  ])('passes %s', (_, source) => {
    expect(breaches(source)).toEqual([])
  })

  const declared = `const GROUNDING_REASON = 'financial figures not grounded in SEC XBRL data'`
  const keyed = `const WORDS: Record<string, string> = { [GROUNDING_REASON]: 'filed revenue or net income not stated' }`
  const compared = `export const label = (reasons: string[]) => (reasons[0] === GROUNDING_REASON ? 'Partial coverage' : WORDS[reasons[0]])`

  it('passes the allowed reason as the one constant the badge compares', () => {
    const source = [declared, keyed, compared].join('\n')
    expect(breaches(source, BADGE_MODULE)).toEqual([])
    expect(breaches(source), 'only in the badge’s module').toContain('retired label')
    expect(allowanceProblems(source)).toEqual([])
  })

  it.each([
    ['exported', [`export ${declared}`, keyed, compared]],
    ['exported by name', [declared, keyed, compared, 'export { GROUNDING_REASON }']],
    ['exported under another name', [declared, keyed, compared, 'export { GROUNDING_REASON as REASON }']],
    ['exported as the default', [declared, keyed, compared, 'export default GROUNDING_REASON']],
    ['handed on in a shorthand property', [declared, keyed, compared, 'export const REASONS = { GROUNDING_REASON }']],
    ['rendered', [declared, keyed, compared, 'export const T = () => <span>{GROUNDING_REASON}</span>']],
    ['put in a template', [declared, keyed, compared, 'export const line = `${GROUNDING_REASON}`']],
    ['held by another constant', [declared, keyed, compared, 'const REASON = GROUNDING_REASON', 'export const isIt = (r: string) => r === REASON']],
    ['written twice', [declared, keyed, compared, `export const AGAIN = 'financial figures not grounded in SEC XBRL data'`]],
    ['never compared', [declared, keyed, 'export const words = (r: string) => WORDS[r]']],
    ['not a constant', [`export const label = (r: string) => (r === 'financial figures not grounded in SEC XBRL data' ? 'Partial coverage' : r)`]],
  ])('withdraws the allowance from a reason %s', (_, lines) => {
    expect(allowanceProblems(lines.join('\n'))).not.toEqual([])
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
    // A declaration's strings joined, their escapes read, a string's `;` and `}` its own; `justify-content` adds nothing.
    const sheet = `.a::after { content: "Verified \\2713"; } .b::before { content: "Ver" 'ified'; } .c { justify-content: center; } .d::after { content: "a;b}c"; } .e::after { content: "\\"Cited\\""; }`
    expect(cssContent(sheet)).toEqual(['Verified ✓', 'Verified', 'a;b}c', '"Cited"'])
    expect(cssContent(sheet).filter((text) => retiredText(text, true))).toEqual(['Verified ✓', 'Verified', '"Cited"'])
    // A content's alternative text is read apart, and a custom property named for content is read too.
    expect(cssContent(`.f::after { content: "✓" / "Verified"; } .g { --chip-content: 'Cited'; }`)).toEqual(['✓', 'Verified', 'Cited'])
  })

  it('reads the attributes a style shows and the data attributes a module reads', () => {
    expect(cssShownAttributes(`.x::after { content: attr(data-label); }\n.y::after { content: " (" attr(href) ")"; }\n.z { content: none; }`)).toEqual(['data-label', 'href'])
    expect(classContent(`after:content-[attr(data-label)] before:content-['Matches_filing'] after:content-['a\\_b']`)).toEqual({
      texts: ['Matches filing', 'a_b'],
      attributes: ['data-label'],
    })
    // An arbitrary property, and a stylesheet's @apply.
    expect(classContent(`after:[content:'Matches_filing'] before:[content:attr(title)]`)).toEqual({ texts: ['Matches filing'], attributes: ['title'] })
    expect(classContent(`.chip { @apply after:content-['Verified']; }`).texts).toEqual(['Verified'])
    expect(unreadAttributes(['data-label', 'aria-label', 'href', 'onClick', 'data-en-ref', 'title'])).toEqual(['data-label', 'href', 'onClick'])
    const planted = (source: string) => ts.createSourceFile('features/x/Planted.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const reads = [
      `const a = el.dataset.enRef`,
      `const b = el.dataset?.['changeId']`,
      `const c = el.getAttribute('data-label')`,
      `const { label, layoutTwin: twin } = el.dataset`,
      `const d = el.dataset[key]`,
      `const { ...rest } = el.dataset`,
      `const e = el.getAttribute(LABEL_ATTRIBUTE)`,
      'const f = el.getAttribute(`data-${key}`)',
      `el.dataset.count += 1`,
    ].join('\n')
    expect(dataReadsIn(planted(reads))).toEqual([
      'data-en-ref', 'data-change-id', 'data-label', 'data-label', 'data-layout-twin', 'data-*', 'data-*', 'data-*', 'data-*', 'data-count',
    ])
    // A write or a delete is no read.
    expect(dataReadsIn(planted([`el.dataset.label = 'x'`, `delete el.dataset.label`, `el.dataset['label'] = 'y'`].join('\n')))).toEqual([])
    // A variable named dataset, a field of that name, and an attribute that is not data, are no data attribute read.
    const others = [`const s = dataset.series`, `const t = el.getAttribute('title')`, `const u = demo.dataset as unknown as AnalysisDataset`].join('\n')
    expect(dataReadsIn(planted(others))).toEqual([])
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
    ['{ } Revenue · SEC&#160;XBRL', true],
    ['{ } Revenue &#xB7; Verified', true],
    ['{ } Revenue &bull; Verified', true],
    ['{ } Revenue &CenterDot; Verified', true],
    ['{ } Revenue · Verified in\n      filing', true],
    ['{ } Revenue · SEC <b>XBRL</b>', true],
    ['{ } Revenue · Cited <b>3</b>', true],
    ['Figures from SEC<br>XBRL data', true],
    ['{ } Revenue · Matches filing', false],
    ['{ } Revenue &middot; Matches filing', false],
    ['{ } Revenue · <b>Matches</b> filing', false],
  ])('reads "%s" as retired: %s', (chip, retired) => {
    const html = `<style>.chip{}</style><div class="meta"><span class="chip">${chip}</span><span><b>Apple Inc.</b></span></div>`
    expect(htmlSegments(html).some((segment) => retiredText(segment, true))).toBe(retired)
  })

  it('reads the text its styles add', () => {
    const html = `<style>.chip::after { content: "Verified"; }</style><span class="chip">Revenue</span>`
    expect(htmlSegments(html).some((segment) => retiredText(segment, true))).toBe(true)
    const escaped = `<style>.chip::after { content: "Verified \\2713"; }</style><span class="chip">Revenue</span>`
    expect(htmlSegments(escaped).filter((segment) => retiredText(segment, true))).toEqual(['Verified ✓'])
  })

  it('reads no comment, style or script as text', () => {
    const html = `<!-- Verified --><style>.x { color: red; }</style><script>const label = 'Cited'</script><span>Apple Inc.</span>`
    expect([...new Set(htmlSegments(html))]).toEqual(['Apple Inc.'])
  })
})
