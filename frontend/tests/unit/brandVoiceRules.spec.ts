import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { heldValues, leavesOf, scopeResolver } from './heldValues'
import { isIconModule } from './iconModules'

/**
 * The voice rules of docs/brand/07-voice.md as one gate (CLAUDE.md rule 12; docs/brand/decisions-log.md
 * D-031). Until this spec they were prose, and the 2026-10 audit found each of them broken somewhere.
 * It reads the TypeScript AST of every shipped module under app, components, features, hooks and lib:
 *
 *  - sentenceCase: a label is in sentence case: its first word starts with a capital (or a digit, a
 *    symbol or an expression), after the first word of a phrase a capitalised word must be a proper noun
 *    (PROPER_NOUNS), and a label of two or more words is never all capitals, whatever punctuation closes a
 *    word (`START FREE TRIAL`, `START FREE TRIAL…`, `SIGN-UP NOW:`; an acronym beside lowercase words, `Export CSV`, passes). The labels read: the text of a heading (h1 to h6), of a
 *    dialog or card title (ModalHeader, CardTitle, CardHeader), of a button (<Button>, <button>, and any
 *    element whose className reaches buttonVariants(), such as a <Link> or <a> styled as a button) and
 *    of every component found to render its children into one of those (see discoverReach), a component read by the name
 *    its module exports (an import under another name, `CardTitle as Title`, or a namespace's member); the title
 *    prop of a GuidanceCard, Notice, Modal, ModalHeader, SecondaryHeader or UpgradeModal and of every
 *    component found to render its title prop into a label; every aria-label; a page's metadata title.
 *    The check is a heuristic, so a false positive goes to the residue with its reason, never to a
 *    weaker regex. Its limits: a label passed through a variable of another name (`const heading =
 *    title`), a component's title read from a spread, a label built in a function and returned, and a
 *    className styled through a variable (`const btn = buttonVariants()`) are not followed; those stay
 *    review-checked (lessons/test-gates-must-be-as-wide-as-their-rule.md). A label joined with `+` is
 *    read as the joined text.
 *  - exclamation: no exclamation mark in copy, wherever it sits (`Great!!`, `Really!?`, `Hello!Welcome`); the
 *    source a RegExp is built from is code, not copy.
 *  - emoji: no emoji in copy: a character that presents as an emoji by default, or any pictograph
 *    forced to one with U+FE0F. Typographic glyphs (the ▲ ▼ direction marks, ↗ for an external link,
 *    © ® ™) are text, not emoji.
 *  - buzzword: none of the banned words (BUZZWORDS).
 *  - headingIcon: no icon element inside a heading (a section heading carries no icon; DESIGN.md). An icon is
 *    a tag bound to an import from @/lib/icons (by its alias or a relative path) or the Phosphor package (any
 *    entry), under any local name or as a namespace's member (tests/unit/iconModules.ts), a tag named
 *    ...Icon (a hand-drawn component named for its icon), or a same-file binding that holds one, read by its
 *    name to a fixed point (`const AlertMark = BellIcon`, `const Mark = Ph.Bell`, a conditional or a chain of
 *    them, a member destructured from an icon namespace), or an object's property that holds one (`<MARK.alert />`,
 *    `MARK[kind]` held by a binding, a spread of the object, a nested member); and an icon element a binding holds,
 *    placed in the heading (`const mark = <BellIcon />` read as `{mark}`). A value is followed by the reading the glyph
 *    gate shares (tests/unit/heldValues.ts) from every place a name is given one: its declaration, each assignment, a
 *    destructuring, a loop, a parameter at each same-file call (a component's props included), a callback however it is
 *    handed over, a function's return, what is put in an object after it is made, and React's createElement,
 *    cloneElement and Children; any other expression placed in the heading is read by its value (`{ok && mark}`,
 *    `{createElement(BellIcon)}`). Out of reach, planted as gaps in the self-check and review-checked: an icon that
 *    crosses modules (an app module's export), React state, a class's field read through `this`, a promise's
 *    `then` and a generator's `yield`.
 *  - developerWording: copy in lib/ and hooks/ (the fallback errors a user reads) never names the
 *    backend, an API path, a "reader" or an HTTP status number.
 *
 * Copy is a JSX text node, or a string or template literal outside the places code keeps its own
 * strings (imports, class lists, comparisons, identifiers such as hrefs and keys; see isCodeString). A
 * `createElement` call is read as JSX is: its type is code, a prop is read by the attribute's rule and a
 * child is copy (the literal clauses; the label clauses read JSX elements only). What `replace` puts in a
 * pattern's place, and the value `setAttribute` gives an attribute that is not code, are read by their context. An
 * attribute that is not code (CODE_ATTRS) is copy, so a placeholder, an aria-label, an alt or a title is
 * read by the exclamation, emoji and buzzword clauses (and by no-em-dash-copy.spec.ts, which reads every
 * literal), whatever its shape, and so is an expression rendered as an element's child; a string with no
 * context that says copy or code is read as a class list when it is shaped like one (lowercase tokens, one
 * with a hyphen, a colon or a bracket), so a lowercase phrase held in a variable or an object property of
 * another name (`const SUBHEAD = 'decision-ready insights'`) is the scan's limit and review-checked. A JSON module the app imports is data this scan does not read, so the copy it holds
 * (features/analysis/demo/demo-analysis.json, the landing's samples) is review-checked
 * (tests/unit/importWalk.ts).
 *
 * DEVELOPER_WORDING's HTTP status is any three-digit number from 400 to 599, so a count in a sentence
 * ("500 companies") fails it too. Its scope (lib/ and hooks/) holds no such sentence today; one that
 * needs a count writes it through a value (`${count} companies`), which reads as `{x}`.
 *
 * VOICE_RESIDUE holds what the audit found on the day the gate landed, counted per file and clause.
 * It only shrinks: each surface PR that fixes a file lowers or deletes its line, a new violation fails
 * (an unlisted file, or a listed count that rises), a fixed one fails until its count is lowered, and
 * the list's size equals VOICE_RESIDUE_MAX, which seeds at the audit's count and moves with the list in
 * the same commit (a shrink lowers it, so no slack is left). A PR that must add an entry raises it and
 * says why in its body.
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

type Clause = 'sentenceCase' | 'exclamation' | 'emoji' | 'buzzword' | 'headingIcon' | 'developerWording'

/** Names that keep their capitals mid-phrase: the product's names, the regulator and its systems, the
    nine parts of the summary outline (backend/app/services/summary_schema.py SECTION_META), months and
    the third parties a page names. Longest first, so a phrase wins over its words. */
const PROPER_NOUNS = [
  'Earnings Quality & Cash Conversion', 'Value Drivers & Capital Allocation', 'Balance Sheet & Liquidity',
  'Results That Matter', 'Multi-Period Analysis', 'Notable Footnotes', 'Forward Signals', 'Ask this Filing',
  'Trace to Source', 'The Print', 'Segments', 'Risks',
  // The summary's export titles (backend/app/services/summary_sections.py) and the filing's own names.
  'Financial Highlights', 'Executive Assessment', 'Item 1A', 'Form 4', 'S&P 500', 'Nasdaq 100',
  'EarningsNerd', 'Pro', 'SEC', 'EDGAR', 'XBRL', 'U.S.',
  'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December',
  'Jan', 'Feb', 'Mar', 'Apr', 'Jun', 'Jul', 'Aug', 'Sep', 'Sept', 'Oct', 'Nov', 'Dec',
  'Google', 'Apple', 'Stripe', 'GitHub', 'LinkedIn', 'WhatsApp', 'Twitter', 'Excel', 'Markdown',
].sort((a, b) => b.length - a.length)

/** Each proper noun as a whole word: 'Pro' never swallows the start of 'Profile', nor 'Mar' of 'Margin'. */
const PROPER_NOUN_RES = PROPER_NOUNS.map(
  (noun) => new RegExp(`(?<![\\p{L}\\p{N}])${noun.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\p{L}\\p{N}])`, 'gu'),
)

const BUZZWORDS: Array<[string, RegExp]> = [
  ['unlock', /\bunlock(?:s|ed|ing)?\b/i],
  ['seamless', /\bseamless(?:ly)?\b/i],
  ['effortless', /\beffortless(?:ly)?\b/i],
  ['empower', /\bempower(?:s|ed|ing|ment)?\b/i],
  ['supercharge', /\bsupercharg(?:e|es|ed|ing)\b/i],
  ['transform', /\btransform(?:s|ed|ing|ative)?\b/i],
  ['actionable', /\bactionable\b/i],
  ['decision-ready', /\bdecision-ready\b/i],
  ['game-changing', /\bgame-chang(?:ing|er)\b/i],
  ['clarity', /\bclarity\b/i],
  ['edge', /\b(?:an?|the|your|our) edge\b/i],
  ['markets move fast', /\bmarkets move fast\b/i],
]

const EMOJI = /\p{Emoji_Presentation}|\p{Extended_Pictographic}\uFE0F/u
/** Every emoji in a text: each is a finding, so a second one in an already-listed literal counts. */
const EMOJI_ALL = new RegExp(EMOJI.source, 'gu')
const EXCLAMATION = /!/u
const DEVELOPER_WORDING = /\bbackend\b|\/api\/|\breader\b|\b[45]\d\d\b/i
const HEADINGS = new Set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
/** Components whose title prop is a visible title. UpgradeModal is named because its title reaches its
    ModalHeader through a local (`const heading = title ?? …`), which discoverReach does not follow. */
const TITLED = new Set(['GuidanceCard', 'Notice', 'Modal', 'ModalHeader', 'SecondaryHeader', 'UpgradeModal'])
/** Components whose children are a title: the dialog's header, the card's title and the card's header
    (CardTitle spreads its props onto an h3, which discoverReach cannot see). */
const TITLE_CHILDREN = new Set(['ModalHeader', 'CardTitle', 'CardHeader'])
const BUTTONS = new Set(['Button', 'button'])
const CONTROLS = new Set(['Button', 'button', 'a', 'Link'])
/** Attributes that hold code, not copy. */
const CODE_ATTRS = /^(?:className|class|href|src|srcSet|id|key|type|role|name|rel|target|variant|size|as|method|action|htmlFor|autoComplete|inputMode|enterKeyHint|lang|viewBox|d|fill|stroke|strokeWidth|strokeLinecap|strokeLinejoin|xmlns|mode|side|align|tone|tabIndex|pattern|form|scope|dateTime|sizes|crossOrigin|referrerPolicy|layout|data-[\w-]+|aria-(?:controls|labelledby|describedby|haspopup|live|current|expanded|hidden|selected|pressed|checked|disabled|modal|orientation|sort|atomic|relevant|busy|invalid|required|owns|activedescendant))$/
/** CODE_ATTRS for a DOM attribute's name, which is lowercase (`tabindex`, `for`). */
const CODE_ATTRS_ANY_CASE = new RegExp(CODE_ATTRS.source.replace('htmlFor|', 'htmlFor|for|'), 'i')
/** Calls whose string arguments are code: class lists, keys, selectors, patterns, event names. Two positions are read
    by their context instead (isCodeString): what `replace` and `replaceAll` put in a pattern's place, and the value
    `setAttribute` gives an attribute that is not code; `createElement` is read as JSX is. */
const CODE_CALLS = new Set(['RegExp', 'cx', 'clsx', 'cn', 'buttonVariants', 'inputClasses', 'require', 'querySelector', 'querySelectorAll', 'getItem', 'setItem', 'removeItem', 'addEventListener', 'removeEventListener', 'getElementById', 'matchMedia', 'startsWith', 'endsWith', 'includes', 'replace', 'replaceAll', 'split', 'test', 'match', 'capture', 'track', 'identify', 'register', 'useQuery', 'setAttribute', 'getAttribute'])

interface Finding {
  rel: string
  line: number
  clause: Clause
  text: string
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const parse = (source: string, fileName: string) =>
  ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)

/** A literal's text, a template's `${…}` read as `{x}`. */
function literalText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text
  if (ts.isJsxText(node)) return node.containsOnlyTriviaWhiteSpaces ? null : node.text
  if (ts.isTemplateExpression(node)) return [node.head.text, ...node.templateSpans.map((span) => `{x}${span.literal.text}`)].join('')
  return null
}

const looksLikeClasses = (text: string) => {
  const tokens = text.trim().split(/\s+/).filter(Boolean)
  return tokens.length > 0 && tokens.every((t) => /^[!a-z0-9:_\-[\]/.%#&>()=,*@~+{}'"]+$/.test(t)) && tokens.some((t) => /[-:[]/.test(t))
}

const callName = (call: ts.CallExpression) =>
  ts.isIdentifier(call.expression) ? call.expression.text : ts.isPropertyAccessExpression(call.expression) ? call.expression.name.text : ''

/** Whether a string literal is code's own string, not copy: an import, a key, a comparison, a code attribute or
    argument, or, with no context that says either, a class list by its shape. Context is read first, so a copy
    attribute (a title, an aria-label) and an expression rendered as an element's child are copy whatever their
    shape ("decision-ready insights" reads as a class list by shape alone). */
function isCodeString(node: ts.Node, text: string): boolean {
  if (ts.isJsxText(node)) return false
  if (!/\p{L}/u.test(text)) return true
  // Markup a module builds (an SVG for an export) is code.
  if (/<\/?[a-z][\w-]*[\s>/]/.test(text)) return true
  const parent = node.parent
  if (!parent) return true
  if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent) || ts.isExternalModuleReference(parent) || ts.isLiteralTypeNode(parent)) return true
  if ((ts.isPropertyAssignment(parent) || ts.isPropertyDeclaration(parent) || ts.isMethodDeclaration(parent)) && parent.name === node) return true
  if (ts.isElementAccessExpression(parent) || ts.isCaseClause(parent)) return true
  if (ts.isBinaryExpression(parent) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken, ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.InKeyword].includes(parent.operatorToken.kind)) return true
  // The outermost property passed on the way up, for a createElement call's props.
  let prop: string | undefined
  for (let n: ts.Node | undefined = parent, from: ts.Node = node; n; from = n, n = n.parent) {
    if (ts.isJsxAttribute(n)) return CODE_ATTRS.test(n.name.getText())
    if (ts.isPropertyAssignment(n) && /^(?:className|classNames|href|key|queryKey|id|type|variant)$/.test(n.name.getText())) return true
    if (ts.isPropertyAssignment(n)) prop = ts.isIdentifier(n.name) || ts.isStringLiteral(n.name) ? n.name.text : n.name.getText()
    // createElement(type, props, ...children) reads as JSX does: the type is code (a DOM node's tag too, as in
    // `document.createElement('a')`), a prop is read by the attribute's rule, and a child is copy.
    if (ts.isCallExpression(n) && callName(n) === 'createElement') {
      const at = n.arguments.indexOf(from as ts.Expression)
      return at === 1 ? prop === undefined || CODE_ATTRS.test(prop) : at < 2
    }
    if (ts.isCallExpression(n) && CODE_CALLS.has(callName(n))) {
      // A replacement is read by its context (`<p>{note.replace('x', 'Wow!')}</p>` renders it), and so is an attribute's
      // value when the attribute is not code (`el.setAttribute('aria-label', …)`).
      const at = n.arguments.indexOf(from as ts.Expression)
      const attribute = n.arguments[0]
      if (/^replace(?:All)?$/.test(callName(n)) && at > 0) continue
      if (callName(n) === 'setAttribute' && at === 1 && !(ts.isStringLiteralLike(attribute) && CODE_ATTRS_ANY_CASE.test(attribute.text))) continue
      return true
    }
    // The source a RegExp is built from (`new RegExp(\`(?<!x)[.!?]\`)`) is a pattern, not a sentence.
    if (ts.isNewExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === 'RegExp') return true
    // An expression rendered as an element's child is copy, whatever its shape.
    if (ts.isJsxExpression(n) && (ts.isJsxElement(n.parent) || ts.isJsxFragment(n.parent))) return false
    if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isBlock(n) || ts.isSourceFile(n)) break
  }
  return looksLikeClasses(text)
}

/** A word as it is spelled: the punctuation that opens or closes it (`More…`, `Again!`, `(Beta)`) is not its spelling. */
const bareWord = (raw: string) => raw.replace(/^['‘’"“(\[]+|[,.;:!?…'‘’"”)\]]+$/g, '')

/** The words that break sentence case: a capitalised word after a phrase's first that is not a proper noun, a
    first word that starts lowercase, and every word of a label two or more words long written all in capitals. */
export function titleCaseWords(text: string): string[] {
  let t = ` ${text} `
  for (const noun of PROPER_NOUN_RES) t = t.replace(noun, ' {n} ')
  const out: string[] = []
  // A phrase starts again after a sentence stop, a separator, a bracket or quote, or an expression
  // (`{x}`: an icon or a value before a label).
  t.split(/[.?!|·:;–—]\s+|\s[-–—]\s|\n|\(|\)|["“”]|\{x\}/).forEach((segment, index) => {
    const words = segment.trim().split(/\s+/).filter(Boolean)
    // The label's first word starts with a capital, a digit or a symbol; a lowercase start (`save changes`) is
    // not sentence case. A later phrase may start lowercase (`{count} companies`, `Filed · today`).
    const first = words[0]?.replace(/^['‘’]+/, '')
    if (index === 0 && first && /^\p{Ll}/u.test(first)) out.push(first)
    words.slice(1).forEach((raw) => {
      // A word's own punctuation is not its spelling: `More…` and `Again!` are read as `More` and `Again`.
      const word = bareWord(raw)
      if (/^[A-Z][a-z]+(?:['’]s)?$/.test(word)) out.push(word)
    })
  })
  // Two or more words all in capitals (`START FREE TRIAL`) is shouting, not a label; an acronym stands alone or
  // beside lowercase words (`Export CSV`). Each word is read as spelled (bareWord: `TRIAL…` and `NOW:` are capitals),
  // a hyphen or an apostrophe inside it included (`SIGN-UP`, `DON'T`). A proper noun (`{n}` above) and an expression
  // (`{x}`) are not words of the label: `SEC FILING ALERTS` and `{count} NEW FILINGS` shout in the words around them.
  const lettered = t.trim().split(/\s+/).map((w) => bareWord(w.replace(/\{[nx]\}/g, ''))).filter((w) => /\p{L}/u.test(w))
  if (lettered.length >= 2 && lettered.every((w) => /^[A-Z]{2,}(?:[-'’][A-Z]+)*$/.test(w))) out.push(...lettered)
  return out
}

/** The texts an expression can render where copy is read in context (a button label, a heading, a
    title): each literal leaf of a conditional, of a logical and/or/nullish expression and of a
    parenthesised one, so `{busy ? 'Sending Message' : 'Send Message'}` is read as both labels, and the
    texts of a JSX element or fragment in such a branch (`{busy ? <span>Sending now</span> : 'Send'}`).
    The condition of an `&&` renders nothing a reader sees. A `+` joins each variant of its left side to
    each of its right (`{'Send Message' + ' Again Later'}` reads as the label a reader sees); any other
    expression reads as `{x}`, and so does an element that is a label of its own (`read`), which is read
    where it stands. */
function renderedVariants(expr: ts.Expression, read: ReadsLabel): string[] {
  if (ts.isParenthesizedExpression(expr)) return renderedVariants(expr.expression, read)
  if (ts.isConditionalExpression(expr)) return [...renderedVariants(expr.whenTrue, read), ...renderedVariants(expr.whenFalse, read)]
  if (ts.isBinaryExpression(expr)) {
    const op = expr.operatorToken.kind
    if (op === ts.SyntaxKind.AmpersandAmpersandToken) return renderedVariants(expr.right, read)
    if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken)
      return [...renderedVariants(expr.left, read), ...renderedVariants(expr.right, read)]
    if (op === ts.SyntaxKind.PlusToken) {
      const right = renderedVariants(expr.right, read)
      return renderedVariants(expr.left, read).flatMap((left) => right.map((r) => left + r))
    }
  }
  if (ts.isJsxElement(expr) && read(expr.openingElement)) return ['{x}']
  if (ts.isJsxElement(expr) || ts.isJsxFragment(expr)) return childTexts(expr, read).map((t) => t.replace(/\s+/g, ' '))
  return [literalText(expr) ?? '{x}']
}

/** The most combinations of its conditionals' leaves one element is read in. Past it the element is not
    sliced to its first combinations (that would drop whole branches unread): the scan throws, naming the
    element and its count, and the gate fails until the element is split or the bound raised. Today's
    tree reads at most 4 per heading or button. */
const MAX_VARIANTS = 32

const where = (node: ts.Node) => {
  const sf = node.getSourceFile()
  return `${sf.fileName}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
}

/** The texts an element or fragment's children can render, one per combination of its conditionals'
    leaves, other expressions read as `{x}`. An attribute is never label text, so a child's attributes
    (an icon's `className={a ? 'x' : 'y'}`) are not read and add no combinations. A child that is a label
    of its own (a CardTitle or a button inside a CardHeader) reads as `{x}` here and is read on its own,
    so its text is neither counted twice nor run into its neighbour's. */
function childTexts(owner: ts.JsxElement | ts.JsxFragment, read: ReadsLabel): string[] {
  let texts = ['']
  let count = 1
  const append = (options: string[]) => {
    count *= options.length
    texts = count > MAX_VARIANTS ? [] : texts.flatMap((t) => options.map((o) => t + o))
  }
  const visit = (node: ts.Node) => {
    if (ts.isJsxAttributes(node)) return
    if (ts.isJsxElement(node) && read(node.openingElement)) {
      append(['{x}'])
      return
    }
    if (ts.isJsxText(node)) append([node.text])
    else if (ts.isJsxExpression(node)) {
      append(node.expression ? renderedVariants(node.expression, read) : ['{x}'])
      return
    }
    ts.forEachChild(node, visit)
  }
  owner.children.forEach(visit)
  if (count > MAX_VARIANTS) {
    const tag = ts.isJsxElement(owner) ? owner.openingElement.tagName.getText() : ''
    throw new Error(`${where(owner)} <${tag}> renders ${count} combinations of its conditionals, more than MAX_VARIANTS (${MAX_VARIANTS}) reads: split the element or raise the bound`)
  }
  return texts
}

/** The texts an element can render (childTexts, whitespace collapsed, each once). */
const elementTexts = (element: ts.JsxElement, read: ReadsLabel) => [...new Set(childTexts(element, read).map((t) => t.replace(/\s+/g, ' ').trim()))]

/** The first of the texts a node can render that breaks sentence case. */
const titleCased = (texts: string[]) => texts.find((t) => titleCaseWords(t).length)

/** The names a source imports under another name, and its namespace imports: `import { CardTitle as Title }` maps
    `Title` to `CardTitle`. */
const importsBySource = new WeakMap<ts.SourceFile, { renamed: Map<string, string>; namespaces: Set<string> }>()
const importsOf = (sf: ts.SourceFile) => {
  let found = importsBySource.get(sf)
  if (!found) {
    found = { renamed: new Map(), namespaces: new Set() }
    for (const stmt of sf.statements) {
      const bindings = ts.isImportDeclaration(stmt) ? stmt.importClause?.namedBindings : undefined
      if (bindings && ts.isNamedImports(bindings)) for (const el of bindings.elements) if (el.propertyName) found.renamed.set(el.name.text, el.propertyName.text)
      if (bindings && ts.isNamespaceImport(bindings)) found.namespaces.add(bindings.name.text)
    }
    importsBySource.set(sf, found)
  }
  return found
}
const resolvers = new WeakMap<ts.SourceFile, ReturnType<typeof scopeResolver>>()
const declarationOf = (id: ts.Identifier) => {
  const sf = id.getSourceFile()
  const resolve = resolvers.get(sf) ?? scopeResolver(sf)
  resolvers.set(sf, resolve)
  return resolve(id)
}
/** The names an expression naming a component may be: a same-file alias, resolved by scope, is every name its
    initializer may be (`const Title = CardTitle`, `const Heading = big ? 'h2' : 'h3'`, a fallback's two sides); an
    import renamed in the file is the name its module exports (`CardTitle as Title`), a namespace's member its member's
    name (`UI.CardTitle`) and a string its tag. What the scan cannot read names nothing. */
function namesOf(e: ts.Expression, seen: Set<ts.Node>): string[] {
  const x = unwrapHeld(e)
  if (ts.isIdentifier(x)) {
    const declaration = declarationOf(x)
    if (declaration && ts.isVariableDeclaration(declaration) && declaration.initializer && !seen.has(declaration)) {
      seen.add(declaration)
      const names = namesOf(declaration.initializer, seen)
      if (names.length) return names
    }
    return [importsOf(x.getSourceFile()).renamed.get(x.text) ?? x.text]
  }
  if (ts.isPropertyAccessExpression(x) && ts.isIdentifier(x.expression) && importsOf(x.getSourceFile()).namespaces.has(x.expression.text)) return [x.name.text]
  if (ts.isStringLiteralLike(x)) return [x.text]
  if (ts.isConditionalExpression(x)) return [...namesOf(x.whenTrue, seen), ...namesOf(x.whenFalse, seen)]
  const op = ts.isBinaryExpression(x) ? x.operatorToken.kind : undefined
  if (ts.isBinaryExpression(x) && (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken)) return [...namesOf(x.left, seen), ...namesOf(x.right, seen)]
  return []
}
/** The components a tag may render (namesOf), since neither a rename nor an alias changes what renders; a tag the
    scan cannot resolve is read by its own text. */
const tagsOf = (node: ts.JsxOpeningLikeElement): string[] => {
  const names = ts.isIdentifier(node.tagName) || ts.isPropertyAccessExpression(node.tagName) ? namesOf(node.tagName, new Set()) : []
  return names.length ? names : [node.tagName.getText()]
}
/** An expression under its parentheses and type assertions (`as`, `satisfies`, `!`). */
const unwrapHeld = (e: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isNonNullExpression(e) ? unwrapHeld(e.expression) : e

const attribute = (node: ts.JsxOpeningLikeElement, name: string) =>
  node.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === name)

/** An attribute's value as an expression (`title="x"` or `title={x}`). */
const attributeValue = (attr: ts.JsxAttribute | undefined) => {
  const init = attr?.initializer
  return init && ts.isJsxExpression(init) ? init.expression : init
}

/** Whether an element's className reaches the DS button factory: a <Link> or <a> styled as a button. */
function reachesButtonVariants(node: ts.JsxOpeningLikeElement): boolean {
  let hit = false
  const find = (n: ts.Node) => {
    if (ts.isCallExpression(n) && callName(n) === 'buttonVariants') hit = true
    else ts.forEachChild(n, find)
  }
  const value = attributeValue(attribute(node, 'className'))
  if (value) find(value)
  return hit
}

/** Whether an element's children are a label the sentence-case clause reads. */
type ReadsLabel = (node: ts.JsxOpeningLikeElement) => boolean

/** The components whose children, and those whose title prop, render as a label. */
export interface Reach {
  children: Set<string>
  titles: Set<string>
}

const SEED_REACH: Reach = { children: new Set([...HEADINGS, ...BUTTONS, ...TITLE_CHILDREN]), titles: new Set(TITLED) }

const readsChildren = (reach: Reach): ReadsLabel => (node) => tagsOf(node).some((tag) => reach.children.has(tag)) || reachesButtonVariants(node)

/** The component a node is written in: a named function, or a function bound to a capitalised name
    (directly or through forwardRef or memo). */
function componentName(node: ts.Node): string | null {
  for (let n: ts.Node | undefined = node.parent; n; n = n.parent) {
    if (ts.isFunctionDeclaration(n)) return n.name && /^[A-Z]/.test(n.name.text) ? n.name.text : null
    if (ts.isArrowFunction(n) || ts.isFunctionExpression(n)) {
      let up: ts.Node = n.parent
      if (ts.isCallExpression(up)) up = up.parent
      return ts.isVariableDeclaration(up) && ts.isIdentifier(up.name) && /^[A-Z]/.test(up.name.text) ? up.name.text : null
    }
  }
  return null
}

/** The prop an expression renders: `children` or `title`, bare or as `props.<name>`. */
function renderedProp(expr: ts.Expression): 'children' | 'title' | null {
  const name = ts.isIdentifier(expr) ? expr.text : ts.isPropertyAccessExpression(expr) && ts.isIdentifier(expr.expression) && expr.expression.text === 'props' ? expr.name.text : null
  return name === 'children' || name === 'title' ? name : null
}

/** Whether `{expr}` lands in a label: inside an element whose children are read, or as the title of a
    component whose title is read. */
function landsInLabel(expr: ts.JsxExpression, reach: Reach): boolean {
  if (ts.isJsxAttribute(expr.parent)) {
    const owner = expr.parent.parent.parent
    return expr.parent.name.getText() === 'title' && tagsOf(owner).some((tag) => reach.titles.has(tag))
  }
  const read = readsChildren(reach)
  for (let n: ts.Node | undefined = expr.parent; n && !ts.isFunctionLike(n); n = n.parent) {
    if (ts.isJsxElement(n) && read(n.openingElement)) return true
  }
  return false
}

/**
 * The tree's reach: SEED_REACH, widened to a fixed point by every component that renders its children
 * or its title prop into a label (SecondaryHeader's title in its h1, ModalHeader's children in its h2,
 * MarketingCta's children in its buttonVariants() link), so a call site of such a component is read as
 * the label it renders. Components are matched by name across the tree.
 */
export function discoverReach(files: ts.SourceFile[]): Reach {
  const reach: Reach = { children: new Set(SEED_REACH.children), titles: new Set(SEED_REACH.titles) }
  for (let changed = true; changed; ) {
    changed = false
    for (const sf of files) {
      const visit = (node: ts.Node) => {
        if (ts.isJsxExpression(node) && node.expression) {
          const prop = renderedProp(node.expression)
          const owner = prop && componentName(node)
          const set = prop === 'children' ? reach.children : reach.titles
          if (owner && !set.has(owner) && landsInLabel(node, reach)) {
            set.add(owner)
            changed = true
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }
  }
  return reach
}

/** Every violation in one source; the reach is discovered from the source alone unless given. */
export function voiceFindings(source: string, rel: string, reach?: Reach): Finding[] {
  const sf = parse(source, rel)
  return findingsIn(sf, reach ?? discoverReach([sf]))
}

function findingsIn(sf: ts.SourceFile, reach: Reach): Finding[] {
  const rel = sf.fileName
  const read = readsChildren(reach)
  const findings: Finding[] = []
  const add = (node: ts.Node, clause: Clause, text: string) =>
    findings.push({ rel, line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1, clause, text: text.replace(/\s+/g, ' ').trim().slice(0, 80) })
  const devScope = rel.startsWith('lib/') || rel.startsWith('hooks/')
  // An icon by where it comes from, not its local spelling: every name bound to an import from the icon modules,
  // and every namespace imported from one (so `import { BellIcon as Bell }` and `<Icons.Bell />` are read).
  // Each name read by the declaration its scope gives it (heldValues.ts's scopeResolver), so a parameter or a local that
  // shadows an icon's import is not the icon.
  const iconDeclarations = new Set<ts.Node>()
  const namespaceDeclarations = new Set<ts.Node>()
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier) || !isIconModule(stmt.moduleSpecifier.text, rel)) continue
    const bindings = stmt.importClause?.namedBindings
    if (bindings && ts.isNamedImports(bindings)) for (const el of bindings.elements) iconDeclarations.add(el)
    if (bindings && ts.isNamespaceImport(bindings)) namespaceDeclarations.add(bindings)
  }
  const declaredIn = (set: Set<ts.Node>) => (id: ts.Identifier) => {
    const declaration = declarationOf(id)
    return !!declaration && set.has(declaration)
  }
  const isIconName = declaredIn(iconDeclarations)
  const isIconNamespace = declaredIn(namespaceDeclarations)
  // A member destructured from an icon namespace (`const { Bell: Mark } = Ph`) is an icon by its import too.
  const destructured = (n: ts.Node): void => {
    if (ts.isVariableDeclaration(n) && ts.isObjectBindingPattern(n.name) && n.initializer) {
      const from = unwrapHeld(n.initializer)
      if (ts.isIdentifier(from) && isIconNamespace(from)) {
        for (const el of n.name.elements) if (ts.isIdentifier(el.name)) iconDeclarations.add(el)
      }
    }
    ts.forEachChild(n, destructured)
  }
  destructured(sf)
  // An icon by itself: a name bound to an icon import, a namespace's member, or a name ending in Icon (a hand-drawn
  // component named for its icon).
  const iconLeaf = (x: ts.Expression): Array<'icon'> | undefined =>
    (ts.isIdentifier(x) && (isIconName(x) || /Icon$/.test(x.text)))
    || (ts.isPropertyAccessExpression(x) && ts.isIdentifier(x.expression) && (isIconNamespace(x.expression) || /Icon$/.test(x.name.text)))
      ? ['icon']
      : undefined
  // What each same-file binding holds, by the reading the glyph gate shares (tests/unit/heldValues.ts): an alias, a
  // conditional, an element (`const mark = <BellIcon />`), an object's property, a spread or a nested member of one,
  // a member destructured from one, each read by name to a fixed point.
  const values = heldValues(sf, iconLeaf)
  const holdsIcon = (e: ts.Expression) => leavesOf(values.valueOf(e)).size > 0
  const isIconTag = (n: ts.JsxOpeningLikeElement): boolean => {
    const name = n.tagName
    if (ts.isIdentifier(name) || ts.isPropertyAccessExpression(name)) return holdsIcon(name)
    return tagsOf(n).some((tag) => /Icon$/.test(tag))
  }

  const visit = (node: ts.Node, inMetadata: boolean): void => {
    // Copy: every literal outside code's own strings.
    const text = literalText(node)
    if (text !== null && !isCodeString(node, text)) {
      if (EXCLAMATION.test(text)) add(node, 'exclamation', text)
      for (const _ of text.matchAll(EMOJI_ALL)) add(node, 'emoji', text)
      for (const [word, re] of BUZZWORDS) if (re.test(text)) add(node, 'buzzword', `${word}: ${text}`)
      if (devScope && /\s/.test(text.trim()) && DEVELOPER_WORDING.test(text)) add(node, 'developerWording', text)
    }
    // Headings, titles, buttons: their rendered text; headings: no icon inside.
    if (ts.isJsxElement(node)) {
      const tag = tagsOf(node.openingElement).find((name) => HEADINGS.has(name))
      if (read(node.openingElement)) {
        const rendered = titleCased(elementTexts(node, read))
        if (rendered !== undefined) add(node, 'sentenceCase', rendered)
      }
      if (tag) {
        const icons: ts.Node[] = []
        // An icon inside a control the heading wraps (a disclosure button's caret) is the control's
        // affordance, not the heading's icon.
        const find = (n: ts.Node) => {
          if (ts.isJsxElement(n) && tagsOf(n.openingElement).some((name) => CONTROLS.has(name))) return
          if ((ts.isJsxSelfClosingElement(n) || ts.isJsxOpeningElement(n)) && isIconTag(n)) icons.push(n)
          // An icon a binding or a member holds, placed in the heading (`{mark}`, `{MARK.alert}`); an inline element
          // is read by its tag above.
          const placed = ts.isJsxExpression(n) && n.expression ? unwrapHeld(n.expression) : undefined
          const named = !!placed && (ts.isIdentifier(placed) || ts.isPropertyAccessExpression(placed) || ts.isElementAccessExpression(placed))
          if (named && holdsIcon(placed)) icons.push(n)
          const before = icons.length
          ts.forEachChild(n, find)
          // Any other placed expression holds what it may render (`{ok && mark}`, `{createElement(BellIcon)}`, a
          // helper's return, `Children.map`'s), unless the walk found the icon's own tag inside it.
          if (placed && !named && !ts.isJsxElement(placed) && !ts.isJsxSelfClosingElement(placed) && !ts.isJsxFragment(placed) && icons.length === before && holdsIcon(placed)) icons.push(n)
        }
        node.children.forEach(find)
        for (const icon of icons) {
          add(icon, 'headingIcon', `${ts.isJsxExpression(icon) ? icon.getText() : `<${(icon as ts.JsxOpeningLikeElement).tagName.getText()}>`} in <${tag}>`)
        }
      }
    }
    // A component's title (GuidanceCard, Notice, Modal, SecondaryHeader and the discovered ones), and
    // any element's aria-label.
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      for (const name of tagsOf(node).some((tag) => reach.titles.has(tag)) ? ['title', 'aria-label'] : ['aria-label']) {
        const expr = attributeValue(attribute(node, name))
        const value = expr ? titleCased(renderedVariants(expr, read)) : undefined
        if (value !== undefined) add(expr!, 'sentenceCase', value)
      }
    }
    // A page's metadata title (`export const metadata`, generateMetadata), its default and template included.
    if (inMetadata && ts.isPropertyAssignment(node) && /^(?:title|default|template)$/.test(node.name.getText())) {
      const value = titleCased(renderedVariants(node.initializer, read))
      if (value !== undefined) add(node.initializer, 'sentenceCase', value)
    }
    const metadataScope =
      inMetadata ||
      (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === 'metadata') ||
      (ts.isFunctionDeclaration(node) && node.name?.text === 'generateMetadata')
    ts.forEachChild(node, (child) => visit(child, metadataScope))
  }
  visit(sf, false)
  return findings
}

const FILES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))
const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')
const SOURCES = FILES.map((file) => parse(readFileSync(file, 'utf8'), rel(file)))
const TREE_REACH = discoverReach(SOURCES)

/**
 * The violations found on 2026-10-12, per file and clause. Each line names the sweep PR that owns the
 * file, or why the text stays.
 */
const VOICE_RESIDUE: Record<string, Partial<Record<Clause, number>>> = {
  'app/dashboard/error.tsx': { sentenceCase: 4 }, // brand-dashboard-watchlist (#1290, DSW-12)
  'app/dashboard/settings/page.tsx': { sentenceCase: 1 }, // brand-settings-subscriptions (#1291)
  'app/error.tsx': { sentenceCase: 1 }, // brand-chrome-primitives (#1289; the development-only details panel)
  'app/filing/[id]/page.tsx': { sentenceCase: 2 }, // brand-metadata-social (#1312; meta titles)
  'app/privacy/page.tsx': { sentenceCase: 16 }, // founder-gated, legal page: its headings wait on the founder (legalDates bump)
  'app/search/page.tsx': { sentenceCase: 1 }, // brand-calendar-search (#1301; meta title)
  'app/security/page.tsx': { sentenceCase: 12 }, // founder-gated, legal page: the /security recase lands with its claims (UA ids)
  'app/terms/page.tsx': { sentenceCase: 4 }, // founder-gated, legal page: its headings wait on the founder (legalDates bump)
  'components/CookieConsent.tsx': { sentenceCase: 7 }, // brand-chrome-primitives (#1289; the ModalHeader's "Cookie Preferences" is the seventh)
  'features/admin/components/ShareInvite.tsx': { sentenceCase: 1 }, // a known false positive, no PR: the aria-label "Share invite via Messages" names Apple's app; the entry leaves when the label changes
  'features/feedback/components/FeedbackWidget.tsx': { emoji: 3 }, // brand-chrome-primitives (#1289)
  'features/filings/components/copilot/FilingWorkspace.tsx': { sentenceCase: 1 }, // the Copilot rail's next change (no open PR edits the flagged line; #1278 edits another line of this file; the aria-label "Filing source and Ask")
  'features/filings/components/copilot/PaneResizer.tsx': { sentenceCase: 1 }, // brand-copilot (#1295; the aria-label "Resize Copilot panel")
  'features/marketing/components/ProDepth.tsx': { sentenceCase: 1 }, // the FeatureRow title "Change Report": a product screen's name beside Ask this Filing and Multi-Period Analysis, which PROPER_NOUNS lists and this does not, while the product also writes "change report" in prose (ComparePeriodsCard); the name's case is the records PR's call (07-voice.md); #1311 left it
  'features/settings/components/NotificationPreferencesForm.tsx': { sentenceCase: 1, headingIcon: 1 }, // brand-settings-subscriptions (#1291, DSW-13)
  'features/subscriptions/components/PeekLocked.tsx': { buzzword: 1 }, // brand-settings-subscriptions (#1291; DSW-11, "unlock")
  'features/summaries/components/SummaryActionsBar.tsx': { sentenceCase: 1 }, // brand-filing-page (#1293)
  'lib/api/client.ts': { developerWording: 1 }, // brand-chrome-primitives (#1289; CAL-12, "backend API")
}
const VOICE_RESIDUE_MAX = { entries: 19, violations: 60 }

describe('brand voice rules (docs/brand/07-voice.md)', () => {
  // An element past MAX_VARIANTS throws; the residue test reports it rather than the whole file failing to load.
  let findings: Finding[] = []
  let scanError: unknown
  try {
    findings = SOURCES.flatMap((sf) => findingsIn(sf, TREE_REACH))
  } catch (error) {
    scanError = error
  }

  it('reads the app (a scan that finds no copy must not pass)', () => {
    expect(FILES.length).toBeGreaterThan(300)
    expect(FILES.map(rel)).toEqual(expect.arrayContaining(['app/page.tsx', 'lib/api/client.ts', 'hooks/useCountUp.ts']))
  })

  it('every violation is in the residue, and every residue count is current', () => {
    if (scanError) throw scanError
    const counts = new Map<string, Finding[]>()
    for (const f of findings) {
      const key = `${f.rel} ${f.clause}`
      counts.set(key, [...(counts.get(key) ?? []), f])
    }
    const problems: string[] = []
    for (const [key, list] of counts) {
      const [file, clause] = key.split(' ') as [string, Clause]
      const allowed = VOICE_RESIDUE[file]?.[clause] ?? 0
      const lines = list.map((f) => `${f.rel}:${f.line} [${f.clause}] ${JSON.stringify(f.text)}`)
      if (list.length > allowed) problems.push(`${key}: ${list.length} found, ${allowed} in VOICE_RESIDUE\n  ${lines.join('\n  ')}`)
      else if (list.length < allowed) problems.push(`${key}: ${list.length} found, ${allowed} in VOICE_RESIDUE: lower the count`)
    }
    for (const [file, clauses] of Object.entries(VOICE_RESIDUE)) {
      for (const clause of Object.keys(clauses) as Clause[]) {
        if (!counts.has(`${file} ${clause}`)) problems.push(`${file} ${clause}: none left, delete it from VOICE_RESIDUE`)
      }
    }
    expect(problems, 'fix the copy (docs/brand/07-voice.md); the residue only shrinks').toEqual([])
  })

  it('the residue only shrinks', () => {
    const entries = Object.values(VOICE_RESIDUE).flatMap((clauses) => Object.values(clauses))
    // Equality, not a ceiling: a PR that shrinks the list lowers the cap in the same commit, so no slack is
    // left for a later PR to add an entry by editing the table alone.
    expect(entries.length, 'VOICE_RESIDUE changed its entries: move VOICE_RESIDUE_MAX.entries with it in the same commit').toBe(VOICE_RESIDUE_MAX.entries)
    expect(entries.reduce((sum, n) => sum + (n ?? 0), 0), 'VOICE_RESIDUE changed its violations: move VOICE_RESIDUE_MAX.violations with it in the same commit').toBe(VOICE_RESIDUE_MAX.violations)
  })

  it('the scan catches what it is for (a self-check on a fixed source)', () => {
    const src = [
      "import { BellIcon } from '@/lib/icons'",
      "export const metadata = { title: 'Filing Alerts | EarningsNerd' }",
      'export function Probe() {',
      '  return (',
      '    <div className="flex items-center">',
      '      <h2><BellIcon />Filing Alerts</h2>',
      '      <Button>Go to Login</Button>',
      '      <GuidanceCard title="Authentication Required" />',
      "      <p>{'Great news!'}</p>",
      '      <span>Upgrade to unlock ✨</span>',
      '      <h3>Results That Matter</h3>',
      '      <h3>Ask this Filing about Apple’s 10-K for Q3 · SEC EDGAR</h3>',
      '      <Button>Wow!</Button>',
      "      <a className=\"md:!block focus-visible:outline-none\" href=\"/pricing\">See Pro plans</a>",
      '      <Button>Edit Profile</Button>',
      '      <Button>Export Excel</Button>',
      "      <Button>{busy ? 'Sending Message' : 'Send message'}</Button>",
      "      <h2>{loading ? 'Loading' : ('Your Watchlist')}</h2>",
      "      <Notice title={error ? 'Something Went Wrong' : 'Saved'} />",
      "      <h3>{count > 0 && 'Recent Filings'}</h3>",
      "      <Modal title={name ?? 'Delete Account'} />",
      "      <Button>{busy ? 'Sending message' : 'Send message'} {count || 'none'}</Button>",
      "      <Button>{busy ? 'Send' : 'Send Again Later'}<Icon className={a ? 'x' : 'y'} /><Icon className={b ? 'x' : 'y'} /></Button>",
      "      <h2>{busy ? <span>Loading Filings</span> : 'Filings'}</h2>",
      "      <button>{busy ? <>Sending Now</> : 'Send'}</button>",
      '      <ModalHeader id="t">Cookie Preferences</ModalHeader>',
      '      <CardTitle>Recent Filings</CardTitle>',
      '      <CardHeader><CardTitle>Recent filings</CardTitle><Button>View All</Button></CardHeader>',
      '      <SecondaryHeader title="Your Watchlist Insights" />',
      "      <Link href=\"/\" className={buttonVariants({ variant: 'secondary' })}>Go Back Home</Link>",
      "      <a href=\"/pricing\" className={cx(buttonVariants(), 'w-full')}>See Pro Plans Now</a>",
      '      <h4>Quarterly Results</h4>',
      '      <h6>Risk factors in Item 1A, Form 4 and the S&P 500 · Nasdaq 100 · Financial Highlights · Executive Assessment</h6>',
      '      <button aria-label="Close Dialog"><XIcon /></button>',
      '      <input placeholder="Search tickers! 🚀" />',
      '      <Panel title="Quarterly Revenue Trend" />',
      '      <Cta>Start Free Trial</Cta>',
      '      <h2><Bell />Price alerts</h2>',
      '      <h2><Ph.Bell />Price alerts</h2>',
      '      <h2><Ring />Doorbells</h2>',
      '      <Notice title="decision-ready insights" />',
      "      <p>{'a game-changing view'}</p>",
      '      <Button>save changes</Button>',
      '      <h3>START FREE TRIAL</h3>',
      '      <h2>{count} companies · SEC EDGAR · Export CSV</h2>',
      "      <button>{'Send Message' + ' Again Later'}</button>",
      '      <h2><AlertMark />Price alerts</h2>',
      '      <h2><PhMark />Price alerts</h2>',
      '      <h2><Chained />Price alerts</h2>',
      '      <h2>{mark}Price alerts</h2>',
      '      <h2><Doorbell />Doorbells</h2>',
      '      <h2><Picked />Price alerts</h2>',
      '      <h2><MARK.alert />Price alerts</h2>',
      '      <h2><MARK.ring />Doorbells</h2>',
      '      <h2><Keyed />Price alerts</h2>',
      "      <p>{'Great!!'}</p>",
      '      <p>Really!?</p>',
      '      <span>Hello!Welcome</span>',
      '      <h2><marks.alert />Alerts</h2>',
      '      <h2><NESTED.group.alert />Alerts</h2>',
      '      <Button>Show More…</Button>',
      '      <h2>{frag}Alerts</h2>',
      '      <h2>{wrapped}Alerts</h2>',
      '      <Button>START FREE TRIAL…</Button>',
      '      <h3>SIGN-UP NOW:</h3>',
      '      <Button>Export CSV…</Button>',
      '      <Button>SEC FILING ALERTS</Button>',
      '      <h3>{count} NEW FILINGS</h3>',
      '      <Title>Recent Filings</Title>',
      '      <UI.Button>View All Filings</UI.Button>',
      '      <Button>SEC EDGAR</Button>',
      '      <LocalTitle>Recent Filings</LocalTitle>',
      '      <Heading>Quarterly Results</Heading>',
      '      <Heading><BellIcon />Alerts</Heading>',
      '    </div>',
      '  )',
      '}',
      'function Panel({ title }: { title: string }) {',
      '  return <h5>{title}</h5>',
      '}',
      'const Cta = ({ children }: { children: ReactNode }) => <Link href="/" className={buttonVariants()}>{children}</Link>',
      // An icon by its import: an alias, and a namespace's member, each from an icon module; Ring comes from
      // a module that is not one, so its bell is not an icon to the scan.
      "import { BellIcon as Bell } from '@/lib/icons'",
      "import * as Ph from '@phosphor-icons/react/dist/ssr'",
      "import { Bell as Ring } from './bells'",
      // A label component held by a same-file alias, and a heading level chosen by a conditional.
      'const LocalTitle = CardTitle',
      "const Heading = big ? 'h2' : 'h3'",
      // A label component imported under another name, and one read through a namespace.
      "import { CardTitle as Title } from '@/components/ui'",
      "import * as UI from '@/components/ui'",
      // Bindings that hold an icon (an alias, a namespace member under a cast, a conditional chain, an element, a
      // member destructured from an icon namespace), and one holding Ring, which is not an icon.
      'const AlertMark = BellIcon',
      'const PhMark = (Ph.Bell) as typeof Ph.Bell',
      'const Chained = flag ? AlertMark : null',
      "const mark = <BellIcon className='h-4' />",
      'const Doorbell = Ring',
      'const { Bell: Picked } = Ph',
      // An object whose property holds an icon, read by name and through a binding by a key the scan cannot read.
      'const MARK = { alert: BellIcon, ring: Ring } as const',
      'const Keyed = MARK[kind]',
      // A RegExp's source is code: its lookbehind and its class of sentence stops are not exclamations.
      "const END = new RegExp('(?<!\\b[A-Za-z])[.!?](?=\\s)', 'u')",
      "const STOP = RegExp('(?<!Mr)[.!?]$')",
      // An icon object copied by a spread, and one nested in another object.
      'const base = { alert: BellIcon }',
      'const marks = { ...base }',
      'const NESTED = { group: { alert: BellIcon } }',
      // An icon held inside a fragment and inside a wrapper element.
      'const frag = <><BellIcon /></>',
      "const wrapped = <span className='inline-flex'><BellIcon /></span>",
    ].join('\n')
    expect(voiceFindings(src, 'features/probe/Probe.tsx').map((f) => `${f.line} ${f.clause}`)).toEqual([
      '2 sentenceCase',
      '6 sentenceCase',
      '6 headingIcon',
      '7 sentenceCase',
      '8 sentenceCase',
      '9 exclamation',
      '10 emoji',
      '10 buzzword',
      '13 exclamation',
      '15 sentenceCase',
      '17 sentenceCase',
      '18 sentenceCase',
      '19 sentenceCase',
      '20 sentenceCase',
      '21 sentenceCase',
      '23 sentenceCase',
      '24 sentenceCase',
      '25 sentenceCase',
      // The wider reach: a ModalHeader child, a CardTitle, a CardHeader's button (its title is read once,
      // as the CardTitle), a SecondaryHeader title, two buttonVariants() links, an h4, an aria-label, a
      // placeholder's exclamation and emoji, and two components found to render a label (Panel's title
      // into an h5, Cta's children into a buttonVariants() link). Line 33 is all proper nouns.
      '26 sentenceCase',
      '27 sentenceCase',
      '28 sentenceCase',
      '29 sentenceCase',
      '30 sentenceCase',
      '31 sentenceCase',
      '32 sentenceCase',
      '34 sentenceCase',
      '35 exclamation',
      '35 emoji',
      '36 sentenceCase',
      '37 sentenceCase',
      // An icon imported under another name, and one reached through a namespace, inside a heading.
      '38 headingIcon',
      '39 headingIcon',
      // A buzzword in a copy attribute (its title, lowercase, is not sentence case either) and in a rendered
      // expression, each shaped like a class list; a lowercase first word and an all-caps label; line 45 passes
      // (a phrase after an expression, two proper nouns, an acronym beside a lowercase word); line 46 is a label
      // joined with `+`, read as the text a reader sees.
      '41 sentenceCase',
      '41 buzzword',
      '42 buzzword',
      '43 sentenceCase',
      '44 sentenceCase',
      '46 sentenceCase',
      // An icon held by a binding inside a heading: an alias, a namespace member, a conditional chain, an element
      // placed as `{mark}`, a destructured namespace member; line 51's Doorbell holds Ring, not an icon. An object's
      // property that holds an icon, by name (line 53) and through a binding by a key the scan cannot read (line
      // 55); line 54's property holds Ring.
      '47 headingIcon',
      '48 headingIcon',
      '49 headingIcon',
      '50 headingIcon',
      '52 headingIcon',
      '53 headingIcon',
      '55 headingIcon',
      // Every exclamation mark in copy: doubled, beside a question mark, and between two words.
      '56 exclamation',
      '57 exclamation',
      '58 exclamation',
      // An icon object's property through a spread of it (line 59) and through a nested object (line 60).
      '59 headingIcon',
      '60 headingIcon',
      // A Title Case word with its own punctuation (`More…`), and an icon placed inside a fragment and a wrapper.
      '61 sentenceCase',
      '62 headingIcon',
      '63 headingIcon',
      '64 sentenceCase',
      '65 sentenceCase',
      '67 sentenceCase',
      '68 sentenceCase',
      '69 sentenceCase',
      '70 sentenceCase',
      '72 sentenceCase',
      '73 sentenceCase',
      '74 headingIcon',
    ])
    // An attribute is never label text: the icons' className leaves are not read into the label.
    expect(voiceFindings(src, 'features/probe/Probe.tsx').filter((f) => f.line >= 23 && f.clause === 'sentenceCase').map((f) => f.text)).toEqual([
      'Send Again Later',
      'Loading Filings',
      'Sending Now',
      'Cookie Preferences',
      'Recent Filings',
      'View All',
      'Your Watchlist Insights',
      'Go Back Home',
      'See Pro Plans Now',
      'Quarterly Results',
      'Close Dialog',
      'Quarterly Revenue Trend',
      'Start Free Trial',
      'decision-ready insights',
      'save changes',
      'START FREE TRIAL',
      'Send Message Again Later',
      'Show More…',
      'START FREE TRIAL…',
      'SIGN-UP NOW:',
      'SEC FILING ALERTS',
      '{x} NEW FILINGS',
      'Recent Filings',
      'View All Filings',
      'Recent Filings',
      'Quarterly Results',
    ])
    // A name two functions declare reads its own function's binding: Q's Mark holds no icon, so its heading passes.
    // A parameter that shadows an icon's import is not the icon (R), while the import itself is (S); a member
    // destructured from an array holds what the array holds (T).
    const shadowed = [
      "import { BellIcon } from '@/lib/icons'",
      'export function P() { const Mark = BellIcon; return <h2><Mark />Price alerts</h2> }',
      'export function Q() { const Mark = Chip; return <h2><Mark />Price alerts</h2> }',
      "import { BellIcon as Ring } from '@/lib/icons'",
      'export function R(Ring: () => null) { return <h2><Ring />Price alerts</h2> }',
      'export function S() { return <h2><Ring />Price alerts</h2> }',
      'export function T() { const [Bell] = [BellIcon]; return <h2><Bell />Price alerts</h2> }',
      'export function U() { const [Mark = BellIcon] = []; return <h2><Mark />Price alerts</h2> }',
      'export function V({ icon: Mark = BellIcon }: { icon?: () => null }) { return <h2><Mark />Price alerts</h2> }',
    ].join('\n')
    // A destructuring default (U) and a component's default prop (V) hold the icon too.
    expect(voiceFindings(shadowed, 'features/probe/Shadowed.tsx').map((f) => `${f.line} ${f.clause}`)).toEqual([
      '2 headingIcon',
      '6 headingIcon',
      '7 headingIcon',
      '8 headingIcon',
      '9 headingIcon',
    ])
    // Every emoji in a literal is a finding (the review's case: a second one in a listed literal counts).
    expect(voiceFindings("export const P = () => <p>New ✨✨ ideas</p>", 'features/probe/Emoji.tsx').map((f) => `${f.line} ${f.clause}`)).toEqual([
      '1 emoji',
      '1 emoji',
    ])
    // createElement reads as JSX does: a child is copy (the review's case), a prop is read by the attribute's rule
    // (a data attribute is code, a title is copy), and the type is code (a custom tag that reads as a buzzword).
    const created = [
      "export const A = () => React.createElement('button', null, 'Wow! 🚀 unlock')",
      "export const B = () => createElement('a', { href: '/pricing', 'data-cta': 'unlock-pro', title: 'Huge savings!' }, busy ? 'Seamless' : 'See plans')",
      "export const C = () => document.createElement('seamless-frame')",
    ].join('\n')
    expect(voiceFindings(created, 'features/probe/Created.tsx').map((f) => `${f.line} ${f.clause}`)).toEqual([
      '1 exclamation',
      '1 emoji',
      '1 buzzword',
      '2 exclamation',
      '2 buzzword',
    ])
    // A replacement is copy where it renders (the review's case), and so is the value setAttribute gives an attribute
    // that is not code; the pattern, an empty replacement and a code attribute's value stay code (a data attribute's
    // label, shaped like copy).
    const replaced = [
      "export const A = ({ note }) => <p>{note.replace('x', 'Wow! unlock 🚀')}</p>",
      "export const B = ({ note }) => <p>{note.replaceAll('Wow!', '')}</p>",
      "export const C = (el) => el.setAttribute('aria-label', 'Close now!')",
      "export const D = (el) => el.setAttribute('data-cta', 'Unlock Pro')",
    ].join('\n')
    expect(voiceFindings(replaced, 'features/probe/Replaced.tsx').map((f) => `${f.line} ${f.clause}`)).toEqual([
      '1 exclamation',
      '1 emoji',
      '1 buzzword',
      '3 exclamation',
    ])
    // Every way a name is given an icon (tests/unit/heldValues.ts; lessons/test-gates-must-be-as-wide-as-their-rule.md),
    // one heading each: an assignment after the declaration (the review's case), a logical assignment, a destructuring
    // assignment, a loop's variable, a parameter at a direct call, a component's prop, a callback handed to an array's
    // method and to a same-file function, a function's return, a property put in after the object is made; and placed in
    // a heading, React's createElement, Children.map over the children a component is given, and a conditional. A name
    // given only something else (line 28) passes.
    const family = [
      "import { BellIcon } from '@/lib/icons'",
      'let Mark; Mark = BellIcon',
      'export const A = () => <h2><Mark />Alerts</h2>',
      'let Later = null; Later ??= BellIcon',
      'export const B = () => <h2><Later />Alerts</h2>',
      'let Picked; ({ icon: Picked } = { icon: BellIcon })',
      'export const C = () => <h2><Picked />Alerts</h2>',
      'export function D() { for (const Each of [BellIcon]) return <h2><Each />Alerts</h2> }',
      'function heading(Passed) { return <h2><Passed />Alerts</h2> }',
      'export const E = () => heading(BellIcon)',
      'function Section({ icon: Prop }) { return <h2><Prop />Alerts</h2> }',
      'export const F = () => <Section icon={BellIcon} />',
      'export const G = () => [BellIcon].map((Item) => <h2 key="g"><Item />Alerts</h2>)',
      'function withMark(cb) { return cb(BellIcon) }',
      'export const H = () => withMark((Handed) => <h2><Handed />Alerts</h2>)',
      'const pick = () => BellIcon',
      'const Returned = pick()',
      'export const I = () => <h2><Returned />Alerts</h2>',
      'const SLOT = {}',
      'SLOT.icon = BellIcon',
      'export const J = () => <h2><SLOT.icon />Alerts</h2>',
      'export const K = () => <h2>{createElement(BellIcon)}Alerts</h2>',
      'function Titled({ children }) { return <h2>{Children.map(children, (child) => child)}Alerts</h2> }',
      'export const L = () => <Titled><BellIcon /></Titled>',
      'const mark = <BellIcon />',
      'export const M = ({ ok }) => <h2>{ok && mark}Alerts</h2>',
      'let Plain; Plain = Chip',
      'export const N = () => <h2><Plain />Alerts</h2>',
    ].join('\n')
    expect(voiceFindings(family, 'features/probe/Family.tsx').map((f) => `${f.line} ${f.clause}`)).toEqual([
      '3 headingIcon',
      '5 headingIcon',
      '7 headingIcon',
      '8 headingIcon',
      '9 headingIcon',
      '11 headingIcon',
      '13 headingIcon',
      '15 headingIcon',
      '18 headingIcon',
      '21 headingIcon',
      '22 headingIcon',
      '23 headingIcon',
      '26 headingIcon',
    ])
    // Out of reach, planted as the gaps the header names (each passes): an icon held in React state, a class's field
    // read through `this`, a promise's then, a generator's yield, and an imported component that renders its prop in a
    // heading.
    const gaps = [
      "import { BellIcon } from '@/lib/icons'",
      "import { Section } from './Section'",
      'export function A() { const [State] = useState(() => BellIcon); return <h2><State />Alerts</h2> }',
      'export class B { icon = BellIcon; render() { return <h2><this.icon />Alerts</h2> } }',
      'export const C = () => load().then((Later) => <h2><Later />Alerts</h2>)',
      'function* marks() { yield BellIcon }',
      'export function D() { for (const Yielded of marks()) return <h2><Yielded />Alerts</h2> }',
      'export const E = () => <Section icon={BellIcon} />',
    ].join('\n')
    expect(voiceFindings(gaps, 'features/probe/Gaps.tsx')).toEqual([])
    // Past MAX_VARIANTS the scan throws, naming the element and its count, instead of dropping branches.
    const sixConditionals = "export const P = () => <Button>{a ? 'x' : 'y'}{b ? 'x' : 'y'}{c ? 'x' : 'y'}{d ? 'x' : 'y'}{e ? 'x' : 'y'}{f ? 'x' : 'Send Again Later'}</Button>"
    expect(() => voiceFindings(sixConditionals, 'features/probe/Six.tsx')).toThrow(
      'features/probe/Six.tsx:1 <Button> renders 64 combinations of its conditionals, more than MAX_VARIANTS (32) reads',
    )
    // A metadata title read through generateMetadata's conditional.
    expect(
      voiceFindings("export async function generateMetadata() { return { title: ok ? 'Filing Summary' : 'Filing' } }", 'app/probe/page.tsx').map((f) => `${f.clause} ${f.text}`),
    ).toEqual(['sentenceCase Filing Summary'])
    expect(voiceFindings("export const msg = 'The backend returned 503. Try again.'", 'lib/api/probe.ts').map((f) => f.clause)).toEqual(['developerWording'])
    expect(voiceFindings("export const msg = 'The backend returned 503. Try again.'", 'features/probe/msg.ts')).toEqual([])
  })
})
