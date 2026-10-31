import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Tailwind generates only the class names its extractor finds whole in the source
 * (lessons/frontend-tailwind-classes-are-written-whole.md). A class assembled from an interpolated
 * prefix (`${NARROW}h-auto`), a suffix (`text-${tone}`), a concatenation (`NARROW + 'h-auto'`,
 * `['[@media(max-width:24rem)]:', 'h-auto'].join('')`) or a map over fragments
 * (`['h-auto'].map((c) => `${NARROW}${c}`)`) looks right in a class string, passes every test that
 * reads the string, and emits no CSS. This gate reads every file under app, components, features,
 * hooks and lib; the self-check below scores it on planted forms of the rule, look-alikes and gaps.
 *
 * A template literal fails on an interpolation that resolves to a variant prefix (a string ending in
 * ":", a chain of `token:` segments with no space); on an interpolation that may end inside a token
 * running straight into a utility token (hyphenated, or one of the single-word utilities, also behind
 * an interpolated variant name: `${bp}:flex`); and on a utility stem (`text-`, `bg-`, …) running
 * straight into an interpolation, written before it or held by the interpolation before it.
 *
 * A concatenation is read as parts with a seam between each two: `+`, `+=`, a string's `.concat(…)`
 * and the `.join(…)` of an array the file holds (a literal, a spread of one opened in place, through a
 * same-file const, `.filter` and an array's `.concat`). A join's separator is glued to the literal
 * element before it, or after an interpolated one to the literal after it, so `['text', tone].join('-')`
 * reads as `'text-' + tone`; a separator the file does not hold is a part that may be empty. A seam
 * fails when its left part resolves to a variant prefix and its right part does not start with
 * whitespace; when its right part is a literal that starts with a utility token and its left part is
 * not a literal and may end inside a token; and when its left part ends in a utility stem and its right
 * part is not a literal. Every check reads what is before a seam or an interpolation through same-file
 * consts (the first declaration of the name, `as const` included), conditionals and concatenations, and
 * what is after it as written.
 *
 * Identifiers, keys, URLs and measurements (`${id}-row`, `[ticker, 'summary-v1'].join(':')`,
 * `${base}/api`, `${n}px`, `base + ' h-auto'`) do not match: the token after a seam must begin with a
 * letter and be a utility, and the stem before it must be a known family followed by its hyphen. A part
 * that can only end in whitespace or nothing (`${hint ? 'mt-1.5 ' : ''}inline-flex`,
 * `(open ? 'ring-2 ' : '') + 'h-auto'`) leaves the next token whole. Out of reach, each planted as a gap:
 * an array or a string the file does not hold (a `.map` result; a parameter's `.concat`, which may be an
 * array's, adding a whole class); a `.reduce` that joins its parameters; a utility held in a const after
 * a seam (`p + H_AUTO`); a variant prefix at the end of a longer literal (`'mt-2 sm:' + 'h-auto'`), since
 * a prefix is read as a whole value so that prose ending in a colon is not one; and a variant in a
 * template's text before an interpolation (`sm:${utility}`, `${bp}:${utility}`), the shape of a key
 * (`summary:${id}`).
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const UTILITY_AFTER = /^[a-z][a-z0-9]*(?:-[a-z0-9.[\]/%]+)+(?=\s|$)/
/** The utility families, as the stem before their hyphen. */
const STEMS =
  'h|w|min-h|min-w|max-w|max-h|p[xytblr]?|m[xytblr]?|gap|space-[xy]|text|bg|border|rounded|ring|shadow|font|leading|tracking|whitespace|opacity|z|inset|top|left|right|bottom|translate-[xy]|scale|rotate|grid-cols|grid-rows|col|row|order|basis|flex|justify|items|self|place|content|duration|delay|ease|fill|stroke|outline|decoration|underline-offset|aspect|object|overflow|cursor|select|pointer-events|transition|animate|divide|from|via|to|line-clamp|indent|columns|size'
const STEM_BEFORE = new RegExp(`(?:^|\\s)-?(?:[a-z0-9[\\]().:@-]+:)?(?:${STEMS})-\\[?$`)
/** The heads a hyphenated utility can start with: the families above, and the ones that only ever
    appear whole (`inline-flex`, `shrink-0`, `break-words`, `line-through`, `backdrop-blur`, …). */
const KNOWN_FAMILY = new RegExp(
  `^(?:${STEMS}|inline|shrink|grow|break|line|float|clear|list|not|table|backdrop|blur|drop|origin|skew|appearance|scroll|snap|overscroll|touch|will|mix|accent|caret|box|place|sr|truncate|isolation|visible|invisible|collapse|uppercase|lowercase|capitalize|normal|antialiased|italic|tabular|slashed|lining|oldstyle|proportional|diagonal|stacked|ordinal|hyphens|align|vertical|resize|outline|contain|content|forced|motion|pointer|user)-`,
)

const SINGLE_UTILITIES = new Set([
  'hidden', 'flex', 'grid', 'block', 'inline', 'contents', 'relative', 'absolute', 'fixed', 'sticky', 'static', 'visible',
  'invisible', 'truncate', 'uppercase', 'lowercase', 'capitalize', 'italic', 'underline', 'overline', 'antialiased',
  'isolate', 'container', 'rounded', 'border', 'shadow', 'ring', 'outline', 'transition', 'resize', 'table', 'grow',
  'shrink', 'collapse', 'tabular-nums', 'sr-only',
])
/** Whether text begins with a utility token: a hyphenated one, a single-word one followed by a space or
    the end, or either behind a ":" (an interpolated variant name, `${bp}:flex`, or a chain of them,
    `${bp}:hover:bg-brand`), where the hyphenated token must start with a known family so a colon-joined
    key (`${ticker}:summary-v1`, `${ns}:cache:summary-v1`) is not one. */
function utilityHead(text: string): string | null {
  const colon = text.startsWith(':')
  const chain = colon ? /^:(?:[a-z0-9[\]().@=/&>_!-]+:)*/.exec(text)![0] : ''
  const after = colon ? text.slice(chain.length) : text
  const bang = after.startsWith('!') ? '!' : ''
  const rest = after.slice(bang.length)
  const hyphenated = UTILITY_AFTER.exec(rest)
  if (hyphenated && (!colon || KNOWN_FAMILY.test(hyphenated[0]))) return chain + bang + hyphenated[0]
  const word = /^[a-z][a-z0-9-]*(?=\s|$)/.exec(rest)
  return word && SINGLE_UTILITIES.has(word[0]) ? chain + bang + word[0] : null
}

const isStringy = (e: ts.Expression): e is ts.StringLiteral | ts.NoSubstitutionTemplateLiteral =>
  ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)

/** An expression with its parentheses, `as`, `satisfies`, `!` and type assertions taken off. */
function unwrap(e: ts.Expression): ts.Expression {
  while (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isNonNullExpression(e) || ts.isTypeAssertionExpression(e)) e = e.expression
  return e
}

const declared = new WeakMap<ts.SourceFile, Map<string, ts.Expression>>()
/** The value a name is given where the file first declares it, indexed once per file. */
function constValue(name: ts.Identifier, sf: ts.SourceFile): ts.Expression | undefined {
  let values = declared.get(sf)
  if (!values) {
    const found = new Map<string, ts.Expression>()
    const index = (n: ts.Node) => {
      if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer && !found.has(n.name.text)) found.set(n.name.text, n.initializer)
      ts.forEachChild(n, index)
    }
    index(sf)
    declared.set(sf, (values = found))
  }
  return values.get(name.text)
}

/** The strings an expression is known to end with: a literal's text, a template's last text (or its last
    interpolation's, when that text is empty), a conditional's branches, the right of `+`, a same-file const's. */
function knownEndings(e: ts.Expression, sf: ts.SourceFile, depth = 0): string[] {
  if (depth > 4) return []
  e = unwrap(e)
  if (isStringy(e)) return [e.text]
  if (ts.isTemplateExpression(e)) {
    const last = e.templateSpans[e.templateSpans.length - 1]
    return last.literal.text === '' ? knownEndings(last.expression, sf, depth + 1) : [last.literal.text]
  }
  if (ts.isConditionalExpression(e)) return [...knownEndings(e.whenTrue, sf, depth + 1), ...knownEndings(e.whenFalse, sf, depth + 1)]
  if (ts.isBinaryExpression(e) && e.operatorToken.kind === ts.SyntaxKind.PlusToken) return knownEndings(e.right, sf, depth + 1)
  if (ts.isIdentifier(e)) {
    const value = constValue(e, sf)
    return value ? knownEndings(value, sf, depth + 1) : []
  }
  return []
}

/** Whether every value an expression can take ends in whitespace or is empty, so the token after it starts
    whole, read like knownEndings (both sides of `||` and `??` too); anything it cannot read may end inside one. */
function endsClean(e: ts.Expression, sf: ts.SourceFile, depth = 0): boolean {
  if (depth > 4) return false
  e = unwrap(e)
  if (isStringy(e)) return e.text === '' || /\s$/.test(e.text)
  if (ts.isTemplateExpression(e)) {
    const last = e.templateSpans[e.templateSpans.length - 1]
    return last.literal.text === '' ? endsClean(last.expression, sf, depth + 1) : /\s$/.test(last.literal.text)
  }
  if (ts.isConditionalExpression(e)) return endsClean(e.whenTrue, sf, depth + 1) && endsClean(e.whenFalse, sf, depth + 1)
  if (ts.isBinaryExpression(e)) {
    const op = e.operatorToken.kind
    if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return endsClean(e.left, sf, depth + 1) && endsClean(e.right, sf, depth + 1)
    if (op === ts.SyntaxKind.PlusToken) return endsClean(e.right, sf, depth + 1)
  }
  if (ts.isIdentifier(e)) {
    const value = constValue(e, sf)
    return value !== undefined && endsClean(value, sf, depth + 1)
  }
  return false
}

/** A variant prefix: a chain of `token:` segments with no space (`sm:`, `dark:hover:`,
    `[@media(max-width:24rem)]:`), the surest sign of a composed class. Prose that ends in a colon has
    spaces in it and is not one. */
const isVariant = (text: string) => /^(?:[a-z0-9[\]().:@=/-]+:)+$/.test(text)
const variantPrefix = (e: ts.Expression, sf: ts.SourceFile) => knownEndings(e, sf).some(isVariant)

/** A literal's text, through parentheses, `as` and a same-file const, or null. */
function heldLiteral(e: ts.Expression, sf: ts.SourceFile, depth = 0): string | null {
  if (depth > 4) return null
  e = unwrap(e)
  if (isStringy(e)) return e.text
  if (!ts.isIdentifier(e)) return null
  const value = constValue(e, sf)
  return value ? heldLiteral(value, sf, depth + 1) : null
}

/** The elements of an array the file holds: an array literal (a spread of one opened in place, any other
    spread kept as one part), through parentheses, `as` and a same-file const, and the receiver of
    `.filter(…)`, which keeps their order, or of an array's `.concat(…)`, which adds its arguments after them. */
function heldArray(e: ts.Expression, sf: ts.SourceFile, depth = 0): ts.Expression[] | null {
  if (depth > 4) return null
  e = unwrap(e)
  if (ts.isArrayLiteralExpression(e)) return e.elements.flatMap((el) => (ts.isSpreadElement(el) ? (heldArray(el.expression, sf, depth + 1) ?? [el.expression]) : [el]))
  if (ts.isIdentifier(e)) {
    const value = constValue(e, sf)
    return value ? heldArray(value, sf, depth + 1) : null
  }
  if (ts.isCallExpression(e) && ts.isPropertyAccessExpression(e.expression)) {
    const held = heldArray(e.expression.expression, sf, depth + 1)
    if (held && e.expression.name.text === 'filter') return held
    if (held && e.expression.name.text === 'concat') return [...held, ...e.arguments.flatMap((arg) => heldArray(arg, sf, depth + 1) ?? [arg])]
  }
  return null
}

/** Whether the file holds an expression as a string: a literal or template, a `+` with a string on one side,
    any `.join`, a string's `.concat`, a conditional between strings, a same-file const holding one. */
function heldString(e: ts.Expression, sf: ts.SourceFile, depth = 0): boolean {
  if (depth > 4) return false
  e = unwrap(e)
  if (isStringy(e) || ts.isTemplateExpression(e)) return true
  if (ts.isBinaryExpression(e) && e.operatorToken.kind === ts.SyntaxKind.PlusToken) return heldString(e.left, sf, depth + 1) || heldString(e.right, sf, depth + 1)
  if (ts.isConditionalExpression(e)) return heldString(e.whenTrue, sf, depth + 1) && heldString(e.whenFalse, sf, depth + 1)
  if (ts.isIdentifier(e)) {
    const value = constValue(e, sf)
    return value !== undefined && heldString(value, sf, depth + 1)
  }
  if (ts.isCallExpression(e) && ts.isPropertyAccessExpression(e.expression)) {
    const method = e.expression.name.text
    return method === 'join' || (method === 'concat' && heldString(e.expression.expression, sf, depth + 1))
  }
  return false
}

/** One part of a concatenation: an expression as written, or text the walk assembled (a join's separator
    glued to a literal element). */
type Part = ts.Expression | string
const literalText = (part: Part): string | null => {
  if (typeof part === 'string') return part
  const e = unwrap(part)
  return isStringy(e) ? e.text : null
}

/** The parts a `.join` concatenates, or null when the file does not hold the array (see the header). */
function joinParts(call: ts.CallExpression, receiver: ts.Expression, sf: ts.SourceFile): Part[] | null {
  const elements = heldArray(receiver, sf)
  if (!elements) return null
  const arg = call.arguments[0]
  const separator: Part = arg === undefined ? ',' : (heldLiteral(arg, sf) ?? arg)
  const parts: Part[] = []
  elements.forEach((element, i) => {
    let part: Part = literalText(element) ?? element
    if (i > 0 && separator !== '') {
      const last = parts[parts.length - 1]
      if (typeof separator !== 'string') parts.push(separator)
      else if (typeof last === 'string') parts[parts.length - 1] = last + separator
      else if (typeof part === 'string') part = separator + part
      else parts.push(separator)
    }
    parts.push(part)
  })
  return parts
}

/** What fails at the seam where `left` runs into `right` (the rules are in the header), as messages. */
function seams(left: Part, right: Part, sf: ts.SourceFile): string[] {
  const after = literalText(right)
  const head = after === null ? null : utilityHead(after)
  const endings = typeof left === 'string' ? [left] : knownEndings(left, sf)
  const found: string[] = []
  if (endings.some(isVariant) && !(after !== null && /^\s/.test(after))) {
    found.push(`"${typeof left === 'string' ? `'${left}'` : left.getText(sf)} + …" is a variant prefix`)
  } else if (head && typeof left !== 'string' && literalText(left) === null && !endsClean(left, sf)) {
    found.push(`"… + '${head}'"`)
  }
  const stem = after === null ? endings.find((text) => STEM_BEFORE.test(text)) : undefined
  if (stem !== undefined) found.push(`"'${stem.trim().split(/\s+/).pop()}' + …"`)
  return found
}

/** Every composed class the gate names in one file's source, as `file:line "…"`. */
function offendersIn(source: string, rel: string): string[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const offenders: string[] = []
  const at = (n: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1}`
  const readParts = (node: ts.Node, parts: Part[], form: string) => {
    for (let i = 1; i < parts.length; i++) for (const found of seams(parts[i - 1], parts[i], sf)) offenders.push(`${at(node)} ${found}${form}`)
  }
  const visit = (node: ts.Node) => {
    if (ts.isTemplateExpression(node)) {
      let before = node.head.text
      let previous: ts.Expression | undefined
      for (const span of node.templateSpans) {
        const after = span.literal.text
        const head = utilityHead(after)
        if (variantPrefix(span.expression, sf)) offenders.push(`${at(span)} "\${…}" is a variant prefix`)
        else if (head && !endsClean(span.expression, sf)) offenders.push(`${at(span)} "\${…}${head}"`)
        const stem = before === '' && previous ? knownEndings(previous, sf).find((text) => STEM_BEFORE.test(text)) : STEM_BEFORE.test(before) ? before : undefined
        if (stem !== undefined) offenders.push(`${at(span)} "${stem.trim().split(/\s+/).pop()}\${…}"`)
        before = after
        previous = span.expression
      }
    }
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) readParts(node, [node.left, node.right], '')
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusEqualsToken) readParts(node, [node.left, node.right], ' (+=)')
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)) {
      const receiver = node.expression.expression
      if (node.expression.name.text === 'join') {
        const parts = joinParts(node, receiver, sf)
        if (parts) readParts(node, parts, ' (.join)')
      }
      if (node.expression.name.text === 'concat' && heldString(receiver, sf)) readParts(node, [receiver, ...node.arguments], ' (.concat)')
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return offenders
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

/** Planted forms, one per line, read as a file under components/. The mark ending a line says what the gate
    must do with it; a gap is a form the rule forbids that the gate passes, each named in the header. */
const FORMS = [
  "const NARROW = '[@media(max-width:24rem)]:'",
  "const TIGHT = '[@media(max-width:24rem)]:' as const",
  "const STEM = 'text-'",
  "const H_AUTO = 'h-auto'",
  "const EMPTY = ''",
  "const PARTS = [NARROW, 'min-h-10'] as const",
  'export const t1 = `${NARROW}h-auto` // flag',
  'export const t2 = (tone: string) => `text-${tone}` // flag',
  'export const t3 = (bp: string) => `${bp}:flex ${bp}:hover:bg-brand` // flag',
  "export const t4 = ['h-auto'].map((c) => `${NARROW}${c}`) // flag",
  'export const t5 = String.raw`${NARROW}h-auto` // flag',
  "export const p1 = NARROW + 'h-auto' // flag",
  "export const p2 = (tone: string) => 'text-' + tone // flag",
  "export const p3 = (p: string) => p + 'h-auto' // flag",
  "export const j1 = ['[@media(max-width:24rem)]:', 'h-auto'].join('') // flag",
  "export const j2 = [NARROW, 'h-auto'].join('') // flag",
  "export const j3 = PARTS.join('') // flag",
  "export const j4 = [NARROW, 'py-2'].filter(Boolean).join(EMPTY) // flag",
  "export const j5 = (tone: string) => ['text', tone].join('-') // flag",
  "export const j6 = (tone: string) => ['text-', tone].join('') // flag",
  "export const j7 = (p: string) => [p, 'h-auto'].join('') // flag",
  "export const j8 = ['sm', 'h-auto'].join(':') // flag",
  "export const j9 = (bp: string) => [bp, 'flex'].join(':') // flag",
  "export const j10 = [...PARTS, 'h-auto'].join('') // flag",
  "export const j11 = (sep: string) => [NARROW, 'h-auto'].join(sep) // flag",
  "export const j12 = [NARROW].concat(['h-auto']).join('') // flag",
  "export const j13 = [NARROW, 'h-auto'].join() // flag",
  "export const c1 = NARROW.concat('h-auto') // flag",
  "export const c2 = ''.concat(NARROW, 'h-auto') // flag",
  "export function a1() { let cls = NARROW; cls += 'h-auto'; return cls } // flag",
  "export function a2(tone: string) { let tint = 'bg-'; tint += tone; return tint } // flag",
  'export const v1 = [\'h-auto\'].map((c) => `${TIGHT}${c}`) // flag',
  'export const v2 = (tone: string) => STEM + tone // flag',
  'export const v3 = (tone: string) => `${STEM}${tone}` // flag',
  "export const k1 = ['h-10', 'w-full'].join(' ') // clean",
  "export const k2 = [...PARTS, 'h-auto'].join(' ') // clean",
  "export const k3 = (id: string) => [id, 'row'].join('-') // clean",
  "export const k4 = (base: string) => [base, 'api', 'v1'].join('/') // clean",
  "export const k5 = (n: number) => [n, 'px'].join('') // clean",
  "export const k6 = (ticker: string) => [ticker, 'summary-v1'].join(':') // clean",
  "export const k7 = ['Revenue', 'Net income'].join(', ') // clean",
  "export const k8 = (open: boolean) => [open ? 'ring-2 ' : '', 'h-auto'].join('') // clean",
  "export const k9 = 'flex'.concat(' ', 'h-auto') // clean",
  "export const k10 = (classes: string[]) => classes.concat('h-auto') // clean",
  'export function k11() { let n = 0; n += 1; return n } // clean',
  'export const k12 = (id: string) => `${id}-row ${id}/api` // clean',
  'export const k13 = (n: number) => `${n}px` // clean',
  "export const k14 = (base: string) => base + ' h-auto' // clean",
  "export const k15 = (hint: boolean) => `${hint ? 'mt-1.5 ' : ''}inline-flex` // clean",
  'export const k16 = (ticker: string) => `${ticker}:summary-v1` // clean',
  "export const k17 = (label: string) => 'Note: ' + label // clean",
  "export const k18 = (open: boolean) => (open ? 'ring-2 ' : '') + 'h-auto' // clean",
  "export const g1 = [NARROW, 'h-auto'].map((c) => c).join('') // gap",
  "export const g2 = [NARROW, 'h-auto'].reduce((a, c) => a + c, '') // gap",
  "export const g3 = (p: string) => p.concat('h-auto') // gap",
  'export const g4 = (p: string) => p + H_AUTO // gap',
  "export const g5 = 'mt-2 sm:' + 'h-auto' // gap",
  'export const g6 = (utility: string, bp: string) => `sm:${utility} ${bp}:${utility}` // gap',
]
const PROBE = 'components/zzfixture/Probe.tsx'

describe('every Tailwind class is written whole', () => {
  it('nothing under app, components, features, hooks or lib composes a class from an interpolation or a concatenation', () => {
    const files = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))
    expect(files.length, 'the walk reads the tree').toBeGreaterThan(100)
    const offenders = files.flatMap((file) => offendersIn(readFileSync(file, 'utf8'), path.relative(ROOT, file)))
    expect(offenders, 'write the whole class per case and let a map choose between whole strings').toEqual([])
  })

  it('the scan catches what it is for (a self-check on planted forms)', () => {
    const found = offendersIn(FORMS.join('\n'), PROBE)
    const lineOf = (offender: string) => Number(/:(\d+) /.exec(offender)![1])
    const marked = (mark: string) => FORMS.flatMap((line, i) => (line.endsWith(`// ${mark}`) ? [i + 1] : []))
    // Every line marked flag is named and nothing else is: no look-alike fails and every gap still passes.
    expect([...new Set(found.map(lineOf))]).toEqual(marked('flag'))
    expect([marked('flag').length, marked('clean').length, marked('gap').length]).toEqual([28, 18, 6])
    expect(found).toEqual([
      `${PROBE}:7 "\${…}" is a variant prefix`,
      `${PROBE}:8 "text-\${…}"`,
      `${PROBE}:9 "\${…}:flex"`,
      `${PROBE}:9 "\${…}:hover:bg-brand"`,
      `${PROBE}:10 "\${…}" is a variant prefix`,
      `${PROBE}:11 "\${…}" is a variant prefix`,
      `${PROBE}:12 "NARROW + …" is a variant prefix`,
      `${PROBE}:13 "'text-' + …"`,
      `${PROBE}:14 "… + 'h-auto'"`,
      // A join, a string's concat and += are read as the same seams as +.
      `${PROBE}:15 "'[@media(max-width:24rem)]:' + …" is a variant prefix (.join)`,
      `${PROBE}:16 "NARROW + …" is a variant prefix (.join)`,
      `${PROBE}:17 "NARROW + …" is a variant prefix (.join)`,
      `${PROBE}:18 "NARROW + …" is a variant prefix (.join)`,
      `${PROBE}:19 "'text-' + …" (.join)`,
      `${PROBE}:20 "'text-' + …" (.join)`,
      `${PROBE}:21 "… + 'h-auto'" (.join)`,
      `${PROBE}:22 "'sm:' + …" is a variant prefix (.join)`,
      `${PROBE}:23 "… + ':flex'" (.join)`,
      `${PROBE}:24 "NARROW + …" is a variant prefix (.join)`,
      // A separator the file does not hold may be empty, so both of its seams are read.
      `${PROBE}:25 "NARROW + …" is a variant prefix (.join)`,
      `${PROBE}:25 "… + 'h-auto'" (.join)`,
      `${PROBE}:26 "NARROW + …" is a variant prefix (.join)`,
      `${PROBE}:27 "NARROW + …" is a variant prefix (.join)`,
      `${PROBE}:28 "NARROW + …" is a variant prefix (.concat)`,
      `${PROBE}:29 "NARROW + …" is a variant prefix (.concat)`,
      `${PROBE}:30 "cls + …" is a variant prefix (+=)`,
      `${PROBE}:31 "'bg-' + …" (+=)`,
      // A prefix or a stem held in a const is read through the binding, `as const` included.
      `${PROBE}:32 "\${…}" is a variant prefix`,
      `${PROBE}:33 "'text-' + …"`,
      `${PROBE}:34 "text-\${…}"`,
    ])
  })
})
