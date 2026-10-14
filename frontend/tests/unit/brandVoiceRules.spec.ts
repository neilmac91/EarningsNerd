import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * The voice rules of docs/brand/07-voice.md as one gate (CLAUDE.md rule 12; docs/brand/decisions-log.md
 * D-031). Until this spec they were prose, and the 2026-10 audit found each of them broken somewhere.
 * It reads the TypeScript AST of every shipped module under app, components, features, hooks and lib:
 *
 *  - sentenceCase: a label is in sentence case: after the first word of a phrase, a capitalised word
 *    must be a proper noun (PROPER_NOUNS). The labels read: the text of a heading (h1 to h6), of a
 *    dialog or card title (ModalHeader, CardTitle, CardHeader), of a button (<Button>, <button>, and any
 *    element whose className reaches buttonVariants(), such as a <Link> or <a> styled as a button) and
 *    of every component found to render its children into one of those (see discoverReach); the title
 *    prop of a GuidanceCard, Notice, Modal, ModalHeader, SecondaryHeader or UpgradeModal and of every
 *    component found to render its title prop into a label; every aria-label; a page's metadata title.
 *    The check is a heuristic, so a false positive goes to the residue with its reason, never to a
 *    weaker regex. Its limits: a label passed through a variable of another name (`const heading =
 *    title`), a component's title read from a spread, a label built in a function and returned, and a
 *    className styled through a variable (`const btn = buttonVariants()`) are not followed; those stay
 *    review-checked (lessons/test-gates-must-be-as-wide-as-their-rule.md).
 *  - exclamation: no exclamation mark in copy.
 *  - emoji: no emoji in copy: a character that presents as an emoji by default, or any pictograph
 *    forced to one with U+FE0F. Typographic glyphs (the ▲ ▼ direction marks, ↗ for an external link,
 *    © ® ™) are text, not emoji.
 *  - buzzword: none of the banned words (BUZZWORDS).
 *  - headingIcon: no icon element inside a heading (a section heading carries no icon; DESIGN.md).
 *  - developerWording: copy in lib/ and hooks/ (the fallback errors a user reads) never names the
 *    backend, an API path, a "reader" or an HTTP status number.
 *
 * Copy is a JSX text node, or a string or template literal outside the places code keeps its own
 * strings (imports, class lists, comparisons, identifiers such as hrefs and keys; see isCodeString). An
 * attribute that is not code (CODE_ATTRS) is copy, so a placeholder, an aria-label, an alt or a title is
 * read by the exclamation, emoji and buzzword clauses (and by no-em-dash-copy.spec.ts, which reads every
 * literal).
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
const EXCLAMATION = /[\p{L}\p{N})'"’”.]!(?=\s|$|['"’”)])/u
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
/** Calls whose string arguments are class lists or keys. */
const CODE_CALLS = new Set(['cx', 'clsx', 'cn', 'buttonVariants', 'inputClasses', 'require', 'querySelector', 'querySelectorAll', 'getItem', 'setItem', 'removeItem', 'addEventListener', 'removeEventListener', 'getElementById', 'matchMedia', 'startsWith', 'endsWith', 'includes', 'replace', 'split', 'test', 'match', 'capture', 'track', 'identify', 'register', 'useQuery', 'setAttribute', 'getAttribute', 'createElement'])

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

/** Whether a string literal is code's own string, not copy: an import, a key, a class list, a comparison, a code attribute or argument. */
function isCodeString(node: ts.Node, text: string): boolean {
  if (ts.isJsxText(node)) return false
  if (looksLikeClasses(text) || !/\p{L}/u.test(text)) return true
  // Markup a module builds (an SVG for an export) is code.
  if (/<\/?[a-z][\w-]*[\s>/]/.test(text)) return true
  const parent = node.parent
  if (!parent) return true
  if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent) || ts.isExternalModuleReference(parent) || ts.isLiteralTypeNode(parent)) return true
  if ((ts.isPropertyAssignment(parent) || ts.isPropertyDeclaration(parent) || ts.isMethodDeclaration(parent)) && parent.name === node) return true
  if (ts.isElementAccessExpression(parent) || ts.isCaseClause(parent)) return true
  if (ts.isBinaryExpression(parent) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken, ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.InKeyword].includes(parent.operatorToken.kind)) return true
  for (let n: ts.Node | undefined = parent; n; n = n.parent) {
    if (ts.isJsxAttribute(n)) return CODE_ATTRS.test(n.name.getText())
    if (ts.isPropertyAssignment(n) && /^(?:className|classNames|href|key|queryKey|id|type|variant)$/.test(n.name.getText())) return true
    if (ts.isCallExpression(n) && CODE_CALLS.has(callName(n))) return true
    if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isBlock(n) || ts.isSourceFile(n)) break
  }
  return false
}

/** Capitalised words after a phrase's first word that are not proper nouns. */
export function titleCaseWords(text: string): string[] {
  let t = ` ${text} `
  for (const noun of PROPER_NOUN_RES) t = t.replace(noun, ' {n} ')
  const out: string[] = []
  // A phrase starts again after a sentence stop, a separator, a bracket or quote, or an expression
  // (`{x}`: an icon or a value before a label).
  for (const segment of t.split(/[.?!|·:;–—]\s+|\s[-–—]\s|\n|\(|\)|["“”]|\{x\}/)) {
    const words = segment.trim().split(/\s+/).filter(Boolean)
    words.slice(1).forEach((raw) => {
      const word = raw.replace(/^['‘’]+|[,'‘’]+$/g, '')
      if (/^[A-Z][a-z]+(?:['’]s)?$/.test(word)) out.push(word)
    })
  }
  return out
}

/** The texts an expression can render where copy is read in context (a button label, a heading, a
    title): each literal leaf of a conditional, of a logical and/or/nullish expression and of a
    parenthesised one, so `{busy ? 'Sending Message' : 'Send Message'}` is read as both labels, and the
    texts of a JSX element or fragment in such a branch (`{busy ? <span>Sending now</span> : 'Send'}`).
    The condition of an `&&` renders nothing a reader sees; any other expression reads as `{x}`, and so
    does an element that is a label of its own (`read`), which is read where it stands. */
function renderedVariants(expr: ts.Expression, read: ReadsLabel): string[] {
  if (ts.isParenthesizedExpression(expr)) return renderedVariants(expr.expression, read)
  if (ts.isConditionalExpression(expr)) return [...renderedVariants(expr.whenTrue, read), ...renderedVariants(expr.whenFalse, read)]
  if (ts.isBinaryExpression(expr)) {
    const op = expr.operatorToken.kind
    if (op === ts.SyntaxKind.AmpersandAmpersandToken) return renderedVariants(expr.right, read)
    if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken)
      return [...renderedVariants(expr.left, read), ...renderedVariants(expr.right, read)]
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
    const tag = ts.isJsxElement(owner) ? tagOf(owner.openingElement) : ''
    throw new Error(`${where(owner)} <${tag}> renders ${count} combinations of its conditionals, more than MAX_VARIANTS (${MAX_VARIANTS}) reads: split the element or raise the bound`)
  }
  return texts
}

/** The texts an element can render (childTexts, whitespace collapsed, each once). */
const elementTexts = (element: ts.JsxElement, read: ReadsLabel) => [...new Set(childTexts(element, read).map((t) => t.replace(/\s+/g, ' ').trim()))]

/** The first of the texts a node can render that breaks sentence case. */
const titleCased = (texts: string[]) => texts.find((t) => titleCaseWords(t).length)

const tagOf = (node: ts.JsxOpeningLikeElement) => node.tagName.getText()

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

const readsChildren = (reach: Reach): ReadsLabel => (node) => reach.children.has(tagOf(node)) || reachesButtonVariants(node)

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
    return expr.parent.name.getText() === 'title' && reach.titles.has(tagOf(owner))
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

  const visit = (node: ts.Node, inMetadata: boolean): void => {
    // Copy: every literal outside code's own strings.
    const text = literalText(node)
    if (text !== null && !isCodeString(node, text)) {
      if (EXCLAMATION.test(text)) add(node, 'exclamation', text)
      if (EMOJI.test(text)) add(node, 'emoji', text)
      for (const [word, re] of BUZZWORDS) if (re.test(text)) add(node, 'buzzword', `${word}: ${text}`)
      if (devScope && /\s/.test(text.trim()) && DEVELOPER_WORDING.test(text)) add(node, 'developerWording', text)
    }
    // Headings, titles, buttons: their rendered text; headings: no icon inside.
    if (ts.isJsxElement(node)) {
      const tag = tagOf(node.openingElement)
      if (read(node.openingElement)) {
        const rendered = titleCased(elementTexts(node, read))
        if (rendered !== undefined) add(node, 'sentenceCase', rendered)
      }
      if (HEADINGS.has(tag)) {
        const icons: ts.Node[] = []
        // An icon inside a control the heading wraps (a disclosure button's caret) is the control's
        // affordance, not the heading's icon.
        const find = (n: ts.Node) => {
          if (ts.isJsxElement(n) && CONTROLS.has(tagOf(n.openingElement))) return
          if ((ts.isJsxSelfClosingElement(n) || ts.isJsxOpeningElement(n)) && /Icon$/.test(tagOf(n))) icons.push(n)
          ts.forEachChild(n, find)
        }
        node.children.forEach(find)
        for (const icon of icons) add(icon, 'headingIcon', `<${tagOf(icon as ts.JsxOpeningLikeElement)}> in <${tag}>`)
      }
    }
    // A component's title (GuidanceCard, Notice, Modal, SecondaryHeader and the discovered ones), and
    // any element's aria-label.
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      for (const name of reach.titles.has(tagOf(node)) ? ['title', 'aria-label'] : ['aria-label']) {
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
  'app/admin/feedback/page.tsx': { sentenceCase: 1 }, // brand-admin (#1309)
  'app/admin/invites/page.tsx': { sentenceCase: 1 }, // brand-admin (#1309)
  'app/contact/page.tsx': { sentenceCase: 3 }, // brand-contact-security-presentation (#1303)
  'app/dashboard/error.tsx': { sentenceCase: 4 }, // brand-dashboard-watchlist (#1290, DSW-12)
  'app/dashboard/settings/page.tsx': { sentenceCase: 1 }, // brand-settings-subscriptions (#1291)
  'app/error.tsx': { sentenceCase: 1 }, // brand-chrome-primitives (#1289; the development-only details panel)
  'app/filing/[id]/page.tsx': { sentenceCase: 2 }, // brand-metadata-social (#1312; meta titles)
  'app/privacy/page.tsx': { sentenceCase: 16 }, // founder-gated, legal page: its headings wait on the founder (legalDates bump)
  'app/search/page.tsx': { sentenceCase: 1 }, // brand-calendar-search (#1301; meta title)
  'app/security/page.tsx': { sentenceCase: 12 }, // founder-gated, legal page: the /security recase lands with its claims (UA ids)
  'app/terms/page.tsx': { sentenceCase: 4 }, // founder-gated, legal page: its headings wait on the founder (legalDates bump)
  'app/waitlist/page.tsx': { buzzword: 1 }, // brand-public-pages (#1311; BG-23, "clarity")
  'components/CookieConsent.tsx': { sentenceCase: 7 }, // brand-chrome-primitives (#1289; the ModalHeader's "Cookie Preferences" is the seventh)
  'features/admin/components/ShareInvite.tsx': { sentenceCase: 1 }, // a known false positive, no PR: the aria-label "Share invite via Messages" names Apple's app; the entry leaves when the label changes
  'features/contact/components/ContactForm.tsx': { sentenceCase: 1 }, // brand-contact-security-presentation (#1303)
  'features/feedback/components/FeedbackWidget.tsx': { emoji: 3 }, // brand-chrome-primitives (#1289)
  'features/filings/components/copilot/FilingWorkspace.tsx': { sentenceCase: 1 }, // the Copilot rail's next change (no open PR edits this file; the aria-label "Filing source and Ask")
  'features/filings/components/copilot/PaneResizer.tsx': { sentenceCase: 1 }, // brand-copilot (#1295; the aria-label "Resize Copilot panel")
  'features/fundamentals/components/FundamentalsTrendChart.tsx': { sentenceCase: 1 }, // brand-company-page (#1292)
  'features/insiders/components/InsiderActivityPanel.tsx': { sentenceCase: 2 }, // brand-company-page (#1292)
  'features/marketing/components/ProDepth.tsx': { sentenceCase: 1 }, // brand-public-pages (#1311; the FeatureRow title "Change Report")
  'features/peers/components/PeerComparisonPanel.tsx': { sentenceCase: 1 }, // brand-company-page (#1292)
  'features/settings/components/NotificationPreferencesForm.tsx': { sentenceCase: 1, headingIcon: 1 }, // brand-settings-subscriptions (#1291, DSW-13)
  'features/subscriptions/components/PeekLocked.tsx': { buzzword: 1 }, // brand-settings-subscriptions (#1291; DSW-11, "unlock")
  'features/summaries/components/SummaryActionsBar.tsx': { sentenceCase: 1 }, // brand-filing-page (#1293)
  'lib/api/client.ts': { developerWording: 1 }, // brand-chrome-primitives (#1289; CAL-12, "backend API")
}
const VOICE_RESIDUE_MAX = { entries: 27, violations: 71 }

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
      '    </div>',
      '  )',
      '}',
      'function Panel({ title }: { title: string }) {',
      '  return <h5>{title}</h5>',
      '}',
      'const Cta = ({ children }: { children: ReactNode }) => <Link href="/" className={buttonVariants()}>{children}</Link>',
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
    ])
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
